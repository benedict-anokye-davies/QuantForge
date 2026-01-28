"""
Momentum Indicators - RSI, MACD, Stochastic, etc.
"""



import numpy as np

import pandas as pd

from typing import List, Optional, Tuple

from dataclasses import dataclass





class RSI:

    """
    Relative Strength Index
    Measures speed and change of price movements
    """



    def __init__(self, period: int = 14, upper: float = 70, lower: float = 30):

        self.period = period

        self.upper = upper

        self.lower = lower



    def calculate(self, prices: pd.Series) -> pd.Series:

        """Calculate RSI"""

        delta = prices.diff()



        gain = (delta.where(delta > 0, 0)).rolling(window=self.period).mean()

        loss = (-delta.where(delta < 0, 0)).rolling(window=self.period).mean()



        rs = gain / loss

        rsi = 100 - (100 / (1 + rs))



        return rsi



    def signals(self, prices: pd.Series) -> pd.Series:

        """Generate signals: 1 = oversold (buy), -1 = overbought (sell), 0 = neutral"""

        rsi = self.calculate(prices)



        signals = pd.Series(0, index=prices.index)

        signals[rsi < self.lower] = 1

        signals[rsi > self.upper] = -1



        return signals



    def is_divergence(

        self,

        prices: pd.Series,

        lookback: int = 5

    ) -> Tuple[bool, str]:

        """Detect bullish/bearish divergence"""

        rsi = self.calculate(prices)





        if len(prices) < lookback + 1:

            return False, ""



        price_low_now = prices.iloc[-1]

        price_low_prev = prices.iloc[-lookback-1:-1].min()

        rsi_low_now = rsi.iloc[-1]

        rsi_low_prev = rsi.iloc[-lookback-1:-1].min()



        if price_low_now < price_low_prev and rsi_low_now > rsi_low_prev:

            return True, "bullish"





        price_high_now = prices.iloc[-1]

        price_high_prev = prices.iloc[-lookback-1:-1].max()

        rsi_high_now = rsi.iloc[-1]

        rsi_high_prev = rsi.iloc[-lookback-1:-1].max()



        if price_high_now > price_high_prev and rsi_high_now < rsi_high_prev:

            return True, "bearish"



        return False, ""





