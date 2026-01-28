"""
VWAP Trading Strategies
"""



from typing import Optional, Tuple, Dict, Any

import pandas as pd

import numpy as np



from .base import Strategy, StrategyConfig

from ..core.events import MarketEvent, SignalEvent

from ..indicators.volume import VWAP





class VWAPStrategy(Strategy):

    """
    VWAP Trading Strategy
    Trade mean reversion to VWAP or momentum breaks
    """



    def __init__(

        self,

        symbols: list = None,

        vwap_period: int = 14,

        band_mult: float = 1.0,

        mode: str = 'mean_reversion'

    ):

        config = StrategyConfig(

            name="VWAPStrategy",

            symbols=symbols,

        )

        super().__init__(config)



        self.vwap_period = vwap_period

        self.band_mult = band_mult

        self.mode = mode



    def calculate_vwap(self, data: pd.DataFrame) -> pd.Series:

        """Calculate VWAP"""

        typical_price = (data['high'] + data['low'] + data['close']) / 3

        vwap = (typical_price * data['volume']).cumsum() / data['volume'].cumsum()

        return vwap



    def calculate_vwap_bands(

        self,

        data: pd.DataFrame,

        vwap: pd.Series

    ) -> Tuple[pd.Series, pd.Series]:

        """Calculate VWAP standard deviation bands"""

        typical_price = (data['high'] + data['low'] + data['close']) / 3

        variance = ((typical_price - vwap) ** 2 * data['volume']).cumsum() / data['volume'].cumsum()

        std = np.sqrt(variance)



        upper = vwap + std * self.band_mult

        lower = vwap - std * self.band_mult



        return upper, lower



    def on_market_data(self, event: MarketEvent) -> Optional[SignalEvent]:

        """Generate VWAP-based signals"""

        self.update_data(event)



        data = self.data_history.get(event.symbol)

        if data is None or len(data) < self.vwap_period:

            return None





        vwap = self.calculate_vwap(data)

        upper, lower = self.calculate_vwap_bands(data, vwap)



        current_vwap = vwap.iloc[-1]

        current_upper = upper.iloc[-1]

        current_lower = lower.iloc[-1]



        position = self.get_position(event.symbol)



        if self.mode == 'mean_reversion':



            if event.close < current_lower:

                if position <= 0:

                    return self.generate_signal(

                        symbol=event.symbol,

                        signal_type='LONG',

                        price=event.close,

                        strength=1.0,

                        metadata={

                            'vwap': current_vwap,

                            'distance_from_vwap': (event.close - current_vwap) / current_vwap

                        }

                    )



            elif event.close > current_upper:

                if position >= 0:

                    return self.generate_signal(

                        symbol=event.symbol,

                        signal_type='SHORT',

                        price=event.close,

                        strength=1.0,

                        metadata={

                            'vwap': current_vwap,

                            'distance_from_vwap': (event.close - current_vwap) / current_vwap

                        }

                    )





            if position > 0 and event.close > current_vwap:

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='EXIT',

                    price=event.close,

                    metadata={'vwap': current_vwap, 'reason': 'vwap_reversion'}

                )

            elif position < 0 and event.close < current_vwap:

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='EXIT',

                    price=event.close,

                    metadata={'vwap': current_vwap, 'reason': 'vwap_reversion'}

                )



        else:



            if event.close > current_upper and event.open < current_upper:

                if position <= 0:

                    return self.generate_signal(

                        symbol=event.symbol,

                        signal_type='LONG',

                        price=event.close,

                        strength=1.0,

                        metadata={'vwap': current_vwap, 'breakout': 'upper'}

                    )



            elif event.close < current_lower and event.open > current_lower:

                if position >= 0:

                    return self.generate_signal(

                        symbol=event.symbol,

                        signal_type='SHORT',

                        price=event.close,

                        strength=1.0,

                        metadata={'vwap': current_vwap, 'breakout': 'lower'}

                    )



        return None





class AnchoredVWAPStrategy(Strategy):

    """
    Anchored VWAP Strategy
    VWAP calculated from a specific anchor point (e.g., earnings, highs, lows)
    """



    def __init__(

        self,

        symbols: list = None,

        anchor_lookback: int = 20,

        band_mult: float = 2.0

    ):

        config = StrategyConfig(

            name="AnchoredVWAPStrategy",

            symbols=symbols,

        )

        super().__init__(config)



        self.anchor_lookback = anchor_lookback

        self.band_mult = band_mult

        self.anchor_points = {}



    def find_anchor(self, data: pd.DataFrame) -> int:

        """Find anchor point - highest high in lookback"""

        if len(data) < self.anchor_lookback:

            return 0



        recent_highs = data['high'].iloc[-self.anchor_lookback:]

        anchor_idx = recent_highs.idxmax()

        return anchor_idx



    def calculate_anchored_vwap(

        self,

        data: pd.DataFrame,

        anchor_idx: int

    ) -> pd.Series:

        """Calculate VWAP from anchor point"""

        from_anchor = data.iloc[anchor_idx:]



        typical_price = (from_anchor['high'] + from_anchor['low'] + from_anchor['close']) / 3

        vwap = (typical_price * from_anchor['volume']).cumsum() / from_anchor['volume'].cumsum()





        vwap_full = pd.Series(index=data.index, dtype=float)

        vwap_full.iloc[anchor_idx:] = vwap.values

        vwap_full.iloc[:anchor_idx] = vwap.iloc[0]



        return vwap_full



    def on_market_data(self, event: MarketEvent) -> Optional[SignalEvent]:

        """Generate anchored VWAP signals"""

        self.update_data(event)



        data = self.data_history.get(event.symbol)

        if data is None or len(data) < self.anchor_lookback:

            return None





        anchor_idx = self.find_anchor(data)





        vwap = self.calculate_anchored_vwap(data, anchor_idx)



        current_vwap = vwap.iloc[-1]





        deviation = (event.close - current_vwap) / current_vwap * 100



        position = self.get_position(event.symbol)





        if deviation < -self.band_mult and event.close > event.open:

            if position <= 0:

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='LONG',

                    price=event.close,

                    strength=1.0,

                    metadata={'avwap': current_vwap, 'deviation': deviation}

                )





        elif deviation > self.band_mult and event.close < event.open:

            if position >= 0:

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='SHORT',

                    price=event.close,

                    strength=1.0,

                    metadata={'avwap': current_vwap, 'deviation': deviation}

                )



        return None
