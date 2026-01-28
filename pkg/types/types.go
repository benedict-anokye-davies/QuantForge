package types

import (
	"sync"
	"sync/atomic"
	"time"
)

// PricePoint represents a single price with timestamp
// Aligned for cache efficiency - fits in single cache line (64 bytes)
type PricePoint struct {
	Timestamp int64   // 8 bytes
	Price     float64 // 8 bytes
	Volume    float64 // 8 bytes
	Bid       float64 // 8 bytes
	Ask       float64 // 8 bytes
	Sequence  uint64  // 8 bytes
	_         [8]byte // padding to 64 bytes
}

// TickEvent is the core event type for the event-driven engine
// Uses value semantics for zero-allocation hot path
type TickEvent struct {
	Symbol    string
	Timestamp int64
	Price     float64
	Volume    float64
	Bid       float64
	Ask       float64
	Sequence  uint64
}

// SignalEvent represents a trading signal
type SignalEvent struct {
	Timestamp  int64
	Symbol     string
	StrategyID string
	Action     SignalAction
	Confidence float64
	Price      float64
	Metadata   map[string]float64
}

type SignalAction int8

const (
	SignalHold SignalAction = iota
	SignalBuy
	SignalSell
)

// OrderEvent represents an order
type OrderEvent struct {
	ID          string
	Timestamp   int64
	Symbol      string
	Side        OrderSide
	OrderType   OrderType
	Quantity    float64
	Price       float64
	StopPrice   float64
	StrategyID  string
}

type OrderSide int8

const (
	SideBuy OrderSide = iota
	SideSell
)

type OrderType int8

const (
	OrderMarket OrderType = iota
	OrderLimit
	OrderStop
	OrderStopLimit
)

// FillEvent represents a filled order
type FillEvent struct {
	Timestamp int64
	OrderID   string
	Symbol    string
	Side      OrderSide
	Price     float64
	Quantity  float64
	Fee       float64
	Slippage  float64
}

// Position tracks current position for a symbol
type Position struct {
	Symbol       string
	Quantity     float64
	AvgEntryPrice float64
	OpenedAt     int64
	UpdatedAt    int64
}

// PortfolioState tracks entire portfolio
type PortfolioState struct {
	Cash          float64
	Equity        float64
	Positions     map[string]*Position
	OpenOrders    map[string]*OrderEvent
	TotalValue    float64
	DailyPnL      float64
	MaxDrawdown   float64
	PeakEquity    float64
	mu            sync.RWMutex
}

func NewPortfolioState(initialCash float64) *PortfolioState {
	return &PortfolioState{
		Cash:        initialCash,
		Equity:      initialCash,
		Positions:   make(map[string]*Position),
		OpenOrders:  make(map[string]*OrderEvent),
		TotalValue:  initialCash,
		PeakEquity:  initialCash,
	}
}

func (p *PortfolioState) UpdatePrice(symbol string, price float64) {
	p.mu.Lock()
	defer p.mu.Unlock()
	
	if pos, exists := p.Positions[symbol]; exists {
		if pos.Quantity > 0 {
			p.Equity += (price - pos.AvgEntryPrice) * pos.Quantity
		}
	}
	
	p.TotalValue = p.Cash + p.calculatePositionValues(price)
	
	if p.TotalValue > p.PeakEquity {
		p.PeakEquity = p.TotalValue
	}
	
	dd := (p.PeakEquity - p.TotalValue) / p.PeakEquity
	if dd > p.MaxDrawdown {
		p.MaxDrawdown = dd
	}
}

func (p *PortfolioState) calculatePositionValues(currentPrice float64) float64 {
	var total float64
	for _, pos := range p.Positions {
		total += pos.Quantity * currentPrice
	}
	return total
}

func (p *PortfolioState) ApplyFill(fill *FillEvent) {
	p.mu.Lock()
	defer p.mu.Unlock()
	
	cost := fill.Price * fill.Quantity
	fee := fill.Fee
	
	if fill.Side == SideBuy {
		p.Cash -= cost + fee
		if pos, exists := p.Positions[fill.Symbol]; exists {
			totalCost := pos.AvgEntryPrice*pos.Quantity + cost
			pos.Quantity += fill.Quantity
			pos.AvgEntryPrice = totalCost / pos.Quantity
		} else {
			p.Positions[fill.Symbol] = &Position{
				Symbol:        fill.Symbol,
				Quantity:      fill.Quantity,
				AvgEntryPrice: fill.Price,
				OpenedAt:      fill.Timestamp,
			}
		}
	} else {
		p.Cash += cost - fee
		if pos, exists := p.Positions[fill.Symbol]; exists {
			pos.Quantity -= fill.Quantity
			if pos.Quantity <= 0 {
				delete(p.Positions, fill.Symbol)
			}
		}
	}
	
	delete(p.OpenOrders, fill.OrderID)
}

