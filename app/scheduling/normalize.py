"""Chuẩn hoá tài liệu ưu tiên v2 (design.md mục 6.7, 7, 9).

Giá trị bề mặt do LLM sinh được đổi sang giá trị chuẩn một cách tất định (D13):
- thuộc tính dạng tập giá trị -> frozenset các giá trị chuẩn;
- `session`, `periods` -> frozenset các tiết;
- thuộc tính dạng khoảng -> tuple các khoảng đóng (a, b) đã gộp, cận mở được thay bằng biên miền.

Giá trị không chuẩn hoá được ném `NormalizeError` kèm lý do, để đưa vào `unsupported`.
"""
import math
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, FrozenSet, Iterable, List, Optional, Sequence, Tuple

from app.scheduling import vocab
from app.scheduling.schema import ParsedConstraint, ParsedDocument, UnsupportedItem, filter_items, parse_document


class NormalizeError(ValueError):
    """Giá trị không chuẩn hoá được; thông điệp là lý do đưa vào `unsupported`."""


Interval = Tuple[int, int]
IntervalSet = Tuple[Interval, ...]

# ---------------------------------------------------------------------------
# Gập chuỗi
# ---------------------------------------------------------------------------


def strip_diacritics(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    without = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return without.replace("đ", "d").replace("Đ", "D")


def fold_words(text: str) -> str:
    """Bỏ dấu, chữ thường, gộp khoảng trắng."""
    return " ".join(strip_diacritics(text).lower().split())


def fold(text: str) -> str:
    """Bỏ dấu, chữ thường, bỏ mọi khoảng trắng (như `normalize_day` của v1)."""
    return fold_words(text).replace(" ", "")


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _show(value: Any) -> str:
    return repr(value) if isinstance(value, str) else str(value)


# ---------------------------------------------------------------------------
# List: giữ phần dùng được (design.md mục 7.6)
# ---------------------------------------------------------------------------


def _as_list(raw: Any) -> List[Any]:
    return list(raw) if isinstance(raw, list) else [raw]


def _union_of(name: str, raw: Any, one: Callable[[Any], FrozenSet]) -> Tuple[FrozenSet, List[str]]:
    """Chuẩn hoá từng phần tử rồi lấy hợp. Phần tử lỗi bị bỏ, kèm warning; lỗi hết thì ném lỗi."""
    result: set = set()
    errors: List[str] = []
    for item in _as_list(raw):
        try:
            result |= one(item)
        except NormalizeError as exc:
            errors.append(str(exc))
    if not result:
        raise NormalizeError(errors[0] if len(errors) == 1 else "; ".join(errors))
    warnings = [f"Bỏ một giá trị của '{name}': {error}" for error in errors]
    return frozenset(result), warnings


# ---------------------------------------------------------------------------
# Thứ
# ---------------------------------------------------------------------------


def _day_codes(value: Any) -> FrozenSet[str]:
    if not isinstance(value, str):
        raise NormalizeError(f"Thứ không xác định: {_show(value)}")
    key = fold(value)
    if key in vocab.DAY_GROUPS:
        return vocab.DAY_GROUPS[key]
    if key in vocab.DAY_ALIASES:
        return frozenset({vocab.DAY_ALIASES[key]})
    raise NormalizeError(f"Thứ không xác định: {_show(value)}")


def normalize_day(raw: Any) -> Tuple[FrozenSet[str], List[str]]:
    return _union_of("day", raw, _day_codes)


# ---------------------------------------------------------------------------
# Buổi và tiết
# ---------------------------------------------------------------------------


def _session_periods(value: Any) -> FrozenSet[int]:
    if isinstance(value, str):
        name = vocab.SESSION_ALIASES.get(fold(value))
        if name is not None:
            return vocab.SESSIONS[name]
    raise NormalizeError(f"Buổi không xác định: {_show(value)}")


def normalize_session(raw: Any) -> Tuple[FrozenSet[int], List[str]]:
    return _union_of("session", raw, _session_periods)


def _check_period(period: int) -> int:
    if not vocab.MIN_PERIOD <= period <= vocab.MAX_PERIOD:
        raise NormalizeError(f"Tiết phải từ {vocab.MIN_PERIOD} đến {vocab.MAX_PERIOD}, gặp {period}")
    return period


_PERIOD_TEXT = re.compile(r"^\s*(?:tiet\s*)?(\d+)\s*(?:(?:-|den|toi)\s*(?:tiet\s*)?(\d+))?\s*$")


def _period_set(value: Any) -> FrozenSet[int]:
    if _is_int(value):
        return frozenset({_check_period(value)})
    if isinstance(value, dict):
        low, high = _bounds(value, vocab.MIN_PERIOD, vocab.MAX_PERIOD, _check_period)
        return frozenset(range(low, high + 1))
    if isinstance(value, str):
        match = _PERIOD_TEXT.match(fold_words(value))
        if match:
            low = _check_period(int(match.group(1)))
            high = _check_period(int(match.group(2) or low))
            if low > high:
                raise NormalizeError(f"Khoảng tiết {_show(value)} có tiết đầu lớn hơn tiết cuối")
            return frozenset(range(low, high + 1))
    raise NormalizeError(f"Tiết không đọc được: {_show(value)}")


def normalize_periods(raw: Any) -> Tuple[FrozenSet[int], List[str]]:
    # Khoảng {min, max} là một giá trị, không phải list
    return _union_of("periods", raw, _period_set)


# ---------------------------------------------------------------------------
# Khoảng: tiết bắt đầu/kết thúc, thời lượng, giờ
# ---------------------------------------------------------------------------

MINUTES_PER_DAY = 24 * 60

_TIME_TEXT = re.compile(
    r"^(\d{1,2})\s*(?:(?::|h|gio)\s*(\d{1,2})?)?\s*(?:phut)?\s*(sang|trua|chieu|toi)?$"
)


def parse_time(value: Any) -> int:
    """Giờ bề mặt -> phút trong ngày. Hậu tố "chiều" / "tối" cộng 12 giờ nếu giờ < 12."""
    if _is_int(value):
        hour, minute, suffix = value, 0, None
    elif isinstance(value, str):
        match = _TIME_TEXT.match(fold_words(value))
        if not match:
            raise NormalizeError(f"Giờ không đọc được: {_show(value)}")
        hour, minute, suffix = int(match.group(1)), int(match.group(2) or 0), match.group(3)
    else:
        raise NormalizeError(f"Giờ không đọc được: {_show(value)}")
    if suffix in ("chieu", "toi") and hour < 12:
        hour += 12
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise NormalizeError(f"Giờ không hợp lệ: {_show(value)}")
    return hour * 60 + minute


def _check_int_in(low: int, high: int) -> Callable[[Any], int]:
    def check(value: Any) -> int:
        if not _is_int(value):
            raise NormalizeError(f"Cần số nguyên, gặp {_show(value)}")
        if not low <= value <= high:
            raise NormalizeError(f"Giá trị phải từ {low} đến {high}, gặp {value}")
        return value
    return check


def _bounds(value: dict, domain_low: int, domain_high: int, convert: Callable[[Any], int]) -> Interval:
    low = convert(value["min"]) if value.get("min") is not None else domain_low
    high = convert(value["max"]) if value.get("max") is not None else domain_high
    if low > high:
        raise NormalizeError(f"Khoảng {value} có min lớn hơn max")
    return low, high


# thuộc tính -> (biên dưới, biên trên, hàm đổi một giá trị bề mặt)
_RANGE_DOMAINS = {
    "start_period": (vocab.MIN_PERIOD, vocab.MAX_PERIOD, _check_int_in(vocab.MIN_PERIOD, vocab.MAX_PERIOD)),
    "end_period": (vocab.MIN_PERIOD, vocab.MAX_PERIOD, _check_int_in(vocab.MIN_PERIOD, vocab.MAX_PERIOD)),
    "duration": (1, vocab.MAX_PERIOD, _check_int_in(1, vocab.MAX_PERIOD)),
    "start_time": (0, MINUTES_PER_DAY - 1, parse_time),
    "end_time": (0, MINUTES_PER_DAY - 1, parse_time),
}


def merge_intervals(intervals: Iterable[Interval]) -> IntervalSet:
    merged: List[List[int]] = []
    for low, high in sorted(intervals):
        if merged and low <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], high)
        else:
            merged.append([low, high])
    return tuple((low, high) for low, high in merged)


