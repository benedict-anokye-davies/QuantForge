package engine

import (
	"context"
	"fmt"
	"runtime"
	"sync"
	"sync/atomic"
	"time"

	"github.com/openclaw/skills/quant-researcher/pkg/types"
)

// EventHandler is the interface for all event handlers
type EventHandler interface {
	OnTick(event *types.TickEvent)
	OnSignal(event *types.SignalEvent)
	OnOrder(event *types.OrderEvent)
	OnFill(event *types.FillEvent)
}

// EventHandlerFunc allows functions to implement EventHandler
type EventHandlerFunc struct {
	TickFunc   func(*types.TickEvent)
	SignalFunc func(*types.SignalEvent)
	OrderFunc  func(*types.OrderEvent)
	FillFunc   func(*types.FillEvent)
}

func (e EventHandlerFunc) OnTick(event *types.TickEvent) {
	if e.TickFunc != nil {
		e.TickFunc(event)
	}
}

func (e EventHandlerFunc) OnSignal(event *types.SignalEvent) {
	if e.SignalFunc != nil {
		e.SignalFunc(event)
	}
}

func (e EventHandlerFunc) OnOrder(event *types.OrderEvent) {
	if e.OrderFunc != nil {
		e.OrderFunc(event)
	}
}

func (e EventHandlerFunc) OnFill(event *types.FillEvent) {
	if e.FillFunc != nil {
		e.FillFunc(event)
	}
}

// ExecutionEngine is the high-performance event-driven backtesting engine
type ExecutionEngine struct {
	// Event ring buffer for lock-free event queuing
	eventQueue *types.RingBuffer[eventEnvelope]
	
	// Object pools for zero-allocation hot path
	tickPool   *types.ObjectPool[*types.TickEvent]
	signalPool *types.ObjectPool[*types.SignalEvent]
	orderPool  *types.ObjectPool[*types.OrderEvent]
	fillPool   *types.ObjectPool[*types.FillEvent]
	
	// Handlers
	handlers []EventHandler
	handlerMu sync.RWMutex
	
	// Execution state
	running    atomic.Bool
	paused     atomic.Bool
	sequence   atomic.Uint64
	
	// Worker pool
	workers    int
	workerWg   sync.WaitGroup
	ctx        context.Context
	cancel     context.CancelFunc
	
	// Performance metrics
	ticksProcessed   atomic.Uint64
	eventsProcessed  atomic.Uint64
	processingTimeNs atomic.Uint64
	
	// Portfolio state
	portfolio *types.PortfolioState
	
	// Symbol subscriptions
	subscriptions map[string]bool
	subMu         sync.RWMutex
}

type eventEnvelope struct {
	typ   eventType
	tick  *types.TickEvent
	signal *types.SignalEvent
	order  *types.OrderEvent
	fill   *types.FillEvent
}

type eventType int8

const (
	eventTick eventType = iota
	eventSignal
	eventOrder
	eventFill
)

// Config for engine initialization
type Config struct {
	InitialCash      float64
	BufferSize       uint64
	Workers          int
	EnablePreWarm    bool
}

func DefaultConfig() *Config {
	return &Config{
		InitialCash:   100000.0,
		BufferSize:    1 << 20, // 1M events
		Workers:       runtime.NumCPU(),
		EnablePreWarm: true,
	}
}

func NewExecutionEngine(cfg *Config) *ExecutionEngine {
	if cfg == nil {
		cfg = DefaultConfig()
	}
	
	ctx, cancel := context.WithCancel(context.Background())
	
	e := &ExecutionEngine{
		eventQueue:    types.NewRingBuffer[eventEnvelope](cfg.BufferSize),
		tickPool:      types.NewObjectPool(func() *types.TickEvent { return &types.TickEvent{} }),
		signalPool:    types.NewObjectPool(func() *types.SignalEvent { return &types.SignalEvent{} }),
		orderPool:     types.NewObjectPool(func() *types.OrderEvent { return &types.OrderEvent{} }),
		fillPool:      types.NewObjectPool(func() *types.FillEvent { return &types.FillEvent{} }),
		workers:       cfg.Workers,
		ctx:           ctx,
		cancel:        cancel,
		portfolio:     types.NewPortfolioState(cfg.InitialCash),
		subscriptions: make(map[string]bool),
	}
	
	if cfg.EnablePreWarm {
		e.prewarmPools()
	}
	
	return e
}

