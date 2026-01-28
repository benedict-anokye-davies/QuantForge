"""
Portfolio Module

Tracks portfolio state including positions, cash, equity curve,
and PnL calculations. Handles FillEvents to update positions
and compute realized/unrealized PnL.
"""



from __future__ import annotations



from dataclasses import dataclass, field

from datetime import datetime

from typing import Dict, List, Optional, Tuple



import pandas as pd

import numpy as np



from quantforge.core.events import EventBus, EventType, FillEvent, MarketDataEvent, Event





@dataclass

class Position:

    """
    Represents a position in a single instrument.

    Tracks quantity, average entry price, and realized PnL for the position.
    Supports both long and short positions.

    Attributes:
        symbol: Trading symbol
        quantity: Number of shares/contracts (positive=long, negative=short)
        avg_entry_price: Weighted average entry price
        realized_pnl: Realized profit/loss from closed portions
        opened_at: Timestamp when position was first opened
    """

    symbol: str

    quantity: int = 0

    avg_entry_price: float = 0.0

    realized_pnl: float = 0.0

    opened_at: Optional[datetime] = None



    def __post_init__(self) -> None:

        """Validate position state."""

        if not self.symbol:

            raise ValueError("symbol cannot be empty")



    @property

    def is_long(self) -> bool:

        """True if this is a long position."""

        return self.quantity > 0



    @property

    def is_short(self) -> bool:

        """True if this is a short position."""

        return self.quantity < 0



    @property

    def is_flat(self) -> bool:

        """True if position is flat (zero quantity)."""

        return self.quantity == 0



    def market_value(self, current_price: float) -> float:

        """
        Calculate market value of position at given price.

        For long positions: positive value
        For short positions: negative value (liability)
        """

        return self.quantity * current_price



    def abs_market_value(self, current_price: float) -> float:

        """Absolute market value (always positive)."""

        return abs(self.quantity) * current_price



    def update_from_fill(self, fill: FillEvent) -> None:

        """
        Update position based on a fill event.

        This method handles:
        - Opening new positions
        - Adding to existing positions (averaging entry price)
        - Reducing positions (realizing PnL)
        - Flipping positions (short to long or vice versa)

        Note: Commission is NOT deducted here because it's already
        deducted from cash in Portfolio._on_fill(). Position's realized_pnl
        tracks only trading gains/losses, not transaction costs.

        Args:
            fill: The fill event to process
        """

        if fill.symbol != self.symbol:

            raise ValueError(f"Fill symbol {fill.symbol} != position symbol {self.symbol}")



        fill_qty = fill.quantity

        fill_price = fill.fill_price





        if self.quantity == 0:

            self.quantity = fill_qty

            self.avg_entry_price = fill_price

            self.opened_at = fill.timestamp

            return





        if (self.quantity > 0 and fill_qty > 0) or (self.quantity < 0 and fill_qty < 0):



            current_value = self.quantity * self.avg_entry_price

            fill_value = fill_qty * fill_price

            self.avg_entry_price = (current_value + fill_value) / (self.quantity + fill_qty)

            self.quantity += fill_qty

            return





        if abs(fill_qty) < abs(self.quantity):



            close_qty = abs(fill_qty)

            if self.quantity > 0:

                pnl = close_qty * (fill_price - self.avg_entry_price)

            else:

                pnl = close_qty * (self.avg_entry_price - fill_price)



            self.realized_pnl += pnl

            self.quantity += fill_qty



        else:





            if self.quantity > 0:

                pnl = self.quantity * (fill_price - self.avg_entry_price)

            else:

                pnl = abs(self.quantity) * (self.avg_entry_price - fill_price)



            self.realized_pnl += pnl





            remaining_qty = fill_qty + self.quantity



            if remaining_qty == 0:



                self.quantity = 0

                self.avg_entry_price = 0.0

            else:



                self.quantity = remaining_qty

                self.avg_entry_price = fill_price

                self.opened_at = fill.timestamp



    def calculate_unrealized_pnl(self, current_price: float) -> float:

        """
        Calculate unrealized PnL at current market price.

        For long positions: (current_price - entry) * quantity
        For short positions: (entry - current_price) * |quantity|
        """

        if self.quantity == 0:

            return 0.0



        if self.quantity > 0:

            return self.quantity * (current_price - self.avg_entry_price)

        else:

            return abs(self.quantity) * (self.avg_entry_price - current_price)



    def total_pnl(self, current_price: float) -> float:

        """Total PnL (realized + unrealized)."""

        return self.realized_pnl + self.calculate_unrealized_pnl(current_price)





