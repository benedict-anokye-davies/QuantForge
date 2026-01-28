"""
Quant Researcher CLI
Usage: quant backtest --strategy momentum --symbol BTC/USDT
"""



import click

import json

from datetime import datetime, timedelta

from typing import Optional



from ..core.engine import BacktestEngine

from ..core.portfolio import Portfolio

from ..core.execution import SimulatedExecution, SlippageModel

from ..risk.position_sizing import KellyCriterion, FixedFractional

from ..risk.risk_manager import RiskManager, PositionLimitRule, DrawdownRule

from ..data.feeds import YahooFinanceFeed, CCXTFeed, CSVFeed, SyntheticDataFeed

from ..strategies import *







STRATEGIES = {

    'momentum': MomentumStrategy,

    'rsi': RSIStrategy,

    'macd': MACDStrategy,

    'mean_reversion': MeanReversionStrategy,

    'bollinger': BollingerBandsStrategy,

    'trend_following': TrendFollowingStrategy,

    'adx': ADXStrategy,

    'stat_arb': StatArbStrategy,

    'pairs': PairsTradingStrategy,

    'breakout': BreakoutStrategy,

    'donchian': DonchianStrategy,

    'vwap': VWAPStrategy,

    'ml': MLStrategy,

}





@click.group()

@click.version_option(version="1.0.0", prog_name="quant")

def cli():

    """Quant Researcher - Professional backtesting framework"""

    pass





@cli.command()

@click.option('--strategy', '-s', required=True,

              type=click.Choice(list(STRATEGIES.keys())),

              help='Strategy to backtest')

@click.option('--symbol', '-sym', required=True, multiple=True,

              help='Trading symbol(s)')

