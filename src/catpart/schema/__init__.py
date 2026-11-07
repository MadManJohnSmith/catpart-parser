"""Versioned JSON schemas for the CLI's output (Spec A #8).

The schemas ship as package data inside this subpackage; tests and the
fitness runner load them through :func:`load_schema` so every consumer
validates against the same committed file.

Evolution rule: output changes are additive within a schema version —
consumers must ignore properties they do not know. That is why schema
v0 sets ``additionalProperties`` to ``true``: the detected-version field
arrives with the version-detection ticket (#13) while the schema stays
v0.
"""

from __future__ import annotations

import json
from importlib.resources import files

_SCHEMAS = files("catpart.schema")


def available_versions() -> tuple[str, ...]:
    """Schema versions committed in this package (e.g. ``("v0",)``)."""
    return tuple(
        sorted(
            entry.name.removesuffix(".json")
            for entry in _SCHEMAS.iterdir()
            if entry.name.endswith(".json")
        )
    )


def load_schema(version: str = "v0") -> dict:
    """Return the committed JSON schema for ``version`` (e.g. ``"v0"``).

    Raises :class:`KeyError` for a version this package does not carry.
    """
    resource = _SCHEMAS / f"{version}.json"
    if not resource.is_file():
        raise KeyError(
            f"unknown schema version {version!r}; available: "
            + ", ".join(available_versions())
        )
    return json.loads(resource.read_text(encoding="utf-8"))
