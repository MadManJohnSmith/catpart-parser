"""Seam 1: ``catpart-inspect <file>`` JSON output (Spec A #8).

Tests assert only on the CLI's external contract: exit code, stdout JSON,
stderr. Every emitted report is validated against the committed schema v1,
mirroring the clean-parse definition used by the fitness runner. The
schema-v1 field-level behavior is pinned slice by slice in
``test_inspect_v1.py``; this file pins the CLI wrapper and the
end-to-end report shape.
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
    validate(report, load_schema("v1"))


def test_inspect_emits_schema_v1_json_for_synthetic_file(
    catpart_file: Path, capsys
) -> None:
    code, out, err = run_inspect([str(catpart_file)], capsys)
    assert code == 0, err
    assert err == ""
    report = json.loads(out)
    assert_schema_valid(report)
    assert report["schema_version"] == 1
    assert report["magic"] == "V5_CFV2"
    assert report["detected_version"] == "V5R21SP0HF0"
    assert report["kind"] == "part"
    assert [c["name"] for c in report["containers"]] == [
        "CATPrtCont",
        "CATFeatCont",
        "CGMGeom",
    ]
    assert report["trailer"]["a"] == 1


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
    # 6 corpus files lack the V5_CFV2 magic; the tool still describes them
    # (the clean-parse invariant, not the parser, enforces the magic).
    odd = tmp_path / "odd.CATPart"
    odd.write_bytes(build_catpart(magic=b"XX_CFV2\x00"))
    code, out, _ = run_inspect([str(odd)], capsys)
    assert code == 0
    report = json.loads(out)
    assert_schema_valid(report)
    assert report["magic"] == "XX_CFV2"


def test_inspect_without_version_marker(build_catpart, tmp_path: Path, capsys) -> None:
    # The unknown bucket (map decision on ticket #4): files without the
    # CNEXTINFOS marker report "unknown", not a null or a missing field;
    # the 338-file bucket is independent of the table parse.
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
    # them through the same mmap buffer it scans for the table records.
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
