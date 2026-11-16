"""Test suite for synthetic multi-file assembly fixtures (Phase 6, Spec F #45 §9.1).

Design Authority: `docs/specs/phase6-assembly-viewer-spec.md` (§9.1).
Prior Fixture Generator: `tests/fixtures_gen.py` (Phase 5 A2 fixture discipline).
Declared P4 Assembly Bar: `docs/evidence/2026-11-14-p4-assembly-bar.md`.

Tests:
1. `fixture_assembly_canonical`: 1 root `.CATProduct` + 3 `.CATPart` files (`Base`, `Arm`, `Bolt`).
   Exercises `Resolved & Placed` with known non-zero translation ([10.0, 20.0, 30.0]) and 90-degree rotation.
2. `fixture_assembly_identity`: 1 root `.CATProduct` with no `_Position` tokens + 2 `.CATPart` files (`Plate`, `Cover`).
   Exercises `Resolved & Identity`.
3. `fixture_assembly_partial`: 1 root `.CATProduct` declaring 4 parts (`Housing`, `Gear`, `Shaft`, `Pin`),
   but user supplies only 2 `.CATPart` files (`Housing`, `Gear`).
   Exercises `Unresolved Part` (verifies nodes are rendered in tree with warning badge, never omitted).
4. `fixture_assembly_undecodable`: 1 root `.CATProduct` carrying legacy undecodable placement tags.
   Exercises `Undecodable Placement` (verifies anti-masking invariant: rejected from identity fallback).
5. All 4 canonical classification states are distinctly produced.
6. Packaging utilities (`package_to_zip`, `write_to_directory`) produce valid archives and folders.
7. Seeded determinism: same seed -> byte-identical output.
"""

from __future__ import annotations

import io
import math
import zipfile
from pathlib import Path

from catpart.containers import detect_kind, parse_container_table
from catpart.fixtures_assembly import (
    MAGIC,
    TRAILER_MARKER,
    classify_assembly,
    fixture_assembly_canonical,
    fixture_assembly_identity,
    fixture_assembly_partial,
    fixture_assembly_undecodable,
    package_to_zip,
    read_product_structure,
    write_to_directory,
)
from catpart.geometry import build_export
from catpart.header import parse_header
from catpart.identity import parse_document_name
from catpart.trailer import parse_trailer
from catpart.version import detect_version


def _assert_valid_catia_container(data: bytes, expected_kind: str, expected_doc_name: str | None = None) -> None:
    """Assert file has genuine CATIA V5 container structure (magic, header, trailer, container table)."""
    assert data[:8] == MAGIC, "magic must be V5_CFV2\\0"
    assert data.endswith(TRAILER_MARKER), "file must end with CB__END\\0"

    h = parse_header(data)
    assert h.magic == "V5_CFV2"

    t = parse_trailer(data)
    assert t is not None, "trailer must parse cleanly"

    v = detect_version(data)
    assert v != "unknown", "version marker should be detected"

    tbl = parse_container_table(data)
    assert len(tbl) >= 1, "container table must have at least one record"
    kind = detect_kind(tbl)
    assert kind == expected_kind, f"expected kind {expected_kind}, got {kind}"

    if expected_doc_name is not None:
        doc_name = parse_document_name(data)
        assert doc_name == expected_doc_name, f"expected document_name {expected_doc_name}, got {doc_name}"


# --- 1. fixture_assembly_canonical -------------------------------------------


def test_fixture_assembly_canonical_valid_bytes(tmp_path: Path) -> None:
    """Canonical fixture: 1 root .CATProduct + 3 .CATPart files generate genuine, valid bytes."""
    fixture = fixture_assembly_canonical(seed=42)

    assert fixture.name == "fixture_assembly_canonical"
    assert fixture.product_filename == "CanonicalAssembly.CATProduct"
    assert len(fixture.part_files) == 3
    assert set(fixture.part_files.keys()) == {"Base.CATPart", "Arm.CATPart", "Bolt.CATPart"}

    # Root .CATProduct validity
    _assert_valid_catia_container(fixture.product_bytes, "product", "CanonicalAssembly")

    # Component .CATPart validity and geometry export
    for filename, part_bytes in fixture.part_files.items():
        stem = filename.rsplit(".", 1)[0]
        _assert_valid_catia_container(part_bytes, "part", stem)

        part_path = tmp_path / filename
        ply_path = tmp_path / f"{stem}.ply"
        part_path.write_bytes(part_bytes)

        summary = build_export(part_path, ply_path)
        assert summary["triangle_count"] == 12, "box part should export 12 triangles"
        assert summary["mesh"]["manifold"] is True, "box mesh should be a closed manifold"
        assert summary["mesh"]["closed"] is True


