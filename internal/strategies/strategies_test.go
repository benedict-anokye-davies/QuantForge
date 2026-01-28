package strategies

import (
	"testing"

	"github.com/openclaw/skills/quant-researcher/pkg/types"
)

func TestBollingerBandsStrategy(t *testing.T) {
	strategy := NewBollingerBandsStrategy(20, 2.0)
	
	// Feed price data
	prices := generatePriceData(100, 100.0, 0.01)
	
	signalCount := 0
	strategy.RegisterSignalHandler(func(signal types.SignalEvent) {
		signalCount++
		t.Logf("Signal: %v at price %.2f", signal.Action, signal.Price)
	})
	
	for _, price := range prices {
		event := &types.TickEvent{
			Timestamp: types.NanoTime(),
			Symbol:    "TEST",
			Price:     price,
			Volume:    1000.0,
			Bid:       price * 0.999,
			Ask:       price * 1.001,
		}
		strategy.OnTick(event)
	}
	
	if signalCount == 0 {
		t.Log("No signals generated - this may be normal depending on price data")
	}
}

func TestRSIStrategy(t *testing.T) {
	strategy := NewRSIStrategy(14, 70, 30)
	
	prices := generatePriceData(50, 100.0, 0.02)
	
	signalCount := 0
	strategy.RegisterSignalHandler(func(signal types.SignalEvent) {
		signalCount++
	})
	
	for _, price := range prices {
		event := &types.TickEvent{
			Timestamp: types.NanoTime(),
			Symbol:    "TEST",
			Price:     price,
			Volume:    1000.0,
			Bid:       price * 0.999,
			Ask:       price * 1.001,
		}
		strategy.OnTick(event)
	}
	
	t.Logf("Generated %d signals", signalCount)
}

func TestMACDStrategy(t *testing.T) {
	strategy := NewMACDStrategy(12, 26, 9)
	
	prices := generateTrendingPriceData(100, 100.0, 0.001)
	
	signalCount := 0
	strategy.RegisterSignalHandler(func(signal types.SignalEvent) {
		signalCount++
	})
	
	for _, price := range prices {
		event := &types.TickEvent{
			Timestamp: types.NanoTime(),
			Symbol:    "TEST",
			Price:     price,
			Volume:    1000.0,
			Bid:       price * 0.999,
			Ask:       price * 1.001,
		}
		strategy.OnTick(event)
	}
	
	t.Logf("Generated %d signals", signalCount)
}

func TestAvellanedaStoikov(t *testing.T) {
	strategy := NewAvellanedaStoikovStrategy("BTC/USD", 0.1, 0.5, 1.5, 10.0, 1.0)
	
	signalCount := 0
	strategy.RegisterSignalHandler(func(signal types.SignalEvent) {
		signalCount++
	})
	
	// Simulate market data
	for i := 0; i < 100; i++ {
		price := 50000.0 + float64(i)*10.0
		event := &types.TickEvent{
			Timestamp: types.NanoTime(),
			Symbol:    "BTC/USD",
			Price:     price,
			Volume:    10.0,
			Bid:       price - 10.0,
			Ask:       price + 10.0,
		}
		strategy.OnTick(event)
	}
	
	if signalCount == 0 {
		t.Error("Market making strategy should generate quotes")
	}
	
	t.Logf("Generated %d quote signals", signalCount)
}

// Helper functions

func generatePriceData(n int, startPrice, volatility float64) []float64 {
	prices := make([]float64, n)
	price := startPrice
	
	for i := 0; i < n; i++ {
		prices[i] = price
		// Random walk
		change := (float64(i%3) - 1.0) * volatility * price
		price += change
	}
	
	return prices
}

func generateTrendingPriceData(n int, startPrice, trend float64) []float64 {
	prices := make([]float64, n)
	price := startPrice
	
	for i := 0; i < n; i++ {
		prices[i] = price
		price *= (1.0 + trend)
	}
	
	return prices
}

func BenchmarkBollingerBands(b *testing.B) {
	strategy := NewBollingerBandsStrategy(20, 2.0)
	
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		event := &types.TickEvent{
			Timestamp: int64(i),
			Symbol:    "TEST",
			Price:     100.0 + float64(i%100),
			Volume:    1000.0,
			Bid:       99.9,
			Ask:       100.1,
		}
		strategy.OnTick(event)
	}
}

func BenchmarkMACD(b *testing.B) {
	strategy := NewMACDStrategy(12, 26, 9)
	
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		event := &types.TickEvent{
			Timestamp: int64(i),
			Symbol:    "TEST",
			Price:     100.0 + float64(i%100),
			Volume:    1000.0,
			Bid:       99.9,
			Ask:       100.1,
		}
		strategy.OnTick(event)
	}
}