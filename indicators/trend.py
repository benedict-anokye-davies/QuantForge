"""
Trend Indicators - EMA, SMA, ADX, Parabolic SAR, Ichimoku
"""



import numpy as np

import pandas as pd

from typing import Tuple





class EMA:

    """Exponential Moving Average"""



    def __init__(self, period: int = 20):

        self.period = period



    def calculate(self, prices: pd.Series) -> pd.Series:

        return prices.ewm(span=self.period, adjust=False).mean()





class SMA:

    """Simple Moving Average"""



    def __init__(self, period: int = 20):

        self.period = period



    def calculate(self, prices: pd.Series) -> pd.Series:

        return prices.rolling(window=self.period).mean()





class ADX:

    """
    Average Directional Index
    Measures trend strength
    """



    def __init__(self, period: int = 14):

        self.period = period

        self.plus_di = None

        self.minus_di = None



    def calculate(

        self,

        high: pd.Series,

        low: pd.Series,

        close: pd.Series

    ) -> pd.Series:

        """Calculate ADX, +DI, and -DI"""



        tr1 = high - low

        tr2 = abs(high - close.shift(1))

        tr3 = abs(low - close.shift(1))

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)





        plus_dm = high.diff()

        minus_dm = -low.diff()



        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)

        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)





        atr = tr.ewm(alpha=1/self.period, min_periods=self.period).mean()

        plus_di_val = 100 * plus_dm.ewm(alpha=1/self.period, min_periods=self.period).mean() / atr

        minus_di_val = 100 * minus_dm.ewm(alpha=1/self.period, min_periods=self.period).mean() / atr





        dx = 100 * abs(plus_di_val - minus_di_val) / (plus_di_val + minus_di_val)

        adx = dx.ewm(alpha=1/self.period, min_periods=self.period).mean()



        self.plus_di = plus_di_val

        self.minus_di = minus_di_val



        return adx



    def trend_strength(self, adx_values: pd.Series) -> pd.Series:

        """Classify trend strength"""

        strength = pd.Series('weak', index=adx_values.index)

        strength[adx_values > 25] = 'strong'

        strength[adx_values > 50] = 'very_strong'

        return strength





class ParabolicSAR:

    """
    Parabolic Stop and Reverse
    Dynamic trailing stop
    """



    def __init__(

        self,

        af_start: float = 0.02,

        af_increment: float = 0.02,

        af_max: float = 0.2

    ):

        self.af_start = af_start

        self.af_increment = af_increment

        self.af_max = af_max



    def calculate(

        self,

        high: pd.Series,

        low: pd.Series

    ) -> pd.Series:

        """Calculate Parabolic SAR"""

        n = len(high)

        psar = pd.Series(index=high.index, dtype=float)





        psar.iloc[0] = low.iloc[0]

        uptrend = True

        ep = high.iloc[0]

        af = self.af_start



        for i in range(1, n):



            psar.iloc[i] = psar.iloc[i-1] + af * (ep - psar.iloc[i-1])





            if uptrend:

                if low.iloc[i] < psar.iloc[i]:



                    uptrend = False

                    psar.iloc[i] = ep

                    ep = low.iloc[i]

                    af = self.af_start

                else:



                    if high.iloc[i] > ep:

                        ep = high.iloc[i]

                        af = min(af + self.af_increment, self.af_max)

            else:

                if high.iloc[i] > psar.iloc[i]:



                    uptrend = True

                    psar.iloc[i] = ep

                    ep = high.iloc[i]

                    af = self.af_start

                else:



                    if low.iloc[i] < ep:

                        ep = low.iloc[i]

                        af = min(af + self.af_increment, self.af_max)



        return psar





class Ichimoku:

    """
    Ichimoku Cloud
    Comprehensive trend indicator
    """



    def __init__(

        self,

        tenkan_period: int = 9,

        kijun_period: int = 26,

        senkou_b_period: int = 52,

        displacement: int = 26

    ):

        self.tenkan_period = tenkan_period

        self.kijun_period = kijun_period

        self.senkou_b_period = senkou_b_period

        self.displacement = displacement



    def calculate(

        self,

        high: pd.Series,

        low: pd.Series,

        close: pd.Series

    ) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.Series]:

        """
        Calculate Ichimoku components:
        - Tenkan-sen (Conversion line)
        - Kijun-sen (Base line)
        - Senkou Span A (Leading span A)
        - Senkou Span B (Leading span B)
        - Chikou Span (Lagging span)
        """



        tenkan = (high.rolling(window=self.tenkan_period).max() +

                  low.rolling(window=self.tenkan_period).min()) / 2





        kijun = (high.rolling(window=self.kijun_period).max() +

                 low.rolling(window=self.kijun_period).min()) / 2





        senkou_a = ((tenkan + kijun) / 2).shift(-self.displacement)





        senkou_b = ((high.rolling(window=self.senkou_b_period).max() +

                     low.rolling(window=self.senkou_b_period).min()) / 2).shift(-self.displacement)





        chikou = close.shift(self.displacement)



        return tenkan, kijun, senkou_a, senkou_b, chikou



    def cloud_color(

        self,

        senkou_a: pd.Series,

        senkou_b: pd.Series

    ) -> pd.Series:

        """Determine cloud color: 'green' (bullish) or 'red' (bearish)"""

        color = pd.Series('red', index=senkou_a.index)

        color[senkou_a > senkou_b] = 'green'

        return color



    def signals(

        self,

        close: pd.Series,

        tenkan: pd.Series,

        kijun: pd.Series,

        senkou_a: pd.Series,

        senkou_b: pd.Series

    ) -> pd.Series:

        """Generate Ichimoku signals"""

        signals = pd.Series(0, index=close.index)





        above_cloud = (close > senkou_a) & (close > senkou_b)

        below_cloud = (close < senkou_a) & (close < senkou_b)





        tenkan_cross_up = (tenkan > kijun) & (tenkan.shift(1) <= kijun.shift(1))

        tenkan_cross_down = (tenkan < kijun) & (tenkan.shift(1) >= kijun.shift(1))



        signals[above_cloud & tenkan_cross_up] = 1

        signals[below_cloud & tenkan_cross_down] = -1



        return signals
