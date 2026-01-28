package strategies

import (
	"math"
	"sync"

	"github.com/openclaw/skills/quant-researcher/pkg/types"
)

// BollingerBandsStrategy implements Bollinger Bands mean reversion
type BollingerBandsStrategy struct {
	BaseStrategy
	Window     int
	Deviations float64
	
	prices     *types.TimeSeries
	upperBand  float64
	middleBand float64
	lowerBand  float64
	mu         sync.RWMutex
}

func NewBollingerBandsStrategy(window int, deviations float64) *BollingerBandsStrategy {
	return &BollingerBandsStrategy{
		BaseStrategy: NewBaseStrategy("bollinger_bands"),
		Window:       window,
		Deviations:   deviations,
		prices:       types.NewTimeSeries(window * 2),
	}
}

func (s *BollingerBandsStrategy) OnTick(event *types.TickEvent) {
	s.mu.Lock()
	defer s.mu.Unlock()
	
	point := types.PricePoint{
		Timestamp: event.Timestamp,
		Price:     event.Price,
		Volume:    event.Volume,
	}
	s.prices.Add(point)
	
	if s.prices.Len() < s.Window {
		return
	}
	
	s.calculateBands()
	
	// Generate signals
	if event.Price <= s.lowerBand {
		// Price below lower band - buy signal
		s.EmitSignal(types.SignalEvent{
			Timestamp:  event.Timestamp,
			Symbol:     event.Symbol,
			StrategyID: s.ID(),
			Action:     types.SignalBuy,
			Confidence: s.calculateConfidence(event.Price, s.lowerBand, s.middleBand),
			Price:      event.Price,
		})
	} else if event.Price >= s.upperBand {
		// Price above upper band - sell signal
		s.EmitSignal(types.SignalEvent{
			Timestamp:  event.Timestamp,
			Symbol:     event.Symbol,
			StrategyID: s.ID(),
			Action:     types.SignalSell,
			Confidence: s.calculateConfidence(event.Price, s.upperBand, s.middleBand),
			Price:      event.Price,
		})
	}
}

func (s *BollingerBandsStrategy) calculateBands() {
	prices := s.prices.ToSlice()
	
	// Calculate SMA
	var sum float64
	start := len(prices) - s.Window
	if start < 0 {
		start = 0
	}
	
	for i := start; i < len(prices); i++ {
		sum += prices[i].Price
	}
	
	s.middleBand = sum / float64(s.Window)
	
	// Calculate standard deviation
	var variance float64
	for i := start; i < len(prices); i++ {
		diff := prices[i].Price - s.middleBand
		variance += diff * diff
	}
	
	stdDev := math.Sqrt(variance / float64(s.Window))
	s.upperBand = s.middleBand + s.Deviations*stdDev
	s.lowerBand = s.middleBand - s.Deviations*stdDev
}

func (s *BollingerBandsStrategy) calculateConfidence(price, band, middle float64) float64 {
	distance := math.Abs(price - middle)
	bandWidth := math.Abs(band - middle)
	
	if bandWidth == 0 {
		return 0.5
	}
	
	// Confidence increases as price moves further from middle
	confidence := distance / bandWidth
	return math.Min(confidence, 1.0)
}

// RSIStrategy implements RSI mean reversion
type RSIStrategy struct {
	BaseStrategy
	Period      int
	Overbought  float64
	Oversold    float64
	
	gains       []float64
	losses      []float64
	prevPrice   float64
	avgGain     float64
	avgLoss     float64
	rsi         float64
	initialized bool
	mu          sync.RWMutex
}

func NewRSIStrategy(period int, overbought, oversold float64) *RSIStrategy {
	return &RSIStrategy{
		BaseStrategy: NewBaseStrategy("rsi"),
		Period:       period,
		Overbought:   overbought,
		Oversold:     oversold,
		gains:        make([]float64, 0, period),
		losses:       make([]float64, 0, period),
	}
}

