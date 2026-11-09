"""Container-name table record parsing: validation edge cases (B1 evidence).

The record model and its corpus-wide laws (T1 names-area size, T2 record
size/contiguity, T3 constants) are documented in
docs/evidence/2026-11-07-container-table-and-trailer.md; the parser
reports only records that validate against the model. These tests pin
what the parser does with the documented exception families (satellite
blobs, distributed tables, no table at all) and with payload bytes that
merely resemble records — through the ``build_inspect_report`` seam.
"""

from __future__ import annotations

from pathlib import Path

from conftest import container_record

from catpart.cli import build_inspect_report


def inspect(path: Path) -> dict:
    return build_inspect_report(path)


def test_records_between_satellite_blobs_are_parsed(tmp_path: Path) -> None:
    # Satellite blobs (382 corpus files) sit between container rows,
    # starting 04 00 c0 20 (the V5USERID row) or 04 00 fc 3f; the
    # records on both sides still parse (B1, "Satellite blobs").
    path = tmp_path / "satellites.CATPart"
    satellite = b"\x04\x00\xc0\x20" + b"\x0a\x00\x00\x00" + b"V5USERID\x00" + b"\x00" * 8
    path.write_bytes(
        container_record("CATPrtCont", "CATProdCont")
        + satellite
        + container_record("CATFeatCont", "CATPrtCont", stream_id=6, index=2)
    )
    report = inspect(path)
    assert [c["name"] for c in report["containers"]] == ["CATPrtCont", "CATFeatCont"]


def test_anchor_bytes_without_a_valid_record_are_skipped(tmp_path: Path) -> None:
    # The anchor dword 02 00 81 20 occurs only at valid record starts in
    # the corpus (0 rejected positions on 1810 files, B1); payload bytes
    # that mimic it without satisfying the record model are skipped, not
    # reported and not fatal.
    path = tmp_path / "false-anchor.CATPart"
    junk = (
        b"\x00\x00\x00\x00" * 3
        + b"\x02\x00\x81\x20"
        + b"junk-not-a-record\x00"
        + b"\x00" * 16
    )
    path.write_bytes(
        junk + container_record("CATPrtCont", "CATProdCont", stream_id=6, index=1)
    )
    report = inspect(path)
    assert [c["name"] for c in report["containers"]] == ["CATPrtCont"]


def test_record_violating_constants_is_not_a_record(tmp_path: Path) -> None:
    # Law T3 constants (f5, f6, f8, f9, tail) and law T1 (f10) hold on
    # every corpus record; a blob violating one is not reported. The
    # file then has no table: kind unknown, containers empty.
    path = tmp_path / "bad-constants.CATPart"
    record = bytearray(container_record("CATPrtCont", "CATProdCont"))
    record[16] = 0x99  # f5 constant 0x006c0001 broken
    path.write_bytes(bytes(record))
    report = inspect(path)
    assert report["containers"] == []
    assert report["kind"] == "unknown"


def test_record_names_bad_padding_is_rejected(tmp_path: Path) -> None:
    # Law T1: the names area is zero-padded to a multiple of 8 and the
    # padding bytes verified zero (19300/19300 records).
    path = tmp_path / "bad-pad.CATPart"
    record = bytearray(container_record("CATPrtCont", "CATProdCont"))
    # names = "CATPrtCont\0CATProdCont\0" (23 bytes) + 1 padding byte at
    # record offset 40 + 23 = 63; the padding must be zero (law T1).
    record[63] = 0x41
    path.write_bytes(bytes(record))
    assert inspect(path)["containers"] == []


def test_truncated_record_at_end_of_window_is_not_parsed(tmp_path: Path) -> None:
    # A record straddling the end of the buffer (here: end of file) is
    # out of the validated model's reach and is not reported.
    path = tmp_path / "truncated.CATPart"
    full = container_record("CATPrtCont", "CATProdCont")
    path.write_bytes(b"\x00" * 32 + full[:-20])
    report = inspect(path)
    assert report["containers"] == []


def test_payload_junk_never_yields_records(tmp_path: Path) -> None:
    # Payload strings that merely contain vocabulary names
    # (CATContainersForLinksNotUpdated) or resemble registration data
    # must not produce records (the v0 whole-file scan's known flaw).
    path = tmp_path / "junk.CATPart"
    path.write_bytes(
        b"\x00CATUnicodeString\x00CATContainersForLinksNotUpdated\x00"
        b"CATCatalogManager\x00catalogManager\x00CATIA\x00"
        b"\x04\x01\x80\x03" + b"041803P\x00JFIF\x00" + b"\x12\x34" * 16
        + container_record("CATStdCont", "CATContainer", stream_id=1, index=1)
    )
    report = inspect(path)
    assert [c["name"] for c in report["containers"]] == ["CATStdCont"]


def test_records_reported_in_file_order(tmp_path: Path) -> None:
    # Records report in file order (the scan walks anchors forward);
    # the directory join (law D1) is not parsed, so no reordering.
    path = tmp_path / "order.CATPart"
    path.write_bytes(
        container_record("CGMGeom", "CATContainer", stream_id=21, index=3)
        + container_record("CATPrtCont", "CATProdCont", stream_id=1, index=1)
    )
    report = inspect(path)
    assert [c["name"] for c in report["containers"]] == ["CGMGeom", "CATPrtCont"]
    assert [c["index"] for c in report["containers"]] == [3, 1]
