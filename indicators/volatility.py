"""
Volatility Indicators - ATR, Bollinger Bands, Keltner Channels
"""



import numpy as np

import pandas as pd

from typing import Tuple





class ATR:

    """
    Average True Range
    Measures market volatility
    """



    def __init__(self, period: int = 14):

        self.period = period



    def calculate(

        self,

        high: pd.Series,

        low: pd.Series,

        close: pd.Series

    ) -> pd.Series:

        """Calculate ATR"""



        tr1 = high - low

        tr2 = abs(high - close.shift(1))

        tr3 = abs(low - close.shift(1))



        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)





        atr = tr.ewm(alpha=1/self.period, min_periods=self.period).mean()



        return atr



    def normalized_atr(

        self,

        high: pd.Series,

        low: pd.Series,

        close: pd.Series

    ) -> pd.Series:

        """ATR as percentage of price"""

        atr = self.calculate(high, low, close)

        return (atr / close) * 100



    def volatility_regime(

        self,

        high: pd.Series,

        low: pd.Series,

        close: pd.Series,

        lookback: int = 50

    ) -> pd.Series:

        """Classify volatility regime: low, normal, high"""

        atr = self.normalized_atr(high, low, close)





        atr_rank = atr.rolling(window=lookback).apply(

            lambda x: pd.Series(x).rank(pct=True).iloc[-1]

        )



        regime = pd.Series('normal', index=close.index)

        regime[atr_rank < 0.2] = 'low'

        regime[atr_rank > 0.8] = 'high'



        return regime



    def stop_loss_levels(

        self,

        high: pd.Series,

        low: pd.Series,

        close: pd.Series,

        multiplier: float = 2.0,

        direction: str = 'long'

    ) -> pd.Series:

        """Calculate ATR-based stop loss levels"""

        atr = self.calculate(high, low, close)



        if direction == 'long':

            stops = close - (atr * multiplier)

        else:

            stops = close + (atr * multiplier)



        return stops



    def position_sizing_multiplier(

        self,

        high: pd.Series,

        low: pd.Series,

        close: pd.Series,

        target_volatility: float = 0.02

    ) -> pd.Series:

        """Calculate position sizing multiplier based on ATR"""

        atr = self.normalized_atr(high, low, close) / 100





        multiplier = target_volatility / atr

        multiplier = multiplier.clip(0.1, 3.0)



        return multiplier





