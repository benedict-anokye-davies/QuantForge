package strategies

import (
	"math"
	"sync"

	"github.com/openclaw/skills/quant-researcher/pkg/types"
)

// AvellanedaStoikovStrategy implements the Avellaneda-Stoikov market making model
type AvellanedaStoikovStrategy struct {
	BaseStrategy
	Symbol           string
	Gamma            float64 // Risk aversion parameter
	Sigma            float64 // Volatility estimate
	K                float64 // Order arrival intensity
	QMax             float64 // Maximum inventory
	Delta            float64 // Time horizon
	
	// State
	inventory        float64
	midPrice         float64
	spread           float64
	reservationPrice float64
	bidQuote         float64
	askQuote         float64
	
	// Price history for volatility estimation
	priceHistory     []float64
	returns          []float64
	volatilityWindow int
	
	mu               sync.RWMutex
}

func NewAvellanedaStoikovStrategy(symbol string, gamma, sigma, k, qMax, delta float64) *AvellanedaStoikovStrategy {
	return &AvellanedaStoikovStrategy{
		BaseStrategy:     NewBaseStrategy("avellaneda_stoikov_" + symbol),
		Symbol:           symbol,
		Gamma:            gamma,
		Sigma:            sigma,
		K:                k,
		QMax:             qMax,
		Delta:            delta,
		priceHistory:     make([]float64, 0, 100),
		returns:          make([]float64, 0, 100),
		volatilityWindow: 20,
	}
}

func (s *AvellanedaStoikovStrategy) OnTick(event *types.TickEvent) {
	s.mu.Lock()
	defer s.mu.Unlock()
	
	if event.Symbol != s.Symbol {
		return
	}
	
	// Update mid price
	s.midPrice = (event.Bid + event.Ask) / 2
	
	// Update price history for volatility estimation
	s.priceHistory = append(s.priceHistory, s.midPrice)
	if len(s.priceHistory) > s.volatilityWindow+1 {
		s.priceHistory = s.priceHistory[1:]
	}
	
	// Calculate returns and update volatility estimate
	if len(s.priceHistory) >= 2 {
		ret := math.Log(s.priceHistory[len(s.priceHistory)-1] / s.priceHistory[len(s.priceHistory)-2])
		s.returns = append(s.returns, ret)
		if len(s.returns) > s.volatilityWindow {
			s.returns = s.returns[1:]
		}
		
		// Update volatility estimate
		if len(s.returns) >= s.volatilityWindow {
			s.Sigma = s.calculateVolatility()
		}
	}
	
	// Calculate reservation price
	s.calculateReservationPrice()
	
	// Calculate optimal spread
	s.calculateSpread()
	
	// Calculate bid/ask quotes
	s.bidQuote = s.reservationPrice - s.spread/2
	s.askQuote = s.reservationPrice + s.spread/2
	
	// Ensure quotes are within market bounds
	if s.bidQuote >= event.Ask {
		s.bidQuote = event.Ask - 0.01
	}
	if s.askQuote <= event.Bid {
		s.askQuote = event.Bid + 0.01
	}
	
	// Generate signals
	s.generateSignals(event)
}

func (s *AvellanedaStoikovStrategy) calculateReservationPrice() {
	// Reservation price adjustment based on inventory
	// r(s,t) = s - q * gamma * sigma^2 * (T-t)
	inventoryAdjustment := s.inventory * s.Gamma * s.Sigma * s.Sigma * s.Delta
	s.reservationPrice = s.midPrice - inventoryAdjustment
}

func (s *AvellanedaStoikovStrategy) calculateSpread() {
	// Optimal spread from Avellaneda-Stoikov model
	// delta = gamma * sigma^2 * (T-t) + (2/gamma) * ln(1 + gamma/k)
	timeComponent := s.Gamma * s.Sigma * s.Sigma * s.Delta
	orderBookComponent := (2.0 / s.Gamma) * math.Log(1.0 + s.Gamma/s.K)
	s.spread = timeComponent + orderBookComponent
	
	// Minimum spread
	minSpread := s.midPrice * 0.0001 // 1 basis point
	if s.spread < minSpread {
		s.spread = minSpread
	}
}

func (s *AvellanedaStoikovStrategy) calculateVolatility() float64 {
	if len(s.returns) == 0 {
		return s.Sigma
	}
	
	var sumSquares float64
	for _, r := range s.returns {
		sumSquares += r * r
	}
	
	// Annualized volatility
	variance := sumSquares / float64(len(s.returns))
	return math.Sqrt(variance * 252.0) // Assuming daily returns, annualize
}

