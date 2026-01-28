"""
HEDGE FUND ENSEMBLE STRATEGY
============================
Multi-model ensemble combining:
1. XGBoost (gradient boosting)
2. LightGBM (faster gradient boosting)
3. Neural Network (MLP for non-linear patterns)
4. Regime Detection (Hidden Markov Model style)

Features:
- 50+ technical indicators
- Macro regime detection (risk-on/risk-off)
- Volatility-adjusted position sizing
- Walk-forward validation

Hardware optimized for:
- RTX 3060 Ti (6GB VRAM)
- 16GB RAM
- Batch processing for memory efficiency
"""



import numpy as np

import pandas as pd

from typing import Dict, List, Tuple, Optional

from dataclasses import dataclass

from enum import Enum

import warnings

warnings.filterwarnings('ignore')



class MarketRegime(Enum):

    BULL_LOW_VOL = "bull_low_vol"

    BULL_HIGH_VOL = "bull_high_vol"

    BEAR_LOW_VOL = "bear_low_vol"

    BEAR_HIGH_VOL = "bear_high_vol"

    SIDEWAYS = "sideways"



@dataclass

class TradeSignal:

    timestamp: pd.Timestamp

    direction: int

    confidence: float

    regime: MarketRegime

    position_size: float

    stop_loss: float

    take_profit: float