class Portfolio:

    """
    Portfolio tracker for the backtesting engine.

    Manages:
    - Cash balance
    - Positions for multiple instruments
    - Equity curve (time series of portfolio value)
    - Realized and unrealized PnL
    - Transaction history

    The portfolio subscribes to FillEvents via the event bus and updates
    its state accordingly. It also tracks market prices via MarketDataEvents
    to compute unrealized PnL and equity curve.

    Example:
        >>> portfolio = Portfolio(event_bus, initial_cash=100000.0)
        >>> # As fills occur, portfolio updates automatically
        >>> print(portfolio.total_equity)
    """



    def __init__(

        self,

        event_bus: EventBus,

        initial_cash: float = 100000.0,

    ) -> None:

        """
        Initialize the portfolio.

        Args:
            event_bus: Event bus for subscribing to fills and market data
            initial_cash: Starting cash balance
        """

        self._event_bus = event_bus

        self._initial_cash = initial_cash

        self._cash = initial_cash





        self._positions: Dict[str, Position] = {}





        self._current_prices: Dict[str, float] = {}





        self._equity_curve: Dict[datetime, float] = {}





        self._fills: List[FillEvent] = []





        self._event_bus.subscribe(EventType.FILL, self._on_fill)

        self._event_bus.subscribe(EventType.MARKET_DATA, self._on_market_data)





        self._peak_equity = initial_cash



    @property

    def initial_cash(self) -> float:

        """Initial cash deposit."""

        return self._initial_cash



    @property

    def cash(self) -> float:

        """Current cash balance."""

        return self._cash



    @property

    def positions(self) -> Dict[str, Position]:

        """Dictionary of all positions."""

        return self._positions.copy()



    @property

    def symbols(self) -> List[str]:

        """List of symbols with positions."""

        return list(self._positions.keys())



    @property

    def num_positions(self) -> int:

        """Number of non-zero positions."""

        return sum(1 for p in self._positions.values() if not p.is_flat)



    def get_position(self, symbol: str) -> Position:

        """
        Get position for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Position object (creates flat position if not found)
        """

        if symbol not in self._positions:

            self._positions[symbol] = Position(symbol=symbol)

        return self._positions[symbol]



    def get_position_quantity(self, symbol: str) -> int:

        """Get quantity for a symbol (0 if no position)."""

        return self._positions.get(symbol, Position(symbol)).quantity



    @property

    def long_exposure(self) -> float:

        """Total long market exposure."""

        exposure = 0.0

        for symbol, position in self._positions.items():

            if position.quantity > 0 and symbol in self._current_prices:

                exposure += position.market_value(self._current_prices[symbol])

        return exposure



    @property

    def short_exposure(self) -> float:

        """Total short market exposure (absolute value)."""

        exposure = 0.0

        for symbol, position in self._positions.items():

            if position.quantity < 0 and symbol in self._current_prices:

                exposure += abs(position.market_value(self._current_prices[symbol]))

        return exposure



    @property

    def gross_exposure(self) -> float:

        """Total gross exposure (long + short)."""

        return self.long_exposure + self.short_exposure



    @property

    def net_exposure(self) -> float:

        """Net exposure (long - short)."""

        return self.long_exposure - self.short_exposure



    @property

    def leverage(self) -> float:

        """Gross exposure divided by equity."""

        equity = self.total_equity

        if equity == 0:

            return 0.0

        return self.gross_exposure / equity



    @property

    def realized_pnl(self) -> float:

        """Total realized PnL across all positions."""

        return sum(p.realized_pnl for p in self._positions.values())



    @property

    def unrealized_pnl(self) -> float:

        """Total unrealized PnL across all positions."""

        pnl = 0.0

        for symbol, position in self._positions.items():

            if symbol in self._current_prices:

                pnl += position.calculate_unrealized_pnl(self._current_prices[symbol])

        return pnl



    @property

    def total_pnl(self) -> float:

        """Total PnL (realized + unrealized)."""

        return self.realized_pnl + self.unrealized_pnl



    @property

    def total_pnl_pct(self) -> float:

        """Total PnL as percentage of initial capital."""

        if self._initial_cash == 0:

            return 0.0

        return self.total_pnl / self._initial_cash



    @property

    def positions_market_value(self) -> float:

        """Total market value of all positions."""

        value = 0.0

        for symbol, position in self._positions.items():

            if symbol in self._current_prices:

                value += position.market_value(self._current_prices[symbol])

        return value



    @property

    def total_equity(self) -> float:

        """
        Total portfolio equity (cash + positions market value).

        This is the net asset value of the portfolio.
        """

        return self._cash + self.positions_market_value



    @property

    def total_value(self) -> float:

        """Alias for total_equity."""

        return self.total_equity



    def get_equity_series(self) -> pd.Series:

        """
        Get equity curve as a pandas Series.

        Returns:
            Time series of portfolio equity values indexed by timestamp
        """

        if not self._equity_curve:

            return pd.Series(dtype=float)



        series = pd.Series(self._equity_curve)

        series.index = pd.to_datetime(series.index)

        return series.sort_index()



    @property

    def equity_curve(self) -> pd.Series:

        """Equity curve as pandas Series."""

        return self.get_equity_series()



    def get_current_price(self, symbol: str) -> Optional[float]:

        """Get last known price for a symbol."""

        return self._current_prices.get(symbol)



    def _on_fill(self, event: Event) -> None:

        """Handle fill events from the event bus."""

        fill = event

        if not isinstance(fill, FillEvent):

            return





        fill_value = fill.quantity * fill.fill_price

        commission = fill.commission







        self._cash -= fill_value + commission





        position = self.get_position(fill.symbol)

        position.update_from_fill(fill)





        self._fills.append(fill)





        self._update_equity_curve(fill.timestamp)



    def _on_market_data(self, event: Event) -> None:

        """Handle market data events for price updates."""

        if not isinstance(event, MarketDataEvent):

            return





        self._current_prices[event.symbol] = event.close





        self._update_equity_curve(event.timestamp)



    def _update_equity_curve(self, timestamp: datetime) -> None:

        """Update equity curve at given timestamp."""

        equity = self.total_equity

        self._equity_curve[timestamp] = equity





        if equity > self._peak_equity:

            self._peak_equity = equity



    @property

    def peak_equity(self) -> float:

        """Highest equity value reached."""

        return self._peak_equity



    @property

    def current_drawdown(self) -> float:

        """Current drawdown from peak equity."""

        if self._peak_equity == 0:

            return 0.0

        return (self._peak_equity - self.total_equity) / self._peak_equity



    @property

    def max_drawdown(self) -> float:

        """Maximum drawdown observed in the equity curve."""

        if not self._equity_curve:

            return 0.0



        equity_series = self.get_equity_series()

        if len(equity_series) < 2:

            return 0.0



        running_max = equity_series.cummax()

        drawdown = (equity_series - running_max) / running_max

        return drawdown.min()



    def get_returns(self) -> pd.Series:

        """
        Get daily returns series from equity curve.

        Returns:
            Daily returns as percentage change
        """

        equity = self.get_equity_series()

        if len(equity) < 2:

            return pd.Series(dtype=float)



        return equity.pct_change().dropna()



    def get_fill_history(self) -> pd.DataFrame:

        """
        Get transaction history as DataFrame.

        Returns:
            DataFrame with columns: timestamp, symbol, quantity, fill_price,
            commission, slippage
        """

        if not self._fills:

            return pd.DataFrame()



        records = []

        for fill in self._fills:

            records.append({

                'timestamp': fill.timestamp,

                'symbol': fill.symbol,

                'quantity': fill.quantity,

                'fill_price': fill.fill_price,

                'notional': fill.notional_value,

                'commission': fill.commission,

                'slippage': fill.slippage,

                'total_cost': fill.total_cost,

            })



        df = pd.DataFrame(records)

        if not df.empty:

            df = df.sort_values('timestamp')

        return df



    def get_position_summary(self) -> pd.DataFrame:

        """
        Get summary of all positions as DataFrame.

        Returns:
            DataFrame with position details including market values and PnL
        """

        if not self._positions:

            return pd.DataFrame()



        records = []

        for symbol, position in self._positions.items():

            if position.is_flat:

                continue



            current_price = self._current_prices.get(symbol, position.avg_entry_price)



            records.append({

                'symbol': symbol,

                'quantity': position.quantity,

                'side': 'LONG' if position.is_long else 'SHORT',

                'avg_entry': position.avg_entry_price,

                'current_price': current_price,

                'market_value': position.market_value(current_price),

                'unrealized_pnl': position.calculate_unrealized_pnl(current_price),

                'realized_pnl': position.realized_pnl,

                'total_pnl': position.total_pnl(current_price),

            })



        df = pd.DataFrame(records)

        if not df.empty:

            df = df.sort_values('market_value', ascending=False)

        return df



    def get_stats(self) -> dict:

        """
        Get portfolio statistics summary.

        Returns:
            Dictionary with key portfolio metrics
        """

        return {

            'initial_cash': self._initial_cash,

            'current_cash': self._cash,

            'total_equity': self.total_equity,

            'total_return': self.total_equity - self._initial_cash,

            'total_return_pct': self.total_pnl_pct,

            'realized_pnl': self.realized_pnl,

            'unrealized_pnl': self.unrealized_pnl,

            'total_pnl': self.total_pnl,

            'num_positions': self.num_positions,

            'long_exposure': self.long_exposure,

            'short_exposure': self.short_exposure,

            'gross_exposure': self.gross_exposure,

            'net_exposure': self.net_exposure,

            'leverage': self.leverage,

            'peak_equity': self._peak_equity,

            'current_drawdown': self.current_drawdown,

            'max_drawdown': self.max_drawdown,

            'num_trades': len(self._fills),

        }



    def can_trade(self, symbol: str, quantity: int, price: float) -> Tuple[bool, str]:

        """
        Check if a trade is possible given current portfolio state.

        Args:
            symbol: Trading symbol
            quantity: Number of shares (positive=buy, negative=sell)
            price: Expected trade price

        Returns:
            Tuple of (can_trade: bool, reason: str)
        """



        if quantity > 0:

            cost = quantity * price

            if cost > self._cash:

                return False, f"Insufficient cash: need {cost:.2f}, have {self._cash:.2f}"





        if quantity < 0:

            current_qty = self.get_position_quantity(symbol)





            if abs(quantity) > current_qty:

                return False, f"Insufficient shares: have {current_qty}, want to sell {abs(quantity)}"



        return True, "OK"



    def reset(self) -> None:

        """Reset portfolio to initial state."""

        self._cash = self._initial_cash

        self._positions.clear()

        self._current_prices.clear()

        self._equity_curve.clear()

        self._fills.clear()

        self._peak_equity = self._initial_cash
