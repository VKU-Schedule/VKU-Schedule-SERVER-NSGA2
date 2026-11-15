"""Mọi ví dụ JSON trong llm-guide.md phải hợp lệ với schema v2 (không ràng buộc nào vào unsupported).

Module LLM chỉ ghi `review.phrase`; test mô phỏng bước gateway điền `aspect` / `sentiment` từ SA
(design.md mục 17.1) trước khi chuẩn hoá.
"""
import copy
import json
import re
from pathlib import Path

import pytest

from app.scheduling.normalize import normalize_document
from conftest import CANDIDATES, REVIEW_STATS, SELECTED_COURSES

GUIDE = Path(__file__).resolve().parents[2] / "docs" / "specs" / "json_v2" / "llm-guide.md"
BLOCKS = [json.loads(block) for block in re.findall(r"```json\n(.*?)\n```", GUIDE.read_text(encoding="utf-8"), re.DOTALL)]


def test_guide_has_examples():
    assert len(BLOCKS) >= 7




def gateway(raw):
    """Điền aspect / sentiment như SA sẽ trả; LLM không ghi hai field này."""
    raw = copy.deepcopy(raw)
    for constraint in raw["constraints"]:
        for kind in ("prefer", "avoid"):
            review = constraint.get(kind, {}).get("review")
            if review is not None:
                assert set(review) == {"phrase"}, "LLM chỉ ghi phrase"
                review.update(aspect="noi_chung", sentiment="positive")
    return raw


@pytest.mark.parametrize("raw", BLOCKS)
def test_guide_example_is_valid(raw):
    result = normalize_document(gateway(raw), SELECTED_COURSES, CANDIDATES, REVIEW_STATS)
    assert [item.reason for item in result.unsupported if item.index is not None] == []
    assert len(result.constraints) == len(raw["constraints"])
