"""
Save trained models to disk
"""

import os

import sys

import json

import joblib

from datetime import datetime





sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))



import pandas as pd

from hedge_fund_v2 import train_ensemble





data_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'csv', 'SPY.csv')

df = pd.read_csv(data_path, parse_dates=['date'], index_col='date')



print("Training models...")

results = train_ensemble(df)





save_dir = os.path.join(os.path.dirname(__file__), '..', 'models')

os.makedirs(save_dir, exist_ok=True)



timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')





xgb_path = os.path.join(save_dir, f'xgb_{timestamp}.json')

results['models']['xgb'].save_model(xgb_path)

print(f'Saved XGBoost: {xgb_path}')





lgb_path = os.path.join(save_dir, f'lgb_{timestamp}.txt')

results['models']['lgb'].booster_.save_model(lgb_path)

print(f'Saved LightGBM: {lgb_path}')





nn_path = os.path.join(save_dir, f'nn_{timestamp}.pkl')

scaler_path = os.path.join(save_dir, f'scaler_{timestamp}.pkl')

joblib.dump(results['models']['nn'], nn_path)

joblib.dump(results['scaler'], scaler_path)

print(f'Saved Neural Net: {nn_path}')

print(f'Saved Scaler: {scaler_path}')





meta = {

    'timestamp': timestamp,

    'features': results['features'],

    'metrics': {

        'accuracy': float(results['accuracy']),

        'confident_accuracy': float(results['confident_accuracy']),

        'cumulative_return': float(results['return']),

        'sharpe': float(results['sharpe']),

        'max_drawdown': float(results['max_dd']),

        'win_rate': float(results['win_rate'])

    },

    'files': {

        'xgb': f'xgb_{timestamp}.json',

        'lgb': f'lgb_{timestamp}.txt',

        'nn': f'nn_{timestamp}.pkl',

        'scaler': f'scaler_{timestamp}.pkl'

    }

}



meta_path = os.path.join(save_dir, f'hedge_fund_v2_{timestamp}.json')

with open(meta_path, 'w') as f:

    json.dump(meta, f, indent=2)

print(f'Saved metadata: {meta_path}')





latest_path = os.path.join(save_dir, 'hedge_fund_v2_latest.json')

with open(latest_path, 'w') as f:

    json.dump(meta, f, indent=2)

print(f'Saved latest pointer: {latest_path}')



print(f'\n✅ All models saved to {save_dir}/')
