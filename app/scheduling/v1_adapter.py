"""Chuyển tài liệu ưu tiên v1 (`defaults` / `periods`) sang v2 (design.md mục 12.1).

Dùng cho các lịch đã lưu `parsed_prompt` v1 (câu hỏi Q2). Hành vi mặc định giữ như code v1
(`app/service/constraints_service.py`): thiếu `like` coi là `false`, thiếu `up_or_down` coi là
`"down"`. Ràng buộc được sinh theo thứ tự key trong tài liệu v1.

Phần không chuyển được không bị bỏ âm thầm: nó được trả về để đưa vào `unsupported` (R7).
"""
from typing import Any, Dict, List, Optional, Tuple

ALL_WEEK = "cả tuần"
UNSUPPORTED_REASON = "Không chuyển được từ v1"


class V1AdapterError(ValueError):
    """Tài liệu v1 sai cấu trúc tới mức không chuyển được: API trả 400."""


Constraint = Dict[str, Any]
Scope = Dict[str, Any]


class _Converter:
    def __init__(self) -> None:
        self.constraints: List[Constraint] = []
        self.warnings: List[str] = []
        self.unsupported: List[Tuple[Any, str]] = []  # (đoạn v1 gốc, lý do)

    # --- tiện ích ---------------------------------------------------------

    def emit(self, constraint: Constraint, scope: Scope) -> None:
        if scope:
            constraint["scope"] = dict(scope)
        self.constraints.append(constraint)

    def skip(self, where: str, source: Any, reason: str) -> None:
        self.unsupported.append(({where: source}, f"{UNSUPPORTED_REASON}: {reason}"))

    @staticmethod
    def kind(pref: Dict[str, Any]) -> str:
        return "prefer" if pref.get("like", False) else "avoid"

    @staticmethod
    def one_or_list(values: List[Any]) -> Any:
        return values[0] if len(values) == 1 else values

    def emit_grouped(self, attribute: str, items: List[Dict[str, Any]], value_key: str, scope: Scope) -> None:
        """List các {value, like}: gom theo like, mỗi nhóm một ràng buộc, theo thứ tự xuất hiện."""
        groups: Dict[str, List[Any]] = {}
        for item in items:
            if isinstance(item, dict) and item.get(value_key) not in (None, ""):
                groups.setdefault(self.kind(item), []).append(item[value_key])
        for kind, values in groups.items():
            self.emit({kind: {attribute: self.one_or_list(values)}}, scope)

    # --- từng key v1 -------------------------------------------------------

    def subject_limit(self, metric: str, value: Any, scope: Scope, where: str) -> None:
        if isinstance(value, dict):
            value = value.get("value")
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            self.skip(where, value, "cần số nguyên ≥ 0")
            return
        self.emit({"limit": metric, "max": value}, scope)

    def subject_count(self, pref: Any, scope: Scope, where: str) -> None:
        value = pref.get("value") if isinstance(pref, dict) else pref
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            self.skip(where, pref, "cần số nguyên ≥ 0")
            return
        self.emit({"limit": "subjects_per_day", "min": value, "max": value}, scope)

    def duration(self, pref: Dict[str, Any], scope: Scope, where: str) -> None:
        value = pref.get("value")
        if not isinstance(value, int):
            self.skip(where, pref, "'value' phải là số nguyên")
            return
        bound = "min" if pref.get("up_or_down", "down") == "up" else "max"
        self.emit({self.kind(pref): {"duration": {bound: value}}}, scope)

    def period(self, pref: Dict[str, Any], scope: Scope, where: str) -> None:
        values = pref.get("value")
        if not isinstance(values, list) or not values or not all(isinstance(v, int) for v in values):
            self.skip(where, pref, "'value' phải là list tiết")
            return
        periods = sorted(set(values))
        contiguous = len(periods) > 1 and periods == list(range(periods[0], periods[-1] + 1))
        value = {"min": periods[0], "max": periods[-1]} if contiguous else periods
        self.emit({self.kind(pref): {"periods": value}}, scope)

    def period_onward(self, pref: Dict[str, Any], scope: Scope, where: str) -> None:
        value = pref.get("value")
        if not isinstance(value, int):
            self.skip(where, pref, "'value' phải là số nguyên")
            return
        self.emit({self.kind(pref): {"start_period": {"min": value}}}, scope)

    def hour_onward(self, pref: Dict[str, Any], scope: Scope, where: str) -> None:
        value = pref.get("value")
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value < 24:
            self.skip(where, pref, "'value' phải là giờ từ 0 đến 23")
            return
        hours, minutes = int(value), round((value - int(value)) * 60)
        self.emit({self.kind(pref): {"start_time": {"min": f"{hours:02d}:{minutes:02d}"}}}, scope)

    def rest_interval(self, pref: Dict[str, Any], scope: Scope, where: str) -> None:
        value = pref.get("value")
        if not isinstance(value, int) or value < 0:
            self.skip(where, pref, "'value' phải là số nguyên ≥ 0")
            return
        up = pref.get("up_or_down", "down") == "up"
        if pref.get("like", False):
            bound, bound_value = ("min", value) if up else ("max", value)
        else:
            # không thích "≥ v" nghĩa là muốn "≤ v − 1"; không thích "≤ v" nghĩa là muốn "≥ v + 1"
            bound, bound_value = ("max", value - 1) if up else ("min", value + 1)
            if bound_value < 0:
                self.skip(where, pref, "không có khoảng nghỉ nào nhỏ hơn 0")
                return
        self.emit({"limit": "gap_periods", bound: bound_value}, scope)

    def classes(self, items: Any, scope: Scope, where: str) -> None:
        for item in items if isinstance(items, list) else [items]:
            if not isinstance(item, dict):
                self.skip(where, item, "phần tử phải là object")
                continue
            class_scope = dict(scope)
            if item.get("name"):
                class_scope = {"course": item["name"], **scope}
            self.emit_grouped("class_group", item.get("class_group") or [], "value", class_scope)
            self.emit_grouped("teacher", item.get("teacher") or [], "name", class_scope)

    def key(self, name: str, pref: Any, scope: Scope, where: str) -> None:
        if pref is None or pref == [] or pref == {}:
            return
        if name in ("room", "area", "teacher"):
            attribute = name
            items = pref if isinstance(pref, list) else [pref]
            self.emit_grouped(attribute, items, "name" if name == "teacher" else "value", scope)
        elif name == "class":
            self.classes(pref, scope, where)
        elif name == "subject_per_session":
            self.subject_limit("subjects_per_session", pref, scope, where)
        elif name == "subject_per_day":
            self.subject_limit("subjects_per_day", pref, scope, where)
        elif name == "subject_count":
            self.subject_count(pref, scope, where)
        elif name in _OBJECT_HANDLERS:
            if not isinstance(pref, dict):
                self.skip(where, pref, "phải là object {value, like}")
                return
            _OBJECT_HANDLERS[name](self, pref, scope, where)
        else:
            self.skip(where, pref, f"key '{name}' không có trong v1")

    # --- tài liệu -----------------------------------------------------------

    def defaults(self, defaults: Dict[str, Any]) -> None:
        for name, pref in defaults.items():
            self.key(name, pref, {}, f"defaults.{name}")

    def period_entry(self, index: int, entry: Dict[str, Any]) -> None:
        day = entry.get("day")
        day_value: Optional[str] = day.get("value") if isinstance(day, dict) else None
        others = {name: pref for name, pref in entry.items() if name != "day" and pref not in (None, [], {})}
        where = f"periods[{index}]"

        if day_value and not day.get("like", False) and not others:
            self.emit({"avoid": {"day": day_value.lower()}}, {})
            return
        if day_value and not day.get("like", False):
            self.warnings.append(
                f"{where}: 'day.like' là false nhưng entry có ràng buộc khác; "
                f"áp dụng các ràng buộc đó cho '{day_value}' như v1"
            )

        scope: Scope = {}
        if day_value and day_value.strip().lower() != ALL_WEEK:
            scope = {"day": day_value.lower()}
        for name, pref in others.items():
            self.key(name, pref, scope, f"{where}.{name}")


