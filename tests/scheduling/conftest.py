"""Bộ lớp ứng viên mẫu cho tests của app/scheduling.

Dựa trên `app/constant/constant_input_test.py`, bổ sung:
- các môn và giảng viên mà ví dụ trong design.md mục 12.2, 13 nhắc tới;
- lớp không có lịch (`Thứ _`, không có tiết);
- lớp có khu, phòng, giảng viên không xác định.
"""
import json
import re
from pathlib import Path

import pytest

from app.model.Class_Info import ClassInfo

EXAMPLES_PATH = Path(__file__).with_name("examples.json")
DESIGN_PATH = Path(__file__).resolve().parents[2] / "docs" / "specs" / "json_v2" / "design.md"


def _cls(course, index, teacher, day, periods, area="K", room="A101", language="Tiếng Việt", size=60):
    return ClassInfo(course, index, language, "IT", "", teacher, day, periods, area, room, size)


AUTOMAT = "Automat và ngôn ngữ hình thức"
BAO_MAT = "Bảo mật và an toàn hệ thống thông tin"
CTDL = "Cấu trúc dữ liệu và giải thuật"
JAVA = "Lập trình Java"
MANG = "Mạng máy tính"
CNXH = "Chủ nghĩa xã hội khoa học"
TACN2 = "Tiếng Anh chuyên ngành 2"
TANC4 = "Tiếng anh nâng cao 4"
TRIET = "Triết học Mac-Lenin"

CANDIDATES = {
    AUTOMAT: [
        _cls(AUTOMAT, "1", "ThS.Trần Đình Sơn", "Thứ Sáu", [8, 9], "K", "A213", size=80),
        _cls(AUTOMAT, "2", "ThS.Dương Thị Mai Nga", "Thứ Tư", [3, 4], "K", "A313", size=75),
        _cls(AUTOMAT, "3", "TS.Nguyễn Đức Hiển", "Thứ Hai", [1, 2], "K", "A113", size=70),
        _cls(AUTOMAT, "4", "ThS.Phan Thị Mai Lam", "Thứ Ba", [6, 7, 8], "V", "A201"),
        _cls(AUTOMAT, "5", "TS.Lê Anh Tuấn", "Thứ Năm", [1, 2, 3]),
    ],
    BAO_MAT: [
        _cls(BAO_MAT, "1", "ThS.Trần Thanh Liêm", "Thứ Sáu", [1, 2, 3, 4], "K", "B306", size=85),
        _cls(BAO_MAT, "2", "ThS.Trần Đình Sơn", "Thứ Hai", [6, 7, 8], "V", "A214"),
    ],
    CTDL: [
        _cls(CTDL, "1", "ThS.Lê Song Toàn", "Thứ Sáu", [1, 2], "K", "A101", size=90),
        _cls(CTDL, "2", "PGS.TS.Nguyễn Thanh Bình", "Thứ Hai", [1, 2], "K", "A110", size=95),
        _cls(CTDL, "3", "ThS.Lê Song Toàn", "Thứ Tư", [6, 7], "Chưa xếp phòng", "_"),
    ],
    JAVA: [
        _cls(JAVA, "1", "ThS.Trần Đình Sơn", "Thứ Sáu", [1, 2, 3]),
        _cls(JAVA, "2", "ThS.Nguyễn Văn A", "Thứ Ba", [6, 7, 8], "K", "A212", size=65),
        _cls(JAVA, "3", "Khoa.KH MT", "Thứ _", [], "(Chọn)", "_"),
    ],
    MANG: [
        _cls(MANG, "1", "ThS.Hoàng Văn Phượng", "Thứ Tư", [1, 2, 3]),
        _cls(MANG, "2", ".", "Thứ Năm", [6, 7, 8], "Khác", "_"),
    ],
    CNXH: [
        _cls(CNXH, "1", "ThS.Lê Văn Trọng", "Thứ Sáu", [6, 7]),
        _cls(CNXH, "2", "ThS.Lê Văn Trọng", "Thứ Hai", [3, 4]),
    ],
    TACN2: [
        _cls(TACN2, str(i), "ThS.Võ Thị Hồng", day, periods, language="Tiếng Anh")
        for i, day, periods in ((13, "Thứ Hai", [1, 2]), (14, "Thứ Ba", [8, 9]), (15, "Thứ Bảy", [1, 2]))
    ],
    TANC4: [
        _cls(TANC4, "2", "ThS.Nguyễn Thị Kim Tuyến", "Thứ Hai", [6, 7, 8], language="Tiếng Anh"),
        _cls(TANC4, "4", "ThS.Đặng Thị Hà", "Thứ Hai", [8, 9], language="Tiếng Anh"),
    ],
    TRIET: [
        _cls(TRIET, "2", "ThS.Trần Thị Phượng", "Thứ Tư", [1, 2, 3]),
        _cls(TRIET, "", "ThS.Ngô Văn Hải", "Thứ Tư", [6, 7]),  # thiếu nhóm lớp
    ],
}

SELECTED_COURSES = list(CANDIDATES)


_HEADING = re.compile(r"^### (E\d+|12\.2)\b\s*(?:—\s*)?(.*)$", re.MULTILINE)
_JSON_BLOCK = re.compile(r"```json\n(.*?)\n```", re.DOTALL)


def design_examples():
    """Các ví dụ E1–E32 và tài liệu 12.2 trong design.md: list (id, tiêu đề, JSON đầu vào).

    Lấy khối ```json đầu tiên sau mỗi tiêu đề `### E…` hoặc `### 12.2`.
    """
    text = DESIGN_PATH.read_text(encoding="utf-8")
    headings = list(_HEADING.finditer(text))
    examples = []
    for i, heading in enumerate(headings):
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        block = _JSON_BLOCK.search(text, heading.end(), end)
        if block:
            examples.append((heading.group(1), heading.group(2).strip(), json.loads(block.group(1))))
    return examples


def design_example(example_id):
    return next(raw for eid, _, raw in design_examples() if eid == example_id)


def load_examples():
    return json.loads(EXAMPLES_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def candidates():
    return CANDIDATES


@pytest.fixture
def selected_courses():
    return SELECTED_COURSES
