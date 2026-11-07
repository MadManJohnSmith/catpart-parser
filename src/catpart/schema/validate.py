"""Minimal, fail-closed validator for the JSON Schema subset this project uses.

The package core is stdlib-only (ADR-0002), so the schema contract cannot
depend on the third-party ``jsonschema`` package. This module implements
exactly the keywords the committed schemas use, and **rejects schemas
containing any other checking keyword** — a schema can never silently
pass unvalidated. If a future schema needs more than this subset, extend
the validator in the same commit as the schema change.

Supported checking keywords: ``type``, ``const``, ``enum``, ``required``,
``properties``, ``additionalProperties``, ``items`` (schema form only),
``minItems``, ``maxItems``, ``uniqueItems``, ``minimum``, ``maximum``,
``minLength``, ``maxLength``, ``pattern``. Annotation keywords
(``$schema``, ``$id``, ``$comment``, ``title``, ``description``,
``default``, ``examples``) are ignored.
"""

from __future__ import annotations

import re

_ANNOTATIONS = frozenset(
    {"$schema", "$id", "$comment", "title", "description", "default", "examples"}
)

_CHECKING_KEYWORDS = frozenset(
    {
        "type",
        "const",
        "enum",
        "required",
        "properties",
        "additionalProperties",
        "items",
        "minItems",
        "maxItems",
        "uniqueItems",
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
        "pattern",
    }
)

_TYPES = frozenset(
    {"object", "array", "string", "integer", "number", "boolean", "null"}
)


class SchemaError(Exception):
    """The schema itself is invalid or uses unsupported keywords."""


class ValidationError(Exception):
    """The instance does not satisfy the schema."""


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _check_type(value: object, types: object, where: str) -> None:
    if isinstance(types, str):
        names = [types]
    elif isinstance(types, list) and all(isinstance(name, str) for name in types):
        names = list(types)
    else:
        raise SchemaError(f"{where}: unsupported 'type' keyword: {types!r}")
    if not names or any(name not in _TYPES for name in names):
        raise SchemaError(f"{where}: unsupported 'type' keyword: {types!r}")
    checks = {
        "object": lambda v: isinstance(v, dict),
        "array": lambda v: isinstance(v, list),
        "string": lambda v: isinstance(v, str),
        "boolean": lambda v: isinstance(v, bool),
        "null": lambda v: v is None,
        "integer": _is_integer,
        "number": _is_number,
    }
    if not any(checks[name](value) for name in names):
        raise ValidationError(
            f"{where}: expected type {'/'.join(names)}, got {type(value).__name__}"
        )


def validate(instance: object, schema: object, where: str = "$") -> None:
    """Validate ``instance`` against ``schema``.

    Raises :class:`SchemaError` when the schema uses unsupported or
    malformed keywords, :class:`ValidationError` when the instance
    violates the schema. ``where`` is the JSON Pointer of the current
    position, used in error messages.
    """
    if not isinstance(schema, dict):
        raise SchemaError(f"{where}: schema must be an object")
    unsupported = sorted(set(schema) - _ANNOTATIONS - _CHECKING_KEYWORDS)
    if unsupported:
        raise SchemaError(
            f"{where}: unsupported schema keywords: {', '.join(unsupported)}"
        )

    if "type" in schema:
        _check_type(instance, schema["type"], where)

    if "const" in schema and instance != schema["const"]:
        raise ValidationError(f"{where}: expected {schema['const']!r}, got {instance!r}")
    if "enum" in schema:
        if not isinstance(schema["enum"], list):
            raise SchemaError(f"{where}: 'enum' keyword must be an array")
        if instance not in schema["enum"]:
            raise ValidationError(
                f"{where}: {instance!r} is not one of {schema['enum']!r}"
            )

    if isinstance(instance, dict):
        _validate_object(instance, schema, where)
    if isinstance(instance, list):
        _validate_array(instance, schema, where)
    if isinstance(instance, str):
        _validate_string(instance, schema, where)
    if _is_number(instance):
        _validate_number(instance, schema, where)


def _validate_object(instance: dict, schema: dict, where: str) -> None:
    required = schema.get("required", [])
    if not isinstance(required, list) or any(not isinstance(name, str) for name in required):
        raise SchemaError(f"{where}: 'required' keyword must be an array of strings")
    for name in required:
        if name not in instance:
            raise ValidationError(f"{where}: missing required property {name!r}")

    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        raise SchemaError(f"{where}: 'properties' keyword must be an object")
    for name, sub_schema in properties.items():
        if name in instance:
            validate(instance[name], sub_schema, f"{where}.{name}")

    additional = schema.get("additionalProperties", True)
    if additional is False:
        extra = sorted(set(instance) - set(properties))
        if extra:
            raise ValidationError(f"{where}: unexpected properties: {', '.join(extra)}")
    elif additional is not True:
        for name in instance:
            if name not in properties:
                validate(instance[name], additional, f"{where}.{name}")


def _validate_array(instance: list, schema: dict, where: str) -> None:
    if "items" in schema:
        items = schema["items"]
        if not isinstance(items, dict):
            raise SchemaError(f"{where}: only the schema form of 'items' is supported")
        for index, item in enumerate(instance):
            validate(item, items, f"{where}[{index}]")
    for key in ("minItems", "maxItems"):
        if key in schema and not _is_integer(schema[key]):
            raise SchemaError(f"{where}: {key!r} keyword must be an integer")
    if "minItems" in schema and len(instance) < schema["minItems"]:
        raise ValidationError(
            f"{where}: array has {len(instance)} items, minimum {schema['minItems']}"
        )
    if "maxItems" in schema and len(instance) > schema["maxItems"]:
        raise ValidationError(
            f"{where}: array has {len(instance)} items, maximum {schema['maxItems']}"
        )
    if schema.get("uniqueItems"):
        for index, item in enumerate(instance):
            if item in instance[:index]:
                raise ValidationError(f"{where}: duplicate item at index {index}")


def _validate_string(instance: str, schema: dict, where: str) -> None:
    for key in ("minLength", "maxLength"):
        if key in schema and not _is_integer(schema[key]):
            raise SchemaError(f"{where}: {key!r} keyword must be an integer")
    if "minLength" in schema and len(instance) < schema["minLength"]:
        raise ValidationError(
            f"{where}: string shorter than minLength {schema['minLength']}"
        )
    if "maxLength" in schema and len(instance) > schema["maxLength"]:
        raise ValidationError(
            f"{where}: string longer than maxLength {schema['maxLength']}"
        )
    if "pattern" in schema:
        pattern = schema["pattern"]
        if not isinstance(pattern, str):
            raise SchemaError(f"{where}: 'pattern' keyword must be a string")
        try:
            matcher = re.compile(pattern)
        except re.error as exc:
            raise SchemaError(f"{where}: invalid 'pattern' keyword: {exc}") from exc
        if matcher.search(instance) is None:
            raise ValidationError(
                f"{where}: {instance!r} does not match pattern {pattern!r}"
            )


def _validate_number(instance: float, schema: dict, where: str) -> None:
    for key in ("minimum", "maximum"):
        if key in schema and not _is_number(schema[key]):
            raise SchemaError(f"{where}: {key!r} keyword must be a number")
    if "minimum" in schema and instance < schema["minimum"]:
        raise ValidationError(
            f"{where}: {instance} is below minimum {schema['minimum']}"
        )
    if "maximum" in schema and instance > schema["maximum"]:
        raise ValidationError(
            f"{where}: {instance} is above maximum {schema['maximum']}"
        )
