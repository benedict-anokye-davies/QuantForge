"""
Momentum Strategies - RSI, MACD, and Composite Momentum
"""



from typing import Optional

import pandas as pd

import numpy as np



from .base import Strategy, StrategyConfig

from ..core.events import MarketEvent, SignalEvent

from ..indicators.momentum import RSI, MACD, MomentumIndex, RateOfChange

from ..indicators.trend import ADX





class MomentumStrategy(Strategy):

    """
    Composite Momentum Strategy
    Combines multiple momentum indicators for robust signals
    """



    def __init__(

        self,

        symbols: list = None,

        momentum_threshold: float = 0.3,

        lookback: int = 20

    ):

        config = StrategyConfig(

            name="MomentumStrategy",

            symbols=symbols,

        )

        super().__init__(config)



        self.momentum_index = MomentumIndex()

        self.momentum_threshold = momentum_threshold

        self.lookback = lookback

        self.adx = ADX(period=14)



    def on_market_data(self, event: MarketEvent) -> Optional[SignalEvent]:

        """Generate momentum-based signals"""

        self.update_data(event)



        data = self.data_history.get(event.symbol)

        if data is None or len(data) < self.lookback:

            return None



        close = data['close']

        high = data['high']

        low = data['low']





        momentum = self.momentum_index.calculate(close)

        current_momentum = momentum.iloc[-1]





        adx_value = self.adx.calculate(high, low, close).iloc[-1]





        if adx_value < 25:

            return None





        position = self.get_position(event.symbol)





        if current_momentum > self.momentum_threshold:

            if position <= 0:

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='LONG',

                    price=event.close,

                    strength=min(abs(current_momentum), 1.0),

                    confidence=adx_value / 100,

                    metadata={

                        'momentum': current_momentum,

                        'adx': adx_value

                    }

                )



        elif current_momentum < -self.momentum_threshold:

            if position >= 0:

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='SHORT',

                    price=event.close,

                    strength=min(abs(current_momentum), 1.0),

                    confidence=adx_value / 100,

                    metadata={

                        'momentum': current_momentum,

                        'adx': adx_value

                    }

                )





        if position > 0 and current_momentum < 0:

            return self.generate_signal(

                symbol=event.symbol,

                signal_type='EXIT',

                price=event.close,

                strength=1.0,

                metadata={'reason': 'momentum_reversal'}

            )

        elif position < 0 and current_momentum > 0:

            return self.generate_signal(

                symbol=event.symbol,

                signal_type='EXIT',

                price=event.close,

                strength=1.0,

                metadata={'reason': 'momentum_reversal'}

            )



        return None





class RSIStrategy(Strategy):

    """
    RSI Mean Reversion Strategy
    Buy oversold, sell overbought
    """



    def __init__(

        self,

        symbols: list = None,

        period: int = 14,

        oversold: float = 30,

        overbought: float = 70,

        use_divergence: bool = True

    ):

        config = StrategyConfig(

            name="RSIStrategy",

            symbols=symbols,

        )

        super().__init__(config)



        self.rsi = RSI(period=period, upper=overbought, lower=oversold)

        self.oversold = oversold

        self.overbought = overbought

        self.use_divergence = use_divergence



    def on_market_data(self, event: MarketEvent) -> Optional[SignalEvent]:

        """Generate RSI-based signals"""

        self.update_data(event)



        data = self.data_history.get(event.symbol)

        if data is None or len(data) < self.rsi.period + 5:

            return None



        close = data['close']

        rsi_values = self.rsi.calculate(close)

        current_rsi = rsi_values.iloc[-1]



        position = self.get_position(event.symbol)





        divergence = None

        if self.use_divergence:

            is_divergence, div_type = self.rsi.is_divergence(close, lookback=5)

            if is_divergence:

                divergence = div_type





        if current_rsi < self.oversold:



            if position <= 0:

                confidence = 0.5 + (self.oversold - current_rsi) / 100

                if divergence == "bullish":

                    confidence += 0.2



                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='LONG',

                    price=event.close,

                    strength=(self.oversold - current_rsi) / self.oversold,

                    confidence=min(confidence, 1.0),

                    metadata={

                        'rsi': current_rsi,

                        'divergence': divergence

                    }

                )



        elif current_rsi > self.overbought:



            if position >= 0:

                confidence = 0.5 + (current_rsi - self.overbought) / 100

                if divergence == "bearish":

                    confidence += 0.2



                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='SHORT',

                    price=event.close,

                    strength=(current_rsi - self.overbought) / (100 - self.overbought),

                    confidence=min(confidence, 1.0),

                    metadata={

                        'rsi': current_rsi,

                        'divergence': divergence

                    }

                )





        if position > 0 and current_rsi > 50:

            return self.generate_signal(

                symbol=event.symbol,

                signal_type='EXIT',

                price=event.close,

                strength=1.0,

                metadata={'rsi': current_rsi, 'reason': 'return_to_neutral'}

            )

        elif position < 0 and current_rsi < 50:

            return self.generate_signal(

                symbol=event.symbol,

                signal_type='EXIT',

                price=event.close,

                strength=1.0,

                metadata={'rsi': current_rsi, 'reason': 'return_to_neutral'}

            )



        return None





