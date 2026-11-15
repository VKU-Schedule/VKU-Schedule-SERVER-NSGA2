"""Hàm chấm chung (Phần B, task B5): số liệu lấy từ ví dụ trong json_v2/design.md mục 6, 13, 17."""
import pytest

from app.scheduling.constraints import Evaluator, limit_violation, relation_violation
from app.scheduling.model import build_problem, class_view
from app.scheduling.normalize import normalize_document
from app.scheduling.topk import select_diverse
from conftest import AUTOMAT, CANDIDATES, CTDL, JAVA, REVIEW_STATS, TACN2, _cls, design_example


def evaluator(constraints, candidates=None, review_stats=None, pinned=None):
    candidates = candidates or CANDIDATES
    doc = normalize_document({"constraints": constraints}, list(candidates), candidates, review_stats)
    assert not doc.unsupported, doc.unsupported
    return Evaluator(build_problem(candidates, pinned), doc)


def pick(ev, **by_course_index):
    """x theo class_index của từng môn; môn không nêu lấy lớp đầu tiên."""
    x = []
    for course, opts in zip(ev.problem.courses, ev.problem.options):
        wanted = by_course_index.get(course)
        x.append(0 if wanted is None else next(i for i, v in enumerate(opts) if v.class_index == wanted))
    return x


def only(*courses):
    return {course: CANDIDATES[course] for course in courses}


# --- prefer / avoid (6.2) -----------------------------------------------------------

def test_e1_avoid_weekend():
    ev = evaluator(design_example("E1")["constraints"], only(TACN2))
    assert ev.evaluate(pick(ev, **{TACN2: "15"})).soft == 3   # thứ 7, trọng số 3
    assert ev.evaluate(pick(ev, **{TACN2: "13"})).soft == 0


def test_e8_morning_other_day_beats_afternoon():
    ev = evaluator(design_example("E8")["constraints"], only(CTDL))
    assert ev.evaluate(pick(ev, **{CTDL: "2"})).soft == 0     # sáng thứ 2
    assert ev.evaluate(pick(ev, **{CTDL: "1"})).soft == 3     # sáng thứ 6
    assert ev.evaluate(pick(ev, **{CTDL: "3"})).soft == 5     # chiều thứ 4: 3 + 2


def test_e10_weight_is_max_of_attributes():
    ev = evaluator(design_example("E10")["constraints"], only(JAVA))
    assert ev.evaluate(pick(ev, **{JAVA: "2"})).soft == 4


def test_unknown_area_is_out_of_scope():
    # E5: lớp CTDL nhóm 3 "Chưa xếp phòng" không bị phạt
    ev = evaluator(design_example("E5")["constraints"], only(CTDL))
    assert ev.evaluate(pick(ev, **{CTDL: "3"})).soft == 0
    assert ev.evaluate(pick(ev, **{CTDL: "1"})).soft == 1


def test_unscheduled_class_is_out_of_time_scope():
    ev = evaluator([{"avoid": {"day": "thứ 6"}}], only(JAVA))
    assert ev.evaluate(pick(ev, **{JAVA: "3"})).soft == 0     # lớp "Thứ _"
    assert ev.evaluate(pick(ev, **{JAVA: "1"})).soft == 3


def test_avoid_periods_uses_touch_rule():
    # E13: lớp [1, 2, 3] bị phạt dù chỉ giao một phần với [1, 2]
    ev = evaluator(design_example("E13")["constraints"], only(JAVA))
    assert ev.evaluate(pick(ev, **{JAVA: "1"})).soft == 2


def test_prefer_session_requires_containment():
    candidates = {"X": [_cls("X", "1", "ThS.A B", "Thứ Hai", [4, 5, 6])]}
    ev = evaluator([{"prefer": {"session": "sáng"}}], candidates)
    assert ev.evaluate([0]).soft == 2


def test_e11_start_time_must_counts_hard():
    ev = evaluator(design_example("E11")["constraints"], only(AUTOMAT))
    assert ev.evaluate(pick(ev, **{AUTOMAT: "2"})).hard == 1   # tiết 3 = 9:30
    assert ev.evaluate(pick(ev, **{AUTOMAT: "1"})).hard == 0   # tiết 8
    assert ev.evaluate(pick(ev, **{AUTOMAT: "2"})).soft == 0


def test_e15_end_time():
    candidates = {"X": [_cls("X", "1", "ThS.A B", "Thứ Hai", [7, 8]), _cls("X", "2", "ThS.A B", "Thứ Hai", [8, 9])]}
    ev = evaluator(design_example("E15")["constraints"], candidates)
    assert ev.evaluate([0]).soft == 0 and ev.evaluate([1]).soft == 3


