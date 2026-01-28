"""
Mean Reversion Strategies - Bollinger Bands, Statistical Arbitrage
"""



from typing import Optional, Tuple

import pandas as pd

import numpy as np

from scipy import stats



from .base import Strategy, StrategyConfig

from ..core.events import MarketEvent, SignalEvent

from ..indicators.volatility import BollingerBands, ATR, KeltnerChannels

from ..indicators.statistical import ZScore





class MeanReversionStrategy(Strategy):

    """
    Generic Mean Reversion Strategy
    Uses Z-Score and volatility channels
    """



    def __init__(

        self,

        symbols: list = None,

        zscore_period: int = 20,

        entry_zscore: float = 2.0,

        exit_zscore: float = 0.5,

        use_atr_filter: bool = True

    ):

        config = StrategyConfig(

            name="MeanReversionStrategy",

            symbols=symbols,

        )

        super().__init__(config)



        self.zscore_period = zscore_period

        self.entry_zscore = entry_zscore

        self.exit_zscore = exit_zscore

        self.use_atr_filter = use_atr_filter

        self.atr = ATR(period=14)



    def on_market_data(self, event: MarketEvent) -> Optional[SignalEvent]:

        """Generate mean reversion signals"""

        self.update_data(event)



        data = self.data_history.get(event.symbol)

        if data is None or len(data) < self.zscore_period + 10:

            return None



        close = data['close']

        high = data['high']

        low = data['low']





        mean = close.rolling(window=self.zscore_period).mean()

        std = close.rolling(window=self.zscore_period).std()

        zscore = (close - mean) / std

        current_z = zscore.iloc[-1]





        if self.use_atr_filter:

            atr_values = self.atr.normalized_atr(high, low, close)

            if atr_values.iloc[-1] > 5:

                return None



        position = self.get_position(event.symbol)





        if current_z < -self.entry_zscore:



            if position <= 0:

                confidence = min(abs(current_z) / 4, 1.0)

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='LONG',

                    price=event.close,

                    strength=1.0,

                    confidence=confidence,

                    metadata={'zscore': current_z, 'mean': mean.iloc[-1]}

                )



        elif current_z > self.entry_zscore:



            if position >= 0:

                confidence = min(abs(current_z) / 4, 1.0)

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='SHORT',

                    price=event.close,

                    strength=1.0,

                    confidence=confidence,

                    metadata={'zscore': current_z, 'mean': mean.iloc[-1]}

                )





        if position > 0 and current_z > -self.exit_zscore:

            return self.generate_signal(

                symbol=event.symbol,

                signal_type='EXIT',

                price=event.close,

                strength=1.0,

                metadata={'zscore': current_z, 'reason': 'mean_reversion'}

            )

        elif position < 0 and current_z < self.exit_zscore:

            return self.generate_signal(

                symbol=event.symbol,

                signal_type='EXIT',

                price=event.close,

                strength=1.0,

                metadata={'zscore': current_z, 'reason': 'mean_reversion'}

            )



        return None





