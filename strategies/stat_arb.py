"""
Statistical Arbitrage Strategies - Pairs Trading, Cointegration
"""



from typing import Optional, Dict, Tuple

import pandas as pd

import numpy as np

from scipy import stats

from scipy.stats import pearsonr



from .base import Strategy, StrategyConfig

from ..core.events import MarketEvent, SignalEvent





class StatArbStrategy(Strategy):

    """
    Statistical Arbitrage using cointegration
    """



    def __init__(

        self,

        symbols: list = None,

        lookback: int = 60,

        entry_threshold: float = 2.0,

        exit_threshold: float = 0.5,

        min_correlation: float = 0.8

    ):

        config = StrategyConfig(

            name="StatArbStrategy",

            symbols=symbols or [],

        )

        super().__init__(config)



        if len(self.symbols) < 2:

            raise ValueError("StatArbStrategy requires at least 2 symbols")



        self.lookback = lookback

        self.entry_threshold = entry_threshold

        self.exit_threshold = exit_threshold

        self.min_correlation = min_correlation



        self.hedge_ratio = 1.0

        self.spread_mean = 0

        self.spread_std = 1



    def calculate_spread(self) -> Optional[pd.Series]:

        """Calculate spread between two assets"""

        if len(self.symbols) != 2:

            return None



        sym1, sym2 = self.symbols[0], self.symbols[1]



        if sym1 not in self.data_history or sym2 not in self.data_history:

            return None



        data1 = self.data_history[sym1]['close'].iloc[-self.lookback:]

        data2 = self.data_history[sym2]['close'].iloc[-self.lookback:]



        if len(data1) < self.lookback or len(data2) < self.lookback:

            return None





        corr, _ = pearsonr(data1, data2)

        if abs(corr) < self.min_correlation:

            return None





        slope, intercept, _, _, _ = stats.linregress(data2, data1)

        self.hedge_ratio = slope





        spread = data1 - (self.hedge_ratio * data2 + intercept)





        self.spread_mean = spread.mean()

        self.spread_std = spread.std()



        return spread



    def on_market_data(self, event: MarketEvent) -> Optional[SignalEvent]:

        """Generate statistical arbitrage signals"""

        self.update_data(event)





        if event.symbol != self.symbols[0]:

            return None



        spread = self.calculate_spread()

        if spread is None:

            return None



        current_spread = spread.iloc[-1]

        zscore = (current_spread - self.spread_mean) / self.spread_std



        position = self.get_position(event.symbol)





        if zscore < -self.entry_threshold:

            if position <= 0:

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='LONG',

                    price=event.close,

                    strength=1.0,

                    confidence=min(abs(zscore) / 4, 1.0),

                    metadata={'zscore': zscore, 'spread': current_spread}

                )



        elif zscore > self.entry_threshold:

            if position >= 0:

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='SHORT',

                    price=event.close,

                    strength=1.0,

                    confidence=min(abs(zscore) / 4, 1.0),

                    metadata={'zscore': zscore, 'spread': current_spread}

                )





        if position > 0 and zscore > -self.exit_threshold:

            return self.generate_signal(

                symbol=event.symbol,

                signal_type='EXIT',

                price=event.close,

                strength=1.0,

                metadata={'zscore': zscore, 'reason': 'mean_reversion'}

            )

        elif position < 0 and zscore < self.exit_threshold:

            return self.generate_signal(

                symbol=event.symbol,

                signal_type='EXIT',

                price=event.close,

                strength=1.0,

                metadata={'zscore': zscore, 'reason': 'mean_reversion'}

            )



        return None





class PairsTradingStrategy(Strategy):

    """
    Classic Pairs Trading Strategy
    """



    def __init__(

        self,

        symbols: list = None,

        lookback: int = 30,

        entry_zscore: float = 2.0,

        exit_zscore: float = 0.5

    ):

        config = StrategyConfig(

            name="PairsTradingStrategy",

            symbols=symbols or [],

        )

        super().__init__(config)



        if len(self.symbols) != 2:

            raise ValueError("PairsTradingStrategy requires exactly 2 symbols")



        self.lookback = lookback

        self.entry_zscore = entry_zscore

        self.exit_zscore = exit_zscore

        self.ratio_mean = None

        self.ratio_std = None



    def calculate_ratio(self) -> Optional[pd.Series]:

        """Calculate price ratio between pairs"""

        sym1, sym2 = self.symbols[0], self.symbols[1]



        if sym1 not in self.data_history or sym2 not in self.data_history:

            return None



        close1 = self.data_history[sym1]['close'].iloc[-self.lookback:]

        close2 = self.data_history[sym2]['close'].iloc[-self.lookback:]



        if len(close1) < self.lookback or len(close2) < self.lookback:

            return None



        ratio = close1 / close2

        self.ratio_mean = ratio.mean()

        self.ratio_std = ratio.std()



        return ratio



    def on_market_data(self, event: MarketEvent) -> Optional[SignalEvent]:

        """Generate pairs trading signals"""

        self.update_data(event)



        if event.symbol != self.symbols[0]:

            return None



        ratio = self.calculate_ratio()

        if ratio is None or self.ratio_std == 0:

            return None



        current_ratio = ratio.iloc[-1]

        zscore = (current_ratio - self.ratio_mean) / self.ratio_std



        position = self.get_position(event.symbol)





        if zscore < -self.entry_zscore:

            if position <= 0:

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='LONG',

                    price=event.close,

                    strength=1.0,

                    metadata={'zscore': zscore, 'ratio': current_ratio}

                )





        elif zscore > self.entry_zscore:

            if position >= 0:

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='SHORT',

                    price=event.close,

                    strength=1.0,

                    metadata={'zscore': zscore, 'ratio': current_ratio}

                )





        if position > 0 and zscore > -self.exit_zscore:

            return self.generate_signal(

                symbol=event.symbol,

                signal_type='EXIT',

                price=event.close,

                metadata={'zscore': zscore, 'reason': 'ratio_normalized'}

            )

        elif position < 0 and zscore < self.exit_zscore:

            return self.generate_signal(

                symbol=event.symbol,

                signal_type='EXIT',

                price=event.close,

                metadata={'zscore': zscore, 'reason': 'ratio_normalized'}

            )



        return None
