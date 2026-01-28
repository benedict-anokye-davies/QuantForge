package risk

import (
	"testing"

	"github.com/openclaw/skills/quant-researcher/pkg/types"
)

func TestRiskManager(t *testing.T) {
	portfolio := types.NewPortfolioState(100000.0)
	cfg := DefaultConfig()
	
	rm := NewRiskManager(cfg, portfolio)
	
	// Test order validation (small order to pass position size check)
	order := &types.OrderEvent{
		ID:       "test-1",
		Symbol:   "BTC/USD",
		Side:     types.SideBuy,
		Quantity: 0.1,     // Small order: $5k value
		Price:    50000.0,
	}
	
	ok, reason := rm.ValidateOrder(order)
	if !ok {
		t.Errorf("Order should be valid, got: %s", reason)
	}
}

func TestKellyPositionSizing(t *testing.T) {
	portfolio := types.NewPortfolioState(100000.0)
	rm := NewRiskManager(DefaultConfig(), portfolio)
	
	// Update with some trade stats
	rm.UpdateTradeStats(1000.0)  // Win
	rm.UpdateTradeStats(500.0)   // Win
	rm.UpdateTradeStats(-200.0)  // Loss
	
	// Calculate position size
	size := rm.CalculateKellyPositionSize(100000.0, 50000.0)
	
	t.Logf("Kelly position size: %.4f", size)
	
	if size <= 0 {
		t.Error("Position size should be positive")
	}
}

func TestATRPositionSizing(t *testing.T) {
	portfolio := types.NewPortfolioState(100000.0)
	rm := NewRiskManager(DefaultConfig(), portfolio)
	
	// Update ATR values
	for i := 0; i < 20; i++ {
		high := 100.0 + float64(i)
		low := 99.0 + float64(i)
		close := 99.5 + float64(i)
		rm.UpdateATR("TEST", high, low, close)
	}
	
	// Calculate position size
	size := rm.CalculateATRPositionSize("TEST", 100000.0, 100.0, 0.02)
	
	t.Logf("ATR position size: %.4f", size)
	
	if size <= 0 {
		t.Error("Position size should be positive")
	}
}

func TestDrawdownKillSwitch(t *testing.T) {
	portfolio := types.NewPortfolioState(100000.0)
	cfg := &Config{
		MaxDrawdown: 0.10, // 10% max drawdown
	}
	
	rm := NewRiskManager(cfg, portfolio)
	
	// Simulate drawdown
	rm.UpdateDrawdown(0.15) // 15% drawdown
	
	// Try to place order
	order := &types.OrderEvent{
		ID:       "test-1",
		Symbol:   "BTC/USD",
		Side:     types.SideBuy,
		Quantity: 1.0,
		Price:    50000.0,
	}
	
	ok, reason := rm.ValidateOrder(order)
	if ok {
		t.Error("Order should be rejected due to drawdown kill switch")
	}
	
	if reason != "drawdown kill switch activated" {
		t.Errorf("Expected drawdown kill switch reason, got: %s", reason)
	}
}

func TestDailyLossLimit(t *testing.T) {
	portfolio := types.NewPortfolioState(100000.0)
	cfg := &Config{
		DailyLossLimit: 5000.0,
	}
	
	rm := NewRiskManager(cfg, portfolio)
	
	// Simulate daily loss
	rm.UpdateDailyLoss(6000.0, 1)
	
	// Try to place order
	order := &types.OrderEvent{
		ID:       "test-1",
		Symbol:   "BTC/USD",
		Side:     types.SideBuy,
		Quantity: 1.0,
		Price:    50000.0,
	}
	
	ok, reason := rm.ValidateOrder(order)
	if ok {
		t.Error("Order should be rejected due to daily loss limit")
	}
	
	if reason == "" {
		t.Error("Should have rejection reason")
	}
}

func TestConsecutiveLossCircuitBreaker(t *testing.T) {
	portfolio := types.NewPortfolioState(100000.0)
	cfg := &Config{
		MaxConsecutiveLosses: 3,
		DailyLossLimit:       100000.0, // High limit so daily loss doesn't trigger first
	}
	
	rm := NewRiskManager(cfg, portfolio)
	
	// Simulate consecutive losses
	rm.UpdateTradeStats(-100.0)
	rm.UpdateTradeStats(-200.0)
	rm.UpdateTradeStats(-150.0)
	rm.UpdateTradeStats(-300.0) // Should trigger circuit breaker
	
	// Try to place order (small order to pass position size check)
	order := &types.OrderEvent{
		ID:       "test-1",
		Symbol:   "BTC/USD",
		Side:     types.SideBuy,
		Quantity: 0.1,
		Price:    50000.0,
	}
	
	ok, reason := rm.ValidateOrder(order)
	if ok {
		t.Error("Order should be rejected due to circuit breaker")
	}
	
	if reason != "consecutive loss circuit breaker activated" {
		t.Errorf("Expected circuit breaker reason, got: %s", reason)
	}
	
	// Reset and verify
	rm.ResetCircuitBreaker()
	
	ok, _ = rm.ValidateOrder(order)
	if !ok {
		t.Error("Order should be valid after reset")
	}
}

func TestPositionSizeLimit(t *testing.T) {
	portfolio := types.NewPortfolioState(100000.0)
	rm := NewRiskManager(DefaultConfig(), portfolio)
	
	// Try oversized order (>20% of equity)
	order := &types.OrderEvent{
		ID:       "test-1",
		Symbol:   "BTC/USD",
		Side:     types.SideBuy,
		Quantity: 10.0,  // $500k at $50k/BTC
		Price:    50000.0,
	}
	
	ok, reason := rm.ValidateOrder(order)
	if ok {
		t.Error("Order should be rejected due to position size limit")
	}
	
	if reason == "" {
		t.Error("Should have rejection reason")
	}
}

func BenchmarkRiskCheck(b *testing.B) {
	portfolio := types.NewPortfolioState(100000.0)
	rm := NewRiskManager(DefaultConfig(), portfolio)
	
	order := &types.OrderEvent{
		ID:       "test-1",
		Symbol:   "BTC/USD",
		Side:     types.SideBuy,
		Quantity: 1.0,
		Price:    50000.0,
	}
	
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		rm.ValidateOrder(order)
	}
}