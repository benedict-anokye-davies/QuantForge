package metrics

import (
	"fmt"
	"math"
	"sort"
	"sync"
	"time"

	"github.com/openclaw/skills/quant-researcher/pkg/types"
)

// PerformanceMetrics calculates trading performance metrics
type PerformanceMetrics struct {
	// Trade history
	trades     []Trade
	equityCurve []EquityPoint
	
	// Calculated metrics
	sharpeRatio    float64
	sortinoRatio   float64
	calmarRatio    float64
	maxDrawdown    float64
	maxDrawdownPct float64
	winRate        float64
	profitFactor   float64
	expectancy     float64
	var95          float64
	var99          float64
	cvar95         float64
	cvar99         float64
	
	// Transaction costs
	totalSlippage  float64
	totalFees      float64
	
	mu             sync.RWMutex
}

type Trade struct {
	Timestamp int64
	Symbol    string
	Side      types.OrderSide
	Price     float64
	Quantity  float64
	PnL       float64
	Fee       float64
	Slippage  float64
}

type EquityPoint struct {
	Timestamp int64
	Equity    float64
}

func NewPerformanceMetrics() *PerformanceMetrics {
	return &PerformanceMetrics{
		trades:      make([]Trade, 0),
		equityCurve: make([]EquityPoint, 0),
	}
}

// AddTrade adds a trade to history
func (pm *PerformanceMetrics) AddTrade(trade Trade) {
	pm.mu.Lock()
	defer pm.mu.Unlock()
	pm.trades = append(pm.trades, trade)
	pm.totalFees += trade.Fee
	pm.totalSlippage += trade.Slippage
}

// AddEquityPoint adds an equity curve point
func (pm *PerformanceMetrics) AddEquityPoint(point EquityPoint) {
	pm.mu.Lock()
	defer pm.mu.Unlock()
	pm.equityCurve = append(pm.equityCurve, point)
}

// CalculateAll computes all performance metrics
func (pm *PerformanceMetrics) CalculateAll(riskFreeRate float64) PerformanceReport {
	pm.mu.Lock()
	defer pm.mu.Unlock()
	
	if len(pm.trades) == 0 {
		return PerformanceReport{}
	}
	
	pm.calculateReturns()
	pm.calculateWinRate()
	pm.calculateProfitFactor()
	pm.calculateExpectancy()
	pm.calculateDrawdown()
	pm.calculateSharpe(riskFreeRate)
	pm.calculateSortino(riskFreeRate)
	pm.calculateCalmar(riskFreeRate)
	pm.calculateVaR()
	
	return PerformanceReport{
		SharpeRatio:      pm.sharpeRatio,
		SortinoRatio:     pm.sortinoRatio,
		CalmarRatio:      pm.calmarRatio,
		MaxDrawdown:      pm.maxDrawdown,
		MaxDrawdownPct:   pm.maxDrawdownPct,
		WinRate:          pm.winRate,
		ProfitFactor:     pm.profitFactor,
		Expectancy:       pm.expectancy,
		VaR95:            pm.var95,
		VaR99:            pm.var99,
		CVaR95:           pm.cvar95,
		CVaR99:           pm.cvar99,
		TotalTrades:      len(pm.trades),
		TotalSlippage:    pm.totalSlippage,
		TotalFees:        pm.totalFees,
		TotalTransactionCosts: pm.totalSlippage + pm.totalFees,
	}
}

func (pm *PerformanceMetrics) calculateReturns() []float64 {
	if len(pm.equityCurve) < 2 {
		return nil
	}
	
	returns := make([]float64, len(pm.equityCurve)-1)
	for i := 1; i < len(pm.equityCurve); i++ {
		returns[i-1] = (pm.equityCurve[i].Equity - pm.equityCurve[i-1].Equity) / pm.equityCurve[i-1].Equity
	}
	
	return returns
}

func (pm *PerformanceMetrics) calculateSharpe(riskFreeRate float64) {
	returns := pm.calculateReturns()
	if len(returns) == 0 {
		return
	}
	
	// Calculate mean return
	var meanReturn float64
	for _, r := range returns {
		meanReturn += r
	}
	meanReturn /= float64(len(returns))
	
	// Annualize (assuming daily returns)
	annualizedReturn := meanReturn * 252.0
	
	// Calculate standard deviation
	var variance float64
	for _, r := range returns {
		diff := r - meanReturn
		variance += diff * diff
	}
	stdDev := math.Sqrt(variance / float64(len(returns)))
	annualizedStdDev := stdDev * math.Sqrt(252.0)
	
	if annualizedStdDev > 0 {
		pm.sharpeRatio = (annualizedReturn - riskFreeRate) / annualizedStdDev
	}
}

