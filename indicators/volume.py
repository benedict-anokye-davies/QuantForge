"""
Volume Indicators - VWAP, OBV, Volume Profile, MFI
"""



import numpy as np

import pandas as pd

from typing import Tuple, Dict, Optional

from scipy import stats





class VWAP:

    """
    Volume Weighted Average Price
    """



    def __init__(self, reset_period: Optional[int] = None):

        self.reset_period = reset_period



    def calculate(

        self,

        high: pd.Series,

        low: pd.Series,

        close: pd.Series,

        volume: pd.Series

    ) -> pd.Series:

        """Calculate VWAP"""

        typical_price = (high + low + close) / 3



        if self.reset_period:



            vwap = (typical_price * volume).groupby(

                pd.Grouper(freq=f'{self.reset_period}D')

            ).apply(lambda x: x.cumsum() / volume.loc[x.index].cumsum())

        else:



            vwap = (typical_price * volume).cumsum() / volume.cumsum()



        return vwap



    def deviation(

        self,

        close: pd.Series,

        vwap: pd.Series

    ) -> pd.Series:

        """Price deviation from VWAP as percentage"""

        return (close - vwap) / vwap * 100





class OBV:

    """
    On-Balance Volume
    Cumulative volume flow indicator
    """



    def calculate(

        self,

        close: pd.Series,

        volume: pd.Series

    ) -> pd.Series:

        """Calculate OBV"""

        obv = pd.Series(index=close.index, dtype=float)

        obv.iloc[0] = volume.iloc[0]



        for i in range(1, len(close)):

            if close.iloc[i] > close.iloc[i-1]:

                obv.iloc[i] = obv.iloc[i-1] + volume.iloc[i]

            elif close.iloc[i] < close.iloc[i-1]:

                obv.iloc[i] = obv.iloc[i-1] - volume.iloc[i]

            else:

                obv.iloc[i] = obv.iloc[i-1]



        return obv



    def divergence(

        self,

        close: pd.Series,

        obv: pd.Series,

        lookback: int = 20

    ) -> str:

        """Detect OBV divergence"""

        if len(close) < lookback + 1:

            return ""





        price_low_now = close.iloc[-1]

        price_low_prev = close.iloc[-lookback-1:-1].min()

        obv_low_now = obv.iloc[-1]

        obv_low_prev = obv.iloc[-lookback-1:-1].min()



        if price_low_now < price_low_prev and obv_low_now > obv_low_prev:

            return "bullish"





        price_high_now = close.iloc[-1]

        price_high_prev = close.iloc[-lookback-1:-1].max()

        obv_high_now = obv.iloc[-1]

        obv_high_prev = obv.iloc[-lookback-1:-1].max()



        if price_high_now > price_high_prev and obv_high_now < obv_high_prev:

            return "bearish"



        return ""





class VolumeProfile:

    """
    Volume Profile - price levels with most trading activity
    """



    def __init__(self, num_bins: int = 24):

        self.num_bins = num_bins



    def calculate(

        self,

        low: pd.Series,

        high: pd.Series,

        close: pd.Series,

        volume: pd.Series

    ) -> Tuple[pd.Series, pd.Series]:

        """
        Calculate volume profile
        Returns: (price_levels, volume_at_level)
        """



        price_range = high.max() - low.min()

        bin_size = price_range / self.num_bins



        bins = np.linspace(low.min(), high.max(), self.num_bins + 1)





        vol_profile = pd.Series(0.0, index=bins[:-1])



        for i in range(len(close)):



            price = close.iloc[i]

            vol = volume.iloc[i]





            bin_idx = int((price - bins[0]) / bin_size)

            if 0 <= bin_idx < len(vol_profile):

                vol_profile.iloc[bin_idx] += vol



        return pd.Series(bins[:-1]), vol_profile



    def poc(self, price_levels: pd.Series, volume: pd.Series) -> float:

        """Point of Control - price level with highest volume"""

        return price_levels.iloc[volume.idxmax()]



    def value_area(

        self,

        price_levels: pd.Series,

        volume: pd.Series,

        va_pct: float = 0.70

    ) -> Tuple[float, float]:

        """
        Calculate Value Area
        Returns: (va_low, va_high)
        """

        total_vol = volume.sum()

        target_vol = total_vol * va_pct



        poc_idx = volume.idxmax()





        cum_vol = volume.iloc[poc_idx]

        lower_idx = upper_idx = poc_idx



        while cum_vol < target_vol and (lower_idx > 0 or upper_idx < len(volume) - 1):



            if lower_idx > 0:

                lower_idx -= 1

                cum_vol += volume.iloc[lower_idx]



            if cum_vol >= target_vol:

                break





            if upper_idx < len(volume) - 1:

                upper_idx += 1

                cum_vol += volume.iloc[upper_idx]



        return price_levels.iloc[lower_idx], price_levels.iloc[upper_idx]