@click.option('--start', '-sd',

              default=(datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'),

              help='Start date (YYYY-MM-DD)')

@click.option('--end', '-ed',

              default=datetime.now().strftime('%Y-%m-%d'),

              help='End date (YYYY-MM-DD)')

@click.option('--timeframe', '-tf', default='1d',

              type=click.Choice(['1m', '5m', '15m', '1h', '4h', '1d', '1w']),

              help='Timeframe')

@click.option('--capital', '-c', default=100000.0, help='Initial capital')

@click.option('--data-source', '-d', default='yahoo',

              type=click.Choice(['yahoo', 'csv', 'synthetic']),

              help='Data source')

@click.option('--csv-file', help='CSV file path (for csv source)')

@click.option('--position-size', '-ps', default='kelly',

              type=click.Choice(['kelly', 'fixed', 'volatility']),

              help='Position sizing method')

@click.option('--output', '-o', help='Output file for results (JSON)')

@click.option('--plot', '-p', is_flag=True, help='Generate equity curve plot')

@click.option('--verbose', '-v', is_flag=True, help='Verbose output')

def backtest(

    strategy: str,

    symbol: tuple,

    start: str,

    end: str,

    timeframe: str,

    capital: float,

    data_source: str,

    csv_file: Optional[str],

    position_size: str,

    output: Optional[str],

    plot: bool,

    verbose: bool

):

    """Run backtest with specified strategy"""



    symbols = list(symbol)

    start_date = datetime.strptime(start, '%Y-%m-%d')

    end_date = datetime.strptime(end, '%Y-%m-%d')



    if verbose:

        click.echo(f"🔬 Backtesting {strategy} on {symbols}")

        click.echo(f"📅 Period: {start} to {end}")

        click.echo(f"💰 Initial capital: ${capital:,.2f}")





    if data_source == 'yahoo':

        feed = YahooFinanceFeed(timeframe=timeframe)

    elif data_source == 'csv':

        if not csv_file:

            raise click.UsageError("--csv-file required when using csv source")

        feed = CSVFeed(filepath=csv_file, timeframe=timeframe)

    else:

        feed = SyntheticDataFeed(timeframe=timeframe)





    if position_size == 'kelly':

        sizer = KellyCriterion(kelly_fraction=0.25)

    elif position_size == 'fixed':

        sizer = FixedFractional(risk_per_trade_pct=0.02)

    else:

        from ..risk.position_sizing import VolatilityTargeting

        sizer = VolatilityTargeting(target_volatility=0.15)





    risk_manager = RiskManager()

    risk_manager.add_rule(PositionLimitRule(max_position_pct=0.25))

    risk_manager.add_rule(DrawdownRule(max_drawdown=0.30))





    portfolio = Portfolio(

        initial_capital=capital,

        position_sizer=sizer,

        risk_manager=risk_manager

    )





    execution = SimulatedExecution(

        slippage_model=SlippageModel(

            model_type="percentage",

            percentage=0.001

        )

    )





    engine = BacktestEngine(

        initial_capital=capital,

        start_date=start_date,

        end_date=end_date,

        execution_handler=execution,

        portfolio=portfolio,

        verbose=verbose

    )





    strategy_class = STRATEGIES[strategy]

    strategy_instance = strategy_class(symbols=symbols)

    engine.add_strategy(strategy_instance)





    engine.add_data(feed, symbols)





    if verbose:

        click.echo("\n⏳ Running backtest...")



    metrics = engine.run()





    metrics.print_report()





    if output:

        results = {

            'summary': engine.get_results_summary(),

            'metrics': metrics.get_summary(),

            'portfolio_stats': portfolio.get_portfolio_stats(),

        }

        with open(output, 'w') as f:

            json.dump(results, f, indent=2, default=str)

        click.echo(f"\n💾 Results saved to {output}")





    if plot:

        try:

            import matplotlib.pyplot as plt

            equity_df = portfolio.get_equity_dataframe()



            fig, axes = plt.subplots(2, 1, figsize=(12, 8))





            axes[0].plot(equity_df.index, equity_df['equity'])

            axes[0].set_title('Equity Curve')

            axes[0].set_ylabel('Equity ($)')

            axes[0].grid(True)





            rolling_max = equity_df['equity'].expanding().max()

            drawdown = (equity_df['equity'] - rolling_max) / rolling_max

            axes[1].fill_between(equity_df.index, drawdown, 0, color='red', alpha=0.3)

            axes[1].set_title('Drawdown')

            axes[1].set_ylabel('Drawdown (%)')

            axes[1].grid(True)



            plt.tight_layout()

            plt.savefig(output.replace('.json', '.png') if output else 'backtest.png')

            click.echo(f"📊 Plot saved")

        except ImportError:

            click.echo("⚠️ matplotlib not installed, skipping plot")





@cli.command()

@click.option('--strategy', '-s', required=True,

              type=click.Choice(list(STRATEGIES.keys())),

              help='Strategy to optimize')

@click.option('--symbol', '-sym', required=True, multiple=True,

              help='Trading symbol(s)')

@click.option('--param', '-p', multiple=True,

              help='Parameter to optimize (format: name:min:max:step)')

@click.option('--method', '-m', default='grid',

              type=click.Choice(['grid', 'random', 'genetic']),

              help='Optimization method')

@click.option('--metric', default='sharpe',

              type=click.Choice(['sharpe', 'return', 'profit_factor', 'calmar']),

              help='Optimization metric')

@click.option('--iterations', '-i', default=100, help='Number of iterations')

@click.option('--start', default=(datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'))

@click.option('--end', default=datetime.now().strftime('%Y-%m-%d'))

def optimize(

    strategy: str,

    symbol: tuple,

    param: tuple,

    method: str,

    metric: str,

    iterations: int,

    start: str,

    end: str

):

    """Optimize strategy parameters"""



    click.echo(f"🔧 Optimizing {strategy} parameters")

    click.echo(f"📊 Method: {method}, Metric: {metric}")





    param_grid = {}

    for p in param:

        parts = p.split(':')

        if len(parts) != 4:

            raise click.UsageError(f"Invalid parameter format: {p}")

        name, min_val, max_val, step = parts

        param_grid[name] = {

            'min': float(min_val),

            'max': float(max_val),

            'step': float(step)

        }



    click.echo(f"📋 Parameters: {list(param_grid.keys())}")





    click.echo("⚠️ Optimization not yet fully implemented")





@cli.command()

@click.option('--strategies', '-s', multiple=True,

              type=click.Choice(list(STRATEGIES.keys())),

              help='Strategies to compare')

@click.option('--symbol', '-sym', required=True, multiple=True,

              help='Trading symbol(s)')

@click.option('--start', default=(datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'))

@click.option('--end', default=datetime.now().strftime('%Y-%m-%d'))

@click.option('--output', '-o', help='Output file for comparison')

def compare(

    strategies: tuple,

    symbol: tuple,

    start: str,

    end: str,

    output: Optional[str]

):

    """Compare multiple strategies"""



    if not strategies:

        strategies = list(STRATEGIES.keys())[:5]



    symbols = list(symbol)

    start_date = datetime.strptime(start, '%Y-%m-%d')

    end_date = datetime.strptime(end, '%Y-%m-%d')



    click.echo(f"📊 Comparing {len(strategies)} strategies on {symbols}")



    results = []



    for strat_name in strategies:

        click.echo(f"\n⏳ Testing {strat_name}...")





        feed = YahooFinanceFeed(timeframe='1d')

        engine = BacktestEngine(

            initial_capital=100000,

            start_date=start_date,

            end_date=end_date,

            verbose=False

        )





        strategy_class = STRATEGIES[strat_name]

        strategy_instance = strategy_class(symbols=symbols)

        engine.add_strategy(strategy_instance)

        engine.add_data(feed, symbols)





        metrics = engine.run()



        results.append({

            'strategy': strat_name,

            'sharpe': metrics.metrics.get('sharpe_ratio', 0),

            'return': metrics.metrics.get('total_return', 0),

            'max_dd': metrics.metrics.get('max_drawdown', 0),

            'win_rate': metrics.metrics.get('win_rate', 0),

            'profit_factor': metrics.metrics.get('profit_factor', 0),

        })





    results.sort(key=lambda x: x['sharpe'], reverse=True)





    click.echo("\n" + "=" * 80)

    click.echo("STRATEGY COMPARISON")

    click.echo("=" * 80)

    click.echo(f"{'Rank':<6}{'Strategy':<20}{'Sharpe':<10}{'Return':<10}{'Max DD':<10}{'Win Rate':<10}")

    click.echo("-" * 80)



    for i, r in enumerate(results, 1):

        click.echo(

            f"{i:<6}{r['strategy']:<20}"

            f"{r['sharpe']:<10.2f}"

            f"{r['return']*100:<10.1f}%"

            f"{r['max_dd']*100:<10.1f}%"

            f"{r['win_rate']*100:<10.1f}%"

        )



    click.echo("=" * 80)





    if output:

        with open(output, 'w') as f:

            json.dump(results, f, indent=2)

        click.echo(f"\n💾 Comparison saved to {output}")





@cli.command()

@click.option('--strategy', '-s', required=True,

              type=click.Choice(list(STRATEGIES.keys())),

              help='Strategy for paper trading')

@click.option('--symbol', '-sym', required=True, multiple=True,

              help='Trading symbol(s)')

@click.option('--duration', '-d', default=7, help='Paper trading duration (days)')

@click.option('--interval', '-i', default=60, help='Check interval (minutes)')

def paper_trade(

    strategy: str,

    symbol: tuple,

    duration: int,

    interval: int

):

    """Run paper trading simulation"""



    symbols = list(symbol)



    click.echo(f"📰 Paper Trading: {strategy} on {symbols}")

    click.echo(f"⏱️  Duration: {duration} days, Interval: {interval} minutes")

    click.echo("\n⚠️  Paper trading requires live data feed setup")

    click.echo("   Configure your exchange API keys in config.yaml")





if __name__ == '__main__':

    cli()
