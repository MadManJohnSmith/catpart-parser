#!/usr/bin/env python3
"""Measure how much of a part the L2 export actually recovers.

L2 (`catpart-export`, the fitness runner) certifies *topology legality*:
a non-empty mesh, manifold edges, a finite plausible bounding box and a
degenerate-triangle cap.  It does **not** measure surface completeness,
so an L2 "pass" can render a part whose plate body is missing while its
hole rims are present (the 2026-11-18 viewer audit).  This harness
re-plays the shipped Python export seam over one file or a deterministic
manifest sample and records the numbers L2 does not report.

Per part it records, straight from the shipped decode
(:func:`catpart.geometry.export._export_data`, the seam
``docs/evidence/2026-11-13-stage14-export-failures.md`` and
``scripts/triage/not_manifold_audit.py`` already replay — no CATIA, no
new laws, no ``src/`` change):

- ``pool_vertices`` — the decoded pool / element-space size the
  exporter reports as ``vertex_count``;
- ``used_vertices`` — how many of those any exported triangle references;
- ``triangle_count`` and ``exported_area_mm2`` — the exact triangle
  count and the summed Euclidean area of the emitted triangles;
- ``degenerate_count`` — the exporter's skipped degenerate strips
  (``degenerate_triangle_count``);
- ``boundary_edge_count`` / ``manifold`` / ``closed`` / ``oriented`` —
  the exporter's mesh invariants;
- ``bbox_diag_mm`` — the diagonal of the exporter's bounding box.

Two **normalized coverage proxies** are emitted so parts of different
size can be compared:

- ``used_vertex_fraction`` = used_vertices / pool_vertices;
- ``area_density`` = exported_area_mm2 / bbox_diag_mm**2.

They are proxies, **not a fidelity claim**.  A high fraction/density
does not prove the surface is complete and a low one is not proof of a
decode bug: a legitimately sparse sheet-like part (an open shell, a
wire-frame part, a part whose solid is stored outside the decoded CGM
payload) can score low for content reasons, and the denominator is the
bounding box, not the true surface.  They only bound what the exporter
*emitted* relative to what it *found* and to its own envelope.  No
ground-truth area exists in the corpus, so none is claimed.

The exporter's warning records are carried verbatim (class + detail),
including ``curve-entry-loops-unexported``, ``unused-pool-vertices`` and
``open-shell``.

``--screenshot DIR`` additionally drives the shipped viewer headlessly
(Playwright, the ``scripts/assembly_viewer_acceptance.py`` static-server
pattern) with the same file, saves one PNG per part and records whether
the canvas carries non-background pixels (a pixel counts as
non-background when it differs from the image's dominant colour by more
than 8 in any RGB channel).  Screenshots are local-only evidence, never
a CI step.

Usage:

    # one file
    .venv/bin/python scripts/triage/measure_viewer_fidelity.py \\
        corpus/.../part.CATPart --out /tmp/one.csv

    # deterministic manifest sample (the committed 20-part audit run)
    .venv/bin/python scripts/triage/measure_viewer_fidelity.py \\
        --manifest --sample-size 20 \\
        --anchor CATIA/CATIA_vol/Usinage/Gabarit_trou_alu_alpha.CATPart \\
        --anchor 'diseño_3d/labios/main.CATPart' \\
        --anchor CATIA/new_catia/SP02_BETA/SP02_BETA_COIFFE.CATPart \\
        --anchor sample/CAAMechanicalModeler.edu/InputData/CAAMmrPartCopy_Comp1.CATPart \\
        --out docs/evidence/data/fidelity-2026-11-18.csv

Sample mode reads the accepted fitness row
(``--report``, default ``fitness/reports/20261118T171127Z-0882ce.json``),
joins it to the manifest by SHA-256, and selects deterministically:
anchors in command order, then a fixed quota per L2 class (sorted by
SHA-256 within the class, classes in :data:`STRATA` order), then any
shortfall backfilled in SHA-256 order.  The same inputs always yield
the same rows.

Output: a deterministic CSV at ``--out`` (sorted/rounded numbers, no
machine paths) plus a human summary on stdout, including the run
command.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import mmap
import shlex
import statistics
import sys
import zlib
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
DEFAULT_REPORT = ROOT / "fitness" / "reports" / "20261118T171127Z-0882ce.json"
DEFAULT_SCREENSHOT_DIR = ROOT / "docs" / "evidence" / "data" / "fidelity-screenshots"

sys.path.insert(0, str(ROOT / "src"))

from catpart.geometry import export as export_mod  # noqa: E402
from catpart.geometry.errors import ExportError  # noqa: E402

FIELDS = [
    "sample_index",
    "sample_class",
    "report_l2_status",
    "report_l2_class",
    "sha256",
    "split",
    "path",
    "status",
    "error_class",
    "error_detail",
    "pool_vertices",
    "used_vertices",
    "used_vertex_fraction",
    "triangle_count",
    "exported_area_mm2",
    "area_density",
    "degenerate_count",
    "boundary_edge_count",
    "manifold",
    "closed",
    "oriented",
    "bbox_diag_mm",
    "bbox_min_x",
    "bbox_min_y",
    "bbox_min_z",
    "bbox_max_x",
    "bbox_max_y",
    "bbox_max_z",
    "warnings",
    "screenshot",
    "viewer_status",
    "canvas_visible",
    "canvas_has_content",
    "canvas_nonbackground_fraction",
]

#: Selection strata, in priority order.  A record's class is the first
#: matching label, so ``pass:curve-entry`` wins over ``pass:closed`` and
#: ``pass:open-shell``; the strata are therefore disjoint by
#: construction (first match).
STRATA = [
    "pass:closed",
    "pass:curve-entry",
    "pass:open-shell",
    "fail:empty-mesh",
    "fail:not-manifold",
    "fail:degenerate-triangles",
    "fail:undecoded-variant",
    "fail:missing-geometry-store",
]

SCREENSHOT_BG_THRESHOLD = 8
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


# --------------------------------------------------------------------------
# measurement
# --------------------------------------------------------------------------


def triangle_area(tri, vertices) -> float:
    """Euclidean area of one emitted triangle (3-D cross product)."""
    a, b, c = (vertices[i] for i in tri)
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    cx = uy * vz - uz * vy
    cy = uz * vx - ux * vz
    cz = ux * vy - uy * vx
    return 0.5 * math.sqrt(cx * cx + cy * cy + cz * cz)


def _round(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def measure_export(summary: dict, vertices: list, triangles: list) -> dict:
    """The fidelity metrics of one successful export, from shipped data.

    ``summary``/``vertices``/``triangles`` are exactly what
    ``catpart.geometry.export._export_data`` returns; nothing is
    re-decoded and no law is applied here.
    """
    pool = len(vertices)
    used = sorted({i for tri in triangles for i in tri if 0 <= i < pool})
    area = math.fsum(triangle_area(tri, vertices) for tri in triangles)

    bbox = summary.get("bounding_box")
    if bbox is None:
        bbox_min = bbox_max = [0.0, 0.0, 0.0]
    else:
        bbox_min = list(bbox["min"])
        bbox_max = list(bbox["max"])
    dx = bbox_max[0] - bbox_min[0]
    dy = bbox_max[1] - bbox_min[1]
    dz = bbox_max[2] - bbox_min[2]
    diag = math.sqrt(dx * dx + dy * dy + dz * dz)

    stats = summary.get("mesh") or {}
    return {
        "pool_vertices": pool,
        "used_vertices": len(used),
        "used_vertex_fraction": _round(len(used) / pool) if pool else 0.0,
        "triangle_count": len(triangles),
        "exported_area_mm2": _round(area),
        "area_density": _round(area / (diag * diag)) if diag else 0.0,
        "degenerate_count": summary.get("degenerate_triangle_count", 0),
        "boundary_edge_count": stats.get("boundary_edge_count"),
        "manifold": stats.get("manifold"),
        "closed": stats.get("closed"),
        "oriented": stats.get("oriented"),
        "bbox_diag_mm": _round(diag),
        "bbox_min_x": _round(bbox_min[0]),
        "bbox_min_y": _round(bbox_min[1]),
        "bbox_min_z": _round(bbox_min[2]),
        "bbox_max_x": _round(bbox_max[0]),
        "bbox_max_y": _round(bbox_max[1]),
        "bbox_max_z": _round(bbox_max[2]),
        "warnings": _warnings_json(summary.get("warnings") or []),
    }


def _warnings_json(warnings: list) -> str:
    """The exporter's warning records verbatim, as a compact JSON list."""
    return json.dumps(
        warnings, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _empty_metrics() -> dict:
    return {
        "pool_vertices": None,
        "used_vertices": None,
        "used_vertex_fraction": None,
        "triangle_count": None,
        "exported_area_mm2": None,
        "area_density": None,
        "degenerate_count": None,
        "boundary_edge_count": None,
        "manifold": None,
        "closed": None,
        "oriented": None,
        "bbox_diag_mm": None,
        "bbox_min_x": None,
        "bbox_min_y": None,
        "bbox_min_z": None,
        "bbox_max_x": None,
        "bbox_max_y": None,
        "bbox_max_z": None,
        "warnings": "",
    }


def measure_path(path: Path) -> dict:
    """Replay the shipped export seam over ``path`` (read-only mmap).

    Returns the metric columns plus ``status`` (``ok`` / ``error``) and,
    on ``ExportError``, its classified ``error_class``/``error_detail``.
    A missing/unreadable file is ``unavailable``; it is reported, never
    silently skipped.
    """
    if not path.is_file():
        return {
            "status": "unavailable",
            "error_class": "missing-file",
            "error_detail": f"not on disk: {path}",
            **_empty_metrics(),
        }
    try:
        with open(path, "rb") as fh:
            data = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
    except OSError as exc:
        return {
            "status": "error",
            "error_class": "unreadable-file",
            "error_detail": str(exc),
            **_empty_metrics(),
        }
    try:
        summary, vertices, triangles = export_mod._export_data(data)
    except ExportError as exc:
        return {
            "status": "error",
            "error_class": exc.error_class,
            "error_detail": exc.detail,
            **_empty_metrics(),
        }
    finally:
        data.close()
    return {
        "status": "ok",
        "error_class": "",
        "error_detail": "",
        **measure_export(summary, vertices, triangles),
    }


# --------------------------------------------------------------------------
# sample selection
# --------------------------------------------------------------------------


def l2_class(record: dict) -> str:
    """The first :data:`STRATA` label a fitness record matches."""
    l2 = record["l2"]
    warnings = l2.get("warnings") or []
    if l2.get("status") == "pass":
        if any(str(w.get("class", "")).startswith("curve-entry") for w in warnings):
            return "pass:curve-entry"
        mesh = l2.get("mesh") or {}
        if mesh.get("closed"):
            return "pass:closed"
        return "pass:open-shell"
    if l2.get("error_class"):
        return f"fail:{l2['error_class']}"
    if l2.get("failed_check"):
        return f"fail:{l2['failed_check']}"
    return "fail:unclassified"


def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_manifest(path: Path = MANIFEST) -> dict[str, dict]:
    """Manifest rows keyed by SHA-256 (a digest is the corpus identity)."""
    with open(path, newline="", encoding="utf-8") as fh:
        return {row["sha256"]: row for row in csv.DictReader(fh)}


def load_report(path: Path = DEFAULT_REPORT) -> dict:
    report = _load_json(path)
    if "files" not in report:
        raise SystemExit(f"measure_viewer_fidelity: {path} has no 'files' array")
    return report


def report_records(report: dict, manifest: dict[str, dict]) -> list[dict]:
    """Every manifest-backed L2 record (parts only; products have no mesh)."""
    records = []
    for row in report["files"]:
        if row.get("l2") is None:
            continue
        if row.get("kind") not in ("part", "unknown"):
            continue
        man = manifest.get(row["sha256"])
        if man is None:
            continue
        records.append(
            {
                "sha256": row["sha256"],
                "path": row["path"],
                "split": row.get("split") or man.get("split", ""),
                "local_path": man.get("local_path", ""),
                "l2": row["l2"],
            }
        )
    return records


def select_sample(
    records: list[dict], size: int, anchors: list[str] = ()
) -> list[tuple[dict, str]]:
    """Deterministic sample: anchors, then an even quota per L2 class.

    Anchors are exact fitness ``path`` values and keep command order.
    The 16 remaining rows (``size - len(anchors)``) are split evenly
    over :data:`STRATA` in order, each class sorted by SHA-256; a class
    with fewer candidates takes what it has, and any shortfall is
    backfilled from the not-yet-chosen rows in SHA-256 order
    (``sample_class`` = ``backfill``).  Same inputs -> same output.
    """
    if size < 1:
        raise ValueError("sample size must be >= 1")
    by_path = {rec["path"]: rec for rec in records}
    chosen: list[tuple[dict, str]] = []
    seen: set[str] = set()
    for anchor in anchors:
        rec = by_path.get(anchor)
        if rec is None:
            raise SystemExit(
                f"measure_viewer_fidelity: anchor not in the fitness report: {anchor!r}"
            )
        if rec["sha256"] in seen:
            raise SystemExit(f"measure_viewer_fidelity: duplicate anchor {anchor!r}")
        seen.add(rec["sha256"])
        chosen.append((rec, "audit-anchor"))
    remaining = size - len(chosen)
    if remaining < 0:
        raise SystemExit(
            f"measure_viewer_fidelity: {len(anchors)} anchors exceed --sample-size {size}"
        )

    ordered = sorted(records, key=lambda rec: rec["sha256"])
    quotas = {
        stratum: remaining // len(STRATA)
        + (1 if i < remaining % len(STRATA) else 0)
        for i, stratum in enumerate(STRATA)
    }
    for stratum in STRATA:
        taken = 0
        for rec in ordered:
            if taken >= quotas[stratum]:
                break
            if rec["sha256"] in seen or l2_class(rec) != stratum:
                continue
            seen.add(rec["sha256"])
            chosen.append((rec, stratum))
            taken += 1
    if len(chosen) < size:
        for rec in ordered:
            if len(chosen) >= size:
                break
            if rec["sha256"] in seen:
                continue
            seen.add(rec["sha256"])
            chosen.append((rec, "backfill"))
    return chosen


# --------------------------------------------------------------------------
# CSV
# --------------------------------------------------------------------------


def build_row(
    index: int,
    record: dict,
    sample_class: str,
    measurement: dict,
    screenshot: dict | None = None,
) -> dict:
    l2 = record.get("l2") or {}
    row = {
        "sample_index": index,
        "sample_class": sample_class,
        "report_l2_status": l2.get("status", ""),
        "report_l2_class": l2_class(record) if l2 else "",
        "sha256": record["sha256"],
        "split": record["split"],
        "path": record["path"],
    }
    row.update(measurement)
    shot = screenshot or {}
    row.update(
        {
            "screenshot": shot.get("screenshot", ""),
            "viewer_status": shot.get("viewer_status", ""),
            "canvas_visible": _bool(shot.get("canvas_visible")),
            "canvas_has_content": _bool(shot.get("canvas_has_content")),
            "canvas_nonbackground_fraction": shot.get(
                "canvas_nonbackground_fraction", ""
            ),
        }
    )
    return row


def _bool(value) -> str:
    if value is None or value == "":
        return ""
    return "true" if value else "false"


def write_csv(rows: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDS})