def normalize_range(name: str, raw: Any) -> Tuple[IntervalSet, List[str]]:
    """Số, list số (OR) hoặc khoảng -> tập khoảng đóng đã gộp."""
    domain_low, domain_high, convert = _RANGE_DOMAINS[name]
    intervals: List[Interval] = []
    errors: List[str] = []
    for item in _as_list(raw):
        try:
            if isinstance(item, dict):
                intervals.append(_bounds(item, domain_low, domain_high, convert))
            else:
                point = convert(item)
                intervals.append((point, point))
        except NormalizeError as exc:
            errors.append(str(exc))
    if not intervals:
        raise NormalizeError(f"'{name}': " + "; ".join(errors))
    return merge_intervals(intervals), [f"Bỏ một giá trị của '{name}': {error}" for error in errors]


# ---------------------------------------------------------------------------
# Khu, phòng, ngôn ngữ, nhóm lớp
# ---------------------------------------------------------------------------


def _area_code(value: Any) -> FrozenSet[str]:
    if isinstance(value, str) and fold(value) in vocab.AREA_ALIASES:
        return frozenset({vocab.AREA_ALIASES[fold(value)]})
    raise NormalizeError(f"Khu không xác định: {_show(value)}")


def normalize_area(raw: Any) -> Tuple[FrozenSet[str], List[str]]:
    return _union_of("area", raw, _area_code)


