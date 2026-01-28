package risk

import (
	"fmt"
	"math"
	"sync"
	"sync/atomic"

	"github.com/openclaw/skills/quant-researcher/pkg/types"
)

// RiskManager handles all risk management functions
type RiskManager struct {
	// Kelly Criterion
	kellyFraction    float64
	winRate          float64
	avgWin           float64
	avgLoss          float64
	
	// Volatility sizing
	atrMultiplier    float64
	atrLookback      int
	atrValues        map[string][]float64
	
	// Drawdown controls
	maxDrawdown      float64
	currentDrawdown  uint64 // atomic.Float64 equivalent using bits
	drawdownKillSwitch bool
	
	// Daily limits
	dailyLossLimit   float64
	currentDailyLoss uint64 // atomic.Float64 equivalent using bits
	lastResetDay     int64
	
	// Consecutive loss circuit breaker
	maxConsecutiveLosses int
	consecutiveLosses    int32 // atomic.Int32 equivalent
	circuitBroken        uint32 // atomic.Bool equivalent
	
	// Portfolio state
	portfolio        *types.PortfolioState
	
	// Risk checks
	checks           []RiskCheck
	mu               sync.RWMutex
}

type RiskCheck func(*types.OrderEvent, *types.PortfolioState) (bool, string)

// Config for risk manager
type Config struct {
	KellyFraction        float64
	ATRLookback          int
	ATRMultiplier        float64
	MaxDrawdown          float64 // e.g., 0.20 for 20%
	DailyLossLimit       float64 // Dollar amount
	MaxConsecutiveLosses int
}

func DefaultConfig() *Config {
	return &Config{
		KellyFraction:        0.25, // Quarter Kelly for safety
		ATRLookback:          14,
		ATRMultiplier:        2.0,
		MaxDrawdown:          0.20,
		DailyLossLimit:       10000.0,
		MaxConsecutiveLosses: 5,
	}
}

func NewRiskManager(cfg *Config, portfolio *types.PortfolioState) *RiskManager {
	if cfg == nil {
		cfg = DefaultConfig()
	}
	
	rm := &RiskManager{
		kellyFraction:        cfg.KellyFraction,
		atrMultiplier:        cfg.ATRMultiplier,
		atrLookback:          cfg.ATRLookback,
		atrValues:            make(map[string][]float64),
		maxDrawdown:          cfg.MaxDrawdown,
		dailyLossLimit:       cfg.DailyLossLimit,
		maxConsecutiveLosses: cfg.MaxConsecutiveLosses,
		portfolio:            portfolio,
		checks:               make([]RiskCheck, 0),
	}
	
	// Register default risk checks
	rm.RegisterCheck(rm.checkDrawdownKillSwitch)
	rm.RegisterCheck(rm.checkDailyLossLimit)
	rm.RegisterCheck(rm.checkCircuitBreaker)
	rm.RegisterCheck(rm.checkPositionSize)
	rm.RegisterCheck(rm.checkPortfolioExposure)
	
	return rm
}

// RegisterCheck adds a risk check
func (rm *RiskManager) RegisterCheck(check RiskCheck) {
	rm.mu.Lock()
	defer rm.mu.Unlock()
	rm.checks = append(rm.checks, check)
}

// ValidateOrder runs all risk checks on an order
func (rm *RiskManager) ValidateOrder(order *types.OrderEvent) (bool, string) {
	rm.mu.RLock()
	defer rm.mu.RUnlock()
	
	for _, check := range rm.checks {
		if ok, reason := check(order, rm.portfolio); !ok {
			return false, reason
		}
	}
	
	return true, ""
}

// Kelly Criterion position sizing
func (rm *RiskManager) CalculateKellyPositionSize(equity, price float64) float64 {
	rm.mu.RLock()
	defer rm.mu.RUnlock()
	
	if rm.avgLoss == 0 {
		return 0
	}
	
	// Kelly % = W - [(1-W) / R]
	// where W = win rate, R = win/loss ratio
	winLossRatio := rm.avgWin / rm.avgLoss
	kellyPct := rm.winRate - ((1.0-rm.winRate)/winLossRatio)
	
	// Apply Kelly fraction (typically 0.25 to 0.5 for safety)
	kellyPct *= rm.kellyFraction
	
	if kellyPct <= 0 {
		return 0
	}
	
	// Calculate position size
	positionValue := equity * kellyPct
	return positionValue / price
}

