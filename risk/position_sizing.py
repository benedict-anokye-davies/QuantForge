"""
Position Sizing - Kelly Criterion, Fixed Fractional, Volatility Targeting
"""



from abc import ABC, abstractmethod

from typing import Optional, Dict, Any, TYPE_CHECKING

from dataclasses import dataclass

import numpy as np



from ..core.events import SignalEvent



if TYPE_CHECKING:

    from ..core.portfolio import Position





class PositionSizer(ABC):

    """Abstract base class for position sizing"""



    @abstractmethod

    def calculate_position_size(

        self,

        signal: SignalEvent,

        equity: float,

        current_price: float,

        existing_position: Optional[Any] = None,

        **kwargs

    ) -> float:

        """Calculate position size in units"""

        pass





@dataclass

class KellyCriterion(PositionSizer):

    """
    Kelly Criterion position sizing
    f* = (p*b - q) / b
    where p = win probability, b = win/loss ratio, q = 1-p
    """



    win_rate: float = 0.5

    win_loss_ratio: float = 1.5

    kelly_fraction: float = 0.25

    max_position_pct: float = 0.20



    def __post_init__(self):

        self.q = 1 - self.win_rate



    def calculate_kelly_fraction(self) -> float:

        """Calculate full Kelly fraction"""

        if self.win_loss_ratio <= 0:

            return 0.0

        kelly = (self.win_rate * self.win_loss_ratio - self.q) / self.win_loss_ratio

        return max(0.0, kelly)



    def calculate_position_size(

        self,

        signal: SignalEvent,

        equity: float,

        current_price: float,

        existing_position: Optional[Any] = None,

        **kwargs

    ) -> float:

        """Calculate position size using Kelly Criterion"""

        kelly = self.calculate_kelly_fraction()

        adjusted_kelly = kelly * self.kelly_fraction





        position_value = equity * min(adjusted_kelly, self.max_position_pct)





        if current_price <= 0:

            return 0.0



        quantity = position_value / current_price





        quantity *= signal.strength



        return quantity



    def update_from_trades(self, trades: list):

        """Update Kelly parameters from historical trades"""

        if not trades or len(trades) < 10:

            return



        wins = [t for t in trades if t.get('pnl', 0) > 0]

        losses = [t for t in trades if t.get('pnl', 0) < 0]



        if not wins or not losses:

            return



        self.win_rate = len(wins) / len(trades)



        avg_win = np.mean([t.get('pnl', 0) for t in wins])

        avg_loss = abs(np.mean([t.get('pnl', 0) for t in losses]))



        if avg_loss > 0:

            self.win_loss_ratio = avg_win / avg_loss





@dataclass

class FixedFractional(PositionSizer):

    """
    Fixed fractional position sizing
    Risk fixed percentage of equity per trade
    """



    risk_per_trade_pct: float = 0.02

    max_position_pct: float = 0.20

    atr_multiplier: float = 2.0



    def calculate_position_size(

        self,

        signal: SignalEvent,

        equity: float,

        current_price: float,

        existing_position: Optional[Any] = None,

        stop_loss: Optional[float] = None,

        atr: Optional[float] = None,

        **kwargs

    ) -> float:

        """Calculate position size based on risk amount"""



        if stop_loss and stop_loss > 0:

            stop_distance = abs(current_price - stop_loss) / current_price

        elif atr and atr > 0:

            stop_distance = (atr * self.atr_multiplier) / current_price

        else:



            stop_distance = 0.05





        risk_amount = equity * self.risk_per_trade_pct





        position_value = risk_amount / stop_distance if stop_distance > 0 else 0





        max_position_value = equity * self.max_position_pct

        position_value = min(position_value, max_position_value)





        if current_price <= 0:

            return 0.0



        quantity = position_value / current_price

        quantity *= signal.strength



        return quantity





@dataclass

class VolatilityTargeting(PositionSizer):

    """
    Volatility targeting position sizing
    Target constant portfolio volatility
    """



    target_volatility: float = 0.15

    lookback_periods: int = 20

    max_leverage: float = 2.0

    min_position_pct: float = 0.01



    def __init__(self, **kwargs):

        super().__init__(**kwargs)

        self.volatility_history: list = []



    def calculate_position_size(

        self,

        signal: SignalEvent,

        equity: float,

        current_price: float,

        existing_position: Optional[Any] = None,

        returns: Optional[list] = None,

        **kwargs

    ) -> float:

        """Calculate position size based on volatility targeting"""

        if returns is None or len(returns) < self.lookback_periods:



            return (equity * 0.5) / current_price if current_price > 0 else 0





        recent_returns = returns[-self.lookback_periods:]

        realized_vol = np.std(recent_returns) * np.sqrt(252)



        if realized_vol <= 0:

            return 0.0







        vol_scalar = self.target_volatility / realized_vol





        vol_scalar = min(vol_scalar, self.max_leverage)

        vol_scalar = max(vol_scalar, 0)





        position_value = equity * vol_scalar





        if position_value < equity * self.min_position_pct:

            return 0.0





        if current_price <= 0:

            return 0.0



        quantity = position_value / current_price

        quantity *= signal.strength



        return quantity





@dataclass

class OptimalF(PositionSizer):

    """
    Ralph Vince's Optimal f
    Maximizes geometric growth rate
    """



    max_loss_pct: float = 0.10

    optimal_f: float = 0.25



    def calculate_position_size(

        self,

        signal: SignalEvent,

        equity: float,

        current_price: float,

        existing_position: Optional[Any] = None,

        trade_history: Optional[list] = None,

        **kwargs

    ) -> float:

        """Calculate position size using Optimal f"""

        if trade_history:

            self.optimal_f = self._calculate_optimal_f(trade_history)





        dollar_per_unit = self.max_loss_pct / self.optimal_f if self.optimal_f > 0 else 0



        if dollar_per_unit <= 0:

            return 0.0





        units = (equity * self.optimal_f) / dollar_per_unit

        units *= signal.strength



        return units



    def _calculate_optimal_f(self, trades: list) -> float:

        """Calculate Optimal f from trade history"""

        if not trades:

            return self.optimal_f



        returns = [t.get('return_pct', 0) for t in trades]





        best_f = 0.0

        best_g = 0.0



        for f in np.linspace(0.01, 1.0, 100):

            hpr = [1 + f * r for r in returns]

            if any(h <= 0 for h in hpr):

                continue



            g_mean = np.exp(np.mean(np.log(hpr)))



            if g_mean > best_g:

                best_g = g_mean

                best_f = f



        return best_f * 0.5





class RiskParity(PositionSizer):

    """
    Risk parity position sizing
    Equal risk contribution from each position
    """



    def __init__(self, target_risk_per_asset: float = 0.05):

        self.target_risk_per_asset = target_risk_per_asset



    def calculate_position_size(

        self,

        signal: SignalEvent,

        equity: float,

        current_price: float,

        existing_position: Optional[Any] = None,

        volatility: Optional[float] = None,

        correlations: Optional[Dict] = None,

        **kwargs

    ) -> float:

        """Calculate position size for risk parity"""

        if volatility is None or volatility <= 0:

            return 0.0





        target_vol = self.target_risk_per_asset





        if correlations:



            avg_corr = np.mean(list(correlations.values())) if correlations else 0

            target_vol *= (1 + (1 - avg_corr))





        position_pct = target_vol / volatility

        position_value = equity * position_pct



        if current_price <= 0:

            return 0.0



        quantity = position_value / current_price

        quantity *= signal.strength



        return quantity