func (s *RSIStrategy) OnTick(event *types.TickEvent) {
	s.mu.Lock()
	defer s.mu.Unlock()
	
	if !s.initialized {
		s.prevPrice = event.Price
		s.initialized = true
		return
	}
	
	change := event.Price - s.prevPrice
	s.prevPrice = event.Price
	
	var gain, loss float64
	if change > 0 {
		gain = change
	} else {
		loss = -change
	}
	
	s.gains = append(s.gains, gain)
	s.losses = append(s.losses, loss)
	
	if len(s.gains) < s.Period {
		return
	}
	
	// Keep only last N periods
	if len(s.gains) > s.Period {
		s.gains = s.gains[1:]
		s.losses = s.losses[1:]
	}
	
	// Calculate RSI
	if len(s.gains) == s.Period {
		var sumGain, sumLoss float64
		for i := 0; i < s.Period; i++ {
			sumGain += s.gains[i]
			sumLoss += s.losses[i]
		}
		
		s.avgGain = sumGain / float64(s.Period)
		s.avgLoss = sumLoss / float64(s.Period)
		
		if s.avgLoss == 0 {
			s.rsi = 100
		} else {
			rs := s.avgGain / s.avgLoss
			s.rsi = 100 - (100 / (1 + rs))
		}
		
		// Generate signals
		if s.rsi <= s.Oversold {
			s.EmitSignal(types.SignalEvent{
				Timestamp:  event.Timestamp,
				Symbol:     event.Symbol,
				StrategyID: s.ID(),
				Action:     types.SignalBuy,
				Confidence: (s.Oversold - s.rsi) / s.Oversold,
				Price:      event.Price,
				Metadata: map[string]float64{
					"rsi": s.rsi,
				},
			})
		} else if s.rsi >= s.Overbought {
			s.EmitSignal(types.SignalEvent{
				Timestamp:  event.Timestamp,
				Symbol:     event.Symbol,
				StrategyID: s.ID(),
				Action:     types.SignalSell,
				Confidence: (s.rsi - s.Overbought) / (100 - s.Overbought),
				Price:      event.Price,
				Metadata: map[string]float64{
					"rsi": s.rsi,
				},
			})
		}
	}
}

// ZScoreStrategy implements Z-score mean reversion
type ZScoreStrategy struct {
	BaseStrategy
	Lookback int
	Threshold float64
	
	prices    []float64
	mean      float64
	stdDev    float64
	zScore    float64
	mu        sync.RWMutex
}

func NewZScoreStrategy(lookback int, threshold float64) *ZScoreStrategy {
	return &ZScoreStrategy{
		BaseStrategy: NewBaseStrategy("zscore"),
		Lookback:     lookback,
		Threshold:    threshold,
		prices:       make([]float64, 0, lookback),
	}
}

func (s *ZScoreStrategy) OnTick(event *types.TickEvent) {
	s.mu.Lock()
	defer s.mu.Unlock()
	
	s.prices = append(s.prices, event.Price)
	
	if len(s.prices) > s.Lookback {
		s.prices = s.prices[1:]
	}
	
	if len(s.prices) < s.Lookback {
		return
	}
	
	// Calculate mean
	var sum float64
	for _, p := range s.prices {
		sum += p
	}
	s.mean = sum / float64(len(s.prices))
	
	// Calculate standard deviation
	var variance float64
	for _, p := range s.prices {
		diff := p - s.mean
		variance += diff * diff
	}
	s.stdDev = math.Sqrt(variance / float64(len(s.prices)))
	
	// Calculate Z-score
	if s.stdDev > 0 {
		s.zScore = (event.Price - s.mean) / s.stdDev
	} else {
		s.zScore = 0
	}
	
	// Generate signals
	if s.zScore <= -s.Threshold {
		// Price is significantly below mean - buy
		s.EmitSignal(types.SignalEvent{
			Timestamp:  event.Timestamp,
			Symbol:     event.Symbol,
			StrategyID: s.ID(),
			Action:     types.SignalBuy,
			Confidence: math.Min(-s.zScore/s.Threshold, 1.0),
			Price:      event.Price,
			Metadata: map[string]float64{
				"zscore": s.zScore,
				"mean":   s.mean,
				"stddev": s.stdDev,
			},
		})
	} else if s.zScore >= s.Threshold {
		// Price is significantly above mean - sell
		s.EmitSignal(types.SignalEvent{
			Timestamp:  event.Timestamp,
			Symbol:     event.Symbol,
			StrategyID: s.ID(),
			Action:     types.SignalSell,
			Confidence: math.Min(s.zScore/s.Threshold, 1.0),
			Price:      event.Price,
			Metadata: map[string]float64{
				"zscore": s.zScore,
				"mean":   s.mean,
				"stddev": s.stdDev,
			},
		})
	}
}