_OBJECT_HANDLERS = {
    "duration_of_session": _Converter.duration,
    "period": _Converter.period,
    "period_onward": _Converter.period_onward,
    "hour_onward": _Converter.hour_onward,
    "rest_interval": _Converter.rest_interval,
}


def is_v1_document(raw: Any) -> bool:
    return isinstance(raw, dict) and ("defaults" in raw or "periods" in raw)


def convert_v1(raw: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str], List[Tuple[Any, str]]]:
    """Trả về (tài liệu v2, warnings, các phần không chuyển được dạng (đoạn v1, lý do))."""
    defaults = raw.get("defaults")
    periods = raw.get("periods")
    defaults = {} if defaults is None else defaults
    periods = [] if periods is None else periods
    if not isinstance(defaults, dict):
        raise V1AdapterError("'defaults' của tài liệu v1 phải là object")
    if not isinstance(periods, list):
        raise V1AdapterError("'periods' của tài liệu v1 phải là mảng")

    converter = _Converter()
    converter.defaults(defaults)
    for index, entry in enumerate(periods):
        if not isinstance(entry, dict):
            converter.skip(f"periods[{index}]", entry, "phần tử phải là object")
            continue
        converter.period_entry(index, entry)

    for key in raw:
        if key not in ("defaults", "periods"):
            converter.warnings.append(f"Bỏ qua key '{key}' của tài liệu v1")

    document = {"version": "2.0", "constraints": converter.constraints, "unsupported": []}
    return document, converter.warnings, converter.unsupported
