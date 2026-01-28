"""
Backtest Engine Module

Main backtesting engine that orchestrates the event-driven simulation.

The BacktestEngine wires together all components:
- DataHandler: Provides market data bars
- Strategy: Generates trading signals
- RiskManager: Validates trades against risk limits
- ExecutionSimulator: Simulates order fills with costs
- Portfolio: Tracks positions and P&L

Event Loop:
    while data_handler.has_more_data():
        events = data_handler.update_bars()
        event_bus.run()  # Process all events
        # Record state

Key Features:
- Event-driven architecture for realistic simulation
- Pre-trade risk checks
- Realistic execution with slippage and commission
- Comprehensive performance metrics
- No look-ahead bias

Example:
    >>> from quantforge.core.events import EventBus
    >>> from quantforge.core.data_handler import HistoricalCSVDataHandler
    >>> from quantforge.strategies.momentum import MomentumStrategy
    >>> from quantforge.execution.simulator import ExecutionSimulator
    >>> from quantforge.risk.risk_manager import RiskManager
    >>> from quantforge.core.portfolio import Portfolio
    >>>
    >>> # Initialize components
    >>> bus = EventBus()
    >>> data = HistoricalCSVDataHandler("data/", ["AAPL"], bus)
    >>> strategy = MomentumStrategy("mom", bus, ["AAPL"])
    >>> portfolio = Portfolio(bus, initial_cash=100000)
    >>> execution = ExecutionSimulator(bus)
    >>> risk = RiskManager(bus)
    >>>
    >>> # Create and run backtest
    >>> engine = BacktestEngine(
    ...     data_handler=data,
    ...     strategy=strategy,
    ...     portfolio=portfolio,
    ...     execution_simulator=execution,
    ...     risk_manager=risk,
    ...     event_bus=bus
    ... )
    >>>
    >>> results = engine.run()
    >>> print(f"Total Return: {results['total_return_pct']:.2%}")
    >>> print(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
"""



from dataclasses import dataclass, field

from datetime import datetime

from typing import Dict, List, Optional, Any, Callable

from pathlib import Path

import json



import numpy as np

import pandas as pd



from quantforge.core.events import (

    EventBus,

    EventType,

    MarketDataEvent,

    SignalEvent,

    OrderEvent,

    OrderType,

    FillEvent,

    Event,

)

from quantforge.core.data_handler import DataHandler

from quantforge.core.portfolio import Portfolio

from quantforge.strategies.base import Strategy

from quantforge.execution.simulator import ExecutionSimulator

from quantforge.risk.risk_manager import RiskManager

from quantforge.risk.position_sizing import PositionSizer





@dataclass

class BacktestConfig:

    """Configuration for backtest execution."""

    initial_capital: float = 100000.0

    position_sizing_method: str = 'volatility_target'

    target_volatility: float = 0.10

    rebalance_threshold: float = 0.05

    record_interval: str = 'daily'

    enable_risk_management: bool = True

    max_positions: int = 10





    max_position_pct: float = 0.20

    max_drawdown_pct: float = 0.20

    max_leverage: float = 2.0





