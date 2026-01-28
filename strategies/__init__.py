"""
Trading Strategies Module
10+ production-ready quant strategies
"""



from .base import Strategy

from .momentum import MomentumStrategy, RSIStrategy, MACDStrategy

from .mean_reversion import MeanReversionStrategy, BollingerBandsStrategy

from .trend_following import TrendFollowingStrategy, ADXStrategy

from .stat_arb import StatArbStrategy, PairsTradingStrategy

from .breakout import BreakoutStrategy, DonchianStrategy

from .vwap import VWAPStrategy

from .ml import MLStrategy



__all__ = [

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

]
