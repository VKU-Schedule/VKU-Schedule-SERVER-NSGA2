"""Hàm chấm chung cho mọi solver (docs/specs/algorithms/design.md mục 2).

Ngữ nghĩa phạt: docs/specs/json_v2/design.md mục 6 (prefer/avoid/limit, ngoại lệ, mức độ,
giá trị không xác định) và 17 (review, relation).

`Evaluator(problem, document)` biên dịch các `NormalizedConstraint` một lần:
- `prefer` / `avoid`: hệ số 0/1 cho từng lớp ứng viên -> phạt tách được theo môn (unary);
- `limit`, `relation`: tính trên cả lịch.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, NamedTuple, Optional, Sequence, Tuple

from app.scheduling import vocab
from app.scheduling.model import ClassView, Problem
from app.scheduling.normalize import (
    NormalizedConstraint,
    NormalizedDocument,
    NormalizedFilter,
    fold_words,
    teacher_name_matches,
)

# Hằng số đổi (conflicts, H, P) sang một số vô hướng giữ thứ tự từ điển (design mục 2)
CONFLICT_SCALE = 10 ** 7
HARD_SCALE = 10 ** 5

OBJECTIVES = ("time", "people_place", "shape")
_PEOPLE_PLACE_KEYS = frozenset({"teacher", "class_group", "review", "language", "area", "room"})

REVIEW_SMOOTHING = 5  # α trong s = (p − q) / (n + α), json_v2/design.md 17.1


# ---------------------------------------------------------------------------
# Khớp bộ lọc với một lớp (json_v2/design.md mục 4, 6.7)
# ---------------------------------------------------------------------------


def attribute_known(view: ClassView, name: str) -> bool:
    if name in vocab.TIME_ATTRIBUTES:
        return view.scheduled
    if name == "course":
        return True
    if name in ("teacher", "review"):
        return view.teacher is not None
    if name == "class_group":
        return view.group is not None
    if name == "language":
        return view.language is not None
    if name == "area":
        return view.area is not None
    if name == "room":
        return view.room is not None
    raise KeyError(name)


def _in_intervals(value: int, intervals) -> bool:
    return any(low <= value <= high for low, high in intervals)


def attribute_matches(view: ClassView, name: str, value, touch: bool) -> bool:
    """Lớp có khớp một key của bộ lọc không. `touch=True` là quy tắc của `avoid` (có giao)."""
    if name == "course":
        return view.course in value
    if name == "teacher":
        return view.teacher in value
    if name == "class_group":
        return view.group in value
    if name == "language":
        return view.language in value
    if name == "day":
        return view.day in value
    if name == "area":
        return view.area in value
    if name == "room":
        return view.room in value
    if name in ("session", "periods"):
        periods = set(view.periods)
        return bool(periods & value) if touch else periods <= value
    if name == "start_period":
        return _in_intervals(view.start, value)
    if name == "end_period":
        return _in_intervals(view.end, value)
    if name == "start_time":
        return _in_intervals(view.start_minute, value)
    if name == "end_time":
        return _in_intervals(view.end_minute, value)
    if name == "duration":
        return _in_intervals(view.duration, value)
    raise KeyError(name)


def filter_matches(view: ClassView, normalized: NormalizedFilter, touch: bool = False) -> bool:
    """AND của mọi key. Thuộc tính không xác định thì không khớp."""
    return all(
        attribute_known(view, name) and attribute_matches(view, name, value, touch)
        for name, value in normalized.items()
    )


def in_scope(view: ClassView, constraint: NormalizedConstraint, extra_known: Sequence[str] = ()) -> bool:
    """Lớp thuộc S_c (json_v2/design.md 6.1): khớp scope, không bị exclude, thuộc tính dùng đều xác định."""
    for name in list(constraint.scope) + list(extra_known):
        if not attribute_known(view, name):
            return False
    if not filter_matches(view, constraint.scope):
        return False
    return not any(filter_matches(view, scope) for scope in constraint.exclude)


# ---------------------------------------------------------------------------
# Quy `review` về giảng viên (json_v2/design.md 17.1)
# ---------------------------------------------------------------------------


def resolve_review(constraint: NormalizedConstraint, problem: Problem, document: NormalizedDocument,
                   warnings: List[str]) -> List[NormalizedConstraint]:
    """Đổi một ràng buộc `review` thành các ràng buộc `teacher`, mỗi môn một ràng buộc."""
    target = constraint.condition["review"]
    scope_courses = constraint.scope.get("course") or frozenset(problem.courses)
    result = []
    for i, course in enumerate(problem.courses):
        if course not in scope_courses:
            continue
        scores: Dict[str, List[int]] = defaultdict(lambda: [0, 0, 0])
        for row in document.review_stats:
            if fold_words(row.subject) != fold_words(course):
                continue
            if target.aspect != vocab.REVIEW_ALL_ASPECTS and row.aspect != target.aspect:
                continue
            total = scores[row.lecturer]
            total[0] += row.positive
            total[1] += row.negative
            total[2] += row.total
        teachers = sorted({v.teacher for v in problem.options[i] if v.teacher})
        best_k, best = 0.0, set()
        for lecturer, (positive, negative, count) in scores.items():
            s = (positive - negative) / (count + REVIEW_SMOOTHING)
            k = s if target.sentiment == "positive" else -s
            matched = {t for t in teachers if teacher_name_matches(lecturer, t)}
            if k <= 0 or not matched:
                continue
            if k > best_k + 1e-12:
                best_k, best = k, set(matched)
            elif abs(k - best_k) <= 1e-12:
                best |= matched
        if not best:
            warnings.append(f"Ràng buộc {constraint.id}: 'review' không quy được về giảng viên nào của môn {course}")
            continue
        scope = dict(constraint.scope)
        scope["course"] = frozenset({course})
        result.append(NormalizedConstraint(
            id=constraint.id, kind=constraint.kind, level=constraint.level, weight=constraint.weight,
            source=constraint.source, condition={"teacher": frozenset(best)}, scope=scope,
            exclude=list(constraint.exclude),
        ))
    return result


# ---------------------------------------------------------------------------
# Dạng biên dịch
# ---------------------------------------------------------------------------


def objective_of(constraint: NormalizedConstraint) -> int:
    if constraint.kind in ("limit", "relation"):
        return 2
    return 1 if set(constraint.condition) & _PEOPLE_PLACE_KEYS else 0


@dataclass
class _Compiled:
    constraint: NormalizedConstraint
    hard: bool
    weight: int
    objective: int


@dataclass
class _LimitRule(_Compiled):
    member: List[List[bool]] = field(default_factory=list)  # member[i][l]: lớp l của môn i thuộc S_c


@dataclass
class _RelationRule(_Compiled):
    course_indices: Tuple[int, ...] = ()


class Score(NamedTuple):
    conflicts: int
    hard: int
    soft: int
    objectives: Tuple[int, int, int]

    @property
    def key(self) -> Tuple[int, int, int]:
        return self.conflicts, self.hard, self.soft

    @property
    def scalar(self) -> int:
        return self.conflicts * CONFLICT_SCALE + self.hard * HARD_SCALE + self.soft

    @property
    def violation(self) -> int:
        """CV của NSGA-II cải tiến: trùng lịch và `must`."""
        return self.conflicts * CONFLICT_SCALE + self.hard


class Violation(NamedTuple):
    constraint_id: int
    amount: int
    penalty: int
    hard: bool


# ---------------------------------------------------------------------------
# Chỉ số limit (json_v2/design.md mục 5, 6.3)
# ---------------------------------------------------------------------------


def _bound_penalty(value: int, low: Optional[int], high: Optional[int], squared: bool = False) -> int:
    over = max(0, value - high) if high is not None else 0
    under = max(0, low - value) if low is not None else 0
    if squared:
        return over * over + under * under
    return over + under


def _runs(periods: Sequence[int]) -> List[int]:
    """Độ dài các khối tiết liên tiếp."""
    runs, length, previous = [], 0, None
    for period in sorted(set(periods)):
        if previous is not None and period == previous + 1:
            length += 1
        else:
            if length:
                runs.append(length)
            length = 1
        previous = period
    if length:
        runs.append(length)
    return runs


def limit_violation(metric: str, low: Optional[int], high: Optional[int], classes: Sequence[ClassView],
                    max_only: bool = False) -> int:
    """v(c) của một `limit` trên các lớp đã thuộc S_c. `max_only`: chỉ số hạng `max` (cận dưới cho B&B)."""
    if max_only:
        low = None
    by_day: Dict[str, List[ClassView]] = defaultdict(list)
    for view in classes:
        by_day[view.day].append(view)
    if metric == "subjects_per_day":
        return sum(_bound_penalty(len(day), low, high, squared=True) for day in by_day.values())
    if metric == "subjects_per_session":
        sessions: Dict[Tuple[str, str], int] = defaultdict(int)
        for view in classes:
            sessions[(view.day, view.session)] += 1
        return sum(_bound_penalty(count, low, high) for count in sessions.values())
    if metric == "periods_per_day":
        return sum(_bound_penalty(sum(v.duration for v in day), low, high) for day in by_day.values())
    if metric == "study_days":
        return _bound_penalty(len(by_day), low, high)
    if metric == "consecutive_periods":
        return sum(max(0, run - high) for day in by_day.values()
                   for run in _runs([p for v in day for p in v.periods]))
    if metric == "gap_periods":
        total = 0
        for day in by_day.values():
            ordered = sorted(day, key=lambda v: (v.start, v.end))
            for first, second in zip(ordered, ordered[1:]):
                total += _bound_penalty(second.start - first.end - 1, low, high)
        return total
    raise KeyError(metric)


# metric mà số hạng `max` không giảm khi thêm lớp: dùng làm cận dưới của B&B
MONOTONE_MAX_METRICS = frozenset({
    "subjects_per_day", "subjects_per_session", "periods_per_day", "study_days", "consecutive_periods",
})


# ---------------------------------------------------------------------------
# relation (json_v2/design.md 17.2)
# ---------------------------------------------------------------------------


def relation_violation(relation: str, classes: Sequence[ClassView]) -> int:
    """`classes`: lớp được chọn của các môn, đúng thứ tự trong `courses`. Lớp không có lịch bị bỏ."""
    present = [view for view in classes if view.scheduled]
    if len(present) < 2:
        return 0
    if relation == "same_day":
        return 0 if len({view.day for view in present}) == 1 else 1
    if relation == "different_day":
        return sum(1 for i, a in enumerate(present) for b in present[i + 1:] if a.day == b.day)
    if relation == "before":
        return sum(1 for a, b in zip(present, present[1:]) if a.day != b.day or a.start >= b.start)
    raise KeyError(relation)


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------


class Evaluator:
    """Hàm chấm của một `Problem` với một `NormalizedDocument`. Đếm số lần chấm ở `evaluations`."""

    def __init__(self, problem: Problem, document: NormalizedDocument):
        self.problem = problem
        self.document = document
        self.warnings: List[str] = []
        self.evaluations = 0
        n = problem.n

        constraints: List[NormalizedConstraint] = []
        for constraint in document.constraints:
            if constraint.kind in vocab.FILTER_KINDS and "review" in constraint.condition:
                constraints.extend(resolve_review(constraint, problem, document, self.warnings))
            else:
                constraints.append(constraint)
        self.constraints = constraints

        # unary[i][l] = (H, P, (o_time, o_people, o_shape))
        hard = [[0] * len(opts) for opts in problem.options]
        soft = [[0] * len(opts) for opts in problem.options]
        objs = [[[0, 0, 0] for _ in opts] for opts in problem.options]
        self.filter_rules: List[Tuple[_Compiled, List[List[int]]]] = []
        self.limits: List[_LimitRule] = []
        self.relations: List[_RelationRule] = []

        for constraint in constraints:
            is_hard = constraint.level == "must"
            objective = objective_of(constraint)
            if constraint.kind in vocab.FILTER_KINDS:
                touch = constraint.kind == "avoid"
                used = list(constraint.condition)
                coeff = []
                for i, opts in enumerate(problem.options):
                    row = []
                    for view in opts:
                        violated = 0
                        if in_scope(view, constraint, used):
                            match = filter_matches(view, constraint.condition, touch)
                            violated = int(match if touch else not match)
                        row.append(violated)
                        if violated:
                            l = len(row) - 1
                            if is_hard:
                                hard[i][l] += 1
                            else:
                                soft[i][l] += constraint.weight
                                objs[i][l][objective] += constraint.weight
                    coeff.append(row)
                self.filter_rules.append((_Compiled(constraint, is_hard, constraint.weight, objective), coeff))
            elif constraint.kind == "limit":
                member = [[view.scheduled and in_scope(view, constraint) for view in opts]
                          for opts in problem.options]
                self.limits.append(_LimitRule(constraint, is_hard, constraint.weight, objective, member))
            elif constraint.kind == "relation":
                index = {course: i for i, course in enumerate(problem.courses)}
                courses = tuple(index[c] for c in constraint.courses if c in index)
                self.relations.append(_RelationRule(constraint, is_hard, constraint.weight, objective, courses))

        self.unary_hard = hard
        self.unary_soft = soft
        self.unary_objs = [[tuple(o) for o in row] for row in objs]
        self.unary_scalar = [[hard[i][l] * HARD_SCALE + soft[i][l] for l in range(len(problem.options[i]))]
                             for i in range(n)]

        # trùng lịch: conflict[i][j] = tập cặp (a, b), chỉ với i < j
        self.slots = [[view.slots for view in opts] for opts in problem.options]

    # -- chấm ---------------------------------------------------------------

    def conflicts(self, x: Sequence[int]) -> int:
        masks = [self.slots[i][x[i]] for i in range(self.problem.n)]
        count = 0
        for i in range(len(masks)):
            mi = masks[i]
            if not mi:
                continue
            for j in range(i + 1, len(masks)):
                if mi & masks[j]:
                    count += 1
        return count

    def _nonseparable(self, x: Sequence[int], views: List[ClassView]):
        hard, soft, objs = 0, 0, [0, 0, 0]
        details: List[Tuple[_Compiled, int]] = []
        for rule in self.limits:
            members = [views[i] for i in range(len(views)) if rule.member[i][x[i]]]
            c = rule.constraint
            v = limit_violation(c.metric, c.min, c.max, members)
            if v:
                details.append((rule, v))
        for rule in self.relations:
            v = relation_violation(rule.constraint.relation, [views[i] for i in rule.course_indices])
            if v:
                details.append((rule, v))
        for rule, v in details:
            if rule.hard:
                hard += v
            else:
                soft += rule.weight * v
                objs[rule.objective] += rule.weight * v
        return hard, soft, objs, details

    def evaluate(self, x: Sequence[int]) -> Score:
        self.evaluations += 1
        problem = self.problem
        views = [problem.options[i][x[i]] for i in range(problem.n)]
        hard = soft = 0
        objs = [0, 0, 0]
        for i in range(problem.n):
            l = x[i]
            hard += self.unary_hard[i][l]
            soft += self.unary_soft[i][l]
            o = self.unary_objs[i][l]
            objs[0] += o[0]
            objs[1] += o[1]
            objs[2] += o[2]
        h2, s2, o2, _ = self._nonseparable(x, views)
        return Score(self.conflicts(x), hard + h2, soft + s2,
                     (objs[0] + o2[0], objs[1] + o2[1], objs[2] + o2[2]))

    def explain(self, x: Sequence[int]) -> List[Violation]:
        """Vi phạm theo từng ràng buộc gốc (gộp các ràng buộc con của `review`)."""
        totals: Dict[int, List] = {}

        def add(rule: _Compiled, amount: int):
            entry = totals.setdefault(rule.constraint.id, [0, 0, rule.hard])
            entry[0] += amount
            entry[1] += 0 if rule.hard else rule.weight * amount

        for rule, coeff in self.filter_rules:
            amount = sum(coeff[i][x[i]] for i in range(self.problem.n))
            if amount:
                add(rule, amount)
        views = self.problem.classes(x)
        for rule, amount in self._nonseparable(x, views)[3]:
            add(rule, amount)
        return [Violation(cid, amount, penalty, hard) for cid, (amount, penalty, hard) in sorted(totals.items())]

    # -- cận dưới cho B&B -------------------------------------------------------

    def partial_nonseparable_bound(self, assigned: Dict[int, int]) -> int:
        """Cận dưới (vô hướng) của phần limit/relation khi mới gán một phần các môn."""
        bound = 0
        for rule in self.limits:
            c = rule.constraint
            if c.metric not in MONOTONE_MAX_METRICS or c.max is None:
                continue
            members = [self.problem.options[i][l] for i, l in assigned.items() if rule.member[i][l]]
            v = limit_violation(c.metric, c.min, c.max, members, max_only=True)
            if v:
                bound += v * HARD_SCALE if rule.hard else v * rule.weight
        for rule in self.relations:
            if rule.constraint.relation != "different_day":
                continue
            views = [self.problem.options[i][assigned[i]] for i in rule.course_indices if i in assigned]
            v = relation_violation("different_day", views)
            if v:
                bound += v * HARD_SCALE if rule.hard else v * rule.weight
        return bound

    @property
    def has_nonseparable(self) -> bool:
        return bool(self.limits or self.relations)


def infeasible_report(evaluator: Evaluator, x: Sequence[int]) -> List[Dict]:
    """Ràng buộc `must` còn vi phạm ở lịch tốt nhất, kèm lý do (json_v2/design.md 6.6)."""
    report = []
    problem = evaluator.problem
    for v in evaluator.explain(x):
        if not v.hard:
            continue
        reason = "Không lịch nào thoả đồng thời ràng buộc này với các ràng buộc cứng khác"
        for rule, coeff in evaluator.filter_rules:
            if rule.constraint.id != v.constraint_id:
                continue
            for i, row in enumerate(coeff):
                if row and all(row):
                    reason = f"Không lớp nào của môn {problem.courses[i]} thoả"
                    break
        report.append({"constraint_id": v.constraint_id, "amount": v.amount, "reason": reason})
    return report
