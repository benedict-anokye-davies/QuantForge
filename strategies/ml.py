"""
Machine Learning Strategy
Uses sklearn models for prediction
"""



from typing import Optional, Dict, Any

import pandas as pd

import numpy as np



from .base import Strategy, StrategyConfig

from ..core.events import MarketEvent, SignalEvent





class MLStrategy(Strategy):

    """
    Machine Learning Strategy
    Uses predictive models for signal generation
    """



    def __init__(

        self,

        symbols: list = None,

        model_type: str = 'random_forest',

        lookback: int = 50,

        prediction_horizon: int = 5,

        retrain_frequency: int = 30,

        threshold: float = 0.55

    ):

        config = StrategyConfig(

            name="MLStrategy",

            symbols=symbols,

        )

        super().__init__(config)



        self.model_type = model_type

        self.lookback = lookback

        self.prediction_horizon = prediction_horizon

        self.retrain_frequency = retrain_frequency

        self.threshold = threshold



        self.model = None

        self.last_train_idx = 0

        self.feature_cols = []



        self._init_model()



    def _init_model(self):

        """Initialize ML model"""

        try:

            from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier

            from sklearn.linear_model import LogisticRegression



            if self.model_type == 'random_forest':

                self.model = RandomForestClassifier(

                    n_estimators=100,

                    max_depth=5,

                    random_state=42

                )

            elif self.model_type == 'gradient_boosting':

                self.model = GradientBoostingClassifier(

                    n_estimators=100,

                    max_depth=3,

                    random_state=42

                )

            elif self.model_type == 'logistic':

                self.model = LogisticRegression(random_state=42)

            else:

                self.model = RandomForestClassifier(n_estimators=50, random_state=42)

        except ImportError:

            print("Warning: scikit-learn not installed. ML strategy will not work.")

            self.model = None



    def create_features(self, data: pd.DataFrame) -> pd.DataFrame:

        """Create technical features for ML model"""

        df = data.copy()





        df['returns'] = df['close'].pct_change()

        df['log_returns'] = np.log(df['close'] / df['close'].shift(1))





        for period in [5, 10, 20, 50]:

            df[f'sma_{period}'] = df['close'].rolling(period).mean()

            df[f'ema_{period}'] = df['close'].ewm(span=period, adjust=False).mean()

            df[f'dist_sma_{period}'] = (df['close'] - df[f'sma_{period}']) / df[f'sma_{period}']





        df['volatility_10'] = df['returns'].rolling(10).std()

        df['volatility_30'] = df['returns'].rolling(30).std()





        df['high_low_range'] = (df['high'] - df['low']) / df['close']

        df['body_size'] = abs(df['close'] - df['open']) / df['open']

        df['upper_shadow'] = (df['high'] - df[['open', 'close']].max(axis=1)) / df['close']

        df['lower_shadow'] = (df[['open', 'close']].min(axis=1) - df['low']) / df['close']





        df['volume_sma'] = df['volume'].rolling(20).mean()

        df['volume_ratio'] = df['volume'] / df['volume_sma']





        for lag in [1, 2, 3, 5]:

            df[f'return_lag_{lag}'] = df['returns'].shift(lag)







        delta = df['close'].diff()

        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()

        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()

        rs = gain / loss

        df['rsi'] = 100 - (100 / (1 + rs))





        ema_12 = df['close'].ewm(span=12, adjust=False).mean()

        ema_26 = df['close'].ewm(span=26, adjust=False).mean()

        df['macd'] = ema_12 - ema_26

        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()

        df['macd_hist'] = df['macd'] - df['macd_signal']





        tr1 = df['high'] - df['low']

        tr2 = abs(df['high'] - df['close'].shift(1))

        tr3 = abs(df['low'] - df['close'].shift(1))

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        df['atr'] = tr.rolling(window=14).mean()

        df['atr_pct'] = df['atr'] / df['close']





        self.feature_cols = [col for col in df.columns if col not in

                           ['open', 'high', 'low', 'close', 'volume', 'timestamp']]



        return df



    def prepare_data(self, data: pd.DataFrame) -> tuple:

        """Prepare features and target for training"""

        df = self.create_features(data)





        future_returns = df['close'].shift(-self.prediction_horizon) / df['close'] - 1

        df['target'] = np.where(future_returns > 0, 1, 0)





        df = df.dropna()



        if len(df) < self.lookback:

            return None, None



        X = df[self.feature_cols]

        y = df['target']



        return X, y



    def train_model(self, data: pd.DataFrame):

        """Train the ML model"""

        if self.model is None:

            return



        X, y = self.prepare_data(data)

        if X is None or len(X) < 100:

            return





        train_size = int(len(X) * 0.8)

        X_train, y_train = X.iloc[:train_size], y.iloc[:train_size]



        try:

            self.model.fit(X_train, y_train)

        except Exception as e:

            print(f"Model training error: {e}")



    def predict(self, data: pd.DataFrame) -> tuple:

        """Make prediction"""

        if self.model is None:

            return 0.5, 0



        df = self.create_features(data)

        df = df.dropna()



        if len(df) < 1:

            return 0.5, 0



        X = df[self.feature_cols].iloc[-1:]



        try:

            prob = self.model.predict_proba(X)[0]

            prediction = self.model.predict(X)[0]





            up_prob = prob[1] if len(prob) > 1 else 0.5

            return up_prob, prediction

        except Exception as e:

            return 0.5, 0



    def on_market_data(self, event: MarketEvent) -> Optional[SignalEvent]:

        """Generate ML-based signals"""

        self.update_data(event)



        data = self.data_history.get(event.symbol)

        if data is None or len(data) < self.lookback + 10:

            return None





        if len(data) - self.last_train_idx >= self.retrain_frequency:

            self.train_model(data)

            self.last_train_idx = len(data)





        if self.model is None:

            return None





        up_prob, prediction = self.predict(data)



        position = self.get_position(event.symbol)





        if up_prob > self.threshold:

            if position <= 0:

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='LONG',

                    price=event.close,

                    strength=up_prob,

                    confidence=up_prob,

                    metadata={'up_probability': up_prob, 'prediction': int(prediction)}

                )



        elif up_prob < (1 - self.threshold):

            if position >= 0:

                return self.generate_signal(

                    symbol=event.symbol,

                    signal_type='SHORT',

                    price=event.close,

                    strength=1 - up_prob,

                    confidence=1 - up_prob,

                    metadata={'up_probability': up_prob, 'prediction': int(prediction)}

                )





        if position > 0 and up_prob < 0.5:

            return self.generate_signal(

                symbol=event.symbol,

                signal_type='EXIT',

                price=event.close,

                metadata={'up_probability': up_prob, 'reason': 'confidence_drop'}

            )

        elif position < 0 and up_prob > 0.5:

            return self.generate_signal(

                symbol=event.symbol,

                signal_type='EXIT',

                price=event.close,

                metadata={'up_probability': up_prob, 'reason': 'confidence_drop'}

            )



        return None
