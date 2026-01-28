"""
Quant Researcher - Event-Driven Backtesting Engine
Production-grade quantitative trading framework
"""



from .engine import BacktestEngine

from .events import Event, MarketEvent, SignalEvent, OrderEvent, FillEvent

from .portfolio import Portfolio

from .execution import ExecutionHandler, SimulatedExecution

from .performance import PerformanceMetrics



__version__ = "1.0.0"

__all__ = [

    "BacktestEngine",

    "Event",

    "MarketEvent",

    "SignalEvent",

    "OrderEvent",

    "FillEvent",

    "Portfolio",

    "ExecutionHandler",

    "SimulatedExecution",

    "PerformanceMetrics",

]
