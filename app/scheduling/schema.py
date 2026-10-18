"""Pydantic models và validation của tài liệu ưu tiên v2 (design.md mục 3, 8).

Models được sinh từ `vocab.py`, nên đó là nguồn duy nhất của schema (R8).
`parse_document` validate theo từng ràng buộc: ràng buộc lỗi đi vào `unsupported`
kèm lý do, các ràng buộc khác vẫn dùng được (R7).
"""
import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Tuple, Type, Union

from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError, create_model
from typing_extensions import Annotated

from app.scheduling import vocab
from app.scheduling.v1_adapter import V1AdapterError, convert_v1, is_v1_document
from app.scheduling.vocab import AttributeSpec, ValueType

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

_SCALAR_TYPES: Dict[ValueType, Any] = {
    ValueType.TEXT: str,
    ValueType.INT: StrictInt,
    ValueType.INT_OR_TEXT: Union[StrictInt, str],
}

_TYPE_NAMES: Dict[ValueType, str] = {
    ValueType.TEXT: "chuỗi",
    ValueType.INT: "số nguyên",
    ValueType.INT_OR_TEXT: "số nguyên hoặc chuỗi",
}


def _range_model(bound_type: ValueType) -> Type[BaseModel]:
    scalar = _SCALAR_TYPES[bound_type]
    name = "IntRange" if bound_type is ValueType.INT else "TimeRange"
    return create_model(
        name,
        __config__=ConfigDict(extra="forbid", json_schema_extra={"minProperties": 1}),
        __doc__="Khoảng đóng; cần ít nhất một trong min, max.",
        min=(Optional[scalar], None),
        max=(Optional[scalar], None),
    )


_RANGE_MODELS: Dict[ValueType, Type[BaseModel]] = {
    bound_type: _range_model(bound_type)
    for bound_type in {spec.bound_type for spec in vocab.ATTRIBUTES.values() if spec.bound_type}
}


def _attribute_type(spec: AttributeSpec) -> Any:
    scalar = _SCALAR_TYPES[spec.value_type]
    values = Annotated[List[scalar], Field(min_length=1)]
    if spec.bound_type is None:
        return Union[scalar, values]
    return Union[scalar, values, _RANGE_MODELS[spec.bound_type]]


Filter: Type[BaseModel] = create_model(
    "Filter",
    __config__=ConfigDict(extra="forbid", json_schema_extra={"minProperties": 1}),
    __doc__="Bộ lọc: các key kết hợp AND, list là OR, {min, max} là khoảng đóng. Không được rỗng.",
    **{
        name: (Optional[_attribute_type(spec)], Field(None, description=spec.description))
        for name, spec in vocab.ATTRIBUTES.items()
    },
)

Bound = Annotated[StrictInt, Field(ge=0)]


class Constraint(BaseModel):
    """Một ràng buộc nguyên tử. Có đúng một trong prefer, avoid, limit."""

    model_config = ConfigDict(extra="forbid")

    prefer: Optional[Filter] = Field(None, description="Các lớp trong phạm vi nên thoả bộ lọc này.")
    avoid: Optional[Filter] = Field(None, description="Các lớp trong phạm vi nên tránh bộ lọc này.")
    limit: Optional[Literal[tuple(vocab.METRICS)]] = Field(
        None,
        description="Chỉ số hình dạng lịch cần giới hạn. "
        + " ".join(f"{m.name}: {m.description}" for m in vocab.METRICS.values()),
    )
    min: Optional[Bound] = Field(None, description="Cận dưới của limit, tính cả biên.")
    max: Optional[Bound] = Field(None, description="Cận trên của limit, tính cả biên.")
    scope: Optional[Filter] = Field(None, description="Ràng buộc áp dụng cho những lớp nào. Thiếu = mọi lớp.")
    level: Literal[vocab.LEVELS] = Field(vocab.DEFAULT_LEVEL, description="must: bắt buộc; high: rất quan trọng; normal: mặc định.")


class PreferenceDocument(BaseModel):
    """Tài liệu ưu tiên v2 do module LLM sinh."""

    model_config = ConfigDict(extra="forbid")

    version: str = Field(vocab.DEFAULT_VERSION, description="Phiên bản cấu trúc.")
    constraints: List[Constraint] = Field(description="Các ràng buộc; mỗi ý một ràng buộc.")
    unsupported: List[str] = Field(default_factory=list, description="Nguyên văn các ý không biểu diễn được.")


