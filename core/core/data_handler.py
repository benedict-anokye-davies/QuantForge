"""
Data Handler Module

Provides abstract interface and concrete implementations for loading
and streaming market data. The HistoricalCSVDataHandler is designed
to prevent look-ahead bias by only exposing bars up to the current time.
"""



from __future__ import annotations



from abc import ABC, abstractmethod

from datetime import datetime

from pathlib import Path

from typing import Dict, List, Optional, Set, Union



import pandas as pd



from quantforge.core.events import EventBus, MarketDataEvent, EventType





class DataHandler(ABC):

    """
    Abstract base class for all data handlers.

    The DataHandler is responsible for loading and streaming market data
    to the backtester. It must prevent look-ahead bias by only making
    data available up to the current simulation time.

    Implementations must ensure:
    - No future data is accessible (look-ahead bias prevention)
    - Data is properly aligned across symbols
    - Missing data is handled gracefully

    Example:
        >>> handler = HistoricalCSVDataHandler("data/", ["AAPL", "MSFT"], bus)
        >>> while handler.update_bars():
        ...     # Process one bar at a time
        ...     pass
    """



    def __init__(self, event_bus: EventBus) -> None:

        """
        Initialize the data handler.

        Args:
            event_bus: Event bus for publishing market data events
        """

        self._event_bus = event_bus

        self._symbols: Set[str] = set()

        self._current_time: Optional[datetime] = None



    @property

    @abstractmethod

    def symbols(self) -> List[str]:

        """Return list of available symbols."""

        pass



    @abstractmethod

    def get_latest_bars(

        self,

        symbol: str,

        n: int = 1,

        as_df: bool = True

    ) -> Union[pd.DataFrame, List[MarketDataEvent]]:

        """
        Return the last N bars for a symbol (no look-ahead).

        This is the critical method for preventing look-ahead bias.
        It should only return data that was available at or before
        the current simulation time.

        Args:
            symbol: Trading symbol
            n: Number of bars to retrieve
            as_df: If True, return as DataFrame; if False, return list of events

        Returns:
            Last N bars as DataFrame or list of MarketDataEvent

        Raises:
            KeyError: If symbol is not available
            ValueError: If n is invalid
        """

        pass



    @abstractmethod

    def update_bars(self) -> Optional[List[MarketDataEvent]]:

        """
        Advance to the next bar and emit MarketDataEvents.

        This is the main method for driving the backtest forward.
        It should:
        1. Advance the internal time pointer
        2. Load the next bar(s) for all symbols
        3. Publish MarketDataEvents to the event bus

        Returns:
            List of MarketDataEvent objects published, or None if no more data
        """

        pass



    @abstractmethod

    def has_more_data(self) -> bool:

        """Return True if there is more data to process."""

        pass



    @property

    def current_time(self) -> Optional[datetime]:

        """Current simulation time (last bar timestamp)."""

        return self._current_time



    def _publish_market_data(self, event: MarketDataEvent) -> None:

        """Helper to publish market data event to bus."""

        self._event_bus.publish(event)