class FeatureEngineering:

    """Advanced feature engineering for hedge fund strategy"""



    @staticmethod

    def add_all_features(df: pd.DataFrame) -> pd.DataFrame:

        """Add 50+ features for ML models"""

        df = df.copy()

        close = df['close']

        high = df['high']

        low = df['low']

        volume = df['volume']







        for period in [5, 10, 20, 50, 100, 200]:

            df[f'sma_{period}'] = close.rolling(period).mean()

            df[f'ema_{period}'] = close.ewm(span=period).mean()





        df['sma_cross_20_50'] = (df['sma_20'] > df['sma_50']).astype(int)

        df['sma_cross_50_200'] = (df['sma_50'] > df['sma_200']).astype(int)

        df['golden_cross'] = ((df['sma_50'] > df['sma_200']) &

                              (df['sma_50'].shift(1) <= df['sma_200'].shift(1))).astype(int)





        for period in [20, 50, 200]:

            df[f'price_vs_sma_{period}'] = (close - df[f'sma_{period}']) / df[f'sma_{period}']





        exp1 = close.ewm(span=12).mean()

        exp2 = close.ewm(span=26).mean()

        df['macd'] = exp1 - exp2

        df['macd_signal'] = df['macd'].ewm(span=9).mean()

        df['macd_hist'] = df['macd'] - df['macd_signal']

        df['macd_cross'] = ((df['macd'] > df['macd_signal']) &

                            (df['macd'].shift(1) <= df['macd_signal'].shift(1))).astype(int)





        df['atr_14'] = FeatureEngineering._atr(high, low, close, 14)

        df['adx'] = FeatureEngineering._adx(high, low, close, 14)







        for period in [7, 14, 21]:

            df[f'rsi_{period}'] = FeatureEngineering._rsi(close, period)





        df['rsi_oversold'] = (df['rsi_14'] < 30).astype(int)

        df['rsi_overbought'] = (df['rsi_14'] > 70).astype(int)





        df['stoch_k'], df['stoch_d'] = FeatureEngineering._stochastic(high, low, close, 14)





        df['williams_r'] = FeatureEngineering._williams_r(high, low, close, 14)





        for period in [5, 10, 20]:

            df[f'roc_{period}'] = (close - close.shift(period)) / close.shift(period) * 100





        for period in [10, 20]:

            df[f'momentum_{period}'] = close - close.shift(period)







        df['bb_middle'] = close.rolling(20).mean()

        bb_std = close.rolling(20).std()

        df['bb_upper'] = df['bb_middle'] + 2 * bb_std

        df['bb_lower'] = df['bb_middle'] - 2 * bb_std

        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']

        df['bb_position'] = (close - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])





        df['atr_pct'] = df['atr_14'] / close * 100





        for period in [10, 20, 60]:

            df[f'hvol_{period}'] = close.pct_change().rolling(period).std() * np.sqrt(252) * 100





        df['vol_ratio'] = df['hvol_10'] / df['hvol_60']







        df['volume_sma_20'] = volume.rolling(20).mean()

        df['volume_ratio'] = volume / df['volume_sma_20']





        df['obv'] = (np.sign(close.diff()) * volume).cumsum()

        df['obv_sma'] = df['obv'].rolling(20).mean()





        df['vpt'] = (close.pct_change() * volume).cumsum()







        for period in [1, 2, 3, 5, 10, 20]:

            df[f'return_{period}d'] = close.pct_change(period)





        df['higher_high'] = (high > high.shift(1)).astype(int)

        df['lower_low'] = (low < low.shift(1)).astype(int)





        df['gap'] = (df['open'] - close.shift(1)) / close.shift(1)





        df['daily_range'] = (high - low) / close

        df['range_vs_atr'] = (high - low) / df['atr_14']







        df['trend_strength'] = abs(df['price_vs_sma_50'])





        df['vol_regime'] = pd.cut(df['hvol_20'], bins=[0, 15, 25, 100], labels=[0, 1, 2]).astype(float)





        df['trend_direction'] = np.sign(df['sma_20'] - df['sma_50'])







        df['forward_return_1d'] = close.shift(-1) / close - 1

        df['forward_return_5d'] = close.shift(-5) / close - 1





        df['target'] = (df['forward_return_1d'] > 0).astype(int)



        return df



    @staticmethod

    def _rsi(series: pd.Series, period: int) -> pd.Series:

        delta = series.diff()

        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()

        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss

        return 100 - (100 / (1 + rs))



    @staticmethod

    def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:

        tr1 = high - low

        tr2 = abs(high - close.shift())

        tr3 = abs(low - close.shift())

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        return tr.rolling(period).mean()



    @staticmethod

    def _adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:

        plus_dm = high.diff()

        minus_dm = -low.diff()

        plus_dm[plus_dm < 0] = 0

        minus_dm[minus_dm < 0] = 0



        tr = FeatureEngineering._atr(high, low, close, 1) * period

        plus_di = 100 * (plus_dm.rolling(period).sum() / tr)

        minus_di = 100 * (minus_dm.rolling(period).sum() / tr)



        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)

        return dx.rolling(period).mean()



    @staticmethod

    def _stochastic(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> Tuple[pd.Series, pd.Series]:

        lowest_low = low.rolling(period).min()

        highest_high = high.rolling(period).max()

        stoch_k = 100 * (close - lowest_low) / (highest_high - lowest_low)

        stoch_d = stoch_k.rolling(3).mean()

        return stoch_k, stoch_d



    @staticmethod

    def _williams_r(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:

        highest_high = high.rolling(period).max()

        lowest_low = low.rolling(period).min()

        return -100 * (highest_high - close) / (highest_high - lowest_low)





class RegimeDetector:

    """Detect market regimes for adaptive strategy"""



    def __init__(self):

        self.lookback = 60



    def detect_regime(self, df: pd.DataFrame) -> MarketRegime:

        """Detect current market regime based on trend and volatility"""

        if len(df) < self.lookback:

            return MarketRegime.SIDEWAYS



        recent = df.tail(self.lookback)





        current_price = recent['close'].iloc[-1]

        sma_50 = recent['sma_50'].iloc[-1] if 'sma_50' in recent.columns else recent['close'].rolling(50).mean().iloc[-1]

        sma_200 = recent['sma_200'].iloc[-1] if 'sma_200' in recent.columns else recent['close'].rolling(200).mean().iloc[-1]





        current_vol = recent['close'].pct_change().std() * np.sqrt(252) * 100

        vol_threshold = 20



        is_bull = current_price > sma_50 and sma_50 > sma_200

        is_bear = current_price < sma_50 and sma_50 < sma_200

        is_high_vol = current_vol > vol_threshold



        if is_bull:

            return MarketRegime.BULL_HIGH_VOL if is_high_vol else MarketRegime.BULL_LOW_VOL

        elif is_bear:

            return MarketRegime.BEAR_HIGH_VOL if is_high_vol else MarketRegime.BEAR_LOW_VOL

        else:

            return MarketRegime.SIDEWAYS



    def get_regime_weights(self, regime: MarketRegime) -> Dict[str, float]:

        """Get model weights based on regime"""

        weights = {

            MarketRegime.BULL_LOW_VOL: {'xgb': 0.4, 'lgb': 0.3, 'nn': 0.3},

            MarketRegime.BULL_HIGH_VOL: {'xgb': 0.5, 'lgb': 0.3, 'nn': 0.2},

            MarketRegime.BEAR_LOW_VOL: {'xgb': 0.3, 'lgb': 0.4, 'nn': 0.3},

            MarketRegime.BEAR_HIGH_VOL: {'xgb': 0.5, 'lgb': 0.4, 'nn': 0.1},

            MarketRegime.SIDEWAYS: {'xgb': 0.33, 'lgb': 0.33, 'nn': 0.34},

        }

        return weights.get(regime, weights[MarketRegime.SIDEWAYS])





class PositionSizer:

    """Kelly criterion based position sizing with volatility adjustment"""



    def __init__(self, max_position: float = 0.2, max_risk_per_trade: float = 0.02):

        self.max_position = max_position

        self.max_risk_per_trade = max_risk_per_trade



    def calculate_position_size(self, confidence: float, volatility: float,

                                 win_rate: float = 0.55, avg_win_loss_ratio: float = 1.5) -> float:

        """
        Calculate position size using modified Kelly criterion

        Args:
            confidence: Model confidence (0-1)
            volatility: Current annualized volatility
            win_rate: Historical win rate
            avg_win_loss_ratio: Average win / average loss

        Returns:
            Position size as fraction of capital (0 to max_position)
        """



        kelly = (win_rate * avg_win_loss_ratio - (1 - win_rate)) / avg_win_loss_ratio





        half_kelly = kelly / 2





        confidence_adjusted = half_kelly * confidence





        vol_factor = min(1.0, 20 / volatility) if volatility > 0 else 1.0

        vol_adjusted = confidence_adjusted * vol_factor





        return min(self.max_position, max(0, vol_adjusted))



    def calculate_stop_loss(self, entry_price: float, atr: float, multiplier: float = 2.0) -> float:

        """ATR-based stop loss"""

        return entry_price - (atr * multiplier)



    def calculate_take_profit(self, entry_price: float, stop_loss: float, risk_reward: float = 2.0) -> float:

        """Risk-reward based take profit"""

        risk = entry_price - stop_loss

        return entry_price + (risk * risk_reward)





class HedgeFundEnsemble:

    """
    Main ensemble strategy combining multiple models
    """



    def __init__(self, use_gpu: bool = True):

        self.use_gpu = use_gpu

        self.feature_engineer = FeatureEngineering()

        self.regime_detector = RegimeDetector()

        self.position_sizer = PositionSizer()



        self.models = {}

        self.feature_cols = []

        self.is_trained = False





        self.train_metrics = {}

        self.val_metrics = {}



    def get_feature_columns(self, df: pd.DataFrame) -> List[str]:

        """Get feature columns for training"""

        exclude = ['date', 'target', 'forward_return_1d', 'forward_return_5d',

                   'open', 'high', 'low', 'close', 'volume']

        return [col for col in df.columns if col not in exclude and df[col].dtype in ['float64', 'int64', 'float32', 'int32']]



    def prepare_data(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:

        """Prepare train/val/test splits with walk-forward methodology"""



        df = self.feature_engineer.add_all_features(df)





        df = df.dropna()





        self.feature_cols = self.get_feature_columns(df)





        n = len(df)

        train_end = int(n * 0.6)

        val_end = int(n * 0.8)



        train = df.iloc[:train_end]

        val = df.iloc[train_end:val_end]

        test = df.iloc[val_end:]



        return train, val, test



    def train(self, df: pd.DataFrame) -> Dict:

        """Train all ensemble models"""

        print("=" * 60)

        print("HEDGE FUND ENSEMBLE TRAINING")

        print("=" * 60)



        train, val, test = self.prepare_data(df)



        X_train = train[self.feature_cols]

        y_train = train['target']

        X_val = val[self.feature_cols]

        y_val = val['target']

        X_test = test[self.feature_cols]

        y_test = test['target']



        print(f"\nDataset sizes:")

        print(f"  Train: {len(train)} samples ({train.index[0]} to {train.index[-1]})")

        print(f"  Val:   {len(val)} samples")

        print(f"  Test:  {len(test)} samples")

        print(f"  Features: {len(self.feature_cols)}")



        results = {}





        print("\n[1/3] Training XGBoost...")

        results['xgb'] = self._train_xgboost(X_train, y_train, X_val, y_val)





        print("\n[2/3] Training LightGBM...")

        results['lgb'] = self._train_lightgbm(X_train, y_train, X_val, y_val)





        print("\n[3/3] Training Neural Network...")

        results['nn'] = self._train_neural_net(X_train, y_train, X_val, y_val)





        print("\n" + "=" * 60)

        print("ENSEMBLE EVALUATION ON TEST SET")

        print("=" * 60)



        ensemble_results = self._evaluate_ensemble(X_test, y_test, test)

        results['ensemble'] = ensemble_results



        self.is_trained = True

        return results



    def _train_xgboost(self, X_train, y_train, X_val, y_val) -> Dict:

        """Train XGBoost with GPU acceleration"""

        try:

            import xgboost as xgb

        except ImportError:

            print("  XGBoost not installed, skipping...")

            return {'accuracy': 0.5}



        params = {

            'objective': 'binary:logistic',

            'eval_metric': 'auc',

            'max_depth': 6,

            'learning_rate': 0.05,

            'subsample': 0.8,

            'colsample_bytree': 0.8,

            'min_child_weight': 3,

            'reg_alpha': 0.1,

            'reg_lambda': 1.0,

            'n_estimators': 500,

            'early_stopping_rounds': 50,

            'verbosity': 0,

        }



        if self.use_gpu:

            params['tree_method'] = 'hist'

            params['device'] = 'cuda'



        model = xgb.XGBClassifier(**params)

        model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)



        self.models['xgb'] = model



        train_acc = (model.predict(X_train) == y_train).mean()

        val_acc = (model.predict(X_val) == y_val).mean()



        print(f"  Train Accuracy: {train_acc:.4f}")

        print(f"  Val Accuracy:   {val_acc:.4f}")



        return {'train_acc': train_acc, 'val_acc': val_acc}



    def _train_lightgbm(self, X_train, y_train, X_val, y_val) -> Dict:

        """Train LightGBM"""

        try:

            import lightgbm as lgb

        except ImportError:

            print("  LightGBM not installed, skipping...")

            return {'accuracy': 0.5}



        params = {

            'objective': 'binary',

            'metric': 'auc',

            'boosting_type': 'gbdt',

            'num_leaves': 31,

            'learning_rate': 0.05,

            'feature_fraction': 0.8,

            'bagging_fraction': 0.8,

            'bagging_freq': 5,

            'min_child_samples': 20,

            'reg_alpha': 0.1,

            'reg_lambda': 1.0,

            'n_estimators': 500,

            'verbosity': -1,

        }



        if self.use_gpu:

            params['device'] = 'gpu'



        model = lgb.LGBMClassifier(**params)



        try:

            model.fit(X_train, y_train, eval_set=[(X_val, y_val)],

                     callbacks=[lgb.early_stopping(50, verbose=False)])

        except:



            params.pop('device', None)

            model = lgb.LGBMClassifier(**params)

            model.fit(X_train, y_train, eval_set=[(X_val, y_val)],

                     callbacks=[lgb.early_stopping(50, verbose=False)])



        self.models['lgb'] = model



        train_acc = (model.predict(X_train) == y_train).mean()

        val_acc = (model.predict(X_val) == y_val).mean()



        print(f"  Train Accuracy: {train_acc:.4f}")

        print(f"  Val Accuracy:   {val_acc:.4f}")



        return {'train_acc': train_acc, 'val_acc': val_acc}



    def _train_neural_net(self, X_train, y_train, X_val, y_val) -> Dict:

        """Train a simple MLP neural network"""

        try:

            from sklearn.neural_network import MLPClassifier

            from sklearn.preprocessing import StandardScaler

        except ImportError:

            print("  sklearn not installed, skipping...")

            return {'accuracy': 0.5}





        scaler = StandardScaler()

        X_train_scaled = scaler.fit_transform(X_train)

        X_val_scaled = scaler.transform(X_val)



        self.nn_scaler = scaler



        model = MLPClassifier(

            hidden_layer_sizes=(128, 64, 32),

            activation='relu',

            solver='adam',

            alpha=0.001,

            batch_size=64,

            learning_rate='adaptive',

            learning_rate_init=0.001,

            max_iter=200,

            early_stopping=True,

            validation_fraction=0.1,

            n_iter_no_change=20,

            verbose=False,

            random_state=42

        )



        model.fit(X_train_scaled, y_train)

        self.models['nn'] = model



        train_acc = (model.predict(X_train_scaled) == y_train).mean()

        val_acc = (model.predict(X_val_scaled) == y_val).mean()



        print(f"  Train Accuracy: {train_acc:.4f}")

        print(f"  Val Accuracy:   {val_acc:.4f}")



        return {'train_acc': train_acc, 'val_acc': val_acc}



    def _evaluate_ensemble(self, X_test, y_test, test_df) -> Dict:

        """Evaluate ensemble performance with backtesting"""



        predictions = {}

        probabilities = {}



        for name, model in self.models.items():

            if name == 'nn':

                X_scaled = self.nn_scaler.transform(X_test)

                predictions[name] = model.predict(X_scaled)

                probabilities[name] = model.predict_proba(X_scaled)[:, 1]

            else:

                predictions[name] = model.predict(X_test)

                probabilities[name] = model.predict_proba(X_test)[:, 1]





        if probabilities:

            avg_prob = np.mean(list(probabilities.values()), axis=0)

            ensemble_pred = (avg_prob > 0.5).astype(int)





            accuracy = (ensemble_pred == y_test).mean()





            test_returns = test_df['forward_return_1d'].values







            positions = (avg_prob - 0.5) * 2

            strategy_returns = positions[:-1] * test_returns[1:]





            position_changes = np.abs(np.diff(np.concatenate([[0], positions[:-1]])))

            transaction_costs = position_changes * 0.001



            min_len = min(len(strategy_returns), len(transaction_costs))

            strategy_returns_net = strategy_returns[:min_len] - transaction_costs[:min_len]





            cumulative_return = (1 + strategy_returns_net).prod() - 1

            sharpe = strategy_returns_net.mean() / strategy_returns_net.std() * np.sqrt(252) if strategy_returns_net.std() > 0 else 0





            cumulative = (1 + strategy_returns_net).cumprod()

            running_max = np.maximum.accumulate(cumulative)

            drawdowns = (cumulative - running_max) / running_max

            max_drawdown = drawdowns.min()





            winning_trades = (strategy_returns_net > 0).sum()

            total_trades = (strategy_returns_net != 0).sum()

            win_rate = winning_trades / total_trades if total_trades > 0 else 0



            print(f"\n{'='*40}")

            print("ENSEMBLE RESULTS")

            print(f"{'='*40}")

            print(f"Accuracy:          {accuracy:.4f} ({accuracy*100:.1f}%)")

            print(f"Cumulative Return: {cumulative_return*100:.2f}%")

            print(f"Sharpe Ratio:      {sharpe:.2f}")

            print(f"Max Drawdown:      {max_drawdown*100:.2f}%")

            print(f"Win Rate:          {win_rate*100:.1f}%")

            print(f"Total Trades:      {total_trades}")



            return {

                'accuracy': accuracy,

                'cumulative_return': cumulative_return,

                'sharpe': sharpe,

                'max_drawdown': max_drawdown,

                'win_rate': win_rate,

                'total_trades': int(total_trades)

            }



        return {'accuracy': 0.5}



    def predict(self, df: pd.DataFrame) -> TradeSignal:

        """Generate trading signal for current market state"""

        if not self.is_trained:

            raise ValueError("Model not trained. Call train() first.")





        df = self.feature_engineer.add_all_features(df)

        df = df.dropna()



        if len(df) == 0:

            return TradeSignal(

                timestamp=pd.Timestamp.now(),

                direction=0,

                confidence=0.0,

                regime=MarketRegime.SIDEWAYS,

                position_size=0.0,

                stop_loss=0.0,

                take_profit=0.0

            )





        latest = df.iloc[-1:]

        X = latest[self.feature_cols]





        regime = self.regime_detector.detect_regime(df)

        weights = self.regime_detector.get_regime_weights(regime)





        probs = []

        for name, model in self.models.items():

            if name == 'nn':

                X_scaled = self.nn_scaler.transform(X)

                prob = model.predict_proba(X_scaled)[0, 1]

            else:

                prob = model.predict_proba(X)[0, 1]

            probs.append(prob * weights.get(name, 0.33))





        ensemble_prob = sum(probs)





        if ensemble_prob > 0.55:

            direction = 1

            confidence = (ensemble_prob - 0.5) * 2

        elif ensemble_prob < 0.45:

            direction = -1

            confidence = (0.5 - ensemble_prob) * 2

        else:

            direction = 0

            confidence = 0.0





        current_vol = df['hvol_20'].iloc[-1] if 'hvol_20' in df.columns else 20

        position_size = self.position_sizer.calculate_position_size(confidence, current_vol)





        entry_price = df['close'].iloc[-1]

        atr = df['atr_14'].iloc[-1] if 'atr_14' in df.columns else entry_price * 0.02

        stop_loss = self.position_sizer.calculate_stop_loss(entry_price, atr)

        take_profit = self.position_sizer.calculate_take_profit(entry_price, stop_loss)



        return TradeSignal(

            timestamp=pd.Timestamp.now(),

            direction=direction,

            confidence=confidence,

            regime=regime,

            position_size=position_size,

            stop_loss=stop_loss,

            take_profit=take_profit

        )





def main():

    """Main training script"""

    import os





    data_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'csv', 'SPY.csv')



    if not os.path.exists(data_path):

        print(f"Data file not found: {data_path}")

        return



    print("Loading SPY data...")

    df = pd.read_csv(data_path, parse_dates=['date'], index_col='date')

    print(f"Loaded {len(df)} rows from {df.index[0]} to {df.index[-1]}")





    strategy = HedgeFundEnsemble(use_gpu=True)

    results = strategy.train(df)





    print("\n" + "=" * 60)

    print("CURRENT TRADING SIGNAL")

    print("=" * 60)



    signal = strategy.predict(df)

    print(f"Direction:     {'LONG' if signal.direction == 1 else 'SHORT' if signal.direction == -1 else 'FLAT'}")

    print(f"Confidence:    {signal.confidence:.2f}")

    print(f"Regime:        {signal.regime.value}")

    print(f"Position Size: {signal.position_size*100:.1f}%")

    print(f"Stop Loss:     ${signal.stop_loss:.2f}")

    print(f"Take Profit:   ${signal.take_profit:.2f}")



    return results





if __name__ == "__main__":

    main()
