"""Mở rộng A2 (design.md mục 17): thuộc tính `review`, loại ràng buộc `relation`, `review_stats`."""
import pytest

from app.scheduling.normalize import normalize_document
from app.scheduling.schema import parse_document, parse_review_stats
from conftest import AUTOMAT, CANDIDATES, CTDL, JAVA, MANG, REVIEW_STATS, SELECTED_COURSES


def review(phrase="giảng viên dạy dễ hiểu", aspect="ky_nang_giang_day", sentiment="positive"):
    value = {"phrase": phrase}
    if aspect is not None:
        value["aspect"] = aspect
    if sentiment is not None:
        value["sentiment"] = sentiment
    return value


def reasons(constraints):
    return [item.reason for item in parse_document({"constraints": constraints}).unsupported]


def run(constraints, review_stats=REVIEW_STATS):
    return normalize_document({"constraints": constraints}, SELECTED_COURSES, CANDIDATES, review_stats)


# --- V12: relation --------------------------------------------------------------------

@pytest.mark.parametrize("relation", ["same_day", "different_day", "before"])
@pytest.mark.parametrize("courses", [["A", "B"], ["A", "B", "C"], ["A", "B", "C", "D"]])
def test_v12_valid(relation, courses):
    parsed = parse_document({"constraints": [{"relation": relation, "courses": courses, "level": "high"}]})
    assert [c.kind for c in parsed.constraints] == ["relation"]


@pytest.mark.parametrize("constraint, reason", [
    ({"relation": "later", "courses": ["A", "B"]}, "Quan hệ 'later' không có trong từ vựng"),
    ({"relation": "same_day"}, "cần 'courses' là list 2–4 tên môn"),
    ({"relation": "same_day", "courses": ["A"]}, "cần 'courses' là list 2–4 tên môn"),
    ({"relation": "same_day", "courses": ["A", "B", "C", "D", "E"]}, "cần 'courses' là list 2–4 tên môn"),
    ({"relation": "same_day", "courses": ["A", ""]}, "cần 'courses' là list 2–4 tên môn"),
    ({"relation": "same_day", "courses": ["A", "B"], "scope": {"day": "thứ 2"}}, "'relation' không dùng 'scope'"),
    ({"relation": "same_day", "courses": ["A", "B"], "max": 1}, "chỉ đi với 'limit'"),
    ({"prefer": {"day": "thứ 2"}, "courses": ["A", "B"]}, "'courses' chỉ đi với 'relation'"),
    ({"relation": "same_day", "courses": ["A", "B"], "prefer": {"day": "thứ 2"}}, "Cần đúng một trong"),
])
def test_v12_invalid(constraint, reason):
    assert reason in reasons([constraint])[0]


# --- V13: review ----------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["prefer", "avoid"])
def test_v13_valid(kind):
    parsed = parse_document({"constraints": [{kind: {"review": review()}, "scope": {"course": "Java"}}]})
    assert parsed.unsupported == []


@pytest.mark.parametrize("value, reason", [
    (review(aspect=None), "review chưa có aspect/sentiment"),
    (review(sentiment=None), "review chưa có aspect/sentiment"),
    (review(phrase=" "), "'review.phrase'"),
    (review(aspect="abc"), "không thuộc 11 khía cạnh"),
    (review(sentiment="mixed"), "'review.sentiment' phải là một trong"),
    ({**review(), "lecturer": "x"}, "chỉ có key phrase, aspect, sentiment"),
    ("giảng viên dạy dễ hiểu", "phải là object"),
])
def test_v13_invalid(value, reason):
    assert reason in reasons([{"prefer": {"review": value}}])[0]


def test_v4_review_must_stand_alone():
    assert "phải đứng một mình" in reasons([{"prefer": {"review": review(), "day": "thứ 2"}}])[0]


def test_v4_review_not_in_scope():
    assert "không dùng trong 'scope'" in reasons([{"prefer": {"day": "thứ 2"}, "scope": {"review": review()}}])[0]


# --- Chuẩn hoá review -----------------------------------------------------------------

def test_review_condition_and_weight():
    result = run([{"prefer": {"review": review("giảng viên  dạy dễ hiểu")}, "scope": {"course": "Automat"}}])
    (c,) = result.constraints
    assert c.to_dict()["condition"] == {
        "review": {"phrase": "giảng viên dạy dễ hiểu", "aspect": "ky_nang_giang_day", "sentiment": "positive"}
    }
    assert c.to_dict()["scope"] == {"course": [AUTOMAT]}
    assert c.weight == 4
    assert result.warnings == []


def test_review_high_weight_and_negative_target_is_kept():
    """"rất thích giảng viên khó tính": prefer giữ nguyên, sentiment mục tiêu negative (không đảo thành avoid)."""
    result = run([{"prefer": {"review": review("giảng viên khó tính", "hanh_vi", "negative")}, "level": "high"}])
    (c,) = result.constraints
    assert c.kind == "prefer"
    assert c.condition["review"].sentiment == "negative"
    assert c.weight == 8


def test_review_neutral_counts_as_positive():
    (c,) = run([{"prefer": {"review": review(sentiment="neutral")}, "scope": {"course": "Automat"}}]).constraints
    assert c.condition["review"].sentiment == "positive"


@pytest.mark.parametrize("aspect, reason", [
    ("thiet_bi_day_hoc", "dữ liệu review không có phòng"),
    ("chuong_trinh_hoc", "khía cạnh không gắn với giảng viên"),
    ("de_xuat", "khía cạnh không gắn với giảng viên"),
])
def test_review_aspect_not_about_lecturer_is_unsupported(aspect, reason):
    result = run([{"prefer": {"review": review(aspect=aspect)}}])
    assert result.constraints == []
    assert reason in result.unsupported[0].reason


