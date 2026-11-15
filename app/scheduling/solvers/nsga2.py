"""NSGA-II cải tiến (design.md mục 3).

So với bản gốc:
- 3 mục tiêu: phạt thời gian, phạt người và nơi, phạt hình dạng lịch (`Score.objectives`);
- xử lý ràng buộc theo tính khả thi của Deb: lời giải "khả thi" (không trùng lịch, H bằng H nhỏ nhất
  đã gặp) thắng lời giải không khả thi; hai lời giải không khả thi so theo CV = 10⁷·conflicts + H;
  hai lời giải khả thi so theo hạng Pareto rồi crowding;
- toán tử sửa: gán lại lớp không trùng lịch cho môn đang trùng (`repair`);
- lời giải đã gặp không chấm lại;
- 5 lịch đại diện lấy từ front: lịch có P nhỏ nhất, rồi lịch tốt nhất theo từng mục tiêu, rồi theo crowding.
"""
import random
from typing import Dict, List, Optional, Sequence, Tuple

from app.scheduling.constraints import Evaluator, Score
from app.scheduling.solvers.base import DEFAULT_BUDGET, SolveResult, Timer, random_solution, repair, result_from
from app.scheduling.topk import DEFAULT_K, Archive, hamming, min_distance

NAME = "nsga2"
POPULATION = 40
CROSSOVER = 0.9
FINAL_POOL = 200


def dominates(a: Sequence[int], b: Sequence[int]) -> bool:
    return a[0] <= b[0] and a[1] <= b[1] and a[2] <= b[2] and a != b


def non_dominated_fronts(points: List[Sequence[int]]) -> List[List[int]]:
    """Fast non-dominated sort (Deb 2002): danh sách các front, mỗi front là list chỉ số."""
    n = len(points)
    dominated_by: List[List[int]] = [[] for _ in range(n)]
    counts = [0] * n
    fronts: List[List[int]] = [[]]
    for p in range(n):
        for q in range(n):
            if p == q:
                continue
            if dominates(points[p], points[q]):
                dominated_by[p].append(q)
            elif dominates(points[q], points[p]):
                counts[p] += 1
        if counts[p] == 0:
            fronts[0].append(p)
    while fronts[-1]:
        nxt = []
        for p in fronts[-1]:
            for q in dominated_by[p]:
                counts[q] -= 1
                if counts[q] == 0:
                    nxt.append(q)
        fronts.append(nxt)
    return fronts[:-1]


def crowding(points: List[Sequence[int]], front: List[int]) -> Dict[int, float]:
    distance = {i: 0.0 for i in front}
    if len(front) <= 2:
        return {i: float("inf") for i in front}
    for m in range(len(points[front[0]])):
        ordered = sorted(front, key=lambda i: points[i][m])
        low, high = points[ordered[0]][m], points[ordered[-1]][m]
        distance[ordered[0]] = distance[ordered[-1]] = float("inf")
        if high == low:
            continue
        for a, b, c in zip(ordered, ordered[1:], ordered[2:]):
            distance[b] += (points[c][m] - points[a][m]) / (high - low)
    return distance


class _Ranked:
    """Hạng và crowding của một tập lời giải theo quy tắc Deb."""

    def __init__(self, xs: List[Tuple[int, ...]], scores: List[Score], best_hard: int):
        feasible = [j for j, s in enumerate(scores) if s.conflicts == 0 and s.hard <= best_hard]
        infeasible = sorted((j for j, s in enumerate(scores) if not (s.conflicts == 0 and s.hard <= best_hard)),
                            key=lambda j: scores[j].violation)
        points = [scores[j].objectives for j in range(len(scores))]
        self.rank: Dict[int, int] = {}
        self.crowd: Dict[int, float] = {}
        self.order: List[int] = []
        sub = [points[j] for j in feasible]
        for r, front in enumerate(non_dominated_fronts(sub) if feasible else []):
            members = [feasible[i] for i in front]
            dist = crowding(points, members)
            for j in members:
                self.rank[j] = r
                self.crowd[j] = dist[j]
            self.order += sorted(members, key=lambda j: -dist[j])
        base = len(self.order) + 1
        for offset, j in enumerate(infeasible):
            self.rank[j] = base + offset
            self.crowd[j] = 0.0
        self.order += infeasible

    def better(self, a: int, b: int) -> bool:
        if self.rank[a] != self.rank[b]:
            return self.rank[a] < self.rank[b]
        return self.crowd[a] > self.crowd[b]