class BacktestEngine:

    """
    Main backtesting engine for event-driven strategy simulation.

    The engine orchestrates the flow of data and events:

    1. DataHandler emits MarketDataEvents
    2. Strategy processes data and emits SignalEvents
    3. Engine converts signals to OrderEvents (with position sizing)
    4. RiskManager validates orders
    5. ExecutionSimulator converts orders to FillEvents
    6. Portfolio processes fills and updates state
    7. Loop continues until data exhausted

    Attributes:
        config: Backtest configuration
        data_handler: Data source
        strategy: Trading strategy
        portfolio: Portfolio tracker
        execution_simulator: Order execution
        risk_manager: Risk management
        event_bus: Central event system

    Example:
        >>> engine = BacktestEngine(
        ...     data_handler=data,
        ...     strategy=strategy,
        ...     portfolio=portfolio,
        ...     execution_simulator=execution,
        ...     risk_manager=risk,
        ...     event_bus=bus,
        ...     config=BacktestConfig(initial_capital=100000)
        ... )
        >>>
        >>> results = engine.run()
        >>> equity_curve = results['equity_curve']
    """



    def __init__(

        self,

        data_handler: DataHandler,

        strategy: Strategy,

        portfolio: Portfolio,

        execution_simulator: ExecutionSimulator,

        risk_manager: RiskManager,

        event_bus: EventBus,

        config: Optional[BacktestConfig] = None

    ):

        """
        Initialize the backtest engine.

        Args:
            data_handler: Data source for market data
            strategy: Trading strategy for signal generation
            portfolio: Portfolio for P&L tracking
            execution_simulator: Execution for order fills
            risk_manager: Risk manager for pre-trade checks
            event_bus: Event bus for component communication
            config: Backtest configuration
        """

        self.data_handler = data_handler

        self.strategy = strategy

        self.portfolio = portfolio

        self.execution_simulator = execution_simulator

        self.risk_manager = risk_manager

        self.event_bus = event_bus

        self.config = config or BacktestConfig()





        self._position_sizer = PositionSizer(

            target_volatility=self.config.target_volatility,

            max_position_pct=self.config.max_position_pct

        )





        self._current_positions: Dict[str, int] = {}

        self._target_positions: Dict[str, float] = {}

        self._signals: Dict[str, SignalEvent] = {}





        self._equity_history: List[Dict] = []

        self._trade_history: List[Dict] = []

        self._signal_history: List[Dict] = []





        self._bars_processed = 0

        self._events_processed = 0

        self._start_time: Optional[datetime] = None

        self._end_time: Optional[datetime] = None





        self._subscribe()



    def _subscribe(self) -> None:

        """Subscribe to signal events for order generation."""

        self.event_bus.subscribe(EventType.SIGNAL, self._on_signal)

        self.event_bus.subscribe(EventType.FILL, self._on_fill)



    def _on_signal(self, event: Event) -> None:

        """Process trading signals and generate orders."""

        if not isinstance(event, SignalEvent):

            return



        signal = event

        self._signals[signal.symbol] = signal





        self._signal_history.append({

            'timestamp': signal.timestamp,

            'symbol': signal.symbol,

            'signal': signal.signal,

            'confidence': signal.confidence,

            'strategy': signal.strategy_name,

        })





        equity = self.portfolio.total_equity

        if equity <= 0:

            return





        method = self.config.position_sizing_method

        target_value = 0.0



        if method == 'volatility_target':









             meta = getattr(signal, 'metadata', {}) or {}

             vol = meta.get('volatility', 0.0)



             if vol == 0.0:





                 try:

                     hist = self.data_handler.get_latest_bars(signal.symbol, n=60, as_df=True)

                     if len(hist) > 10:

                         rets = hist['close'].pct_change().dropna()

                         vol = rets.std() * np.sqrt(252) if len(rets) > 1 else 0.0

                 except Exception:

                     vol = 0.0





             if vol == 0.0:

                 vol = 0.20



             target_value = self._position_sizer.volatility_target_size(

                 signal=signal.signal,

                 asset_volatility=vol,

                 portfolio_value=equity

             )



        elif method == 'kelly':



            target_value = self._position_sizer.kelly_size(

                capital=equity,

                win_rate=0.55,

                win_loss_ratio=1.5

            )

        else:





            target_value = self._position_sizer.fixed_fractional_size(

                capital=equity,

                fraction=0.20,

                signal=signal.signal

            )



        self._target_positions[signal.symbol] = target_value





        current_qty = self.portfolio.get_position_quantity(signal.symbol)

        current_price = self.portfolio.get_current_price(signal.symbol)



        if current_price is None or current_price <= 0:

            return





        target_qty = int(target_value / current_price)





        order_qty = target_qty - current_qty





        if current_qty != 0:

            position_change_pct = abs(order_qty) / abs(current_qty)

            if position_change_pct < self.config.rebalance_threshold:

                return





        if order_qty == 0:

            return





        order = OrderEvent(

            timestamp=signal.timestamp,

            event_type=EventType.ORDER,

            symbol=signal.symbol,

            quantity=order_qty,

            order_type=OrderType.MARKET,

            strategy_name=signal.strategy_name

        )





        if self.config.enable_risk_management:

            portfolio_value = self.portfolio.total_equity

            check_result = self.risk_manager.check_order(

                order=order,

                portfolio_value=portfolio_value

            )



            if not check_result.approved:



                return





        self.event_bus.publish(order)



    def _on_fill(self, event: Event) -> None:

        """Process fill events for trade history."""

        if not isinstance(event, FillEvent):

            return



        fill = event

        self._trade_history.append({

            'timestamp': fill.timestamp,

            'symbol': fill.symbol,

            'quantity': fill.quantity,

            'fill_price': fill.fill_price,

            'commission': fill.commission,

            'slippage': fill.slippage,

            'total_cost': fill.total_cost,

        })



    def run(self) -> Dict[str, Any]:

        """
        Run the backtest simulation.

        Executes the main event loop:
        1. While data available, emit market data
        2. Process all events (signals -> orders -> fills)
        3. Record portfolio state
        4. Continue until data exhausted

        Returns:
            Dictionary with backtest results including:
            - equity_curve: Time series of portfolio value
            - total_return: Total P&L
            - total_return_pct: Return percentage
            - sharpe_ratio: Risk-adjusted return metric
            - max_drawdown: Maximum peak-to-trough decline
            - num_trades: Total number of trades
            - trade_history: DataFrame of all trades
            - stats: Comprehensive statistics dictionary
        """

        self._start_time = datetime.now()



        print(f"Starting backtest with {self.config.initial_capital:,.2f} initial capital")

        print(f"Symbols: {self.data_handler.symbols}")

        print(f"Strategy: {self.strategy.name}")

        print("-" * 50)





        bar_count = 0

        last_record_date = None



        while self.data_handler.has_more_data():



            events = self.data_handler.update_bars()



            if events is None:

                break



            bar_count += len(events)

            self._bars_processed += len(events)





            events_processed = self.event_bus.run()

            self._events_processed += events_processed





            if events:

                current_time = events[0].timestamp

                should_record = self._should_record(current_time, last_record_date)



                if should_record:

                    self._record_state(current_time)

                    last_record_date = current_time





            if self.risk_manager.is_trading_halted:

                print(f"Trading halted at {self.data_handler.current_time}")

                break





        if self.portfolio.total_equity > 0:

            final_time = self.data_handler.current_time or datetime.now()

            self._record_state(final_time)



        self._end_time = datetime.now()



        print("-" * 50)

        print(f"Backtest complete: {bar_count} bars processed")

        print(f"Events processed: {self._events_processed}")



        return self._generate_results()



    def _should_record(

        self,

        current_time: datetime,

        last_record: Optional[datetime]

    ) -> bool:

        """Determine if we should record state at this time."""

        if self.config.record_interval == 'all':

            return True



        if last_record is None:

            return True



        if self.config.record_interval == 'daily':

            return current_time.date() != last_record.date()



        if self.config.record_interval == 'weekly':

            current_week = current_time.isocalendar()[1]

            last_week = last_record.isocalendar()[1]

            return current_week != last_week



        if self.config.record_interval == 'monthly':

            return (current_time.year, current_time.month) !=
                   (last_record.year, last_record.month)



        return True



    def _record_state(self, timestamp: datetime) -> None:

        """Record current portfolio state."""

        equity = self.portfolio.total_equity



        self._equity_history.append({

            'timestamp': timestamp,

            'equity': equity,

            'cash': self.portfolio.cash,

            'positions_value': self.portfolio.positions_market_value,

            'realized_pnl': self.portfolio.realized_pnl,

            'unrealized_pnl': self.portfolio.unrealized_pnl,

            'num_positions': self.portfolio.num_positions,

            'leverage': self.portfolio.leverage,

            'gross_exposure': self.portfolio.gross_exposure,

            'net_exposure': self.portfolio.net_exposure,

        })



    def _generate_results(self) -> Dict[str, Any]:

        """Generate comprehensive backtest results."""



        equity_df = pd.DataFrame(self._equity_history)

        if not equity_df.empty:

            equity_df.set_index('timestamp', inplace=True)



        trades_df = pd.DataFrame(self._trade_history)

        signals_df = pd.DataFrame(self._signal_history)





        if len(equity_df) > 1:

            equity_series = equity_df['equity']

            returns = equity_series.pct_change().dropna()

        else:

            returns = pd.Series(dtype=float)





        metrics = self._calculate_metrics(equity_df, returns)





        risk_report = self.risk_manager.get_risk_report()



        return {

            'equity_curve': equity_df,

            'returns': returns,

            'trades': trades_df,

            'signals': signals_df,

            'total_return': metrics['total_return'],

            'total_return_pct': metrics['total_return_pct'],

            'sharpe_ratio': metrics['sharpe_ratio'],

            'sortino_ratio': metrics['sortino_ratio'],

            'max_drawdown': metrics['max_drawdown'],

            'max_drawdown_pct': metrics['max_drawdown_pct'],

            'volatility': metrics['volatility'],

            'num_trades': len(trades_df),

            'num_signals': len(signals_df),

            'bars_processed': self._bars_processed,

            'events_processed': self._events_processed,

            'duration': self._end_time - self._start_time if self._end_time else None,

            'portfolio_stats': self.portfolio.get_stats(),

            'risk_report': risk_report,

            'execution_stats': self.execution_simulator.get_stats(),

            'metrics': metrics,

        }



    def _calculate_metrics(

        self,

        equity_df: pd.DataFrame,

        returns: pd.Series

    ) -> Dict[str, float]:

        """Calculate performance metrics."""

        if equity_df.empty or len(equity_df) < 2:

            return {

                'total_return': 0.0,

                'total_return_pct': 0.0,

                'sharpe_ratio': 0.0,

                'sortino_ratio': 0.0,

                'max_drawdown': 0.0,

                'max_drawdown_pct': 0.0,

                'volatility': 0.0,

                'calmar_ratio': 0.0,

            }



        equity = equity_df['equity']

        initial = self.config.initial_capital

        final = equity.iloc[-1]



        total_return = final - initial

        total_return_pct = total_return / initial if initial > 0 else 0





        if len(returns) > 1 and returns.std() > 0:

            excess_returns = returns - (0.02 / 252)

            sharpe = np.sqrt(252) * excess_returns.mean() / returns.std()

        else:

            sharpe = 0.0





        if len(returns) > 1:

            downside = returns[returns < 0]

            if len(downside) > 0 and downside.std() > 0:

                sortino = np.sqrt(252) * returns.mean() / downside.std()

            else:

                sortino = 0.0

        else:

            sortino = 0.0





        running_max = equity.cummax()

        drawdown = (equity - running_max) / running_max

        max_drawdown = drawdown.min()

        max_drawdown_pct = abs(max_drawdown)





        volatility = returns.std() * np.sqrt(252) if len(returns) > 1 else 0.0





        calmar = total_return_pct / max_drawdown_pct if max_drawdown_pct > 0 else 0.0





        trades = self._trade_history

        if trades:



            long_trades = [t for t in trades if t['quantity'] > 0]

            short_trades = [t for t in trades if t['quantity'] < 0]

        else:

            long_trades = []

            short_trades = []



        return {

            'total_return': total_return,

            'total_return_pct': total_return_pct,

            'sharpe_ratio': sharpe,

            'sortino_ratio': sortino,

            'max_drawdown': max_drawdown,

            'max_drawdown_pct': max_drawdown_pct,

            'volatility': volatility,

            'calmar_ratio': calmar,

            'cagr': (final / initial) ** (252 / len(equity)) - 1 if len(equity) > 1 else 0.0,

        }



    def reset(self) -> None:

        """Reset the backtest engine for a new run."""

        self._current_positions.clear()

        self._target_positions.clear()

        self._signals.clear()



        self._equity_history.clear()

        self._trade_history.clear()

        self._signal_history.clear()



        self._bars_processed = 0

        self._events_processed = 0

        self._start_time = None

        self._end_time = None





        self.data_handler.reset()

        self.portfolio.reset()

        self.risk_manager.reset()

        self.execution_simulator.reset()

        self.strategy.reset()



    def save_results(self, filepath: str) -> None:

        """
        Save backtest results to JSON file.

        Args:
            filepath: Path to save results
        """

        results = self._generate_results()





        serializable = {}

        for key, value in results.items():

            if isinstance(value, pd.DataFrame):

                serializable[key] = value.to_dict('records')

            elif isinstance(value, pd.Series):

                serializable[key] = value.to_dict()

            elif isinstance(value, (np.int64, np.float64)):

                serializable[key] = float(value)

            elif isinstance(value, datetime):

                serializable[key] = value.isoformat()

            elif isinstance(value, (dict, list, str, int, float, bool, type(None))):

                serializable[key] = value

            else:

                serializable[key] = str(value)



        with open(filepath, 'w') as f:

            json.dump(serializable, f, indent=2, default=str)



        print(f"Results saved to {filepath}")





__all__ = ['BacktestEngine', 'BacktestConfig']
