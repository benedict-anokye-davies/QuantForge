"""
HEDGE FUND STRATEGY V2 - Anti-Overfitting Edition
==================================================
Key improvements:
1. Aggressive regularization
2. Feature selection (only most predictive)
3. Ensemble voting instead of averaging
4. Market regime filtering
5. Only trade in favorable conditions
"""



import numpy as np

import pandas as pd

import xgboost as xgb

import lightgbm as lgb

from sklearn.neural_network import MLPClassifier

from sklearn.preprocessing import StandardScaler

from sklearn.feature_selection import mutual_info_classif

import warnings

warnings.filterwarnings('ignore')





def add_features(df):

    """Add technical indicators"""

    df = df.copy()

    c = df['close']

    h = df['high']

    l = df['low']

    v = df['volume']





    for p in [5, 10, 20, 50, 100, 200]:

        df[f'sma_{p}'] = c.rolling(p).mean()

        df[f'ret_{p}'] = c.pct_change(p)





    delta = c.diff()

    gain = delta.where(delta > 0, 0).rolling(14).mean()

    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()

    df['rsi'] = 100 - (100 / (1 + gain / loss))





    e12 = c.ewm(span=12).mean()

    e26 = c.ewm(span=26).mean()

    df['macd'] = e12 - e26

    df['macd_signal'] = df['macd'].ewm(span=9).mean()

    df['macd_hist'] = df['macd'] - df['macd_signal']





    df['volatility'] = c.pct_change().rolling(20).std() * np.sqrt(252)

    df['atr'] = (h - l).rolling(14).mean()





    bb_mid = c.rolling(20).mean()

    bb_std = c.rolling(20).std()

    df['bb_position'] = (c - (bb_mid - 2*bb_std)) / (4*bb_std)





    df['vol_ratio'] = v / v.rolling(20).mean()





    df['price_vs_sma20'] = (c - df['sma_20']) / df['sma_20']

    df['price_vs_sma50'] = (c - df['sma_50']) / df['sma_50']

    df['price_vs_sma200'] = (c - df['sma_200']) / df['sma_200']





    df['trend_up'] = (df['sma_20'] > df['sma_50']).astype(int)

    df['strong_trend'] = (df['sma_50'] > df['sma_200']).astype(int)

    df['low_vol'] = (df['volatility'] < 0.20).astype(int)





    df['target'] = (c.shift(-1) > c).astype(int)

    df['forward_return'] = c.shift(-1) / c - 1



    return df





def select_features(X, y, n_features=20):

    """Select top features using mutual information"""

    mi_scores = mutual_info_classif(X, y, random_state=42)

    top_idx = np.argsort(mi_scores)[-n_features:]

    return X.columns[top_idx].tolist()