// ATR-based position sizing
func (rm *RiskManager) CalculateATRPositionSize(symbol string, equity, price, riskPerTrade float64) float64 {
	rm.mu.RLock()
	defer rm.mu.RUnlock()
	
	atr := rm.getCurrentATR(symbol)
	if atr == 0 {
		return 0
	}
	
	// Position size = (Equity * Risk%) / (ATR * Multiplier)
	riskAmount := equity * riskPerTrade
	stopDistance := atr * rm.atrMultiplier
	
	if stopDistance == 0 {
		return 0
	}
	
	return riskAmount / stopDistance
}

// UpdateATR updates ATR calculation for a symbol
func (rm *RiskManager) UpdateATR(symbol string, high, low, close float64) {
	rm.mu.Lock()
	defer rm.mu.Unlock()
	
	if _, ok := rm.atrValues[symbol]; !ok {
		rm.atrValues[symbol] = make([]float64, 0, rm.atrLookback)
	}
	
	// Calculate true range
	tr1 := high - low
	tr2 := math.Abs(high - close)
	tr3 := math.Abs(low - close)
	
	tr := tr1
	if tr2 > tr {
		tr = tr2
	}
	if tr3 > tr {
		tr = tr3
	}
	
	// Add to history
	rm.atrValues[symbol] = append(rm.atrValues[symbol], tr)
	if len(rm.atrValues[symbol]) > rm.atrLookback {
		rm.atrValues[symbol] = rm.atrValues[symbol][1:]
	}
}

func (rm *RiskManager) getCurrentATR(symbol string) float64 {
	values, ok := rm.atrValues[symbol]
	if !ok || len(values) == 0 {
		return 0
	}
	
	var sum float64
	for _, v := range values {
		sum += v
	}
	return sum / float64(len(values))
}

// UpdateTradeStats updates win/loss statistics for Kelly calculation
func (rm *RiskManager) UpdateTradeStats(pnl float64) {
	rm.mu.Lock()
	defer rm.mu.Unlock()
	
	if pnl > 0 {
		rm.winRate = (rm.winRate*float64(rm.avgWin) + 1.0) / (float64(rm.avgWin) + 1.0)
		rm.avgWin = (rm.avgWin*float64(rm.avgWin) + pnl) / (float64(rm.avgWin) + 1.0)
		atomic.StoreInt32(&rm.consecutiveLosses, 0)
	} else {
		rm.winRate = (rm.winRate*float64(rm.avgWin)) / (float64(rm.avgWin) + 1.0)
		rm.avgLoss = (rm.avgLoss*float64(rm.avgLoss) - pnl) / (float64(rm.avgLoss) + 1.0)
		
		losses := atomic.AddInt32(&rm.consecutiveLosses, 1)
		if int(losses) >= rm.maxConsecutiveLosses {
			atomic.StoreUint32(&rm.circuitBroken, 1)
		}
	}
}

// UpdateDrawdown updates current drawdown
func (rm *RiskManager) UpdateDrawdown(drawdown float64) {
	bits := math.Float64bits(drawdown)
	atomic.StoreUint64(&rm.currentDrawdown, bits)
	
	if drawdown >= rm.maxDrawdown {
		rm.drawdownKillSwitch = true
	}
}

// UpdateDailyLoss updates daily loss tracking
func (rm *RiskManager) UpdateDailyLoss(loss float64, day int64) {
	if day != rm.lastResetDay {
		atomic.StoreUint64(&rm.currentDailyLoss, 0)
		rm.lastResetDay = day
	}
	
	for {
		oldBits := atomic.LoadUint64(&rm.currentDailyLoss)
		oldVal := math.Float64frombits(oldBits)
		newVal := oldVal + loss
		newBits := math.Float64bits(newVal)
		if atomic.CompareAndSwapUint64(&rm.currentDailyLoss, oldBits, newBits) {
			break
		}
	}
}

// Risk check implementations