func (e *ExecutionEngine) prewarmPools() {
	// Pre-allocate objects to avoid GC pressure during hot path
	for i := 0; i < 10000; i++ {
		e.tickPool.Put(&types.TickEvent{})
		e.signalPool.Put(&types.SignalEvent{})
		e.orderPool.Put(&types.OrderEvent{})
		e.fillPool.Put(&types.FillEvent{})
	}
}

func (e *ExecutionEngine) Start() error {
	if !e.running.CompareAndSwap(false, true) {
		return fmt.Errorf("engine already running")
	}
	
	// Start worker pool
	for i := 0; i < e.workers; i++ {
		e.workerWg.Add(1)
		go e.worker(i)
	}
	
	return nil
}

func (e *ExecutionEngine) Stop() error {
	if !e.running.CompareAndSwap(true, false) {
		return fmt.Errorf("engine not running")
	}
	
	e.cancel()
	e.workerWg.Wait()
	
	return nil
}

func (e *ExecutionEngine) Pause() {
	e.paused.Store(true)
}

func (e *ExecutionEngine) Resume() {
	e.paused.Store(false)
}

func (e *ExecutionEngine) IsRunning() bool {
	return e.running.Load()
}

func (e *ExecutionEngine) IsPaused() bool {
	return e.paused.Load()
}

func (e *ExecutionEngine) worker(id int) {
	defer e.workerWg.Done()
	
	// Pin goroutine to OS thread for better cache locality
	runtime.LockOSThread()
	defer runtime.UnlockOSThread()
	
	for {
		select {
		case <-e.ctx.Done():
			return
		default:
		}
		
		if e.paused.Load() {
			time.Sleep(time.Millisecond)
			continue
		}
		
		env, ok := e.eventQueue.Pop()
		if !ok {
			// No events, brief pause to avoid busy waiting
			time.Sleep(time.Microsecond)
			continue
		}
		
		start := time.Now()
		e.processEvent(&env)
		duration := time.Since(start)
		
		e.eventsProcessed.Add(1)
		e.processingTimeNs.Add(uint64(duration.Nanoseconds()))
	}
}

func (e *ExecutionEngine) processEvent(env *eventEnvelope) {
	e.handlerMu.RLock()
	handlers := make([]EventHandler, len(e.handlers))
	copy(handlers, e.handlers)
	e.handlerMu.RUnlock()
	
	switch env.typ {
	case eventTick:
		if env.tick != nil {
			for _, h := range handlers {
				h.OnTick(env.tick)
			}
			e.ticksProcessed.Add(1)
			e.tickPool.Put(env.tick)
		}
	case eventSignal:
		if env.signal != nil {
			for _, h := range handlers {
				h.OnSignal(env.signal)
			}
			e.signalPool.Put(env.signal)
		}
	case eventOrder:
		if env.order != nil {
			for _, h := range handlers {
				h.OnOrder(env.order)
			}
			e.orderPool.Put(env.order)
		}
	case eventFill:
		if env.fill != nil {
			for _, h := range handlers {
				h.OnFill(env.fill)
			}
			e.portfolio.ApplyFill(env.fill)
			e.fillPool.Put(env.fill)
		}
	}
}

// SubmitTick submits a tick event - zero allocation hot path
func (e *ExecutionEngine) SubmitTick(symbol string, price, volume, bid, ask float64) {
	if !e.running.Load() {
		return
	}
	
	e.subMu.RLock()
	if !e.subscriptions[symbol] {
		e.subMu.RUnlock()
		return
	}
	e.subMu.RUnlock()
	
	tick := e.tickPool.Get()
	tick.Symbol = symbol
	tick.Timestamp = types.NanoTime()
	tick.Price = price
	tick.Volume = volume
	tick.Bid = bid
	tick.Ask = ask
	tick.Sequence = e.sequence.Add(1)
	
	env := eventEnvelope{
		typ:  eventTick,
		tick: tick,
	}
	
	// Spin until we can push (backpressure)
	for !e.eventQueue.Push(env) {
		runtime.Gosched()
	}
}

