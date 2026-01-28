"""
Trend Following Strategies - Moving Averages, ADX, Breakouts
"""



from typing import Optional

import pandas as pd

import numpy as np



from .base import Strategy, StrategyConfig

from ..core.events import MarketEvent, SignalEvent

from ..indicators.trend import EMA, SMA, ADX, ParabolicSAR

from ..indicators.volatility import ATR, DonchianChannels





class TrendFollowingStrategy(Strategy):

    """
    Multi-timeframe Trend Following Strategy
    Uses EMA crossovers and ADX for trend confirmation
    """



    def __init__(

        self,

        symbols: list = None,

        fast_ema: int = 20,

        slow_ema: int = 50,

        adx_threshold: float = 25,

        use_atr_stops: bool = True

    ):

        config = StrategyConfig(

            name="TrendFollowingStrategy",

            symbols=symbols,

        )

        super().__init__(config)



        self.fast_ema = EMA(period=fast_ema)

        self.slow_ema = EMA(period=slow_ema)

        self.adx = ADX(period=14)

        self.adx_threshold = adx_threshold

        self.use_atr_stops = use_atr_stops

        self.atr = ATR(period=14)



    def on_market_data(self, event: MarketEvent) -> Optional[SignalEvent]:

        """Generate trend following signals"""

        self.update_data(event)



        data = self.data_history.get(event.symbol)

        if data is None or len(data) < self.slow_ema.period + 10:

            return None



        close = data['close']

        high = data['high']

        low = data['low']





        fast = self.fast_ema.calculate(close)

        slow = self.slow_ema.calculate(close)

        adx_values = self.adx.calculate(high, low, close)



        current_fast = fast.iloc[-1]

        current_slow = slow.iloc[-1]

        prev_fast = fast.iloc[-2]

        prev_slow = slow.iloc[-2]

        current_adx = adx_values.iloc[-1]



        position = self.get_position(event.symbol)





        if current_adx < self.adx_threshold:

            return None





        bullish_cross = (current_fast > current_slow) and (prev_fast <= prev_slow)

        bearish_cross = (current_fast < current_slow) and (prev_fast >= prev_slow)





        in_uptrend = current_fast > current_slow

        in_downtrend = current_fast < current_slow



        if bullish_cross:



            if position <= 0:

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='LONG',

                    price=event.close,

                    strength=1.0,

                    confidence=min(current_adx / 50, 1.0),

                    metadata={

                        'fast_ema': current_fast,

                        'slow_ema': current_slow,

                        'adx': current_adx

                    }

                )



        elif bearish_cross:



            if position >= 0:

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='SHORT',

                    price=event.close,

                    strength=1.0,

                    confidence=min(current_adx / 50, 1.0),

                    metadata={

                        'fast_ema': current_fast,

                        'slow_ema': current_slow,

                        'adx': current_adx

                    }

                )





        if self.use_atr_stops and position != 0:

            atr_value = self.atr.calculate(high, low, close).iloc[-1]



            if position > 0:



                stop_level = current_fast - (atr_value * 2)

                if event.close < stop_level:

                    return self.generate_signal(

                        symbol=event.symbol,

                        signal_type='EXIT',

                        price=event.close,

                        strength=1.0,

                        metadata={'reason': 'atr_stop', 'stop_level': stop_level}

                    )

            elif position < 0:



                stop_level = current_fast + (atr_value * 2)

                if event.close > stop_level:

                    return self.generate_signal(

                        symbol=event.symbol,

                        signal_type='EXIT',

                        price=event.close,

                        strength=1.0,

                        metadata={'reason': 'atr_stop', 'stop_level': stop_level}

                    )





        if position > 0 and in_downtrend:

            return self.generate_signal(

                symbol=event.symbol,

                signal_type='EXIT',

                price=event.close,

                strength=1.0,

                metadata={'reason': 'trend_reversal'}

            )

        elif position < 0 and in_uptrend:

            return self.generate_signal(

                symbol=event.symbol,

                signal_type='EXIT',

                price=event.close,

                strength=1.0,

                metadata={'reason': 'trend_reversal'}

            )



        return None





