# Quant Researcher

A high-performance quantitative trading engine in Go, designed for production-grade algorithmic trading.

## Features

- **High Performance**: 1M+ ticks/second, sub-microsecond latency
- **Event-Driven Architecture**: Market data → Signals → Orders → Fills
- **Zero-Allocation Hot Path**: Object pools and lock-free queues
- **Multiple Strategies**: Mean reversion, momentum, stat arb, market making
- **Risk Management**: Kelly Criterion, drawdown controls, circuit breakers
- **Advanced Analytics**: Walk-forward optimization, Monte Carlo simulation

## Quick Start

```bash
# Build
cd skills/quant-researcher
make build

# Run backtest
./build/quant backtest --strategy momentum --symbols BTC/USD --timeframe 1h

# Optimize parameters
./build/quant optimize --strategy bollinger --symbols BTC/USD --params window,10,30,2
```

## Performance

Benchmark results on AMD Ryzen 9 5950X:

| Metric | Value |
|--------|-------|
| Tick Processing | 1.2M ticks/sec |
| Latency (p99) | 450 nanoseconds |
| Memory/1M ticks | 12 MB |
| GC Pause | < 100 microseconds |

## Architecture

```
CLI → gRPC/WebSocket → Event Engine → Strategies → Risk → Execution
                            ↓
                    Memory-Mapped Data
                            ↓
                    SQLite/ClickHouse Storage
```

## Strategies

| Strategy | Type | Description |
|----------|------|-------------|
| Bollinger Bands | Mean Reversion | Volatility-based mean reversion |
| RSI | Mean Reversion | Overbought/oversold indicator |
| MACD | Momentum | Moving average convergence |
| EMA Crossover | Momentum | Trend following |
| Pairs Trading | Stat Arb | Cointegration-based |
| Avellaneda-Stoikov | Market Making | Optimal quote placement |
| VWAP | Execution | Volume-weighted average price |

## Configuration

Create `config.yaml`:

```yaml
engine:
  buffer_size: 1048576
  workers: 8
  
risk:
  max_drawdown: 0.20
  daily_loss_limit: 10000
  kelly_fraction: 0.25
  
strategies:
  momentum:
    fast_period: 12
    slow_period: 26
```

## Development

```bash
# Run tests
make test

# Run benchmarks
make bench

# Generate protobuf
make proto

# Format code
make fmt
```

## License

MIT