def test_e31_exception_more_specific_wins():
    candidates = {"X": [_cls("X", "1", "ThS.A B", "Thứ Hai", [6, 7]),
                        _cls("X", "2", "ThS.A B", "Thứ Hai", [1, 2]),
                        _cls("X", "3", "ThS.A B", "Thứ Ba", [6, 7])]}
    ev = evaluator(design_example("E31")["constraints"], candidates)
    assert ev.evaluate([0]).soft == 0   # chiều thứ 2: chỉ ràng buộc cụ thể áp dụng
    assert ev.evaluate([1]).soft == 3   # sáng thứ 2: vi phạm ràng buộc cụ thể (trọng số max(2, 3))
    assert ev.evaluate([2]).soft == 2   # chiều thứ 3: vi phạm ràng buộc chung


def test_teacher_preference_and_group():
    ev = evaluator(design_example("E18")["constraints"], only(AUTOMAT))
    assert ev.evaluate(pick(ev, **{AUTOMAT: "2"})).soft == 0   # Mai Nga
    assert ev.evaluate(pick(ev, **{AUTOMAT: "1"})).soft == 8   # Sơn: không phải Mai Nga + là Sơn
    assert ev.evaluate(pick(ev, **{AUTOMAT: "3"})).soft == 4


# --- limit (6.3, E24–E27) ----------------------------------------------------------

def _views(*specs):
    return [class_view(f"M{i}", _cls(f"M{i}", "1", "ThS.A B", day, periods)) for i, (day, periods) in enumerate(specs)]


def test_subjects_per_day_is_squared():
    three = _views(("Thứ Hai", [1, 2]), ("Thứ Hai", [3, 4]), ("Thứ Hai", [6, 7]), ("Thứ Tư", [1, 2]))
    assert limit_violation("subjects_per_day", None, 2, three) == 1
    four = _views(("Thứ Hai", [1, 2]), ("Thứ Hai", [3, 4]), ("Thứ Hai", [6, 7]), ("Thứ Hai", [8, 9]))
    assert limit_violation("subjects_per_day", None, 2, four) == 4