class BollingerBandsStrategy(Strategy):

    """
    Bollinger Bands Mean Reversion Strategy
    Classic Bollinger Bands trading
    """



    def __init__(

        self,

        symbols: list = None,

        period: int = 20,

        std_dev: float = 2.0,

        use_squeeze: bool = True,

        use_walk: bool = False

    ):

        config = StrategyConfig(

            name="BollingerBandsStrategy",

            symbols=symbols,

        )

        super().__init__(config)



        self.bb = BollingerBands(period=period, std_dev=std_dev)

        self.use_squeeze = use_squeeze

        self.use_walk = use_walk



    def on_market_data(self, event: MarketEvent) -> Optional[SignalEvent]:

        """Generate Bollinger Bands signals"""

        self.update_data(event)



        data = self.data_history.get(event.symbol)

        if data is None or len(data) < self.bb.period + 5:

            return None



        close = data['close']





        upper, middle, lower = self.bb.calculate(close)

        percent_b = self.bb.percent_b(close)

        current_pb = percent_b.iloc[-1]



        position = self.get_position(event.symbol)





        in_squeeze = False

        if self.use_squeeze:

            squeeze = self.bb.squeeze(close)

            in_squeeze = squeeze.iloc[-1]





        walk = ""

        if self.use_walk:

            walk_status = self.bb.walk(close)

            walk = walk_status.iloc[-1]





        if current_pb < 0.05 and not in_squeeze:



            if position <= 0:

                confidence = 0.6

                if walk == "lower":

                    confidence -= 0.2



                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='LONG',

                    price=event.close,

                    strength=1.0,

                    confidence=max(confidence, 0.3),

                    metadata={

                        'percent_b': current_pb,

                        'squeeze': in_squeeze,

                        'walk': walk

                    }

                )



        elif current_pb > 0.95 and not in_squeeze:



            if position >= 0:

                confidence = 0.6

                if walk == "upper":

                    confidence -= 0.2



                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='SHORT',

                    price=event.close,

                    strength=1.0,

                    confidence=max(confidence, 0.3),

                    metadata={

                        'percent_b': current_pb,

                        'squeeze': in_squeeze,

                        'walk': walk

                    }

                )





        if position > 0 and current_pb > 0.5:

            return self.generate_signal(

                symbol=event.symbol,

                signal_type='EXIT',

                price=event.close,

                strength=1.0,

                metadata={'percent_b': current_pb, 'reason': 'middle_band'}

            )

        elif position < 0 and current_pb < 0.5:

            return self.generate_signal(

                symbol=event.symbol,

                signal_type='EXIT',

                price=event.close,

                strength=1.0,

                metadata={'percent_b': current_pb, 'reason': 'middle_band'}

            )



        return None





class KeltnerStrategy(Strategy):

    """
    Keltner Channels Mean Reversion
    Similar to Bollinger but uses ATR
    """



    def __init__(

        self,

        symbols: list = None,

        ema_period: int = 20,

        atr_period: int = 10,

        multiplier: float = 2.0

    ):

        config = StrategyConfig(

            name="KeltnerStrategy",

            symbols=symbols,

        )

        super().__init__(config)



        self.keltner = KeltnerChannels(

            ema_period=ema_period,

            atr_period=atr_period,

            multiplier=multiplier

        )



    def on_market_data(self, event: MarketEvent) -> Optional[SignalEvent]:

        """Generate Keltner Channel signals"""

        self.update_data(event)



        data = self.data_history.get(event.symbol)

        if data is None or len(data) < 30:

            return None



        close = data['close']

        high = data['high']

        low = data['low']





        upper, middle, lower = self.keltner.calculate(high, low, close)



        position = self.get_position(event.symbol)





        if close.iloc[-1] < lower.iloc[-1]:



            if position <= 0:

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='LONG',

                    price=event.close,

                    strength=1.0,

                    metadata={'position': 'below_lower'}

                )



        elif close.iloc[-1] > upper.iloc[-1]:



            if position >= 0:

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='SHORT',

                    price=event.close,

                    strength=1.0,

                    metadata={'position': 'above_upper'}

                )





        if position > 0 and close.iloc[-1] > middle.iloc[-1]:

            return self.generate_signal(

                symbol=event.symbol,

                signal_type='EXIT',

                price=event.close,

                strength=1.0,

                metadata={'reason': 'middle_line'}

            )

        elif position < 0 and close.iloc[-1] < middle.iloc[-1]:

            return self.generate_signal(

                symbol=event.symbol,

                signal_type='EXIT',

                price=event.close,

                strength=1.0,

                metadata={'reason': 'middle_line'}

            )



        return None





class StatisticalArbStrategy(Strategy):

    """
    Statistical Arbitrage Strategy
    Uses cointegration and mean reversion
    """



    def __init__(

        self,

        symbols: list = None,

        lookback: int = 60,

        entry_threshold: float = 2.0,

        exit_threshold: float = 0.5

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

                    metadata={

                        'zscore': zscore,

                        'spread': current_spread,

                        'hedge_ratio': self.hedge_ratio

                    }

                )



        elif zscore > self.entry_threshold:



            if position >= 0:

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='SHORT',

                    price=event.close,

                    strength=1.0,

                    confidence=min(abs(zscore) / 4, 1.0),

                    metadata={

                        'zscore': zscore,

                        'spread': current_spread,

                        'hedge_ratio': self.hedge_ratio

                    }

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
