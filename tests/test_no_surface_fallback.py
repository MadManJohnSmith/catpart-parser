"""Corpus-free tests for the no-surface display fallback (2026-11-19).

The shipped module (``catpart.geometry.display``) turns a part that would
otherwise fail — no facet triangles, no evaluable ``a5 03 34`` surface,
no triangulable point grid — into exactly what its bytes decode: the
3-divisible f64 point runs as a point cloud, the ``33 3X`` curve records'
centers as points, and a segment **only** where the ``33 32``
``[P][Q][P]+|Q|`` law pins ``P -> P+Q``.  It is a **display**, never a
surface reconstruction: zero triangles, zero welding, zero inferred
connectivity (``docs/evidence/2026-11-19-no-surface-fallback.md``).

Pinned decisions:

- the display points are f32 xyz (rounded once), the segment index pairs
  point into that array, and the label says ``no surface — showing N
  points, M curve segments``;
- a mesh keeps priority (a facet store, an a5 surface, a triangulable
  grid never reach the display route), and a part with surface frames
  but no evaluable surface keeps its named ``no-evaluable-surface``;
- a part with 0 points / 0 segments / 0 triangles keeps its pre-display
  failure class (never a blank success);
- a malformed or law-failing record contributes nothing (fail-closed).

Every fixture here is bytes built in this module; no corpus binary is
read.
"""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path

import pytest

from catpart.geometry import ExportError, build_export, display

import fixtures_gen
from catpart.schema import load_schema
from catpart.schema.validate import validate


def f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def part(records: bytes) -> bytes:
    """A full container whose payload carries ``records`` in a CATPrtCont block."""
    block = fixtures_gen.storage_property_block(b"CATPrtCont", b"CATContainer")
    payload = block + b"\x00" * 64 + records
    return fixtures_gen.build_catpart(
        header_dword=0x0000_0100, payload=payload, pad_before_table=0x600
    )


def bagrep_part(records: bytes) -> bytes:
    """A full container whose payload carries ``records`` in a CGMGeom block.

    The count-framed f32 arrays live in the geometry containers the
    missing-store census named; CGMGeom is the one the plate anchor uses.
    """
    block = fixtures_gen.storage_property_block(b"CGMGeom", b"CATContainer")
    return fixtures_gen.build_catpart(
        header_dword=0x0000_0100, payload=block + records, pad_before_table=0x600
    )


def run(*points) -> bytes:
    """One ``e5 0d`` record carrying the f64le triples of a point run."""
    payload = b"".join(struct.pack("<3d", *point) for point in points)
    return (
        b"\xe5\x0d"
        + b"\x03"
        + struct.pack("<H", 0x00E7)
        + struct.pack("<I", len(payload))
        + struct.pack("<I", 100)
        + payload
    )


def filler() -> bytes:
    return (
        b"\xe5\x0d"
        + b"\x03"
        + struct.pack("<H", 0x0018)
        + struct.pack("<I", 0)
        + struct.pack("<I", 100)
    )


def bagrep_array(*points) -> bytes:
    """One count-framed f32 point array (the bag-rep payload family)."""
    floats = [value for point in points for value in point]
    return struct.pack("<I", len(floats)) + b"".join(
        struct.pack("<f", value) for value in floats
    )


def curve(family: int, payload: bytes, length: int | None = None) -> bytes:
    """One ``33 3X`` record behind its 7-B header (the BR3 C1 layout)."""
    declared = len(payload) if length is None else length
    return (
        b"\x02\x00"
        + struct.pack("<H", 7)
        + b"\x00"
        + struct.pack("<H", declared)
        + bytes((0x33, family))
        + payload
    )


def line(p, q, stored_length: float | None = None) -> bytes:
    """A canonical ``33 32`` line record (len == 2 + the 40-B block)."""
    length = (
        (q[0] ** 2 + q[1] ** 2 + q[2] ** 2) ** 0.5
        if stored_length is None
        else stored_length
    )
    block = struct.pack("<10f", *p, *q, *p, length)
    return curve(0x32, block, length=2)


def fixture(variant: str) -> bytes:
    return fixtures_gen.build_fixture("part", seed=0, variant=variant)


# ---------------------------------------------------------------- export


