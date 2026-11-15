"""Mô hình bài toán xếp lịch cho các solver (docs/specs/algorithms/design.md mục 1).

Một lịch là vector x, x[i] là chỉ số lớp được chọn của môn i trong `Problem.options[i]`.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Tuple

from app.scheduling import vocab
from app.scheduling.normalize import (
    _clean_text,
    class_area,
    class_day_code,
    class_group_number,
    class_has_schedule,
    class_language,
    class_room,
    class_teacher_known,
)

_DAY_INDEX = {code: i for i, code in enumerate(vocab.DAYS)}
_SLOTS_PER_DAY = vocab.MAX_PERIOD + 1


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _periods_of(raw: Any) -> Tuple[int, ...]:
    periods = _get(raw, "periods") or []
    if isinstance(periods, str):  # dữ liệu cũ lưu "[1, 2]"
        periods = [int(p) for p in periods.strip("[] ").split(",") if p.strip()]
    return tuple(sorted({int(p) for p in periods}))


@dataclass(frozen=True)
class ClassView:
    """Một lớp ứng viên, đã tính sẵn mọi giá trị chuẩn hoá mà hàm chấm cần."""

    course: str
    raw: Any = field(compare=False, repr=False)
    class_index: str
    day: Optional[str]                  # T2 … T7, None nếu không có lịch
    periods: Tuple[int, ...]            # rỗng nếu không có lịch
    teacher: Optional[str]              # None nếu không xác định
    group: Optional[int]
    language: Optional[str]
    area: Optional[str]
    room: Optional[str]
    slots: int                          # bitmask (thứ, tiết); 0 nếu không có lịch

    @property
    def scheduled(self) -> bool:
        return bool(self.slots)

    @property
    def start(self) -> Optional[int]:
        return self.periods[0] if self.periods else None

    @property
    def end(self) -> Optional[int]:
        return self.periods[-1] if self.periods else None

    @property
    def start_minute(self) -> Optional[int]:
        return vocab.PERIOD_START_MINUTES[self.start] if self.periods else None

    @property
    def end_minute(self) -> Optional[int]:
        return vocab.PERIOD_END_MINUTES[self.end] if self.periods else None

    @property
    def duration(self) -> int:
        return len(self.periods)

    @property
    def session(self) -> Optional[str]:
        """Buổi theo tiết bắt đầu (subjects_per_session, design.md mục 5)."""
        if not self.periods:
            return None
        return "sáng" if self.start <= vocab.MORNING_LAST_PERIOD else "chiều"

    def identity(self) -> Tuple:
        """Hai lớp cùng identity là một lựa chọn như nhau với sinh viên."""
        return (self.class_index, self.teacher, self.day, self.periods, self.area, self.room, self.language)


def class_view(course: str, raw: Any) -> ClassView:
    periods = _periods_of(raw)
    day_raw = _get(raw, "day")
    scheduled = class_has_schedule(day_raw, periods) and all(
        vocab.MIN_PERIOD <= p <= vocab.MAX_PERIOD for p in periods)
    day = class_day_code(day_raw) if scheduled else None
    slots = 0
    if scheduled:
        base = _DAY_INDEX[day] * _SLOTS_PER_DAY
        for period in periods:
            slots |= 1 << (base + period)
    teacher_raw = _clean_text(_get(raw, "teacher"))
    index_raw = _get(raw, "class_index")
    group = class_group_number(index_raw)
    return ClassView(
        course=course,
        raw=raw,
        class_index=str(group) if group is not None else _clean_text(index_raw),
        day=day,
        periods=periods if scheduled else (),
        teacher=teacher_raw if class_teacher_known(teacher_raw) else None,
        group=group,
        language=class_language(_get(raw, "language")),
        area=class_area(_get(raw, "area")),
        room=class_room(_get(raw, "room")),
        slots=slots,
    )


@dataclass
class Problem:
    courses: List[str]
    options: List[List[ClassView]]
    pinned: FrozenSet[int] = frozenset()   # chỉ số môn đã ghim

    @property
    def n(self) -> int:
        return len(self.courses)

    @property
    def sizes(self) -> List[int]:
        return [len(opts) for opts in self.options]

    @property
    def free_courses(self) -> int:
        return sum(1 for size in self.sizes if size > 1)

    def space_size(self) -> int:
        result = 1
        for size in self.sizes:
            result *= size
        return result

    def classes(self, x: Sequence[int]) -> List[ClassView]:
        return [self.options[i][x[i]] for i in range(self.n)]


def build_problem(candidates: Dict[str, Sequence[Any]],
                  pinned: Optional[Dict[str, Any]] = None) -> Problem:
    """`candidates`: môn -> các lớp (`ClassInfo` hoặc dict).

    `pinned`: môn -> `class_index` của lớp đã đăng ký (reschedule). Môn ghim chỉ còn lớp đó;
    không tìm thấy lớp thì ném ValueError.
    """
    courses: List[str] = []
    options: List[List[ClassView]] = []
    pinned_index = set()
    pinned = pinned or {}
    for course, classes in candidates.items():
        seen = set()
        views = []
        for raw in classes:
            view = class_view(course, raw)
            if view.identity() in seen:
                continue
            seen.add(view.identity())
            views.append(view)
        if course in pinned:
            wanted = str(pinned[course]).strip()
            wanted_group = class_group_number(wanted)
            chosen = [v for v in views if v.class_index == wanted
                      or (wanted_group is not None and v.group == wanted_group)]
            if not chosen:
                raise ValueError(f"Không tìm thấy lớp '{wanted}' của môn '{course}' để ghim")
            views = chosen[:1]
            pinned_index.add(len(courses))
        if not views:
            raise ValueError(f"Môn '{course}' không có lớp ứng viên")
        courses.append(course)
        options.append(views)
    return Problem(courses=courses, options=options, pinned=frozenset(pinned_index))
