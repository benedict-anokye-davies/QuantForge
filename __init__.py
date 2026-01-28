"""
Quant Researcher - Professional Quantitative Trading Framework

A production-grade backtesting and strategy development framework for quant traders.

Example:
    >>> from quant_researcher import BacktestEngine, MomentumStrategy
    >>> from quant_researcher.data import YahooFinanceFeed
    >>>
    >>> engine = BacktestEngine(initial_capital=100000)
    >>> strategy = MomentumStrategy(symbols=['SPY'])
    >>> engine.add_strategy(strategy)
    >>>
    >>> feed = YahooFinanceFeed(timeframe='1d')
    >>> engine.add_data(feed, ['SPY'])
    >>>
    >>> metrics = engine.run()
    >>> metrics.print_report()
"""



__version__ = "1.0.0"

__author__ = "Quant Developer"





from .core.engine import BacktestEngine

from .core.events import MarketEvent, SignalEvent, OrderEvent, FillEvent

from .core.portfolio import Portfolio

from .core.performance import PerformanceMetrics





from .strategies import (

    Strategy,

    MomentumStrategy,

    RSIStrategy,

    MACDStrategy,

    MeanReversionStrategy,

    BollingerBandsStrategy,

    TrendFollowingStrategy,

    ADXStrategy,

    StatArbStrategy,

    PairsTradingStrategy,

    BreakoutStrategy,

    DonchianStrategy,

    VWAPStrategy,

    MLStrategy,

)





from .data.feeds import DataFeed, YahooFinanceFeed, CCXTFeed, CSVFeed





from .risk.position_sizing import (

    PositionSizer,

    KellyCriterion,

    FixedFractional,

    VolatilityTargeting,

)

from .risk.risk_manager import RiskManager

from .risk.kill_switch import KillSwitch



__all__ = [



    "__version__",





    "BacktestEngine",

    "MarketEvent",

    "SignalEvent",

    "OrderEvent",

    "FillEvent",

    "Portfolio",

    "PerformanceMetrics",





    "Strategy",

    "MomentumStrategy",

    "RSIStrategy",

    "MACDStrategy",

    "MeanReversionStrategy",

    "BollingerBandsStrategy",

    "TrendFollowingStrategy",

    "ADXStrategy",

    "StatArbStrategy",

    "PairsTradingStrategy",

    "BreakoutStrategy",

    "DonchianStrategy",

    "VWAPStrategy",

    "MLStrategy",





    "DataFeed",

    "YahooFinanceFeed",

    "CCXTFeed",

    "CSVFeed",





    "PositionSizer",

    "KellyCriterion",

    "FixedFractional",

    "VolatilityTargeting",

    "RiskManager",

    "KillSwitch",

]
