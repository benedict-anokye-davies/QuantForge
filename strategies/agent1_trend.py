"""
Agent 1 Trend Strategy
Implements Time Series Momentum (TSMOM) logic.
"""



import numpy as np

import pandas as pd

from typing import Optional, Dict, Any

from .base import Strategy, StrategyConfig

from ..core.events import MarketEvent, SignalEvent



class Agent1TrendStrategy(Strategy):

    """
    Time Series Momentum (TSMOM) Strategy.

    Logic:
    1. Calculate return over lookback period (default 252 days / 12 months).
    2. If return > 0, Go Long.
    3. If return < 0, Go Short (or Flat).

    We use volatility scaling to target a specific annualized volatility (optional).
    For this implementation, we'll stick to simple sign-based allocation first.
    """



    def __init__(self, config: StrategyConfig, lookback: int = 252, rebalance_freq: str = 'M'):

        super().__init__(config)

        self.lookback = lookback

        self.rebalance_freq = rebalance_freq

        self.last_rebalance = None



    def on_market_data(self, event: MarketEvent) -> Optional[SignalEvent]:

        """
        Process market data.
        """



        self.update_data(event)





        history = self.get_data(event.symbol, lookback=self.lookback + 10)

        if len(history) < self.lookback:

            return None



















        current_price = event.close

        past_price = history.iloc[-self.lookback]['close']



        momentum = (current_price / past_price) - 1.0







        current_pos = self.get_position(event.symbol)



        signal_type = None

        strength = 1.0



        if momentum > 0:

            if current_pos <= 0:

                signal_type = 'LONG'

        elif momentum < 0:

            if current_pos >= 0:

                signal_type = 'SHORT'



        if signal_type:

            return self.generate_signal(

                symbol=event.symbol,

                signal_type=signal_type,

                price=event.close,

                strength=strength,

                metadata={'momentum': momentum}

            )



        return None