// RingBuffer is a lock-free circular buffer for high-throughput events
type RingBuffer[T any] struct {
	buffer []T
	head   atomic.Uint64
	tail   atomic.Uint64
	size   uint64
	mask   uint64
}

func NewRingBuffer[T any](size uint64) *RingBuffer[T] {
	// Round up to power of 2
	size--
	size |= size >> 1
	size |= size >> 2
	size |= size >> 4
	size |= size >> 8
	size |= size >> 16
	size |= size >> 32
	size++
	
	return &RingBuffer[T]{
		buffer: make([]T, size),
		size:   size,
		mask:   size - 1,
	}
}

func (r *RingBuffer[T]) Push(item T) bool {
	tail := r.tail.Load()
	next := (tail + 1) & r.mask
	
	if next == r.head.Load() {
		return false // Buffer full
	}
	
	r.buffer[tail&r.mask] = item
	r.tail.Store(next)
	return true
}

func (r *RingBuffer[T]) Pop() (T, bool) {
	var zero T
	head := r.head.Load()
	
	if head == r.tail.Load() {
		return zero, false // Buffer empty
	}
	
	item := r.buffer[head&r.mask]
	r.head.Store((head + 1) & r.mask)
	return item, true
}

// ObjectPool provides zero-allocation object reuse
type ObjectPool[T any] struct {
	pool sync.Pool
	New  func() T
}

func NewObjectPool[T any](newFunc func() T) *ObjectPool[T] {
	return &ObjectPool[T]{
		pool: sync.Pool{New: func() interface{} { return newFunc() }},
		New:  newFunc,
	}
}

func (p *ObjectPool[T]) Get() T {
	return p.pool.Get().(T)
}

func (p *ObjectPool[T]) Put(item T) {
	p.pool.Put(item)
}

// TimeSeries stores price history with circular buffer
type TimeSeries struct {
	data  []PricePoint
	head  int
	size  int
	count int
	mu    sync.RWMutex
}

func NewTimeSeries(size int) *TimeSeries {
	return &TimeSeries{
		data: make([]PricePoint, size),
		size: size,
	}
}

func (ts *TimeSeries) Add(point PricePoint) {
	ts.mu.Lock()
	defer ts.mu.Unlock()
	
	ts.data[ts.head] = point
	ts.head = (ts.head + 1) % ts.size
	if ts.count < ts.size {
		ts.count++
	}
}

func (ts *TimeSeries) Get(index int) (PricePoint, bool) {
	ts.mu.RLock()
	defer ts.mu.RUnlock()
	
	if index < 0 || index >= ts.count {
		return PricePoint{}, false
	}
	
	idx := (ts.head - ts.count + index) % ts.size
	if idx < 0 {
		idx += ts.size
	}
	return ts.data[idx], true
}

func (ts *TimeSeries) Len() int {
	ts.mu.RLock()
	defer ts.mu.RUnlock()
	return ts.count
}

func (ts *TimeSeries) Last() (PricePoint, bool) {
	ts.mu.RLock()
	defer ts.mu.RUnlock()
	
	if ts.count == 0 {
		return PricePoint{}, false
	}
	
	idx := (ts.head - 1) % ts.size
	if idx < 0 {
		idx += ts.size
	}
	return ts.data[idx], true
}

func (ts *TimeSeries) ToSlice() []PricePoint {
	ts.mu.RLock()
	defer ts.mu.RUnlock()
	
	result := make([]PricePoint, ts.count)
	for i := 0; i < ts.count; i++ {
		idx := (ts.head - ts.count + i) % ts.size
		if idx < 0 {
			idx += ts.size
		}
		result[i] = ts.data[idx]
	}
	return result
}

// NanoTime returns current time in nanoseconds
func NanoTime() int64 {
	return time.Now().UnixNano()
}

// MilliTime returns current time in milliseconds
func MilliTime() int64 {
	return time.Now().UnixMilli()
}