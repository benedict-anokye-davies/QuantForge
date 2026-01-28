"""
Risk Manager - Portfolio-level risk controls
"""



from abc import ABC, abstractmethod

from typing import List, Dict, Optional, Any, TYPE_CHECKING

from dataclasses import dataclass

from datetime import datetime

import numpy as np



from ..core.events import SignalEvent, RiskEvent



if TYPE_CHECKING:

    from ..core.portfolio import Position





class RiskRule(ABC):

    """Abstract base class for risk rules"""



    @abstractmethod

    def check(

        self,

        signal: SignalEvent,

        positions: Dict[str, Any],

        equity: float,

        cash: float,

        **kwargs

    ) -> Optional[RiskEvent]:

        """Check if risk rule is violated"""

        pass





@dataclass

class PositionLimitRule(RiskRule):

    """Maximum position size limit"""



    max_position_pct: float = 0.20

    max_total_exposure: float = 2.0



    def check(

        self,

        signal: SignalEvent,

        positions: Dict[str, Any],

        equity: float,

        cash: float,

        current_price: float = 0.0,

        **kwargs

    ) -> Optional[RiskEvent]:

        """Check position limits"""



        position_value = 0

        if signal.symbol in positions:

            position_value = abs(positions[signal.symbol].quantity * current_price)



        position_pct = position_value / equity if equity > 0 else 0



        if position_pct > self.max_position_pct:

            return RiskEvent(

                risk_type="POSITION_LIMIT",

                severity="WARNING",

                message=f"Position {signal.symbol} exceeds {self.max_position_pct*100}% limit",

                action_required=True

            )





        total_exposure = sum(

            abs(pos.quantity * current_price)

            for pos in positions.values()

        ) / equity if equity > 0 else 0



        if total_exposure > self.max_total_exposure:

            return RiskEvent(

                risk_type="POSITION_LIMIT",

                severity="CRITICAL",

                message=f"Total exposure {total_exposure:.1%} exceeds limit",

                action_required=True

            )



        return None





@dataclass

class DrawdownRule(RiskRule):

    """Drawdown protection rule"""



    warning_drawdown: float = 0.10

    critical_drawdown: float = 0.20

    max_drawdown: float = 0.30



    equity_history: List[float] = None



    def __post_init__(self):

        if self.equity_history is None:

            self.equity_history = []



    def check(

        self,

        signal: SignalEvent,

        positions: Dict[str, Any],

        equity: float,

        cash: float,

        **kwargs

    ) -> Optional[RiskEvent]:

        """Check drawdown levels"""

        if not self.equity_history:

            return None



        peak = max(self.equity_history)

        if peak <= 0:

            return None



        drawdown = (peak - equity) / peak



        if drawdown >= self.max_drawdown:

            return RiskEvent(

                risk_type="DRAWDOWN",

                severity="KILL_SWITCH",

                message=f"Max drawdown {drawdown:.1%} reached - stopping trading",

                action_required=True

            )

        elif drawdown >= self.critical_drawdown:

            return RiskEvent(

                risk_type="DRAWDOWN",

                severity="CRITICAL",

                message=f"Critical drawdown {drawdown:.1%} - reduce positions",

                action_required=True

            )

        elif drawdown >= self.warning_drawdown:

            return RiskEvent(

                risk_type="DRAWDOWN",

                severity="WARNING",

                message=f"Warning: Drawdown at {drawdown:.1%}",

                action_required=False

            )



        return None



    def update_equity(self, equity: float):

        """Update equity history"""

        self.equity_history.append(equity)





@dataclass

class CorrelationRule(RiskRule):

    """Correlation risk rule - prevent concentration in correlated assets"""



    max_correlation: float = 0.70

    correlation_matrix: Dict[str, Dict[str, float]] = None



    def __post_init__(self):

        if self.correlation_matrix is None:

            self.correlation_matrix = {}



    def check(

        self,

        signal: SignalEvent,

        positions: Dict[str, Any],

        equity: float,

        cash: float,

        **kwargs

    ) -> Optional[RiskEvent]:

        """Check correlation risk"""

        if signal.symbol not in self.correlation_matrix:

            return None





        for symbol, position in positions.items():

            if position.is_flat:

                continue



            if symbol in self.correlation_matrix.get(signal.symbol, {}):

                corr = self.correlation_matrix[signal.symbol][symbol]



                if abs(corr) > self.max_correlation:

                    return RiskEvent(

                        risk_type="CORRELATION",

                        severity="WARNING",

                        message=f"High correlation ({corr:.2f}) between {signal.symbol} and {symbol}",

                        action_required=False

                    )



        return None





