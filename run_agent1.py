"""
Run Agent 1 Trend Strategy
"""



import sys

import os

from datetime import datetime, timedelta

import pandas as pd

import numpy as np





sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))



from quantforge.core.engine import BacktestEngine

from quantforge.data.feeds import CSVFeed, YahooFinanceFeed

from quantforge.strategies.base import StrategyConfig

from quantforge.strategies.agent1_trend import Agent1TrendStrategy



def ensure_data(symbols, data_dir):

    """Ensure CSV data exists, download if not."""

    if not os.path.exists(data_dir):

        os.makedirs(data_dir)



    for symbol in symbols:

        csv_path = os.path.join(data_dir, f"{symbol}.csv")

        if not os.path.exists(csv_path):

            print(f"Downloading data for {symbol}...")

            try:

                import yfinance as yf



                df = yf.download(symbol, start="2020-01-01", end=datetime.now().strftime('%Y-%m-%d'), progress=False)

                if df.empty:

                    print(f"Error: No data for {symbol}")

                    continue





                df.reset_index(inplace=True)





                if isinstance(df.columns, pd.MultiIndex):



                    found = False

                    for i in range(df.columns.nlevels):

                        level_values = df.columns.get_level_values(i)

                        if 'Close' in level_values or 'close' in level_values:

                            df.columns = level_values

                            found = True

                            break

                    if not found:



                         df.columns = df.columns.get_level_values(0)





                df.columns = [str(c).lower().strip() for c in df.columns]











                df = df.loc[:, ~df.columns.str.contains('^unnamed')]



                df.to_csv(csv_path, index=False)

                print(f"Saved {symbol} data to {csv_path}")

            except ImportError:

                print("Error: yfinance not installed. Cannot download data.")

                return False

            except Exception as e:

                print(f"Error downloading {symbol}: {e}")

                return False

    return True



def run_strategy():



    symbols = ['SPY', 'AAPL']

    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'data/csv'))





    if not ensure_data(symbols, data_dir):

        print("Failed to ensure data availability.")

        return





    engine = BacktestEngine(

        initial_capital=100000.0,

        start_date=datetime(2021, 1, 1),

        end_date=datetime.now(),

        verbose=True

    )





    config = StrategyConfig(

        name="Agent1_Trend_TSMOM",

        symbols=symbols,

        timeframe="1d"

    )

    strategy = Agent1TrendStrategy(config, lookback=252)

    engine.add_strategy(strategy)





































    class MultiCSVFeed:

        def __init__(self, data_dir, symbols):

            self.data_dir = data_dir

            self.symbols = symbols

            self.feeds = []

            self.latest_events = {}

            for s in symbols:

                path = os.path.join(data_dir, f"{s}.csv")

                self.feeds.append(CSVFeed(path, symbol=s))



        def get_data_iterator(self, symbols, start_date, end_date):



            all_events = []

            for feed in self.feeds:

                for event in feed.get_data_iterator([feed.symbol], start_date, end_date):

                    all_events.append(event)





            all_events.sort(key=lambda x: x.timestamp)





            for event in all_events:

                self.latest_events[event.symbol] = event

                yield event



        def get_bar_count(self, symbols, start_date, end_date):

            total = 0

            for feed in self.feeds:

                total += feed.get_bar_count([feed.symbol], start_date, end_date)

            return total



        def get_latest(self, symbol):

            return self.latest_events.get(symbol)



    feed = MultiCSVFeed(data_dir, symbols)

    engine.add_data(feed, symbols)





    print("Running backtest...")

    metrics = engine.run()





    print("\n" + "="*50)

    print("FINAL REPORT: Agent 1 Trend Strategy")

    print("="*50)









    history = engine.portfolio.equity_curve

    if not history:

        print("No history recorded.")

        return



    df_result = pd.DataFrame(history, columns=['timestamp', 'equity'])

    df_result.set_index('timestamp', inplace=True)

    df_result['returns'] = df_result['equity'].pct_change().fillna(0)



    final_equity = engine.portfolio.equity

    total_return_pct = ((final_equity - engine.initial_capital) / engine.initial_capital) * 100







    mean_return = df_result['returns'].mean()

    std_return = df_result['returns'].std()

    sharpe = 0.0

    if std_return > 0:

        sharpe = (mean_return / std_return) * np.sqrt(252)





    df_result['cummax'] = df_result['equity'].cummax()

    df_result['drawdown'] = (df_result['equity'] - df_result['cummax']) / df_result['cummax']

    max_drawdown_pct = df_result['drawdown'].min() * 100



    print(f"Total Return: {total_return_pct:.2f}%")

    print(f"Sharpe Ratio: {sharpe:.2f}")

    print(f"Max Drawdown: {max_drawdown_pct:.2f}%")

    print("="*50)



if __name__ == "__main__":

    run_strategy()