class ADXStrategy(Strategy):

    """
    ADX-based Trend Strength Strategy
    Trade only when trend is strong and direction is clear
    """



    def __init__(

        self,

        symbols: list = None,

        adx_period: int = 14,

        adx_threshold: float = 25,

        di_threshold: float = 20

    ):

        config = StrategyConfig(

            name="ADXStrategy",

            symbols=symbols,

        )

        super().__init__(config)



        self.adx = ADX(period=adx_period)

        self.adx_threshold = adx_threshold

        self.di_threshold = di_threshold



    def on_market_data(self, event: MarketEvent) -> Optional[SignalEvent]:

        """Generate ADX-based signals"""

        self.update_data(event)



        data = self.data_history.get(event.symbol)

        if data is None or len(data) < self.adx.period + 5:

            return None



        close = data['close']

        high = data['high']

        low = data['low']





        adx_values = self.adx.calculate(high, low, close)

        plus_di = self.adx.plus_di

        minus_di = self.adx.minus_di



        current_adx = adx_values.iloc[-1]

        current_plus_di = plus_di.iloc[-1] if hasattr(plus_di, 'iloc') else plus_di

        current_minus_di = minus_di.iloc[-1] if hasattr(minus_di, 'iloc') else minus_di



        position = self.get_position(event.symbol)





        if current_adx < self.adx_threshold:

            return None





        if current_plus_di > current_minus_di and current_plus_di > self.di_threshold:



            if position <= 0:

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='LONG',

                    price=event.close,

                    strength=1.0,

                    confidence=min(current_adx / 50, 1.0),

                    metadata={

                        'adx': current_adx,

                        'plus_di': current_plus_di,

                        'minus_di': current_minus_di

                    }

                )



        elif current_minus_di > current_plus_di and current_minus_di > self.di_threshold:



            if position >= 0:

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='SHORT',

                    price=event.close,

                    strength=1.0,

                    confidence=min(current_adx / 50, 1.0),

                    metadata={

                        'adx': current_adx,

                        'plus_di': current_plus_di,

                        'minus_di': current_minus_di

                    }

                )





        if position != 0 and current_adx < self.adx_threshold * 0.8:

            return self.generate_signal(

                symbol=event.symbol,

                signal_type='EXIT',

                price=event.close,

                strength=1.0,

                metadata={'adx': current_adx, 'reason': 'weakening_trend'}

            )



        return None





class MovingAverageCrossover(Strategy):

    """
    Simple Moving Average Crossover
    Classic trend following approach
    """



    def __init__(

        self,

        symbols: list = None,

        fast_period: int = 50,

        slow_period: int = 200,

        ma_type: str = 'EMA'

    ):

        config = StrategyConfig(

            name="MACrossover",

            symbols=symbols,

        )

        super().__init__(config)



        self.fast_period = fast_period

        self.slow_period = slow_period

        self.ma_type = ma_type



    def on_market_data(self, event: MarketEvent) -> Optional[SignalEvent]:

        """Generate MA crossover signals"""

        self.update_data(event)



        data = self.data_history.get(event.symbol)

        if data is None or len(data) < self.slow_period + 5:

            return None



        close = data['close']





        if self.ma_type == 'EMA':

            fast = close.ewm(span=self.fast_period, adjust=False).mean()

            slow = close.ewm(span=self.slow_period, adjust=False).mean()

        else:

            fast = close.rolling(window=self.fast_period).mean()

            slow = close.rolling(window=self.slow_period).mean()



        current_fast = fast.iloc[-1]

        current_slow = slow.iloc[-1]

        prev_fast = fast.iloc[-2]

        prev_slow = slow.iloc[-2]



        position = self.get_position(event.symbol)





        if current_fast > current_slow and prev_fast <= prev_slow:

            if position <= 0:

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='LONG',

                    price=event.close,

                    strength=1.0,

                    metadata={'crossover': 'golden', 'fast_ma': current_fast, 'slow_ma': current_slow}

                )





        elif current_fast < current_slow and prev_fast >= prev_slow:

            if position >= 0:

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='SHORT',

                    price=event.close,

                    strength=1.0,

                    metadata={'crossover': 'death', 'fast_ma': current_fast, 'slow_ma': current_slow}

                )



        return None





