"""Golden tests (task T8, T16): mọi ví dụ E1–E40 và tài liệu 12.2 của design.md.

examples.json sinh bằng `python tests/scheduling/build_examples.py`.
"""
import pytest

from app.scheduling.normalize import normalize_document
from conftest import CANDIDATES, REVIEW_STATS, SELECTED_COURSES, design_examples, load_examples

EXAMPLES = load_examples()
BY_ID = {example["id"]: example for example in EXAMPLES}


def test_examples_cover_design_doc():
    expected_ids = ["12.2"] + [f"E{i}" for i in range(1, 41)]
    assert [example["id"] for example in EXAMPLES] == expected_ids


def test_inputs_match_design_doc():
    """examples.json phải được sinh lại khi ví dụ trong design.md thay đổi."""
    design = {example_id: raw for example_id, _, raw in design_examples()}
    for example in EXAMPLES:
        assert example["input"] == design[example["id"]], f"{example['id']}: chạy lại build_examples.py"


@pytest.mark.parametrize("example", EXAMPLES, ids=[example["id"] for example in EXAMPLES])
def test_example_normalizes_to_expected(example):
    result = normalize_document(example["input"], SELECTED_COURSES, CANDIDATES, REVIEW_STATS)
    assert result.to_dict() == example["expected"]


@pytest.mark.parametrize("example_id", [f"E{i}" for i in range(1, 10)])
def test_v1_unrepresentable_sentences_are_fully_supported(example_id):
    """10 mẫu câu v1 không biểu diễn được (E1–E9) đều chuẩn hoá hết, không có gì vào unsupported."""
    expected = BY_ID[example_id]["expected"]
    assert expected["unsupported"] == []
    assert len(expected["constraints"]) == len(BY_ID[example_id]["input"]["constraints"])


def constraint(example_id, index=0):
    return BY_ID[example_id]["expected"]["constraints"][index]


# Ghi chú trong design.md mục 13, kiểm tra trực tiếp để snapshot không trôi khỏi spec
@pytest.mark.parametrize("example_id, index, key, value", [
    ("E1", 0, "condition", {"day": ["CN", "T7"]}),
    ("E1", 0, "weight", 3),
    ("E2", 0, "weight", 3),
    ("E8", 0, "weight", 3),
    ("E8", 1, "weight", 2),
    ("E10", 0, "weight", 4),
    ("E11", 0, "condition", {"start_time": [[600, 1439]]}),
    ("E11", 0, "level", "must"),
    ("E13", 0, "condition", {"periods": [1, 2]}),
    ("E15", 0, "condition", {"end_time": [[0, 960]]}),
    ("E16", 0, "condition", {"session": [8, 9, 10]}),
    ("E18", 0, "condition", {"teacher": ["ThS.Dương Thị Mai Nga"]}),
    ("E18", 1, "condition", {"teacher": ["ThS.Trần Đình Sơn"]}),
    ("E21", 0, "condition", {"area": ["V"], "room": ["A201"]}),
    ("E26", 0, "weight", 4),
    ("E31", 0, "exclude", [{"day": ["T2"]}]),
    ("E33", 0, "condition", {"review": {"phrase": "giảng viên dạy dễ hiểu", "aspect": "ky_nang_giang_day", "sentiment": "positive"}}),
    ("E33", 0, "weight", 4),
    ("E34", 0, "kind", "avoid"),
    ("E36", 0, "relation", "same_day"),
    ("E36", 0, "weight", 3),
    ("E37", 0, "level", "must"),
    ("E38", 0, "courses", ["Cấu trúc dữ liệu và giải thuật", "Lập trình Java"]),
    ("E39", 3, "weight", 8),
    ("E39", 3, "kind", "prefer"),
])
def test_design_notes(example_id, index, key, value):
    assert constraint(example_id, index)[key] == value


@pytest.mark.parametrize("example_id, text", [
    ("E28", "muốn tổng tín chỉ không quá 18"),
    ("E38", "cho em học cùng lớp với bạn Hương"),
    ("E32", "muốn học cùng lớp với bạn Nam"),
])
def test_llm_unsupported(example_id, text):
    assert BY_ID[example_id]["expected"]["unsupported"] == [
        {"index": None, "source": text, "reason": "LLM không ánh xạ được"}
    ]


def test_e35_room_aspect_is_unsupported():
    expected = BY_ID["E35"]["expected"]
    assert expected["constraints"] == []
    assert "dữ liệu review không có phòng" in expected["unsupported"][0]["reason"]