# ---------------------------------------------------------------------------
# Kết quả parse
# ---------------------------------------------------------------------------


class DocumentError(ValueError):
    """Lỗi của cả tài liệu (V9, V10, V11): API trả 400."""


@dataclass
class UnsupportedItem:
    index: Optional[int]  # vị trí trong `constraints`; None nếu không gắn với ràng buộc nào
    source: Any           # JSON gốc của ràng buộc, hoặc chuỗi LLM sinh
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {"index": self.index, "source": self.source, "reason": self.reason}


@dataclass
class ParsedConstraint:
    index: int
    constraint: Constraint
    source: Dict[str, Any]  # JSON gốc, trước khi bỏ key lạ

    @property
    def kind(self) -> str:
        if self.constraint.prefer is not None:
            return "prefer"
        if self.constraint.avoid is not None:
            return "avoid"
        return "limit"


@dataclass
class ParsedDocument:
    version: str
    constraints: List[ParsedConstraint] = field(default_factory=list)
    unsupported: List[UnsupportedItem] = field(default_factory=list)
    llm_unsupported: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

_CONSTRAINT_KEYS = frozenset(Constraint.model_fields)
_DOCUMENT_KEYS = frozenset(PreferenceDocument.model_fields)
_FILTER_FIELDS = ("prefer", "avoid", "scope")


class _ConstraintError(ValueError):
    pass


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _check_version(version: Any) -> str:
    if not isinstance(version, str):
        raise DocumentError("'version' phải là chuỗi, ví dụ \"2.0\"")
    major = version.strip().split(".")[0]
    if not major.isdigit() or int(major) != vocab.SUPPORTED_MAJOR_VERSION:
        raise DocumentError(f"Không hỗ trợ phiên bản '{version}', chỉ hỗ trợ {vocab.SUPPORTED_MAJOR_VERSION}.x")
    return version


def _check_range(where: str, spec: AttributeSpec, value: Dict[str, Any]) -> None:
    if spec.bound_type is None:
        raise _ConstraintError(f"Thuộc tính '{spec.name}' trong '{where}' không dùng được dạng khoảng {{min, max}}")
    extra = set(value) - {"min", "max"}
    if extra:
        raise _ConstraintError(f"Khoảng của '{spec.name}' trong '{where}' chỉ có key min, max; gặp {sorted(extra)}")
    if value.get("min") is None and value.get("max") is None:
        raise _ConstraintError(f"Khoảng của '{spec.name}' trong '{where}' cần ít nhất một trong min, max")
    low, high = value.get("min"), value.get("max")
    if _is_int(low) and _is_int(high) and low > high:
        raise _ConstraintError(f"Khoảng của '{spec.name}' trong '{where}' có min ({low}) lớn hơn max ({high})")


def _check_filter(where: str, value: Any) -> None:
    """V4, V5 và phần V6 cần lý do rõ hơn lỗi mặc định của Pydantic."""
    if not isinstance(value, dict):
        raise _ConstraintError(f"'{where}' phải là object (bộ lọc)")
    if not value:
        raise _ConstraintError(f"Bộ lọc '{where}' không được rỗng")
    for name, attr_value in value.items():
        spec = vocab.ATTRIBUTES.get(name)
        if spec is None:
            raise _ConstraintError(f"Thuộc tính '{name}' không có trong từ vựng")
        if isinstance(attr_value, dict):
            _check_range(where, spec, attr_value)
        elif isinstance(attr_value, list) and not attr_value:
            raise _ConstraintError(f"List của '{name}' trong '{where}' không được rỗng")


def _check_limit(raw: Dict[str, Any]) -> None:
    """V2."""
    metric_name = raw["limit"]
    metric = vocab.METRICS.get(metric_name) if isinstance(metric_name, str) else None
    if metric is None:
        raise _ConstraintError(f"Chỉ số '{metric_name}' không có trong từ vựng")
    bounds = {key: raw[key] for key in ("min", "max") if raw.get(key) is not None}
    if not bounds:
        raise _ConstraintError(f"'limit: {metric.name}' cần ít nhất một trong min, max")
    for key, bound in bounds.items():
        if not _is_int(bound) or bound < 0:
            raise _ConstraintError(f"'{key}' của limit phải là số nguyên ≥ 0, gặp {bound!r}")
        if key not in metric.allowed_bounds:
            raise _ConstraintError(f"Chỉ số '{metric.name}' không dùng cận '{key}'")
    if len(bounds) == 2 and bounds["min"] > bounds["max"]:
        raise _ConstraintError(f"min ({bounds['min']}) lớn hơn max ({bounds['max']})")