_ROOM_WITH_AREA = re.compile(
    r"^(" + "|".join(vocab.AREAS) + r")" + re.escape(vocab.ROOM_AREA_SEPARATOR) + r"(.+)$"
)


def split_room(value: str) -> Tuple[Optional[str], str]:
    """"V.A201" -> ("V", "A201"); "A201" -> (None, "A201"). Chỉ tách khi tiền tố là mã khu."""
    room = " ".join(value.split()).upper()
    match = _ROOM_WITH_AREA.match(room)
    if match:
        return match.group(1), match.group(2)
    return None, room


def normalize_room(raw: Any) -> Tuple[FrozenSet[str], Optional[FrozenSet[str]], List[str]]:
    """Trả về (tập phòng, tập khu lấy từ tiền tố hoặc None, warnings).

    Tiền tố khu chỉ được dùng khi mọi phòng trong list đều có tiền tố, vì điều kiện khu
    được AND với cả bộ lọc.
    """
    rooms: set = set()
    areas: set = set()
    plain = 0
    warnings: List[str] = []
    for item in _as_list(raw):
        if not isinstance(item, str) or not item.strip():
            warnings.append(f"Bỏ một giá trị của 'room': phòng không xác định: {_show(item)}")
            continue
        area, room = split_room(item)
        rooms.add(room)
        if area is None:
            plain += 1
        else:
            areas.add(area)
    if not rooms:
        raise NormalizeError("Không có phòng nào dùng được")
    if areas and plain:
        warnings.append("Bỏ tiền tố khu của 'room' vì list có cả phòng không kèm khu")
        return frozenset(rooms), None, warnings
    return frozenset(rooms), (frozenset(areas) if areas else None), warnings


def _language(value: Any) -> FrozenSet[str]:
    if isinstance(value, str) and fold(value) in vocab.LANGUAGE_ALIASES:
        return frozenset({vocab.LANGUAGE_ALIASES[fold(value)]})
    raise NormalizeError(f"Ngôn ngữ không xác định: {_show(value)}")


def normalize_language(raw: Any) -> Tuple[FrozenSet[str], List[str]]:
    return _union_of("language", raw, _language)


_FIRST_NUMBER = re.compile(r"\d+")


def _class_group(value: Any) -> FrozenSet[int]:
    if _is_int(value) and value >= 1:
        return frozenset({value})
    if isinstance(value, str):
        match = _FIRST_NUMBER.search(value)
        if match and int(match.group()) >= 1:
            return frozenset({int(match.group())})
    raise NormalizeError(f"Nhóm lớp không đọc được: {_show(value)}")


def normalize_class_group(raw: Any) -> Tuple[FrozenSet[int], List[str]]:
    return _union_of("class_group", raw, _class_group)


# ---------------------------------------------------------------------------
# Bộ chuẩn hoá theo thuộc tính (trừ course và teacher, cần ngữ cảnh: xem mục khớp thực thể)
# ---------------------------------------------------------------------------

