package engine

import (
	"fmt"
	"sync"
	"time"

	"github.com/openclaw/skills/quant-researcher/internal/metrics"
	"github.com/openclaw/skills/quant-researcher/internal/risk"
	"github.com/openclaw/skills/quant-researcher/pkg/types"
)

// BacktestRunner manages backtest execution
type BacktestRunner struct {
	engine          *ExecutionEngine
	riskManager     *risk.RiskManager
	metrics         *metrics.PerformanceMetrics
	slippageModel   metrics.SlippageModel
	
	// Backtest state
	startTime       int64
	endTime         int64
	initialCash     float64
	currentTime     int64
	
	// Symbol data
	symbolData      map[string][]types.PricePoint
	
	// Results
	trades          []metrics.Trade
	mu              sync.RWMutex
}

// BacktestConfig configures the backtest
type BacktestConfig struct {
	StartTime       int64
	EndTime         int64
	InitialCash     float64
	Symbols         []string
	SlippageModel   metrics.SlippageModel
	RiskConfig      *risk.Config
}

func NewBacktestRunner(cfg *BacktestConfig) *BacktestRunner {
	engineCfg := &Config{
		InitialCash: cfg.InitialCash,
		BufferSize:  1 << 20,
		Workers:     1, // Single threaded for deterministic backtests
	}
	
	riskCfg := cfg.RiskConfig
	if riskCfg == nil {
		riskCfg = risk.DefaultConfig()
	}
	
	engine := NewExecutionEngine(engineCfg)
	portfolio := engine.GetPortfolio()
	riskManager := risk.NewRiskManager(riskCfg, portfolio)
	
	slippage := cfg.SlippageModel
	if slippage == nil {
		slippage = &metrics.FixedSlippageModel{SlippageBps: 1.0}
	}
	
	return &BacktestRunner{
		engine:        engine,
		riskManager:   riskManager,
		metrics:       metrics.NewPerformanceMetrics(),
		slippageModel: slippage,
		startTime:     cfg.StartTime,
		endTime:       cfg.EndTime,
		initialCash:   cfg.InitialCash,
		symbolData:    make(map[string][]types.PricePoint),
		trades:        make([]metrics.Trade, 0),
	}
}

// LoadData loads historical data for backtesting
func (br *BacktestRunner) LoadData(symbol string, data []types.PricePoint) {
	br.mu.Lock()
	defer br.mu.Unlock()
	br.symbolData[symbol] = data
	br.engine.Subscribe(symbol)
}

// Run executes the backtest
func (br *BacktestRunner) Run(strategy Strategy) (*BacktestResult, error) {
	br.mu.Lock()
	defer br.mu.Unlock()
	
	// Register strategy with engine
	br.engine.RegisterHandler(strategy)
	
	// Start engine
	if err := br.engine.Start(); err != nil {
		return nil, fmt.Errorf("failed to start engine: %w", err)
	}
	defer br.engine.Stop()
	
	// Process all data chronologically
	allEvents := br.mergeData()
	
	startTime := time.Now()
	
	for _, event := range allEvents {
		br.currentTime = event.Timestamp
		
		// Update risk manager ATR
		br.riskManager.UpdateATR(event.Symbol, event.Price*1.001, event.Price*0.999, event.Price)
		
		// Update portfolio prices
		br.engine.GetPortfolio().UpdatePrice(event.Symbol, event.Price)
		
		// Process tick
		br.engine.SubmitTick(event.Symbol, event.Price, event.Volume, event.Bid, event.Ask)
		
		// Record equity curve point periodically
		br.metrics.AddEquityPoint(metrics.EquityPoint{
			Timestamp: event.Timestamp,
			Equity:    br.engine.GetPortfolio().TotalValue,
		})
	}
	
	duration := time.Since(startTime)
	
	// Calculate metrics
	perfMetrics := br.metrics.CalculateAll(0.02) // 2% risk-free rate
	
	return &BacktestResult{
		Metrics:         perfMetrics,
		FinalEquity:     br.engine.GetPortfolio().TotalValue,
		TotalReturn:     (br.engine.GetPortfolio().TotalValue - br.initialCash) / br.initialCash,
		Trades:          br.trades,
		Duration:        duration,
		EngineMetrics:   br.engine.GetMetrics(),
	}, nil
}