func (pm *PerformanceMetrics) calculateSortino(riskFreeRate float64) {
	returns := pm.calculateReturns()
	if len(returns) == 0 {
		return
	}
	
	// Calculate mean return
	var meanReturn float64
	for _, r := range returns {
		meanReturn += r
	}
	meanReturn /= float64(len(returns))
	
	// Annualize
	annualizedReturn := meanReturn * 252.0
	
	// Calculate downside deviation (only negative returns)
	var downsideVariance float64
	downsideCount := 0
	for _, r := range returns {
		if r < 0 {
			downsideVariance += r * r
			downsideCount++
		}
	}
	
	if downsideCount == 0 {
		pm.sortinoRatio = math.Inf(1)
		return
	}
	
	downsideDeviation := math.Sqrt(downsideVariance / float64(downsideCount))
	annualizedDownsideDev := downsideDeviation * math.Sqrt(252.0)
	
	if annualizedDownsideDev > 0 {
		pm.sortinoRatio = (annualizedReturn - riskFreeRate) / annualizedDownsideDev
	}
}

func (pm *PerformanceMetrics) calculateCalmar(riskFreeRate float64) {
	returns := pm.calculateReturns()
	if len(returns) == 0 || pm.maxDrawdownPct == 0 {
		return
	}
	
	// Calculate mean return
	var meanReturn float64
	for _, r := range returns {
		meanReturn += r
	}
	meanReturn /= float64(len(returns))
	
	annualizedReturn := meanReturn * 252.0
	pm.calmarRatio = (annualizedReturn - riskFreeRate) / pm.maxDrawdownPct
}

func (pm *PerformanceMetrics) calculateDrawdown() {
	if len(pm.equityCurve) == 0 {
		return
	}
	
	peak := pm.equityCurve[0].Equity
	maxDD := 0.0
	
	for _, point := range pm.equityCurve {
		if point.Equity > peak {
			peak = point.Equity
		}
		
		drawdown := peak - point.Equity
		if drawdown > maxDD {
			maxDD = drawdown
		}
	}
	
	pm.maxDrawdown = maxDD
	if peak > 0 {
		pm.maxDrawdownPct = maxDD / peak
	}
}

func (pm *PerformanceMetrics) calculateWinRate() {
	if len(pm.trades) == 0 {
		return
	}
	
	wins := 0
	for _, trade := range pm.trades {
		if trade.PnL > 0 {
			wins++
		}
	}
	
	pm.winRate = float64(wins) / float64(len(pm.trades))
}

func (pm *PerformanceMetrics) calculateProfitFactor() {
	grossProfit := 0.0
	grossLoss := 0.0
	
	for _, trade := range pm.trades {
		if trade.PnL > 0 {
			grossProfit += trade.PnL
		} else {
			grossLoss += -trade.PnL
		}
	}
	
	if grossLoss > 0 {
		pm.profitFactor = grossProfit / grossLoss
	} else if grossProfit > 0 {
		pm.profitFactor = math.Inf(1)
	}
}

func (pm *PerformanceMetrics) calculateExpectancy() {
	if len(pm.trades) == 0 {
		return
	}
	
	var totalPnL float64
	for _, trade := range pm.trades {
		totalPnL += trade.PnL
	}
	
	pm.expectancy = totalPnL / float64(len(pm.trades))
}

func (pm *PerformanceMetrics) calculateVaR() {
	returns := pm.calculateReturns()
	if len(returns) == 0 {
		return
	}
	
	// Sort returns for percentile calculation
	sortedReturns := make([]float64, len(returns))
	copy(sortedReturns, returns)
	sort.Float64s(sortedReturns)
	
	// VaR at 95% and 99%
	idx95 := int(0.05 * float64(len(sortedReturns)))
	idx99 := int(0.01 * float64(len(sortedReturns)))
	
	if idx95 < len(sortedReturns) {
		pm.var95 = -sortedReturns[idx95]
	}
	if idx99 < len(sortedReturns) {
		pm.var99 = -sortedReturns[idx99]
	}
	
	// CVaR (Expected Shortfall) - average of returns beyond VaR
	if idx95 > 0 {
		var sum95 float64
		for i := 0; i <= idx95; i++ {
			sum95 += sortedReturns[i]
		}
		pm.cvar95 = -sum95 / float64(idx95+1)
	}
	
	if idx99 > 0 {
		var sum99 float64
		for i := 0; i <= idx99; i++ {
			sum99 += sortedReturns[i]
		}
		pm.cvar99 = -sum99 / float64(idx99+1)
	}
}

