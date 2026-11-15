"""Solver (Phần B, task B7): so với duyệt toàn bộ trên instance nhỏ."""
import itertools

import pytest

from app.scheduling.constraints import Evaluator
from app.scheduling.model import build_problem
from app.scheduling.normalize import normalize_document
from app.scheduling.solvers import EXACT, METAHEURISTICS, SOLVERS
from app.scheduling.topk import hamming, min_distance
from conftest import AUTOMAT, CANDIDATES, CTDL, JAVA, MANG, REVIEW_STATS, TRIET, design_example

COURSES = [AUTOMAT, CTDL, JAVA, MANG, TRIET, "Bảo mật và an toàn hệ thống thông tin", "Chủ nghĩa xã hội khoa học"]
SMALL = {course: CANDIDATES[course] for course in COURSES}

# một ràng buộc cho mỗi loại limit / relation, để kiểm tra mô hình CP-SAT từng phần
SINGLE = [
    {"limit": "subjects_per_day", "max": 1},
    {"limit": "subjects_per_day", "min": 2},
    {"limit": "subjects_per_session", "max": 1},
    {"limit": "subjects_per_session", "min": 2, "max": 2},
    {"limit": "periods_per_day", "max": 4},
    {"limit": "periods_per_day", "min": 5},
    {"limit": "gap_periods", "min": 1},
    {"limit": "gap_periods", "max": 0},
    {"limit": "gap_periods", "min": 1, "max": 2, "scope": {"day": "thứ 4"}},
    {"limit": "consecutive_periods", "max": 3},
    {"limit": "study_days", "max": 2},
    {"limit": "study_days", "min": 5},
    {"relation": "same_day", "courses": ["Automat", "Mạng máy tính"]},
    {"relation": "same_day", "courses": ["Automat", "Mạng máy tính", "Triết học"]},
    {"relation": "different_day", "courses": ["Automat", "Cấu trúc dữ liệu", "Lập trình Java"]},
    {"relation": "before", "courses": ["Cấu trúc dữ liệu", "Lập trình Java"]},
    {"relation": "before", "courses": ["Lập trình Java", "Mạng máy tính", "Automat"]},
    {"prefer": {"session": "sáng"}, "level": "must"},
]

MIXED = design_example("12.2")["constraints"] + [
    {"limit": "gap_periods", "min": 1},
    {"limit": "subjects_per_day", "max": 2},
    {"relation": "different_day", "courses": ["Automat", "Mạng máy tính"]},
    {"prefer": {"review": {"phrase": "giảng viên dạy dễ hiểu", "aspect": "ky_nang_giang_day",
                           "sentiment": "positive"}}},
]


def make(constraints, candidates=SMALL, pinned=None):
    doc = normalize_document({"constraints": constraints}, list(candidates), candidates, REVIEW_STATS)
    # MIXED nhắc môn không có trong SMALL (Tiếng anh nâng cao 4): ràng buộc đó vào unsupported
    assert all("Tiếng anh nâng cao 4" in u.reason for u in doc.unsupported), [u.reason for u in doc.unsupported]
    return Evaluator(build_problem(candidates, pinned), doc)


def brute(ev):
    space = itertools.product(*[range(size) for size in ev.problem.sizes])
    return [(x, ev.evaluate(x)) for x in space]


def greedy_check(ev, schedules, everything, d):
    """Lịch hạng r là lịch tốt nhất khác các lịch hạng trước ít nhất d môn (top-k đa dạng chính xác)."""
    picked = []
    for schedule in sorted(schedules, key=lambda s: s.score.key):
        allowed = [s.scalar for x, s in everything if s.conflicts == 0
                   and all(hamming(x, p) >= d for p in picked)]
        assert schedule.score.scalar == min(allowed)
        picked.append(schedule.x)


@pytest.mark.parametrize("constraint", SINGLE, ids=lambda c: c.get("limit") or c.get("relation") or "must")
def test_cpsat_matches_brute_force_per_constraint(constraint):
    ev = make([constraint])
    best = min(s.scalar for _, s in brute(ev) if s.conflicts == 0)
    result = SOLVERS["cpsat"](make([constraint]), k=1, time_limit=20)
    assert result.optimal and result.schedules[0].score.scalar == best


@pytest.mark.parametrize("name", EXACT)
def test_exact_solvers_give_exact_diverse_top5(name):
    ev = make(MIXED)
    everything = brute(ev)
    result = SOLVERS[name](make(MIXED), k=5, time_limit=30)
    assert result.optimal and len(result.schedules) == 5
    greedy_check(ev, result.schedules, everything, min_distance(ev.problem))


def test_bnb_and_cpsat_agree_on_best():
    a = SOLVERS["bnb"](make(MIXED), k=1)
    b = SOLVERS["cpsat"](make(MIXED), k=1)
    assert a.schedules[0].score.key == b.schedules[0].score.key


@pytest.mark.parametrize("name", list(SOLVERS))
def test_no_solver_returns_conflicts(name):
    result = SOLVERS[name](make(MIXED), k=5, budget=1500, seed=3, time_limit=20)
    assert result.schedules and all(s.score.conflicts == 0 for s in result.schedules)
    assert len(result.schedules) <= 5
    assert len({s.x for s in result.schedules}) == len(result.schedules)


@pytest.mark.parametrize("name", [m for m in METAHEURISTICS if m != "nsga2_legacy"])
def test_metaheuristics_usually_reach_optimum(name):
    ev = make(MIXED)
    best = min(s.scalar for _, s in brute(ev) if s.conflicts == 0)
    hits = sum(SOLVERS[name](make(MIXED), budget=2000, seed=seed).schedules[0].score.scalar == best
               for seed in range(5))
    assert hits >= 4


def test_pinned_course_keeps_its_class():
    result = SOLVERS["bnb"](make(MIXED, pinned={AUTOMAT: "2"}), k=5)
    ev = make(MIXED, pinned={AUTOMAT: "2"})
    assert ev.problem.sizes[0] == 1
    assert all(s.x[0] == 0 for s in result.schedules)


def test_unsatisfiable_must_still_returns_best_effort():
    # Không lớp Java nào vào thứ 7 (trừ lớp không lịch) → bắt buộc học thứ 7 không thoả được
    constraints = [{"prefer": {"day": "thứ 7"}, "scope": {"course": "Lập trình Java"}, "level": "must"}]
    for name in EXACT:
        result = SOLVERS[name](make(constraints), k=3)
        assert result.schedules and result.schedules[0].score.hard == 0   # lớp không lịch nằm ngoài S_c
    constraints = [{"prefer": {"day": "thứ 7"}, "scope": {"course": "Mạng máy tính"}, "level": "must"}]
    for name in EXACT:
        result = SOLVERS[name](make(constraints), k=3)
        assert result.schedules[0].score.hard == 1
