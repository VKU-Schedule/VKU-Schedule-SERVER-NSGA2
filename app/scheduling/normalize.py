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
from typing import Any, Callable, FrozenSet, Iterable, List, Optional, Sequence, Tuple

from app.scheduling import vocab


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