def test_spread_prefers_balanced_days():
    # 9 môn trên 6 ngày: 2-2-2-1-1-1 → 3, 4-1-1-1-1-1 → 9 (design.md mục 5)
    days = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy"]
    balanced = _views(*[(days[i % 6], [1 + 3 * (i // 6), 2 + 3 * (i // 6)]) for i in range(9)])
    skewed = _views(*([("Thứ Hai", [1 + 2 * i, 2 + 2 * i]) for i in range(4)] + [(d, [1, 2]) for d in days[1:]]))
    assert limit_violation("subjects_per_day", None, 1, balanced) == 3
    assert limit_violation("subjects_per_day", None, 1, skewed) == 9


def test_e24_gap_and_e25_consecutive():
    back_to_back = _views(("Thứ Hai", [1, 2]), ("Thứ Hai", [3, 4]))
    assert limit_violation("gap_periods", 1, None, back_to_back) == 1
    block = _views(("Thứ Hai", [1, 2, 3]), ("Thứ Hai", [4, 5]))
    assert limit_violation("consecutive_periods", None, 4, block) == 1


def test_periods_per_day_and_study_days():
    views = _views(("Thứ Hai", [1, 2, 3, 4]), ("Thứ Hai", [6, 7, 8]), ("Thứ Ba", [1, 2]))
    assert limit_violation("periods_per_day", None, 6, views) == 1
    assert limit_violation("study_days", None, 1, views) == 1
    assert limit_violation("study_days", 3, None, views) == 1


def test_e26_study_days_high_weight():
    ev = evaluator(design_example("E26")["constraints"], only(AUTOMAT, CTDL, JAVA, TACN2))
    x = pick(ev, **{AUTOMAT: "1", CTDL: "2", JAVA: "2", TACN2: "15"})   # T6, T2, T3, T7
    assert ev.evaluate(x).soft == 4   # (4 − 3) × 2 × 2


def test_limit_scope_by_day():
    ev = evaluator(design_example("E22")["constraints"], only(AUTOMAT, CTDL, TACN2))
    x = pick(ev, **{AUTOMAT: "3", CTDL: "2", TACN2: "13"})   # cả 3 lớp vào thứ 2 (trùng lịch, chỉ để đếm)
    score = ev.evaluate(x)
    assert score.hard == 1 and score.conflicts > 0


# --- relation (17.2) -----------------------------------------------------------------

def test_relation_semantics():
    a, b, c = _views(("Thứ Hai", [1, 2]), ("Thứ Hai", [3, 4]), ("Thứ Tư", [1, 2]))
    assert relation_violation("same_day", [a, b]) == 0
    assert relation_violation("same_day", [a, b, c]) == 1
    assert relation_violation("different_day", [a, b, c]) == 1
    assert relation_violation("before", [a, b]) == 0
    assert relation_violation("before", [b, a]) == 1
    assert relation_violation("before", [a, c]) == 1
    unscheduled = class_view("Z", _cls("Z", "1", ".", "Thứ _", []))
    assert relation_violation("same_day", [a, unscheduled]) == 0


def test_relation_weight_in_evaluator():
    ev = evaluator(design_example("E36")["constraints"], only(AUTOMAT, CTDL))
    assert ev.evaluate(pick(ev, **{AUTOMAT: "1", CTDL: "1"})).soft == 0   # cùng thứ 6
    assert ev.evaluate(pick(ev, **{AUTOMAT: "2", CTDL: "1"})).soft == 3


# --- review (17.1) -------------------------------------------------------------------

def test_review_resolves_to_best_lecturer():
    constraint = {"prefer": {"review": {"phrase": "giảng viên dạy dễ hiểu", "aspect": "ky_nang_giang_day",
                                        "sentiment": "positive"}}, "scope": {"course": "Automat"}}
    ev = evaluator([constraint], only(AUTOMAT), REVIEW_STATS)
    # Mai Nga: (12 − 1)/(15 + 5) = 0,55 > Sơn: 3/8 = 0,375
    assert ev.evaluate(pick(ev, **{AUTOMAT: "2"})).soft == 0
    assert ev.evaluate(pick(ev, **{AUTOMAT: "1"})).soft == 4
    assert [v.constraint_id for v in ev.explain(pick(ev, **{AUTOMAT: "1"}))] == [0]


def test_avoid_negative_review():
    constraint = {"avoid": {"review": {"phrase": "giảng viên chấm điểm khắt khe", "aspect": "cham_diem",
                                       "sentiment": "negative"}}}
    ev = evaluator([constraint], only(AUTOMAT), REVIEW_STATS)
    assert ev.evaluate(pick(ev, **{AUTOMAT: "3"})).soft == 4   # Nguyễn Đức Hiển
    assert ev.evaluate(pick(ev, **{AUTOMAT: "2"})).soft == 0


# --- trùng lịch, ghim, top-k ---------------------------------------------------------

def test_conflicts_and_objectives():
    ev = evaluator([{"avoid": {"day": "thứ 2"}}, {"prefer": {"area": "V"}}, {"limit": "study_days", "max": 1}],
                   only(CTDL, AUTOMAT))
    x = pick(ev, **{CTDL: "2", AUTOMAT: "3"})   # cả hai thứ 2 tiết 1–2
    score = ev.evaluate(x)
    assert score.conflicts == 1
    assert score.objectives == (6, 2, 0)
    assert score.soft == sum(score.objectives)


def test_build_problem_dedupes_and_pins():
    dup = _cls("X", "1", "ThS.A B", "Thứ Hai", [1, 2])
    problem = build_problem({"X": [dup, dup, _cls("X", "2", "ThS.A B", "Thứ Ba", [1, 2])]}, pinned={"X": "2"})
    assert problem.sizes == [1] and problem.options[0][0].class_index == "2"
    assert build_problem({"X": [dup, dup]}).sizes == [1]
    with pytest.raises(ValueError):
        build_problem({"X": [dup]}, pinned={"X": "9"})


def test_select_diverse_respects_distance():
    from app.scheduling.constraints import Score
    s = lambda p: Score(0, 0, p, (p, 0, 0))
    pool = [((0, 0, 0), s(0)), ((0, 0, 1), s(1)), ((0, 1, 1), s(2)), ((1, 1, 1), s(3)), ((1, 1, 0), s(0))]
    assert [x for x, _ in select_diverse(pool, 3, 2)] == [(0, 0, 0), (1, 1, 0), (0, 1, 1)]
    # không đủ lịch khác 2 môn thì nới về 1
    assert [x for x, _ in select_diverse(pool, 5, 2)] == [(0, 0, 0), (1, 1, 0), (0, 0, 1), (0, 1, 1), (1, 1, 1)]
