"""Sinh lại tests/scheduling/examples.json từ design.md (mục 12.2, 13).

Chạy từ gốc repo:
    python tests/scheduling/build_examples.py

Kết quả chuẩn hoá mong đợi (`expected`) là output hiện tại của `normalize_document`
trên bộ lớp mẫu trong conftest.py. Sau khi sinh lại, xem `git diff` để duyệt từng thay đổi.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.scheduling.normalize import normalize_document  # noqa: E402
from conftest import CANDIDATES, EXAMPLES_PATH, SELECTED_COURSES, design_examples  # noqa: E402


def build():
    return [
        {
            "id": example_id,
            "title": title,
            "input": raw,
            "expected": normalize_document(raw, SELECTED_COURSES, CANDIDATES).to_dict(),
        }
        for example_id, title, raw in design_examples()
    ]


if __name__ == "__main__":
    EXAMPLES_PATH.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Đã ghi {EXAMPLES_PATH}")