// mergeData merges all symbol data into chronological events
func (br *BacktestRunner) mergeData() []types.TickEvent {
	var allEvents []types.TickEvent
	
	for symbol, data := range br.symbolData {
		for _, point := range data {
			if point.Timestamp >= br.startTime && point.Timestamp <= br.endTime {
				allEvents = append(allEvents, types.TickEvent{
					Timestamp: point.Timestamp,
					Symbol:    symbol,
					Price:     point.Price,
					Volume:    point.Volume,
					Bid:       point.Bid,
					Ask:       point.Ask,
				})
			}
		}
	}
	
	// Sort by timestamp
	// Using simple bubble sort for clarity - replace with sort.Slice for production
	for i := 0; i < len(allEvents); i++ {
		for j := i + 1; j < len(allEvents); j++ {
			if allEvents[j].Timestamp < allEvents[i].Timestamp {
				allEvents[i], allEvents[j] = allEvents[j], allEvents[i]
			}
		}
	}
	
	return allEvents
}

// ExecuteOrder simulates order execution with slippage
func (br *BacktestRunner) ExecuteOrder(order *types.OrderEvent, marketPrice, volume float64) (*types.FillEvent, error) {
	// Validate with risk manager
	if ok, reason := br.riskManager.ValidateOrder(order); !ok {
		return nil, fmt.Errorf("risk check failed: %s", reason)
	}
	
	// Calculate slippage
	slippage := br.slippageModel.CalculateSlippage(order, marketPrice, volume)
	
	// Apply slippage based on side
	fillPrice := marketPrice
	if order.Side == types.SideBuy {
		fillPrice += slippage
	} else {
		fillPrice -= slippage
	}
	
	// Calculate fee (e.g., 0.1%)
	fee := fillPrice * order.Quantity * 0.001
	
	fill := &types.FillEvent{
		Timestamp: br.currentTime,
		OrderID:   order.ID,
		Symbol:    order.Symbol,
		Side:      order.Side,
		Price:     fillPrice,
		Quantity:  order.Quantity,
		Fee:       fee,
		Slippage:  slippage,
	}
	
	// Record trade
	pnl := br.calculatePnL(order, fill)
	br.trades = append(br.trades, metrics.Trade{
		Timestamp: br.currentTime,
		Symbol:    order.Symbol,
		Side:      order.Side,
		Price:     fillPrice,
		Quantity:  order.Quantity,
		PnL:       pnl,
		Fee:       fee,
		Slippage:  slippage,
	})
	
	// Update risk manager
	br.riskManager.UpdateTradeStats(pnl)
	
	// Submit fill to engine
	br.engine.SubmitFill(fill)
	
	return fill, nil
}

func (br *BacktestRunner) calculatePnL(order *types.OrderEvent, fill *types.FillEvent) float64 {
	portfolio := br.engine.GetPortfolio()
	
	if order.Side == types.SideSell {
		if pos, exists := portfolio.Positions[order.Symbol]; exists {
			// Closing position - realized PnL
			return (fill.Price - pos.AvgEntryPrice) * fill.Quantity
		}
	}
	
	return 0 // No PnL for opening positions or short sales without position
}

// BacktestResult contains backtest results
type BacktestResult struct {
	Metrics       metrics.PerformanceReport
	FinalEquity   float64
	TotalReturn   float64
	Trades        []metrics.Trade
	Duration      time.Duration
	EngineMetrics EngineMetrics
}

// Strategy interface for backtesting
type Strategy interface {
	OnTick(event *types.TickEvent)
	OnSignal(event *types.SignalEvent)
	OnOrder(event *types.OrderEvent)
	OnFill(event *types.FillEvent)
}

// ParallelBacktestRunner runs multiple backtests in parallel
type ParallelBacktestRunner struct {
	numWorkers int
}

func NewParallelBacktestRunner(numWorkers int) *ParallelBacktestRunner {
	if numWorkers <= 0 {
		numWorkers = 4
	}
	return &ParallelBacktestRunner{numWorkers: numWorkers}
}

// RunParallel runs multiple backtest configurations in parallel
func (pbr *ParallelBacktestRunner) RunParallel(configs []BacktestConfig, strategyFactory func() Strategy) []BacktestResult {
	results := make([]BacktestResult, len(configs))
	
	var wg sync.WaitGroup
	semaphore := make(chan struct{}, pbr.numWorkers)
	
	for i, cfg := range configs {
		wg.Add(1)
		semaphore <- struct{}{}
		
		go func(idx int, config BacktestConfig) {
			defer wg.Done()
			defer func() { <-semaphore }()
			
			runner := NewBacktestRunner(&config)
			strategy := strategyFactory()
			
			result, err := runner.Run(strategy)
			if err != nil {
				// Log error and continue
				return
			}
			
			results[idx] = *result
		}(i, cfg)
	}
	
	wg.Wait()
	return results
}