// SlippageModel models transaction slippage
type SlippageModel interface {
	CalculateSlippage(order *types.OrderEvent, marketPrice float64, volume float64) float64
}

// FixedSlippageModel applies a fixed slippage percentage
type FixedSlippageModel struct {
	SlippageBps float64 // Slippage in basis points
}

func (fsm *FixedSlippageModel) CalculateSlippage(order *types.OrderEvent, marketPrice float64, volume float64) float64 {
	return marketPrice * fsm.SlippageBps / 10000.0
}

// VolumeWeightedSlippageModel applies slippage based on order size relative to volume
type VolumeWeightedSlippageModel struct {
	BaseBps      float64
	ImpactFactor float64
}

func (vws *VolumeWeightedSlippageModel) CalculateSlippage(order *types.OrderEvent, marketPrice float64, volume float64) float64 {
	if volume == 0 {
		return marketPrice * vws.BaseBps / 10000.0
	}
	
	// Slippage increases with order size relative to available volume
	participation := order.Quantity / volume
	slippageBps := vws.BaseBps + (vws.ImpactFactor * participation * 10000.0)
	
	return marketPrice * slippageBps / 10000.0
}

// TransactionCostAnalyzer analyzes transaction costs
type TransactionCostAnalyzer struct {
	trades      []Trade
	totalFees   float64
	totalSlippage float64
	mu          sync.RWMutex
}

func NewTransactionCostAnalyzer() *TransactionCostAnalyzer {
	return &TransactionCostAnalyzer{
		trades: make([]Trade, 0),
	}
}

func (tca *TransactionCostAnalyzer) AddTrade(trade Trade) {
	tca.mu.Lock()
	defer tca.mu.Unlock()
	tca.trades = append(tca.trades, trade)
	tca.totalFees += trade.Fee
	tca.totalSlippage += trade.Slippage
}

func (tca *TransactionCostAnalyzer) GetAnalysis() TransactionCostReport {
	tca.mu.RLock()
	defer tca.mu.RUnlock()
	
	if len(tca.trades) == 0 {
		return TransactionCostReport{}
	}
	
	totalVolume := 0.0
	for _, trade := range tca.trades {
		totalVolume += trade.Price * trade.Quantity
	}
	
	return TransactionCostReport{
		TotalFees:         tca.totalFees,
		TotalSlippage:     tca.totalSlippage,
		TotalCosts:        tca.totalFees + tca.totalSlippage,
		CostPerTrade:      (tca.totalFees + tca.totalSlippage) / float64(len(tca.trades)),
		CostPerVolume:     (tca.totalFees + tca.totalSlippage) / totalVolume,
		AvgSlippageBps:    (tca.totalSlippage / totalVolume) * 10000.0,
	}
}

type TransactionCostReport struct {
	TotalFees      float64
	TotalSlippage  float64
	TotalCosts     float64
	CostPerTrade   float64
	CostPerVolume  float64
	AvgSlippageBps float64
}

// PerformanceReport contains all performance metrics
type PerformanceReport struct {
	SharpeRatio           float64
	SortinoRatio          float64
	CalmarRatio           float64
	MaxDrawdown           float64
	MaxDrawdownPct        float64
	WinRate               float64
	ProfitFactor          float64
	Expectancy            float64
	VaR95                 float64
	VaR99                 float64
	CVaR95                float64
	CVaR99                float64
	TotalTrades           int
	TotalSlippage         float64
	TotalFees             float64
	TotalTransactionCosts float64
	StartTime             time.Time
	EndTime               time.Time
	Duration              time.Duration
}

func (pr PerformanceReport) String() string {
	return fmt.Sprintf(
		"Performance Report:\n"+
		"  Sharpe Ratio: %.2f\n"+
		"  Sortino Ratio: %.2f\n"+
		"  Calmar Ratio: %.2f\n"+
		"  Max Drawdown: %.2f (%.2f%%)\n"+
		"  Win Rate: %.2f%%\n"+
		"  Profit Factor: %.2f\n"+
		"  Expectancy: %.2f\n"+
		"  VaR 95%%: %.2f%%\n"+
		"  VaR 99%%: %.2f%%\n"+
		"  Total Trades: %d\n"+
		"  Transaction Costs: %.2f\n",
		pr.SharpeRatio,
		pr.SortinoRatio,
		pr.CalmarRatio,
		pr.MaxDrawdown,
		pr.MaxDrawdownPct*100,
		pr.WinRate*100,
		pr.ProfitFactor,
		pr.Expectancy,
		pr.VaR95*100,
		pr.VaR99*100,
		pr.TotalTrades,
		pr.TotalTransactionCosts,
	)
}