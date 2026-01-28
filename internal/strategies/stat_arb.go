package strategies

import (
	"math"
	"sync"

	"github.com/openclaw/skills/quant-researcher/pkg/types"
)

// PairsTradingStrategy implements pairs trading / statistical arbitrage
type PairsTradingStrategy struct {
	BaseStrategy
	Symbol1      string
	Symbol2      string
	Lookback     int
	EntryZScore  float64
	ExitZScore   float64
	
	prices1      []float64
	prices2      []float64
	spread       []float64
	mean         float64
	stdDev       float64
	zScore       float64
	hedgeRatio   float64
	position1    float64  // Current position in symbol1
	position2    float64  // Current position in symbol2
	mu           sync.RWMutex
}

func NewPairsTradingStrategy(symbol1, symbol2 string, lookback int, entryZ, exitZ float64) *PairsTradingStrategy {
	return &PairsTradingStrategy{
		BaseStrategy: NewBaseStrategy("pairs_trading_" + symbol1 + "_" + symbol2),
		Symbol1:      symbol1,
		Symbol2:      symbol2,
		Lookback:     lookback,
		EntryZScore:  entryZ,
		ExitZScore:   exitZ,
		prices1:      make([]float64, 0, lookback),
		prices2:      make([]float64, 0, lookback),
		spread:       make([]float64, 0, lookback),
		hedgeRatio:   1.0,
	}
}

func (s *PairsTradingStrategy) OnTick(event *types.TickEvent) {
	s.mu.Lock()
	defer s.mu.Unlock()
	
	// Collect prices for both symbols
	if event.Symbol == s.Symbol1 {
		s.prices1 = append(s.prices1, event.Price)
		if len(s.prices1) > s.Lookback {
			s.prices1 = s.prices1[1:]
		}
	} else if event.Symbol == s.Symbol2 {
		s.prices2 = append(s.prices2, event.Price)
		if len(s.prices2) > s.Lookback {
			s.prices2 = s.prices2[1:]
		}
	}
	
	// Need data for both symbols
	if len(s.prices1) < s.Lookback || len(s.prices2) < s.Lookback {
		return
	}
	
	// Calculate hedge ratio using OLS regression
	s.calculateHedgeRatio()
	
	// Calculate spread
	s.calculateSpread()
	
	// Calculate z-score
	s.calculateZScore()
	
	// Generate signals
	s.generateSignals(event)
}

func (s *PairsTradingStrategy) calculateHedgeRatio() {
	// Simple linear regression for hedge ratio
	n := float64(len(s.prices1))
	
	var sumX, sumY, sumXY, sumX2 float64
	for i := 0; i < len(s.prices1); i++ {
		x := s.prices2[i]
		y := s.prices1[i]
		sumX += x
		sumY += y
		sumXY += x * y
		sumX2 += x * x
	}
	
	// Slope = hedge ratio
	denominator := n*sumX2 - sumX*sumX
	if denominator != 0 {
		s.hedgeRatio = (n*sumXY - sumX*sumY) / denominator
	}
}

func (s *PairsTradingStrategy) calculateSpread() {
	s.spread = s.spread[:0]
	for i := 0; i < len(s.prices1); i++ {
		spread := s.prices1[i] - s.hedgeRatio*s.prices2[i]
		s.spread = append(s.spread, spread)
	}
}

func (s *PairsTradingStrategy) calculateZScore() {
	// Calculate mean
	var sum float64
	for _, v := range s.spread {
		sum += v
	}
	s.mean = sum / float64(len(s.spread))
	
	// Calculate standard deviation
	var variance float64
	for _, v := range s.spread {
		diff := v - s.mean
		variance += diff * diff
	}
	s.stdDev = math.Sqrt(variance / float64(len(s.spread)))
	
	// Current z-score
	currentSpread := s.spread[len(s.spread)-1]
	if s.stdDev > 0 {
		s.zScore = (currentSpread - s.mean) / s.stdDev
	}
}