VALUE_NORMALIZERS = {
    "day": normalize_day,
    "session": normalize_session,
    "periods": normalize_periods,
    "area": normalize_area,
    "language": normalize_language,
    "class_group": normalize_class_group,
    **{name: (lambda raw, _name=name: normalize_range(_name, raw)) for name in _RANGE_DOMAINS},
}


# ---------------------------------------------------------------------------
# Khớp thực thể: môn (design.md mục 7.4) và giảng viên (mục 7.5)
# ---------------------------------------------------------------------------


def _course_matches(said: str, courses: Sequence[str]) -> List[str]:
    """Các môn khớp với tên sinh viên nói, theo bậc ưu tiên đầu tiên có kết quả."""
    said_key = fold_words(said)
    if not said_key:
        return []
    keys = [(course, fold_words(course)) for course in courses]

    exact = [course for course, key in keys if key == said_key]
    if exact:
        return exact
    contained = [course for course, key in keys if said_key in key or key in said_key]
    if contained:
        return contained
    said_words = set(said_key.split())
    return [
        course for course, key in keys
        if len(said_words & set(key.split())) / len(said_words) >= vocab.COURSE_WORD_OVERLAP_THRESHOLD
    ]


def match_courses(raw: Any, selected_courses: Sequence[str]) -> Tuple[FrozenSet[str], List[str]]:
    """Tên môn bề mặt -> tập tên môn trong danh sách đã chọn."""
    warnings: List[str] = []

    def one(value: Any) -> FrozenSet[str]:
        if not isinstance(value, str):
            raise NormalizeError(f"Tên môn không hợp lệ: {_show(value)}")
        matches = _course_matches(value, selected_courses)
        if not matches:
            raise NormalizeError(f"Môn không có trong danh sách đã chọn: {_show(value)}")
        if len(matches) > 1:
            warnings.append(f"Có {len(matches)} môn khớp {_show(value)}: {', '.join(matches)}")
        return frozenset(matches)

    courses, list_warnings = _union_of("course", raw, one)
    return courses, warnings + list_warnings


_TEACHER_TITLE = re.compile(vocab.TEACHER_TITLE_PATTERN, re.IGNORECASE)
_TEACHER_HONORIFICS = re.compile(
    r"(?<!\w)(" + "|".join(re.escape(word) for word in vocab.TEACHER_HONORIFICS) + r")(?!\w)"
)


def clean_teacher_name(name: str) -> str:
    """"PGS.TS.Nguyễn Thanh Bình" -> "nguyễn thanh bình"; "thầy Sơn" -> "sơn". Giữ dấu."""
    text = unicodedata.normalize("NFC", name).strip()
    text = _TEACHER_TITLE.sub("", text).lower()
    text = _TEACHER_HONORIFICS.sub(" ", text)
    return " ".join(text.split())


def teacher_name_matches(said: str, full_name: str) -> bool:
    """Khớp theo từ: trùng toàn bộ, là phần cuối của tên đầy đủ, hoặc trùng cả họ lẫn tên.

    Không khớp chỉ theo họ: "Nguyễn" không khớp "Nguyễn Văn A".
    """
    said_words = clean_teacher_name(said).split()
    full_words = clean_teacher_name(full_name).split()
    if not said_words or not full_words or len(said_words) > len(full_words):
        return False
    if full_words[-len(said_words):] == said_words:
        return True
    return len(said_words) >= 2 and said_words[0] == full_words[0] and said_words[-1] == full_words[-1]


def match_teachers(raw: Any, teachers: Iterable[str]) -> Tuple[FrozenSet[str], List[str]]:
    """Tên giảng viên bề mặt -> tập tên giảng viên thật (đúng chuỗi trong dữ liệu lớp).

    `teachers` là giảng viên của các lớp ứng viên; giá trị không xác định bị bỏ qua.
    """
    known = sorted({teacher for teacher in teachers if class_teacher_known(teacher)})
    result: set = set()
    warnings: List[str] = []
    missing: List[str] = []
    for value in _as_list(raw):
        if not isinstance(value, str) or not clean_teacher_name(value):
            missing.append(_show(value))
            continue
        matches = [teacher for teacher in known if teacher_name_matches(value, teacher)]
        if not matches:
            missing.append(_show(value))
        elif len(matches) > 1:
            warnings.append(f"Có {len(matches)} giảng viên khớp {_show(value)}: {', '.join(matches)}")
        result.update(matches)
    if not result:
        raise NormalizeError(f"Không giảng viên nào khớp {', '.join(missing)}")
    warnings += [f"Bỏ một giá trị của 'teacher': không giảng viên nào khớp {value}" for value in missing]
    return frozenset(result), warnings


