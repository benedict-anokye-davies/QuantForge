import pandas as pd

import numpy as np



def run_backtest():

    print("Running Agent 1 Backtest (Simplified)...")





    try:



        df = pd.read_csv('quantforge/data/csv/SPY.csv', header=2)





        df.columns = ['Date', 'Close', 'High', 'Low', 'Open', 'Volume']

        df['Date'] = pd.to_datetime(df['Date'])

        df.set_index('Date', inplace=True)

        df.sort_index(inplace=True)

    except Exception as e:

        print(f"Error loading data: {e}")

        return





    lookback = 252







    df['Momentum'] = df['Close'].pct_change(lookback)





    df['Signal'] = np.where(df['Momentum'] > 0, 1.0, 0.0)





    df['Position'] = df['Signal'].shift(1)





    df['Strategy_Return'] = df['Position'] * df['Close'].pct_change()

    df['BuyHold_Return'] = df['Close'].pct_change()





    df['Strategy_Equity'] = (1 + df['Strategy_Return']).cumprod()

    df['BuyHold_Equity'] = (1 + df['BuyHold_Return']).cumprod()





    total_return = (df['Strategy_Equity'].iloc[-1] - 1) * 100

    buy_hold_return = (df['BuyHold_Equity'].iloc[-1] - 1) * 100



    daily_sharpe = df['Strategy_Return'].mean() / df['Strategy_Return'].std()

    annualized_sharpe = daily_sharpe * np.sqrt(252)





    peak = df['Strategy_Equity'].cummax()

    drawdown = (df['Strategy_Equity'] - peak) / peak

    max_drawdown = drawdown.min() * 100



    print("\n--- AGENT 1 (MOMENTUM) RESULTS ---")

    print(f"Asset: SPY (S&P 500)")

    print(f"Period: {df.index[0].date()} to {df.index[-1].date()}")

    print(f"Total Return: {total_return:.2f}%")

    print(f"Buy & Hold Return: {buy_hold_return:.2f}%")

    print(f"Sharpe Ratio: {annualized_sharpe:.2f}")

    print(f"Max Drawdown: {max_drawdown:.2f}%")



    if total_return > buy_hold_return:

        print("\n🏆 WINNER: Strategy Beat the Market!")

    else:

        print("\n❌ RESULT: Strategy Lagged Market (Safety Cost?)")



if __name__ == "__main__":

    run_backtest()
