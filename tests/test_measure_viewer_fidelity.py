"""The viewer-fidelity harness (corpus-free synthetic pins).

``scripts/triage/measure_viewer_fidelity.py`` measures what the shipped
export seam actually recovered — pool vs used vertices, summed triangle
area, bbox diagonal and the two normalized coverage *proxies* — because
L2 "pass" certifies topology legality, not surface completeness.  These
pins run it over :mod:`fixtures_gen` parts, never the corpus:

- the golden box fixture (8 vertices / 12 triangles, 20 x 100 x 60 mm)
  pins every metric against a closed-form area and diagonal;
- a classified export failure keeps its class and emits no metrics;
- the vertices-only fixture reports zero coverage, not an error;
- the CSV is byte-identical across runs and keeps the documented header;
- sample selection is deterministic, anchor-first, one quota per class;
- the stdlib PNG reader and the canvas non-background test are proven on
  a synthetic image (the optional browser pin, skipped without Chromium,
  drives the shipped page on two same-named fixtures).
"""

from __future__ import annotations

import csv
import importlib.util
import json
import math
import struct
import zlib
from pathlib import Path

import pytest

from fixtures_gen import build_fixture

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "triage" / "measure_viewer_fidelity.py"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

_spec = importlib.util.spec_from_file_location("measure_viewer_fidelity", SCRIPT)
assert _spec is not None and _spec.loader is not None
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)

#: fixtures_gen's golden box: 20 x 100 x 60 mm (G2 worked example).
BOX_AREA = 2 * (20 * 100 + 20 * 60 + 100 * 60)
BOX_DIAG2 = 20 * 20 + 100 * 100 + 60 * 60


def write_variant(tmp_path: Path, variant: str, name: str = "sample.CATPart") -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / name
    path.write_bytes(build_fixture("part", seed=0, variant=variant))
    return path


def test_box_fixture_metrics_are_closed_form(tmp_path):
    measurement = m.measure_path(write_variant(tmp_path, "geometry"))

    assert measurement["status"] == "ok"
    assert measurement["pool_vertices"] == 8
    assert measurement["used_vertices"] == 8
    assert measurement["used_vertex_fraction"] == 1.0
    assert measurement["triangle_count"] == 12
    assert measurement["exported_area_mm2"] == pytest.approx(BOX_AREA, rel=1e-9)
    assert measurement["area_density"] == pytest.approx(
        round(BOX_AREA / BOX_DIAG2, 6), rel=0
    )
    assert measurement["degenerate_count"] == 0
    assert measurement["boundary_edge_count"] == 0
    assert measurement["manifold"] is True
    assert measurement["closed"] is True
    assert measurement["oriented"] is True
    assert measurement["bbox_diag_mm"] == pytest.approx(math.sqrt(BOX_DIAG2))
    assert json.loads(measurement["warnings"]) == []


def test_classified_failure_keeps_the_class_and_emits_no_metrics(tmp_path):
    measurement = m.measure_path(write_variant(tmp_path, "geometry-nan-coords"))

    assert measurement["status"] == "error"
    assert measurement["error_class"] == "malformed-pool-vertex"
    assert measurement["error_detail"]
    assert measurement["pool_vertices"] is None
    assert measurement["triangle_count"] is None
    assert measurement["exported_area_mm2"] is None


def test_vertices_only_fixture_reports_zero_coverage_not_an_error(tmp_path):
    measurement = m.measure_path(
        write_variant(tmp_path, "geometry-composite-law-e0b-unpinnable")
    )

    assert measurement["status"] == "ok"
    assert measurement["pool_vertices"] == 12
    assert measurement["used_vertices"] == 0
    assert measurement["used_vertex_fraction"] == 0.0
    assert measurement["triangle_count"] == 0
    assert measurement["exported_area_mm2"] == 0.0
    assert measurement["area_density"] == 0.0
    classes = {w["class"] for w in json.loads(measurement["warnings"])}
    assert "no-facet-records" in classes


