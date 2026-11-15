"""Backtracking + Branch & Bound, cho top-k đa dạng chính xác (design.md mục 3, 4).

Lặp k lần: lần r tìm lịch tốt nhất (theo vô hướng 10⁵·H + P) không trùng lịch và khác mọi
lịch đã chọn ít nhất d môn. Hết lịch ở khoảng cách d thì nới về d − 1 (giống `select_diverse`).
"""
from typing import List, Optional, Sequence, Tuple

from app.scheduling.constraints import Evaluator, Score
from app.scheduling.solvers.base import DEFAULT_TIME_LIMIT, SolveResult, Timer, result_from
from app.scheduling.topk import DEFAULT_K, min_distance

NAME = "bnb"


class _Timeout(Exception):
    pass


class BranchAndBound:
    def __init__(self, evaluator: Evaluator, timer: Timer, time_limit: float):
        self.ev = evaluator
        self.timer = timer
        self.time_limit = time_limit
        problem = evaluator.problem
        self.n = problem.n
        self.order = sorted(range(self.n), key=lambda i: (problem.sizes[i], i))
        self.opt_order = [sorted(range(size), key=lambda l, i=i: (evaluator.unary_scalar[i][l], l))
                          for i, size in enumerate(problem.sizes)]
        self.nodes = 0
        self.monotone = any(rule.constraint.metric in ("subjects_per_day", "subjects_per_session",
                                                         "periods_per_day", "study_days", "consecutive_periods")
                            and rule.constraint.max is not None for rule in evaluator.limits) or any(
            rule.constraint.relation == "different_day" for rule in evaluator.relations)
        self.timed_out = False

    def best(self, picked: Sequence[Tuple[int, ...]], distance: int) -> Optional[Tuple[Tuple[int, ...], Score]]:
        """Lịch tốt nhất khác mọi lịch trong `picked` ít nhất `distance` môn."""
        self.best_value = float("inf")
        self.best_x: Optional[Tuple[int, ...]] = None
        self.best_score: Optional[Score] = None
        self.picked = list(picked)
        self.distance = distance
        x: List[int] = [-1] * self.n
        try:
            self._dfs(0, x, 0, 0, [0] * len(self.picked))
        except _Timeout:
            self.timed_out = True
        if self.best_x is None:
            return None
        return self.best_x, self.best_score

    def _dfs(self, depth: int, x: List[int], occupied: int, cost: int, diffs: List[int]) -> None:
        self.nodes += 1
        if self.nodes % 2048 == 0 and self.timer.elapsed > self.time_limit:
            raise _Timeout
        ev = self.ev
        remaining = self.n - depth
        # đủ khác các lịch đã chọn?
        for diff in diffs:
            if diff + remaining < self.distance:
                return

        if depth == self.n:
            score = ev.evaluate(x)
            value = score.scalar
            if value < self.best_value:
                self.best_value, self.best_x, self.best_score = value, tuple(x), score
            return

        # cận dưới: phạt unary nhỏ nhất của các môn chưa gán, chỉ xét lớp không trùng với phần đã gán
        bound = cost
        for i in self.order[depth + 1:]:
            slots_i = ev.slots[i]
            unary_i = ev.unary_scalar[i]
            best_i = None
            for l in self.opt_order[i]:
                if not slots_i[l] & occupied:
                    best_i = unary_i[l]
                    break
            if best_i is None:
                return
            bound += best_i
        if self.monotone and depth:
            bound += ev.partial_nonseparable_bound({j: x[j] for j in self.order[:depth]})

        i = self.order[depth]
        slots_i = ev.slots[i]
        unary_i = ev.unary_scalar[i]
        for l in self.opt_order[i]:
            mask = slots_i[l]
            if mask & occupied:
                continue
            u = unary_i[l]
            # lớp tiếp theo có unary không nhỏ hơn, nên khi lớp này đã vượt cận thì dừng
            if bound + u >= self.best_value:
                break
            x[i] = l
            new_diffs = [diff + (p[i] != l) for diff, p in zip(diffs, self.picked)]
            self._dfs(depth + 1, x, occupied | mask, cost + u, new_diffs)
        x[i] = -1


def solve(evaluator: Evaluator, k: int = DEFAULT_K, time_limit: float = DEFAULT_TIME_LIMIT,
          distance: Optional[int] = None, **_) -> SolveResult:
    timer = Timer()
    search = BranchAndBound(evaluator, timer, time_limit)
    d = min_distance(evaluator.problem) if distance is None else distance
    chosen: List[Tuple[Tuple[int, ...], Score]] = []
    current = d
    while len(chosen) < k and current >= 1:
        found = search.best([x for x, _ in chosen], current)
        if search.timed_out:
            if found is not None:
                chosen.append(found)
            break
        if found is None:
            current -= 1
            continue
        chosen.append(found)
    chosen.sort(key=lambda item: (item[1].key, item[0]))
    return result_from(NAME, chosen, evaluator, timer, optimal=not search.timed_out,
                       meta={"nodes": search.nodes, "distance": d})
