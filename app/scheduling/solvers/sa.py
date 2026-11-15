"""Simulated Annealing (design.md mục 3).

Láng giềng: đổi lớp của một môn. Nửa số lần, lớp mới được chọn trong các lớp không trùng lịch
với phần còn lại của lịch. Nhiệt độ hạ hình học từ T₀ (ước lượng từ mẫu Δ) về T₀/1000;
ngân sách chia đều cho 3 lần khởi động.
"""
import math
import random
from typing import List, Optional

from app.scheduling.constraints import Evaluator
from app.scheduling.solvers.base import DEFAULT_BUDGET, SolveResult, Timer, random_solution, repair, result_from
from app.scheduling.topk import DEFAULT_K, Archive, min_distance

NAME = "sa"
RESTARTS = 3
FINAL_RATIO = 1e-3


def _neighbor(evaluator: Evaluator, x: List[int], free: List[int], rng: random.Random) -> List[int]:
    y = list(x)
    i = rng.choice(free)
    size = len(evaluator.slots[i])
    if rng.random() < 0.5:
        occupied = 0
        for j, l in enumerate(y):
            if j != i:
                occupied |= evaluator.slots[j][l]
        choices = [l for l in range(size) if l != y[i] and not evaluator.slots[i][l] & occupied]
        if choices:
            y[i] = rng.choice(choices)
            return y
    y[i] = rng.choice([l for l in range(size) if l != y[i]])
    return y


def solve(evaluator: Evaluator, k: int = DEFAULT_K, budget: int = DEFAULT_BUDGET, seed: int = 0,
          time_limit: Optional[float] = None, **_) -> SolveResult:
    timer = Timer()
    rng = random.Random(seed)
    problem = evaluator.problem
    archive = Archive()
    start = evaluator.evaluations
    used = lambda: evaluator.evaluations - start
    free = [i for i, size in enumerate(problem.sizes) if size > 1]

    def evaluate(x):
        score = archive.items.get(tuple(x))
        if score is None:            # như GA: lời giải đã gặp không chấm lại, không tốn ngân sách
            score = evaluator.evaluate(x)
            archive.add(x, score)
        return score

    if not free:
        evaluate([0] * problem.n)
        return result_from(NAME, archive.select(k, min_distance(problem)), evaluator, timer)

    # T₀: trung vị |Δ| dương của các bước ngẫu nhiên (chỉ tính phần phạt mềm để không bị trùng lịch lấn át)
    x = repair(evaluator, random_solution(rng, problem.sizes), rng)
    fx = evaluate(x).scalar
    deltas = []
    for _ in range(min(30, max(1, budget // 20))):
        y = _neighbor(evaluator, x, free, rng)
        delta = abs(evaluate(y).scalar - fx)
        if 0 < delta < 10 ** 5:
            deltas.append(delta)
    t0 = sorted(deltas)[len(deltas) // 2] if deltas else 1.0

    segment = max(1, (budget - used()) // RESTARTS)
    for restart in range(RESTARTS):
        if used() >= budget:
            break
        if restart:
            x = repair(evaluator, random_solution(rng, problem.sizes), rng)
            fx = evaluate(x).scalar
        steps = max(1, min(segment, budget - used()))
        begin = used()
        # nhiệt độ theo số lần đánh giá đã dùng; giới hạn số bước để không lặp mãi ở không gian nhỏ
        for _ in range(20 * steps):
            progress = (used() - begin) / steps
            if progress >= 1 or used() >= budget or (time_limit and timer.elapsed > time_limit):
                break
            temperature = t0 * FINAL_RATIO ** progress
            y = _neighbor(evaluator, x, free, rng)
            fy = evaluate(y).scalar
            delta = fy - fx
            if delta <= 0 or rng.random() < math.exp(-delta / max(temperature, 1e-9)):
                x, fx = y, fy
    return result_from(NAME, archive.select(k, min_distance(problem)), evaluator, timer,
                       meta={"t0": t0, "archive": len(archive.items)})