@dataclass

class VolatilityRule(RiskRule):

    """Volatility-based risk rule"""



    max_portfolio_volatility: float = 0.25

    vol_lookback: int = 20



    returns_history: List[float] = None



    def __post_init__(self):

        if self.returns_history is None:

            self.returns_history = []



    def check(

        self,

        signal: SignalEvent,

        positions: Dict[str, Any],

        equity: float,

        cash: float,

        **kwargs

    ) -> Optional[RiskEvent]:

        """Check portfolio volatility"""

        if len(self.returns_history) < self.vol_lookback:

            return None



        recent_returns = self.returns_history[-self.vol_lookback:]

        portfolio_vol = np.std(recent_returns) * np.sqrt(252)



        if portfolio_vol > self.max_portfolio_volatility:

            return RiskEvent(

                risk_type="VOLATILITY",

                severity="WARNING",

                message=f"Portfolio volatility {portfolio_vol:.1%} exceeds limit",

                action_required=True

            )



        return None



    def update_returns(self, returns: float):

        """Update returns history"""

        self.returns_history.append(returns)





@dataclass

class ConsecutiveLossRule(RiskRule):

    """Rule for consecutive losses"""



    max_consecutive_losses: int = 5

    cooldown_periods: int = 10



    trade_history: List[bool] = None



    def __post_init__(self):

        if self.trade_history is None:

            self.trade_history = []



    def check(

        self,

        signal: SignalEvent,

        positions: Dict[str, Any],

        equity: float,

        cash: float,

        **kwargs

    ) -> Optional[RiskEvent]:

        """Check for consecutive losses"""

        if not self.trade_history:

            return None





        consecutive_losses = 0

        for is_win in reversed(self.trade_history):

            if not is_win:

                consecutive_losses += 1

            else:

                break



        if consecutive_losses >= self.max_consecutive_losses:

            return RiskEvent(

                risk_type="CONSECUTIVE_LOSSES",

                severity="WARNING",

                message=f"{consecutive_losses} consecutive losses - taking cooldown",

                action_required=True

            )



        return None



    def add_trade(self, is_win: bool):

        """Add trade result"""

        self.trade_history.append(is_win)





class RiskManager:

    """
    Main risk manager - coordinates all risk rules
    """



    def __init__(self, rules: Optional[List[RiskRule]] = None):

        self.rules = rules or []

        self.risk_events: List[RiskEvent] = []

        self.is_active = True



    def add_rule(self, rule: RiskRule):

        """Add a risk rule"""

        self.rules.append(rule)



    def check_signal(

        self,

        signal: SignalEvent,

        positions: Dict[str, Any],

        equity: float,

        cash: float,

        **kwargs

    ) -> Optional[RiskEvent]:

        """Check signal against all risk rules"""

        if not self.is_active:

            return RiskEvent(

                risk_type="SYSTEM",

                severity="CRITICAL",

                message="Risk manager deactivated",

                action_required=True

            )



        for rule in self.rules:

            risk_event = rule.check(signal, positions, equity, cash, **kwargs)

            if risk_event:

                self.risk_events.append(risk_event)



                if risk_event.severity == "KILL_SWITCH":

                    self.is_active = False



                return risk_event



        return None



    def update_state(self, equity: float, returns: float):

        """Update risk manager state"""

        for rule in self.rules:

            if isinstance(rule, DrawdownRule):

                rule.update_equity(equity)

            elif isinstance(rule, VolatilityRule):

                rule.update_returns(returns)



    def get_risk_summary(self) -> Dict:

        """Get summary of risk status"""

        return {

            'is_active': self.is_active,

            'total_risk_events': len(self.risk_events),

            'critical_events': sum(1 for e in self.risk_events if e.severity == "CRITICAL"),

            'warning_events': sum(1 for e in self.risk_events if e.severity == "WARNING"),

        }