class HistoricalCSVDataHandler(DataHandler):

    """
    Loads OHLCV data from CSV files and emits one bar at a time.

    This implementation:
    - Loads full historical data into memory for each symbol
    - Maintains separate pointers for each symbol
    - Emits bars in chronological order across all symbols
    - Prevents look-ahead by only exposing data up to current index

    CSV files should have columns:
        date, open, high, low, close, volume, [adj_close]

    The date column should be parseable as datetime (preferably YYYY-MM-DD).

    Example CSV format:
        date,open,high,low,close,volume,adj_close
        2020-01-02,74.06,75.15,73.8,75.09,135480400,74.02
        2020-01-03,74.29,75.14,74.13,74.36,146322800,73.30
    """





    COLUMN_MAPPINGS = {

        'date': ['date', 'Date', 'DATE', 'timestamp', 'Timestamp', 'dt'],

        'open': ['open', 'Open', 'OPEN', 'o'],

        'high': ['high', 'High', 'HIGH', 'h'],

        'low': ['low', 'Low', 'LOW', 'l'],

        'close': ['close', 'Close', 'CLOSE', 'c'],

        'volume': ['volume', 'Volume', 'VOLUME', 'vol', 'v'],

        'adj_close': ['adj_close', 'adj close', 'adjusted_close', 'adjClose',

                      'Adj Close', 'adjclose', 'adjusted close'],

    }



    def __init__(

        self,

        data_dir: Union[str, Path],

        symbols: List[str],

        event_bus: EventBus,

        date_format: Optional[str] = None,

        start_date: Optional[Union[str, datetime]] = None,

        end_date: Optional[Union[str, datetime]] = None,

    ) -> None:

        """
        Initialize CSV data handler.

        Args:
            data_dir: Directory containing CSV files named {SYMBOL}.csv
            symbols: List of symbols to load
            event_bus: Event bus for publishing market data
            date_format: Optional strptime format for date parsing
            start_date: Optional start date filter (inclusive)
            end_date: Optional end date filter (inclusive)

        Raises:
            FileNotFoundError: If data directory or files don't exist
            ValueError: If symbols list is empty or contains duplicates
        """

        super().__init__(event_bus)



        if not symbols:

            raise ValueError("symbols list cannot be empty")



        if len(symbols) != len(set(symbols)):

            raise ValueError("symbols list contains duplicates")



        self._symbols = set(symbols)

        self._data_dir = Path(data_dir)

        self._date_format = date_format





        self._start_date = self._parse_date(start_date) if start_date else None

        self._end_date = self._parse_date(end_date) if end_date else None





        self._data: Dict[str, pd.DataFrame] = {}





        self._current_idx: Dict[str, int] = {}





        self._bar_queue: List[tuple[datetime, str, int]] = []





        self._load_data()

        self._build_bar_queue()



    def _parse_date(self, date: Union[str, datetime]) -> datetime:

        """Parse date string to datetime."""

        if isinstance(date, datetime):

            return date

        if isinstance(date, str):

            if self._date_format:

                return datetime.strptime(date, self._date_format)



            return pd.to_datetime(date).to_pydatetime()

        raise TypeError(f"Cannot parse date: {date}")



    def _load_data(self) -> None:

        """Load CSV files for all symbols into memory."""

        if not self._data_dir.exists():

            raise FileNotFoundError(f"Data directory not found: {self._data_dir}")



        for symbol in self._symbols:

            csv_path = self._data_dir / f"{symbol}.csv"



            if not csv_path.exists():

                raise FileNotFoundError(f"Data file not found: {csv_path}")





            df = pd.read_csv(

                csv_path,

                parse_dates=True,

                index_col=0,

            )





            df = self._normalize_columns(df)





            if not isinstance(df.index, pd.DatetimeIndex):

                df.index = pd.to_datetime(df.index)





            df = df.sort_index()





            if self._start_date:

                df = df[df.index >= self._start_date]

            if self._end_date:

                df = df[df.index <= self._end_date]





            required = ['open', 'high', 'low', 'close', 'volume']

            missing = [c for c in required if c not in df.columns]

            if missing:

                raise ValueError(f"{symbol}: Missing columns: {missing}")





            self._validate_data(symbol, df)





            self._data[symbol] = df

            self._current_idx[symbol] = 0



            print(f"Loaded {len(df)} bars for {symbol} ({df.index[0]} to {df.index[-1]})")



    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:

        """Normalize column names to standard format."""

        col_mapping = {}

        for std_name, alternatives in self.COLUMN_MAPPINGS.items():

            for col in df.columns:

                if col in alternatives:

                    col_mapping[col] = std_name.lower()

                    break



        return df.rename(columns=col_mapping)



    def _validate_data(self, symbol: str, df: pd.DataFrame) -> None:

        """Validate OHLCV data integrity."""



        required = ['open', 'high', 'low', 'close', 'volume']

        for col in required:

            if df[col].isna().any():

                na_count = df[col].isna().sum()

                raise ValueError(f"{symbol}: {na_count} missing values in {col}")





        invalid_high_low = (df['high'] < df['low']).sum()

        if invalid_high_low > 0:

            raise ValueError(f"{symbol}: {invalid_high_low} bars with high < low")





        for col in ['open', 'high', 'low', 'close']:

            if (df[col] <= 0).any():

                raise ValueError(f"{symbol}: Zero or negative prices in {col}")





        if (df['volume'] < 0).any():

            raise ValueError(f"{symbol}: Negative volume values")



    def _build_bar_queue(self) -> None:

        """
        Build a chronological queue of all bars across all symbols.

        This ensures that bars are emitted in correct temporal order,
        even when symbols have different trading schedules or gaps.
        """

        bars = []

        for symbol, df in self._data.items():

            for idx, timestamp in enumerate(df.index):

                bars.append((timestamp, symbol, idx))





        bars.sort(key=lambda x: x[0])

        self._bar_queue = bars

        self._queue_idx = 0



    @property

    def symbols(self) -> List[str]:

        """Return list of loaded symbols."""

        return sorted(list(self._symbols))



    def get_latest_bars(

        self,

        symbol: str,

        n: int = 1,

        as_df: bool = True

    ) -> Union[pd.DataFrame, List[MarketDataEvent]]:

        """
        Return the last N bars for a symbol up to current index.

        This is the key method for preventing look-ahead bias.
        It only returns bars that have been "emitted" via update_bars().

        Args:
            symbol: Trading symbol
            n: Number of bars to retrieve
            as_df: Return as DataFrame if True, else list of events

        Returns:
            Last N available bars

        Raises:
            KeyError: If symbol not found
            ValueError: If n is invalid
        """

        if symbol not in self._symbols:

            raise KeyError(f"Symbol not found: {symbol}")



        if n < 1:

            raise ValueError(f"n must be >= 1, got {n}")



        df = self._data[symbol]

        current_idx = self._current_idx[symbol]





        start_idx = max(0, current_idx - n)

        end_idx = current_idx



        if start_idx >= end_idx:



            if as_df:

                return pd.DataFrame(columns=df.columns)

            return []



        bars_df = df.iloc[start_idx:end_idx]



        if as_df:

            return bars_df





        events = []

        for timestamp, row in bars_df.iterrows():

            event = self._create_market_data_event(symbol, timestamp, row)

            events.append(event)



        return events



    def _create_market_data_event(

        self,

        symbol: str,

        timestamp: datetime,

        row: pd.Series

    ) -> MarketDataEvent:

        """Create a MarketDataEvent from a DataFrame row."""

        return MarketDataEvent(

            timestamp=timestamp,

            event_type=EventType.MARKET_DATA,

            symbol=symbol,

            open_price=float(row['open']),

            high_price=float(row['high']),

            low_price=float(row['low']),

            close_price=float(row['close']),

            volume=int(row['volume']),

            adjusted_close=float(row.get('adj_close', row['close'])),

        )



    def update_bars(self) -> Optional[List[MarketDataEvent]]:

        """
        Advance to the next timestamp and emit all bars at that time.

        This method:
        1. Finds the next chronological timestamp in the queue
        2. Emits all bars (across symbols) at that timestamp
        3. Advances current indices for those symbols
        4. Updates the global current time

        Returns:
            List of MarketDataEvent objects emitted, or None if no more data
        """

        if self._queue_idx >= len(self._bar_queue):

            return None





        next_timestamp, _, _ = self._bar_queue[self._queue_idx]



        events = []





        while self._queue_idx < len(self._bar_queue):

            timestamp, symbol, idx = self._bar_queue[self._queue_idx]



            if timestamp != next_timestamp:

                break





            self._current_idx[symbol] = idx + 1





            row = self._data[symbol].iloc[idx]

            event = self._create_market_data_event(symbol, timestamp, row)

            events.append(event)

            self._publish_market_data(event)



            self._queue_idx += 1





        self._current_time = next_timestamp



        return events if events else None



    def has_more_data(self) -> bool:

        """Return True if there are more bars to process."""

        return self._queue_idx < len(self._bar_queue)



    def get_all_data(self, symbol: str) -> pd.DataFrame:

        """
        Get the full historical data for a symbol (for initial analysis).

        WARNING: This bypasses look-ahead protection and should only
        be used for pre-backtest analysis, not during the backtest loop.

        Args:
            symbol: Trading symbol

        Returns:
            Full historical DataFrame
        """

        if symbol not in self._data:

            raise KeyError(f"Symbol not found: {symbol}")



        return self._data[symbol].copy()



    def get_date_range(self) -> tuple[datetime, datetime]:

        """Return the date range of loaded data across all symbols."""

        all_dates = []

        for df in self._data.values():

            all_dates.extend([df.index[0], df.index[-1]])



        return min(all_dates), max(all_dates)



    def get_symbol_info(self, symbol: str) -> dict:

        """Get information about a symbol's data."""

        if symbol not in self._data:

            raise KeyError(f"Symbol not found: {symbol}")



        df = self._data[symbol]

        return {

            'symbol': symbol,

            'start_date': df.index[0],

            'end_date': df.index[-1],

            'total_bars': len(df),

            'current_index': self._current_idx[symbol],

            'remaining_bars': len(df) - self._current_idx[symbol],

        }



    def reset(self) -> None:

        """Reset the data handler to start from the beginning."""

        for symbol in self._symbols:

            self._current_idx[symbol] = 0



        self._queue_idx = 0

        self._current_time = None
