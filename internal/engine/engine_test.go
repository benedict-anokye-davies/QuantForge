package engine

import (
	"testing"
	"time"

	"github.com/openclaw/skills/quant-researcher/pkg/types"
)

func TestExecutionEngine(t *testing.T) {
	cfg := &Config{
		InitialCash: 100000.0,
		BufferSize:  1024,
		Workers:     2,
	}
	
	engine := NewExecutionEngine(cfg)
	
	// Test start/stop
	err := engine.Start()
	if err != nil {
		t.Fatalf("Failed to start engine: %v", err)
	}
	
	if !engine.IsRunning() {
		t.Error("Engine should be running")
	}
	
	err = engine.Stop()
	if err != nil {
		t.Fatalf("Failed to stop engine: %v", err)
	}
	
	if engine.IsRunning() {
		t.Error("Engine should not be running")
	}
}

func TestEventProcessing(t *testing.T) {
	cfg := &Config{
		InitialCash: 100000.0,
		BufferSize:  1024,
		Workers:     1,
	}
	
	engine := NewExecutionEngine(cfg)
	
	// Subscribe to symbol
	engine.Subscribe("BTC/USD")
	
	// Start engine
	if err := engine.Start(); err != nil {
		t.Fatalf("Failed to start engine: %v", err)
	}
	defer engine.Stop()
	
	// Submit some ticks
	for i := 0; i < 100; i++ {
		engine.SubmitTick("BTC/USD", 50000.0+float64(i), 1.0, 49999.0, 50001.0)
	}
	
	// Wait for processing
	time.Sleep(100 * time.Millisecond)
	
	// Check metrics
	metrics := engine.GetMetrics()
	if metrics.TicksProcessed == 0 {
		t.Error("Should have processed some ticks")
	}
}

func TestRingBuffer(t *testing.T) {
	rb := types.NewRingBuffer[int](1024)
	
	// Test push/pop
	for i := 0; i < 100; i++ {
		if !rb.Push(i) {
			t.Errorf("Failed to push %d", i)
		}
	}
	
	for i := 0; i < 100; i++ {
		val, ok := rb.Pop()
		if !ok {
			t.Errorf("Failed to pop at %d", i)
		}
		if val != i {
			t.Errorf("Expected %d, got %d", i, val)
		}
	}
}

func BenchmarkRingBuffer(b *testing.B) {
	rb := types.NewRingBuffer[int](1 << 20)
	
	b.ResetTimer()
	b.RunParallel(func(pb *testing.PB) {
		i := 0
		for pb.Next() {
			rb.Push(i)
			rb.Pop()
			i++
		}
	})
}

func BenchmarkSubmitTick(b *testing.B) {
	cfg := &Config{
		InitialCash: 100000.0,
		BufferSize:  1 << 20,
		Workers:     4,
	}
	
	engine := NewExecutionEngine(cfg)
	engine.Subscribe("BTC/USD")
	
	if err := engine.Start(); err != nil {
		b.Fatalf("Failed to start engine: %v", err)
	}
	defer engine.Stop()
	
	b.ResetTimer()
	b.RunParallel(func(pb *testing.PB) {
		i := 0
		for pb.Next() {
			engine.SubmitTick("BTC/USD", 50000.0, 1.0, 49999.0, 50001.0)
			i++
		}
	})
}