"""
Example: Running a simple backtest
"""



import sys

sys.path.insert(0, '..')



from datetime import datetime, timedelta

from quant_researcher.core.engine import BacktestEngine

from quant_researcher.core.portfolio import Portfolio

from quant_researcher.strategies import MomentumStrategy, BollingerBandsStrategy

from quant_researcher.data.feeds import YahooFinanceFeed, SyntheticDataFeed

from quant_researcher.risk.position_sizing import KellyCriterion, FixedFractional

from quant_researcher.risk.risk_manager import RiskManager, PositionLimitRule





def run_momentum_backtest():

    """Run a momentum strategy backtest"""

    print("=" * 60)

    print("MOMENTUM STRATEGY BACKTEST")

    print("=" * 60)





    engine = BacktestEngine(

        initial_capital=100000,

        verbose=True

    )





    strategy = MomentumStrategy(

        symbols=['SPY'],

        momentum_threshold=0.3,

        lookback=20

    )

    engine.add_strategy(strategy)





    feed = YahooFinanceFeed(timeframe='1d')

    engine.add_data(feed, ['SPY'])





    metrics = engine.run()





    metrics.print_report()



    return metrics





def run_mean_reversion_backtest():

    """Run a mean reversion strategy backtest"""

    print("\n" + "=" * 60)

    print("MEAN REVERSION STRATEGY BACKTEST")

    print("=" * 60)





    risk_manager = RiskManager()

    risk_manager.add_rule(PositionLimitRule(max_position_pct=0.20))



    portfolio = Portfolio(

        initial_capital=100000,

        position_sizer=FixedFractional(risk_per_trade_pct=0.02),

        risk_manager=risk_manager

    )



    engine = BacktestEngine(

        initial_capital=100000,

        portfolio=portfolio,

        verbose=True

    )





    strategy = BollingerBandsStrategy(

        symbols=['AAPL'],

        period=20,

        std_dev=2.0,

        use_squeeze=True

    )

    engine.add_strategy(strategy)





    feed = YahooFinanceFeed(timeframe='1d')

    engine.add_data(feed, ['AAPL'])





    metrics = engine.run()





    metrics.print_report()



    return metrics





def run_synthetic_backtest():

    """Run backtest on synthetic data for quick testing"""

    print("\n" + "=" * 60)

    print("SYNTHETIC DATA BACKTEST")

    print("=" * 60)



    engine = BacktestEngine(

        initial_capital=100000,

        verbose=True

    )





    strategy = MomentumStrategy(symbols=['SYNTH1', 'SYNTH2'])

    engine.add_strategy(strategy)





    feed = SyntheticDataFeed(

        n_bars=500,

        trend=0.0002,

        volatility=0.02

    )

    engine.add_data(feed, ['SYNTH1', 'SYNTH2'])





    metrics = engine.run()





    metrics.print_report()



    return metrics





def compare_strategies():

    """Compare multiple strategies"""

    print("\n" + "=" * 60)

    print("STRATEGY COMPARISON")

    print("=" * 60)



    strategies = [

        ('Momentum', MomentumStrategy(symbols=['SPY'])),

        ('Bollinger', BollingerBandsStrategy(symbols=['SPY'])),

    ]



    results = []



    for name, strategy in strategies:

        print(f"\nTesting {name}...")



        engine = BacktestEngine(initial_capital=100000, verbose=False)

        engine.add_strategy(strategy)



        feed = YahooFinanceFeed(timeframe='1d')

        engine.add_data(feed, ['SPY'])



        metrics = engine.run()



        results.append({

            'name': name,

            'sharpe': metrics.metrics.get('sharpe_ratio', 0),

            'return': metrics.metrics.get('total_return', 0),

            'max_dd': metrics.metrics.get('max_drawdown', 0),

        })





    print("\n" + "-" * 60)

    print(f"{'Strategy':<20}{'Sharpe':<12}{'Return':<12}{'Max DD':<12}")

    print("-" * 60)



    for r in results:

        print(f"{r['name']:<20}{r['sharpe']:<12.2f}{r['return']*100:<11.1f}%{r['max_dd']*100:<11.1f}%")



    print("-" * 60)





if __name__ == '__main__':







    run_synthetic_backtest()


