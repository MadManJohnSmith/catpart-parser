"""Seam 1, slice by slice: the schema-v1 fields of ``catpart-inspect``.

C1 moves the inspect output from v0 to v1. Each test here pins one part
of the v1 contract through :func:`catpart.cli.build_inspect_report` (the
in-process seam the fitness runner consumes) on synthetic fixtures built
by :mod:`conftest`; the CLI wrapper tests stay in
``test_cli_inspect.py``. Every emitted report must validate against the
committed schema v1.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from catpart.schema import load_schema
from catpart.schema.validate import ValidationError, validate


def inspect_report(build_catpart, tmp_path: Path, capsys, **kwargs) -> dict:
    """Build one fixture file, run the inspect seam, return its JSON."""
    from catpart.cli import main_inspect

    path = tmp_path / "sample.CATPart"
    path.write_bytes(build_catpart(**kwargs))
    code = main_inspect([str(path)])
    captured = capsys.readouterr()
    assert code == 0, captured.err
    report = json.loads(captured.out)
    validate(report, load_schema("v1"))
    return report


def test_header_fields_v1(build_catpart, tmp_path: Path, capsys) -> None:
    # Header bytes 8-32 (Phase 1 + B1 evidence): dword8 big-endian at
    # 8-12, dword12 big-endian at 12-16 with the law-H1 chain value
    # (dword8 + dword12 == file size), eight 0xFF bytes at 16-24.
    report = inspect_report(build_catpart, tmp_path, capsys, header_dword=1024)
    size = len(build_catpart(header_dword=1024))
    assert report["schema_version"] == 1
    assert report["magic"] == "V5_CFV2"
    assert report["header_dword"] == 1024
    assert report["file_size"] == size
    assert report["header_dword12"] == size - 1024
    assert report["ff8_at_16_24"] is True
    assert report["header_dword16"] is None
    assert report["header_dword20"] is None


def test_header_dual_region_variant(build_catpart, tmp_path: Path, capsys) -> None:
    # The 146-file variant (B1): bytes 16-24 are two more big-endian
    # dwords (dword16, dword20) instead of the ff x8 marker.
    report = inspect_report(build_catpart, tmp_path, capsys, dual_region=True)
    assert report["ff8_at_16_24"] is False
    assert report["header_dword16"] == 0x10
    assert report["header_dword20"] == 0x20


def test_trailer_fields_v1(build_catpart, tmp_path: Path, capsys) -> None:
    # Trailer model (B1 evidence): the last 36 bytes of a file ending
    # with CB__END\0 - seven big-endian dwords plus the marker. The
    # fixture's registration block sits in the payload; B points at it.
    report = inspect_report(build_catpart, tmp_path, capsys, header_dword=1024)
    data = build_catpart(header_dword=1024)
    trailer = report["trailer"]
    assert trailer is not None
    assert trailer["a"] == 1
    assert trailer["registration_offset"] == data.index(b"DASSAULT-SYSTEMES") - 5
    assert trailer["c"] == 0xE7
    assert trailer["d"] == 0xE7
    assert trailer["e"] == 0
    assert trailer["f"] == 0
    assert trailer["tail_region_length"] == len(data) - 1024
    assert trailer["registration"] == {
        "tag": "N",
        "company": "DASSAULT-SYSTEMES",
        "product": "CATIA",
        "code": "041803",
    }


def test_trailer_absent_without_marker(build_catpart, tmp_path: Path, capsys) -> None:
    # 262/1818 corpus files do not end with CB__END\0 (B1 evidence);
    # the trailer is reported as null, not fabricated.
    report = inspect_report(
        build_catpart, tmp_path, capsys, with_trailer=False, header_dword=1024
    )
    assert report["trailer"] is None


def test_trailer_registration_null_when_block_invalid(
    build_catpart, tmp_path: Path, capsys
) -> None:
    # The registration block validates byte-exact in 1553/1556
    # CB__END-ending files; a differing byte must null the registration,
    # not crash the parse or fake a match.
    report = inspect_report(
        build_catpart,
        tmp_path,
        capsys,
        header_dword=1024,
        payload=b"XX-INVALID-BLOCK-XX" * 2,
        with_registration=False,
    )
    trailer = report["trailer"]
    assert trailer is not None
    assert trailer["registration_offset"] == 0
    assert trailer["registration"] is None


def test_container_records_v1(build_catpart, tmp_path: Path, capsys) -> None:
    # The container-name table records (B1 evidence), in file order,
    # each validated against the record model before being reported.
    report = inspect_report(build_catpart, tmp_path, capsys)
    containers = report["containers"]
    assert [c["name"] for c in containers] == [
        "CATPrtCont",
        "CATFeatCont",
        "CGMGeom",
    ]
    assert [c["parent_name"] for c in containers] == [
        "CATProdCont",
        "CATPrtCont",
        "CATContainer",
    ]
    first = containers[0]
    assert first["table_id"] == 0x00030001
    assert first["index"] == 1
    assert first["stream_id"] == 1
    assert first["weight"] == 11
    assert len(first["guid"]) == 32
    assert first["guid"] == (0).to_bytes(8, "big").hex() + (0x1AE0).to_bytes(8, "big").hex()
    assert [c["index"] for c in containers] == [1, 2, 3]
    assert [c["stream_id"] for c in containers] == [1, 6, 11]


def test_kind_v1_from_table_names(build_catpart, tmp_path: Path, capsys) -> None:
    # Kind law K1 (docs/evidence/2026-11-07-container-kind-law.md):
    # CATPrtCont -> part; CATProdCont/CATMechProdCont without
    # CATPrtCont -> product; no table (8 corpus files) -> unknown.
    assert inspect_report(build_catpart, tmp_path, capsys)["kind"] == "part"
    product = inspect_report(
        build_catpart,
        tmp_path,
        capsys,
        records=(("CATProdCont", "CATFeatCont"),),
    )
    assert product["kind"] == "product"
    mech = inspect_report(
        build_catpart,
        tmp_path,
        capsys,
        records=(("CATMechProdCont", "CATProdCont"), ("CATProdCont", "CATFeatCont")),
    )
    assert mech["kind"] == "product"
    no_table = inspect_report(build_catpart, tmp_path, capsys, records=())
    assert no_table["kind"] == "unknown"
    assert no_table["containers"] == []


def test_kind_part_wins_over_product_containers(
    build_catpart, tmp_path: Path, capsys
) -> None:
    # 2 corpus parts carry CATProdCont/CATMechProdCont next to
    # CATPrtCont (kind-law note); CATPrtCont decides.
    report = inspect_report(
        build_catpart,
        tmp_path,
        capsys,
        records=(
            ("CATProdCont", "CATFeatCont"),
            ("CATPrtCont", "CATProdCont"),
            ("CATMechProdCont", "CATProdCont"),
        ),
    )
    assert report["kind"] == "part"


def test_invalid_reports_rejected_by_schema_v1(
    build_catpart, tmp_path: Path, capsys
) -> None:
    # The committed schema is the authority: a report claiming the wrong
    # schema version, or a bogus kind, must not validate.
    report = inspect_report(build_catpart, tmp_path, capsys)
    schema = load_schema("v1")
    with pytest.raises(ValidationError):
        validate({**report, "schema_version": 0}, schema)
    with pytest.raises(ValidationError):
        validate({**report, "kind": "assembly"}, schema)
    with pytest.raises(ValidationError):
        validate({**report, "ff8_at_16_24": "yes"}, schema)