# ---------------------------------------------------------------------------
# Giá trị trong dữ liệu lớp (design.md mục 6.7)
# ---------------------------------------------------------------------------


def _clean_text(value: Any) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return str(value).strip()


def class_day_code(day: Any) -> Optional[str]:
    """"Thứ Hai" -> "T2"; `Thứ _`, trống -> None."""
    text = _clean_text(day)
    if text in vocab.UNKNOWN_DAYS:
        return None
    return vocab.DAY_ALIASES.get(fold(text))


def class_has_schedule(day: Any, periods: Sequence[int]) -> bool:
    """Lớp có lịch khi có thứ xác định và có ít nhất một tiết."""
    return class_day_code(day) is not None and bool(periods)


def class_area(area: Any) -> Optional[str]:
    text = _clean_text(area)
    if text in vocab.UNKNOWN_AREAS:
        return None
    return vocab.AREA_ALIASES.get(fold(text))


def class_room(room: Any) -> Optional[str]:
    text = _clean_text(room)
    if text in vocab.UNKNOWN_ROOMS:
        return None
    return split_room(text)[1]


def class_teacher_known(teacher: Any) -> bool:
    text = _clean_text(teacher)
    return text not in vocab.UNKNOWN_TEACHERS and not text.startswith(vocab.UNKNOWN_TEACHER_PREFIX)


def class_group_number(class_index: Any) -> Optional[int]:
    """`"2"`, `2`, `2.0` -> 2; trống hoặc NaN -> None."""
    text = _clean_text(class_index)
    if text in vocab.UNKNOWN_CLASS_GROUPS:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return int(number) if number.is_integer() and number >= 1 else None


def class_language(language: Any) -> Optional[str]:
    text = _clean_text(language)
    return vocab.LANGUAGE_ALIASES.get(fold(text)) if text else None


def class_time_range(periods: Sequence[int]) -> Optional[Tuple[int, int]]:
    """(phút bắt đầu của tiết đầu, phút kết thúc của tiết cuối), hoặc None nếu không có tiết."""
    if not periods:
        return None
    return vocab.PERIOD_START_MINUTES[min(periods)], vocab.PERIOD_END_MINUTES[max(periods)]


# ---------------------------------------------------------------------------
# Chuẩn hoá cả tài liệu (design.md mục 6.4, 6.5, 7.6, 9)
# ---------------------------------------------------------------------------

# Bộ lọc đã chuẩn hoá: thuộc tính -> frozenset (giá trị chuẩn hoặc tiết) hoặc IntervalSet
NormalizedFilter = Dict[str, Any]

LLM_UNSUPPORTED_REASON = "LLM không ánh xạ được"


@dataclass
class NormalizedConstraint:
    id: int
    kind: str                                   # prefer / avoid / limit
    level: str
    weight: int
    source: Dict[str, Any]
    condition: NormalizedFilter = field(default_factory=dict)  # với prefer / avoid
    metric: Optional[str] = None                # với limit
    min: Optional[int] = None
    max: Optional[int] = None
    scope: NormalizedFilter = field(default_factory=dict)      # rỗng = mọi lớp
    exclude: List[NormalizedFilter] = field(default_factory=list)

    @property
    def group(self) -> Tuple[str, Any]:
        """Nhóm của quy tắc ngoại lệ (6.4): cùng tập key điều kiện, hoặc cùng chỉ số."""
        if self.kind == "limit":
            return "limit", self.metric
        return "filter", frozenset(self.condition)

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {"id": self.id, "kind": self.kind}
        if self.kind == "limit":
            data["metric"] = self.metric
            data.update({key: getattr(self, key) for key in ("min", "max") if getattr(self, key) is not None})
        else:
            data["condition"] = filter_to_dict(self.condition)
        data.update({
            "scope": filter_to_dict(self.scope),
            "exclude": [filter_to_dict(item) for item in self.exclude],
            "level": self.level,
            "weight": self.weight,
            "source": self.source,
        })
        return data


