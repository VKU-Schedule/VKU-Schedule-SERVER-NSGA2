"""Validation của tài liệu ưu tiên v2: quy tắc V1–V11 (design.md mục 8)."""
import pytest

from app.scheduling.schema import DocumentError, filter_items, parse_document


def parse_one(constraint):
    """Parse một tài liệu chỉ có một ràng buộc."""
    return parse_document({"constraints": [constraint]})


def assert_valid(constraint):
    doc = parse_one(constraint)
    assert doc.unsupported == [], doc.unsupported[0].reason
    assert len(doc.constraints) == 1
    return doc.constraints[0]


def assert_unsupported(constraint, reason_part):
    doc = parse_one(constraint)
    assert doc.constraints == []
    assert len(doc.unsupported) == 1
    item = doc.unsupported[0]
    assert item.index == 0
    assert item.source == constraint
    assert reason_part in item.reason, item.reason
    return item


# --- V1: đúng một trong prefer / avoid / limit ------------------------------

@pytest.mark.parametrize("constraint, kind", [
    ({"prefer": {"day": "thứ 2"}}, "prefer"),
    ({"avoid": {"day": "thứ 7"}}, "avoid"),
    ({"limit": "study_days", "max": 3}, "limit"),
])
def test_v1_valid(constraint, kind):
    assert assert_valid(constraint).kind == kind


@pytest.mark.parametrize("constraint", [
    {"scope": {"day": "thứ 2"}},
    {"prefer": {"day": "thứ 2"}, "avoid": {"day": "thứ 3"}},
    {"prefer": {"day": "thứ 2"}, "limit": "study_days", "max": 3},
])
def test_v1_invalid(constraint):
    assert_unsupported(constraint, "Cần đúng một trong prefer, avoid, limit")


# --- V2: limit ----------------------------------------------------------------

@pytest.mark.parametrize("constraint", [
    {"limit": "subjects_per_day", "max": 2},
    {"limit": "subjects_per_day", "min": 1, "max": 1},
    {"limit": "gap_periods", "min": 0},
    {"limit": "consecutive_periods", "max": 4},
])
def test_v2_valid(constraint):
    assert_valid(constraint)


@pytest.mark.parametrize("constraint, reason", [
    ({"limit": "area_switch", "max": 0}, "không có trong từ vựng"),
    ({"limit": "study_days"}, "cần ít nhất một trong min, max"),
    ({"limit": "study_days", "max": -1}, "số nguyên ≥ 0"),
    ({"limit": "study_days", "max": 2.5}, "số nguyên ≥ 0"),
    ({"limit": "study_days", "max": True}, "số nguyên ≥ 0"),
    ({"limit": "study_days", "min": 4, "max": 3}, "lớn hơn max"),
    ({"limit": "consecutive_periods", "min": 2}, "không dùng cận 'min'"),
])
def test_v2_invalid(constraint, reason):
    assert_unsupported(constraint, reason)


# --- V3: min / max chỉ đi với limit -----------------------------------------

def test_v3_valid():
    assert_valid({"limit": "periods_per_day", "max": 6})


def test_v3_invalid():
    assert_unsupported({"prefer": {"day": "thứ 2"}, "max": 2}, "chỉ đi với 'limit'")


# --- V4: bộ lọc không rỗng, key thuộc từ vựng --------------------------------

def test_v4_valid():
    c = assert_valid({"prefer": {"teacher": "Mai Nga"}, "scope": {"course": "Automat và ngôn ngữ hình thức"}})
    assert filter_items(c.constraint.scope) == [("course", "Automat và ngôn ngữ hình thức")]


@pytest.mark.parametrize("constraint, reason", [
    ({"prefer": {}}, "không được rỗng"),
    ({"avoid": {"day": "thứ 2"}, "scope": {}}, "không được rỗng"),
    ({"prefer": {"weather": "nắng"}}, "Thuộc tính 'weather' không có trong từ vựng"),
    ({"limit": "study_days", "max": 3, "scope": {"weather": "nắng"}}, "'weather'"),
    ({"prefer": "thứ 2"}, "phải là object"),
])
def test_v4_invalid(constraint, reason):
    assert_unsupported(constraint, reason)


