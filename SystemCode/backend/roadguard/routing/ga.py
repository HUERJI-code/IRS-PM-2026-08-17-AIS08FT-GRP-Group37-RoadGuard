from dataclasses import dataclass
import random

from .evaluation import Evaluation, RoutingProblem
from .greedy import greedy_routes
from .settings import GAParameters

Chromosome = tuple[tuple[int, ...], tuple[int, ...]]


@dataclass(frozen=True)
class GAResult:
    best: Evaluation
    generations_run: int
    unique_evaluations: int
    best_key_history: tuple[tuple[int, int, int, float], ...]   # (skipped P1, P2, P3, objective)


class GeneticPlanner:
    def __init__(self, problem: RoutingProblem, parameters: GAParameters, seed: int) -> None:
        self.problem = problem
        self.parameters = parameters
        self.random = random.Random(seed)
        self.tasks = list(problem.schedulable)
        self.crew_count = len(problem.available_crews)
        self.size = len(problem.tasks)
        self.cache: dict[Chromosome, Evaluation] = {}

    def decode(self, chromosome: Chromosome) -> list[list[int]]:
        order, owner = chromosome
        routes: list[list[int]] = [[] for _ in range(self.crew_count)]
        for task in order:
            routes[owner[task]].append(task)
        return routes

    def evaluate(self, chromosome: Chromosome) -> Evaluation:
        cached = self.cache.get(chromosome)
        if cached is None:
            cached = self.problem.evaluate(self.decode(chromosome))
            self.cache[chromosome] = cached
        return cached

    def random_chromosome(self) -> Chromosome:
        order = self.tasks[:]
        self.random.shuffle(order)
        owner = [0] * self.size
        for task in self.tasks:
            owner[task] = self.random.randrange(self.crew_count)
        return tuple(order), tuple(owner)

    def from_routes(self, routes: list[list[int]]) -> Chromosome:
        owner = [0] * self.size
        order = []
        for slot, route in enumerate(routes):
            for task in route:
                owner[task] = slot
                order.append(task)
        return tuple(order), tuple(owner)

    def tournament(self, population: list[Chromosome]) -> Chromosome:
        contenders = self.random.sample(population, min(self.parameters.tournament_size, len(population)))
        return min(contenders, key=lambda c: self.evaluate(c).key)

    def crossover(self, first: Chromosome, second: Chromosome) -> Chromosome:
        order_a, owner_a = first
        order_b, owner_b = second
        n = len(order_a)
        left, right = sorted(self.random.sample(range(n + 1), 2))
        middle = order_a[left:right]
        taken = set(middle)
        rest = [task for task in order_b if task not in taken]
        order = tuple(rest[:left]) + middle + tuple(rest[left:])
        owner = list(owner_a)
        for task in self.tasks:
            if self.random.random() < 0.5:
                owner[task] = owner_b[task]
        return order, tuple(owner)

    def mutate(self, chromosome: Chromosome) -> Chromosome:
        order, owner = list(chromosome[0]), list(chromosome[1])
        n = len(order)
        operator = self.random.randrange(4)
        if operator == 0 and n >= 2:  # swap two visits
            i, j = self.random.sample(range(n), 2)
            order[i], order[j] = order[j], order[i]
        elif operator == 1 and n >= 2:  # reverse a segment
            i, j = sorted(self.random.sample(range(n), 2))
            order[i:j + 1] = reversed(order[i:j + 1])
        elif operator == 2 and self.crew_count > 1:  # move a task to another crew
            task = self.random.choice(order)
            owner[task] = self.random.choice([c for c in range(self.crew_count) if c != owner[task]])
        elif n >= 2:  # relocate one visit in the order
            task = order.pop(self.random.randrange(n))
            order.insert(self.random.randrange(n), task)
        return tuple(order), tuple(owner)

    def run(self) -> GAResult:
        if not self.tasks or not self.crew_count:
            empty = self.problem.evaluate([[] for _ in range(self.crew_count)])
            return GAResult(best=empty, generations_run=0, unique_evaluations=1, best_key_history=(empty.key,))
        p = self.parameters
        population = [self.random_chromosome() for _ in range(p.population_size)]
        if p.seed_with_greedy:
            population[0] = self.from_routes(greedy_routes(self.problem))
        population.sort(key=lambda c: self.evaluate(c).key)
        best = population[0]
        history = [self.evaluate(best).key]
        stale = 0
        generations = 0
        for generations in range(1, p.max_generations + 1):
            offspring = population[:p.elite_count]
            while len(offspring) < p.population_size:
                first, second = self.tournament(population), self.tournament(population)
                child = self.crossover(first, second) if self.random.random() < p.crossover_rate else first
                if self.random.random() < p.mutation_rate:
                    child = self.mutate(child)
                offspring.append(child)
            population = sorted(offspring, key=lambda c: self.evaluate(c).key)
            if self.evaluate(population[0]).key < self.evaluate(best).key:
                best, stale = population[0], 0
            else:
                stale += 1
            history.append(self.evaluate(best).key)
            if stale >= p.patience_generations:
                break
        return GAResult(best=self.evaluate(best), generations_run=generations,
                        unique_evaluations=len(self.cache), best_key_history=tuple(history))


def solve_ga(problem: RoutingProblem, parameters: GAParameters, seed: int) -> GAResult:
    return GeneticPlanner(problem, parameters, seed).run()
