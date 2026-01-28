package strategies

import (
	"math"
	"sync"
	"time"

	"github.com/openclaw/skills/quant-researcher/pkg/types"
)

// VWAPStrategy implements Volume-Weighted Average Price execution
type VWAPStrategy struct {
	BaseStrategy
	Symbol       string
	TargetQty    float64
	TimeWindow   time.Duration
	NumSlices    int
	Side         types.OrderSide
	
	startTime    int64
	endTime      int64
	volumes      []float64
	prices       []float64
	cumulativeVol float64
	sliceIndex   int
	executedQty  float64
	mu           sync.RWMutex
}

func NewVWAPStrategy(symbol string, targetQty float64, timeWindow time.Duration, numSlices int, side types.OrderSide) *VWAPStrategy {
	return &VWAPStrategy{
		BaseStrategy: NewBaseStrategy("vwap_" + symbol),
		Symbol:       symbol,
		TargetQty:    targetQty,
		TimeWindow:   timeWindow,
		NumSlices:    numSlices,
		Side:         side,
		volumes:      make([]float64, 0, numSlices),
		prices:       make([]float64, 0, numSlices),
	}
}

func (s *VWAPStrategy) Start() {
	s.mu.Lock()
	defer s.mu.Unlock()
	
	now := types.NanoTime()
	s.startTime = now
	s.endTime = now + int64(s.TimeWindow)
}

func (s *VWAPStrategy) OnTick(event *types.TickEvent) {
	s.mu.Lock()
	defer s.mu.Unlock()
	
	if event.Symbol != s.Symbol {
		return
	}
	
	// Collect volume profile data
	s.volumes = append(s.volumes, event.Volume)
	s.prices = append(s.prices, event.Price)
	s.cumulativeVol += event.Volume
	
	// Check if we should execute a slice
	now := event.Timestamp
	if now > s.endTime {
		return // Time window expired
	}
	
	progress := float64(now-s.startTime) / float64(s.endTime-s.startTime)
	targetProgress := float64(s.sliceIndex+1) / float64(s.NumSlices)
	
	if progress >= targetProgress && s.sliceIndex < s.NumSlices {
		// Calculate VWAP for this slice
		vwap := s.calculateVWAP()
		
		// Calculate slice quantity based on volume profile
		sliceQty := s.calculateSliceQuantity()
		
		if sliceQty > 0 && s.executedQty+sliceQty <= s.TargetQty {
			// Generate order signal
			s.EmitSignal(types.SignalEvent{
				Timestamp:  event.Timestamp,
				Symbol:     s.Symbol,
				StrategyID: s.ID(),
				Action:     s.sideToAction(),
				Confidence: 1.0,
				Price:      vwap,
				Metadata: map[string]float64{
					"slice_qty":    sliceQty,
					"slice_index":  float64(s.sliceIndex),
					"vwap":         vwap,
					"progress":     progress,
				},
			})
			
			s.executedQty += sliceQty
			s.sliceIndex++
			
			// Reset for next slice
			s.volumes = s.volumes[:0]
			s.prices = s.prices[:0]
			s.cumulativeVol = 0
		}
	}
}

func (s *VWAPStrategy) calculateVWAP() float64 {
	if s.cumulativeVol == 0 {
		return 0
	}
	
	var vwap float64
	for i := 0; i < len(s.prices); i++ {
		vwap += s.prices[i] * s.volumes[i]
	}
	return vwap / s.cumulativeVol
}

func (s *VWAPStrategy) calculateSliceQuantity() float64 {
	if s.cumulativeVol == 0 {
		return s.TargetQty / float64(s.NumSlices)
	}
	
	// Proportional to volume in this time slice
	remainingQty := s.TargetQty - s.executedQty
	remainingSlices := s.NumSlices - s.sliceIndex
	
	if remainingSlices == 0 {
		return remainingQty
	}
	
	baseSlice := remainingQty / float64(remainingSlices)
	
	// Adjust based on volume participation
	avgVolume := s.cumulativeVol / float64(len(s.volumes))
	participationRate := 0.05 // 5% of volume
	
	qty := avgVolume * participationRate * float64(remainingSlices)
	
	// Clamp to reasonable bounds
	if qty > baseSlice*2 {
		qty = baseSlice * 2
	}
	if qty < baseSlice*0.5 {
		qty = baseSlice * 0.5
	}
	
	if qty > remainingQty {
		qty = remainingQty
	}
	
	return qty
}

func (s *VWAPStrategy) sideToAction() types.SignalAction {
	if s.Side == types.SideBuy {
		return types.SignalBuy
	}
	return types.SignalSell
}

// TWAPStrategy implements Time-Weighted Average Price execution
type TWAPStrategy struct {
	BaseStrategy
	Symbol       string
	TargetQty    float64
	TimeWindow   time.Duration
	NumSlices    int
	Side         types.OrderSide
	
	startTime    int64
	endTime      int64
	sliceDuration int64
	sliceIndex   int
	executedQty  float64
	lastSliceTime int64
	mu           sync.RWMutex
}

