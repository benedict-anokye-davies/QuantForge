"""
Base Strategy Class
All strategies must inherit from this
"""



from abc import ABC, abstractmethod

from typing import Optional, Dict, Any, List

from dataclasses import dataclass

import pandas as pd



from ..core.events import MarketEvent, SignalEvent, FillEvent





@dataclass

class StrategyConfig:

    """Strategy configuration"""

    name: str = "BaseStrategy"

    symbols: List[str] = None

    timeframe: str = "1d"

    max_positions: int = 10



    def __post_init__(self):

        if self.symbols is None:

            self.symbols = []





class Strategy(ABC):

    """
    Abstract base class for all trading strategies

    Event-driven architecture:
    1. on_market_data() - Process new market data, generate signals
    2. on_fill() - Process fill events, update state
    3. should_process() - Check if strategy should process this symbol
    """



    def __init__(self, config: Optional[StrategyConfig] = None):

        self.config = config or StrategyConfig()

        self.name = self.config.name

        self.symbols = self.config.symbols





        self.is_active = True

        self.data_history: Dict[str, pd.DataFrame] = {}

        self.current_positions: Dict[str, float] = {}

        self.engine = None





        self.signals_generated = 0

        self.trades_taken = 0



    def set_engine(self, engine):

        """Set reference to backtest engine"""

        self.engine = engine



    def should_process(self, symbol: str) -> bool:

        """Check if strategy should process this symbol"""

        if not self.is_active:

            return False

        if not self.symbols:

            return True

        return symbol in self.symbols



    @abstractmethod

    def on_market_data(self, event: MarketEvent) -> Optional[SignalEvent]:

        """
        Process market data and generate trading signal

        Args:
            event: MarketEvent with OHLCV data

        Returns:
            SignalEvent if signal generated, None otherwise
        """

        pass



    def on_fill(self, event: FillEvent):

        """
        Process fill event - update position tracking

        Args:
            event: FillEvent with execution details
        """

        qty = event.quantity if event.direction == 'BUY' else -event.quantity



        if event.symbol not in self.current_positions:

            self.current_positions[event.symbol] = 0



        self.current_positions[event.symbol] += qty

        self.trades_taken += 1



    def update_data(self, event: MarketEvent):

        """Update internal data history"""

        if event.symbol not in self.data_history:

            self.data_history[event.symbol] = pd.DataFrame()



        new_row = pd.DataFrame([{

            'timestamp': event.timestamp,

            'open': event.open,

            'high': event.high,

            'low': event.low,

            'close': event.close,

            'volume': event.volume,

        }])



        self.data_history[event.symbol] = pd.concat(

            [self.data_history[event.symbol], new_row],

            ignore_index=True

        )





        if len(self.data_history[event.symbol]) > 500:

            self.data_history[event.symbol] = self.data_history[event.symbol].iloc[-500:]



    def get_data(self, symbol: str, lookback: int = 50) -> pd.DataFrame:

        """Get recent data for symbol"""

        if symbol not in self.data_history:

            return pd.DataFrame()



        return self.data_history[symbol].iloc[-lookback:]



    def get_position(self, symbol: str) -> float:

        """Get current position for symbol"""

        return self.current_positions.get(symbol, 0)



    def is_flat(self, symbol: str) -> bool:

        """Check if flat (no position) for symbol"""

        return abs(self.get_position(symbol)) < 0.0001



    def is_long(self, symbol: str) -> bool:

        """Check if long position"""

        return self.get_position(symbol) > 0



    def is_short(self, symbol: str) -> bool:

        """Check if short position"""

        return self.get_position(symbol) < 0



    def generate_signal(

        self,

        symbol: str,

        signal_type: str,

        price: float,

        strength: float = 1.0,

        confidence: float = 0.5,

        metadata: Optional[Dict] = None

    ) -> SignalEvent:

        """Helper to generate signal event"""

        self.signals_generated += 1



        return SignalEvent(

            symbol=symbol,

            signal_type=signal_type,

            strength=strength,

            strategy_id=self.name,

            price=price,

            confidence=confidence,

            metadata=metadata or {}

        )



    def get_stats(self) -> Dict[str, Any]:

        """Get strategy statistics"""

        return {

            'name': self.name,

            'signals_generated': self.signals_generated,

            'trades_taken': self.trades_taken,

            'is_active': self.is_active,

            'symbols_tracked': len(self.data_history),

        }



    def reset(self):

        """Reset strategy state"""

        self.data_history.clear()

        self.current_positions.clear()

        self.signals_generated = 0

        self.trades_taken = 0

        self.is_active = True
