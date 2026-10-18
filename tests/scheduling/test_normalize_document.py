"""Chuẩn hoá cả tài liệu (task T7): course → scope, trọng số, quy tắc ngoại lệ, mâu thuẫn, unsupported."""
import pytest

from app.scheduling.normalize import is_more_specific, normalize_document
from conftest import AUTOMAT, CANDIDATES, JAVA, SELECTED_COURSES, design_example


def run(constraints, **doc):
    return normalize_document({"constraints": constraints, **doc}, SELECTED_COURSES, CANDIDATES)


def by_id(result):
    return {c.id: c for c in result.constraints}


# --- Quy tắc ngoại lệ (design.md mục 6.4) -----------------------------------------

def test_e31_general_rule_gets_exclusion():
    result = normalize_document(design_example("E31"), SELECTED_COURSES, CANDIDATES)
    general, specific = result.constraints
    assert general.exclude == [{"day": frozenset({"T2"})}]
    assert specific.exclude == []
    assert result.warnings == []


def test_doc_12_2_reproduces_v1_override_behaviour():
    result = normalize_document(design_example("12.2"), SELECTED_COURSES, CANDIDATES)
    assert result.unsupported == []
    c = by_id(result)
    assert len(c) == 29
    t2, t4 = {"day": frozenset({"T2"})}, {"day": frozenset({"T4"})}
    # Ràng buộc 12 (tiết 6–9, thứ 2) và 22 (tiết 1–4, thứ 4) thay ràng buộc 3 trên thứ 2, thứ 4
    assert c[3].exclude == [t2, t4]
    # Ràng buộc 16 (thích A101, thứ 2) và 25 (tránh A101, thứ 4) thay ràng buộc 7: cùng nhóm {room}
    assert c[7].exclude == [t2, t4]
    # Ràng buộc 17 và 28 thay ràng buộc 6 (khu K) trên thứ 2, thứ 4: mỗi lớp chỉ bị chấm một lần
    assert c[6].exclude == [t2, t4]
    # limit cùng chỉ số
    assert c[1].exclude == [t2, t4]
    assert c[11].exclude == [t2, t4]
    assert c[0].exclude == []
    # Giảng viên theo môn thay quy tắc chung về giảng viên
    assert c[10].exclude == [
        {"course": frozenset({AUTOMAT})},
        {"course": frozenset({"Tiếng anh nâng cao 4"}), "day": frozenset({"T2"})},
        {"course": frozenset({"Triết học Mac-Lenin"}), "day": frozenset({"T4"})},
    ]
    # Ràng buộc cụ thể nhất không bị loại trừ gì
    assert all(c[i].exclude == [] for i in range(12, 29))


def test_different_groups_do_not_exclude_each_other():
    # E8: nhóm {day, session} và nhóm {session}
    result = normalize_document(design_example("E8"), SELECTED_COURSES, CANDIDATES)
    assert [c.exclude for c in result.constraints] == [[], []]


def test_overlapping_but_not_nested_scopes_both_apply():
    result = run([
        {"prefer": {"area": "K"}, "scope": {"day": ["thứ 2", "thứ 3"]}},
        {"prefer": {"area": "V"}, "scope": {"day": ["thứ 3", "thứ 4"]}},
    ])
    assert [c.exclude for c in result.constraints] == [[], []]
    assert result.warnings == []


def test_nested_chain():
    result = run([
        {"avoid": {"session": "sáng"}},
        {"avoid": {"session": "sáng"}, "scope": {"day": ["thứ 2", "thứ 3"]}},
        {"prefer": {"session": "sáng"}, "scope": {"day": "thứ 2"}},
    ])
    c = by_id(result)
    assert c[0].exclude == [{"day": frozenset({"T2", "T3"})}, {"day": frozenset({"T2"})}]
    assert c[1].exclude == [{"day": frozenset({"T2"})}]
    assert c[2].exclude == []


@pytest.mark.parametrize("inner, outer, expected", [
    ({"day": frozenset({"T2"})}, {}, True),
    ({}, {}, False),
    ({"day": frozenset({"T2"})}, {"day": frozenset({"T2"})}, False),
    ({"day": frozenset({"T2"}), "course": frozenset({JAVA})}, {"day": frozenset({"T2", "T3"})}, True),
    ({"day": frozenset({"T2"})}, {"course": frozenset({JAVA})}, False),
    ({"start_period": ((3, 5),)}, {"start_period": ((1, 10),)}, True),
    ({"start_period": ((3, 5),)}, {"start_period": ((4, 10),)}, False),
    ({"session": frozenset({1, 2})}, {"session": frozenset({1, 2, 3, 4, 5})}, True),
])
def test_is_more_specific(inner, outer, expected):
    assert is_more_specific(inner, outer) is expected


# --- Mâu thuẫn ---------------------------------------------------------------------

def test_opposite_constraints_same_scope_and_condition_warn():
    result = run([
        {"prefer": {"day": "thứ 7"}},
        {"avoid": {"day": "Thứ Bảy"}},  # cùng giá trị sau chuẩn hoá
    ])
    assert len(result.constraints) == 2
    assert result.warnings == [
        "Ràng buộc 0 và 1 mâu thuẫn: cùng phạm vi, cùng điều kiện, một 'prefer' một 'avoid'. Cả hai vẫn được áp dụng"
    ]


def test_same_scope_different_values_is_not_a_contradiction():
    result = normalize_document(design_example("E18"), SELECTED_COURSES, CANDIDATES)
    assert result.warnings == []


# --- course chuyển sang scope ------------------------------------------------------

