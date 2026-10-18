"""Snapshot JSON Schema (task T4): schema xuất từ models phải trùng file đã commit.

Đổi models mà quên xuất lại thì test này đỏ. Xuất lại bằng:
    python -m app.scheduling.schema --export docs/specs/json_v2/
"""
import json
from pathlib import Path

import pytest

from app.scheduling.schema import INLINE_SCHEMA_FILE, SCHEMA_FILE, build_json_schema, dump_json_schema

SPEC_DIR = Path(__file__).resolve().parents[2] / "docs" / "specs" / "json_v2"


@pytest.mark.parametrize("name, inline", [(SCHEMA_FILE, False), (INLINE_SCHEMA_FILE, True)])
def test_schema_snapshot(name, inline):
    committed = (SPEC_DIR / name).read_text(encoding="utf-8")
    assert dump_json_schema(inline) == committed, f"{name} đã cũ, hãy xuất lại schema"


def _walk(node, path=()):
    yield path, node
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _walk(value, path + (key,))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from _walk(value, path + (i,))


def test_no_union_at_constraint_level():
    constraint = build_json_schema()["$defs"]["Constraint"]
    assert "oneOf" not in constraint and "anyOf" not in constraint
    for name, prop in constraint["properties"].items():
        assert "oneOf" not in prop and "anyOf" not in prop, name


def test_no_null_branches():
    for path, node in _walk(build_json_schema()):
        assert node != {"type": "null"}, path


def test_inline_schema_has_no_refs():
    schema = build_json_schema(inline=True)
    assert "$defs" not in schema
    assert '"$ref"' not in json.dumps(schema)