class BollingerBands:

    """
    Bollinger Bands
    Volatility bands placed above and below a moving average
    """



    def __init__(self, period: int = 20, std_dev: float = 2.0):

        self.period = period

        self.std_dev = std_dev



    def calculate(self, prices: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:

        """Calculate middle, upper, and lower bands"""

        middle = prices.rolling(window=self.period).mean()

        std = prices.rolling(window=self.period).std()



        upper = middle + (std * self.std_dev)

        lower = middle - (std * self.std_dev)



        return upper, middle, lower



    def bandwidth(self, prices: pd.Series) -> pd.Series:

        """Bollinger Bandwidth - measure of volatility"""

        upper, middle, lower = self.calculate(prices)

        bandwidth = (upper - lower) / middle

        return bandwidth



    def percent_b(self, prices: pd.Series) -> pd.Series:

        """%B indicator - position within bands"""

        upper, middle, lower = self.calculate(prices)

        percent_b = (prices - lower) / (upper - lower)

        return percent_b



    def squeeze(self, prices: pd.Series, lookback: int = 125) -> pd.Series:

        """Detect Bollinger Squeeze (low volatility)"""

        bandwidth = self.bandwidth(prices)

        lowest_bandwidth = bandwidth.rolling(window=lookback).min()



        squeeze = bandwidth <= (lowest_bandwidth * 1.05)

        return squeeze



    def signals(self, prices: pd.Series) -> pd.Series:

        """Generate signals based on band touches"""

        upper, middle, lower = self.calculate(prices)

        percent_b = self.percent_b(prices)



        signals = pd.Series(0, index=prices.index)

        signals[percent_b < 0.05] = 1

        signals[percent_b > 0.95] = -1



        return signals



    def walk(self, prices: pd.Series) -> pd.Series:

        """
        Bollinger Bands Walk - walking the bands indicates strong trend
        Returns: 'upper', 'lower', 'middle', or 'none'
        """

        upper, middle, lower = self.calculate(prices)



        walk = pd.Series('none', index=prices.index)

        walk[(prices > upper.shift(1)) & (prices > upper.shift(2))] = 'upper'

        walk[(prices < lower.shift(1)) & (prices < lower.shift(2))] = 'lower'



        return walk





class KeltnerChannels:

    """
    Keltner Channels
    Volatility-based envelopes using ATR
    """



    def __init__(self, ema_period: int = 20, atr_period: int = 10, multiplier: float = 2.0):

        self.ema_period = ema_period

        self.atr_period = atr_period

        self.multiplier = multiplier



    def calculate(

        self,

        high: pd.Series,

        low: pd.Series,

        close: pd.Series

    ) -> Tuple[pd.Series, pd.Series, pd.Series]:

        """Calculate upper, middle, and lower channels"""

        middle = close.ewm(span=self.ema_period, adjust=False).mean()



        atr = ATR(period=self.atr_period)

        atr_values = atr.calculate(high, low, close)



        upper = middle + (atr_values * self.multiplier)

        lower = middle - (atr_values * self.multiplier)



        return upper, middle, lower



    def signals(

        self,

        high: pd.Series,

        low: pd.Series,

        close: pd.Series

    ) -> pd.Series:

        """Generate signals"""

        upper, middle, lower = self.calculate(high, low, close)



        signals = pd.Series(0, index=close.index)

        signals[close > upper] = 1

        signals[close < lower] = -1



        return signals





class DonchianChannels:

    """
    Donchian Channels
    Price channel based on highest high and lowest low
    """



    def __init__(self, period: int = 20):

        self.period = period



    def calculate(

        self,

        high: pd.Series,

        low: pd.Series

    ) -> Tuple[pd.Series, pd.Series, pd.Series]:

        """Calculate upper, middle, and lower channels"""

        upper = high.rolling(window=self.period).max()

        lower = low.rolling(window=self.period).min()

        middle = (upper + lower) / 2



        return upper, middle, lower



    def breakout_signals(

        self,

        high: pd.Series,

        low: pd.Series,

        close: pd.Series

    ) -> pd.Series:

        """Turtle trading style breakout signals"""

        upper, middle, lower = self.calculate(high, low)



        signals = pd.Series(0, index=close.index)

        signals[close > upper.shift(1)] = 1

        signals[close < lower.shift(1)] = -1



        return signals



    def width(self, high: pd.Series, low: pd.Series) -> pd.Series:

        """Channel width as volatility measure"""

        upper, middle, lower = self.calculate(high, low)

        width = (upper - lower) / middle

        return width





class VolatilityRegime:

    """
    Volatility regime detection and classification
    """



    def __init__(self, short_period: int = 10, long_period: int = 30):

        self.short_period = short_period

        self.long_period = long_period



    def classify(

        self,

        high: pd.Series,

        low: pd.Series,

        close: pd.Series

    ) -> pd.Series:

        """
        Classify volatility regime:
        - contracting: volatility decreasing
        - expanding: volatility increasing
        - stable: volatility stable
        """

        atr = ATR(period=self.short_period)

        short_atr = atr.calculate(high, low, close)



        atr_long = ATR(period=self.long_period)

        long_atr = atr_long.calculate(high, low, close)



        ratio = short_atr / long_atr



        regime = pd.Series('stable', index=close.index)

        regime[ratio < 0.8] = 'contracting'

        regime[ratio > 1.2] = 'expanding'



        return regime



    def volatility_percentile(

        self,

        high: pd.Series,

        low: pd.Series,

        close: pd.Series,

        lookback: int = 100

    ) -> pd.Series:

        """Current volatility as percentile of historical range"""

        atr = ATR(period=14)

        current_atr = atr.normalized_atr(high, low, close)



        percentile = current_atr.rolling(window=lookback).apply(

            lambda x: pd.Series(x).rank(pct=True).iloc[-1] if len(x) > 0 else 0.5

        )



        return percentile