def test_course_in_condition_moves_to_scope():
    result = run([{"prefer": {"course": "Lập trình Java", "day": "thứ 5"}}])
    (c,) = result.constraints
    assert c.condition == {"day": frozenset({"T5"})}
    assert c.scope == {"course": frozenset({JAVA})}
    assert c.weight == 3


def test_course_in_condition_and_scope_intersect():
    result = run([{"prefer": {"course": "Java", "day": "thứ 5"}, "scope": {"course": ["Java", "Automat"]}}])
    assert result.constraints[0].scope == {"course": frozenset({JAVA})}


def test_course_only_condition_is_unsupported():
    result = run([{"prefer": {"course": "Lập trình Java"}}])
    assert result.constraints == []
    assert "chỉ có 'course'" in result.unsupported[0].reason


# --- Khớp thực thể trong ngữ cảnh ----------------------------------------------------

def test_teacher_is_matched_within_scope_course():
    # "Sơn" dạy cả Automat và Bảo mật, nhưng phạm vi là Automat nên chỉ khớp một lớp, không có warning
    result = run([{"avoid": {"teacher": "Sơn"}, "scope": {"course": "Automat"}}])
    assert result.constraints[0].condition == {"teacher": frozenset({"ThS.Trần Đình Sơn"})}
    assert result.warnings == []


def test_teacher_not_teaching_scope_course_is_unsupported():
    result = run([{"prefer": {"teacher": "Mai Nga"}, "scope": {"course": "Lập trình Java"}}])
    assert result.constraints == []
    assert result.unsupported[0].reason == "'teacher' trong 'prefer': Không giảng viên nào khớp 'Mai Nga'"


def test_unknown_course_is_unsupported():
    result = run([{"avoid": {"day": "thứ 7"}, "scope": {"course": "Kinh tế vĩ mô"}}])
    assert result.unsupported[0].reason == "'course' trong 'scope': Môn không có trong danh sách đã chọn: 'Kinh tế vĩ mô'"


def test_selected_courses_default_to_candidates():
    result = normalize_document({"constraints": [{"avoid": {"day": "thứ 7"}, "scope": {"course": "Java"}}]},
                                candidates=CANDIDATES)
    assert result.constraints[0].scope == {"course": frozenset({JAVA})}


# --- Phòng có tiền tố khu ------------------------------------------------------------

def test_room_prefix_conflicting_with_area_is_unsupported():
    result = run([{"prefer": {"room": "V.A201", "area": "K"}}])
    assert "mâu thuẫn" in result.unsupported[0].reason


def test_room_prefix_with_same_area():
    result = run([{"prefer": {"room": "V.A201", "area": ["K", "V"]}}])
    assert result.constraints[0].condition == {"area": frozenset({"V"}), "room": frozenset({"A201"})}


# --- Trọng số (design.md mục 6.5) ------------------------------------------------------

@pytest.mark.parametrize("constraint, weight", [
    ({"avoid": {"day": "thứ 7"}}, 3),
    ({"avoid": {"day": "thứ 7"}, "level": "high"}, 6),
    ({"prefer": {"area": "K"}, "scope": {"session": "chiều"}}, 2),
    ({"prefer": {"session": "sáng"}, "scope": {"day": "thứ 2"}}, 3),   # chuyển thuộc tính sang scope không đổi trọng số
    ({"prefer": {"session": "sáng", "day": "thứ 2"}}, 3),
    ({"prefer": {"area": "K"}, "scope": {"course": "Java"}}, 1),       # course không tính
    ({"limit": "study_days", "max": 3, "scope": {"day": "thứ 2"}}, 2),  # limit: trọng số của chỉ số
    ({"limit": "gap_periods", "min": 1, "level": "high"}, 2),
    ({"limit": "subjects_per_day", "max": 2, "level": "must"}, 2),
])
def test_weight(constraint, weight):
    assert run([constraint]).constraints[0].weight == weight


# --- unsupported và warnings ----------------------------------------------------------

def test_unsupported_from_validation_normalization_and_llm_are_merged():
    result = run(
        [
            {"avoid": {"day": "thứ 7"}},
            {"avoid": {"session": "trưa"}},      # chuẩn hoá lỗi
            {"prefer": {"weather": "nắng"}},     # validation lỗi
        ],
        unsupported=["muốn học cùng lớp với bạn Nam"],
    )
    assert [c.id for c in result.constraints] == [0]
    assert [(item.index, item.reason) for item in result.unsupported] == [
        (1, "'session' trong 'avoid': Buổi không xác định: 'trưa'"),
        (2, "Thuộc tính 'weather' không có trong từ vựng"),
        (None, "LLM không ánh xạ được"),
    ]
    assert result.unsupported[2].source == "muốn học cùng lớp với bạn Nam"


def test_partial_list_keeps_constraint_with_prefixed_warning():
    result = run([{"avoid": {"day": ["thứ 7", "thứ 9"]}}])
    assert result.constraints[0].condition == {"day": frozenset({"T7"})}
    assert result.warnings == ["Ràng buộc 0: 'day' trong 'avoid': Bỏ một giá trị của 'day': Thứ không xác định: 'thứ 9'"]


def test_to_dict_is_json_ready():
    import json
    result = normalize_document(design_example("12.2"), SELECTED_COURSES, CANDIDATES)
    data = result.to_dict()
    json.dumps(data, ensure_ascii=False)
    assert data["constraints"][3]["condition"] == {"periods": [2, 3, 4, 5, 6, 7]}
    assert data["constraints"][3]["exclude"] == [{"day": ["T2"]}, {"day": ["T4"]}]
    assert data["constraints"][4]["condition"] == {"start_period": [[3, 10]]}
