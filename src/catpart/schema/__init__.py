"""Versioned JSON schemas for the package's JSON outputs (Spec A #8).

The schemas ship as package data inside this subpackage; tests and the
fitness runner load them through :func:`load_schema` so every consumer
validates against the same committed file. Names are ``v1`` (the current
``catpart-inspect`` output, ticket #23; ``v0`` stays committed as the
contract for previously emitted reports), ``fitness-report-v0`` /
``fitness-history-row-v0`` (the two ``catpart-fitness`` artifacts,
ticket #14) and ``export-summary-v1`` (the ``catpart-export`` summary,
ticket #32).

Evolution rule: output changes are additive within a schema version —
consumers must ignore properties they do not know. That is why every
schema sets ``additionalProperties`` to ``true``: the detected-version
field arrived with the version-detection ticket (#13) while the schema
stayed v0, and the inspect fields of later Spec C tickets will arrive
while the schema stays v1. A breaking change — like v1 dropping v0's
whole-file ``container_names`` scan for the parsed table records —
bumps the version instead.
"""

from __future__ import annotations

import json
from importlib.resources import files

_SCHEMAS = files("catpart.schema")


def available_versions() -> tuple[str, ...]:
    """Schema names committed in this package (``"v0"``, ``"fitness-report-v0"``, ...)."""
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
