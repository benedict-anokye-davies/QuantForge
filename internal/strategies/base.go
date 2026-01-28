package strategies

import (
	"github.com/openclaw/skills/quant-researcher/internal/engine"
	"github.com/openclaw/skills/quant-researcher/pkg/types"
)

// BaseStrategy provides common functionality for all strategies
type BaseStrategy struct {
	id          string
	signalChan  chan types.SignalEvent
	handlers    []func(types.SignalEvent)
}

func NewBaseStrategy(id string) BaseStrategy {
	return BaseStrategy{
		id:         id,
		signalChan: make(chan types.SignalEvent, 1000),
		handlers:   make([]func(types.SignalEvent), 0),
	}
}

func (b *BaseStrategy) ID() string {
	return b.id
}

func (b *BaseStrategy) OnTick(event *types.TickEvent) {
	// Override in concrete strategies
}

func (b *BaseStrategy) OnSignal(event *types.SignalEvent) {
	// Override in concrete strategies
}

func (b *BaseStrategy) OnOrder(event *types.OrderEvent) {
	// Override in concrete strategies
}

func (b *BaseStrategy) OnFill(event *types.FillEvent) {
	// Override in concrete strategies
}

func (b *BaseStrategy) EmitSignal(signal types.SignalEvent) {
	select {
	case b.signalChan <- signal:
	default:
		// Channel full, drop signal
	}
	
	// Notify handlers
	for _, handler := range b.handlers {
		handler(signal)
	}
}

func (b *BaseStrategy) RegisterSignalHandler(handler func(types.SignalEvent)) {
	b.handlers = append(b.handlers, handler)
}

func (b *BaseStrategy) SignalChannel() <-chan types.SignalEvent {
	return b.signalChan
}

// Ensure BaseStrategy implements EventHandler
var _ engine.EventHandler = (*BaseStrategy)(nil)