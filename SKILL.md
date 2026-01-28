# Quant Researcher Skill

High-performance quantitative research and backtesting engine in Go.

## Overview

This skill provides a production-grade quantitative trading platform with:
- **1M+ ticks/second** processing capability
- **Sub-microsecond** latency per event
- Event-driven architecture with zero-allocation hot path
- Lock-free queues for maximum throughput
- Memory-mapped data loading for large datasets
- Goroutine-based parallel backtesting

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     CLI / gRPC / WebSocket                   │
├─────────────────────────────────────────────────────────────┤
│                    Event-Driven Engine                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  Ticks   │→ │ Signals  │→ │  Orders  │→ │  Fills   │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
├─────────────────────────────────────────────────────────────┤
│                    Zero-Allocation Hot Path                  │
│              Lock-Free Ring Buffer + Object Pools            │
├─────────────────────────────────────────────────────────────┤
│                      Strategies                              │
│  • Mean Reversion  • Momentum  • Statistical Arbitrage      │
│  • VWAP/TWAP       • Market Making (Avellaneda-Stoikov)     │
├─────────────────────────────────────────────────────────────┤
│                    Risk Management                           │
│  • Kelly Criterion  • ATR Sizing  • Drawdown Kill Switches  │
│  • Daily Loss Limits  • Consecutive Loss Circuit Breakers   │
├─────────────────────────────────────────────────────────────┤
│                    Data Layer                                │
│  • Memory-Mapped Files  • SQLite  • ClickHouse              │
└─────────────────────────────────────────────────────────────┘
```

## Installation

```bash
cd skills/quant-researcher
go mod download
go build -o quant cmd/quant/main.go
```

## CLI Usage

### Backtest

```bash
# Momentum strategy backtest
quant backtest --strategy momentum --symbols BTC/USD,ETH/USD --timeframe 1h

# Mean reversion with custom parameters
quant backtest --strategy bollinger --symbols AAPL --start 2023-01-01 --end 2023-12-31

# Output results as JSON
quant backtest --strategy macd --symbols BTC/USD --output json
```

### Optimization

```bash
# Walk-forward optimization
quant optimize --strategy momentum --symbols BTC/USD --params fast,10,50,5 --params slow,20,100,10

# Grid search with custom windows
quant optimize --strategy mean_reversion --params window,10,30,2 --train 1000 --test 200
```

### Live Trading

```bash
# Paper trading mode
quant live --strategy momentum --symbols BTC/USD --paper --cash 10000

# Market making
quant live --strategy avellaneda --symbols BTC/USD,ETH/USD --paper
```

### Monte Carlo Simulation

```bash
# Validate strategy robustness
quant monte-carlo --strategy momentum --symbols BTC/USD --simulations 10000
```

## Strategies

### Mean Reversion
- **Bollinger Bands**: Mean reversion with volatility bands
- **RSI**: Overbought/oversold signals
- **Z-Score**: Statistical mean reversion

### Momentum
- **MACD**: Moving average convergence divergence
- **EMA Crossover**: Trend following with exponential moving averages
- **Breakout**: Volatility-based breakout detection

### Statistical Arbitrage
- **Pairs Trading**: Cointegration-based pairs trading
- **Cointegration**: Statistical relationship exploitation

### Execution Algorithms
- **VWAP**: Volume-weighted average price execution
- **TWAP**: Time-weighted average price execution
- **Implementation Shortfall**: Arrival price optimization

### Market Making
- **Avellaneda-Stoikov**: Optimal market making with inventory control
- **Simple Market Maker**: Fixed spread market making

## Risk Management

### Position Sizing
- **Kelly Criterion**: Optimal bet sizing based on edge
- **ATR-Based**: Volatility-adjusted position sizing

### Kill Switches
- **Max Drawdown**: Automatic trading halt at drawdown threshold
- **Daily Loss Limit**: Daily loss circuit breaker
- **Consecutive Losses**: Circuit breaker after N consecutive losses

## Performance Metrics

- Sharpe Ratio
- Sortino Ratio
- Calmar Ratio
- Maximum Drawdown
- VaR / CVaR (95%, 99%)
- Win Rate
- Profit Factor
- Expectancy
- Transaction Cost Analysis

## API

### gRPC

```protobuf
service QuantService {
  rpc SubmitTick(Tick) returns (SubmitResponse);
  rpc GetPortfolio(PortfolioRequest) returns (Portfolio);
  rpc GetMetrics(MetricsRequest) returns (MetricsResponse);
  rpc StreamTicks(StreamRequest) returns (stream Tick);
  rpc StreamSignals(StreamRequest) returns (stream Signal);
  rpc RunBacktest(BacktestRequest) returns (BacktestResponse);
  rpc Optimize(OptimizeRequest) returns (stream OptimizationProgress);
}
```

### WebSocket

Connect to `ws://localhost:8080/ws` for real-time updates:

```javascript
const ws = new WebSocket('ws://localhost:8080/ws');

// Subscribe to symbol
ws.send(JSON.stringify({ type: 'subscribe', symbol: 'BTC/USD' }));

// Handle messages
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  console.log(msg.type, msg.data);
};
```

## Configuration

### Engine Configuration

```go
cfg := &engine.Config{
    InitialCash:   100000.0,
    BufferSize:    1 << 20,  // 1M events
    Workers:       8,        // Number of worker goroutines
    EnablePreWarm: true,     // Pre-allocate object pools
}
```

### Risk Configuration

```go
cfg := &risk.Config{
    KellyFraction:        0.25,   // Quarter Kelly
    ATRMultiplier:        2.0,
    MaxDrawdown:          0.20,   // 20% max drawdown
    DailyLossLimit:       10000.0,
    MaxConsecutiveLosses: 5,
}
```

## Performance Tuning

### For Maximum Throughput
- Use `runtime.LockOSThread()` in hot paths
- Enable CPU profiling to identify bottlenecks
- Tune `BufferSize` based on tick frequency
- Use memory-mapped files for historical data

### For Minimum Latency
- Set `GOMAXPROCS` to number of physical cores
- Disable GC during trading: `debug.SetGCPercent(-1)`
- Use huge pages for large buffers
- Pin goroutines to specific cores

## Testing

```bash
# Run all tests
go test ./...

# Run benchmarks
go test -bench=. -benchmem ./...

# Profile performance
go test -cpuprofile=cpu.prof -memprofile=mem.prof -bench=.
```

## License

MIT License - See LICENSE file for details