def test_v4_reason_matches_design_example():
    doc = parse_document({"constraints": [
        {"avoid": {"day": "thứ 7"}},
        {"avoid": {"day": "thứ 6"}},
        {"avoid": {"day": "thứ 5"}},
        {"prefer": {"weather": "nắng"}},
    ]})
    assert [item.to_dict() for item in doc.unsupported] == [
        {"index": 3, "source": {"prefer": {"weather": "nắng"}}, "reason": "Thuộc tính 'weather' không có trong từ vựng"},
    ]


# --- V5: khoảng ----------------------------------------------------------------

@pytest.mark.parametrize("constraint", [
    {"prefer": {"start_period": {"min": 3}}},
    {"avoid": {"periods": {"min": 1, "max": 2}}},
    {"prefer": {"start_time": {"min": "10:00"}}},
    {"prefer": {"end_time": {"max": "16:00"}}},
    {"avoid": {"duration": {"min": 4}}},
])
def test_v5_valid(constraint):
    assert_valid(constraint)


@pytest.mark.parametrize("constraint, reason", [
    ({"prefer": {"day": {"min": 2}}}, "không dùng được dạng khoảng"),
    ({"prefer": {"start_period": {}}}, "cần ít nhất một trong min, max"),
    ({"prefer": {"start_period": {"min": None, "max": None}}}, "cần ít nhất một trong min, max"),
    ({"prefer": {"periods": {"min": 5, "max": 2}}}, "lớn hơn max"),
    ({"prefer": {"duration": {"min": 2, "step": 1}}}, "chỉ có key min, max"),
])
def test_v5_invalid(constraint, reason):
    assert_unsupported(constraint, reason)


# --- V6: kiểu giá trị ----------------------------------------------------------

@pytest.mark.parametrize("constraint", [
    {"prefer": {"class_group": [13, 14]}},
    {"prefer": {"class_group": "nhóm 2"}},
    {"prefer": {"periods": [1, 2]}},
    {"prefer": {"periods": "1-3"}},
    {"prefer": {"start_time": 10}},
    {"prefer": {"day": ["thứ 2", "thứ 4"]}},
    {"prefer": {"session": ["sáng sớm", "chiều muộn"]}},
])
def test_v6_valid(constraint):
    assert_valid(constraint)


@pytest.mark.parametrize("constraint, reason", [
    ({"prefer": {"day": 2}}, "Giá trị của 'day' trong 'prefer' sai kiểu"),
    ({"prefer": {"teacher": ["Sơn", 3]}}, "Giá trị của 'teacher' trong 'prefer' sai kiểu"),
    ({"prefer": {"start_period": "3"}}, "Giá trị của 'start_period' trong 'prefer' sai kiểu"),
    ({"prefer": {"periods": {"min": "a"}}}, "Giá trị của 'periods' trong 'prefer' sai kiểu"),
    ({"prefer": {"class_group": True}}, "Giá trị của 'class_group' trong 'prefer' sai kiểu"),
    ({"avoid": {"day": [["thứ 2"]]}}, "Giá trị của 'day' trong 'avoid' sai kiểu"),
    ({"avoid": {"day": []}}, "không được rỗng"),
])
def test_v6_invalid(constraint, reason):
    assert_unsupported(constraint, reason)


# --- V7: level -----------------------------------------------------------------

@pytest.mark.parametrize("level", ["must", "high", "normal"])
def test_v7_valid(level):
    assert assert_valid({"avoid": {"day": "thứ 7"}, "level": level}).constraint.level == level


def test_v7_default_is_normal():
    assert assert_valid({"avoid": {"day": "thứ 7"}}).constraint.level == "normal"
    assert assert_valid({"avoid": {"day": "thứ 7"}, "level": None}).constraint.level == "normal"