@dataclass
class NormalizedDocument:
    version: str
    constraints: List[NormalizedConstraint] = field(default_factory=list)
    unsupported: List[UnsupportedItem] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "constraints": [constraint.to_dict() for constraint in self.constraints],
            "unsupported": [item.to_dict() for item in self.unsupported],
            "warnings": list(self.warnings),
        }


def filter_to_dict(normalized: NormalizedFilter) -> Dict[str, Any]:
    """Dạng JSON ổn định: tập -> list đã sắp xếp, khoảng -> list [a, b]."""
    data = {}
    for name in vocab.ATTRIBUTES:
        if name not in normalized:
            continue
        value = normalized[name]
        if vocab.ATTRIBUTES[name].kind is vocab.AttrKind.RANGE:
            data[name] = [list(interval) for interval in value]
        else:
            data[name] = sorted(value)
    return data


def _get(obj: Any, name: str) -> Any:
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


def _flatten_candidates(candidates: Any) -> List[Any]:
    if candidates is None:
        return []
    if isinstance(candidates, dict):
        return [cls for classes in candidates.values() for cls in classes]
    return list(candidates)


class _ConstraintContext:
    def __init__(self, selected_courses: Sequence[str], classes: List[Any]):
        self.selected_courses = list(selected_courses)
        self.classes = classes

    def teachers(self, courses: Optional[FrozenSet[str]]) -> List[str]:
        return [
            _get(cls, "teacher") for cls in self.classes
            if _get(cls, "teacher") and (courses is None or _get(cls, "course_name") in courses)
        ]


def _normalize_filter(where: str, items: List[Tuple[str, Any]], context: _ConstraintContext,
                      scope_courses: Optional[FrozenSet[str]], warnings: List[str]) -> NormalizedFilter:
    result: NormalizedFilter = {}
    room_areas: Optional[FrozenSet[str]] = None
    for name, raw in items:
        try:
            if name == "course":
                value, value_warnings = match_courses(raw, context.selected_courses)
            elif name == "teacher":
                value, value_warnings = match_teachers(raw, context.teachers(scope_courses))
            elif name == "room":
                value, room_areas, value_warnings = normalize_room(raw)
            else:
                value, value_warnings = VALUE_NORMALIZERS[name](raw)
        except NormalizeError as exc:
            raise NormalizeError(f"'{name}' trong '{where}': {exc}") from None
        result[name] = value
        warnings.extend(f"'{name}' trong '{where}': {warning}" for warning in value_warnings)
    if room_areas is not None:
        # "V.A201": điều kiện khu được thêm vào cùng bộ lọc
        areas = result["area"] & room_areas if "area" in result else room_areas
        if not areas:
            raise NormalizeError(f"Khu của 'room' mâu thuẫn với 'area' trong '{where}'")
        result["area"] = areas
    return result


def _weight(kind: str, level: str, metric: Optional[str], keys: Iterable[str]) -> int:
    """design.md mục 6.5 (D18)."""
    if kind == "limit":
        base = vocab.METRICS[metric].weight
    else:
        base = max(vocab.ATTRIBUTES[name].weight for name in keys if vocab.ATTRIBUTES[name].weight is not None)
    return base * vocab.HIGH_MULTIPLIER if level == "high" else base