class ParabolicSARStrategy(Strategy):

    """
    Parabolic SAR Strategy
    Classic trend following with dynamic stops
    """



    def __init__(

        self,

        symbols: list = None,

        af_start: float = 0.02,

        af_increment: float = 0.02,

        af_max: float = 0.2

    ):

        config = StrategyConfig(

            name="ParabolicSAR",

            symbols=symbols,

        )

        super().__init__(config)



        self.psar = ParabolicSAR(

            af_start=af_start,

            af_increment=af_increment,

            af_max=af_max

        )



    def on_market_data(self, event: MarketEvent) -> Optional[SignalEvent]:

        """Generate Parabolic SAR signals"""

        self.update_data(event)



        data = self.data_history.get(event.symbol)

        if data is None or len(data) < 10:

            return None



        high = data['high']

        low = data['low']

        close = data['close']





        psar_values = self.psar.calculate(high, low)

        current_psar = psar_values.iloc[-1]

        prev_psar = psar_values.iloc[-2]



        position = self.get_position(event.symbol)





        in_uptrend = current_psar < close.iloc[-1]

        was_uptrend = prev_psar < close.iloc[-2]





        if in_uptrend and not was_uptrend:



            if position <= 0:

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='LONG',

                    price=event.close,

                    strength=1.0,

                    metadata={'psar': current_psar, 'trend': 'up'}

                )



        elif not in_uptrend and was_uptrend:



            if position >= 0:

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='SHORT',

                    price=event.close,

                    strength=1.0,

                    metadata={'psar': current_psar, 'trend': 'down'}

                )



        return None





class DonchianStrategy(Strategy):

    """
    Donchian Channel Breakout Strategy
    Classic trend following - buy breakouts, sell breakdowns
    """



    def __init__(

        self,

        symbols: list = None,

        period: int = 20,

        use_filter: bool = True

    ):

        config = StrategyConfig(

            name="DonchianStrategy",

            symbols=symbols,

        )

        super().__init__(config)



        self.donchian = DonchianChannels(period=period)

        self.use_filter = use_filter

        self.atr = ATR(period=14)



    def on_market_data(self, event: MarketEvent) -> Optional[SignalEvent]:

        """Generate Donchian breakout signals"""

        self.update_data(event)



        data = self.data_history.get(event.symbol)

        if data is None or len(data) < self.donchian.period + 5:

            return None



        high = data['high']

        low = data['low']

        close = data['close']





        upper, middle, lower = self.donchian.calculate(high, low)



        current_upper = upper.iloc[-1]

        current_lower = lower.iloc[-1]

        prev_upper = upper.iloc[-2]

        prev_lower = lower.iloc[-2]



        position = self.get_position(event.symbol)





        breakout_up = close.iloc[-1] > current_upper and close.iloc[-2] <= prev_upper

        breakout_down = close.iloc[-1] < current_lower and close.iloc[-2] >= prev_lower





        if self.use_filter:

            atr_values = self.atr.normalized_atr(high, low, close)

            if atr_values.iloc[-1] < 1.0:

                return None



        if breakout_up:

            if position <= 0:

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='LONG',

                    price=event.close,

                    strength=1.0,

                    metadata={

                        'breakout': 'upper',

                        'channel_upper': current_upper,

                        'channel_lower': current_lower

                    }

                )



        elif breakout_down:

            if position >= 0:

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='SHORT',

                    price=event.close,

                    strength=1.0,

                    metadata={

                        'breakout': 'lower',

                        'channel_upper': current_upper,

                        'channel_lower': current_lower

                    }

                )





        if position > 0 and close.iloc[-1] < middle.iloc[-1]:

            return self.generate_signal(

                symbol=event.symbol,

                signal_type='EXIT',

                price=event.close,

                strength=1.0,

                metadata={'reason': 'middle_line_cross'}

            )

        elif position < 0 and close.iloc[-1] > middle.iloc[-1]:

            return self.generate_signal(

                symbol=event.symbol,

                signal_type='EXIT',

                price=event.close,

                strength=1.0,

                metadata={'reason': 'middle_line_cross'}

            )



        return None