def test_point_cloud_part_opens_with_points_and_no_triangle(tmp_path: Path) -> None:
    path = tmp_path / "points.CATPart"
    path.write_bytes(fixture("geometry-no-surface-points"))
    out = tmp_path / "points.ply"
    summary = build_export(path, out)

    validate(summary, load_schema("export-summary-v1"))
    assert summary["vertex_count"] == 0
    assert summary["triangle_count"] == 0
    block = summary["no_surface_display"]
    assert block["kind"] == "decoded-carriers"
    assert block["surface"] is False
    assert block["point_count"] == 6
    assert block["curve_segment_count"] == 0
    assert block["label"] == "no surface — showing 6 points, 0 curve segments"
    assert block["point_runs"] == 1
    assert block["run_points"] == 6
    assert block["pool_points"] == 0
    assert block["curve_records"] == 0
    assert block["points"] == [
        0.0, 0.0, 0.0,
        6.0, 0.0, 1.5,
        12.0, 0.0, 3.0,
        18.0, 0.0, 4.5,
        24.0, 0.0, 6.0,
        30.0, 0.0, 7.5,
    ]
    assert block["curve_segments"] == []
    assert [warning["class"] for warning in summary["warnings"]] == [
        "no-surface-display"
    ]
    assert summary["bounding_box"] == {"min": [0.0, 0.0, 0.0], "max": [30.0, 0.0, 7.5]}
    # The PLY stays the surface contract: an empty one, never fabricated faces.
    text = out.read_bytes()
    assert text.startswith(b"ply\nformat binary_little_endian 1.0\n")
    assert b"element vertex 0\n" in text and b"element face 0\n" in text


def test_curve_segment_is_law_pinned_and_centres_are_points(tmp_path: Path) -> None:
    path = tmp_path / "curves.CATPart"
    path.write_bytes(fixture("geometry-no-surface-curves"))
    summary = build_export(path, tmp_path / "curves.ply")
    block = summary["no_surface_display"]

    assert summary["triangle_count"] == 0
    assert block["point_count"] == 3
    assert block["curve_segment_count"] == 1
    assert block["label"] == "no surface — showing 3 points, 1 curve segment"
    # P, P+Q (the law-holding line) and the 33 37 circle's center.
    assert block["points"] == [10.0, 0.0, 0.0, 10.0, 10.0, 0.0, 30.0, 40.0, 0.0]
    assert block["curve_segments"] == [0, 1]
    assert block["curve_records"] == 4
    assert block["decoded_curve_records"] == 2
    assert block["skipped_curve_records"] == 2
    assert block["line_records"] == 1
    assert block["families"] == {"33 32": 2, "33 36": 1, "33 37": 1}


def test_display_points_are_f32_and_indices_are_pairs() -> None:
    data = part(run((0.1, 0.2, 0.3), (1.1, 2.2, 3.3), (4.4, 5.5, 6.6)) + filler() + filler())
    scan = display.scan_part(data)
    assert scan.points == (
        (f32(0.1), f32(0.2), f32(0.3)),
        (f32(1.1), f32(2.2), f32(3.3)),
        (f32(4.4), f32(5.5), f32(6.6)),
    )
    assert scan.points[0][0] == 0.10000000149011612  # f32(0.1)
    assert scan.segments == ()
    # A bare approach is not connectivity: three points, zero segments.
    assert scan.label == "no surface — showing 3 points, 0 curve segments"


def test_bagrep_f32_array_opens_as_points_and_never_triangles() -> None:
    # The R-BAG-P lever: a u32le float count in front of f32 triples in
    # the part's geometry container.  The array is decoded as points —
    # the note measured no face list and no implicit strip, so zero
    # segments and zero triangles.
    data = bagrep_part(
        bagrep_array(
            (1.0, 2.0, 3.0),
            (4.0, 5.0, 6.0),
            (7.0, 8.0, 9.0),
        )
    )
    scan = display.scan_part(data)
    assert scan.bagrep_regions == 1
    assert scan.bagrep_arrays == 1
    assert scan.bagrep_floats == 9
    assert scan.bagrep_points == 3
    assert scan.bagrep_skipped == 0
    assert scan.sources == (display.SOURCE_BAGREP,)
    assert scan.points == ((1.0, 2.0, 3.0), (4.0, 5.0, 6.0), (7.0, 8.0, 9.0))
    assert scan.segments == ()


