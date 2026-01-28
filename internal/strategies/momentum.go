package strategies

import (
	"math"
	"sync"

	"github.com/openclaw/skills/quant-researcher/pkg/types"
)

// MACDStrategy implements MACD momentum strategy
type MACDStrategy struct {
	BaseStrategy
	FastPeriod   int
	SlowPeriod   int
	SignalPeriod int
	
	fastEMA     float64
	slowEMA     float64
	signalEMA   float64
	macd        float64
	histogram   float64
	initialized bool
	prices      []float64
	mu          sync.RWMutex
}

func NewMACDStrategy(fast, slow, signal int) *MACDStrategy {
	return &MACDStrategy{
		BaseStrategy: NewBaseStrategy("macd"),
		FastPeriod:   fast,
		SlowPeriod:   slow,
		SignalPeriod: signal,
		prices:       make([]float64, 0, slow),
	}
}

func (s *MACDStrategy) OnTick(event *types.TickEvent) {
	s.mu.Lock()
	defer s.mu.Unlock()
	
	price := event.Price
	
	if !s.initialized {
		s.fastEMA = price
		s.slowEMA = price
		s.signalEMA = 0
		s.initialized = true
		return
	}
	
	// Calculate EMAs
	fastMultiplier := 2.0 / float64(s.FastPeriod+1)
	slowMultiplier := 2.0 / float64(s.SlowPeriod+1)
	signalMultiplier := 2.0 / float64(s.SignalPeriod+1)
	
	s.fastEMA = (price * fastMultiplier) + (s.fastEMA * (1 - fastMultiplier))
	s.slowEMA = (price * slowMultiplier) + (s.slowEMA * (1 - slowMultiplier))
	
	// MACD line
	s.macd = s.fastEMA - s.slowEMA
	
	// Signal line
	s.signalEMA = (s.macd * signalMultiplier) + (s.signalEMA * (1 - signalMultiplier))
	
	// Histogram
	prevHistogram := s.histogram
	s.histogram = s.macd - s.signalEMA
	
	// Generate signals on histogram crossover
	if prevHistogram < 0 && s.histogram > 0 {
		// Bullish crossover - buy
		s.EmitSignal(types.SignalEvent{
			Timestamp:  event.Timestamp,
			Symbol:     event.Symbol,
			StrategyID: s.ID(),
			Action:     types.SignalBuy,
			Confidence: math.Min(s.histogram/s.signalEMA, 1.0),
			Price:      event.Price,
			Metadata: map[string]float64{
				"macd":      s.macd,
				"signal":    s.signalEMA,
				"histogram": s.histogram,
			},
		})
	} else if prevHistogram > 0 && s.histogram < 0 {
		// Bearish crossover - sell
		s.EmitSignal(types.SignalEvent{
			Timestamp:  event.Timestamp,
			Symbol:     event.Symbol,
			StrategyID: s.ID(),
			Action:     types.SignalSell,
			Confidence: math.Min(-s.histogram/s.signalEMA, 1.0),
			Price:      event.Price,
			Metadata: map[string]float64{
				"macd":      s.macd,
				"signal":    s.signalEMA,
				"histogram": s.histogram,
			},
		})
	}
}

// EMAStrategy implements EMA crossover momentum
type EMAStrategy struct {
	BaseStrategy
	FastPeriod int
	SlowPeriod int
	
	fastPrices []float64
	slowPrices []float64
	fastEMA    float64
	slowEMA    float64
	prevTrend  int // -1: down, 0: none, 1: up
	mu         sync.RWMutex
}

func NewEMAStrategy(fast, slow int) *EMAStrategy {
	return &EMAStrategy{
		BaseStrategy: NewBaseStrategy("ema_crossover"),
		FastPeriod:   fast,
		SlowPeriod:   slow,
		fastPrices:   make([]float64, 0, fast),
		slowPrices:   make([]float64, 0, slow),
	}
}

func (s *EMAStrategy) OnTick(event *types.TickEvent) {
	s.mu.Lock()
	defer s.mu.Unlock()
	
	price := event.Price
	
	// Update price buffers
	s.fastPrices = append(s.fastPrices, price)
	s.slowPrices = append(s.slowPrices, price)
	
	if len(s.fastPrices) > s.FastPeriod {
		s.fastPrices = s.fastPrices[1:]
	}
	if len(s.slowPrices) > s.SlowPeriod {
		s.slowPrices = s.slowPrices[1:]
	}
	
	if len(s.slowPrices) < s.SlowPeriod {
		return // Not enough data
	}
	
	// Calculate EMAs
	s.fastEMA = s.calculateEMA(s.fastPrices, s.FastPeriod)
	s.slowEMA = s.calculateEMA(s.slowPrices, s.SlowPeriod)
	
	// Determine trend
	currentTrend := 0
	if s.fastEMA > s.slowEMA {
		currentTrend = 1
	} else if s.fastEMA < s.slowEMA {
		currentTrend = -1
	}
	
	// Generate signals on crossover
	if s.prevTrend != 0 && currentTrend != s.prevTrend {
		if currentTrend == 1 {
			// Golden cross - buy
			s.EmitSignal(types.SignalEvent{
				Timestamp:  event.Timestamp,
				Symbol:     event.Symbol,
				StrategyID: s.ID(),
				Action:     types.SignalBuy,
				Confidence: s.calculateConfidence(),
				Price:      event.Price,
				Metadata: map[string]float64{
					"fast_ema": s.fastEMA,
					"slow_ema": s.slowEMA,
					"spread":   s.fastEMA - s.slowEMA,
				},
			})
		} else {
			// Death cross - sell
			s.EmitSignal(types.SignalEvent{
				Timestamp:  event.Timestamp,
				Symbol:     event.Symbol,
				StrategyID: s.ID(),
				Action:     types.SignalSell,
				Confidence: s.calculateConfidence(),
				Price:      event.Price,
				Metadata: map[string]float64{
					"fast_ema": s.fastEMA,
					"slow_ema": s.slowEMA,
					"spread":   s.slowEMA - s.fastEMA,
				},
			})
		}
	}
	
	s.prevTrend = currentTrend
}

