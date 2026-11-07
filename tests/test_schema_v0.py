"""The committed schema v0: loading, acceptance, and additive evolution.

The schema file is package data (src/catpart/schema/v0.json); these
tests pin its contract rather than its prose: what it accepts, what it
rejects, and that later tickets can add fields (ticket #13's detected
version) without a schema bump.
"""

from __future__ import annotations

import pytest

from catpart.schema import available_versions, load_schema
from catpart.schema.validate import ValidationError, validate

REPORT = {
    "schema_version": 0,
    "magic": "V5_CFV2",
    "header_dword": 65536,
    "file_size": 40983,
    "container_names": ["CATFeatCont", "CATProdCont"],
}


def test_v0_is_available_and_loads() -> None:
    assert "v0" in available_versions()
    schema = load_schema("v0")
    assert schema["type"] == "object"


def test_unknown_version_is_keyerror() -> None:
    with pytest.raises(KeyError):
        load_schema("v999")


def test_valid_report_accepts() -> None:
    validate(REPORT, load_schema("v0"))


def test_empty_container_names_allowed() -> None:
    validate({**REPORT, "container_names": []}, load_schema("v0"))


@pytest.mark.parametrize(
    "mutation",
    [
        lambda r: {**r, "schema_version": 1},
        lambda r: {**r, "magic": None},
        lambda r: {**r, "header_dword": "65536"},
        lambda r: {**r, "header_dword": True},
        lambda r: {**r, "header_dword": 4294967296},
        lambda r: {**r, "header_dword": -1},
        lambda r: {**r, "file_size": 40983.5},
        lambda r: {**r, "container_names": "CATFeatCont"},
        lambda r: {**r, "container_names": ["CATFeatCont", "CATFeatCont"]},
        lambda r: {k: v for k, v in r.items() if k != "container_names"},
        lambda r: {k: v for k, v in r.items() if k != "schema_version"},
    ],
)
def test_malformed_reports_rejected(mutation) -> None:
    with pytest.raises(ValidationError):
        validate(mutation(REPORT), load_schema("v0"))


def test_future_fields_accepted_additively() -> None:
    # Ticket #13 adds the detected version while the schema stays v0:
    # consumers (and this validator) must ignore unknown properties.
    future = {**REPORT, "version": "V5R21SP0HF0"}
    validate(future, load_schema("v0"))