def test_bagrep_array_reaches_the_export_block(tmp_path: Path) -> None:
    path = tmp_path / "bagrep.CATPart"
    path.write_bytes(
        bagrep_part(
            bagrep_array(
                (1.0, 2.0, 3.0),
                (4.0, 5.0, 6.0),
                (7.0, 8.0, 9.0),
            )
        )
    )
    out = tmp_path / "bagrep.ply"
    summary = build_export(path, out)
    validate(summary, load_schema("export-summary-v1"))
    block = summary["no_surface_display"]
    assert summary["triangle_count"] == 0
    assert block["sources"] == ["bagrep-f32-points"]
    assert block["bagrep_arrays"] == 1
    assert block["bagrep_floats"] == 9
    assert block["bagrep_points"] == 3
    assert block["bagrep_skipped"] == 0
    assert block["point_count"] == 3
    assert block["curve_segment_count"] == 0
    assert block["label"] == "no surface — showing 3 points, 0 curve segments"
    assert block["points"] == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]
    assert block["curve_segments"] == []
    # The empty PLY stays the surface contract.
    assert b"element vertex 0\n" in out.read_bytes()


def test_bagrep_array_gates_are_fail_closed(tmp_path: Path) -> None:
    # A count-framed block whose clean run does NOT end (a clean f32
    # follows the declared block) is a byte pattern, not an array; a
    # declared count that is not a multiple of three is not a point
    # array.  Neither contributes a bag-rep point: the bag-rep route
    # stays fail-closed, and the points the scan does show come only
    # from the empty-scan f32-run fallback (#60), whose measured law
    # admits these same bytes as plain 12-byte-stride runs.
    not_ending = bagrep_array(
        (1.0, 2.0, 3.0), (4.0, 5.0, 6.0), (7.0, 8.0, 9.0)
    ) + b"".join(struct.pack("<f", float(value)) for value in range(10, 22))
    not_divisible = struct.pack("<I", 10) + b"".join(
        struct.pack("<f", value) for value in range(1, 11)
    )
    data = bagrep_part(not_ending + not_divisible)
    scan = display.scan_part(data)
    assert scan.bagrep_arrays == 0
    assert scan.bagrep_points == 0
    assert scan.f32_runs == 2
    assert scan.f32_points == 10
    assert display.SOURCE_BAGREP not in scan.sources
    assert display.SOURCE_F32_RUNS in scan.sources

    # The 100 m display envelope is applied per point: a clean array of
    # out-of-envelope coordinates frames (pool scale allows 1e6) but
    # displays nothing and keeps the pre-display classification.  The
    # f32-run fallback stays out too (1e6 is outside its 1e5 ceiling).
    path = tmp_path / "envelope.CATPart"
    path.write_bytes(
        bagrep_part(
            bagrep_array(
                (1.0e6, 2.0e5, 3.0e5),
                (1.0e6, 2.0e5, 3.0e5),
                (1.0e6, 2.0e5, 3.0e5),
            )
        )
    )
    scan = display.scan_part(path.read_bytes())
    assert scan.bagrep_arrays == 1
    assert scan.bagrep_points == 0
    assert scan.bagrep_skipped == 3
    assert scan.f32_points == 0
    assert not scan.has_carriers
    with pytest.raises(ExportError) as excinfo:
        build_export(path, tmp_path / "envelope.ply")
    assert excinfo.value.error_class == "missing-geometry-store"


def test_run_points_are_never_joined_without_a_curve_law() -> None:
    # Four points in a row: no >=3x3 reading and no curve record, so the
    # display shows a 4-point cloud and never a polyline.
    data = part(run((0.0, 0.0, 0.0), (5.0, 0.0, 0.0), (0.0, 5.0, 0.0), (5.0, 5.0, 0.0)) + filler() + filler())
    scan = display.scan_part(data)
    assert len(scan.points) == 4
    assert scan.segments == ()
    assert scan.line_records == 0


def test_circle_midring_and_conic_contribute_centres_only() -> None:
    # The three center-bearing families decode their center as a point.
    # None of them exposes an orientation, so no circle/conic polyline is
    # guessed: zero segments.
    midring = struct.pack(">6f", 1.0, 2.0, 3.0, 0.6, 0.8, 4.0) + b"\x00\x00"
    conic = struct.pack(">7f", 5.0, 6.0, 7.0, 0.6, 0.8, 2.0, 3.0) + b"\x00\x00"
    circle = struct.pack(">4f", 8.0, 9.0, 10.0, 5.0) + b"\x00\x00"
    data = part(curve(0x33, midring) + curve(0x37, circle) + curve(0x38, conic))
    scan = display.scan_part(data)
    assert scan.curve_records == 3
    assert scan.decoded_curve_records == 3
    assert scan.segments == ()
    assert scan.points == ((1.0, 2.0, 3.0), (8.0, 9.0, 10.0), (5.0, 6.0, 7.0))