func (s *EMAStrategy) calculateEMA(prices []float64, period int) float64 {
	multiplier := 2.0 / float64(period+1)
	ema := prices[0]
	
	for i := 1; i < len(prices); i++ {
		ema = (prices[i] * multiplier) + (ema * (1 - multiplier))
	}
	
	return ema
}

func (s *EMAStrategy) calculateConfidence() float64 {
	spread := math.Abs(s.fastEMA - s.slowEMA)
	avgPrice := (s.fastEMA + s.slowEMA) / 2
	
	if avgPrice == 0 {
		return 0.5
	}
	
	// Confidence based on spread percentage
	confidence := spread / avgPrice
	return math.Min(confidence*10, 1.0) // Scale up for meaningful values
}

// BreakoutStrategy implements volatility breakout momentum
type BreakoutStrategy struct {
	BaseStrategy
	Lookback   int
	Multiplier float64
	
	prices     []float64
	highs      []float64
	lows       []float64
	atr        float64
	prevHigh   float64
	prevLow    float64
	prevClose  float64
	mu         sync.RWMutex
}

func NewBreakoutStrategy(lookback int, multiplier float64) *BreakoutStrategy {
	return &BreakoutStrategy{
		BaseStrategy: NewBaseStrategy("breakout"),
		Lookback:     lookback,
		Multiplier:   multiplier,
		prices:       make([]float64, 0, lookback),
		highs:        make([]float64, 0, lookback),
		lows:         make([]float64, 0, lookback),
	}
}

func (s *BreakoutStrategy) OnTick(event *types.TickEvent) {
	s.mu.Lock()
	defer s.mu.Unlock()
	
	price := event.Price
	
	s.prices = append(s.prices, price)
	s.highs = append(s.highs, price)  // Simplified - using price as high/low
	s.lows = append(s.lows, price)
	
	if len(s.prices) > s.Lookback {
		s.prices = s.prices[1:]
		s.highs = s.highs[1:]
		s.lows = s.lows[1:]
	}
	
	if len(s.prices) < 2 {
		s.prevClose = price
		return
	}
	
	// Calculate ATR
	s.atr = s.calculateATR()
	
	// Calculate Donchian channels
	s.prevHigh = s.max(s.highs)
	s.prevLow = s.min(s.lows)
	
	breakoutLevel := s.atr * s.Multiplier
	
	// Generate signals
	if price > s.prevHigh+breakoutLevel {
		// Breakout up - buy
		s.EmitSignal(types.SignalEvent{
			Timestamp:  event.Timestamp,
			Symbol:     event.Symbol,
			StrategyID: s.ID(),
			Action:     types.SignalBuy,
			Confidence: math.Min((price-s.prevHigh)/breakoutLevel, 1.0),
			Price:      event.Price,
			Metadata: map[string]float64{
				"atr":       s.atr,
				"prev_high": s.prevHigh,
				"prev_low":  s.prevLow,
			},
		})
	} else if price < s.prevLow-breakoutLevel {
		// Breakout down - sell
		s.EmitSignal(types.SignalEvent{
			Timestamp:  event.Timestamp,
			Symbol:     event.Symbol,
			StrategyID: s.ID(),
			Action:     types.SignalSell,
			Confidence: math.Min((s.prevLow-price)/breakoutLevel, 1.0),
			Price:      event.Price,
			Metadata: map[string]float64{
				"atr":       s.atr,
				"prev_high": s.prevHigh,
				"prev_low":  s.prevLow,
			},
		})
	}
	
	s.prevClose = price
}

func (s *BreakoutStrategy) calculateATR() float64 {
	if len(s.prices) < 2 {
		return 0
	}
	
	var trSum float64
	for i := 1; i < len(s.prices); i++ {
		high := s.highs[i]
		low := s.lows[i]
		prevClose := s.prices[i-1]
		
		tr1 := high - low
		tr2 := math.Abs(high - prevClose)
		tr3 := math.Abs(low - prevClose)
		
		tr := tr1
		if tr2 > tr {
			tr = tr2
		}
		if tr3 > tr {
			tr = tr3
		}
		
		trSum += tr
	}
	
	return trSum / float64(len(s.prices)-1)
}

func (s *BreakoutStrategy) max(values []float64) float64 {
	if len(values) == 0 {
		return 0
	}
	max := values[0]
	for _, v := range values[1:] {
		if v > max {
			max = v
		}
	}
	return max
}

func (s *BreakoutStrategy) min(values []float64) float64 {
	if len(values) == 0 {
		return 0
	}
	min := values[0]
	for _, v := range values[1:] {
		if v < min {
			min = v
		}
	}
	return min
}