def test_missing_file_is_unavailable_not_a_crash(tmp_path):
    measurement = m.measure_path(tmp_path / "absent.CATPart")

    assert measurement["status"] == "unavailable"
    assert measurement["error_class"] == "missing-file"
    assert measurement["triangle_count"] is None


def test_csv_is_deterministic_and_keeps_the_documented_header(tmp_path, capsys):
    path = write_variant(tmp_path, "geometry")
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"

    assert m.main([str(path), "--out", str(first)]) == 0
    assert m.main([str(path), "--out", str(second)]) == 0
    capsys.readouterr()
    assert first.read_bytes() == second.read_bytes()

    with open(first, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
    assert reader.fieldnames == m.FIELDS
    assert len(rows) == 1
    row = rows[0]
    assert row["status"] == "ok"
    assert row["triangle_count"] == "12"
    assert row["used_vertex_fraction"] == "1.0"
    assert row["sample_class"] == "single-path"


def _record(
    sha: str,
    status: str,
    *,
    error_class: str | None = None,
    failed_check: str | None = None,
    closed: bool = False,
    warnings: list | None = None,
) -> dict:
    return {
        "sha256": sha,
        "path": f"parts/{sha}.CATPart",
        "split": "dev",
        "local_path": f"corpus/parts/{sha}.CATPart",
        "l2": {
            "status": status,
            "error_class": error_class,
            "failed_check": failed_check,
            "mesh": {"closed": closed},
            "warnings": warnings or [],
        },
    }


def test_l2_class_labels_follow_the_strata_priority():
    curve = [{"class": "curve-entry-loops-unexported"}]
    assert m.l2_class(_record("a", "pass", closed=True)) == "pass:closed"
    assert m.l2_class(_record("b", "pass", closed=True, warnings=curve)) == (
        "pass:curve-entry"
    )
    assert m.l2_class(_record("c", "pass")) == "pass:open-shell"
    assert m.l2_class(_record("d", "fail", error_class="undecoded-variant")) == (
        "fail:undecoded-variant"
    )
    assert m.l2_class(_record("e", "fail", failed_check="empty-mesh")) == (
        "fail:empty-mesh"
    )


def test_sample_selection_is_deterministic_anchor_first_and_class_stratified():
    records = [
        _record("01", "pass", closed=True),
        _record("02", "pass", closed=True),
        _record("03", "pass", closed=True),
        _record("04", "pass"),
        _record("05", "pass"),
        _record("06", "pass"),
        _record("07", "fail", error_class="undecoded-variant"),
        _record("08", "fail", error_class="undecoded-variant"),
        _record("09", "fail", failed_check="empty-mesh"),
    ]
    anchor = records[2]["path"]
    first = m.select_sample(records, 4, [anchor])
    second = m.select_sample(records, 4, [anchor])

    assert [(rec["sha256"], cls) for rec, cls in first] == [
        (rec["sha256"], cls) for rec, cls in second
    ]
    assert first[0] == (records[2], "audit-anchor")
    classes = [cls for _rec, cls in first]
    # 3 remaining slots over 8 classes: the first three get one; the
    # empty curve-entry class falls through to the SHA-ordered backfill.
    assert classes == ["audit-anchor", "pass:closed", "pass:open-shell", "backfill"]
    assert len({rec["sha256"] for rec, _cls in first}) == 4


def test_sample_selection_rejects_unknown_anchor():
    with pytest.raises(SystemExit):
        m.select_sample([_record("01", "pass", closed=True)], 1, ["nope/absent.CATPart"])


# --------------------------------------------------------------------------
# PNG + canvas content (stdlib only)
# --------------------------------------------------------------------------


def _png(width: int, height: int, rows: list[bytes], color_type: int = 2) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            len(data).to_bytes(4, "big")
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    header = (
        width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + bytes([8, color_type, 0, 0, 0])
    )
    raw = b"".join(b"\x00" + row for row in rows)
    return (
        PNG_SIGNATURE
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def test_png_reader_and_canvas_content():
    background = bytes((14, 21, 38))
    foreground = bytes((255, 122, 122))
    rows = [
        background * 4,
        background * 2 + foreground + background,
        background * 4,
        background * 4,
    ]
    width, height, channels, pixels = m._png_pixels(_png(4, 4, rows))
    assert (width, height, channels) == (4, 4, 3)
    has_content, fraction = m.canvas_content(width, height, channels, pixels)
    assert has_content is True
    assert fraction == pytest.approx(1 / 16)

    blank_rows = [background * 4 for _ in range(4)]
    width, height, channels, pixels = m._png_pixels(_png(4, 4, blank_rows))
    assert m.canvas_content(width, height, channels, pixels) == (False, 0.0)


def test_png_reader_handles_rgba_filter_one():
    """Playwright writes RGBA8; row filter 1 (Sub) is legal there."""
    background = bytes((14, 21, 38, 255))
    # Filter 1: the first pixel is absolute, the second is a zero delta
    # from it — two identical background pixels per row.
    row = b"\x01" + background + bytes(4)
    raw = row * 2
    header = (
        (2).to_bytes(4, "big")
        + (2).to_bytes(4, "big")
        + bytes([8, 6, 0, 0, 0])
    )

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            len(data).to_bytes(4, "big")
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    raw_png = (
        PNG_SIGNATURE
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
    width, height, channels, pixels = m._png_pixels(raw_png)
    assert (width, height, channels) == (2, 2, 4)
    assert m.canvas_content(width, height, channels, pixels) == (False, 0.0)


# --------------------------------------------------------------------------
# The optional browser pin (local only, skipped without Chromium)
# --------------------------------------------------------------------------


def _chromium_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    try:
        with sync_playwright() as playwright:
            return Path(playwright.chromium.executable_path).exists()
    except Exception:
        return False


def test_screenshot_capture_flags_canvas_content(tmp_path):
    pytest.importorskip("playwright")
    if not _chromium_available():
        pytest.skip("Chromium browser binary not installed (spec §7, local only)")

    # Same basename on purpose: the capture reloads the page per part,
    # so a reused page's stale fileName cannot stand in for a fresh load.
    box = write_variant(tmp_path / "a", "geometry", "part.CATPart")
    carriers = write_variant(
        tmp_path / "b", "geometry-composite-law-e0b-unpinnable", "part.CATPart"
    )
    empty = write_variant(tmp_path / "c", "geometry-seebody-empty", "part.CATPart")
    records = [
        {
            "sha256": "1" * 64,
            "path": "a/part.CATPart",
            "local_path": str(box),
        },
        {
            "sha256": "2" * 64,
            "path": "b/part.CATPart",
            "local_path": str(carriers),
        },
        {
            "sha256": "3" * 64,
            "path": "c/part.CATPart",
            "local_path": str(empty),
        },
    ]
    shots = m.capture_screenshots(
        [(rec, Path(rec["local_path"])) for rec in records],
        tmp_path / "shots",
        port=0,
    )

    box_shot = shots["1" * 64]
    assert box_shot["viewer_status"] == "loaded"
    assert box_shot["canvas_visible"] is True
    assert box_shot["canvas_has_content"] is True
    assert box_shot["canvas_nonbackground_fraction"] > 0
    assert (tmp_path / "shots" / f"{'1' * 16}.png").stat().st_size > 0

    # A vertices-only part now renders its decoded carriers (the 2026-11-19
    # no-surface display fallback): loaded, a visible point cloud.
    carriers_shot = shots["2" * 64]
    assert carriers_shot["viewer_status"] == "loaded"
    assert carriers_shot["canvas_visible"] is True
    assert carriers_shot["canvas_has_content"] is True
    assert (tmp_path / "shots" / f"{'2' * 16}.png").stat().st_size > 0

    # Nothing to display is still the named failure, never a blank "loaded".
    empty_shot = shots["3" * 64]
    assert empty_shot["viewer_status"] == "failed"
    assert empty_shot["canvas_visible"] is False
    assert empty_shot["canvas_has_content"] is False
    assert (tmp_path / "shots" / f"{'3' * 16}.png").stat().st_size > 0