func (s *PairsTradingStrategy) generateSignals(event *types.TickEvent) {
	// No position - look for entry
	if s.position1 == 0 && s.position2 == 0 {
		if s.zScore >= s.EntryZScore {
			// Spread too high - short symbol1, long symbol2
			s.EmitSignal(types.SignalEvent{
				Timestamp:  event.Timestamp,
				Symbol:     s.Symbol1,
				StrategyID: s.ID(),
				Action:     types.SignalSell,
				Confidence: math.Min(s.zScore/s.EntryZScore, 1.0),
				Price:      event.Price,
				Metadata: map[string]float64{
					"zscore":      s.zScore,
					"hedge_ratio": s.hedgeRatio,
					"spread":      s.spread[len(s.spread)-1],
				},
			})
			s.EmitSignal(types.SignalEvent{
				Timestamp:  event.Timestamp,
				Symbol:     s.Symbol2,
				StrategyID: s.ID(),
				Action:     types.SignalBuy,
				Confidence: math.Min(s.zScore/s.EntryZScore, 1.0),
				Price:      event.Price,
				Metadata: map[string]float64{
					"zscore":      s.zScore,
					"hedge_ratio": s.hedgeRatio,
					"spread":      s.spread[len(s.spread)-1],
				},
			})
			s.position1 = -1
			s.position2 = 1
		} else if s.zScore <= -s.EntryZScore {
			// Spread too low - long symbol1, short symbol2
			s.EmitSignal(types.SignalEvent{
				Timestamp:  event.Timestamp,
				Symbol:     s.Symbol1,
				StrategyID: s.ID(),
				Action:     types.SignalBuy,
				Confidence: math.Min(-s.zScore/s.EntryZScore, 1.0),
				Price:      event.Price,
				Metadata: map[string]float64{
					"zscore":      s.zScore,
					"hedge_ratio": s.hedgeRatio,
					"spread":      s.spread[len(s.spread)-1],
				},
			})
			s.EmitSignal(types.SignalEvent{
				Timestamp:  event.Timestamp,
				Symbol:     s.Symbol2,
				StrategyID: s.ID(),
				Action:     types.SignalSell,
				Confidence: math.Min(-s.zScore/s.EntryZScore, 1.0),
				Price:      event.Price,
				Metadata: map[string]float64{
					"zscore":      s.zScore,
					"hedge_ratio": s.hedgeRatio,
					"spread":      s.spread[len(s.spread)-1],
				},
			})
			s.position1 = 1
			s.position2 = -1
		}
	} else {
		// Have position - look for exit
		if math.Abs(s.zScore) <= s.ExitZScore {
			// Exit both positions
			if s.position1 < 0 {
				s.EmitSignal(types.SignalEvent{
					Timestamp:  event.Timestamp,
					Symbol:     s.Symbol1,
					StrategyID: s.ID(),
					Action:     types.SignalBuy,
					Confidence: 1.0,
					Price:      event.Price,
				})
			} else if s.position1 > 0 {
				s.EmitSignal(types.SignalEvent{
					Timestamp:  event.Timestamp,
					Symbol:     s.Symbol1,
					StrategyID: s.ID(),
					Action:     types.SignalSell,
					Confidence: 1.0,
					Price:      event.Price,
				})
			}
			
			if s.position2 < 0 {
				s.EmitSignal(types.SignalEvent{
					Timestamp:  event.Timestamp,
					Symbol:     s.Symbol2,
					StrategyID: s.ID(),
					Action:     types.SignalBuy,
					Confidence: 1.0,
					Price:      event.Price,
				})
			} else if s.position2 > 0 {
				s.EmitSignal(types.SignalEvent{
					Timestamp:  event.Timestamp,
					Symbol:     s.Symbol2,
					StrategyID: s.ID(),
					Action:     types.SignalSell,
					Confidence: 1.0,
					Price:      event.Price,
				})
			}
			
			s.position1 = 0
			s.position2 = 0
		}
	}
}

// CointegrationStrategy implements cointegration-based pairs trading
type CointegrationStrategy struct {
	BaseStrategy
	Symbol1      string
	Symbol2      string
	Lookback     int
	EntryZScore  float64
	ExitZScore   float64
	
	prices1      []float64
	prices2      []float64
	residuals    []float64
	beta         float64
	alpha        float64
	mean         float64
	stdDev       float64
	zScore       float64
	mu           sync.RWMutex
}

