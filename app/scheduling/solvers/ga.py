"""GA đơn mục tiêu (design.md mục 3).

Quần thể 40, tournament 3, lai đều (p = 0,9), đột biến từng gen xác suất 1/n, giữ 2 cá thể tốt nhất.
Fitness = vô hướng 10⁷·conflicts + 10⁵·H + P (nhỏ hơn là tốt hơn).
"""
import random
from typing import List, Optional

from app.scheduling.constraints import Evaluator
from app.scheduling.solvers.base import DEFAULT_BUDGET, SolveResult, Timer, random_solution, result_from
from app.scheduling.topk import DEFAULT_K, Archive, min_distance

NAME = "ga"
POPULATION = 40
TOURNAMENT = 3
CROSSOVER = 0.9
ELITES = 2


def solve(evaluator: Evaluator, k: int = DEFAULT_K, budget: int = DEFAULT_BUDGET, seed: int = 0,
          time_limit: Optional[float] = None, **_) -> SolveResult:
    timer = Timer()
    rng = random.Random(seed)
    problem = evaluator.problem
    sizes = problem.sizes
    n = problem.n
    archive = Archive()
    start = evaluator.evaluations
    used = lambda: evaluator.evaluations - start
    mutation = 1.0 / max(1, problem.free_courses)

    def evaluate(x):
        key = tuple(x)
        score = archive.items.get(key)
        if score is None:            # cá thể đã gặp không chấm lại: không tốn ngân sách
            score = evaluator.evaluate(x)
            archive.add(x, score)
        return score.scalar

    population: List[List[int]] = [random_solution(rng, sizes) for _ in range(min(POPULATION, budget))]
    fitness = [evaluate(x) for x in population]

    def tournament():
        best = None
        for _ in range(TOURNAMENT):
            j = rng.randrange(len(population))
            if best is None or fitness[j] < fitness[best]:
                best = j
        return population[best]

    # lời giải đã gặp không tốn ngân sách, nên giới hạn thêm số thế hệ (không gian nhỏ)
    generation, max_generations = 0, 2 * budget // POPULATION + 1
    while used() < budget and generation < max_generations:
        generation += 1
        if time_limit and timer.elapsed > time_limit:
            break
        ranked = sorted(range(len(population)), key=lambda j: fitness[j])
        children = [list(population[j]) for j in ranked[:ELITES]]
        child_fitness = [fitness[j] for j in ranked[:ELITES]]
        while len(children) < POPULATION and used() < budget:
            a, b = tournament(), tournament()
            if rng.random() < CROSSOVER:
                child = [a[i] if rng.random() < 0.5 else b[i] for i in range(n)]
            else:
                child = list(a)
            mutated = False
            for i in range(n):
                if sizes[i] > 1 and rng.random() < mutation:
                    child[i] = rng.randrange(sizes[i])
                    mutated = True
            if not mutated:
                free = [i for i in range(n) if sizes[i] > 1]
                if free:
                    i = rng.choice(free)
                    child[i] = rng.randrange(sizes[i])
            children.append(child)
            child_fitness.append(evaluate(child))
        population, fitness = children, child_fitness
    return result_from(NAME, archive.select(k, min_distance(problem)), evaluator, timer,
                       meta={"archive": len(archive.items), "generations": generation})