def test_fixture_assembly_canonical_inspection_and_placement() -> None:
    """Canonical fixture: product structure parser extracts 3 instances with known transform on Arm."""
    fixture = fixture_assembly_canonical(seed=42)
    doc = read_product_structure(fixture.product_bytes)

    assert doc["schema_version"] == 1
    assert doc["product_name"] == "CanonicalAssembly"
    assert doc["pool_form"] == "framed"
    assert doc["total_instances"] == 3
    assert doc["placed_instances"] == 3
    assert doc["identity_instances"] == 0

    instances = doc["instances"]
    assert len(instances) == 3

    inst_map = {inst["instance_name"]: inst for inst in instances}
    assert "Base.1" in inst_map
    assert "Arm.1" in inst_map
    assert "Bolt.1" in inst_map

    # Check Arm.1 known non-zero translation ([10.0, 20.0, 30.0]) and 90-degree rotation
    arm = inst_map["Arm.1"]
    assert arm["part_number"] == "Arm"
    assert arm["has_position_attr"] is True
    assert arm["placement_status"] == "placed"
    assert arm["transform"] is not None

    t = arm["transform"][:3]
    q = arm["transform"][3:]

    assert [round(x, 4) for x in t] == [10.0, 20.0, 30.0]

    # 90-degree rotation around Z axis: qw = cos(pi/4), qz = sin(pi/4)
    expected_qw = math.cos(math.pi / 4.0)
    expected_qz = math.sin(math.pi / 4.0)
    assert abs(q[0] - expected_qw) < 1e-6
    assert abs(q[1] - 0.0) < 1e-6
    assert abs(q[2] - 0.0) < 1e-6
    assert abs(q[3] - expected_qz) < 1e-6

    # Unit quaternion norm
    norm2 = sum(x * x for x in q)
    assert abs(norm2 - 1.0) < 1e-9

    # Classifications against uploaded files
    classifications = classify_assembly(doc, fixture.part_files)
    assert classifications == {
        "Base.1": "placed",
        "Arm.1": "placed",
        "Bolt.1": "placed",
    }
    assert classifications == fixture.expected_classifications


# --- 2. fixture_assembly_identity --------------------------------------------


def test_fixture_assembly_identity_valid_bytes() -> None:
    """Identity fixture: 1 root .CATProduct with no _Position tokens + 2 .CATPart files generate valid bytes."""
    fixture = fixture_assembly_identity(seed=42)

    assert fixture.name == "fixture_assembly_identity"
    assert fixture.product_filename == "IdentityAssembly.CATProduct"
    assert set(fixture.part_files.keys()) == {"Plate.CATPart", "Cover.CATPart"}

    _assert_valid_catia_container(fixture.product_bytes, "product", "IdentityAssembly")
    for filename, part_bytes in fixture.part_files.items():
        _assert_valid_catia_container(part_bytes, "part", filename.rsplit(".", 1)[0])


def test_fixture_assembly_identity_inspection_and_placement() -> None:
    """Identity fixture: exercises Resolved & Identity when _Position tokens are absent from pool."""
    fixture = fixture_assembly_identity(seed=42)
    doc = read_product_structure(fixture.product_bytes)

    assert doc["pool_form"] == "framed"
    assert doc["product_name"] == "IdentityAssembly"
    assert doc["total_instances"] == 2
    assert doc["placed_instances"] == 0
    assert doc["identity_instances"] == 2

    for inst in doc["instances"]:
        assert inst["has_position_attr"] is False, "identity fixture must have no _Position attribute"
        assert inst["placement_status"] == "identity"

    classifications = classify_assembly(doc, fixture.part_files)
    assert classifications == {
        "Plate.1": "identity",
        "Cover.1": "identity",
    }
    assert classifications == fixture.expected_classifications


# --- 3. fixture_assembly_partial ---------------------------------------------


def test_fixture_assembly_partial_valid_bytes() -> None:
    """Partial fixture: 1 root .CATProduct declaring 4 parts, user supplies only 2 .CATPart files."""
    fixture = fixture_assembly_partial(seed=42)

    assert fixture.name == "fixture_assembly_partial"
    assert fixture.product_filename == "PartialAssembly.CATProduct"
    # User supplies only Housing and Gear
    assert set(fixture.part_files.keys()) == {"Housing.CATPart", "Gear.CATPart"}
    assert "Shaft.CATPart" not in fixture.part_files
    assert "Pin.CATPart" not in fixture.part_files

    _assert_valid_catia_container(fixture.product_bytes, "product", "PartialAssembly")
    for filename, part_bytes in fixture.part_files.items():
        _assert_valid_catia_container(part_bytes, "part", filename.rsplit(".", 1)[0])


def test_fixture_assembly_partial_unresolved_parts() -> None:
    """Partial fixture: exercises Unresolved Part (verifies nodes are rendered in tree with warning badge, never omitted)."""
    fixture = fixture_assembly_partial(seed=42)
    doc = read_product_structure(fixture.product_bytes)

    assert doc["total_instances"] == 4
    inst_names = [inst["instance_name"] for inst in doc["instances"]]
    assert inst_names == ["Housing.1", "Gear.1", "Shaft.1", "Pin.1"]

    classifications = classify_assembly(doc, fixture.part_files)
    assert classifications == {
        "Housing.1": "placed",
        "Gear.1": "placed",
        "Shaft.1": "unresolved",
        "Pin.1": "unresolved",
    }
    assert classifications == fixture.expected_classifications

    # Critical invariant: Shaft and Pin are classified as 'unresolved', NEVER omitted
    assert "Shaft.1" in classifications
    assert "Pin.1" in classifications
    assert classifications["Shaft.1"] == "unresolved"
    assert classifications["Pin.1"] == "unresolved"