func NewTWAPStrategy(symbol string, targetQty float64, timeWindow time.Duration, numSlices int, side types.OrderSide) *TWAPStrategy {
	return &TWAPStrategy{
		BaseStrategy: NewBaseStrategy("twap_" + symbol),
		Symbol:       symbol,
		TargetQty:    targetQty,
		TimeWindow:   timeWindow,
		NumSlices:    numSlices,
		Side:         side,
	}
}

func (s *TWAPStrategy) Start() {
	s.mu.Lock()
	defer s.mu.Unlock()
	
	now := types.NanoTime()
	s.startTime = now
	s.endTime = now + int64(s.TimeWindow)
	s.sliceDuration = int64(s.TimeWindow) / int64(s.NumSlices)
	s.lastSliceTime = now
}

func (s *TWAPStrategy) OnTick(event *types.TickEvent) {
	s.mu.Lock()
	defer s.mu.Unlock()
	
	if event.Symbol != s.Symbol {
		return
	}
	
	now := event.Timestamp
	if now > s.endTime {
		return // Time window expired
	}
	
	// Check if it's time for next slice
	if now-s.lastSliceTime >= s.sliceDuration && s.sliceIndex < s.NumSlices {
		remainingQty := s.TargetQty - s.executedQty
		remainingSlices := s.NumSlices - s.sliceIndex
		
		sliceQty := remainingQty / float64(remainingSlices)
		
		s.EmitSignal(types.SignalEvent{
			Timestamp:  event.Timestamp,
			Symbol:     s.Symbol,
			StrategyID: s.ID(),
			Action:     s.sideToAction(),
			Confidence: 1.0,
			Price:      event.Price,
			Metadata: map[string]float64{
				"slice_qty":   sliceQty,
				"slice_index": float64(s.sliceIndex),
				"progress":    float64(now-s.startTime) / float64(s.endTime-s.startTime),
			},
		})
		
		s.executedQty += sliceQty
		s.sliceIndex++
		s.lastSliceTime = now
	}
}

func (s *TWAPStrategy) sideToAction() types.SignalAction {
	if s.Side == types.SideBuy {
		return types.SignalBuy
	}
	return types.SignalSell
}

// ImplementationShortfallStrategy implements implementation shortfall / arrival price
type ImplementationShortfallStrategy struct {
	BaseStrategy
	Symbol        string
	TargetQty     float64
	Side          types.OrderSide
	Urgency       float64 // 0-1, higher = more urgent
	
	arrivalPrice  float64
	startTime     int64
	marketImpact  float64
	executedQty   float64
	mu            sync.RWMutex
}

func NewImplementationShortfallStrategy(symbol string, targetQty float64, side types.OrderSide, urgency float64) *ImplementationShortfallStrategy {
	return &ImplementationShortfallStrategy{
		BaseStrategy: NewBaseStrategy("is_" + symbol),
		Symbol:       symbol,
		TargetQty:    targetQty,
		Side:         side,
		Urgency:      urgency,
	}
}

func (s *ImplementationShortfallStrategy) Start(arrivalPrice float64) {
	s.mu.Lock()
	defer s.mu.Unlock()
	
	s.arrivalPrice = arrivalPrice
	s.startTime = types.NanoTime()
}

func (s *ImplementationShortfallStrategy) OnTick(event *types.TickEvent) {
	s.mu.Lock()
	defer s.mu.Unlock()
	
	if event.Symbol != s.Symbol {
		return
	}
	
	if s.executedQty >= s.TargetQty {
		return
	}
	
	// Calculate optimal execution rate based on urgency and market conditions
	remainingQty := s.TargetQty - s.executedQty
	priceMove := (event.Price - s.arrivalPrice) / s.arrivalPrice
	
	// Higher urgency or adverse price move = execute faster
	executionRate := s.Urgency
	if s.Side == types.SideBuy && priceMove > 0 {
		executionRate = math.Min(1.0, executionRate*1.5)
	} else if s.Side == types.SideSell && priceMove < 0 {
		executionRate = math.Min(1.0, executionRate*1.5)
	}
	
	// Calculate order size
	orderQty := remainingQty * executionRate
	
	// Limit order size based on available liquidity
	maxOrderSize := event.Volume * 0.1 // 10% of volume
	if orderQty > maxOrderSize {
		orderQty = maxOrderSize
	}
	
	if orderQty > 0 {
		s.EmitSignal(types.SignalEvent{
			Timestamp:  event.Timestamp,
			Symbol:     s.Symbol,
			StrategyID: s.ID(),
			Action:     s.sideToAction(),
			Confidence: executionRate,
			Price:      event.Price,
			Metadata: map[string]float64{
				"order_qty":    orderQty,
				"remaining":    remainingQty,
				"price_move":   priceMove,
				"urgency":      s.Urgency,
				"arrival_price": s.arrivalPrice,
			},
		})
		
		s.executedQty += orderQty
	}
}

func (s *ImplementationShortfallStrategy) sideToAction() types.SignalAction {
	if s.Side == types.SideBuy {
		return types.SignalBuy
	}
	return types.SignalSell
}