# --------------------------------------------------------------------------
# human summary
# --------------------------------------------------------------------------


def _stats(values: list[float]) -> str:
    if not values:
        return "n/a"
    return (
        f"{min(values):.4g} / {statistics.median(values):.4g} / {max(values):.4g}"
    )


def summarize(rows: list[dict], out_path: Path | None, command: str) -> str:
    lines = []
    measured = [row for row in rows if row["status"] == "ok"]
    by_status: dict[str, list[dict]] = {}
    for row in rows:
        by_status.setdefault(row["report_l2_status"] or "n/a", []).append(row)

    lines.append(f"measured: {len(rows)} part(s); {len(measured)} exported")
    lines.append("")
    lines.append(
        "report L2 status  n  triangles (min/med/max)  area mm2 (min/med/max)"
        "  used_vertex_fraction (min/med/max)  area_density (min/med/max)"
    )
    for status in ("pass", "fail", "n/a"):
        subset = by_status.get(status) or []
        if not subset:
            continue
        exported = [row for row in subset if row["status"] == "ok"]
        triangles = [row["triangle_count"] for row in exported]
        areas = [row["exported_area_mm2"] for row in exported]
        used = [row["used_vertex_fraction"] for row in exported]
        density = [row["area_density"] for row in exported]
        lines.append(
            f"{status:<17} {len(subset):>3}  {_stats(triangles)}"
            f"  {_stats(areas)}  {_stats(used)}  {_stats(density)}"
        )
    lines.append("")
    lines.append("classes:")
    for row in rows:
        metrics = (
            f"{row['triangle_count']:>6} tri  {row['exported_area_mm2']:>12.3f} mm2"
            f"  uvf={row['used_vertex_fraction']:.3f}  dens={row['area_density']:.4f}"
            if row["status"] == "ok"
            else f"{row['status']}: {row['error_class']}"
        )
        lines.append(
            f"  {row['sample_index']:>2} {row['sample_class']:<26}"
            f" {row['report_l2_status'] or '-':<4} {metrics}  {row['path']}"
        )
    warnings = Counter()
    for row in measured:
        for warning in json.loads(row["warnings"] or "[]"):
            warnings[warning["class"]] += 1
    if warnings:
        lines.append("")
        lines.append(
            "exporter warnings (files): "
            + ", ".join(f"{name}={count}" for name, count in sorted(warnings.items()))
        )
    lines.append("")
    lines.append(
        "proxies: used_vertex_fraction = used/pool; area_density ="
        " exported_area/bbox_diag^2. Coverage proxies only, NOT a fidelity"
        " claim and NOT ground truth."
    )
    if out_path is not None:
        lines.append(f"out: {out_path}")
    lines.append(f"run: {command}")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# optional screenshot evidence
