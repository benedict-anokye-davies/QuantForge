"""
Portfolio Management - Position tracking, P&L calculation, risk exposure
"""



from dataclasses import dataclass, field

from typing import Dict, List, Optional, Tuple

from datetime import datetime

from collections import defaultdict

import numpy as np

import pandas as pd



from .events import FillEvent, SignalEvent, OrderEvent, RiskEvent

from ..risk.position_sizing import PositionSizer, FixedFractional

from ..risk.risk_manager import RiskManager





@dataclass

class Position:

    """Represents a single position in a security"""

    symbol: str

    quantity: float = 0.0

    avg_entry_price: float = 0.0

    unrealized_pnl: float = 0.0

    realized_pnl: float = 0.0

    timestamp: datetime = field(default_factory=datetime.now)



    @property

    def market_value(self, current_price: float = 0.0) -> float:

        return self.quantity * current_price



    @property

    def is_long(self) -> bool:

        return self.quantity > 0



    @property

    def is_short(self) -> bool:

        return self.quantity < 0



    @property

    def is_flat(self) -> bool:

        return self.quantity == 0



    def update_unrealized_pnl(self, current_price: float):

        """Update unrealized P&L based on current market price"""

        if self.quantity != 0:

            self.unrealized_pnl = self.quantity * (current_price - self.avg_entry_price)



    def add_fill(self, fill: FillEvent):

        """Process a new fill and update position"""

        if self.is_flat:



            self.avg_entry_price = fill.fill_price

            self.quantity = fill.quantity if fill.direction == 'BUY' else -fill.quantity

        elif (self.is_long and fill.direction == 'BUY') or (self.is_short and fill.direction == 'SELL'):



            current_value = abs(self.quantity) * self.avg_entry_price

            new_value = fill.quantity * fill.fill_price

            total_qty = abs(self.quantity) + fill.quantity

            self.avg_entry_price = (current_value + new_value) / total_qty

            self.quantity += fill.quantity if fill.direction == 'BUY' else -fill.quantity

        else:



            if fill.quantity > abs(self.quantity):



                realized = abs(self.quantity) * (fill.fill_price - self.avg_entry_price)

                if self.is_short:

                    realized = -realized

                self.realized_pnl += realized



                remaining = fill.quantity - abs(self.quantity)

                self.quantity = remaining if fill.direction == 'BUY' else -remaining

                self.avg_entry_price = fill.fill_price

            else:



                realized = fill.quantity * (fill.fill_price - self.avg_entry_price)

                if self.is_short:

                    realized = -realized

                self.realized_pnl += realized

                self.quantity += fill.quantity if fill.direction == 'SELL' else -fill.quantity



        self.timestamp = fill.timestamp