def test_law_failing_and_malformed_records_contribute_nothing(tmp_path: Path) -> None:
    # A wrong stored length, a mid-range non-unit direction pair, a
    # non-positive conic b, and an undecoded 33 36: all walked, none
    # displayed — and the part keeps its pre-display classification.
    midring = struct.pack(">6f", 0.0, 0.0, 20.0, 0.5, 0.5, 3.0) + b"\x00\x00"
    conic = struct.pack(">7f", 0.0, 0.0, 30.0, 0.0, 0.0, 2.0, -3.0) + b"\x00\x00"
    records = (
        line((10.0, 0.0, 0.0), (0.0, 10.0, 0.0), stored_length=7.0)
        + curve(0x33, midring)
        + curve(0x38, conic)
        + curve(0x36, b"\x00\x00")
    )
    data = part(records)
    scan = display.scan_part(data)
    assert scan.curve_records == 4
    assert scan.decoded_curve_records == 0
    assert scan.skipped_curve_records == 4
    assert scan.points == ()
    assert scan.segments == ()
    assert not scan.has_carriers

    path = tmp_path / "malformed.CATPart"
    path.write_bytes(data)
    with pytest.raises(ExportError) as excinfo:
        build_export(path, tmp_path / "malformed.ply")
    assert excinfo.value.error_class == "missing-geometry-store"


def test_empty_part_stays_a_named_failure(tmp_path: Path) -> None:
    path = tmp_path / "empty.CATPart"
    path.write_bytes(part(filler() + filler() + filler()))
    out = tmp_path / "empty.ply"
    with pytest.raises(ExportError) as excinfo:
        build_export(path, out)
    assert excinfo.value.error_class == "missing-geometry-store"
    assert not out.exists()


def test_mesh_and_surface_paths_keep_priority(tmp_path: Path) -> None:
    mesh_path = tmp_path / "mesh.CATPart"
    mesh_path.write_bytes(fixture("geometry"))
    mesh = build_export(mesh_path, tmp_path / "mesh.ply")
    assert mesh["triangle_count"] > 0
    assert "no_surface_display" not in mesh

    surface_path = tmp_path / "surface.CATPart"
    surface_path.write_bytes(fixture("geometry-surface-bspline"))
    surface = build_export(surface_path, tmp_path / "surface.ply")
    assert "surface_tessellation" in surface
    assert "no_surface_display" not in surface

    refused_path = tmp_path / "refused.CATPart"
    refused_path.write_bytes(fixture("geometry-surface-no-evaluable"))
    with pytest.raises(ExportError) as excinfo:
        build_export(refused_path, tmp_path / "refused.ply")
    assert excinfo.value.error_class == "no-evaluable-surface"


def test_display_export_is_deterministic(tmp_path: Path) -> None:
    path = tmp_path / "curves.CATPart"
    path.write_bytes(fixture("geometry-no-surface-curves"))
    first = tmp_path / "a.ply"
    second = tmp_path / "b.ply"
    summary_a = build_export(path, first)
    summary_b = build_export(path, second)
    assert summary_a == summary_b
    assert hashlib.sha256(first.read_bytes()).digest() == hashlib.sha256(
        second.read_bytes()
    ).digest()


def test_label_pluralization() -> None:
    assert display.label_for(0, 0) == "no surface — showing 0 points, 0 curve segments"
    assert display.label_for(1, 1) == "no surface — showing 1 point, 1 curve segment"
    assert display.label_for(2, 3) == "no surface — showing 2 points, 3 curve segments"


# ---------------------------------------------------------------- census