class MACDStrategy(Strategy):

    """
    MACD Trend Following Strategy
    Signal on MACD line crossovers
    """



    def __init__(

        self,

        symbols: list = None,

        fast: int = 12,

        slow: int = 26,

        signal: int = 9,

        use_histogram: bool = True

    ):

        config = StrategyConfig(

            name="MACDStrategy",

            symbols=symbols,

        )

        super().__init__(config)



        self.macd = MACD(fast=fast, slow=slow, signal=signal)

        self.use_histogram = use_histogram

        self.prev_signals = {}



    def on_market_data(self, event: MarketEvent) -> Optional[SignalEvent]:

        """Generate MACD-based signals"""

        self.update_data(event)



        data = self.data_history.get(event.symbol)

        if data is None or len(data) < self.macd.slow + 10:

            return None



        close = data['close']

        macd_line, signal_line, histogram = self.macd.calculate(close)





        current_macd = macd_line.iloc[-1]

        current_signal = signal_line.iloc[-1]

        prev_macd = macd_line.iloc[-2]

        prev_signal = signal_line.iloc[-2]



        position = self.get_position(event.symbol)





        bullish_cross = (current_macd > current_signal) and (prev_macd <= prev_signal)

        bearish_cross = (current_macd < current_signal) and (prev_macd >= prev_signal)





        hist_trend = ""

        if self.use_histogram and len(histogram) >= 3:

            if histogram.iloc[-1] > histogram.iloc[-2] > histogram.iloc[-3]:

                hist_trend = "rising"

            elif histogram.iloc[-1] < histogram.iloc[-2] < histogram.iloc[-3]:

                hist_trend = "falling"





        if bullish_cross:

            if position <= 0:

                confidence = 0.6

                if hist_trend == "rising":

                    confidence += 0.2



                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='LONG',

                    price=event.close,

                    strength=1.0,

                    confidence=confidence,

                    metadata={

                        'macd': current_macd,

                        'signal': current_signal,

                        'histogram_trend': hist_trend

                    }

                )



        elif bearish_cross:

            if position >= 0:

                confidence = 0.6

                if hist_trend == "falling":

                    confidence += 0.2



                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='SHORT',

                    price=event.close,

                    strength=1.0,

                    confidence=confidence,

                    metadata={

                        'macd': current_macd,

                        'signal': current_signal,

                        'histogram_trend': hist_trend

                    }

                )



        return None





class ROCStrategy(Strategy):

    """
    Rate of Change Momentum Strategy
    """



    def __init__(

        self,

        symbols: list = None,

        period: int = 12,

        threshold: float = 5.0

    ):

        config = StrategyConfig(

            name="ROCStrategy",

            symbols=symbols,

        )

        super().__init__(config)



        self.roc = RateOfChange(period=period)

        self.threshold = threshold



    def on_market_data(self, event: MarketEvent) -> Optional[SignalEvent]:

        """Generate ROC-based signals"""

        self.update_data(event)



        data = self.data_history.get(event.symbol)

        if data is None or len(data) < self.roc.period + 5:

            return None



        close = data['close']

        roc_values = self.roc.calculate(close)

        current_roc = roc_values.iloc[-1]



        position = self.get_position(event.symbol)





        prev_roc = roc_values.iloc[-2]



        if prev_roc < 0 and current_roc > 0:



            if position <= 0 and current_roc > self.threshold:

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='LONG',

                    price=event.close,

                    strength=min(abs(current_roc) / 10, 1.0),

                    metadata={'roc': current_roc}

                )



        elif prev_roc > 0 and current_roc < 0:



            if position >= 0 and current_roc < -self.threshold:

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='SHORT',

                    price=event.close,

                    strength=min(abs(current_roc) / 10, 1.0),

                    metadata={'roc': current_roc}

                )



        return None
