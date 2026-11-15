"""Adapter v1 → v2 (task T9, design.md mục 12.1)."""
import json
from pathlib import Path

import pytest

from app.scheduling.normalize import normalize_document
from app.scheduling.schema import parse_document
from app.scheduling.v1_adapter import convert_v1
from conftest import CANDIDATES, SELECTED_COURSES, design_example

PROMPT_V1 = Path(__file__).resolve().parents[2] / "data" / "prompt.json"


def converted(raw):
    doc, warnings, unsupported = convert_v1(raw)
    assert unsupported == [], unsupported
    return doc["constraints"], warnings


def defaults(**keys):
    return converted({"defaults": keys})[0]


# --- data/prompt.json → tài liệu 12.2 ---------------------------------------------

def test_prompt_json_converts_to_doc_12_2():
    raw = json.loads(PROMPT_V1.read_text(encoding="utf-8"))
    constraints, warnings = converted(raw)
    assert constraints == design_example("12.2")["constraints"]
    assert warnings == []


def test_prompt_json_normalizes_like_doc_12_2():
    raw = json.loads(PROMPT_V1.read_text(encoding="utf-8"))
    from_v1 = normalize_document(raw, SELECTED_COURSES, CANDIDATES).to_dict()
    from_v2 = normalize_document(design_example("12.2"), SELECTED_COURSES, CANDIDATES).to_dict()
    assert from_v1["constraints"] == from_v2["constraints"]
    assert from_v1["warnings"] == ["Tài liệu đã được chuyển từ v1 sang v2"] + from_v2["warnings"]


# --- Bảng 12.1, từng dòng ----------------------------------------------------------

@pytest.mark.parametrize("keys, expected", [
    ({"subject_per_session": 1}, [{"limit": "subjects_per_session", "max": 1}]),
    ({"subject_per_day": 3}, [{"limit": "subjects_per_day", "max": 3}]),
    ({"duration_of_session": {"value": 2, "up_or_down": "down", "like": True}}, [{"prefer": {"duration": {"max": 2}}}]),
    ({"duration_of_session": {"value": 3, "up_or_down": "up", "like": False}}, [{"avoid": {"duration": {"min": 3}}}]),
    ({"duration_of_session": {"value": 3, "like": True}}, [{"prefer": {"duration": {"max": 3}}}]),  # thiếu up_or_down = down
    ({"period": {"value": [2, 3, 4], "like": True}}, [{"prefer": {"periods": {"min": 2, "max": 4}}}]),
    ({"period": {"value": [1, 2, 8], "like": False}}, [{"avoid": {"periods": [1, 2, 8]}}]),
    ({"period": {"value": [3]}}, [{"avoid": {"periods": [3]}}]),  # thiếu like = false
    ({"period_onward": {"value": 3, "like": True}}, [{"prefer": {"start_period": {"min": 3}}}]),
    ({"hour_onward": {"value": 9, "unit": "hour", "like": True}}, [{"prefer": {"start_time": {"min": "09:00"}}}]),
    ({"hour_onward": {"value": 13.5, "unit": "hour", "like": False}}, [{"avoid": {"start_time": {"min": "13:30"}}}]),
    ({"area": {"value": "K", "like": True}}, [{"prefer": {"area": "K"}}]),
    ({"area": [{"value": "V", "like": False}]}, [{"avoid": {"area": "V"}}]),
    ({"room": [{"value": "A101", "like": True}, {"value": "B2", "like": False}, {"value": "A102", "like": True}]},
     [{"prefer": {"room": ["A101", "A102"]}}, {"avoid": {"room": "B2"}}]),
    ({"class": [{"name": "Automat", "class_group": [{"value": 2, "like": False}], "teacher": []}]},
     [{"avoid": {"class_group": 2}, "scope": {"course": "Automat"}}]),
    ({"class": [{"name": "Automat", "class_group": [], "teacher": [{"name": "Sơn", "like": True}]}]},
     [{"prefer": {"teacher": "Sơn"}, "scope": {"course": "Automat"}}]),
    ({"class": [{"name": "", "class_group": [], "teacher": [{"name": "Sơn", "like": False}]}]},
     [{"avoid": {"teacher": "Sơn"}}]),
    ({"teacher": [{"name": "Phượng", "like": True}, {"name": "Trọng", "like": True}]},
     [{"prefer": {"teacher": ["Phượng", "Trọng"]}}]),
    ({"rest_interval": {"value": 1, "up_or_down": "up", "like": True}}, [{"limit": "gap_periods", "min": 1}]),
    ({"rest_interval": {"value": 1, "up_or_down": "down", "like": True}}, [{"limit": "gap_periods", "max": 1}]),
    ({"rest_interval": {"value": 2, "up_or_down": "up", "like": False}}, [{"limit": "gap_periods", "max": 1}]),
    ({"rest_interval": {"value": 1, "up_or_down": "down", "like": False}}, [{"limit": "gap_periods", "min": 2}]),
])
def test_defaults_mapping(keys, expected):
    assert defaults(**keys) == expected


