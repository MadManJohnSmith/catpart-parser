"""Unit tests for the Phase 7 B-rep construct vocabulary and census (Spec G #47, Ticket #48)."""

from __future__ import annotations

import csv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "docs" / "evidence" / "data"
VOCAB_CSV = DATA_DIR / "brep-construct-vocabulary.csv"
CLAIMS_CSV = DATA_DIR / "br1-brep-census-claims.csv"
EVIDENCE_MD = REPO_ROOT / "docs" / "evidence" / "2026-11-17-br1-brep-census.md"

EXPECTED_COLUMNS = [
    "construct_id",
    "family",
    "name",
    "carrier_container",
    "record_signature",
    "semantic_type",
    "status",
    "corpus_occurrences",
    "rate_l2_pass",
]

EXPECTED_TOPOLOGY = [
    "Solid/Body",
    "Lump",
    "Shell",
    "Face",
    "Loop",
    "Edge",
    "Vertex",
]

EXPECTED_CURVES = [
    "Line/Segment",
    "Circle/Arc",
    "Ellipse",
    "Parabola",
    "Hyperbola",
    "NURBS/BSpline Curve",
    "Polyline",
    "Trimmed Curve",
]

EXPECTED_SURFACES = [
    "Plane",
    "Cylindrical Surface",
    "Conical Surface",
    "Spherical Surface",
    "Toroidal Surface",
    "Surface of Revolution",
    "Extruded Surface",
    "NURBS/BSpline Surface",
]

VALID_SEMANTIC_TYPES = {"analytic", "nurbs", "topology", "attribute"}
VALID_STATUSES = {"candidate", "frozen"}
VALID_FAMILIES = {"topology", "curve", "surface", "attribute"}


def test_brep_vocabulary_file_exists() -> None:
    assert VOCAB_CSV.is_file(), f"Missing {VOCAB_CSV}"


def test_brep_vocabulary_schema_and_columns() -> None:
    with open(VOCAB_CSV, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        assert header == EXPECTED_COLUMNS, f"Header mismatch: got {header}, expected {EXPECTED_COLUMNS}"


def test_brep_vocabulary_all_candidate_classes_present() -> None:
    with open(VOCAB_CSV, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    names_by_family: dict[str, list[str]] = {
        "topology": [],
        "curve": [],
        "surface": [],
        "attribute": [],
    }

    for row in rows:
        fam = row["family"]
        assert fam in VALID_FAMILIES, f"Invalid family {fam} in row {row}"
        names_by_family[fam].append(row["name"])

        # Check semantic types and statuses
        assert row["semantic_type"] in VALID_SEMANTIC_TYPES, f"Invalid semantic_type in {row}"
        assert row["status"] in VALID_STATUSES, f"Invalid status in {row}"

        # Numeric checks
        occurrences = int(row["corpus_occurrences"])
        assert occurrences >= 0, f"Occurrences must be non-negative: {occurrences}"

        rate = float(row["rate_l2_pass"])
        assert 0.0 <= rate <= 1.0, f"rate_l2_pass must be in [0, 1]: {rate}"

    # Verify all expected classes
    for name in EXPECTED_TOPOLOGY:
        assert name in names_by_family["topology"], f"Missing topology construct: {name}"

    for name in EXPECTED_CURVES:
        assert name in names_by_family["curve"], f"Missing curve construct: {name}"

    for name in EXPECTED_SURFACES:
        assert name in names_by_family["surface"], f"Missing surface construct: {name}"

    # Verify frozen denominator count is exactly 23
    frozen_rows = [r for r in rows if r["status"] == "frozen"]
    assert len(frozen_rows) == 23, f"Expected exactly 23 frozen constructs, got {len(frozen_rows)}"


def test_br1_census_claims_csv_valid() -> None:
    assert CLAIMS_CSV.is_file(), f"Missing {CLAIMS_CSV}"
    with open(CLAIMS_CSV, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        assert len(header) == 5
        rows = list(reader)
        assert len(rows) >= 5
        for row in rows:
            assert len(row) == len(header)
            assert row[0].startswith("BR1-")


def test_br1_evidence_document_exists_and_references_artifacts() -> None:
    assert EVIDENCE_MD.is_file(), f"Missing {EVIDENCE_MD}"
    content = EVIDENCE_MD.read_text(encoding="utf-8")
    assert "brep-construct-vocabulary.csv" in content
    assert "Spec G" in content
    assert "L3 Fitness" in content
    assert "23" in content
    assert "TOP-01" in content
    assert "CRV-01" in content
    assert "SRF-01" in content
