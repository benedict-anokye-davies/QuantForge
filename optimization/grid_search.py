"""
Grid Search Optimizer - Exhaustive parameter search
"""



from typing import Dict, List, Any, Callable, Optional

import pandas as pd

import numpy as np

from itertools import product

from dataclasses import dataclass

from tqdm import tqdm





@dataclass

class OptimizationResult:

    """Result from optimization run"""

    params: Dict[str, Any]

    score: float

    metrics: Dict[str, float]





class GridSearchOptimizer:

    """
    Exhaustive grid search for strategy parameters
    """



    def __init__(

        self,

        strategy_class: type,

        param_grid: Dict[str, List[Any]],

        scoring: str = 'sharpe_ratio',

        n_jobs: int = 1

    ):

        self.strategy_class = strategy_class

        self.param_grid = param_grid

        self.scoring = scoring

        self.n_jobs = n_jobs



        self.results: List[OptimizationResult] = []

        self.best_result: Optional[OptimizationResult] = None



    def optimize(

        self,

        backtest_func: Callable,

        symbols: List[str],

        verbose: bool = True

    ) -> OptimizationResult:

        """
        Run grid search optimization

        Args:
            backtest_func: Function that takes strategy instance and returns metrics
            symbols: List of symbols to test on
            verbose: Show progress

        Returns:
            Best optimization result
        """



        param_names = list(self.param_grid.keys())

        param_values = list(self.param_grid.values())



        combinations = list(product(*param_values))



        if verbose:

            print(f"Testing {len(combinations)} parameter combinations...")



        iterator = tqdm(combinations) if verbose else combinations



        for combo in iterator:

            params = dict(zip(param_names, combo))



            try:



                strategy = self.strategy_class(**params)





                metrics = backtest_func(strategy, symbols)





                score = metrics.get(self.scoring, 0)





                result = OptimizationResult(

                    params=params,

                    score=score,

                    metrics=metrics

                )

                self.results.append(result)





                if self.best_result is None or score > self.best_result.score:

                    self.best_result = result



            except Exception as e:

                if verbose:

                    print(f"Error with params {params}: {e}")

                continue



        if verbose and self.best_result:

            print(f"\nBest parameters: {self.best_result.params}")

            print(f"Best {self.scoring}: {self.best_result.score:.4f}")



        return self.best_result



    def get_results_df(self) -> pd.DataFrame:

        """Get all results as DataFrame"""

        records = []

        for r in self.results:

            record = {**r.params, 'score': r.score, **r.metrics}

            records.append(record)



        return pd.DataFrame(records)



    def get_top_results(self, n: int = 10) -> List[OptimizationResult]:

        """Get top N results by score"""

        sorted_results = sorted(self.results, key=lambda x: x.score, reverse=True)

        return sorted_results[:n]