def test_v7_invalid():
    assert_unsupported({"avoid": {"day": "thứ 7"}, "level": "low"}, "'level' phải là một trong")


# --- V8: key lạ → bỏ qua, kèm warning ----------------------------------------

def test_v8_valid_has_no_warning():
    doc = parse_one({"avoid": {"day": "thứ 7"}})
    assert doc.warnings == []


def test_v8_unknown_constraint_key():
    doc = parse_one({"avoid": {"day": "thứ 7"}, "reason": "đi làm thêm"})
    assert len(doc.constraints) == 1
    assert doc.constraints[0].source == {"avoid": {"day": "thứ 7"}, "reason": "đi làm thêm"}
    assert doc.warnings == ["Ràng buộc 0: bỏ qua key lạ 'reason'"]


def test_v8_unknown_document_key():
    doc = parse_document({"constraints": [], "note": "x"})
    assert doc.warnings == ["Bỏ qua key lạ 'note' ở cấp tài liệu"]


# --- V9: constraints thiếu hoặc không phải mảng → lỗi cả tài liệu -------------

def test_v9_valid_empty():
    doc = parse_document({"constraints": []})
    assert doc.constraints == [] and doc.unsupported == []


@pytest.mark.parametrize("raw", [{}, {"constraints": {}}, {"constraints": "x"}, [], "x"])
def test_v9_invalid(raw):
    with pytest.raises(DocumentError):
        parse_document(raw)


# --- V10: tài liệu v1 → chuyển qua adapter (chi tiết ở test_v1_adapter.py) ------

@pytest.mark.parametrize("raw", [{"defaults": {}}, {"periods": []}])
def test_v10_v1_document_is_converted(raw):
    doc = parse_document(raw)
    assert doc.constraints == []
    assert doc.warnings == ["Tài liệu đã được chuyển từ v1 sang v2"]


@pytest.mark.parametrize("raw", [{"defaults": []}, {"periods": {}}])
def test_v10_broken_v1_document_is_rejected(raw):
    with pytest.raises(DocumentError, match="v1"):
        parse_document(raw)


def test_v10_v2_document_is_not_v1():
    assert parse_document({"constraints": [{"prefer": {"periods": [1, 2]}}]}).warnings == []


# --- V11: phiên bản ------------------------------------------------------------

@pytest.mark.parametrize("version", ["2.0", "2", "2.1"])
def test_v11_valid(version):
    assert parse_document({"version": version, "constraints": []}).version == version


def test_v11_default_version():
    assert parse_document({"constraints": []}).version == "2.0"


@pytest.mark.parametrize("version", ["1.0", "3.0", "abc", 2])
def test_v11_invalid(version):
    with pytest.raises(DocumentError):
        parse_document({"version": version, "constraints": []})


# --- Một ràng buộc lỗi không làm hỏng các ràng buộc khác ---------------------

def test_errors_are_isolated_per_constraint():
    doc = parse_document({"constraints": [
        {"avoid": {"day": "thứ 7"}},
        {"prefer": {"weather": "nắng"}},
        "không phải object",
        {"limit": "subjects_per_day", "max": 2, "scope": {"day": ["thứ 2", "thứ 4"]}, "level": "must"},
    ]})
    assert [c.index for c in doc.constraints] == [0, 3]
    assert [item.index for item in doc.unsupported] == [1, 2]


# --- unsupported do LLM sinh ---------------------------------------------------

def test_llm_unsupported_strings_are_kept():
    doc = parse_document({"constraints": [], "unsupported": ["muốn học cùng lớp với bạn Nam"]})
    assert doc.llm_unsupported == ["muốn học cùng lớp với bạn Nam"]
    assert doc.warnings == []


def test_llm_unsupported_non_strings_are_dropped_with_warning():
    doc = parse_document({"constraints": [], "unsupported": ["a", 3, ""]})
    assert doc.llm_unsupported == ["a"]
    assert len(doc.warnings) == 2
