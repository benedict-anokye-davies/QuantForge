import pandas as pd

import numpy as np

import xgboost as xgb

from sklearn.model_selection import train_test_split

from sklearn.metrics import accuracy_score, classification_report

import time



def train_gpu_model():

    print("Initializing GPU Training on NVIDIA RTX 3060 Ti...")





    try:



        df = pd.read_csv('quantforge/data/csv/SPY_FULL_FEATURES.csv')

        df['Date'] = pd.to_datetime(df['Date'])

        df.set_index('Date', inplace=True)





        df.rename(columns={'SPY_Close': 'Close', 'SPY_Volume': 'Volume'}, inplace=True)



    except Exception as e:

        print(f"Error loading data: {e}")

        return





    print("Generating features...")

    df['Returns'] = df['Close'].pct_change()





    for w in [5, 10, 20, 50, 200]:

        df[f'Mom_{w}'] = df['Close'].pct_change(w)





    for w in [10, 20, 30, 60]:

        df[f'Vol_{w}'] = df['Returns'].rolling(w).std()





    df['Vol_Ratio'] = df['Volume'] / df['Volume'].rolling(20).mean()







    if 'High' in df.columns and 'Low' in df.columns:

        df['Range'] = (df['High'] - df['Low']) / df['Close']







    df['Rates_x_Mom'] = df['Fed_Rate'] * df['Mom_20']





    df['VIX_x_Vol'] = df['VIX'] * df['Vol_20']





    df['Target'] = np.where(df['Returns'].shift(-1) > 0, 1, 0)



    df.dropna(inplace=True)







    drop_cols = ['Target', 'Returns', 'Close', 'Volume', 'Open', 'High', 'Low']

    feature_cols = [c for c in df.columns if c not in drop_cols]



    print(f"Features: {feature_cols}")

    X = df[feature_cols]

    y = df['Target']





    split = int(len(df) * 0.8)

    X_train, X_test = X.iloc[:split], X.iloc[split:]

    y_train, y_test = y.iloc[:split], y.iloc[split:]



    print(f"Training on {len(X_train)} samples with {len(feature_cols)} features...")











    sample_weights = np.where(y_train == 0, 1.5, 1.0)







    params = {

        'tree_method': 'hist',

        'device': 'cuda',

        'n_estimators': 5000,

        'learning_rate': 0.005,

        'max_depth': 4,

        'subsample': 0.7,

        'colsample_bytree': 0.7,

        'eval_metric': 'logloss',

        'early_stopping_rounds': 50,



    }



    model = xgb.XGBClassifier(**params)



    start_time = time.time()





    model.fit(

        X_train, y_train,



        eval_set=[(X_test, y_test)],

        verbose=100

    )



    end_time = time.time()

    print(f"\nTraining Complete in {end_time - start_time:.2f} seconds.")





    preds = model.predict(X_test)

    acc = accuracy_score(y_test, preds)



    print(f"\nGPU Model Accuracy: {acc*100:.2f}%")

    print("\nClassification Report:")

    print(classification_report(y_test, preds))





    print("\nTop 5 Alpha Factors:")

    importance = pd.Series(model.feature_importances_, index=feature_cols).sort_values(ascending=False)

    print(importance.head(5))





    model.save_model("quantforge/strategies/spy_gpu_model.json")

    print("\nModel saved to quantforge/strategies/spy_gpu_model.json")



if __name__ == "__main__":

    train_gpu_model()
