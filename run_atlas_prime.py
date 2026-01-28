import pandas as pd

import numpy as np



def run_atlas_prime():

    print("Running ATLAS ADAPTIVE PRIME Strategy...")

    print("Initializing Regime Detection & Dynamic Rotation...")





    try:

        df = pd.read_csv('quantforge/data/csv/ATLAS_UNIVERSE.csv', header=2)











        df = df.iloc[:, [0, 1, 2, 3]]

        df.columns = ['Date', 'GLD', 'SPY', 'TLT']

        df['Date'] = pd.to_datetime(df['Date'])

        df.set_index('Date', inplace=True)

        df.sort_index(inplace=True)

        df.dropna(inplace=True)

    except Exception as e:

        print(f"Error: {e}")

        return









    lookback = 60

    df['Mom_SPY'] = df['SPY'].pct_change(lookback)

    df['Mom_TLT'] = df['TLT'].pct_change(lookback)

    df['Mom_GLD'] = df['GLD'].pct_change(lookback)





    df['Vol_SPY'] = df['SPY'].pct_change().rolling(20).std() * np.sqrt(252)

















    positions = []



    for i in range(len(df)):

        vol = df['Vol_SPY'].iloc[i]





        if vol < 0.15:





            moms = {'SPY': df['Mom_SPY'].iloc[i], 'TLT': df['Mom_TLT'].iloc[i], 'GLD': df['Mom_GLD'].iloc[i]}

            best_asset = max(moms, key=moms.get)





            if moms[best_asset] > 0:

                positions.append(best_asset)

            else:

                positions.append('CASH')



        else:









            if df['Mom_GLD'].iloc[i] > 0:

                positions.append('GLD')

            elif df['Mom_TLT'].iloc[i] > 0:

                positions.append('TLT')

            else:

                positions.append('CASH')



    df['Position'] = positions





    df['Position'] = df['Position'].shift(1)





    returns = []

    for i in range(len(df)):

        pos = df['Position'].iloc[i]

        if pos == 'SPY':

            ret = df['SPY'].pct_change().iloc[i]

        elif pos == 'TLT':

            ret = df['TLT'].pct_change().iloc[i]

        elif pos == 'GLD':

            ret = df['GLD'].pct_change().iloc[i]

        else:

            ret = 0.0

        returns.append(ret)



    df['Strategy_Ret'] = returns

    df['Strategy_Equity'] = (1 + df['Strategy_Ret']).cumprod()





    df['Benchmark_Equity'] = (1 + df['SPY'].pct_change()).cumprod()





    total_ret = (df['Strategy_Equity'].iloc[-1] - 1) * 100

    bench_ret = (df['Benchmark_Equity'].iloc[-1] - 1) * 100



    daily_sharpe = df['Strategy_Ret'].mean() / df['Strategy_Ret'].std()

    sharpe = daily_sharpe * np.sqrt(252)



    peak = df['Strategy_Equity'].cummax()

    dd = (df['Strategy_Equity'] - peak) / peak

    max_dd = dd.min() * 100



    print("\n--- ATLAS ADAPTIVE PRIME RESULTS ---")

    print(f"Total Return: {total_ret:.2f}%")

    print(f"Benchmark:    {bench_ret:.2f}%")

    print(f"Sharpe Ratio: {sharpe:.2f}")

    print(f"Max Drawdown: {max_dd:.2f}%")



    if total_ret > bench_ret and max_dd > -15:

        print("\n🏆 VERDICT: HOLY GRAIL STATUS.")

        print("We beat the market with HALF the risk.")

    elif total_ret > bench_ret:

        print("\n✅ VERDICT: Strong Outperformance.")

    else:

        print("\n❌ VERDICT: Back to the lab.")



if __name__ == "__main__":

    run_atlas_prime()
