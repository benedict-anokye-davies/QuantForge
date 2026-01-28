import pandas as pd

import numpy as np



def run_pairs_backtest():

    print("Running Agent 2 Backtest (Pairs Trading: AAPL vs MSFT)...")





    try:



        df = pd.read_csv('quantforge/data/csv/PAIRS.csv', header=2)





        df = df.iloc[:, [0, 1, 2]]

        df.columns = ['Date', 'AAPL', 'MSFT']

        df['Date'] = pd.to_datetime(df['Date'])

        df.set_index('Date', inplace=True)

        df.sort_index(inplace=True)

        df.dropna(inplace=True)

    except Exception as e:

        print(f"Error loading data: {e}")

        return









    df['Log_AAPL'] = np.log(df['AAPL'])

    df['Log_MSFT'] = np.log(df['MSFT'])

    df['Spread'] = df['Log_AAPL'] - df['Log_MSFT']





    window = 20

    df['Mean'] = df['Spread'].rolling(window).mean()

    df['Std'] = df['Spread'].rolling(window).std()

    df['Z_Score'] = (df['Spread'] - df['Mean']) / df['Std']













    df['Signal'] = 0.0







    long_condition = df['Z_Score'] < -2.0

    short_condition = df['Z_Score'] > 2.0

    exit_condition = abs(df['Z_Score']) < 0.5



    current_signal = 0

    signals = []



    for i in range(len(df)):

        z = df['Z_Score'].iloc[i]



        if z < -2.0:

            current_signal = 1

        elif z > 2.0:

            current_signal = -1

        elif abs(z) < 0.5:

            current_signal = 0



        signals.append(current_signal)



    df['Position'] = signals





    df['Position'] = df['Position'].shift(1)







    df['AAPL_Ret'] = df['AAPL'].pct_change()

    df['MSFT_Ret'] = df['MSFT'].pct_change()

    df['Spread_Ret'] = df['AAPL_Ret'] - df['MSFT_Ret']



    df['Strategy_Return'] = df['Position'] * df['Spread_Ret']





    df['Strategy_Equity'] = (1 + df['Strategy_Return']).cumprod()





    total_return = (df['Strategy_Equity'].iloc[-1] - 1) * 100

    daily_sharpe = df['Strategy_Return'].mean() / df['Strategy_Return'].std()

    annualized_sharpe = daily_sharpe * np.sqrt(252)





    peak = df['Strategy_Equity'].cummax()

    drawdown = (df['Strategy_Equity'] - peak) / peak

    max_drawdown = drawdown.min() * 100



    print("\n--- AGENT 2 (MEAN REVERSION) RESULTS ---")

    print(f"Pair: AAPL vs MSFT")

    print(f"Period: {df.index[0].date()} to {df.index[-1].date()}")

    print(f"Total Return: {total_return:.2f}% (Market Neutral)")

    print(f"Sharpe Ratio: {annualized_sharpe:.2f}")

    print(f"Max Drawdown: {max_drawdown:.2f}%")



    if annualized_sharpe > 1.0:

         print("\nWINNER: Excellent Risk-Adjusted Returns!")

    elif annualized_sharpe > 0.5:

         print("\nRESULT: Decent Stability.")

    else:

         print("\nFAIL: Too much chop.")



if __name__ == "__main__":

    run_pairs_backtest()