// SubmitSignal submits a signal event
func (e *ExecutionEngine) SubmitSignal(symbol, strategyID string, action types.SignalAction, confidence, price float64) {
	if !e.running.Load() {
		return
	}
	
	signal := e.signalPool.Get()
	signal.Timestamp = types.NanoTime()
	signal.Symbol = symbol
	signal.StrategyID = strategyID
	signal.Action = action
	signal.Confidence = confidence
	signal.Price = price
	
	env := eventEnvelope{
		typ:    eventSignal,
		signal: signal,
	}
	
	for !e.eventQueue.Push(env) {
		runtime.Gosched()
	}
}

// SubmitOrder submits an order event
func (e *ExecutionEngine) SubmitOrder(order *types.OrderEvent) {
	if !e.running.Load() {
		return
	}
	
	order.Timestamp = types.NanoTime()
	
	env := eventEnvelope{
		typ:   eventOrder,
		order: order,
	}
	
	for !e.eventQueue.Push(env) {
		runtime.Gosched()
	}
}

// SubmitFill submits a fill event
func (e *ExecutionEngine) SubmitFill(fill *types.FillEvent) {
	if !e.running.Load() {
		return
	}
	
	fill.Timestamp = types.NanoTime()
	
	env := eventEnvelope{
		typ:  eventFill,
		fill: fill,
	}
	
	for !e.eventQueue.Push(env) {
		runtime.Gosched()
	}
}

// RegisterHandler adds an event handler
func (e *ExecutionEngine) RegisterHandler(handler EventHandler) {
	e.handlerMu.Lock()
	defer e.handlerMu.Unlock()
	e.handlers = append(e.handlers, handler)
}

// UnregisterHandler removes an event handler
func (e *ExecutionEngine) UnregisterHandler(handler EventHandler) {
	e.handlerMu.Lock()
	defer e.handlerMu.Unlock()
	
	for i, h := range e.handlers {
		if h == handler {
			e.handlers = append(e.handlers[:i], e.handlers[i+1:]...)
			return
		}
	}
}

// Subscribe subscribes to a symbol
func (e *ExecutionEngine) Subscribe(symbol string) {
	e.subMu.Lock()
	defer e.subMu.Unlock()
	e.subscriptions[symbol] = true
}

// Unsubscribe unsubscribes from a symbol
func (e *ExecutionEngine) Unsubscribe(symbol string) {
	e.subMu.Lock()
	defer e.subMu.Unlock()
	delete(e.subscriptions, symbol)
}

// GetPortfolio returns the current portfolio state
func (e *ExecutionEngine) GetPortfolio() *types.PortfolioState {
	return e.portfolio
}

// GetMetrics returns performance metrics
func (e *ExecutionEngine) GetMetrics() EngineMetrics {
	ticks := e.ticksProcessed.Load()
	events := e.eventsProcessed.Load()
	totalNs := e.processingTimeNs.Load()
	
	var avgLatencyNs float64
	if events > 0 {
		avgLatencyNs = float64(totalNs) / float64(events)
	}
	
	return EngineMetrics{
		TicksProcessed:  ticks,
		EventsProcessed: events,
		AvgLatencyNs:    avgLatencyNs,
		QueueDepth:      e.getQueueDepth(),
	}
}

type EngineMetrics struct {
	TicksProcessed  uint64
	EventsProcessed uint64
	AvgLatencyNs    float64
	QueueDepth      uint64
}

func (e *ExecutionEngine) getQueueDepth() uint64 {
	// Access through public methods - for now return 0
	// In production, add public methods to RingBuffer
	return 0
}

// ProcessBatch processes a batch of ticks synchronously (for backtesting)
func (e *ExecutionEngine) ProcessBatch(ticks []*types.TickEvent) {
	for _, tick := range ticks {
		e.subMu.RLock()
		if !e.subscriptions[tick.Symbol] {
			e.subMu.RUnlock()
			continue
		}
		e.subMu.RUnlock()
		
		env := eventEnvelope{
			typ:  eventTick,
			tick: tick,
		}
		
		start := time.Now()
		e.processEvent(&env)
		duration := time.Since(start)
		
		e.ticksProcessed.Add(1)
		e.eventsProcessed.Add(1)
		e.processingTimeNs.Add(uint64(duration.Nanoseconds()))
	}
}