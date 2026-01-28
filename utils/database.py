"""
Database Module

DuckDB interface for storing and querying OHLCV data.
DuckDB is a fast, embedded analytical database perfect for
quantitative finance workloads.
"""



from __future__ import annotations



from datetime import datetime

from pathlib import Path

from typing import List, Optional, Tuple, Union, Dict, Any



import pandas as pd

import duckdb

import numpy as np





class DuckDBInterface:

    """
    Interface for DuckDB database operations.

    Provides methods for:
    - Storing OHLCV data
    - Querying historical data
    - Computing features
    - Managing symbols

    DuckDB is chosen for:
    - Fast analytical queries
    - SQL interface
    - Zero external dependencies (embedded)
    - Great pandas integration

    Example:
        >>> db = DuckDBInterface("./data/quantforge.db")
        >>> db.store_ohlcv("AAPL", df)
        >>> data = db.get_ohlcv("AAPL", start="2020-01-01", end="2020-12-31")
    """



    def __init__(self, db_path: Union[str, Path] = "./data/quantforge.db") -> None:

        """
        Initialize DuckDB connection.

        Args:
            db_path: Path to DuckDB database file
        """

        self._db_path = Path(db_path)

        self._db_path.parent.mkdir(parents=True, exist_ok=True)





        self._conn = duckdb.connect(str(self._db_path))





        self._init_schema()



    def _init_schema(self) -> None:

        """Create database tables if they don't exist."""





        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS ohlcv (
                symbol VARCHAR NOT NULL,
                date DATE NOT NULL,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume BIGINT,
                adj_close DOUBLE,
                PRIMARY KEY (symbol, date)
            )
        """)





        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS features (
                symbol VARCHAR NOT NULL,
                date DATE NOT NULL,
                ret_1d DOUBLE,
                ret_5d DOUBLE,
                ret_21d DOUBLE,
                vol_5d DOUBLE,
                vol_21d DOUBLE,
                rsi_14 DOUBLE,
                sma_20 DOUBLE,
                sma_50 DOUBLE,
                ema_12 DOUBLE,
                ema_26 DOUBLE,
                macd_hist DOUBLE,
                bb_upper DOUBLE,
                bb_lower DOUBLE,
                bb_pct DOUBLE,
                atr_14 DOUBLE,
                volume_ratio_20 DOUBLE,
                PRIMARY KEY (symbol, date)
            )
        """)





        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS symbols (
                symbol VARCHAR PRIMARY KEY,
                name VARCHAR,
                sector VARCHAR,
                industry VARCHAR,
                first_date DATE,
                last_date DATE,
                total_bars INTEGER
            )
        """)





        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS backtest_results (
                run_id VARCHAR PRIMARY KEY,
                strategy_name VARCHAR,
                start_date DATE,
                end_date DATE,
                symbols VARCHAR[],
                initial_capital DOUBLE,
                final_equity DOUBLE,
                total_return DOUBLE,
                total_return_pct DOUBLE,
                sharpe_ratio DOUBLE,
                max_drawdown DOUBLE,
                num_trades INTEGER,
                win_rate DOUBLE,
                config JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)



    def close(self) -> None:

        """Close database connection."""

        self._conn.close()



    def __enter__(self) -> "DuckDBInterface":

        """Context manager entry."""

        return self



    def __exit__(self, exc_type, exc_val, exc_tb) -> None:

        """Context manager exit."""

        self.close()











    def store_ohlcv(

        self,

        symbol: str,

        df: pd.DataFrame,

        if_exists: str = "replace"

    ) -> None:

        """
        Store OHLCV data for a symbol.

        Args:
            symbol: Trading symbol
            df: DataFrame with columns [open, high, low, close, volume, adj_close]
            if_exists: 'replace', 'append', or 'fail'
        """



        df = df.copy()



        if 'date' not in df.columns and df.index.name in ['date', 'Date', 'timestamp']:

            df = df.reset_index()



        if 'date' not in df.columns:

            raise ValueError("DataFrame must have 'date' column or datetime index")





        df.columns = [c.lower() for c in df.columns]





        df['symbol'] = symbol





        required = ['symbol', 'date', 'open', 'high', 'low', 'close', 'volume']

        missing = [c for c in required if c not in df.columns]

        if missing:

            raise ValueError(f"Missing columns: {missing}")





        if 'adj_close' not in df.columns:

            df['adj_close'] = df['close']





        cols = ['symbol', 'date', 'open', 'high', 'low', 'close', 'volume', 'adj_close']

        df = df[cols]





        df['date'] = pd.to_datetime(df['date']).dt.date





        if if_exists == "replace":

            self._conn.execute("DELETE FROM ohlcv WHERE symbol = ?", [symbol])

        elif if_exists == "fail":

            existing = self._conn.execute(

                "SELECT COUNT(*) FROM ohlcv WHERE symbol = ?", [symbol]

            ).fetchone()[0]

            if existing > 0:

                raise ValueError(f"Data already exists for {symbol}")





        self._conn.execute("""
            INSERT INTO ohlcv
            SELECT * FROM df
        """)





        self._update_symbol_metadata(symbol, df)



    def _update_symbol_metadata(self, symbol: str, df: pd.DataFrame) -> None:

        """Update symbol metadata after storing data."""

        first_date = df['date'].min()

        last_date = df['date'].max()

        total_bars = len(df)



        self._conn.execute("""
            INSERT OR REPLACE INTO symbols (symbol, first_date, last_date, total_bars)
            VALUES (?, ?, ?, ?)
        """, [symbol, first_date, last_date, total_bars])



    def get_ohlcv(

        self,

        symbol: str,

        start: Optional[Union[str, datetime]] = None,

        end: Optional[Union[str, datetime]] = None,

        columns: Optional[List[str]] = None

    ) -> pd.DataFrame:

        """
        Retrieve OHLCV data for a symbol.

        Args:
            symbol: Trading symbol
            start: Start date (inclusive)
            end: End date (inclusive)
            columns: Specific columns to retrieve (None = all)

        Returns:
            DataFrame with OHLCV data
        """



        if columns:

            cols = ', '.join(columns)

        else:

            cols = "symbol, date, open, high, low, close, volume, adj_close"



        query = f"SELECT {cols} FROM ohlcv WHERE symbol = ?"

        params: List[Any] = [symbol]



        if start:

            query += " AND date >= ?"

            params.append(pd.to_datetime(start).date())



        if end:

            query += " AND date <= ?"

            params.append(pd.to_datetime(end).date())



        query += " ORDER BY date"





        df = self._conn.execute(query, params).fetchdf()



        if not df.empty and 'date' in df.columns:

            df['date'] = pd.to_datetime(df['date'])

            df = df.set_index('date')



        return df



    def get_symbols(self) -> List[str]:

        """Get list of all symbols in database."""

        result = self._conn.execute(

            "SELECT symbol FROM symbols ORDER BY symbol"

        ).fetchall()

        return [row[0] for row in result]



    def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:

        """Get metadata for a symbol."""

        result = self._conn.execute(

            "SELECT * FROM symbols WHERE symbol = ?", [symbol]

        ).fetchone()



        if result is None:

            return None



        columns = [desc[0] for desc in self._conn.description]

        return dict(zip(columns, result))



    def delete_symbol(self, symbol: str) -> None:

        """Remove all data for a symbol."""

        self._conn.execute("DELETE FROM ohlcv WHERE symbol = ?", [symbol])

        self._conn.execute("DELETE FROM features WHERE symbol = ?", [symbol])

        self._conn.execute("DELETE FROM symbols WHERE symbol = ?", [symbol])











    def compute_and_store_features(

        self,

        symbol: str,

        start: Optional[Union[str, datetime]] = None,

        end: Optional[Union[str, datetime]] = None

    ) -> pd.DataFrame:

        """
        Compute technical features for a symbol and store them.

        Computes:
        - Returns at various horizons (1d, 5d, 21d)
        - Volatility (5d, 21d realized)
        - RSI (14-day)
        - Moving averages (SMA 20, 50; EMA 12, 26)
        - MACD histogram
        - Bollinger Bands
        - ATR (14-day)
        - Volume ratio

        Args:
            symbol: Trading symbol
            start: Start date
            end: End date

        Returns:
            DataFrame with computed features
        """



        df = self.get_ohlcv(symbol, start, end)



        if df.empty:

            return pd.DataFrame()





        features = pd.DataFrame(index=df.index)

        features['symbol'] = symbol

        features['date'] = df.index.date





        close = df['adj_close'] if 'adj_close' in df.columns else df['close']

        features['ret_1d'] = close.pct_change(1)

        features['ret_5d'] = close.pct_change(5)

        features['ret_21d'] = close.pct_change(21)





        log_ret = np.log(close / close.shift(1))

        features['vol_5d'] = log_ret.rolling(5).std() * np.sqrt(252)

        features['vol_21d'] = log_ret.rolling(21).std() * np.sqrt(252)





        delta = close.diff()

        gain = delta.where(delta > 0, 0).rolling(14).mean()

        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()

        rs = gain / loss

        features['rsi_14'] = 100 - (100 / (1 + rs))





        features['sma_20'] = close.rolling(20).mean()

        features['sma_50'] = close.rolling(50).mean()

        features['ema_12'] = close.ewm(span=12, adjust=False).mean()

        features['ema_26'] = close.ewm(span=26, adjust=False).mean()





        macd = features['ema_12'] - features['ema_26']

        signal = macd.ewm(span=9, adjust=False).mean()

        features['macd_hist'] = macd - signal





        sma20 = features['sma_20']

        std20 = close.rolling(20).std()

        features['bb_upper'] = sma20 + (2 * std20)

        features['bb_lower'] = sma20 - (2 * std20)

        features['bb_pct'] = (close - features['bb_lower']) / (features['bb_upper'] - features['bb_lower'])





        high = df['high']

        low = df['low']

        prev_close = close.shift(1)

        tr1 = high - low

        tr2 = abs(high - prev_close)

        tr3 = abs(low - prev_close)

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        features['atr_14'] = tr.rolling(14).mean()





        if 'volume' in df.columns:

            features['volume_ratio_20'] = df['volume'] / df['volume'].rolling(20).mean()





        features = features.dropna()



        if not features.empty:



            self._conn.execute(

                "DELETE FROM features WHERE symbol = ?", [symbol]

            )





            self._conn.execute("""
                INSERT INTO features
                SELECT * FROM features
            """)



        return features



    def get_features(

        self,

        symbol: str,

        start: Optional[Union[str, datetime]] = None,

        end: Optional[Union[str, datetime]] = None

    ) -> pd.DataFrame:

        """Retrieve computed features for a symbol."""

        query = "SELECT * FROM features WHERE symbol = ?"

        params: List[Any] = [symbol]



        if start:

            query += " AND date >= ?"

            params.append(pd.to_datetime(start).date())



        if end:

            query += " AND date <= ?"

            params.append(pd.to_datetime(end).date())



        query += " ORDER BY date"



        df = self._conn.execute(query, params).fetchdf()



        if not df.empty and 'date' in df.columns:

            df['date'] = pd.to_datetime(df['date'])

            df = df.set_index('date')



        return df











    def store_backtest_result(

        self,

        run_id: str,

        strategy_name: str,

        start_date: Union[str, datetime],

        end_date: Union[str, datetime],

        symbols: List[str],

        initial_capital: float,

        final_equity: float,

        total_return: float,

        total_return_pct: float,

        sharpe_ratio: float,

        max_drawdown: float,

        num_trades: int,

        win_rate: float,

        config: Dict[str, Any]

    ) -> None:

        """Store backtest results."""

        self._conn.execute("""
            INSERT INTO backtest_results
            (run_id, strategy_name, start_date, end_date, symbols, initial_capital,
             final_equity, total_return, total_return_pct, sharpe_ratio, max_drawdown,
             num_trades, win_rate, config)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [

            run_id, strategy_name, pd.to_datetime(start_date).date(),

            pd.to_datetime(end_date).date(), symbols, initial_capital,

            final_equity, total_return, total_return_pct, sharpe_ratio, max_drawdown,

            num_trades, win_rate, str(config)

        ])



    def get_backtest_results(

        self,

        strategy_name: Optional[str] = None,

        start_date: Optional[Union[str, datetime]] = None,

        limit: int = 100

    ) -> pd.DataFrame:

        """Retrieve backtest results."""

        query = "SELECT * FROM backtest_results WHERE 1=1"

        params: List[Any] = []



        if strategy_name:

            query += " AND strategy_name = ?"

            params.append(strategy_name)



        if start_date:

            query += " AND start_date >= ?"

            params.append(pd.to_datetime(start_date).date())



        query += " ORDER BY created_at DESC LIMIT ?"

        params.append(limit)



        return self._conn.execute(query, params).fetchdf()











    def get_date_range(self, symbol: str) -> Tuple[Optional[datetime], Optional[datetime]]:

        """Get date range for a symbol."""

        result = self._conn.execute("""
            SELECT MIN(date), MAX(date) FROM ohlcv WHERE symbol = ?
        """, [symbol]).fetchone()



        if result and result[0]:

            return pd.to_datetime(result[0]), pd.to_datetime(result[1])

        return None, None



    def get_price_at_date(

        self,

        symbol: str,

        date: Union[str, datetime],

        price_type: str = "close"

    ) -> Optional[float]:

        """Get price for a symbol at specific date."""

        result = self._conn.execute(f"""
            SELECT {price_type} FROM ohlcv
            WHERE symbol = ? AND date = ?
        """, [symbol, pd.to_datetime(date).date()]).fetchone()



        if result:

            return result[0]

        return None



    def execute_query(self, query: str, params: Optional[List[Any]] = None) -> pd.DataFrame:

        """Execute arbitrary SQL query and return results as DataFrame."""

        if params:

            return self._conn.execute(query, params).fetchdf()

        return self._conn.execute(query).fetchdf()