class MoneyFlowIndex:

    """
    Money Flow Index (MFI)
    Volume-weighted RSI
    """



    def __init__(self, period: int = 14, overbought: float = 80, oversold: float = 20):

        self.period = period

        self.overbought = overbought

        self.oversold = oversold



    def calculate(

        self,

        high: pd.Series,

        low: pd.Series,

        close: pd.Series,

        volume: pd.Series

    ) -> pd.Series:

        """Calculate MFI"""

        typical_price = (high + low + close) / 3



        raw_money_flow = typical_price * volume





        money_flow_sign = np.where(

            typical_price > typical_price.shift(1),

            1,

            np.where(typical_price < typical_price.shift(1), -1, 0)

        )



        positive_flow = pd.Series(

            np.where(money_flow_sign > 0, raw_money_flow, 0),

            index=close.index

        )

        negative_flow = pd.Series(

            np.where(money_flow_sign < 0, raw_money_flow, 0),

            index=close.index

        )



        positive_sum = positive_flow.rolling(window=self.period).sum()

        negative_sum = negative_flow.rolling(window=self.period).sum()



        money_ratio = positive_sum / negative_sum

        mfi = 100 - (100 / (1 + money_ratio))



        return mfi



    def signals(

        self,

        high: pd.Series,

        low: pd.Series,

        close: pd.Series,

        volume: pd.Series

    ) -> pd.Series:

        """Generate MFI signals"""

        mfi = self.calculate(high, low, close, volume)



        signals = pd.Series(0, index=close.index)

        signals[mfi < self.oversold] = 1

        signals[mfi > self.overbought] = -1



        return signals





class VolumeSpike:

    """
    Detect unusual volume activity
    """



    def __init__(self, lookback: int = 20, spike_threshold: float = 2.0):

        self.lookback = lookback

        self.spike_threshold = spike_threshold



    def detect(

        self,

        volume: pd.Series,

        close: pd.Series

    ) -> pd.Series:

        """
        Detect volume spikes
        Returns: spike magnitude (1.0 = average, >2.0 = spike)
        """

        avg_volume = volume.rolling(window=self.lookback).mean()

        spike_ratio = volume / avg_volume



        return spike_ratio



    def with_price_confirmation(

        self,

        volume: pd.Series,

        close: pd.Series,

        spike_threshold: float = 2.0

    ) -> pd.Series:

        """
        Volume spike with price move confirmation
        """

        spike = self.detect(volume, close)

        price_change = close.pct_change().abs()





        confirmation = (spike > spike_threshold) & (price_change > price_change.rolling(self.lookback).mean())



        return confirmation





class RelativeVolume:

    """
    Compare current volume to historical average at same time
    Useful for intraday trading
    """



    def __init__(self, lookback_days: int = 20):

        self.lookback_days = lookback_days



    def calculate(

        self,

        volume: pd.Series,

        timestamp: pd.Series

    ) -> pd.Series:

        """
        Calculate relative volume at time
        """



        rvol = pd.Series(index=volume.index, dtype=float)



        for idx in volume.index:

            current_time = timestamp.iloc[idx].time()





            mask = timestamp.apply(lambda x: x.time() == current_time)

            historical = volume[mask].iloc[-self.lookback_days:]



            if len(historical) > 0:

                avg_vol = historical.mean()

                rvol.iloc[idx] = volume.iloc[idx] / avg_vol if avg_vol > 0 else 1.0

            else:

                rvol.iloc[idx] = 1.0



        return rvol