def _type_error_reason(error: Dict[str, Any]) -> str:
    loc = error["loc"]
    if len(loc) >= 2 and loc[0] in _FILTER_FIELDS and loc[1] in vocab.ATTRIBUTES:
        spec = vocab.ATTRIBUTES[loc[1]]
        expected = f"giá trị đơn ({_TYPE_NAMES[spec.value_type]}) hoặc list các giá trị đó"
        if spec.bound_type is not None:
            expected += f", hoặc khoảng {{min, max}} với cận là {_TYPE_NAMES[spec.bound_type]}"
        return f"Giá trị của '{loc[1]}' trong '{loc[0]}' sai kiểu: cần {expected}"
    path = ".".join(str(part) for part in loc)
    return f"Giá trị của '{path}' không hợp lệ: {error['msg']}"


def _parse_constraint(index: int, raw: Any, warnings: List[str]) -> Constraint:
    if not isinstance(raw, dict):
        raise _ConstraintError("Ràng buộc phải là object")

    # V8: key lạ ở cấp ràng buộc
    cleaned = {}
    for key, value in raw.items():
        if value is None:
            continue  # null không mang thông tin; coi như không có key
        if key in _CONSTRAINT_KEYS:
            cleaned[key] = value
        else:
            warnings.append(f"Ràng buộc {index}: bỏ qua key lạ '{key}'")

    # V1
    kinds = [kind for kind in vocab.KINDS if cleaned.get(kind) is not None]
    if len(kinds) != 1:
        found = ", ".join(kinds) if kinds else "không có"
        raise _ConstraintError(f"Cần đúng một trong prefer, avoid, limit (gặp: {found})")
    kind = kinds[0]

    # V3, V2
    if kind == "limit":
        _check_limit(cleaned)
    elif cleaned.get("min") is not None or cleaned.get("max") is not None:
        raise _ConstraintError("'min' / 'max' ở cấp ràng buộc chỉ đi với 'limit'")

    # V4, V5
    for where in _FILTER_FIELDS:
        if cleaned.get(where) is not None:
            _check_filter(where, cleaned[where])

    # V7
    level = cleaned.get("level")
    if level is not None and level not in vocab.LEVELS:
        raise _ConstraintError(f"'level' phải là một trong {', '.join(vocab.LEVELS)}, gặp {level!r}")

    # V6: kiểu giá trị
    try:
        return Constraint.model_validate(cleaned)
    except ValidationError as exc:
        raise _ConstraintError(_type_error_reason(exc.errors()[0])) from None


def parse_document(raw: Any) -> ParsedDocument:
    """Validate tài liệu ưu tiên v2.

    Lỗi của cả tài liệu (V9–V11) ném `DocumentError`. Lỗi của một ràng buộc
    (V1–V7) đưa ràng buộc đó vào `unsupported`. Key lạ (V8) bị bỏ, kèm warning.
    """
    if not isinstance(raw, dict):
        raise DocumentError("Tài liệu ưu tiên phải là object")

    warnings: List[str] = []
    adapter_unsupported: List[UnsupportedItem] = []

    # V10
    if is_v1_document(raw):
        try:
            raw, adapter_warnings, skipped = convert_v1(raw)
        except V1AdapterError as exc:
            raise DocumentError(str(exc)) from None
        warnings.append("Tài liệu đã được chuyển từ v1 sang v2")
        warnings.extend(adapter_warnings)
        adapter_unsupported = [UnsupportedItem(index=None, source=source, reason=reason) for source, reason in skipped]

    # V11
    version = _check_version(raw.get("version", vocab.DEFAULT_VERSION))

    # V9
    constraints = raw.get("constraints")
    if not isinstance(constraints, list):
        raise DocumentError("'constraints' thiếu hoặc không phải mảng")

    # V8: key lạ ở top-level
    for key in raw:
        if key not in _DOCUMENT_KEYS:
            warnings.append(f"Bỏ qua key lạ '{key}' ở cấp tài liệu")

    result = ParsedDocument(version=version, warnings=warnings)
    result.unsupported.extend(adapter_unsupported)

    llm_unsupported = raw.get("unsupported", [])
    if not isinstance(llm_unsupported, list):
        warnings.append("Bỏ qua 'unsupported' vì không phải mảng")
        llm_unsupported = []
    for item in llm_unsupported:
        if isinstance(item, str) and item.strip():
            result.llm_unsupported.append(item)
        else:
            warnings.append(f"Bỏ qua phần tử 'unsupported' không phải chuỗi: {item!r}")

    for index, raw_constraint in enumerate(constraints):
        source = copy.deepcopy(raw_constraint)
        try:
            constraint = _parse_constraint(index, raw_constraint, warnings)
        except _ConstraintError as exc:
            result.unsupported.append(UnsupportedItem(index=index, source=source, reason=str(exc)))
            continue
        result.constraints.append(ParsedConstraint(index=index, constraint=constraint, source=source))

    return result


