"""Shared test fixtures: synthetic CATIA V5-shaped files.

The byte-assembly primitives, the seeded deterministic front end and
the named corrupted variants live in ``tests/fixtures_gen.py`` (A2,
#12) — this module re-exports them for pytest so tests keep using the
``build_catpart``/``catpart_file`` fixtures. See fixtures_gen's
docstring for the structural facts exercised and the variant ->
classification mapping.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fixtures_gen import (  # noqa: F401 - re-exported for tests
    CORRUPTED_VARIANTS,
    KIND_RECORDS,
    MAGIC,
    VALID_VARIANTS,
    build_catpart,
    build_fixture,
    catia_identity_block,
    ceil8,
    container_record,
    registration_block,
)


@pytest.fixture(name="build_catpart")
def build_catpart_fixture():
    return build_catpart


@pytest.fixture(name="build_fixture")
def build_fixture_fixture():
    return build_fixture


@pytest.fixture(name="catpart_file")
def catpart_file_fixture(tmp_path: Path, build_catpart):
    """A valid-shaped synthetic .CATPart on disk."""
    path = tmp_path / "sample.CATPart"
    path.write_bytes(build_catpart())
    return path
