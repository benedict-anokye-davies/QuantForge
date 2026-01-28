"""
Backtest Engine - Event-driven backtesting system
The heart of the quant framework
"""



from typing import List, Dict, Optional, Callable, Any, Type

from datetime import datetime

from collections import deque

import pandas as pd

import numpy as np

from tqdm import tqdm



from .events import (

    Event, MarketEvent, SignalEvent, OrderEvent,

    FillEvent, RiskEvent, EventType

)

from .portfolio import Portfolio

from .execution import ExecutionHandler, SimulatedExecution

from .performance import PerformanceMetrics

from ..strategies.base import Strategy

from ..data.feeds import DataFeed





class BacktestEngine:

    """
    Event-driven backtesting engine

    Flow:
    1. Market data arrives -> MarketEvent
    2. Strategy processes -> SignalEvent
    3. Portfolio/Risk processes -> OrderEvent
    4. Execution processes -> FillEvent
    5. Portfolio updates -> PortfolioUpdateEvent
    """



    def __init__(

        self,

        initial_capital: float = 100000.0,

        start_date: Optional[datetime] = None,

        end_date: Optional[datetime] = None,

        execution_handler: Optional[ExecutionHandler] = None,

        portfolio: Optional[Portfolio] = None,

        risk_manager: Optional[Any] = None,

        verbose: bool = True,

    ):

        self.initial_capital = initial_capital

        self.start_date = start_date

        self.end_date = end_date

        self.verbose = verbose





        self.execution_handler = execution_handler or SimulatedExecution()

        self.portfolio = portfolio or Portfolio(initial_capital=initial_capital)

        self.risk_manager = risk_manager





        self.events: deque = deque()





        self.strategies: List[Strategy] = []





        self.data_feed: Optional[DataFeed] = None

        self.symbols: List[str] = []





        self.current_idx: int = 0

        self.is_running: bool = False

        self.current_prices: Dict[str, float] = {}





        self.signals: List[SignalEvent] = []

        self.orders: List[OrderEvent] = []

        self.fills: List[FillEvent] = []

        self.risk_events: List[RiskEvent] = []





        self.on_market_callbacks: List[Callable] = []

        self.on_fill_callbacks: List[Callable] = []



    def add_strategy(self, strategy: Strategy):

        """Add a strategy to the engine"""

        self.strategies.append(strategy)

        strategy.set_engine(self)



    def add_data(self, data_feed: DataFeed, symbols: List[str]):

        """Add data source and symbols"""

        self.data_feed = data_feed

        self.symbols = symbols



    def set_execution_handler(self, handler: ExecutionHandler):

        """Set custom execution handler"""

        self.execution_handler = handler



    def set_portfolio(self, portfolio: Portfolio):

        """Set custom portfolio manager"""

        self.portfolio = portfolio



    def register_callback(self, event_type: str, callback: Callable):

        """Register callback for specific events"""

        if event_type == "market":

            self.on_market_callbacks.append(callback)

        elif event_type == "fill":

            self.on_fill_callbacks.append(callback)



    def _process_market_event(self, event: MarketEvent):

        """Process market data event"""



        self.current_prices[event.symbol] = event.close





        self.portfolio.update_market_data(

            event.symbol, event.close, event.timestamp

        )





        for strategy in self.strategies:

            if strategy.should_process(event.symbol):

                signal = strategy.on_market_data(event)

                if signal:

                    self.events.append(signal)

                    self.signals.append(signal)





        for callback in self.on_market_callbacks:

            callback(event)



    def set_risk_manager(self, risk_manager):

        """Set risk manager for pre-trade checks"""

        self.risk_manager = risk_manager



    def _process_signal_event(self, event: SignalEvent):

        """Process trading signal"""



        current_price = self.current_prices.get(event.symbol, event.price)





        if self.risk_manager is not None:

            risk_events = self.risk_manager.check(

                event, self.portfolio, self.current_prices

            )

            for risk_event in risk_events:

                self.events.append(risk_event)

                self.risk_events.append(risk_event)



                if hasattr(risk_event, 'severity') and risk_event.severity == 'KILL_SWITCH':

                    return





        order = self.portfolio.on_signal(event, current_price)



        if order:

            self.events.append(order)

            self.orders.append(order)



    def _process_order_event(self, event: OrderEvent):

        """Process order"""





        market_event = self._get_latest_market_data(event.symbol)



        if market_event:

            fill = self.execution_handler.execute_order(event, market_event)

            if fill:



                fill.commission = self.portfolio.calculate_commission(

                    fill.quantity, fill.fill_price

                )

                self.events.append(fill)

                self.fills.append(fill)



    def _process_fill_event(self, event: FillEvent):

        """Process fill"""



        self.portfolio.on_fill(event)





        for strategy in self.strategies:

            strategy.on_fill(event)





        for callback in self.on_fill_callbacks:

            callback(event)



    def _get_latest_market_data(self, symbol: str) -> Optional[MarketEvent]:

        """Get latest market data for symbol"""

        if self.data_feed:

            return self.data_feed.get_latest(symbol)

        return None



    def _process_event(self, event: Event):

        """Route event to appropriate handler"""

        if event.type == EventType.MARKET:

            self._process_market_event(event)

        elif event.type == EventType.SIGNAL:

            self._process_signal_event(event)

        elif event.type == EventType.ORDER:

            self._process_order_event(event)

        elif event.type == EventType.FILL:

            self._process_fill_event(event)

        elif event.type == EventType.RISK:

            self.risk_events.append(event)



    def run(self) -> PerformanceMetrics:

        """
        Run the backtest
        """

        if not self.data_feed:

            raise ValueError("No data feed provided")



        if not self.strategies:

            raise ValueError("No strategies added")



        self.is_running = True





        data_iterator = self.data_feed.get_data_iterator(

            self.symbols, self.start_date, self.end_date

        )





        total_bars = self.data_feed.get_bar_count(

            self.symbols, self.start_date, self.end_date

        )





        iterator = tqdm(data_iterator, total=total_bars, desc="Backtesting") if self.verbose else data_iterator



        for market_event in iterator:



            self.events.append(market_event)





            while self.events:

                event = self.events.popleft()

                self._process_event(event)



            self.current_idx += 1



        self.is_running = False





        metrics = PerformanceMetrics(

            portfolio=self.portfolio,

            signals=self.signals,

            orders=self.orders,

            fills=self.fills,

            risk_events=self.risk_events

        )



        return metrics



    def run_walk_forward(

        self,

        train_size: int,

        test_size: int,

        step_size: Optional[int] = None

    ) -> List[PerformanceMetrics]:

        """
        Run walk-forward analysis

        Args:
            train_size: Number of bars for training
            test_size: Number of bars for testing
            step_size: Step size (default = test_size)
        """

        if step_size is None:

            step_size = test_size



        results = []





        all_data = list(self.data_feed.get_data_iterator(self.symbols))

        total_bars = len(all_data)



        window_start = 0



        while window_start + train_size + test_size <= total_bars:

            train_end = window_start + train_size

            test_end = train_end + test_size





            train_data = all_data[window_start:train_end]





            for strategy in self.strategies:

                if hasattr(strategy, 'optimize'):

                    strategy.optimize(train_data)





            test_data = all_data[train_end:test_end]







            self.portfolio = Portfolio(initial_capital=self.initial_capital)

            self.events.clear()

            self.signals.clear()

            self.orders.clear()

            self.fills.clear()

            self.risk_events.clear()



            for market_event in test_data:

                self.events.append(market_event)

                while self.events:

                    event = self.events.popleft()

                    self._process_event(event)





            metrics = PerformanceMetrics(

                portfolio=self.portfolio,

                signals=self.signals,

                orders=self.orders,

                fills=self.fills,

                risk_events=self.risk_events

            )

            results.append(metrics)



            window_start += step_size



        return results



    def get_results_summary(self) -> Dict[str, Any]:

        """Get summary of backtest results"""

        return {

            'initial_capital': self.initial_capital,

            'final_equity': self.portfolio.equity,

            'total_return': (self.portfolio.equity - self.initial_capital) / self.initial_capital,

            'total_signals': len(self.signals),

            'total_orders': len(self.orders),

            'total_fills': len(self.fills),

            'total_risk_events': len(self.risk_events),

            'strategies': [s.name for s in self.strategies],

            'symbols': self.symbols,

        }