def filter_items(model: Optional[BaseModel]) -> List[Tuple[str, Any]]:
    """Các cặp (thuộc tính, giá trị) có mặt trong một bộ lọc, theo thứ tự của vocab."""
    if model is None:
        return []
    return [
        (name, value.model_dump() if isinstance(value, BaseModel) else value)
        for name, value in model
        if value is not None
    ]


# ---------------------------------------------------------------------------
# Xuất JSON Schema (task T4, D15)
# ---------------------------------------------------------------------------

JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
SCHEMA_FILE = "schema.json"
INLINE_SCHEMA_FILE = "schema.inline.json"


def _drop_null_branches(node: Any) -> Any:
    """Bỏ nhánh `null` mà Pydantic sinh cho field Optional: field không bắt buộc thì cứ bỏ trống.

    Nhờ vậy schema không có `anyOf` ở cấp ràng buộc; `anyOf` chỉ còn ở giá trị của thuộc tính.
    """
    if isinstance(node, list):
        return [_drop_null_branches(item) for item in node]
    if not isinstance(node, dict):
        return node
    node = {key: _drop_null_branches(value) for key, value in node.items()}
    branches = node.get("anyOf")
    if isinstance(branches, list) and {"type": "null"} in branches:
        branches = [branch for branch in branches if branch != {"type": "null"}]
        del node["anyOf"]
        if node.get("default", ...) is None:
            del node["default"]
        if len(branches) == 1:
            node = {**branches[0], **node}
        else:
            node["anyOf"] = branches
    return node


def _inline_refs(node: Any, defs: Dict[str, Any]) -> Any:
    if isinstance(node, list):
        return [_inline_refs(item, defs) for item in node]
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        name = node["$ref"].rsplit("/", 1)[-1]
        rest = {key: value for key, value in node.items() if key != "$ref"}
        return {**_inline_refs(defs[name], defs), **_inline_refs(rest, defs)}
    return {key: _inline_refs(value, defs) for key, value in node.items() if key != "$defs"}


def build_json_schema(inline: bool = False) -> Dict[str, Any]:
    """JSON Schema của `PreferenceDocument`; `inline=True` cho bản không dùng `$ref`."""
    schema = _drop_null_branches(PreferenceDocument.model_json_schema())
    if inline:
        schema = _inline_refs(schema, schema.get("$defs", {}))
    return {"$schema": JSON_SCHEMA_DIALECT, **schema}


def dump_json_schema(inline: bool = False) -> str:
    import json

    return json.dumps(build_json_schema(inline), ensure_ascii=False, indent=2) + "\n"


def export_json_schema(out_dir: str) -> List[str]:
    """Ghi `schema.json` và `schema.inline.json` vào `out_dir`; trả về đường dẫn các file."""
    import os

    paths = []
    for name, inline in ((SCHEMA_FILE, False), (INLINE_SCHEMA_FILE, True)):
        path = os.path.join(out_dir, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(dump_json_schema(inline))
        paths.append(path)
    return paths


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Xuất JSON Schema của tài liệu ưu tiên v2.")
    parser.add_argument("--export", metavar="DIR", required=True, help="thư mục ghi schema.json và schema.inline.json")
    for written in export_json_schema(parser.parse_args().export):
        print(f"Đã ghi {written}")
