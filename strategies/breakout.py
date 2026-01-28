"""
Breakout Strategies - Volatility Breakouts, Range Breakouts
"""



from typing import Optional

import pandas as pd

import numpy as np



from .base import Strategy, StrategyConfig

from ..core.events import MarketEvent, SignalEvent

from ..indicators.volatility import BollingerBands, ATR, VolatilityRegime

from ..indicators.volume import VolumeProfile





class BreakoutStrategy(Strategy):

    """
    Volatility Breakout Strategy
    Enter on high volatility breakouts with volume confirmation
    """



    def __init__(

        self,

        symbols: list = None,

        lookback: int = 20,

        volume_confirm: bool = True,

        min_volume_spike: float = 1.5,

        use_bollinger: bool = True

    ):

        config = StrategyConfig(

            name="BreakoutStrategy",

            symbols=symbols,

        )

        super().__init__(config)



        self.lookback = lookback

        self.volume_confirm = volume_confirm

        self.min_volume_spike = min_volume_spike

        self.use_bollinger = use_bollinger



        self.bb = BollingerBands(period=20, std_dev=2.0)

        self.vol_regime = VolatilityRegime()



    def on_market_data(self, event: MarketEvent) -> Optional[SignalEvent]:

        """Generate breakout signals"""

        self.update_data(event)



        data = self.data_history.get(event.symbol)

        if data is None or len(data) < self.lookback + 5:

            return None



        close = data['close']

        high = data['high']

        low = data['low']

        volume = data['volume']





        highest_high = high.rolling(window=self.lookback).max().iloc[-1]

        lowest_low = low.rolling(window=self.lookback).min().iloc[-1]



        position = self.get_position(event.symbol)





        volume_ok = True

        if self.volume_confirm:

            avg_volume = volume.rolling(window=self.lookback).mean().iloc[-1]

            current_volume = volume.iloc[-1]

            volume_ok = current_volume > (avg_volume * self.min_volume_spike)



        if not volume_ok:

            return None





        breakout_up = close.iloc[-1] > highest_high and close.iloc[-2] <= high.rolling(window=self.lookback).max().shift(1).iloc[-1]

        breakout_down = close.iloc[-1] < lowest_low and close.iloc[-2] >= low.rolling(window=self.lookback).min().shift(1).iloc[-1]





        if self.use_bollinger:

            squeeze = self.bb.squeeze(close, lookback=50)

            if not squeeze.iloc[-5:].any():



                pass



        if breakout_up:

            if position <= 0:

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='LONG',

                    price=event.close,

                    strength=1.0,

                    confidence=0.7 if volume_ok else 0.5,

                    metadata={

                        'breakout_type': 'range_high',

                        'range_high': highest_high,

                        'range_low': lowest_low,

                        'volume_confirmed': volume_ok

                    }

                )



        elif breakout_down:

            if position >= 0:

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='SHORT',

                    price=event.close,

                    strength=1.0,

                    confidence=0.7 if volume_ok else 0.5,

                    metadata={

                        'breakout_type': 'range_low',

                        'range_high': highest_high,

                        'range_low': lowest_low,

                        'volume_confirmed': volume_ok

                    }

                )



        return None





class DonchianStrategy(Strategy):

    """
    Donchian Channel Breakout (Turtle Trading Style)
    Classic trend following system
    """



    def __init__(

        self,

        symbols: list = None,

        entry_period: int = 20,

        exit_period: int = 10,

        use_filter: bool = True

    ):

        config = StrategyConfig(

            name="DonchianStrategy",

            symbols=symbols,

        )

        super().__init__(config)



        self.entry_period = entry_period

        self.exit_period = exit_period

        self.use_filter = use_filter



    def on_market_data(self, event: MarketEvent) -> Optional[SignalEvent]:

        """Generate Donchian breakout signals"""

        self.update_data(event)



        data = self.data_history.get(event.symbol)

        if data is None or len(data) < self.entry_period + 5:

            return None



        close = data['close']

        high = data['high']

        low = data['low']





        entry_high = high.rolling(window=self.entry_period).max().iloc[-1]

        entry_low = low.rolling(window=self.entry_period).min().iloc[-1]





        exit_high = high.rolling(window=self.exit_period).max().iloc[-1]

        exit_low = low.rolling(window=self.exit_period).min().iloc[-1]



        position = self.get_position(event.symbol)





        if close.iloc[-1] > entry_high and close.iloc[-2] <= entry_high:

            if position <= 0:

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='LONG',

                    price=event.close,

                    strength=1.0,

                    metadata={

                        'entry_period': self.entry_period,

                        'breakout_level': entry_high

                    }

                )



        elif close.iloc[-1] < entry_low and close.iloc[-2] >= entry_low:

            if position >= 0:

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='SHORT',

                    price=event.close,

                    strength=1.0,

                    metadata={

                        'entry_period': self.entry_period,

                        'breakout_level': entry_low

                    }

                )





        if position > 0 and close.iloc[-1] < exit_low:

            return self.generate_signal(

                symbol=event.symbol,

                signal_type='EXIT',

                price=event.close,

                strength=1.0,

                metadata={'exit_period': self.exit_period, 'reason': 'exit_channel'}

            )

        elif position < 0 and close.iloc[-1] > exit_high:

            return self.generate_signal(

                symbol=event.symbol,

                signal_type='EXIT',

                price=event.close,

                strength=1.0,

                metadata={'exit_period': self.exit_period, 'reason': 'exit_channel'}

            )



        return None





