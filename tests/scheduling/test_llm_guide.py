"""Mọi ví dụ JSON trong llm-guide.md phải hợp lệ với schema v2 (không ràng buộc nào vào unsupported)."""
import json
import re
from pathlib import Path

import pytest

from app.scheduling.normalize import normalize_document
from conftest import CANDIDATES, SELECTED_COURSES

GUIDE = Path(__file__).resolve().parents[2] / "docs" / "specs" / "json_v2" / "llm-guide.md"
BLOCKS = [json.loads(block) for block in re.findall(r"```json\n(.*?)\n```", GUIDE.read_text(encoding="utf-8"), re.DOTALL)]


def test_guide_has_examples():
    assert len(BLOCKS) >= 7


@pytest.mark.parametrize("raw", BLOCKS)
def test_guide_example_is_valid(raw):
    result = normalize_document(raw, SELECTED_COURSES, CANDIDATES)
    assert [item.reason for item in result.unsupported if item.index is not None] == []
    assert len(result.constraints) == len(raw["constraints"])