# --- 4. fixture_assembly_undecodable -----------------------------------------


def test_fixture_assembly_undecodable_valid_bytes() -> None:
    """Undecodable fixture: 1 root .CATProduct carrying legacy reference tags + 1 component part."""
    fixture = fixture_assembly_undecodable(seed=42)

    assert fixture.name == "fixture_assembly_undecodable"
    assert fixture.product_filename == "UndecodableAssembly.CATProduct"
    assert set(fixture.part_files.keys()) == {"Bracket.CATPart"}

    _assert_valid_catia_container(fixture.product_bytes, "product")
    for filename, part_bytes in fixture.part_files.items():
        _assert_valid_catia_container(part_bytes, "part", filename.rsplit(".", 1)[0])


def test_fixture_assembly_undecodable_anti_masking_invariant() -> None:
    """Undecodable fixture: exercises Undecodable Placement (anti-masking invariant: rejected from identity fallback)."""
    fixture = fixture_assembly_undecodable(seed=42)
    doc = read_product_structure(fixture.product_bytes)

    assert doc["pool_form"] == "r15-ref"
    assert any(w["class"] == "r15-legacy-reference-form" for w in doc["warnings"])

    classifications = classify_assembly(doc, fixture.part_files)
    assert "Bracket.1" in classifications
    assert classifications["Bracket.1"] == "undecodable"
    assert classifications == fixture.expected_classifications

    # Anti-masking check: MUST NOT default to identity!
    assert classifications["Bracket.1"] != "identity", "undecodable placement must never be masked to identity"


# --- 5. All 4 Classification States Distinct ---------------------------------


def test_all_four_classification_states_distinct() -> None:
    """Verify that across the 4 fixtures, all 4 canonical states are distinctly produced."""
    f_canonical = fixture_assembly_canonical()
    f_identity = fixture_assembly_identity()
    f_partial = fixture_assembly_partial()
    f_undecodable = fixture_assembly_undecodable()

    c_canonical = classify_assembly(read_product_structure(f_canonical.product_bytes), f_canonical.part_files)
    c_identity = classify_assembly(read_product_structure(f_identity.product_bytes), f_identity.part_files)
    c_partial = classify_assembly(read_product_structure(f_partial.product_bytes), f_partial.part_files)
    c_undecodable = classify_assembly(read_product_structure(f_undecodable.product_bytes), f_undecodable.part_files)

    all_states = set(c_canonical.values()) | set(c_identity.values()) | set(c_partial.values()) | set(c_undecodable.values())
    expected_states = {"placed", "identity", "unresolved", "undecodable"}

    assert all_states == expected_states, f"expected states {expected_states}, got {all_states}"


# --- 6. Packaging Utilities --------------------------------------------------


def test_packaging_to_zip(tmp_path: Path) -> None:
    """Test packaging fixtures into a .zip archive bytes and file."""
    fixture = fixture_assembly_canonical()

    # In-memory packaging
    zip_bytes = package_to_zip(fixture)
    assert len(zip_bytes) > 0

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = set(zf.namelist())
        expected_names = {fixture.product_filename, *fixture.part_files.keys()}
        assert names == expected_names
        for name in names:
            extracted = zf.read(name)
            assert extracted == fixture.files[name], f"zip content mismatch for {name}"

    # On-disk packaging
    out_zip = tmp_path / "canonical.zip"
    written_bytes = package_to_zip(fixture, out_path=out_zip)
    assert out_zip.exists()
    assert out_zip.read_bytes() == written_bytes


def test_packaging_write_to_directory(tmp_path: Path) -> None:
    """Test writing fixtures to a directory structure on disk."""
    fixture = fixture_assembly_canonical()
    dir_path = tmp_path / "assembly_output"

    out_dir = write_to_directory(fixture, dir_path)
    assert out_dir == dir_path.resolve()
    assert out_dir.is_dir()

    for name, expected_content in fixture.files.items():
        file_path = out_dir / name
        assert file_path.exists(), f"missing file {name} in directory"
        assert file_path.read_bytes() == expected_content, f"content mismatch in {name}"


# --- 7. Seeded Determinism ---------------------------------------------------


def test_fixture_determinism() -> None:
    """Test that same seed produces identical bytes across all fixtures."""
    for fn in (
        fixture_assembly_canonical,
        fixture_assembly_identity,
        fixture_assembly_partial,
        fixture_assembly_undecodable,
    ):
        f1 = fn(seed=123)
        f2 = fn(seed=123)
        assert f1.product_bytes == f2.product_bytes
        for k in f1.part_files:
            assert f1.part_files[k] == f2.part_files[k]
