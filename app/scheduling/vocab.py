"""Từ vựng của JSON v2: nguồn duy nhất cho các hằng số của schema và chuẩn hoá.

Mỗi bảng ghi mục tương ứng trong docs/specs/json_v2/design.md. Muốn thêm thuộc tính
hoặc chỉ số mới, làm theo design.md mục 16.

Các bảng alias lưu key ở dạng "gập" (bỏ dấu, chữ thường, bỏ khoảng trắng), giống
`normalize_day` của v1. Hàm gập nằm ở `normalize.py`.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Dict, FrozenSet, Optional, Tuple

# ---------------------------------------------------------------------------
# Phiên bản (design.md D16, V11)
# ---------------------------------------------------------------------------

DEFAULT_VERSION = "2.0"
SUPPORTED_MAJOR_VERSION = 2

# ---------------------------------------------------------------------------
# Loại ràng buộc và mức độ (design.md mục 3.2, 6.5)
# ---------------------------------------------------------------------------

KINDS = ("prefer", "avoid", "limit")
FILTER_KINDS = ("prefer", "avoid")

LEVELS = ("must", "high", "normal")
DEFAULT_LEVEL = "normal"
HIGH_MULTIPLIER = 2

# ---------------------------------------------------------------------------
# Thuộc tính lọc (design.md mục 4, 6.5, 9)
# ---------------------------------------------------------------------------


class AttrKind(str, Enum):
    """Dạng của thuộc tính sau chuẩn hoá (design.md mục 9)."""

    VALUES = "values"    # tập giá trị chuẩn
    PERIODS = "periods"  # tập tiết
    RANGE = "range"      # khoảng đóng [a, b]


class ValueType(str, Enum):
    """Kiểu giá trị bề mặt mà LLM được phép sinh (V6)."""

    TEXT = "text"        # chuỗi
    INT = "int"          # số nguyên
    INT_OR_TEXT = "int_or_text"  # số nguyên hoặc chuỗi có số: "nhóm 2", "1-3", "10h"


@dataclass(frozen=True)
class AttributeSpec:
    name: str
    kind: AttrKind
    value_type: ValueType
    ordered: bool                 # cho phép dạng khoảng {min, max} (V5)
    weight: Optional[int]         # trọng số cơ sở; None = không tính vào trọng số (course)
    scope_only: bool = False      # chỉ có nghĩa trong scope; ở prefer/avoid sẽ được chuyển sang scope


ATTRIBUTES: Dict[str, AttributeSpec] = {
    spec.name: spec
    for spec in (
        AttributeSpec("course", AttrKind.VALUES, ValueType.TEXT, False, None, scope_only=True),
        AttributeSpec("class_group", AttrKind.VALUES, ValueType.INT_OR_TEXT, False, 4),
        AttributeSpec("teacher", AttrKind.VALUES, ValueType.TEXT, False, 4),
        AttributeSpec("language", AttrKind.VALUES, ValueType.TEXT, False, 2),
        AttributeSpec("day", AttrKind.VALUES, ValueType.TEXT, False, 3),
        AttributeSpec("session", AttrKind.PERIODS, ValueType.TEXT, False, 2),
        AttributeSpec("periods", AttrKind.PERIODS, ValueType.INT_OR_TEXT, True, 2),
        AttributeSpec("start_period", AttrKind.RANGE, ValueType.INT, True, 3),
        AttributeSpec("end_period", AttrKind.RANGE, ValueType.INT, True, 3),
        AttributeSpec("start_time", AttrKind.RANGE, ValueType.INT_OR_TEXT, True, 3),
        AttributeSpec("end_time", AttrKind.RANGE, ValueType.INT_OR_TEXT, True, 3),
        AttributeSpec("duration", AttrKind.RANGE, ValueType.INT, True, 1),
        AttributeSpec("area", AttrKind.VALUES, ValueType.TEXT, False, 1),
        AttributeSpec("room", AttrKind.VALUES, ValueType.TEXT, False, 1),
    )
}

# ---------------------------------------------------------------------------
# Chỉ số cho limit (design.md mục 5, 6.5)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MetricSpec:
    name: str
    allowed_bounds: FrozenSet[str]  # tập con của {"min", "max"} (V2)
    weight: int


METRICS: Dict[str, MetricSpec] = {
    spec.name: spec
    for spec in (
        MetricSpec("subjects_per_day", frozenset({"min", "max"}), 2),
        MetricSpec("subjects_per_session", frozenset({"min", "max"}), 2),
        MetricSpec("periods_per_day", frozenset({"min", "max"}), 2),
        MetricSpec("gap_periods", frozenset({"min", "max"}), 1),
        MetricSpec("consecutive_periods", frozenset({"max"}), 1),
        MetricSpec("study_days", frozenset({"min", "max"}), 2),
    )
}

# ---------------------------------------------------------------------------
# Tiết và giờ (design.md mục 7.1)
# ---------------------------------------------------------------------------

MIN_PERIOD = 1
MAX_PERIOD = 10
PERIOD_LENGTH_MINUTES = 50  # giả định (Q1)

PERIOD_START_MINUTES: Dict[int, int] = {
    1: 7 * 60 + 30,
    2: 8 * 60 + 30,
    3: 9 * 60 + 30,
    4: 10 * 60 + 30,
    5: 11 * 60 + 30,
    6: 13 * 60,
    7: 14 * 60,
    8: 15 * 60,
    9: 16 * 60,
    10: 17 * 60,
}
PERIOD_END_MINUTES: Dict[int, int] = {
    period: start + PERIOD_LENGTH_MINUTES for period, start in PERIOD_START_MINUTES.items()
}

# ---------------------------------------------------------------------------
# Buổi (design.md mục 5, 7.2)
# ---------------------------------------------------------------------------

def _periods(first: int, last: int) -> FrozenSet[int]:
    return frozenset(range(first, last + 1))


SESSIONS: Dict[str, FrozenSet[int]] = {
    "sáng": _periods(1, 5),
    "chiều": _periods(6, 10),
    "sáng sớm": _periods(1, 2),    # giả định
    "chiều muộn": _periods(8, 10),  # giả định
}

# key đã gập -> tên buổi chuẩn
SESSION_ALIASES: Dict[str, str] = {
    "sang": "sáng",
    "buoisang": "sáng",
    "chieu": "chiều",
    "buoichieu": "chiều",
    "sangsom": "sáng sớm",
    "buoisangsom": "sáng sớm",
    "chieumuon": "chiều muộn",
    "buoichieumuon": "chiều muộn",
}

# subjects_per_session: buổi của lớp tính theo tiết bắt đầu (≤ 5 là sáng, ≥ 6 là chiều)
MORNING_LAST_PERIOD = 5

# ---------------------------------------------------------------------------
# Thứ (design.md mục 7.3)
# ---------------------------------------------------------------------------

DAYS = ("T2", "T3", "T4", "T5", "T6", "T7", "CN")

# key đã gập -> mã thứ. Dùng cho cả giá trị LLM sinh lẫn cột `day` của dữ liệu lớp
# ("Thứ Hai" -> "thuhai" -> "T2").
DAY_ALIASES: Dict[str, str] = {
    "thu2": "T2", "thuhai": "T2", "t2": "T2",
    "thu3": "T3", "thuba": "T3", "t3": "T3",
    "thu4": "T4", "thutu": "T4", "t4": "T4",
    "thu5": "T5", "thunam": "T5", "t5": "T5",
    "thu6": "T6", "thusau": "T6", "t6": "T6",
    "thu7": "T7", "thubay": "T7", "t7": "T7",
    "chunhat": "CN", "cn": "CN",
}

# key đã gập -> nhóm thứ
DAY_GROUPS: Dict[str, FrozenSet[str]] = {
    "cuoituan": frozenset({"T7", "CN"}),
    "ngaythuong": frozenset({"T2", "T3", "T4", "T5", "T6"}),
    "cacngaytrongtuan": frozenset({"T2", "T3", "T4", "T5", "T6"}),
}

# ---------------------------------------------------------------------------
# Ngôn ngữ, khu (design.md mục 7.3)
# ---------------------------------------------------------------------------

LANGUAGE_EN = "Tiếng Anh"
LANGUAGE_VI = "Tiếng Việt"

LANGUAGE_ALIASES: Dict[str, str] = {
    "tienganh": LANGUAGE_EN, "english": LANGUAGE_EN, "ta": LANGUAGE_EN,
    "tiengviet": LANGUAGE_VI, "tv": LANGUAGE_VI,
}

AREAS = ("K", "V")
AREA_ALIASES: Dict[str, str] = {
    "k": "K", "khuk": "K",
    "v": "V", "khuv": "V",
}

# Phòng có tiền tố khu: "V.A201" -> khu V, phòng A201
ROOM_AREA_SEPARATOR = "."

# ---------------------------------------------------------------------------
# Giá trị không xác định trong dữ liệu lớp (design.md mục 6.7)
# ---------------------------------------------------------------------------

# So sánh sau khi strip(). Chuỗi rỗng luôn là không xác định.
UNKNOWN_AREAS: FrozenSet[str] = frozenset({"", "Khác", "(Chọn)", "Chưa xếp phòng", "-"})
UNKNOWN_ROOMS: FrozenSet[str] = frozenset({"", "_"})
UNKNOWN_TEACHERS: FrozenSet[str] = frozenset({"", "."})
UNKNOWN_TEACHER_PREFIX = "Khoa."
UNKNOWN_DAYS: FrozenSet[str] = frozenset({"", "Thứ _"})
UNKNOWN_CLASS_GROUPS: FrozenSet[str] = frozenset({""})

# Thuộc tính thời gian: không xác định khi lớp không có lịch
TIME_ATTRIBUTES: FrozenSet[str] = frozenset({
    "day", "session", "periods", "start_period", "end_period", "start_time", "end_time", "duration",
})

# ---------------------------------------------------------------------------
# Khớp tên (design.md mục 7.4, 7.5)
# ---------------------------------------------------------------------------

COURSE_WORD_OVERLAP_THRESHOLD = 0.6

TEACHER_TITLE_PATTERN = r"^((PGS|GS|TS|ThS|KS|CN)\.)+"
# Các từ xưng hô bị bỏ khi làm sạch tên (so sánh theo từ, sau khi chuyển chữ thường)
TEACHER_HONORIFICS: Tuple[str, ...] = ("thầy", "cô", "giảng viên", "gv")
