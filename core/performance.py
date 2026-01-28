"""
Performance Metrics - Calculate trading performance analytics
Sharpe, Sortino, Calmar, drawdowns, and more
"""



from typing import List, Dict, Optional, Any

from datetime import datetime

from dataclasses import dataclass

import pandas as pd

import numpy as np

from scipy import stats



from .events import SignalEvent, OrderEvent, FillEvent, RiskEvent

from .portfolio import Portfolio





@dataclass

class TradeRecord:

    """Record of a single trade"""

    symbol: str

    entry_time: datetime

    exit_time: datetime

    entry_price: float

    exit_price: float

    quantity: float

    direction: str

    pnl: float

    return_pct: float

    holding_periods: int = 0



    @property

    def is_win(self) -> bool:

        return self.pnl > 0



    @property

    def is_loss(self) -> bool:

        return self.pnl < 0





class PerformanceMetrics:

    """
    Comprehensive performance analytics
    """



    def __init__(

        self,

        portfolio: Portfolio,

        signals: List[SignalEvent],

        orders: List[OrderEvent],

        fills: List[FillEvent],

        risk_events: List[RiskEvent],

        risk_free_rate: float = 0.02,

    ):

        self.portfolio = portfolio

        self.signals = signals

        self.orders = orders

        self.fills = fills

        self.risk_events = risk_events

        self.risk_free_rate = risk_free_rate





        self.equity_df = portfolio.get_equity_dataframe()





        if not self.equity_df.empty:

            self.returns = self.equity_df['returns'].dropna()

            self.calculate_all_metrics()



    def calculate_all_metrics(self):

        """Calculate all performance metrics"""

        self.metrics = {



            'total_return': self.calculate_total_return(),

            'cagr': self.calculate_cagr(),

            'annualized_return': self.calculate_annualized_return(),





            'volatility': self.calculate_volatility(),

            'annualized_volatility': self.calculate_annualized_volatility(),

            'sharpe_ratio': self.calculate_sharpe_ratio(),

            'sortino_ratio': self.calculate_sortino_ratio(),

            'calmar_ratio': self.calculate_calmar_ratio(),





            'max_drawdown': self.calculate_max_drawdown(),

            'max_drawdown_duration': self.calculate_max_drawdown_duration(),

            'avg_drawdown': self.calculate_avg_drawdown(),





            'total_trades': len(self.fills) // 2,

            'win_rate': self.calculate_win_rate(),

            'profit_factor': self.calculate_profit_factor(),

            'avg_trade_return': self.calculate_avg_trade_return(),

            'avg_win': self.calculate_avg_win(),

            'avg_loss': self.calculate_avg_loss(),

            'win_loss_ratio': self.calculate_win_loss_ratio(),





            'skewness': self.calculate_skewness(),

            'kurtosis': self.calculate_kurtosis(),

            'var_95': self.calculate_var(0.95),

            'cvar_95': self.calculate_cvar(0.95),





            'omega_ratio': self.calculate_omega_ratio(),

            'information_ratio': self.calculate_information_ratio(),

            'treynor_ratio': None,

            'up_capture': None,

            'down_capture': None,

        }





        self.mc_metrics = self.run_monte_carlo()



    def calculate_total_return(self) -> float:

        """Total return over backtest period"""

        if self.equity_df.empty:

            return 0.0

        final = self.equity_df['equity'].iloc[-1]

        initial = self.portfolio.initial_capital

        return (final - initial) / initial



    def calculate_cagr(self) -> float:

        """Compound Annual Growth Rate"""

        if self.equity_df.empty or len(self.equity_df) < 2:

            return 0.0



        final = self.equity_df['equity'].iloc[-1]

        initial = self.portfolio.initial_capital





        start = self.equity_df.index[0]

        end = self.equity_df.index[-1]

        years = (end - start).days / 365.25



        if years <= 0:

            return 0.0



        return (final / initial) ** (1 / years) - 1



    def calculate_annualized_return(self) -> float:

        """Annualized return"""

        if self.equity_df.empty or len(self.returns) < 2:

            return 0.0





        periods_per_year = 252

        avg_return = self.returns.mean()

        return avg_return * periods_per_year



    def calculate_volatility(self) -> float:

        """Daily volatility (standard deviation)"""

        if len(self.returns) < 2:

            return 0.0

        return self.returns.std()



    def calculate_annualized_volatility(self) -> float:

        """Annualized volatility"""

        if len(self.returns) < 2:

            return 0.0

        daily_vol = self.returns.std()

        return daily_vol * np.sqrt(252)



    def calculate_sharpe_ratio(self) -> float:

        """Sharpe ratio - risk-adjusted return"""

        if len(self.returns) < 2:

            return 0.0



        excess_returns = self.returns - (self.risk_free_rate / 252)

        if excess_returns.std() == 0:

            return 0.0



        sharpe = excess_returns.mean() / excess_returns.std() * np.sqrt(252)

        return sharpe



    def calculate_sortino_ratio(self) -> float:

        """Sortino ratio - downside risk-adjusted return"""

        if len(self.returns) < 2:

            return 0.0



        excess_returns = self.returns - (self.risk_free_rate / 252)

        downside_returns = self.returns[self.returns < 0]



        if len(downside_returns) == 0 or downside_returns.std() == 0:

            return np.inf if excess_returns.mean() > 0 else 0.0



        downside_std = downside_returns.std() * np.sqrt(252)

        sortino = (excess_returns.mean() * 252) / downside_std

        return sortino



    def calculate_calmar_ratio(self) -> float:

        """Calmar ratio - return relative to max drawdown"""

        max_dd = abs(self.calculate_max_drawdown())

        if max_dd == 0:

            return np.inf



        cagr = self.calculate_cagr()

        return cagr / max_dd



    def calculate_max_drawdown(self) -> float:

        """Maximum peak-to-trough drawdown"""

        if self.equity_df.empty:

            return 0.0



        equity = self.equity_df['equity']

        rolling_max = equity.expanding().max()

        drawdown = (equity - rolling_max) / rolling_max

        return drawdown.min()



    def calculate_max_drawdown_duration(self) -> int:

        """Duration of longest drawdown in periods"""

        if self.equity_df.empty:

            return 0



        equity = self.equity_df['equity']

        rolling_max = equity.expanding().max()

        drawdown = equity < rolling_max





        max_duration = 0

        current_duration = 0



        for is_dd in drawdown:

            if is_dd:

                current_duration += 1

                max_duration = max(max_duration, current_duration)

            else:

                current_duration = 0



        return max_duration



    def calculate_avg_drawdown(self) -> float:

        """Average drawdown"""

        if self.equity_df.empty:

            return 0.0



        equity = self.equity_df['equity']

        rolling_max = equity.expanding().max()

        drawdowns = (equity - rolling_max) / rolling_max

        return drawdowns[drawdowns < 0].mean()



    def calculate_win_rate(self) -> float:

        """Percentage of winning trades"""

        trades = self._extract_trades()

        if not trades:

            return 0.0



        wins = sum(1 for t in trades if t.is_win)

        return wins / len(trades)



    def calculate_profit_factor(self) -> float:

        """Gross profit / Gross loss"""

        trades = self._extract_trades()

        if not trades:

            return 0.0



        gross_profit = sum(t.pnl for t in trades if t.is_win)

        gross_loss = abs(sum(t.pnl for t in trades if t.is_loss))



        if gross_loss == 0:

            return np.inf if gross_profit > 0 else 0.0



        return gross_profit / gross_loss



    def calculate_avg_trade_return(self) -> float:

        """Average return per trade"""

        trades = self._extract_trades()

        if not trades:

            return 0.0



        return np.mean([t.return_pct for t in trades])



    def calculate_avg_win(self) -> float:

        """Average winning trade return"""

        trades = self._extract_trades()

        wins = [t.pnl for t in trades if t.is_win]

        return np.mean(wins) if wins else 0.0



    def calculate_avg_loss(self) -> float:

        """Average losing trade return"""

        trades = self._extract_trades()

        losses = [t.pnl for t in trades if t.is_loss]

        return np.mean(losses) if losses else 0.0



    def calculate_win_loss_ratio(self) -> float:

        """Average win / Average loss (absolute)"""

        avg_win = self.calculate_avg_win()

        avg_loss = abs(self.calculate_avg_loss())



        if avg_loss == 0:

            return np.inf if avg_win > 0 else 0.0



        return avg_win / avg_loss



    def calculate_skewness(self) -> float:

        """Return distribution skewness"""

        if len(self.returns) < 3:

            return 0.0

        return stats.skew(self.returns)



    def calculate_kurtosis(self) -> float:

        """Return distribution kurtosis"""

        if len(self.returns) < 4:

            return 0.0

        return stats.kurtosis(self.returns)



    def calculate_var(self, confidence: float = 0.95) -> float:

        """Value at Risk at given confidence level"""

        if len(self.returns) < 10:

            return 0.0

        return np.percentile(self.returns, (1 - confidence) * 100)



    def calculate_cvar(self, confidence: float = 0.95) -> float:

        """Conditional Value at Risk (expected shortfall)"""

        if len(self.returns) < 10:

            return 0.0

        var = self.calculate_var(confidence)

        return self.returns[self.returns <= var].mean()



    def calculate_omega_ratio(self, threshold: float = 0.0) -> float:

        """Omega ratio - probability-weighted gains/losses relative to threshold"""

        if len(self.returns) < 2:

            return 0.0



        excess = self.returns - threshold

        gains = excess[excess > 0].sum()

        losses = abs(excess[excess < 0].sum())



        if losses == 0:

            return np.inf if gains > 0 else 0.0



        return gains / losses



    def calculate_information_ratio(self, benchmark_returns: Optional[pd.Series] = None) -> float:

        """Information ratio - active return / tracking error"""

        if len(self.returns) < 2:

            return 0.0



        if benchmark_returns is None:



            active_return = self.returns.mean() * 252

            tracking_error = self.returns.std() * np.sqrt(252)

        else:

            aligned = pd.concat([self.returns, benchmark_returns], axis=1).dropna()

            if len(aligned) < 2:

                return 0.0



            active_returns = aligned.iloc[:, 0] - aligned.iloc[:, 1]

            active_return = active_returns.mean() * 252

            tracking_error = active_returns.std() * np.sqrt(252)



        if tracking_error == 0:

            return 0.0



        return active_return / tracking_error



    def run_monte_carlo(

        self,

        n_simulations: int = 1000,

        confidence: float = 0.95

    ) -> Dict[str, Any]:

        """
        Monte Carlo simulation for robustness testing
        """

        if len(self.returns) < 10:

            return {}





        trades = self._extract_trades()

        if not trades:

            return {}





        trade_returns = [t.return_pct for t in trades]





        sim_results = []

        n_trades = len(trades)



        for _ in range(n_simulations):



            sampled_returns = np.random.choice(trade_returns, size=n_trades, replace=True)





            cumulative = np.prod([1 + r for r in sampled_returns]) - 1

            sim_results.append(cumulative)



        sim_results = np.array(sim_results)



        return {

            'median_return': np.median(sim_results),

            'mean_return': np.mean(sim_results),

            'std_return': np.std(sim_results),

            'worst_case': np.percentile(sim_results, (1 - confidence) * 100),

            'best_case': np.percentile(sim_results, confidence * 100),

            'probability_profit': np.mean(sim_results > 0),

            'probability_2x': np.mean(sim_results > 1.0),

        }



    def _extract_trades(self) -> List[TradeRecord]:

        """Extract completed trades from fills"""

        trades = []





        fills_by_symbol = {}

        for fill in self.fills:

            if fill.symbol not in fills_by_symbol:

                fills_by_symbol[fill.symbol] = []

            fills_by_symbol[fill.symbol].append(fill)





        for symbol, symbol_fills in fills_by_symbol.items():



            position = 0

            entry_price = 0

            entry_time = None



            for fill in symbol_fills:

                qty = fill.quantity if fill.direction == 'BUY' else -fill.quantity



                if position == 0:



                    position = qty

                    entry_price = fill.fill_price

                    entry_time = fill.timestamp

                elif (position > 0 and qty > 0) or (position < 0 and qty < 0):



                    position += qty

                else:



                    if abs(qty) >= abs(position):



                        exit_qty = abs(position)

                        pnl = position * (fill.fill_price - entry_price)

                        return_pct = (fill.fill_price - entry_price) / entry_price

                        if position < 0:

                            pnl = -pnl

                            return_pct = -return_pct



                        trades.append(TradeRecord(

                            symbol=symbol,

                            entry_time=entry_time,

                            exit_time=fill.timestamp,

                            entry_price=entry_price,

                            exit_price=fill.fill_price,

                            quantity=exit_qty,

                            direction='LONG' if position > 0 else 'SHORT',

                            pnl=pnl,

                            return_pct=return_pct

                        ))

                        position = 0

                    else:



                        position += qty



        return trades



    def get_summary(self) -> Dict[str, Any]:

        """Get formatted performance summary"""

        return {

            'returns': {

                'total_return_pct': f"{self.metrics['total_return'] * 100:.2f}%",

                'cagr_pct': f"{self.metrics['cagr'] * 100:.2f}%",

                'annualized_volatility_pct': f"{self.metrics['annualized_volatility'] * 100:.2f}%",

            },

            'risk_metrics': {

                'sharpe_ratio': f"{self.metrics['sharpe_ratio']:.2f}",

                'sortino_ratio': f"{self.metrics['sortino_ratio']:.2f}",

                'calmar_ratio': f"{self.metrics['calmar_ratio']:.2f}",

                'max_drawdown_pct': f"{self.metrics['max_drawdown'] * 100:.2f}%",

                'var_95_daily_pct': f"{self.metrics['var_95'] * 100:.2f}%",

            },

            'trade_stats': {

                'total_trades': self.metrics['total_trades'],

                'win_rate_pct': f"{self.metrics['win_rate'] * 100:.1f}%",

                'profit_factor': f"{self.metrics['profit_factor']:.2f}",

                'avg_win': f"${self.metrics['avg_win']:.2f}",

                'avg_loss': f"${self.metrics['avg_loss']:.2f}",

                'win_loss_ratio': f"{self.metrics['win_loss_ratio']:.2f}",

            },

            'monte_carlo': {

                'median_return_pct': f"{self.mc_metrics.get('median_return', 0) * 100:.2f}%",

                'probability_of_profit_pct': f"{self.mc_metrics.get('probability_profit', 0) * 100:.1f}%",

                'worst_case_pct': f"{self.mc_metrics.get('worst_case', 0) * 100:.2f}%",

            }

        }



    def print_report(self):

        """Print formatted performance report"""

        summary = self.get_summary()



        print("\n" + "=" * 60)

        print("PERFORMANCE REPORT")

        print("=" * 60)



        print("\n📈 RETURNS")

        for key, value in summary['returns'].items():

            print(f"  {key}: {value}")



        print("\n⚠️  RISK METRICS")

        for key, value in summary['risk_metrics'].items():

            print(f"  {key}: {value}")



        print("\n💰 TRADE STATISTICS")

        for key, value in summary['trade_stats'].items():

            print(f"  {key}: {value}")



        print("\n🎲 MONTE CARLO SIMULATION")

        for key, value in summary['monte_carlo'].items():

            print(f"  {key}: {value}")



        print("\n" + "=" * 60)