@pytest.mark.parametrize("keys", [
    {"subject_per_session": None},
    {"area": []},
    {"room": []},
    {"duration_of_session": None},
    {"class": [{"name": "", "class_group": [], "teacher": []}]},
])
def test_empty_values_produce_nothing(keys):
    assert defaults(**keys) == []


def test_period_entry_scopes_by_day():
    constraints, _ = converted({"periods": [{
        "day": {"value": "Thứ 2", "like": True},
        "subject_count": {"value": 1, "like": True},
        "area": {"value": "K", "like": True},
        "class": [{"name": "Triết", "class_group": [{"value": 2, "like": True}]}],
    }]})
    assert constraints == [
        {"limit": "subjects_per_day", "min": 1, "max": 1, "scope": {"day": "thứ 2"}},
        {"prefer": {"area": "K"}, "scope": {"day": "thứ 2"}},
        {"prefer": {"class_group": 2}, "scope": {"course": "Triết", "day": "thứ 2"}},
    ]


@pytest.mark.parametrize("day", [None, {"value": "Cả tuần", "like": True}])
def test_period_entry_for_all_days_has_no_scope(day):
    constraints, _ = converted({"periods": [{"day": day, "area": {"value": "K", "like": True}}]})
    assert constraints == [{"prefer": {"area": "K"}}]


def test_period_entry_disliked_day_alone_is_avoid_day():
    constraints, _ = converted({"periods": [{"day": {"value": "Thứ 7", "like": False}, "period": None, "room": []}]})
    assert constraints == [{"avoid": {"day": "thứ 7"}}]


def test_period_entry_disliked_day_with_other_keys_keeps_v1_behaviour():
    constraints, warnings = converted({"periods": [{"day": {"value": "Thứ 7", "like": False},
                                                    "area": {"value": "K", "like": True}}]})
    assert constraints == [{"prefer": {"area": "K"}, "scope": {"day": "thứ 7"}}]
    assert len(warnings) == 1


# --- Phần không chuyển được đi vào unsupported --------------------------------------

def test_unconvertible_parts_go_to_unsupported():
    doc = parse_document({"defaults": {
        "subject_per_day": "ba",
        "rest_interval": {"value": 0, "up_or_down": "down", "like": False},
        "weather": {"value": "nắng"},
        "area": {"value": "K", "like": True},
    }})
    assert [c.source for c in doc.constraints] == [
        {"limit": "gap_periods", "min": 1},
        {"prefer": {"area": "K"}},
    ]
    assert [(item.index, item.source, item.reason) for item in doc.unsupported] == [
        (None, {"defaults.subject_per_day": "ba"}, "Không chuyển được từ v1: cần số nguyên ≥ 0"),
        (None, {"defaults.weather": {"value": "nắng"}}, "Không chuyển được từ v1: key 'weather' không có trong v1"),
    ]


def test_v1_nulls_and_empty_lists_are_ignored():
    # Cùng dạng USER_PREFERENCES trong app/constant/constant_input_test.py
    doc = parse_document({
        "defaults": {
            "subject_per_session": None, "subject_per_day": None, "duration_of_session": None,
            "period_onward": None, "hour_onward": None, "area": [],
            "room": [{"value": "A101", "like": True}], "class": [], "rest_interval": None,
        },
        "periods": [{"day": {"value": "Thứ Sáu", "like": True}, "period": None, "class": []}],
    })
    assert doc.unsupported == []
    assert [c.source for c in doc.constraints] == [{"prefer": {"room": "A101"}}]
