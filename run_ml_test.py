import pandas as pd

import numpy as np

try:

    import xgboost as xgb

except ImportError:

    print("XGBoost not found. Please pip install xgboost")

    exit()



from sklearn.model_selection import train_test_split

from sklearn.metrics import accuracy_score



def run_ml_backtest():

    print("Running Agent 3 Backtest (XGBoost ML Strategy)...")





    try:



        df = pd.read_csv('quantforge/data/csv/SPY.csv', header=2)

        df.columns = ['Date', 'Close', 'High', 'Low', 'Open', 'Volume']

        df['Date'] = pd.to_datetime(df['Date'])

        df.set_index('Date', inplace=True)

        df.sort_index(inplace=True)





        cols = ['Close', 'High', 'Low', 'Open', 'Volume']

        for c in cols:

            df[c] = pd.to_numeric(df[c], errors='coerce')

        df.dropna(inplace=True)



    except Exception as e:

        print(f"Error loading data: {e}")

        return





    df['Returns'] = df['Close'].pct_change()





    df['Mom_5'] = df['Close'].pct_change(5)

    df['Mom_20'] = df['Close'].pct_change(20)





    df['Vol_20'] = df['Returns'].rolling(20).std()





    df['Range'] = (df['High'] - df['Low']) / df['Close']





    df['Target'] = np.where(df['Returns'].shift(-1) > 0, 1, 0)





    df.dropna(inplace=True)







    split_idx = int(len(df) * 0.70)



    features = ['Mom_5', 'Mom_20', 'Vol_20', 'Range']

    X = df[features]

    y = df['Target']



    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]

    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]



    print(f"Training on {len(X_train)} days, Testing on {len(X_test)} days...")





    model = xgb.XGBClassifier(

        n_estimators=100,

        learning_rate=0.05,

        max_depth=3,

        random_state=42,

        eval_metric='logloss'

    )



    model.fit(X_train, y_train)







    preds = model.predict(X_test)





    acc = accuracy_score(y_test, preds)

    print(f"Model Accuracy on Test Data: {acc*100:.2f}% (Random is 50%)")







    test_returns = df['Returns'].iloc[split_idx:]

    strategy_returns = preds * test_returns





    strategy_equity = (1 + strategy_returns).cumprod()

    benchmark_equity = (1 + test_returns).cumprod()



    total_return = (strategy_equity.iloc[-1] - 1) * 100

    benchmark_return = (benchmark_equity.iloc[-1] - 1) * 100



    daily_sharpe = strategy_returns.mean() / strategy_returns.std()

    annualized_sharpe = daily_sharpe * np.sqrt(252)





    peak = strategy_equity.cummax()

    dd = (strategy_equity - peak) / peak

    max_dd = dd.min() * 100



    print("\n--- AGENT 3 (AI/ML) RESULTS ---")

    print(f"Asset: SPY (Out-of-Sample Test)")

    print(f"Total Return: {total_return:.2f}%")

    print(f"Benchmark (Buy&Hold): {benchmark_return:.2f}%")

    print(f"Sharpe Ratio: {annualized_sharpe:.2f}")

    print(f"Max Drawdown: {max_dd:.2f}%")



    if total_return > benchmark_return:

        print("\n🏆 WINNER: AI Beat the Market!")

    elif annualized_sharpe > 1.0:

        print("\n🥈 RUNNER UP: Lower return but safer ride.")

    else:

        print("\n❌ FAIL: AI hallucinated profit.")



if __name__ == "__main__":

    run_ml_backtest()