def test_review_without_stats_is_unsupported():
    result = run([{"prefer": {"review": review()}}], review_stats=None)
    assert result.constraints == []
    assert "thiếu dữ liệu review" in result.unsupported[0].reason


def test_review_warns_about_courses_without_stats():
    result = run([{"prefer": {"review": review(aspect="bai_tap")}, "scope": {"course": ["Automat", "Cấu trúc dữ liệu"]}}])
    assert len(result.constraints) == 1
    assert result.warnings == [f"Ràng buộc 0: 'review': không có số liệu aspect 'bai_tap' cho môn {AUTOMAT}"]


def test_review_noi_chung_uses_every_aspect():
    result = run([{"prefer": {"review": review("giảng viên tốt", "noi_chung")}, "scope": {"course": "Java"}}])
    assert result.warnings == []


def test_same_review_prefer_and_avoid_conflict():
    result = run([{"prefer": {"review": review()}}, {"avoid": {"review": review()}}])
    assert any("mâu thuẫn" in warning for warning in result.warnings)


def test_review_more_specific_scope_excludes_general():
    result = run([
        {"prefer": {"review": review()}},
        {"avoid": {"review": review()}, "scope": {"course": "Java"}},
    ])
    general, specific = result.constraints
    assert general.exclude == [{"course": frozenset({JAVA})}]


# --- review_stats ---------------------------------------------------------------------

def test_review_stats_kept_for_algorithm():
    result = run([])
    assert [row.to_dict() for row in result.review_stats] == REVIEW_STATS


@pytest.mark.parametrize("row, reason", [
    ("x", "không phải object"),
    ({**REVIEW_STATS[0], "lecturer": ""}, "'lecturer' phải là chuỗi không rỗng"),
    ({**REVIEW_STATS[0], "aspect": "abc"}, "aspect 'abc' không thuộc 11 khía cạnh"),
    ({**REVIEW_STATS[0], "positive": -1}, "'positive' phải là số nguyên ≥ 0"),
    ({**REVIEW_STATS[0], "total": "15"}, "'total' phải là số nguyên ≥ 0"),
    ({**REVIEW_STATS[0], "positive": 10, "negative": 10, "total": 15}, "positive + negative lớn hơn total"),
])
def test_review_stats_bad_row_is_dropped(row, reason):
    rows, warnings = parse_review_stats([REVIEW_STATS[0], row])
    assert len(rows) == 1
    assert warnings == [f"Bỏ qua dòng 1 của 'review_stats': {reason}"]


def test_review_stats_not_a_list():
    rows, warnings = parse_review_stats({"x": 1})
    assert rows is None and warnings == ["Bỏ qua 'review_stats' vì không phải mảng"]


# --- Chuẩn hoá relation ---------------------------------------------------------------

def test_relation_courses_keep_order_and_weight():
    result = run([{"relation": "before", "courses": ["Java", "Automat"], "level": "high"}])
    (c,) = result.constraints
    assert c.to_dict() == {
        "id": 0, "kind": "relation", "relation": "before", "courses": [JAVA, AUTOMAT],
        "scope": {}, "exclude": [], "level": "high", "weight": 6,
        "source": {"relation": "before", "courses": ["Java", "Automat"], "level": "high"},
    }


@pytest.mark.parametrize("courses, reason", [
    (["Java", "Lập trình Java"], "nhiều tên cùng chỉ một môn (Lập trình Java)"),
    (["Automat", "Java", "Lập trình Java"], "nhiều tên cùng chỉ một môn (Lập trình Java)"),
    (["Java", "Hoá sinh"], "Môn không có trong danh sách đã chọn"),
])
def test_relation_courses_invalid(courses, reason):
    result = run([{"relation": "same_day", "courses": courses}])
    assert result.constraints == []
    assert reason in result.unsupported[0].reason


def test_relation_course_matching_several_is_unsupported():
    result = normalize_document({"constraints": [{"relation": "same_day", "courses": ["Tiếng Anh", "Java"]}]},
                                SELECTED_COURSES, CANDIDATES)
    assert "khớp nhiều môn" in result.unsupported[0].reason


def test_relation_opposite_pair_warns():
    result = run([
        {"relation": "same_day", "courses": ["Java", "Automat"]},
        {"relation": "different_day", "courses": ["Automat", "Java"]},
        {"relation": "same_day", "courses": ["Java", CTDL]},
    ])
    assert len(result.constraints) == 3
    assert result.warnings == [
        f"Ràng buộc 0 và 1 mâu thuẫn: chung các môn {JAVA}, {AUTOMAT}, một 'same_day' một 'different_day'. "
        "Cả hai vẫn được áp dụng"
    ]


def test_relation_with_more_courses_keeps_order():
    result = run([{"relation": "before", "courses": ["Cấu trúc dữ liệu", "Java", "Automat", "Mạng máy tính"]}])
    (c,) = result.constraints
    assert c.courses == (CTDL, JAVA, AUTOMAT, MANG)


def test_relation_opposite_sharing_one_pair_warns():
    result = run([
        {"relation": "different_day", "courses": ["Java", "Automat", "Mạng máy tính"]},
        {"relation": "same_day", "courses": ["Automat", "Mạng máy tính"]},
        {"relation": "same_day", "courses": ["Java", CTDL]},
    ])
    assert len(result.warnings) == 1
    assert result.warnings[0].startswith(f"Ràng buộc 0 và 1 mâu thuẫn: chung các môn {AUTOMAT}, {MANG},")


def test_relation_is_never_excluded():
    result = run([
        {"relation": "same_day", "courses": ["Java", "Automat"]},
        {"relation": "same_day", "courses": ["Java", CTDL]},
    ])
    assert all(c.exclude == [] for c in result.constraints)