# --------------------------------------------------------------------------


def _load_viewer_acceptance():
    """Reuse the acceptance runner's static-server pattern, not a copy."""
    script = ROOT / "scripts" / "assembly_viewer_acceptance.py"
    spec = importlib.util.spec_from_file_location(
        "assembly_viewer_acceptance", script
    )
    if spec is None or spec.loader is None:
        raise SystemExit("measure_viewer_fidelity: cannot load the acceptance runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _find_free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _png_pixels(raw: bytes) -> tuple[int, int, int, bytes]:
    """Decode an 8-bit non-interlaced PNG to ``(width, height, channels, data)``.

    Stdlib only (zlib + struct): Playwright screenshots are RGBA8.
    Colour types 0, 2, 4 and 6 are supported; palette PNGs raise rather
    than guess.  The returned bytes are rows in RGB(A)/grey order with
    the PNG filters already reversed.
    """
    if not raw.startswith(PNG_SIGNATURE):
        raise ValueError("not a PNG")
    pos = len(PNG_SIGNATURE)
    width = height = bit_depth = color_type = None
    idat = bytearray()
    while pos + 8 <= len(raw):
        length = int.from_bytes(raw[pos : pos + 4], "big")
        chunk_type = raw[pos + 4 : pos + 8]
        chunk = raw[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if chunk_type == b"IHDR":
            width = int.from_bytes(chunk[0:4], "big")
            height = int.from_bytes(chunk[4:8], "big")
            bit_depth = chunk[8]
            color_type = chunk[9]
            if chunk[12] != 0:
                raise ValueError("interlaced PNG not supported")
        elif chunk_type == b"IDAT":
            idat.extend(chunk)
        elif chunk_type == b"IEND":
            break
    if width is None or height is None:
        raise ValueError("PNG has no IHDR")
    if bit_depth != 8:
        raise ValueError(f"PNG bit depth {bit_depth} not supported")
    channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(color_type)
    if channels is None:
        raise ValueError(f"PNG colour type {color_type} not supported")
    stride = width * channels
    raw_rows = zlib.decompress(bytes(idat))
    out = bytearray(width * height * channels)
    previous = bytearray(stride)
    src = 0
    for y in range(height):
        filter_type = raw_rows[src]
        src += 1
        row = bytearray(raw_rows[src : src + stride])
        src += stride
        if filter_type == 1:
            for x in range(channels, stride):
                row[x] = (row[x] + row[x - channels]) & 0xFF
        elif filter_type == 2:
            for x in range(stride):
                row[x] = (row[x] + previous[x]) & 0xFF
        elif filter_type == 3:
            for x in range(stride):
                left = row[x - channels] if x >= channels else 0
                row[x] = (row[x] + ((left + previous[x]) >> 1)) & 0xFF
        elif filter_type == 4:
            for x in range(stride):
                left = row[x - channels] if x >= channels else 0
                up = previous[x]
                up_left = previous[x - channels] if x >= channels else 0
                p = left + up - up_left
                pa, pb, pc = abs(p - left), abs(p - up), abs(p - up_left)
                predictor = left if pa <= pb and pa <= pc else (up if pb <= pc else up_left)
                row[x] = (row[x] + predictor) & 0xFF
        elif filter_type != 0:
            raise ValueError(f"PNG filter {filter_type} not supported")
        out[y * stride : (y + 1) * stride] = row
        previous = row
    return width, height, channels, bytes(out)


def canvas_content(
    width: int, height: int, channels: int, pixels: bytes
) -> tuple[bool, float]:
    """``(has_nonbackground, fraction)`` for one decoded canvas image.

    The background is the image's dominant RGB value (the viewer clears
    to a flat colour); a pixel is non-background when any RGB channel
    differs by more than :data:`SCREENSHOT_BG_THRESHOLD`.  Alpha-only
    pixels (fully transparent) are background.
    """
    if width * height == 0:
        return False, 0.0
    rgb = []
    for i in range(0, len(pixels), channels):
        if channels == 2:
            rgb.append((pixels[i],) * 3)
        elif channels == 4:
            rgb.append((pixels[i], pixels[i + 1], pixels[i + 2]))
        else:
            rgb.append(tuple(pixels[i : i + 3]))
    background = Counter(rgb).most_common(1)[0][0]
    nonbackground = sum(
        1
        for pixel in rgb
        if max(abs(pixel[c] - background[c]) for c in range(3))
        > SCREENSHOT_BG_THRESHOLD
    )
    return nonbackground > 0, nonbackground / len(rgb)


def capture_screenshots(
    items: list[tuple[dict, Path]], shot_dir: Path, port: int = 0
) -> dict[str, dict]:
    """Drive the shipped viewer over each part; return per-SHA shot results.

    ``items`` is ``[(record, local_path)]``.  The page is loaded once and
    reused, exactly like the acceptance runner.  A part whose canvas is
    hidden (the empty-mesh failure state) records ``canvas_visible =
    False`` and its PNG is the page screenshot that documents the
    failure, not a canvas capture.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise SystemExit(
            "measure_viewer_fidelity: --screenshot needs Playwright. Local-only:\n"
            "    python -m pip install 'playwright==1.65.2' && "
            "python -m playwright install chromium"
        ) from exc
    runner = _load_viewer_acceptance()
    shot_dir.mkdir(parents=True, exist_ok=True)
    server = runner.StaticServer(port or _find_free_port())
    results: dict[str, dict] = {}
    try:
        server.wait_ready()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            for record, local_path in items:
                # A fresh load per part: two corpus files can share a
                # basename (the sample does), so a reused page's stale
                # ``fileName`` would satisfy the wait before decoding.
                page.goto(f"{server.base}/{runner.PAGE}", wait_until="load")
                page.wait_for_function(
                    "window.viewer && window.viewer.status === 'idle'", timeout=15000
                )
                page.set_input_files("#file-input", str(local_path))
                page.wait_for_function(
                    "['loaded','failed'].includes(window.viewer.status)", timeout=30000
                )
                status = page.evaluate("window.viewer.status")
                visible = page.is_visible("#scene")
                shot = shot_dir / f"{record['sha256'][:16]}.png"
                entry = {
                    "screenshot": shot.relative_to(ROOT).as_posix()
                    if shot.is_relative_to(ROOT)
                    else str(shot),
                    "viewer_status": status,
                    "canvas_visible": visible,
                }
                if visible:
                    raw = page.locator("#scene").screenshot(type="png")
                else:
                    raw = page.screenshot(type="png")
                shot.write_bytes(raw)
                if visible:
                    width, height, channels, pixels = _png_pixels(raw)
                    has_content, fraction = canvas_content(
                        width, height, channels, pixels
                    )
                    entry["canvas_has_content"] = has_content
                    entry["canvas_nonbackground_fraction"] = round(fraction, 6)
                else:
                    entry["canvas_has_content"] = False
                    entry["canvas_nonbackground_fraction"] = 0.0
                results[record["sha256"]] = entry
            browser.close()
    finally:
        server.stop()
    return results


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _local_path(record: dict) -> Path:
    return ROOT / record["local_path"]


def run(args: argparse.Namespace) -> int:
    if args.paths and args.manifest:
        print(
            "measure_viewer_fidelity: give file paths OR --manifest, not both",
            file=sys.stderr,
        )
        return 2
    if not args.paths and not args.manifest:
        print(
            "measure_viewer_fidelity: give a file path or --manifest",
            file=sys.stderr,
        )
        return 2
    if args.anchor and not args.manifest:
        print(
            "measure_viewer_fidelity: --anchor only applies to --manifest",
            file=sys.stderr,
        )
        return 2

    if args.paths:
        items = []
        for raw in args.paths:
            path = Path(raw)
            try:
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:
                digest = ""
            items.append(
                (
                    {
                        "sha256": digest,
                        "path": path.as_posix(),
                        "split": "",
                        "local_path": str(path),
                        "l2": None,
                    },
                    "single-path",
                    path,
                )
            )
    else:
        report = load_report(args.report)
        manifest = load_manifest(args.manifest_path)
        records = report_records(report, manifest)
        if len(records) < args.sample_size:
            print(
                f"measure_viewer_fidelity: report has {len(records)} L2 part rows, "
                f"cannot sample {args.sample_size}",
                file=sys.stderr,
            )
            return 2
        selected = select_sample(records, args.sample_size, list(args.anchor))
        items = [
            (record, sample_class, _local_path(record))
            for record, sample_class in selected
        ]

    measurements = [(record, sample_class, path, measure_path(path)) for record, sample_class, path in items]

    shots: dict[str, dict] = {}
    if args.screenshot is not None:
        shot_dir = Path(args.screenshot)
        shots = capture_screenshots(
            [(record, path) for record, _sample_class, path, _measurement in measurements],
            shot_dir,
            port=args.port,
        )

    rows = []
    for index, (record, sample_class, _path, measurement) in enumerate(measurements, 1):
        rows.append(
            build_row(
                index,
                record,
                sample_class,
                measurement,
                shots.get(record["sha256"]),
            )
        )

    out_path = Path(args.out) if args.out else None
    if out_path is not None:
        write_csv(rows, out_path)
    command = "scripts/triage/measure_viewer_fidelity.py " + shlex.join(args.argv)
    print(summarize(rows, out_path, command.strip()))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Measure what the L2 export recovers: mesh counts, summed triangle "
            "area, bbox diagonal and normalized coverage proxies (proxies only, "
            "not ground truth)."
        )
    )
    parser.add_argument("paths", nargs="*", help="one or more .CATPart/.CATProduct files")
    parser.add_argument(
        "--manifest",
        action="store_true",
        help="sample N parts deterministically from the corpus manifest + fitness report",
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=MANIFEST,
        help=f"corpus manifest (default: {MANIFEST.relative_to(ROOT)})",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT,
        help=f"accepted fitness row for sample classes (default: {DEFAULT_REPORT.relative_to(ROOT)})",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=20,
        help="sample size in --manifest mode (default 20)",
    )
    parser.add_argument(
        "--anchor",
        action="append",
        default=[],
        metavar="REPORT_PATH",
        help="exact fitness path to force into the sample (repeatable, keeps order)",
    )
    parser.add_argument("--out", type=Path, default=None, help="CSV output path")
    parser.add_argument(
        "--screenshot",
        type=Path,
        nargs="?",
        const=DEFAULT_SCREENSHOT_DIR,
        default=None,
        metavar="DIR",
        help="capture one viewer PNG per part into DIR (default: %(const)s)",
    )
    parser.add_argument(
        "--port", type=int, default=0, help="static-server port for --screenshot"
    )
    args = parser.parse_args(argv)
    args.argv = list(argv) if argv is not None else sys.argv[1:]
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