def _normalize_constraint(parsed: ParsedConstraint, context: _ConstraintContext,
                          warnings: List[str]) -> NormalizedConstraint:
    constraint = parsed.constraint
    kind = parsed.kind
    condition_items = filter_items(constraint.prefer if kind == "prefer" else constraint.avoid)
    scope_items = filter_items(constraint.scope)

    # `course` chỉ có nghĩa trong scope (R2)
    moved = [(name, value) for name, value in condition_items if name == "course"]
    condition_items = [(name, value) for name, value in condition_items if name != "course"]
    if kind != "limit" and not condition_items:
        raise NormalizeError(f"Điều kiện của '{kind}' chỉ có 'course': không có gì để {kind}")

    scope = _normalize_filter("scope", scope_items, context, None, warnings) if scope_items else {}
    if moved:
        courses = _normalize_filter(kind, moved, context, None, warnings)["course"]
        if "course" in scope:
            courses = scope["course"] & courses
            if not courses:
                raise NormalizeError("'course' trong điều kiện không giao với 'course' trong 'scope'")
        scope["course"] = courses

    condition: NormalizedFilter = {}
    if kind != "limit":
        condition = _normalize_filter(kind, condition_items, context, scope.get("course"), warnings)

    keys = [name for name, _ in condition_items + scope_items if name != "course"]
    if kind != "limit" and not keys:
        raise NormalizeError("Ràng buộc không có thuộc tính nào ngoài 'course'")
    return NormalizedConstraint(
        id=parsed.index,
        kind=kind,
        level=constraint.level,
        weight=_weight(kind, constraint.level, constraint.limit, keys),
        source=parsed.source,
        condition=condition,
        metric=constraint.limit,
        min=constraint.min,
        max=constraint.max,
        scope=scope,
    )


def _value_subset(name: str, inner: Any, outer: Any) -> bool:
    if vocab.ATTRIBUTES[name].kind is vocab.AttrKind.RANGE:
        return all(any(o_low <= low and high <= o_high for o_low, o_high in outer) for low, high in inner)
    return inner <= outer


def is_more_specific(inner: NormalizedFilter, outer: NormalizedFilter) -> bool:
    """Phạm vi `inner` nằm trong `outer` và khác `outer` (design.md mục 6.4)."""
    if inner == outer:
        return False
    return all(name in inner and _value_subset(name, inner[name], value) for name, value in outer.items())


def _apply_exceptions(constraints: List[NormalizedConstraint], warnings: List[str]) -> None:
    for general in constraints:
        for specific in constraints:
            if specific is general or specific.group != general.group:
                continue
            if is_more_specific(specific.scope, general.scope) and specific.scope not in general.exclude:
                general.exclude.append(specific.scope)

    for i, first in enumerate(constraints):
        for second in constraints[i + 1:]:
            if (
                {first.kind, second.kind} == {"prefer", "avoid"}
                and first.scope == second.scope
                and first.condition == second.condition
            ):
                warnings.append(
                    f"Ràng buộc {first.id} và {second.id} mâu thuẫn: cùng phạm vi, cùng điều kiện, "
                    f"một '{first.kind}' một '{second.kind}'. Cả hai vẫn được áp dụng"
                )


def normalize_document(doc: Any, selected_courses: Optional[Sequence[str]] = None,
                       candidates: Any = None) -> NormalizedDocument:
    """Validate (nếu cần) và chuẩn hoá tài liệu ưu tiên v2.

    - `doc`: `ParsedDocument`, hoặc JSON thô (sẽ được `parse_document`).
    - `selected_courses`: tên các môn sinh viên đã chọn. Thiếu thì lấy từ `candidates`.
    - `candidates`: các lớp ứng viên (`ClassInfo` hoặc dict), dạng list hoặc dict môn -> list lớp.
    """
    parsed = doc if isinstance(doc, ParsedDocument) else parse_document(doc)
    classes = _flatten_candidates(candidates)
    if selected_courses is None:
        selected_courses = list(dict.fromkeys(_get(cls, "course_name") for cls in classes))
    context = _ConstraintContext(selected_courses, classes)

    result = NormalizedDocument(version=parsed.version, warnings=list(parsed.warnings))
    unsupported = list(parsed.unsupported)
    for item in parsed.constraints:
        constraint_warnings: List[str] = []
        try:
            normalized = _normalize_constraint(item, context, constraint_warnings)
        except NormalizeError as exc:
            unsupported.append(UnsupportedItem(index=item.index, source=item.source, reason=str(exc)))
            continue
        result.constraints.append(normalized)
        result.warnings.extend(f"Ràng buộc {item.index}: {warning}" for warning in constraint_warnings)

    _apply_exceptions(result.constraints, result.warnings)

    unsupported.sort(key=lambda entry: entry.index)
    unsupported += [UnsupportedItem(index=None, source=text, reason=LLM_UNSUPPORTED_REASON) for text in parsed.llm_unsupported]
    result.unsupported = unsupported
    return result