class Portfolio:

    """
    Portfolio manager - tracks positions, cash, generates orders
    """



    def __init__(

        self,

        initial_capital: float = 100000.0,

        position_sizer: Optional[PositionSizer] = None,

        risk_manager: Optional[RiskManager] = None,

        commission_model: str = "percentage",

        commission_value: float = 0.001,

    ):

        self.initial_capital = initial_capital

        self.cash = initial_capital

        self.equity = initial_capital





        self.positions: Dict[str, Position] = {}

        self.closed_trades: List[Dict] = []





        self.position_sizer = position_sizer or FixedFractional()

        self.risk_manager = risk_manager or RiskManager()





        self.commission_model = commission_model

        self.commission_value = commission_value





        self.equity_curve: List[Tuple[datetime, float]] = []

        self.orders_generated: List[OrderEvent] = []



    @property

    def total_value(self) -> float:

        """Total portfolio value (cash + positions)"""

        position_value = sum(

            pos.quantity * pos.avg_entry_price

            for pos in self.positions.values()

        )

        return self.cash + position_value



    @property

    def total_pnl(self) -> float:

        """Total realized P&L"""

        return sum(pos.realized_pnl for pos in self.positions.values())



    @property

    def open_positions_count(self) -> int:

        """Number of non-flat positions"""

        return sum(1 for pos in self.positions.values() if not pos.is_flat)



    def get_position(self, symbol: str) -> Position:

        """Get or create position for symbol"""

        if symbol not in self.positions:

            self.positions[symbol] = Position(symbol=symbol)

        return self.positions[symbol]



    def update_market_data(self, symbol: str, price: float, timestamp: datetime):

        """Update position P&L with latest market price"""

        if symbol in self.positions:

            self.positions[symbol].update_unrealized_pnl(price)

            self._update_equity(timestamp)



    def _update_equity(self, timestamp: datetime):

        """Update total equity value"""

        self.equity = self.total_value

        self.equity_curve.append((timestamp, self.equity))



    def calculate_commission(self, quantity: float, price: float) -> float:

        """Calculate commission for a trade"""

        notional = quantity * price

        if self.commission_model == "percentage":

            return notional * self.commission_value

        elif self.commission_model == "fixed":

            return self.commission_value

        elif self.commission_model == "tiered":



            if notional < 10000:

                return notional * 0.001

            elif notional < 100000:

                return notional * 0.0008

            else:

                return notional * 0.0005

        return 0.0



    def on_signal(self, signal: SignalEvent, current_price: float) -> Optional[OrderEvent]:

        """
        Process trading signal and generate order
        """



        risk_event = self.risk_manager.check_signal(

            signal, self.positions, self.equity, self.cash

        )

        if risk_event and risk_event.action_required:

            return None





        position = self.get_position(signal.symbol)





        if signal.is_exit:

            if not position.is_flat:

                return OrderEvent(

                    symbol=signal.symbol,

                    order_type="MARKET",

                    direction="SELL" if position.is_long else "BUY",

                    quantity=abs(position.quantity),

                    price=current_price,

                    timestamp=signal.timestamp,

                    strategy_id=signal.strategy_id

                )

            return None





        target_quantity = self.position_sizer.calculate_position_size(

            signal=signal,

            equity=self.equity,

            current_price=current_price,

            existing_position=position

        )





        direction = "BUY" if signal.is_long else "SELL"





        current_qty = position.quantity

        if signal.is_long:

            target_quantity = abs(target_quantity)

        else:

            target_quantity = -abs(target_quantity)



        delta = target_quantity - current_qty





        if abs(delta) < 0.0001:

            return None



        order_direction = "BUY" if delta > 0 else "SELL"

        order_quantity = abs(delta)





        required_cash = order_quantity * current_price * 1.01

        if order_direction == "BUY" and required_cash > self.cash:



            order_quantity = int(self.cash / (current_price * 1.01))

            if order_quantity < 1:

                return None



        order = OrderEvent(

            symbol=signal.symbol,

            order_type="MARKET",

            direction=order_direction,

            quantity=order_quantity,

            price=current_price,

            timestamp=signal.timestamp,

            strategy_id=signal.strategy_id

        )



        self.orders_generated.append(order)

        return order



    def on_fill(self, fill: FillEvent):

        """Process fill event and update portfolio state"""



        position = self.get_position(fill.symbol)

        position.add_fill(fill)





        fill_cost = fill.fill_price * fill.quantity + fill.commission

        if fill.direction == "BUY":

            self.cash -= fill_cost

        else:

            self.cash += fill_cost - fill.commission





        if position.is_flat and position.realized_pnl != 0:

            self.closed_trades.append({

                'symbol': fill.symbol,

                'exit_time': fill.timestamp,

                'realized_pnl': position.realized_pnl,

                'exit_price': fill.fill_price,

            })



        self._update_equity(fill.timestamp)



    def get_portfolio_stats(self) -> Dict:

        """Get current portfolio statistics"""

        return {

            'cash': self.cash,

            'equity': self.equity,

            'total_pnl': self.total_pnl,

            'open_positions': self.open_positions_count,

            'total_trades': len(self.closed_trades),

            'winning_trades': sum(1 for t in self.closed_trades if t['realized_pnl'] > 0),

            'losing_trades': sum(1 for t in self.closed_trades if t['realized_pnl'] < 0),

        }



    def get_equity_dataframe(self) -> pd.DataFrame:

        """Get equity curve as DataFrame"""

        if not self.equity_curve:

            return pd.DataFrame()



        df = pd.DataFrame(self.equity_curve, columns=['timestamp', 'equity'])

        df.set_index('timestamp', inplace=True)

        df['returns'] = df['equity'].pct_change()

        return df