func (rm *RiskManager) checkDrawdownKillSwitch(order *types.OrderEvent, portfolio *types.PortfolioState) (bool, string) {
	if rm.drawdownKillSwitch {
		return false, "drawdown kill switch activated"
	}
	return true, ""
}

func (rm *RiskManager) checkDailyLossLimit(order *types.OrderEvent, portfolio *types.PortfolioState) (bool, string) {
	currentLossBits := atomic.LoadUint64(&rm.currentDailyLoss)
	currentLoss := math.Float64frombits(currentLossBits)
	if currentLoss >= rm.dailyLossLimit {
		return false, fmt.Sprintf("daily loss limit reached: %.2f", currentLoss)
	}
	return true, ""
}

func (rm *RiskManager) checkCircuitBreaker(order *types.OrderEvent, portfolio *types.PortfolioState) (bool, string) {
	if atomic.LoadUint32(&rm.circuitBroken) != 0 {
		return false, "consecutive loss circuit breaker activated"
	}
	return true, ""
}

func (rm *RiskManager) checkPositionSize(order *types.OrderEvent, portfolio *types.PortfolioState) (bool, string) {
	// Check if order size exceeds limits
	equity := portfolio.Equity
	maxPositionValue := equity * 0.20 // Max 20% in single position
	
	orderValue := order.Quantity * order.Price
	if orderValue > maxPositionValue {
		return false, fmt.Sprintf("position size exceeds limit: %.2f > %.2f", orderValue, maxPositionValue)
	}
	
	return true, ""
}

func (rm *RiskManager) checkPortfolioExposure(order *types.OrderEvent, portfolio *types.PortfolioState) (bool, string) {
	// Calculate total exposure
	var totalExposure float64
	for _, pos := range portfolio.Positions {
		totalExposure += math.Abs(pos.Quantity * pos.AvgEntryPrice)
	}
	
	// Add new order
	newExposure := totalExposure + (order.Quantity * order.Price)
	maxExposure := portfolio.TotalValue * 2.0 // Max 2x leverage
	
	if newExposure > maxExposure {
		return false, fmt.Sprintf("portfolio exposure exceeds limit: %.2f > %.2f", newExposure, maxExposure)
	}
	
	return true, ""
}

// ResetCircuitBreaker resets the consecutive loss circuit breaker
func (rm *RiskManager) ResetCircuitBreaker() {
	atomic.StoreUint32(&rm.circuitBroken, 0)
	atomic.StoreInt32(&rm.consecutiveLosses, 0)
}

// ResetDrawdownKillSwitch resets the drawdown kill switch
func (rm *RiskManager) ResetDrawdownKillSwitch() {
	rm.drawdownKillSwitch = false
	atomic.StoreUint64(&rm.currentDrawdown, 0)
}

// GetRiskMetrics returns current risk metrics
func (rm *RiskManager) GetRiskMetrics() RiskMetrics {
	currentDDBits := atomic.LoadUint64(&rm.currentDrawdown)
	currentDailyLossBits := atomic.LoadUint64(&rm.currentDailyLoss)
	
	return RiskMetrics{
		KellyFraction:      rm.kellyFraction,
		WinRate:            rm.winRate,
		AvgWin:             rm.avgWin,
		AvgLoss:            rm.avgLoss,
		CurrentDrawdown:    math.Float64frombits(currentDDBits),
		MaxDrawdown:        rm.maxDrawdown,
		DailyLoss:          math.Float64frombits(currentDailyLossBits),
		DailyLossLimit:     rm.dailyLossLimit,
		ConsecutiveLosses:  int(atomic.LoadInt32(&rm.consecutiveLosses)),
		CircuitBroken:      atomic.LoadUint32(&rm.circuitBroken) != 0,
		KillSwitchActive:   rm.drawdownKillSwitch,
	}
}

type RiskMetrics struct {
	KellyFraction      float64
	WinRate            float64
	AvgWin             float64
	AvgLoss            float64
	CurrentDrawdown    float64
	MaxDrawdown        float64
	DailyLoss          float64
	DailyLossLimit     float64
	ConsecutiveLosses  int
	CircuitBroken      bool
	KillSwitchActive   bool
}