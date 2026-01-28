"""
Statistical Indicators - Z-Score, Linear Regression, Hurst Exponent
"""



import numpy as np

import pandas as pd

from typing import Tuple

from scipy import stats





class ZScore:

    """
    Z-Score normalization
    Measures how many standard deviations from the mean
    """



    def __init__(self, period: int = 20):

        self.period = period



    def calculate(self, prices: pd.Series) -> pd.Series:

        """Calculate Z-Score"""

        rolling_mean = prices.rolling(window=self.period).mean()

        rolling_std = prices.rolling(window=self.period).std()



        zscore = (prices - rolling_mean) / rolling_std

        return zscore



    def normalize(

        self,

        prices: pd.Series,

        target_mean: float = 0,

        target_std: float = 1

    ) -> pd.Series:

        """Normalize to target mean and std"""

        zscore = self.calculate(prices)

        return zscore * target_std + target_mean





class LinearRegression:

    """
    Linear regression analysis on price series
    """



    def __init__(self, period: int = 20):

        self.period = period



    def calculate(self, prices: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:

        """
        Calculate linear regression components
        Returns: (slope, intercept, r_squared)
        """

        slope = pd.Series(index=prices.index, dtype=float)

        intercept = pd.Series(index=prices.index, dtype=float)

        r_squared = pd.Series(index=prices.index, dtype=float)



        for i in range(self.period - 1, len(prices)):

            y = prices.iloc[i - self.period + 1:i + 1].values

            x = np.arange(len(y))



            slope_val, intercept_val, r_val, _, _ = stats.linregress(x, y)



            slope.iloc[i] = slope_val

            intercept.iloc[i] = intercept_val

            r_squared.iloc[i] = r_val ** 2



        return slope, intercept, r_squared



    def forecast(

        self,

        prices: pd.Series,

        periods_ahead: int = 1

    ) -> pd.Series:

        """Forecast future price based on linear trend"""

        slope, intercept, _ = self.calculate(prices)



        forecast = intercept + slope * (self.period + periods_ahead - 1)

        return forecast



    def trend_strength(self, r_squared: pd.Series) -> pd.Series:

        """Classify trend strength based on R-squared"""

        strength = pd.Series('weak', index=r_squared.index)

        strength[r_squared > 0.5] = 'moderate'

        strength[r_squared > 0.8] = 'strong'

        return strength





class HurstExponent:

    """
    Hurst Exponent - measure of long-term memory of time series
    H < 0.5: Mean-reverting
    H = 0.5: Random walk
    H > 0.5: Trending
    """



    def __init__(self, max_lag: int = 100):

        self.max_lag = max_lag



    def calculate(self, prices: pd.Series) -> float:

        """
        Calculate Hurst Exponent using R/S analysis
        """

        lags = range(2, min(self.max_lag, len(prices) // 4))



        tau = [np.std(np.subtract(prices[lag:].values, prices[:-lag].values))

               for lag in lags]





        log_lags = np.log(list(lags))

        log_tau = np.log(tau)



        slope, _, _, _, _ = stats.linregress(log_lags, log_tau)





        hurst = slope / 2



        return hurst



    def rolling_hurst(

        self,

        prices: pd.Series,

        window: int = 200

    ) -> pd.Series:

        """Calculate rolling Hurst Exponent"""

        hurst = pd.Series(index=prices.index, dtype=float)



        for i in range(window, len(prices)):

            hurst.iloc[i] = self.calculate(prices.iloc[i - window:i])



        return hurst



    def regime(self, hurst: float) -> str:

        """Classify market regime based on Hurst"""

        if hurst < 0.4:

            return 'mean_reverting'

        elif hurst > 0.6:

            return 'trending'

        else:

            return 'random_walk'





class AugmentedDF:

    """
    Augmented Dickey-Fuller test for stationarity
    """



    def __init__(self):

        pass



    def test(self, prices: pd.Series) -> Tuple[float, float, bool]:

        """
        Perform ADF test
        Returns: (test_statistic, p_value, is_stationary)
        """

        try:

            from statsmodels.tsa.stattools import adfuller



            result = adfuller(prices.dropna(), autolag='AIC')

            test_stat = result[0]

            p_value = result[1]

            is_stationary = p_value < 0.05



            return test_stat, p_value, is_stationary

        except ImportError:

            return 0, 1, False





class Cointegration:

    """
    Test for cointegration between two time series
    """



    def __init__(self):

        pass



    def test(

        self,

        series1: pd.Series,

        series2: pd.Series

    ) -> Tuple[float, float, bool]:

        """
        Engle-Granger cointegration test
        Returns: (test_statistic, p_value, is_cointegrated)
        """

        try:

            from statsmodels.tsa.stattools import coint



            score, p_value, _ = coint(series1, series2)

            is_cointegrated = p_value < 0.05



            return score, p_value, is_cointegrated

        except ImportError:

            return 0, 1, False



    def hedge_ratio(

        self,

        series1: pd.Series,

        series2: pd.Series

    ) -> float:

        """Calculate hedge ratio for pairs trading"""

        slope, _, _, _, _ = stats.linregress(series2, series1)

        return slope





class Autocorrelation:

    """
    Autocorrelation analysis
    """



    def __init__(self, max_lags: int = 20):

        self.max_lags = max_lags



    def calculate(self, returns: pd.Series) -> pd.Series:

        """Calculate autocorrelation for multiple lags"""

        autocorr = pd.Series(index=range(1, self.max_lags + 1), dtype=float)



        for lag in range(1, self.max_lags + 1):

            autocorr.iloc[lag - 1] = returns.autocorr(lag=lag)



        return autocorr



    def significance(

        self,

        autocorr: pd.Series,

        n_obs: int,

        alpha: float = 0.05

    ) -> pd.Series:

        """Determine which autocorrelations are significant"""



        se = 1 / np.sqrt(n_obs)





        critical_val = stats.norm.ppf(1 - alpha / 2) * se



        is_significant = autocorr.abs() > critical_val



        return is_significant





class VarianceRatio:

    """
    Variance Ratio Test
    Tests random walk hypothesis
    """



    def __init__(self, period: int = 2):

        self.period = period



    def calculate(self, prices: pd.Series) -> float:

        """
        Calculate variance ratio
        VR = 1: Random walk
        VR < 1: Mean reverting
        VR > 1: Momentum
        """

        returns = prices.pct_change().dropna()





        var_1 = returns.var()





        returns_k = prices.pct_change(self.period).dropna()

        var_k = returns_k.var() / self.period



        if var_k == 0:

            return 1.0



        vr = var_1 / var_k



        return vr





class HalfLife:

    """
    Calculate half-life of mean reversion
    """



    def calculate(self, prices: pd.Series) -> float:

        """
        Calculate half-life of mean reversion using Ornstein-Uhlenbeck
        """



        lagged_price = prices.shift(1).dropna()

        delta_price = prices.diff().dropna()





        lagged_price = lagged_price[1:]





        slope, intercept, _, _, _ = stats.linregress(lagged_price, delta_price)





        if slope >= 0:

            return np.inf



        half_life = -np.log(2) / slope



        return half_life
