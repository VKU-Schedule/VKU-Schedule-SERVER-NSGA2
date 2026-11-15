"""NSGA-II gốc của hệ thống cũ, port sang hàm chấm v2 (design.md mục 3).

Giữ nguyên cấu hình của `app/service/constraints_service.run_nsga_ii`:
- DEAP, một mục tiêu `weights=(-1.0,)`, cá thể là list chỉ số lớp;
- quần thể 30, `cxUniform(indpb=0.5)`, `mutUniformInt(indpb=0.5)`, `selNSGA2`;
- `eaMuPlusLambda(mu=30, lambda_=30, cxpb=0.5, mutpb=0.5)`;
- trùng lịch → fitness `inf`;
- kết quả: front đầu của quần thể cuối, bỏ trùng, xếp theo fitness, lấy 5;
- một môn: chấm mọi lớp, lấy 5 lớp tốt nhất.

Khác bản gốc: fitness là 10⁵·H + P của JSON v2 thay cho điểm v1; seed là tham số (bản gốc cố định 42);
số thế hệ = (ngân sách − 30) / 30 (ngân sách 1.500 ứng với 49 thế hệ, bản gốc 50);
`creator` / `toolbox` cục bộ (bản gốc dùng biến toàn cục, không an toàn khi chạy song song).
"""
import random
from typing import Dict, Optional, Tuple

from deap import algorithms, base, creator, tools

from app.scheduling.constraints import Evaluator, Score
from app.scheduling.solvers.base import DEFAULT_BUDGET, SolveResult, Timer, result_from
from app.scheduling.topk import DEFAULT_K

NAME = "nsga2_legacy"
POPULATION = 30
CROSSOVER = 0.5
MUTATION = 0.5

if not hasattr(creator, "LegacyFitnessMin"):
    creator.create("LegacyFitnessMin", base.Fitness, weights=(-1.0,))
    creator.create("LegacyIndividual", list, fitness=creator.LegacyFitnessMin)


def generations_for(budget: int) -> int:
    return max(1, (budget - POPULATION) // POPULATION)


def solve(evaluator: Evaluator, k: int = DEFAULT_K, budget: int = DEFAULT_BUDGET, seed: int = 42,
          time_limit: Optional[float] = None, **_) -> SolveResult:
    timer = Timer()
    problem = evaluator.problem
    sizes = problem.sizes
    scores: Dict[Tuple[int, ...], Score] = {}

    def evaluate(individual):
        score = evaluator.evaluate(individual)
        scores[tuple(individual)] = score
        if score.conflicts > 0:
            return (float("inf"),)
        return (score.hard * 10 ** 5 + score.soft,)

    if problem.n == 1:
        results = []
        for l in range(sizes[0]):
            evaluate([l])
            results.append(((l,), scores[(l,)]))
        results.sort(key=lambda item: item[1].key)
        return result_from(NAME, results[:k], evaluator, timer, meta={"generations": 0})

    state = random.getstate()
    random.seed(seed)
    try:
        toolbox = base.Toolbox()
        toolbox.register("individual", lambda: creator.LegacyIndividual([random.randint(0, s - 1) for s in sizes]))
        toolbox.register("population", tools.initRepeat, list, toolbox.individual)
        toolbox.register("evaluate", evaluate)
        toolbox.register("mate", tools.cxUniform, indpb=0.5)
        toolbox.register("mutate", tools.mutUniformInt, low=0, up=[s - 1 for s in sizes], indpb=MUTATION)
        toolbox.register("select", tools.selNSGA2)
        population = toolbox.population(n=POPULATION)
        generations = generations_for(budget)
        algorithms.eaMuPlusLambda(population, toolbox, mu=POPULATION, lambda_=POPULATION, cxpb=CROSSOVER,
                                  mutpb=MUTATION, ngen=generations, verbose=False)
    finally:
        random.setstate(state)

    front = tools.sortNondominated(population, len(population), first_front_only=True)[0]
    unique = {tuple(ind): ind for ind in front}
    ordered = sorted(unique, key=lambda x: unique[x].fitness.values[0])
    # không trả lịch trùng lịch (B2); bản gốc trả cả lịch có điểm inf
    results = [(x, scores[x]) for x in ordered if scores[x].conflicts == 0][:k]
    return result_from(NAME, results, evaluator, timer, meta={"generations": generations})
