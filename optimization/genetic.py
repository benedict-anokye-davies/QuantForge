"""
Genetic Algorithm Optimizer
Evolutionary optimization for strategy parameters
"""



from typing import Dict, List, Any, Callable, Optional, Tuple

import numpy as np

import random

from dataclasses import dataclass

from tqdm import tqdm





@dataclass

class Individual:

    """Individual in genetic algorithm population"""

    genes: Dict[str, Any]

    fitness: float = 0.0

    metrics: Dict[str, float] = None



    def __post_init__(self):

        if self.metrics is None:

            self.metrics = {}





class GeneticOptimizer:

    """
    Genetic Algorithm for strategy parameter optimization
    """



    def __init__(

        self,

        strategy_class: type,

        param_bounds: Dict[str, Tuple[float, float]],

        param_types: Optional[Dict[str, str]] = None,

        population_size: int = 50,

        generations: int = 20,

        crossover_rate: float = 0.8,

        mutation_rate: float = 0.2,

        elitism: int = 2,

        scoring: str = 'sharpe_ratio'

    ):

        self.strategy_class = strategy_class

        self.param_bounds = param_bounds

        self.param_types = param_types or {}

        self.population_size = population_size

        self.generations = generations

        self.crossover_rate = crossover_rate

        self.mutation_rate = mutation_rate

        self.elitism = elitism

        self.scoring = scoring



        self.population: List[Individual] = []

        self.best_individual: Optional[Individual] = None

        self.generation_history: List[Dict] = []



    def _create_random_individual(self) -> Individual:

        """Create individual with random genes"""

        genes = {}

        for param, (min_val, max_val) in self.param_bounds.items():

            param_type = self.param_types.get(param, 'float')



            if param_type == 'int':

                genes[param] = random.randint(int(min_val), int(max_val))

            elif param_type == 'float':

                genes[param] = random.uniform(min_val, max_val)

            elif param_type == 'log':



                log_min, log_max = np.log(min_val), np.log(max_val)

                genes[param] = np.exp(random.uniform(log_min, log_max))



        return Individual(genes=genes)



    def _initialize_population(self):

        """Initialize random population"""

        self.population = [

            self._create_random_individual()

            for _ in range(self.population_size)

        ]



    def _evaluate_individual(

        self,

        individual: Individual,

        backtest_func: Callable,

        symbols: List[str]

    ) -> float:

        """Evaluate fitness of individual"""

        try:



            strategy = self.strategy_class(**individual.genes)





            metrics = backtest_func(strategy, symbols)





            individual.metrics = metrics





            fitness = metrics.get(self.scoring, 0)





            max_dd = metrics.get('max_drawdown', 0)

            if max_dd < -0.30:

                fitness *= 0.5



            return fitness



        except Exception as e:

            return -999



    def _evaluate_population(

        self,

        backtest_func: Callable,

        symbols: List[str],

        verbose: bool = True

    ):

        """Evaluate entire population"""

        iterator = tqdm(self.population, desc="Evaluating") if verbose else self.population



        for individual in iterator:

            individual.fitness = self._evaluate_individual(

                individual, backtest_func, symbols

            )



    def _select_parent(self) -> Individual:

        """Select parent using tournament selection"""

        tournament_size = 3

        tournament = random.sample(self.population, tournament_size)

        return max(tournament, key=lambda x: x.fitness)



    def _crossover(

        self,

        parent1: Individual,

        parent2: Individual

    ) -> Tuple[Individual, Individual]:

        """Perform crossover between two parents"""

        if random.random() > self.crossover_rate:

            return parent1, parent2



        child1_genes = {}

        child2_genes = {}



        for param in self.param_bounds.keys():

            if random.random() < 0.5:

                child1_genes[param] = parent1.genes[param]

                child2_genes[param] = parent2.genes[param]

            else:

                child1_genes[param] = parent2.genes[param]

                child2_genes[param] = parent1.genes[param]



        child1 = Individual(genes=child1_genes)

        child2 = Individual(genes=child2_genes)



        return child1, child2



    def _mutate(self, individual: Individual):

        """Mutate individual's genes"""

        for param, (min_val, max_val) in self.param_bounds.items():

            if random.random() < self.mutation_rate:

                param_type = self.param_types.get(param, 'float')



                if param_type == 'int':

                    individual.genes[param] = random.randint(int(min_val), int(max_val))

                elif param_type == 'float':



                    current = individual.genes[param]

                    std = (max_val - min_val) * 0.1

                    new_val = current + random.gauss(0, std)

                    individual.genes[param] = max(min_val, min(max_val, new_val))

                elif param_type == 'log':

                    log_min, log_max = np.log(min_val), np.log(max_val)

                    individual.genes[param] = np.exp(random.uniform(log_min, log_max))



    def _create_next_generation(self):

        """Create next generation through selection, crossover, mutation"""



        sorted_pop = sorted(self.population, key=lambda x: x.fitness, reverse=True)





        new_population = sorted_pop[:self.elitism]





        while len(new_population) < self.population_size:

            parent1 = self._select_parent()

            parent2 = self._select_parent()



            child1, child2 = self._crossover(parent1, parent2)



            self._mutate(child1)

            self._mutate(child2)



            new_population.append(child1)

            if len(new_population) < self.population_size:

                new_population.append(child2)



        self.population = new_population



    def optimize(

        self,

        backtest_func: Callable,

        symbols: List[str],

        verbose: bool = True

    ) -> Individual:

        """
        Run genetic algorithm optimization

        Args:
            backtest_func: Function that takes strategy and returns metrics
            symbols: List of symbols to test
            verbose: Show progress

        Returns:
            Best individual found
        """



        self._initialize_population()





        for generation in range(self.generations):

            if verbose:

                print(f"\nGeneration {generation + 1}/{self.generations}")





            self._evaluate_population(backtest_func, symbols, verbose)





            sorted_pop = sorted(self.population, key=lambda x: x.fitness, reverse=True)





            current_best = sorted_pop[0]

            if self.best_individual is None or current_best.fitness > self.best_individual.fitness:

                self.best_individual = Individual(

                    genes=current_best.genes.copy(),

                    fitness=current_best.fitness,

                    metrics=current_best.metrics.copy()

                )





            fitnesses = [ind.fitness for ind in self.population]

            self.generation_history.append({

                'generation': generation,

                'best_fitness': current_best.fitness,

                'avg_fitness': np.mean(fitnesses),

                'worst_fitness': min(fitnesses),

            })



            if verbose:

                print(f"  Best fitness: {current_best.fitness:.4f}")

                print(f"  Avg fitness: {np.mean(fitnesses):.4f}")

                print(f"  Best params: {current_best.genes}")





            if generation < self.generations - 1:

                self._create_next_generation()



        if verbose:

            print(f"\nOptimization complete!")

            print(f"Best fitness: {self.best_individual.fitness:.4f}")

            print(f"Best parameters: {self.best_individual.genes}")



        return self.best_individual



    def get_optimization_history(self) -> List[Dict]:

        """Get history of optimization process"""

        return self.generation_history
