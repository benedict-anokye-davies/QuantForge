"""
Kill Switch and Circuit Breakers - Emergency risk controls
"""



from typing import Optional, Callable, List

from dataclasses import dataclass, field

from datetime import datetime, timedelta

from enum import Enum





class KillSwitchState(Enum):

    """Kill switch states"""

    ARMED = "armed"

    TRIGGERED = "triggered"

    DISARMED = "disarmed"

    COOLDOWN = "cooldown"





@dataclass

class KillSwitch:

    """
    Kill switch - emergency stop for all trading
    """



    max_drawdown_pct: float = 0.30

    max_daily_loss_pct: float = 0.10

    max_consecutive_errors: int = 10



    state: KillSwitchState = KillSwitchState.ARMED

    triggered_at: Optional[datetime] = None

    trigger_reason: str = ""





    daily_pnl: float = 0.0

    consecutive_errors: int = 0

    peak_equity: float = 0.0





    on_trigger: Optional[Callable] = None



    def __post_init__(self):

        self._callbacks: List[Callable] = []



    def check(

        self,

        equity: float,

        daily_pnl: Optional[float] = None,

        error_occurred: bool = False

    ) -> bool:

        """
        Check if kill switch should trigger
        Returns True if trading should stop
        """

        if self.state == KillSwitchState.DISARMED:

            return False



        if self.state == KillSwitchState.TRIGGERED:

            return True





        self.peak_equity = max(self.peak_equity, equity)



        if daily_pnl is not None:

            self.daily_pnl = daily_pnl



        if error_occurred:

            self.consecutive_errors += 1

        else:

            self.consecutive_errors = 0





        if self.peak_equity > 0:

            drawdown = (self.peak_equity - equity) / self.peak_equity

            if drawdown >= self.max_drawdown_pct:

                self._trigger(f"Max drawdown reached: {drawdown:.1%}")

                return True





        if self.daily_pnl <= -self.max_daily_loss_pct:

            self._trigger(f"Max daily loss reached: {self.daily_pnl:.1%}")

            return True





        if self.consecutive_errors >= self.max_consecutive_errors:

            self._trigger(f"Too many consecutive errors: {self.consecutive_errors}")

            return True



        return False



    def _trigger(self, reason: str):

        """Trigger the kill switch"""

        self.state = KillSwitchState.TRIGGERED

        self.triggered_at = datetime.now()

        self.trigger_reason = reason





        if self.on_trigger:

            self.on_trigger(reason)



        for callback in self._callbacks:

            callback(reason)



    def reset(self, after_minutes: int = 60):

        """Reset kill switch after cooldown"""

        if self.state == KillSwitchState.TRIGGERED:

            if self.triggered_at:

                elapsed = datetime.now() - self.triggered_at

                if elapsed >= timedelta(minutes=after_minutes):

                    self.state = KillSwitchState.ARMED

                    self.triggered_at = None

                    self.trigger_reason = ""

                    self.daily_pnl = 0.0

                    self.consecutive_errors = 0



    def disarm(self):

        """Manually disarm kill switch"""

        self.state = KillSwitchState.DISARMED



    def arm(self):

        """Re-arm kill switch"""

        self.state = KillSwitchState.ARMED

        self.triggered_at = None

        self.trigger_reason = ""



    def register_callback(self, callback: Callable):

        """Register callback for trigger event"""

        self._callbacks.append(callback)



    def get_status(self) -> dict:

        """Get kill switch status"""

        return {

            'state': self.state.value,

            'is_active': self.state == KillSwitchState.ARMED,

            'is_triggered': self.state == KillSwitchState.TRIGGERED,

            'trigger_reason': self.trigger_reason,

            'triggered_at': self.triggered_at.isoformat() if self.triggered_at else None,

            'peak_equity': self.peak_equity,

            'daily_pnl': self.daily_pnl,

            'consecutive_errors': self.consecutive_errors,

        }





@dataclass

class CircuitBreaker:

    """
    Circuit breaker - temporary trading halt on volatility spikes
    """



    volatility_threshold: float = 0.05

    consecutive_hits: int = 3

    cooldown_minutes: int = 15



    hits: int = 0

    last_hit: Optional[datetime] = None

    is_open: bool = False



    def check(self, price_change_pct: float) -> bool:

        """
        Check if circuit breaker should trigger
        Returns True if trading should halt
        """

        now = datetime.now()





        if self.last_hit and (now - self.last_hit) > timedelta(minutes=5):

            self.hits = 0





        if abs(price_change_pct) >= self.volatility_threshold:

            self.hits += 1

            self.last_hit = now



            if self.hits >= self.consecutive_hits:

                self.is_open = True

                return True





        if self.is_open:

            if self.last_hit and (now - self.last_hit) > timedelta(minutes=self.cooldown_minutes):

                self.is_open = False

                self.hits = 0



        return self.is_open



    def manual_reset(self):

        """Manually reset circuit breaker"""

        self.is_open = False

        self.hits = 0

        self.last_hit = None



    def get_status(self) -> dict:

        """Get circuit breaker status"""

        return {

            'is_open': self.is_open,

            'hits': self.hits,

            'last_hit': self.last_hit.isoformat() if self.last_hit else None,

            'threshold_pct': self.volatility_threshold * 100,

        }
