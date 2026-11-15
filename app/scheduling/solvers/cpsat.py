"""CP-SAT (OR-Tools), cho top-k đa dạng chính xác (design.md mục 3; json_v2/design.md 6.8, 17.2).

Biến x[i][l] ∈ {0, 1}: chọn lớp l của môn i. Mục tiêu 10⁵·H + P (thứ tự từ điển H rồi P).
Mỗi vòng thêm cắt "khác các lịch đã chọn ít nhất d môn".
"""
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from ortools.sat.python import cp_model

from app.scheduling import vocab
from app.scheduling.constraints import HARD_SCALE, Evaluator, Score, _bound_penalty
from app.scheduling.solvers.base import DEFAULT_TIME_LIMIT, SolveResult, Timer, result_from
from app.scheduling.topk import DEFAULT_K, min_distance

NAME = "cpsat"


class _Model:
    def __init__(self, evaluator: Evaluator):
        self.ev = ev = evaluator
        problem = ev.problem
        self.model = m = cp_model.CpModel()
        n = problem.n
        self.x = [[m.NewBoolVar(f"x{i}_{l}") for l in range(size)] for i, size in enumerate(problem.sizes)]
        for row in self.x:
            m.AddExactlyOne(row)

        # trùng lịch: mỗi (thứ, tiết) có tối đa một lớp
        cover: Dict[Tuple[str, int], List] = defaultdict(list)
        for i, opts in enumerate(problem.options):
            for l, view in enumerate(opts):
                for period in view.periods:
                    cover[(view.day, period)].append(self.x[i][l])
        for vars_ in cover.values():
            if len(vars_) > 1:
                m.AddAtMostOne(vars_)

        hard_terms = [ev.unary_hard[i][l] * self.x[i][l] for i in range(n)
                      for l in range(problem.sizes[i]) if ev.unary_hard[i][l]]
        soft_terms = [ev.unary_soft[i][l] * self.x[i][l] for i in range(n)
                      for l in range(problem.sizes[i]) if ev.unary_soft[i][l]]

        self._unscheduled = [sum(self.x[i][l] for l, v in enumerate(opts) if not v.scheduled)
                             for i, opts in enumerate(problem.options)]
        for rule in ev.limits:
            v = self._limit(rule)
            if v is not None:
                (hard_terms if rule.hard else soft_terms).append(v if rule.hard else rule.weight * v)
        for rule in ev.relations:
            v = self._relation(rule)
            if v is not None:
                (hard_terms if rule.hard else soft_terms).append(v if rule.hard else rule.weight * v)
        self.hard = sum(hard_terms) if hard_terms else 0
        self.soft = sum(soft_terms) if soft_terms else 0

    # -- limit (json_v2/design.md 6.8) -----------------------------------------

    def _int(self, high: int, name: str):
        return self.model.NewIntVar(0, max(0, high), name)

    def _unit_terms(self, count, has_class, low, high, squared, cap, tag):
        """Biến phạt của một đơn vị: max(0, m − max) [+ max(0, min·b − m)], bình phương nếu cần."""
        m = self.model
        terms = []
        if high is not None:
            e = self._int(cap, f"e_{tag}")
            m.Add(e >= count - high)
            terms.append(e)
        if low is not None:
            d = self._int(low, f"d_{tag}")
            m.Add(d >= low * has_class - count)
            terms.append(d)
        if not squared:
            return terms
        result = []
        for t, var in enumerate(terms):
            sq = self._int(cap * cap, f"sq_{tag}_{t}")
            m.AddMultiplicationEquality(sq, [var, var])
            result.append(sq)
        return result

    def _indicator(self, vars_, tag):
        """b = 1 khi có ít nhất một biến bằng 1."""
        b = self.model.NewBoolVar(f"b_{tag}")
        for var in vars_:
            self.model.Add(b >= var)
        self.model.Add(b <= sum(vars_))
        return b

    def _limit(self, rule):
        ev, m = self.ev, self.model
        c = rule.constraint
        members = [(i, l, view) for i, opts in enumerate(ev.problem.options)
                   for l, view in enumerate(opts) if rule.member[i][l]]
        n = ev.problem.n
        tag = f"c{c.id}_{id(rule)}"
        terms = []
        if c.metric in ("subjects_per_day", "periods_per_day", "subjects_per_session"):
            units: Dict[Tuple, List] = defaultdict(list)
            for i, l, view in members:
                key = (view.day, view.session) if c.metric == "subjects_per_session" else (view.day,)
                units[key].append((self.x[i][l], view.duration if c.metric == "periods_per_day" else 1))
            cap = n * (vocab.MAX_PERIOD if c.metric == "periods_per_day" else 1)
            for u, (key, items) in enumerate(units.items()):
                count = sum(coef * var for var, coef in items)
                has = self._indicator([var for var, _ in items], f"{tag}_{u}") if c.min is not None else 0
                terms += self._unit_terms(count, has, c.min, c.max, c.metric == "subjects_per_day", cap, f"{tag}_{u}")
        elif c.metric == "study_days":
            by_day: Dict[str, List] = defaultdict(list)
            for i, l, view in members:
                by_day[view.day].append(self.x[i][l])
            days = [self._indicator(vars_, f"{tag}_{d}") for d, vars_ in by_day.items()]
            count = sum(days) if days else 0
            terms += self._unit_terms(count, 1, c.min, c.max, False, len(vocab.DAYS), tag)
        elif c.metric == "consecutive_periods":
            occupied: Dict[Tuple[str, int], List] = defaultdict(list)
            for i, l, view in members:
                for p in view.periods:
                    occupied[(view.day, p)].append(self.x[i][l])
            days = {d for d, _ in occupied}
            for d in days:
                for t in range(vocab.MIN_PERIOD, vocab.MAX_PERIOD - c.max + 1):
                    window = [var for p in range(t, t + c.max + 1) for var in occupied.get((d, p), [])]
                    if len(window) <= c.max:
                        continue
                    w = self._int(1, f"w_{tag}_{d}_{t}")
                    m.Add(w >= sum(window) - c.max)
                    terms.append(w)
        elif c.metric == "gap_periods":
            by_day: Dict[str, List] = defaultdict(list)
            for i, l, view in members:
                by_day[view.day].append((i, l, view))
            for d, items in by_day.items():
                for ia, la, a in items:
                    for ib, lb, b in items:
                        if ia == ib or not (a.start, a.end) < (b.start, b.end) or a.end >= b.start:
                            continue
                        dev = _bound_penalty(b.start - a.end - 1, c.min, c.max)
                        if not dev:
                            continue
                        between = [self.x[ic][lc] for ic, lc, cv in items
                                   if ic not in (ia, ib) and (a.start, a.end) < (cv.start, cv.end) < (b.start, b.end)]
                        q = self._int(1, f"q_{tag}_{ia}_{la}_{ib}_{lb}")
                        m.Add(q >= self.x[ia][la] + self.x[ib][lb] - 1 - sum(between))
                        terms.append(dev * q)
        else:
            raise KeyError(c.metric)
        return sum(terms) if terms else None

    # -- relation (json_v2/design.md 17.2) --------------------------------------

    def _on_day(self, i):
        days: Dict[str, List] = defaultdict(list)
        for l, view in enumerate(self.ev.problem.options[i]):
            if view.scheduled:
                days[view.day].append(self.x[i][l])
        return days

    def _relation(self, rule):
        m = self.model
        courses = rule.course_indices
        tag = f"r{rule.constraint.id}_{id(rule)}"
        relation = rule.constraint.relation
        if len(courses) < 2:
            return None
        if relation == "different_day":
            terms = []
            day_vars = {i: self._on_day(i) for i in courses}
            for a in range(len(courses)):
                for b in range(a + 1, len(courses)):
                    da, db = day_vars[courses[a]], day_vars[courses[b]]
                    for d in set(da) & set(db):
                        z = self._int(1, f"z_{tag}_{a}_{b}_{d}")
                        m.Add(z >= sum(da[d]) + sum(db[d]) - 1)
                        terms.append(z)
            return sum(terms) if terms else None
        if relation == "same_day":
            day_vars = {i: self._on_day(i) for i in courses}
            ys = []
            for d in vocab.DAYS:
                y = m.NewBoolVar(f"y_{tag}_{d}")
                for i in courses:
                    m.Add(y <= sum(day_vars[i].get(d, [])) + self._unscheduled[i])
                ys.append(y)
            present = sum(1 - self._unscheduled[i] for i in courses)
            g = m.NewBoolVar(f"g_{tag}")
            m.Add(present >= 2).OnlyEnforceIf(g)
            m.Add(present <= 1).OnlyEnforceIf(g.Not())
            v = m.NewBoolVar(f"v_{tag}")
            m.Add(v + sum(ys) >= 1).OnlyEnforceIf(g)
            return v
        if relation == "before":
            terms = []
            options = self.ev.problem.options
            for a in range(len(courses)):
                for b in range(a + 1, len(courses)):
                    ia, ib = courses[a], courses[b]
                    dropped_between = [1 - self._unscheduled[courses[mid]] for mid in range(a + 1, b)]
                    for la, va in enumerate(options[ia]):
                        if not va.scheduled:
                            continue
                        for lb, vb in enumerate(options[ib]):
                            if not vb.scheduled or (va.day == vb.day and va.start < vb.start):
                                continue
                            z = self._int(1, f"z_{tag}_{a}_{la}_{b}_{lb}")
                            m.Add(z >= self.x[ia][la] + self.x[ib][lb] - 1 - sum(dropped_between))
                            terms.append(z)
            return sum(terms) if terms else None
        raise KeyError(relation)

    # -- giải ---------------------------------------------------------------------

    def solve_round(self, picked, distance, time_left, workers, seed) -> Tuple[Optional[Tuple[int, ...]], bool]:
        """Trả (x, optimal). x là None khi không còn lịch nào thoả cắt đa dạng."""
        m = self.model
        n = self.ev.problem.n
        for p in picked[self._cuts:]:
            m.Add(sum(self.x[i][p[i]] for i in range(n)) <= n - distance)
        self._cuts = len(picked)
        if not self._objective_set:
            # thứ tự từ điển (H, P) qua cùng vô hướng 10⁵·H + P với B&B và metaheuristic (design.md mục 2)
            m.Minimize(HARD_SCALE * self.hard + self.soft)
            self._objective_set = True
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = max(0.05, time_left())
        solver.parameters.num_search_workers = workers
        solver.parameters.random_seed = seed
        status = solver.Solve(m)
        if status in (cp_model.INFEASIBLE, cp_model.MODEL_INVALID):
            return None, True
        if status == cp_model.UNKNOWN:
            return None, False
        x = tuple(next(l for l, var in enumerate(row) if solver.Value(var)) for row in self.x)
        return x, status == cp_model.OPTIMAL

    _objective_set = False

    _cuts = 0


def solve(evaluator: Evaluator, k: int = DEFAULT_K, time_limit: float = DEFAULT_TIME_LIMIT,
          distance: Optional[int] = None, workers: int = 1, seed: int = 0, **_) -> SolveResult:
    timer = Timer()
    model = _Model(evaluator)
    d = min_distance(evaluator.problem) if distance is None else distance
    chosen: List[Tuple[Tuple[int, ...], Score]] = []
    all_optimal = True
    current = d
    while len(chosen) < k and current >= 1:
        left = lambda: time_limit - timer.elapsed
        if left() <= 0:
            all_optimal = False
            break
        x, optimal = model.solve_round([c[0] for c in chosen], current, left, workers, seed)
        if x is None:
            if not optimal:
                all_optimal = False
                break
            current -= 1
            model = _Model(evaluator)   # nới d: các cắt cũ (khoảng cách d) chặt hơn cần thiết
            continue
        all_optimal = all_optimal and optimal
        chosen.append((x, evaluator.evaluate(x)))
    chosen.sort(key=lambda item: (item[1].key, item[0]))
    return result_from(NAME, chosen, evaluator, timer, optimal=all_optimal, meta={"distance": d})