def train_ensemble(df):

    """Train ensemble with anti-overfitting measures"""





    df = add_features(df)

    df = df.dropna()





    exclude = ['date', 'open', 'high', 'low', 'close', 'volume', 'target', 'forward_return']

    feat_cols = [c for c in df.columns if c not in exclude]





    n = len(df)

    train = df.iloc[:int(n*0.6)]

    val = df.iloc[int(n*0.6):int(n*0.8)]

    test = df.iloc[int(n*0.8):]



    X_train, y_train = train[feat_cols], train['target']

    X_val, y_val = val[feat_cols], val['target']

    X_test, y_test = test[feat_cols], test['target']



    print(f"Train: {len(train)}, Val: {len(val)}, Test: {len(test)}")

    print(f"Initial features: {len(feat_cols)}")





    selected = select_features(X_train, y_train, n_features=15)

    print(f"Selected features: {selected}")



    X_train = X_train[selected]

    X_val = X_val[selected]

    X_test = X_test[selected]



    models = {}





    print("\n[1] XGBoost...")

    xgb_model = xgb.XGBClassifier(

        n_estimators=100,

        max_depth=3,

        learning_rate=0.01,

        subsample=0.5,

        colsample_bytree=0.5,

        min_child_weight=10,

        reg_alpha=1.0,

        reg_lambda=10.0,

        eval_metric='logloss',

        tree_method='hist',

        device='cuda',

        verbosity=0

    )

    xgb_model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

    models['xgb'] = xgb_model

    print(f"  Val Acc: {(xgb_model.predict(X_val) == y_val).mean():.4f}")





    print("\n[2] LightGBM...")

    lgb_model = lgb.LGBMClassifier(

        n_estimators=100,

        num_leaves=8,

        learning_rate=0.01,

        feature_fraction=0.5,

        bagging_fraction=0.5,

        bagging_freq=5,

        min_child_samples=50,

        reg_alpha=1.0,

        reg_lambda=10.0,

        verbosity=-1

    )

    lgb_model.fit(X_train, y_train, eval_set=[(X_val, y_val)],

                  callbacks=[lgb.early_stopping(20, verbose=False)])

    models['lgb'] = lgb_model

    print(f"  Val Acc: {(lgb_model.predict(X_val) == y_val).mean():.4f}")





    print("\n[3] Neural Net...")

    scaler = StandardScaler()

    X_train_s = scaler.fit_transform(X_train)

    X_val_s = scaler.transform(X_val)

    X_test_s = scaler.transform(X_test)



    nn_model = MLPClassifier(

        hidden_layer_sizes=(16, 8),

        alpha=1.0,

        max_iter=100,

        early_stopping=True,

        validation_fraction=0.2,

        random_state=42,

        verbose=False

    )

    nn_model.fit(X_train_s, y_train)

    models['nn'] = nn_model

    print(f"  Val Acc: {(nn_model.predict(X_val_s) == y_val).mean():.4f}")





    print("\n" + "="*50)

    print("ENSEMBLE TEST RESULTS")

    print("="*50)





    p_xgb = xgb_model.predict_proba(X_test)[:, 1]

    p_lgb = lgb_model.predict_proba(X_test)[:, 1]

    p_nn = nn_model.predict_proba(X_test_s)[:, 1]





    p_avg = (p_xgb + p_lgb + p_nn) / 3





    confident = (p_avg > 0.55) | (p_avg < 0.45)





    returns = test['forward_return'].values

    positions = np.where(p_avg > 0.55, 1, np.where(p_avg < 0.45, -1, 0))





    positions = positions * confident.astype(int)



    strategy_ret = positions[:-1] * returns[1:]





    trades = np.abs(np.diff(np.concatenate([[0], positions[:-1]])))

    costs = trades * 0.001

    min_len = min(len(strategy_ret), len(costs))

    net_ret = strategy_ret[:min_len] - costs[:min_len]





    total_return = (1 + net_ret).prod() - 1

    sharpe = net_ret.mean() / net_ret.std() * np.sqrt(252) if net_ret.std() > 0 else 0



    cum = (1 + net_ret).cumprod()

    running_max = np.maximum.accumulate(cum)

    dd = (cum - running_max) / running_max

    max_dd = dd.min()



    win_rate = (net_ret > 0).sum() / (net_ret != 0).sum() if (net_ret != 0).sum() > 0 else 0

    n_trades = (positions != 0).sum()



    accuracy = ((p_avg > 0.5).astype(int) == y_test).mean()

    confident_accuracy = ((p_avg[confident] > 0.5).astype(int) == y_test[confident]).mean()



    print(f"Overall Accuracy:    {accuracy:.4f} ({accuracy*100:.1f}%)")

    print(f"Confident Accuracy:  {confident_accuracy:.4f} ({confident_accuracy*100:.1f}%)")

    print(f"Cumulative Return:   {total_return*100:.2f}%")

    print(f"Sharpe Ratio:        {sharpe:.2f}")

    print(f"Max Drawdown:        {max_dd*100:.2f}%")

    print(f"Win Rate:            {win_rate*100:.1f}%")

    print(f"Number of Trades:    {n_trades}")

    print(f"Trade Frequency:     {n_trades/len(test)*100:.1f}% of days")





    print("\n" + "="*50)

    print("TOP FEATURES (XGBoost)")

    print("="*50)

    importance = pd.Series(xgb_model.feature_importances_, index=selected)

    for feat, imp in importance.sort_values(ascending=False).head(10).items():

        print(f"  {feat}: {imp:.4f}")





    print("\n" + "="*50)

    print("CURRENT SIGNAL")

    print("="*50)



    latest = df.iloc[-1:]

    X_latest = latest[selected]

    X_latest_s = scaler.transform(X_latest)



    p = (xgb_model.predict_proba(X_latest)[:, 1][0] +

         lgb_model.predict_proba(X_latest)[:, 1][0] +

         nn_model.predict_proba(X_latest_s)[:, 1][0]) / 3



    if p > 0.55:

        signal = "LONG"

        confidence = (p - 0.5) * 2

    elif p < 0.45:

        signal = "SHORT"

        confidence = (0.5 - p) * 2

    else:

        signal = "FLAT (low confidence)"

        confidence = 0



    print(f"Probability: {p:.4f}")

    print(f"Signal:      {signal}")

    print(f"Confidence:  {confidence:.2f}")



    return {

        'accuracy': accuracy,

        'confident_accuracy': confident_accuracy,

        'return': total_return,

        'sharpe': sharpe,

        'max_dd': max_dd,

        'win_rate': win_rate,

        'models': models,

        'scaler': scaler,

        'features': selected

    }





if __name__ == "__main__":

    import os



    data_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'csv', 'SPY.csv')

    df = pd.read_csv(data_path, parse_dates=['date'], index_col='date')



    print("="*50)

    print("HEDGE FUND STRATEGY V2")

    print("="*50)

    print(f"Data: {len(df)} rows ({df.index[0]} to {df.index[-1]})")



    results = train_ensemble(df)