class MACD:

    """
    Moving Average Convergence Divergence
    Trend-following momentum indicator
    """



    def __init__(

        self,

        fast: int = 12,

        slow: int = 26,

        signal: int = 9

    ):

        self.fast = fast

        self.slow = slow

        self.signal = signal



    def calculate(self, prices: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:

        """Calculate MACD line, signal line, and histogram"""

        ema_fast = prices.ewm(span=self.fast, adjust=False).mean()

        ema_slow = prices.ewm(span=self.slow, adjust=False).mean()



        macd_line = ema_fast - ema_slow

        signal_line = macd_line.ewm(span=self.signal, adjust=False).mean()

        histogram = macd_line - signal_line



        return macd_line, signal_line, histogram



    def signals(self, prices: pd.Series) -> pd.Series:

        """Generate signals based on MACD crossovers"""

        macd_line, signal_line, _ = self.calculate(prices)



        signals = pd.Series(0, index=prices.index)

        signals[macd_line > signal_line] = 1

        signals[macd_line < signal_line] = -1





        prev_macd = macd_line.shift(1)

        prev_signal = signal_line.shift(1)



        bullish_cross = (macd_line > signal_line) & (prev_macd <= prev_signal)

        bearish_cross = (macd_line < signal_line) & (prev_macd >= prev_signal)



        return signals, bullish_cross, bearish_cross



    def histogram_divergence(self, prices: pd.Series, lookback: int = 5) -> str:

        """Detect histogram divergence patterns"""

        _, _, histogram = self.calculate(prices)



        if len(histogram) < lookback + 2:

            return ""



        recent_hist = histogram.iloc[-lookback:]





        if all(recent_hist.diff().iloc[1:] < 0) and recent_hist.iloc[-1] > 0:

            return "bullish_convergence"

        elif all(recent_hist.diff().iloc[1:] > 0) and recent_hist.iloc[-1] < 0:

            return "bearish_convergence"



        return ""





class Stochastic:

    """
    Stochastic Oscillator
    Momentum indicator comparing closing price to price range
    """



    def __init__(

        self,

        k_period: int = 14,

        d_period: int = 3,

        smooth: int = 3

    ):

        self.k_period = k_period

        self.d_period = d_period

        self.smooth = smooth



    def calculate(

        self,

        high: pd.Series,

        low: pd.Series,

        close: pd.Series

    ) -> Tuple[pd.Series, pd.Series]:

        """Calculate %K and %D lines"""

        lowest_low = low.rolling(window=self.k_period).min()

        highest_high = high.rolling(window=self.k_period).max()



        k = 100 * (close - lowest_low) / (highest_high - lowest_low)



        if self.smooth > 1:

            k = k.rolling(window=self.smooth).mean()



        d = k.rolling(window=self.d_period).mean()



        return k, d



    def signals(

        self,

        high: pd.Series,

        low: pd.Series,

        close: pd.Series

    ) -> pd.Series:

        """Generate signals"""

        k, d = self.calculate(high, low, close)



        signals = pd.Series(0, index=close.index)

        signals[(k > d) & (k < 20)] = 1

        signals[(k < d) & (k > 80)] = -1



        return signals





class WilliamsR:

    """
    Williams %R
    Momentum indicator similar to Stochastic
    """



    def __init__(self, period: int = 14):

        self.period = period



    def calculate(

        self,

        high: pd.Series,

        low: pd.Series,

        close: pd.Series

    ) -> pd.Series:

        """Calculate Williams %R"""

        highest_high = high.rolling(window=self.period).max()

        lowest_low = low.rolling(window=self.period).min()



        wr = -100 * (highest_high - close) / (highest_high - lowest_low)



        return wr



    def signals(

        self,

        high: pd.Series,

        low: pd.Series,

        close: pd.Series

    ) -> pd.Series:

        """Generate signals: -20 = overbought, -80 = oversold"""

        wr = self.calculate(high, low, close)



        signals = pd.Series(0, index=close.index)

        signals[wr < -80] = 1

        signals[wr > -20] = -1



        return signals





class CCI:

    """
    Commodity Channel Index
    Measures current price level relative to average price
    """



    def __init__(self, period: int = 20, constant: float = 0.015):

        self.period = period

        self.constant = constant



    def calculate(

        self,

        high: pd.Series,

        low: pd.Series,

        close: pd.Series

    ) -> pd.Series:

        """Calculate CCI"""

        tp = (high + low + close) / 3

        sma_tp = tp.rolling(window=self.period).mean()



        mean_deviation = tp.rolling(window=self.period).apply(

            lambda x: np.mean(np.abs(x - np.mean(x)))

        )



        cci = (tp - sma_tp) / (self.constant * mean_deviation)



        return cci



    def signals(

        self,

        high: pd.Series,

        low: pd.Series,

        close: pd.Series

    ) -> pd.Series:

        """Generate signals"""

        cci = self.calculate(high, low, close)



        signals = pd.Series(0, index=close.index)

        signals[cci < -100] = 1

        signals[cci > 100] = -1



        return signals





class RateOfChange:

    """
    Rate of Change (ROC)
    Pure momentum oscillator
    """



    def __init__(self, period: int = 12):

        self.period = period



    def calculate(self, prices: pd.Series) -> pd.Series:

        """Calculate ROC"""

        roc = (prices / prices.shift(self.period) - 1) * 100

        return roc



    def signals(self, prices: pd.Series) -> pd.Series:

        """Generate signals based on zero line cross"""

        roc = self.calculate(prices)



        signals = pd.Series(0, index=prices.index)

        signals[roc > 0] = 1

        signals[roc < 0] = -1



        return signals





class MomentumIndex:

    """
    Custom momentum index combining multiple momentum indicators
    """



    def __init__(self):

        self.rsi = RSI(period=14)

        self.macd = MACD()

        self.roc = RateOfChange(period=10)



    def calculate(self, prices: pd.Series) -> pd.Series:

        """Calculate composite momentum index (-1 to 1)"""

        rsi_val = self.rsi.calculate(prices) / 50 - 1



        macd_line, signal_line, _ = self.macd.calculate(prices)

        macd_val = ((macd_line - signal_line) / prices).clip(-1, 1)



        roc_val = self.roc.calculate(prices) / 100

        roc_val = roc_val.clip(-1, 1)





        momentum = (rsi_val * 0.4 + macd_val * 0.4 + roc_val * 0.2)



        return momentum



    def signals(self, prices: pd.Series) -> pd.Series:

        """Generate signals from momentum index"""

        momentum = self.calculate(prices)



        signals = pd.Series(0, index=prices.index)

        signals[momentum > 0.3] = 1

        signals[momentum < -0.3] = -1



        return signals