def test_scan_part_reports_the_carrier_census() -> None:
    data = part(
        run((10.0, 0.0, 0.0), (20.0, 0.0, 0.0), (30.0, 0.0, 0.0))
        + filler()
        + filler()
        + line((10.0, 0.0, 0.0), (0.0, 10.0, 0.0))
        + curve(0x37, struct.pack(">4f", 30.0, 40.0, 0.0, 5.0) + b"\x00\x00")
    )
    scan = display.scan_part(data)
    assert scan.regions >= 1
    assert scan.point_runs == 1
    assert scan.run_points == 3
    assert scan.curve_records == 2
    assert scan.decoded_curve_records == 2
    assert scan.line_records == 1
    assert [point for point in scan.points] == [
        (10.0, 0.0, 0.0),
        (20.0, 0.0, 0.0),
        (30.0, 0.0, 0.0),
        (10.0, 0.0, 0.0),
        (10.0, 10.0, 0.0),
        (30.0, 40.0, 0.0),
    ]
    assert scan.segments == ((3, 4),)


# ------------------------------------------------------- corpus-gated


#: The 128-row grid-meshing census; the display arms are its 120 rows
#: that neither meshed through the grid (``open``) nor through a5.
GRID_PARTS = Path(__file__).resolve().parents[1] / "docs/evidence/data/grid-meshing-parts.csv"
CORPUS_MANIFEST = Path(__file__).resolve().parents[1] / "manifests/corpus-manifest.csv"

#: One pinned part: a store recovered in a CATBRepModeContainer block
#: with 51 point runs, 8 ``33 32`` records (6 law-holding), 4 mid-ring /
#: 8 circle records and 20 filler records — the mixed carrier shape.
PINNED_PART = "002e03ea032528d30a7d8d13340869b0fd115b22a13ae64c723bf4ff16fc4f7a"


def _manifest() -> dict[str, dict[str, str]]:
    import csv

    with CORPUS_MANIFEST.open(newline="", encoding="utf-8") as fh:
        return {row["sha256"]: row for row in csv.DictReader(fh)}


def _targets() -> list[str]:
    import csv

    with GRID_PARTS.open(newline="", encoding="utf-8") as fh:
        return [
            row["sha256"]
            for row in csv.DictReader(fh)
            if row["open"] == "False" and row["a5_open"] == "False"
        ]


#: The 14 formerly-BLANK rows the bag-rep f32 arrays open (the four
#: other formerly-BLANK rows with an array are the a5-priority parts that
#: stay closed; the other 51 carry no array at all).
BAGREP_OPENED = {
    "084841b3a2068a72",
    "18a5e736be72bf2d",
    "2e1684b0e0461b11",
    "314092359a7c42b0",
    "3b9452edecb4f777",
    "4c361f3c5f63d9df",
    "95636572111e8b7a",
    "b00e31c89c8b5791",
    "b0e07338249a0067",
    "c2598108ba61b0df",
    "c2d1ecc6dca46685",
    "d6aa6e71a25e9dd8",
    "dc7e292322cf3435",
    "eaf6890653df8d33",
}
#: The five a5-priority rows. Four of them carried a bag-rep array and
#: stayed BLANK under the bag-rep-only run; the subtype-4 patch head now
#: opens all five as MESH (the display route is still not consulted).
SUBTYPE4_RECOVERED = {
    "58ed8b2875b2734a",
    "6c6a2e9f3d5f5303",
    "8e8500b1c0627bcb",
    "b4fd22e357f83410",
    "d523721f99b2dec9",
}
OPEN_RATE = Path(__file__).resolve().parents[1] / "docs/evidence/data/open-rate-files.csv"


@pytest.mark.skipif(
    not OPEN_RATE.exists(),
    reason="open-rate census is absent (the corpus-gated case)",
)
def test_bagrep_arrays_open_the_missing_store_rows() -> None:
    """The combined open-rate census after both display levers (2026-11-19).

    ``docs/evidence/data/open-rate-files.csv`` is the merged-tree probe
    over all 1,442 manifest part rows: 56 rows stay BLANK, the 14
    formerly-BLANK rows whose geometry containers carry a count-framed
    f32 array are DISPLAY, and the five a5-priority rows (four of which
    also carry an array) are MESH through the subtype-4 patch head.
    """
    import csv

    with OPEN_RATE.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1442, len(rows)
    by_sha = {row["sha16"]: row for row in rows}
    blank = {row["sha16"] for row in rows if row["open kind"] == "BLANK"}
    assert len(blank) == 56, sorted(blank)
    for sha in BAGREP_OPENED:
        row = by_sha[sha]
        assert row["open kind"] == "DISPLAY", (sha, row)
        assert int(row["points"]) > 0, (sha, row)
    for sha in SUBTYPE4_RECOVERED:
        row = by_sha[sha]
        assert row["open kind"] == "MESH", (sha, row)
        assert int(row["triangles"]) > 0, (sha, row)
    assert SUBTYPE4_RECOVERED.isdisjoint(blank)
    assert BAGREP_OPENED.isdisjoint(blank)