func NewCointegrationStrategy(symbol1, symbol2 string, lookback int, entryZ, exitZ float64) *CointegrationStrategy {
	return &CointegrationStrategy{
		BaseStrategy: NewBaseStrategy("cointegration_" + symbol1 + "_" + symbol2),
		Symbol1:      symbol1,
		Symbol2:      symbol2,
		Lookback:     lookback,
		EntryZScore:  entryZ,
		ExitZScore:   exitZ,
		prices1:      make([]float64, 0, lookback),
		prices2:      make([]float64, 0, lookback),
		residuals:    make([]float64, 0, lookback),
	}
}

func (s *CointegrationStrategy) OnTick(event *types.TickEvent) {
	s.mu.Lock()
	defer s.mu.Unlock()
	
	// Collect prices
	if event.Symbol == s.Symbol1 {
		s.prices1 = append(s.prices1, event.Price)
		if len(s.prices1) > s.Lookback {
			s.prices1 = s.prices1[1:]
		}
	} else if event.Symbol == s.Symbol2 {
		s.prices2 = append(s.prices2, event.Price)
		if len(s.prices2) > s.Lookback {
			s.prices2 = s.prices2[1:]
		}
	}
	
	if len(s.prices1) < s.Lookback || len(s.prices2) < s.Lookback {
		return
	}
	
	// Estimate cointegration relationship
	s.estimateCointegration()
	
	// Calculate current z-score
	s.calculateZScore()
	
	// Generate signals (similar to pairs trading)
	s.generateSignals(event)
}

func (s *CointegrationStrategy) estimateCointegration() {
	n := float64(len(s.prices1))
	
	// OLS regression: price1 = alpha + beta * price2 + residual
	var sumX, sumY, sumXY, sumX2 float64
	for i := 0; i < len(s.prices1); i++ {
		x := s.prices2[i]
		y := s.prices1[i]
		sumX += x
		sumY += y
		sumXY += x * y
		sumX2 += x * x
	}
	
	denominator := n*sumX2 - sumX*sumX
	if denominator != 0 {
		s.beta = (n*sumXY - sumX*sumY) / denominator
		s.alpha = (sumY - s.beta*sumX) / n
	}
	
	// Calculate residuals
	s.residuals = s.residuals[:0]
	for i := 0; i < len(s.prices1); i++ {
		predicted := s.alpha + s.beta*s.prices2[i]
		residual := s.prices1[i] - predicted
		s.residuals = append(s.residuals, residual)
	}
}

func (s *CointegrationStrategy) calculateZScore() {
	// Calculate mean and std of residuals
	var sum float64
	for _, r := range s.residuals {
		sum += r
	}
	s.mean = sum / float64(len(s.residuals))
	
	var variance float64
	for _, r := range s.residuals {
		diff := r - s.mean
		variance += diff * diff
	}
	s.stdDev = math.Sqrt(variance / float64(len(s.residuals)))
	
	// Current z-score
	currentResidual := s.residuals[len(s.residuals)-1]
	if s.stdDev > 0 {
		s.zScore = (currentResidual - s.mean) / s.stdDev
	}
}

func (s *CointegrationStrategy) generateSignals(event *types.TickEvent) {
	// Similar to pairs trading strategy
	if s.zScore >= s.EntryZScore {
		s.EmitSignal(types.SignalEvent{
			Timestamp:  event.Timestamp,
			Symbol:     s.Symbol1,
			StrategyID: s.ID(),
			Action:     types.SignalSell,
			Confidence: math.Min(s.zScore/s.EntryZScore, 1.0),
			Price:      event.Price,
			Metadata: map[string]float64{
				"zscore": s.zScore,
				"beta":   s.beta,
				"alpha":  s.alpha,
			},
		})
	} else if s.zScore <= -s.EntryZScore {
		s.EmitSignal(types.SignalEvent{
			Timestamp:  event.Timestamp,
			Symbol:     s.Symbol1,
			StrategyID: s.ID(),
			Action:     types.SignalBuy,
			Confidence: math.Min(-s.zScore/s.EntryZScore, 1.0),
			Price:      event.Price,
			Metadata: map[string]float64{
				"zscore": s.zScore,
				"beta":   s.beta,
				"alpha":  s.alpha,
			},
		})
	}
}