"""Contract of ``catpart.schema.validate`` — the stdlib-only validator.

The fitness runner (ticket #14) classifies parses by this validator's
verdict, so its behavior is a public interface, pinned here: fail-closed
on unsupported schema keywords, JSON-Schema typing rules (bool is not
integer), and annotation keywords ignored.
"""

from __future__ import annotations

import pytest

from catpart.schema.validate import SchemaError, ValidationError, validate


def ok(instance, schema) -> None:
    validate(instance, schema)  # must not raise


def bad(instance, schema) -> None:
    with pytest.raises(ValidationError):
        validate(instance, schema)


def test_type_rules() -> None:
    ok({"a": 1}, {"type": "object"})
    ok([1, 2], {"type": "array"})
    ok("x", {"type": "string"})
    ok(True, {"type": "boolean"})
    ok(None, {"type": "null"})
    ok(3, {"type": "integer"})
    ok(3.5, {"type": "number"})
    ok(3, {"type": "number"})
    bad(True, {"type": "integer"})  # bool is not an integer in JSON Schema
    bad(True, {"type": "number"})
    bad(3.5, {"type": "integer"})
    bad("3", {"type": "integer"})
    bad(None, {"type": "string"})
    ok(1, {"type": ["integer", "null"]})
    bad("1", {"type": ["integer", "null"]})


def test_type_keyword_with_unknown_type_is_schema_error() -> None:
    with pytest.raises(SchemaError):
        validate(1, {"type": "integer8"})


def test_const_and_enum() -> None:
    ok(0, {"const": 0})
    bad(1, {"const": 0})
    ok("a", {"enum": ["a", "b"]})
    bad("c", {"enum": ["a", "b"]})
    with pytest.raises(SchemaError):
        validate("a", {"enum": "ab"})


def test_object_keywords() -> None:
    schema = {
        "type": "object",
        "required": ["a"],
        "properties": {"a": {"type": "integer"}, "b": {"type": "string"}},
        "additionalProperties": False,
    }
    ok({"a": 1}, schema)
    ok({"a": 1, "b": "x"}, schema)
    bad({"b": "x"}, schema)  # missing required a
    bad({"a": "x"}, schema)  # wrong type at $.a
    bad({"a": 1, "c": 2}, schema)  # additionalProperties false
    ok({"a": 1, "c": 2}, {**schema, "additionalProperties": True})
    bad({"a": True}, schema)  # bool is not integer, also at sublevel


def test_array_keywords() -> None:
    schema = {
        "type": "array",
        "items": {"type": "string"},
        "minItems": 1,
        "maxItems": 2,
        "uniqueItems": True,
    }
    ok(["a"], schema)
    ok(["a", "b"], schema)
    bad([], schema)
    bad(["a", "b", "c"], schema)
    bad(["a", 1], schema)
    bad(["a", "a"], schema)


def test_number_and_string_bounds() -> None:
    ok(5, {"minimum": 0, "maximum": 10})
    bad(-1, {"minimum": 0})
    bad(11, {"maximum": 10})
    ok("abc", {"minLength": 1, "maxLength": 5})
    bad("", {"minLength": 1})
    bad("abcdef", {"maxLength": 5})
    ok("hello", {"pattern": "^h"})
    bad("hello", {"pattern": "^x"})


def test_annotations_are_ignored() -> None:
    ok(
        {"a": 1},
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://example.com/s.json",
            "$comment": "note",
            "title": "T",
            "description": "D",
            "default": {"a": 0},
            "examples": [{"a": 1}],
            "type": "object",
        },
    )


def test_unknown_checking_keyword_fails_closed() -> None:
    with pytest.raises(SchemaError):
        validate({"a": 1}, {"properties": {"a": {"exclusiveMinimum": 0}}})


def test_nested_error_paths() -> None:
    schema = {
        "type": "object",
        "properties": {"names": {"type": "array", "items": {"type": "string"}}},
    }
    with pytest.raises(ValidationError) as excinfo:
        validate({"names": ["ok", 7]}, schema)
    assert "$.names[1]" in str(excinfo.value)


def test_malformed_schema_keywords_fail_closed() -> None:
    with pytest.raises(SchemaError):
        validate([], {"items": [1, 2]})  # tuple form unsupported
    with pytest.raises(SchemaError):
        validate({}, {"required": "a"})
    with pytest.raises(SchemaError):
        validate({}, {"properties": ["a"]})
    with pytest.raises(SchemaError):
        validate("x", {"pattern": "["})
    with pytest.raises(SchemaError):
        validate(1, {"minimum": "0"})
    with pytest.raises(SchemaError):
        validate("x", {"minLength": "1"})
    with pytest.raises(SchemaError):
        validate([], {"minItems": "1"})
    with pytest.raises(SchemaError):
        validate(1, [1, 2])  # schema must be an object