@pytest.mark.skipif(
    not GRID_PARTS.exists() or not CORPUS_MANIFEST.exists(),
    reason="corpus census is gitignored / absent (the corpus-gated case)",
)
def test_corpus_population_renders_the_decoded_carriers(tmp_path: Path) -> None:
    """The measured population (docs/evidence/2026-11-19-no-surface-fallback.md).

    Of the 120 no-facet parts, the T1 grid relaxation (#59) now
    triangulates 5 that refused whole before (4,422 candidate
    triangles); 105 still open via the display fallback and 10 keep
    their ``undecoded-variant`` class.  The bag-rep count-framed f32
    arrays keep their measured share; the counts are pinned part by
    part in ``docs/evidence/data/no-surface-fallback-parts.csv``.
    """
    root = Path(__file__).resolve().parents[1]
    manifest = _manifest()
    targets = _targets()
    assert len(targets) == 120, "the grid-meshing census must carry the 120 rows"
    missing = [sha for sha in targets if not (root / manifest[sha]["local_path"]).exists()]
    if missing:
        pytest.skip(f"corpus is absent ({len(missing)} of the 120 files missing)")

    classes: dict[str, int] = {}
    totals = {"points": 0, "curve_segments": 0, "parts_with_segments": 0, "triangles": 0}
    pinned = None
    for sha in targets:
        path = root / manifest[sha]["local_path"]
        out = tmp_path / f"{sha[:16]}.ply"
        try:
            summary = build_export(path, out)
        except ExportError as exc:
            classes[exc.error_class] = classes.get(exc.error_class, 0) + 1
            continue
        totals["triangles"] += summary["triangle_count"]
        if summary["triangle_count"]:
            # the T1-relaxed grids: a mesh, not a display (no block)
            classes["mesh"] = classes.get("mesh", 0) + 1
            continue
        classes["display"] = classes.get("display", 0) + 1
        block = summary["no_surface_display"]
        totals["points"] += block["point_count"]
        totals["curve_segments"] += block["curve_segment_count"]
        totals["parts_with_segments"] += 1 if block["curve_segment_count"] else 0
        if sha == PINNED_PART:
            pinned = block

    assert classes == {"mesh": 5, "display": 105, "undecoded-variant": 10}, classes
    assert totals == {
        "points": 9685,
        "curve_segments": 188,
        "parts_with_segments": 31,
        "triangles": 4422,
    }, totals
    assert pinned is not None, "the pinned part must be in the display population"
    assert pinned["point_count"] == 116
    assert len(pinned["points"]) == 348  # flat f32 xyz
    assert pinned["curve_segment_count"] == 6
    assert len(pinned["curve_segments"]) == 12  # flat index pairs
    assert pinned["point_runs"] == 51
    assert pinned["run_points"] == 92
    assert pinned["curve_records"] == 40
    assert pinned["decoded_curve_records"] == 18
    assert pinned["skipped_curve_records"] == 22
    assert pinned["line_records"] == 6
    assert pinned["surface"] is False
    assert pinned["label"] == "no surface — showing 116 points, 6 curve segments"


def test_empty_scan_f32_run_fallback_opens_container_less_carriers() -> None:
    # #60: a part whose only geometry is a plain 12-byte-stride f32 run
    # (no count framing for the bag-rep law, no grid reading, no curve
    # record) displays the run's points under the measured missing-store
    # law — the CAAMaiUdfForMfgHole* lever (+2 open) and the 22 further
    # BLANK rows the same fallback rescues.  The fallback never runs
    # when any primary carrier decoded (the gates test pins that side).
    payload = b"".join(
        struct.pack("<3f", 10.0 * i, 5.0 * i, 1.0 * i) for i in range(1, 8)
    )
    scan = display.scan_part(bagrep_part(payload))
    assert scan.f32_runs == 1
    assert scan.f32_points == 7
    assert scan.points == tuple((10.0 * i, 5.0 * i, 1.0 * i) for i in range(1, 8))
    assert scan.sources == (display.SOURCE_F32_RUNS,)
    assert scan.label == "no surface — showing 7 points, 0 curve segments"