func (s *AvellanedaStoikovStrategy) generateSignals(event *types.TickEvent) {
	// Calculate order sizes based on inventory skew
	baseSize := 1.0 // Base order size
	
	// Inventory skew - reduce size as we approach limits
	inventorySkew := 1.0 - math.Abs(s.inventory)/s.QMax
	if inventorySkew < 0.1 {
		inventorySkew = 0.1
	}
	
	bidSize := baseSize * inventorySkew
	askSize := baseSize * inventorySkew
	
	// Further skew based on inventory direction
	if s.inventory > 0 {
		// Long inventory - want to sell more
		askSize *= (1.0 + s.inventory/s.QMax)
		bidSize *= (1.0 - s.inventory/s.QMax)
	} else if s.inventory < 0 {
		// Short inventory - want to buy more
		bidSize *= (1.0 + math.Abs(s.inventory)/s.QMax)
		askSize *= (1.0 - math.Abs(s.inventory)/s.QMax)
	}
	
	// Emit bid signal
	if bidSize > 0 && s.inventory < s.QMax {
		s.EmitSignal(types.SignalEvent{
			Timestamp:  event.Timestamp,
			Symbol:     s.Symbol,
			StrategyID: s.ID(),
			Action:     types.SignalBuy,
			Confidence: 1.0,
			Price:      s.bidQuote,
			Metadata: map[string]float64{
				"order_size":        bidSize,
				"quote_type":        0, // 0 = bid
				"inventory":         s.inventory,
				"reservation_price": s.reservationPrice,
				"spread":            s.spread,
			},
		})
	}
	
	// Emit ask signal
	if askSize > 0 && s.inventory > -s.QMax {
		s.EmitSignal(types.SignalEvent{
			Timestamp:  event.Timestamp,
			Symbol:     s.Symbol,
			StrategyID: s.ID(),
			Action:     types.SignalSell,
			Confidence: 1.0,
			Price:      s.askQuote,
			Metadata: map[string]float64{
				"order_size":        askSize,
				"quote_type":        1, // 1 = ask
				"inventory":         s.inventory,
				"reservation_price": s.reservationPrice,
				"spread":            s.spread,
			},
		})
	}
}

func (s *AvellanedaStoikovStrategy) UpdateInventory(delta float64) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.inventory += delta
}

func (s *AvellanedaStoikovStrategy) GetInventory() float64 {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.inventory
}

func (s *AvellanedaStoikovStrategy) GetQuotes() (bid, ask float64) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.bidQuote, s.askQuote
}

// SimpleMarketMaker is a simpler market making strategy
type SimpleMarketMaker struct {
	BaseStrategy
	Symbol       string
	SpreadBps    float64 // Spread in basis points
	BaseSize     float64
	MaxInventory float64
	
	inventory    float64
	mu           sync.RWMutex
}

func NewSimpleMarketMaker(symbol string, spreadBps, baseSize, maxInventory float64) *SimpleMarketMaker {
	return &SimpleMarketMaker{
		BaseStrategy: NewBaseStrategy("simple_mm_" + symbol),
		Symbol:       symbol,
		SpreadBps:    spreadBps,
		BaseSize:     baseSize,
		MaxInventory: maxInventory,
	}
}

func (s *SimpleMarketMaker) OnTick(event *types.TickEvent) {
	s.mu.Lock()
	defer s.mu.Unlock()
	
	if event.Symbol != s.Symbol {
		return
	}
	
	midPrice := (event.Bid + event.Ask) / 2
	spreadAmount := midPrice * s.SpreadBps / 10000.0
	
	bidPrice := midPrice - spreadAmount/2
	askPrice := midPrice + spreadAmount/2
	
	// Inventory adjustment
	bidSize := s.BaseSize
	askSize := s.BaseSize
	
	if s.inventory > 0 {
		// Reduce bid size when long
		bidSize *= (1.0 - s.inventory/s.MaxInventory)
		askSize *= (1.0 + s.inventory/s.MaxInventory)
	} else if s.inventory < 0 {
		// Reduce ask size when short
		askSize *= (1.0 - math.Abs(s.inventory)/s.MaxInventory)
		bidSize *= (1.0 + math.Abs(s.inventory)/s.MaxInventory)
	}
	
	// Emit bid
	if bidSize > 0 && s.inventory < s.MaxInventory {
		s.EmitSignal(types.SignalEvent{
			Timestamp:  event.Timestamp,
			Symbol:     s.Symbol,
			StrategyID: s.ID(),
			Action:     types.SignalBuy,
			Confidence: 1.0,
			Price:      bidPrice,
			Metadata: map[string]float64{
				"order_size": bidSize,
				"quote_type": 0,
				"inventory":  s.inventory,
			},
		})
	}
	
	// Emit ask
	if askSize > 0 && s.inventory > -s.MaxInventory {
		s.EmitSignal(types.SignalEvent{
			Timestamp:  event.Timestamp,
			Symbol:     s.Symbol,
			StrategyID: s.ID(),
			Action:     types.SignalSell,
			Confidence: 1.0,
			Price:      askPrice,
			Metadata: map[string]float64{
				"order_size": askSize,
				"quote_type": 1,
				"inventory":  s.inventory,
			},
		})
	}
}

func (s *SimpleMarketMaker) UpdateInventory(delta float64) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.inventory += delta
}

func (s *SimpleMarketMaker) GetInventory() float64 {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.inventory
}