def representatives(candidates: List[Tuple[Tuple[int, ...], Score]], k: int, d: int) -> List[Tuple[Tuple[int, ...], Score]]:
    """5 lịch đại diện trên front (design.md mục 3)."""
    usable = [(x, s) for x, s in candidates if s.conflicts == 0]
    if not usable:
        return []
    best_hard = min(s.hard for _, s in usable)
    usable = [(x, s) for x, s in usable if s.hard == best_hard]
    points = [s.objectives for _, s in usable]
    chosen: List[int] = []
    for distance in range(d, 0, -1):
        for front in non_dominated_fronts(points):
            dist = crowding(points, front)
            picks = [min(front, key=lambda j: (usable[j][1].soft, usable[j][0]))]
            for m in range(3):
                picks.append(min(front, key=lambda j: (points[j][m], usable[j][1].soft, usable[j][0])))
            picks += sorted(front, key=lambda j: (-dist[j], usable[j][1].soft, usable[j][0]))
            for j in picks:
                if len(chosen) >= k:
                    break
                if j in chosen:
                    continue
                if all(hamming(usable[j][0], usable[c][0]) >= distance for c in chosen):
                    chosen.append(j)
            if len(chosen) >= k:
                break
        if len(chosen) >= k:
            break
    result = [usable[j] for j in chosen]
    result.sort(key=lambda item: (item[1].key, item[0]))
    return result


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
    free = [i for i in range(n) if sizes[i] > 1]
    mutation = 1.0 / max(1, len(free))
    best_hard = [float("inf")]

    def evaluate(x) -> Score:
        key = tuple(x)
        score = archive.items.get(key)
        if score is None:
            score = evaluator.evaluate(x)
            archive.add(key, score)
            if score.conflicts == 0:
                best_hard[0] = min(best_hard[0], score.hard)
        return score

    population = []
    for _ in range(min(POPULATION, budget)):
        population.append(tuple(repair(evaluator, random_solution(rng, sizes), rng)))
    population = list(dict.fromkeys(population))
    scores = [evaluate(x) for x in population]
    ranked = _Ranked(population, scores, best_hard[0])

    # lời giải đã gặp không tốn ngân sách, nên giới hạn thêm số thế hệ (không gian nhỏ)
    generation, max_generations = 0, 2 * budget // POPULATION + 1
    while used() < budget and free and generation < max_generations:
        generation += 1
        if time_limit and timer.elapsed > time_limit:
            break

        def pick():
            a, b = rng.randrange(len(population)), rng.randrange(len(population))
            return population[a] if ranked.better(a, b) else population[b]

        offspring = []
        for _ in range(POPULATION):
            if used() >= budget:
                break
            p1, p2 = pick(), pick()
            child = [p1[i] if rng.random() < 0.5 else p2[i] for i in range(n)] if rng.random() < CROSSOVER else list(p1)
            for i in free:
                if rng.random() < mutation:
                    child[i] = rng.randrange(sizes[i])
            child = tuple(repair(evaluator, child, rng))
            evaluate(child)
            offspring.append(child)

        merged = list(dict.fromkeys(population + offspring))
        merged_scores = [archive.items[x] for x in merged]
        ranked_all = _Ranked(merged, merged_scores, best_hard[0])
        keep = ranked_all.order[:POPULATION]
        population = [merged[j] for j in keep]
        scores = [merged_scores[j] for j in keep]
        ranked = _Ranked(population, scores, best_hard[0])

    pool = sorted(((x, s) for x, s in archive.items.items() if s.conflicts == 0),
                  key=lambda item: (item[1].key, item[0]))[:FINAL_POOL]
    pool += [(x, archive.items[x]) for x in population]
    pool = list({x: (x, s) for x, s in pool}.values())
    return result_from(NAME, representatives(pool, k, min_distance(problem)), evaluator, timer,
                       meta={"archive": len(archive.items), "generations": generation})
