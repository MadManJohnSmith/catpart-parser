"""Seam 1: ``catpart-inspect <file>`` JSON output (Spec A #8).

Tests assert only on the CLI's external contract: exit code, stdout JSON,
stderr. Every emitted report is validated against the committed schema v0,
mirroring the clean-parse definition used by the fitness runner.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from catpart.schema import load_schema
from catpart.schema.validate import validate


def run_inspect(argv: list[str], capsys) -> tuple[int, str, str]:
    """Invoke the console-script entry function in-process, capture stdio.

    ``argv`` holds the arguments only (no program name), mirroring how
    the console script hands ``sys.argv[1:]`` to argparse.
    """
    from catpart.cli import main_inspect

    code = main_inspect(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def assert_schema_valid(report: dict) -> None:
    validate(report, load_schema("v0"))


def test_inspect_emits_schema_v0_json_for_synthetic_file(
    catpart_file: Path, capsys
) -> None:
    code, out, err = run_inspect([str(catpart_file)], capsys)
    assert code == 0, err
    assert err == ""
    report = json.loads(out)
    assert_schema_valid(report)
    assert report["schema_version"] == 0
    assert report["magic"] == "V5_CFV2"
    assert report["header_dword"] == 0x0001_0000
    assert report["file_size"] == catpart_file.stat().st_size
    assert report["detected_version"] == "V5R21SP0HF0"
    assert report["container_names"] == [
        "CameraStartupContainer",
        "CATFeatCont",
        "CATProdCont",
        "CGMGeom",
        "CATContainer",
        "V5USERID",
    ]


def test_inspect_is_deterministic(catpart_file: Path, capsys) -> None:
    first = run_inspect([str(catpart_file)], capsys)
    second = run_inspect([str(catpart_file)], capsys)
    assert first == second
    assert first[0] == 0


def test_inspect_missing_file_fails_with_stderr(capsys, tmp_path: Path) -> None:
    code, out, err = run_inspect([str(tmp_path / "absent.CATPart")], capsys)
    assert code == 1
    assert out == ""
    assert "absent.CATPart" in err
    assert "catpart-inspect" in err


def test_inspect_tiny_file_fails_with_stderr(capsys, tmp_path: Path) -> None:
    tiny = tmp_path / "tiny.CATPart"
    tiny.write_bytes(b"V5_CFV2\x00\x00\x00")  # 11 bytes: no 32-byte header
    code, out, err = run_inspect([str(tiny)], capsys)
    assert code == 1
    assert out == ""
    assert "32 bytes" in err


def test_inspect_usage_error_exits_2(capsys) -> None:
    with pytest.raises(SystemExit) as excinfo:
        run_inspect([], capsys)
    assert excinfo.value.code == 2


def test_inspect_reports_magic_as_observed(
    build_catpart, tmp_path: Path, capsys
) -> None:
    # 6 corpus files lack the V5_CFV2 magic; the tool still describes them.
    odd = tmp_path / "odd.CATPart"
    odd.write_bytes(build_catpart(magic=b"XX_CFV2\x00"))
    code, out, _ = run_inspect([str(odd)], capsys)
    assert code == 0
    report = json.loads(out)
    assert_schema_valid(report)
    assert report["magic"] == "XX_CFV2"


JUNK_PAYLOAD = (
    b"\x00CATUnicodeString\x00CATContainersForLinksNotUpdated\x00"
    b"CATCatalogManager\x00catalogManager\x00CATIA\x00"
    b"\x04\x01\x80\x03" + b"041803P\x00JFIF\x00" + b"\x12\x34" * 16
)


def inspect_names(path: Path, capsys) -> list[str]:
    code, out, err = run_inspect([str(path)], capsys)
    assert code == 0, err
    return json.loads(out)["container_names"]


def test_scan_ignores_payload_junk(build_catpart, tmp_path: Path, capsys) -> None:
    path = tmp_path / "junk.CATPart"
    path.write_bytes(
        build_catpart(table_names=("CATFeatCont",), payload=JUNK_PAYLOAD)
    )
    assert inspect_names(path, capsys) == ["CATFeatCont"]


def test_scan_whole_name_only(build_catpart, tmp_path: Path, capsys) -> None:
    # CATContainersForLinksNotUpdated contains CATContainer as a substring;
    # only delimited whole-name matches count (see containers.py docstring).
    path = tmp_path / "substring.CATPart"
    path.write_bytes(
        build_catpart(table_names=("CATFeatCont",), payload=JUNK_PAYLOAD)
    )
    assert "CATContainer" not in inspect_names(path, capsys)


def test_scan_finds_names_anywhere_in_file(
    build_catpart, tmp_path: Path, capsys
) -> None:
    path = tmp_path / "late.CATPart"
    path.write_bytes(build_catpart(table_names=(), payload=b"\x00CATStdCont\x00"))
    assert inspect_names(path, capsys) == ["CATStdCont"]


def test_scan_first_occurrence_order_and_dedupe(
    build_catpart, tmp_path: Path, capsys
) -> None:
    path = tmp_path / "dupes.CATPart"
    path.write_bytes(
        build_catpart(
            table_names=("CATFeatCont", "CATProdCont", "CATFeatCont"),
            payload=b"\x00CATFeatCont\x00",
        )
    )
    assert inspect_names(path, capsys) == ["CATFeatCont", "CATProdCont"]


def test_scan_empty_when_no_names(build_catpart, tmp_path: Path, capsys) -> None:
    path = tmp_path / "empty.CATPart"
    path.write_bytes(build_catpart(table_names=(), payload=b"\x01\x02\x03\x04" * 32))
    code, out, err = run_inspect([str(path)], capsys)
    assert code == 0, err
    report = json.loads(out)
    assert_schema_valid(report)
    assert report["container_names"] == []


def test_scan_without_version_marker(build_catpart, tmp_path: Path, capsys) -> None:
    # 338 corpus files have no CNEXTINFOS marker; the scan is independent of it.
    path = tmp_path / "nomarker.CATPart"
    path.write_bytes(
        build_catpart(table_names=("CATPrtCont",), with_marker=False)
    )
    assert inspect_names(path, capsys) == ["CATPrtCont"]


def test_inspect_detected_version_unknown_when_marker_absent(
    build_catpart, tmp_path: Path, capsys
) -> None:
    # The unknown bucket (map decision on ticket #4): files without the
    # marker report "unknown", not a null or a missing field.
    path = tmp_path / "nomarker.CATPart"
    path.write_bytes(build_catpart(with_marker=False))
    code, out, err = run_inspect([str(path)], capsys)
    assert code == 0, err
    report = json.loads(out)
    assert_schema_valid(report)
    assert report["detected_version"] == "unknown"


def test_inspect_detected_version_beyond_8k(
    build_catpart, tmp_path: Path, capsys
) -> None:
    # +78 corpus files carry the marker only past 8 KB; the CLI detects
    # them through the same mmap buffer it scans for container names.
    path = tmp_path / "late-marker.CATPart"
    path.write_bytes(build_catpart(pad_before_table=9000))
    code, out, err = run_inspect([str(path)], capsys)
    assert code == 0, err
    report = json.loads(out)
    assert_schema_valid(report)
    assert report["detected_version"] == "V5R21SP0HF0"


def test_inspect_detected_version_unknown_for_bare_token(
    build_catpart, tmp_path: Path, capsys
) -> None:
    # Only the CNEXTINFOS-anchored form is a marker (evidence note:
    # naive V5Rxx patterns are a negative result).
    path = tmp_path / "bare.CATPart"
    path.write_bytes(build_catpart(with_marker=False, payload=b"\x00V5R19SP0HF0\x00"))
    code, out, err = run_inspect([str(path)], capsys)
    assert code == 0, err
    assert json.loads(out)["detected_version"] == "unknown"