class VolatilityBreakout(Strategy):

    """
    Volatility Breakout Strategy
    Trade when volatility expands after contraction
    """



    def __init__(

        self,

        symbols: list = None,

        contraction_periods: int = 20,

        expansion_threshold: float = 1.5

    ):

        config = StrategyConfig(

            name="VolatilityBreakout",

            symbols=symbols,

        )

        super().__init__(config)



        self.contraction_periods = contraction_periods

        self.expansion_threshold = expansion_threshold

        self.atr = ATR(period=14)



    def on_market_data(self, event: MarketEvent) -> Optional[SignalEvent]:

        """Generate volatility breakout signals"""

        self.update_data(event)



        data = self.data_history.get(event.symbol)

        if data is None or len(data) < self.contraction_periods + 10:

            return None



        close = data['close']

        high = data['high']

        low = data['low']





        atr_values = self.atr.calculate(high, low, close)

        current_atr = atr_values.iloc[-1]

        avg_atr = atr_values.rolling(window=self.contraction_periods).mean().iloc[-1]

        min_atr = atr_values.rolling(window=self.contraction_periods).min().iloc[-1]



        position = self.get_position(event.symbol)





        atr_expanding = current_atr > (avg_atr * self.expansion_threshold)

        was_contracted = min_atr * 1.2 >= current_atr



        if not (atr_expanding and was_contracted):

            return None





        price_change = (close.iloc[-1] - close.iloc[-2]) / close.iloc[-2]



        if price_change > 0:

            if position <= 0:

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='LONG',

                    price=event.close,

                    strength=1.0,

                    metadata={

                        'atr_ratio': current_atr / avg_atr,

                        'price_change': price_change

                    }

                )

        else:

            if position >= 0:

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='SHORT',

                    price=event.close,

                    strength=1.0,

                    metadata={

                        'atr_ratio': current_atr / avg_atr,

                        'price_change': price_change

                    }

                )



        return None





class OpeningRangeBreakout(Strategy):

    """
    Opening Range Breakout
    Trade breakouts from first N minutes of session
    """



    def __init__(

        self,

        symbols: list = None,

        range_minutes: int = 30,

        use_volume: bool = True

    ):

        config = StrategyConfig(

            name="OpeningRangeBreakout",

            symbols=symbols,

        )

        super().__init__(config)



        self.range_minutes = range_minutes

        self.use_volume = use_volume

        self.daily_high = None

        self.daily_low = None

        self.daily_volume = 0

        self.current_date = None



    def on_market_data(self, event: MarketEvent) -> Optional[SignalEvent]:

        """Generate opening range breakout signals"""

        self.update_data(event)





        event_date = event.timestamp.date() if hasattr(event.timestamp, 'date') else event.timestamp



        if self.current_date != event_date:



            self.current_date = event_date

            self.daily_high = event.high

            self.daily_low = event.low

            self.daily_volume = event.volume

            return None





        self.daily_high = max(self.daily_high, event.high)

        self.daily_low = min(self.daily_low, event.low)

        self.daily_volume += event.volume





        data = self.data_history.get(event.symbol)

        if data is None or len(data) < self.range_minutes:

            return None





        opening_data = data.iloc[:self.range_minutes]

        or_high = opening_data['high'].max()

        or_low = opening_data['low'].min()



        position = self.get_position(event.symbol)





        if event.close > or_high and event.close > event.open:

            if position <= 0:

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='LONG',

                    price=event.close,

                    strength=1.0,

                    metadata={

                        'or_high': or_high,

                        'or_low': or_low,

                        'breakout_direction': 'up'

                    }

                )



        elif event.close < or_low and event.close < event.open:

            if position >= 0:

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='SHORT',

                    price=event.close,

                    strength=1.0,

                    metadata={

                        'or_high': or_high,

                        'or_low': or_low,

                        'breakout_direction': 'down'

                    }

                )



        return None
