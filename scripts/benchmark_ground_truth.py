#!/usr/bin/env python3
"""The ground-truth fidelity harness (marathon W7): one reproducible
mesh-vs-mesh comparison per merge, so every Orquestador merge reports
its REAL fidelity delta instead of a build log impression.

``.CATPart`` side: the export seam writes the binary-little-endian PLY
(:mod:`catpart.geometry.ply`, the shipped exporter — the harness
consumes the artifact, it never forks the decoder). Reference side:
``.STL`` (binary or ASCII, size-probed) or ``.OBJ``. ``.STEP`` is
refused BY NAME: STEP carries B-rep, not tessellation, so a "STEP
comparison" here would fabricate a mesh — the refusal is a named
outcome (exit 2, ``step-reference-unsupported``), never a silent skip.

Metrics (all streaming, one pair in flight, no mesh accumulation):

- ``area_ratio`` = area(CATPart mesh) / area(reference mesh): one pass
  over triangles each side, Heron areas, degenerate triangles count 0.
- ``chamfer`` = the symmetric mean directed distance over VERTEX SETS
  (``chamfer_ab`` mean over A→B, ``chamfer_ba`` the reverse, reported
  separately).
- ``hausdorff_max`` = max of the two directed maxima over the vertex
  sets; ``hausdorff_p95`` = max of the two directed 95th-percentile
  distances (the standard symmetric-p95 convention), each direction's
  distribution reported too.

Nearest-vertex distance is EXACT for the vertex sets: a uniform voxel
grid over the target mesh (cell size = bbox diagonal / 128, override
with ``--cell-size``), ring-outward search until the found best
distance cannot be beaten by an unscanned cell. What the harness does
NOT discriminate (stated once, per the dispatch-recipes detector rule):
vertex-set sampling only — a reference differing only in interior
triangle density passes Hausdorff and Chamfer and is caught ONLY by
``area_ratio``; normals/orientation are never compared; a reference
with extra far-away vertices inflates B→A distances without any
CATPart-side signal. ``--selftest`` pins the edges on synthetic
fixtures (the negative-fixture rule) and is what CI runs.

Cross-unit/cross-scale pairs (marathon W24): CATPart files carry no
units field, so a pair whose reference is exported at different units
(cm vs mm) or scale cannot be compared raw — the distances are unit
garbage and ``area_ratio`` carries the squared mismatch (Dodge
Challenger: raw ratio 202.2 = x100 units x 2.02 physical). The
``--ref-scale auto|1|10`` mode resolves a deterministic per-pair
linear factor from the bbox diagonals (``factor = diag(catpart) /
diag(reference)``, snapped to ``AUTO_CANDIDATES`` within
``AUTO_TOLERANCE``) and SCALES THE REFERENCE by it, so metrics land in
the CATPart's units; the factor, its raw diagonal ratio and the
snap deviation are REPORTED in every record (``normalization`` block
+ ``ref_scale_*`` CSV columns) — never applied silently. What auto
does NOT discriminate (the detector rule, stated once): a genuine unit
mismatch from a coincidental ~x10 size ratio — both look identical
from a bbox diagonal; the reported raw ratio + deviation is the audit
trail and ``--ref-scale 1`` restores the raw pairing. An auto ratio
outside every candidate's window is a named refusal
(``normalization-uncertain``, exit 2), never a guessed factor; the
forced ``1``/``10`` modes skip the confidence window by definition
(the operator owns the override and the record says ``forced``).

Batch mode (``--batch pairs.csv`` with ``catpart_path,reference_path``
columns) streams pair by pair — the 757-file sweep holds one mesh at a
time and appends one CSV row per pair, never accumulating. Peak RSS is
measured (``getrusage``), not estimated, and reported in every output.

Stdlib-only (the local-tools convention); the one repo import is the
committed PLY writer for the selftest fixtures, by module path.
"""

from __future__ import annotations

import argparse
import array
import csv
import json
import math
import struct
import sys
import tempfile
import time
from pathlib import Path
from resource import RUSAGE_SELF, getrusage

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from catpart.geometry import build_export  # noqa: E402 - path setup first
from catpart.geometry.errors import ExportError  # noqa: E402 - path setup first

#: The named outcomes (a refusal or failure is data, never a skip).
OUTCOME_METRICS = "metrics"
OUTCOME_EXPORT_FAILURE = "export-failure"
OUTCOME_EMPTY_MESH = "empty-mesh"
OUTCOME_STEP_REFUSED = "step-reference-unsupported"
OUTCOME_UNREADABLE_REFERENCE = "unreadable-reference"
OUTCOME_NORMALIZATION_UNCERTAIN = "normalization-uncertain"

#: The voxel grid's default cell: the reference bbox diagonal / this.
CELL_DIVISOR = 128

#: The auto normalization's candidate factors (the --ref-scale choices)
#: and its confidence window: a bbox-diagonal ratio further than ±5%
#: from EVERY candidate refuses loudly instead of guessing. The window
#: covers the measured shape-variant drift of an independently
#: re-tessellated same-part pair (Dodge: the 3D diagonal sits 1.6% off
#: the exact x10 while the x extent is f32-exact; the y/z extents
#: differ 9.3%/1.4% because the variants genuinely differ).
AUTO_CANDIDATES = (1.0, 10.0)
AUTO_TOLERANCE = 0.05

#: The selftest's synthetic tolerance (float32 vertices travel through
#: the PLY; the zero-mesh checks pin 1e-5, not bit zero).
SELFTEST_TOL = 1e-5


# --- mesh readers (streaming) ----------------------------------------------


class MeshData:
    """One mesh: flat float64 vertex array + flat int triangle array.

    The reader fills these incrementally; no intermediate mesh object
    is built, so the resident size is the vertex + index arrays plus
    the nearest-neighbor grid, never the file's parse tree.
    """

    def __init__(self) -> None:
        self.vertices = array.array("d")  # xyz triples
        self.triangles = array.array("i")  # vertex-index triples

    @property
    def vertex_count(self) -> int:
        return len(self.vertices) // 3

    @property
    def triangle_count(self) -> int:
        return len(self.triangles) // 3

    def vertex(self, index: int) -> tuple[float, float, float]:
        i = index * 3
        return self.vertices[i], self.vertices[i + 1], self.vertices[i + 2]


def _read_binary_le_ply(path: Path) -> MeshData:
    """The export seam's PLY: ``format binary_little_endian 1.0``,
    ``property float x/y/z`` vertices, ``property list uchar int
    vertex_indices`` faces. The header is parsed (the exporter's exact
    property layout is asserted, so a format change fails loudly
    instead of mis-parsing silently)."""
    mesh = MeshData()
    with path.open("rb") as fh:
        header = bytearray()
        while True:
            line = fh.readline()
            if not line:
                raise ValueError(f"{path}: PLY header has no end_header")
            header += line
            if line.rstrip() == b"end_header":
                break
        text = header.decode("ascii")
        if "format binary_little_endian 1.0" not in text:
            raise ValueError(f"{path}: not a binary_little_endian PLY")
        n_vertices = n_faces = None
        for line in text.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[0] == "element":
                if parts[1] == "vertex":
                    n_vertices = int(parts[2])
                elif parts[1] == "face":
                    n_faces = int(parts[2])
        if n_vertices is None or n_faces is None:
            raise ValueError(f"{path}: PLY header lacks element vertex/face counts")
        # The exporter's layout: 3 float32 vertex coords, uchar+3*int32 faces.
        if "property float x" not in text or "property list uchar int vertex_indices" not in text:
            raise ValueError(f"{path}: unexpected PLY property layout (export seam format)")
        coords = fh.read(12 * n_vertices)
        if len(coords) != 12 * n_vertices:
            raise ValueError(f"{path}: truncated PLY vertex block")
        # float32 little-endian -> float64: array.frombytes would
        # mis-read the 4-byte records as 8-byte doubles, so decode
        # through struct and store the widened values.
        mesh.vertices = array.array("d", struct.unpack(f"<{n_vertices * 3}f", coords))
        for _ in range(n_faces):
            record = fh.read(13)  # uchar count + 3 int32 indices
            if len(record) != 13:
                raise ValueError(f"{path}: truncated PLY face block")
            count = record[0]
            if count != 3:
                raise ValueError(f"{path}: non-triangle PLY face ({count} vertices)")
            a, b, c = struct.unpack("<iii", record[1:])
            mesh.triangles.extend((a, b, c))
    return mesh


def _read_stl(path: Path) -> MeshData:
    """Binary or ASCII STL, size-probed: 84 + 50 * n == file size means
    binary (the robust test — binary files may legally start with
    'solid'). Binary facets stream in bounded chunks (the file is never
    materialized — the anti-OOM rule); ASCII streams line by line.
    Vertices are deduplicated by rounding key so the per-facet
    duplication does not triple the vertex set."""
    mesh = MeshData()
    size = path.stat().st_size
    with path.open("rb") as fh:
        head = fh.read(84)
        if len(head) == 84:
            (count,) = struct.unpack("<I", head[80:84])
            if size == 84 + 50 * count:
                verts: dict[tuple[int, int, int], int] = {}
                remaining = count
                while remaining:
                    want = min(remaining, 8192)
                    chunk = fh.read(50 * want)
                    if len(chunk) < 50 * want:
                        raise ValueError(f"{path}: truncated STL facet block")
                    for offset in range(0, 50 * want, 50):
                        record = chunk[offset : offset + 50]
                        xyz = struct.unpack("<12f", record[:48])
                        for j in (3, 6, 9):
                            mesh.triangles.append(_stl_vertex(mesh, verts, xyz[j : j + 3]))
                    remaining -= want
                return mesh
    # ASCII STL: solid facet loop (vertex dedup as above).
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        verts = {}
        face: list[int] = []
        for line in fh:
            parts = line.split()
            if len(parts) >= 4 and parts[0] == "vertex":
                face.append(_stl_vertex(mesh, verts, tuple(float(v) for v in parts[1:4])))
                if len(face) == 3:
                    mesh.triangles.extend(face)
                    face = []
    return mesh


def _stl_vertex(mesh: MeshData, verts: dict, xyz) -> int:
    """Dedup an STL facet corner: STL lists each vertex three times
    (once per incident facet); the mesh's vertex set must not."""
    key = (round(xyz[0] * 1e6), round(xyz[1] * 1e6), round(xyz[2] * 1e6))
    index = verts.get(key)
    if index is None:
        index = mesh.vertex_count
        mesh.vertices.extend(xyz)
        verts[key] = index
    return index


def _read_obj(path: Path) -> MeshData:
    """OBJ: ``v x y z`` vertices appended straight into the vertex array
    (no intermediate list — the anti-OOM rule), ``f a/b/c ...`` faces
    with 1-based (possibly negative) indices, n-gons fan-triangulated.
    Faces reference already-defined vertices (the OBJ contract), so the
    negative-index base is the vertex count so far."""
    mesh = MeshData()
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            parts = line.split()
            if len(parts) >= 4 and parts[0] == "v":
                mesh.vertices.extend((float(parts[1]), float(parts[2]), float(parts[3])))
            elif len(parts) >= 4 and parts[0] == "f":
                indices = []
                for token in parts[1:]:
                    field = token.split("/")[0]
                    i = int(field)
                    i = mesh.vertex_count + i + 1 if i < 0 else i - 1
                    indices.append(i)
                for k in range(1, len(indices) - 1):
                    mesh.triangles.extend((indices[0], indices[k], indices[k + 1]))
    return mesh


def read_reference_mesh(path: Path) -> MeshData:
    """The reference mesh by extension (STL binary/ASCII, OBJ)."""
    suffix = path.suffix.lower()
    if suffix == ".stl":
        return _read_stl(path)
    if suffix == ".obj":
        return _read_obj(path)
    raise ValueError(f"unsupported reference format: {path.suffix!r}")


# --- the exact nearest-vertex machinery -------------------------------------


class VertexGrid:
    """Uniform voxel index over a mesh's vertices; ring-outward exact
    nearest-vertex queries.

    Cell size is the caller's; the query grows the search ring until
    the best distance found cannot be beaten by any unscanned cell
    (ring radius * cell size > best distance), which makes the result
    the true vertex-set minimum — an approximation in NEITHER direction.
    """

    def __init__(self, mesh: MeshData, cell: float):
        if cell <= 0:
            raise ValueError("cell size must be positive")
        self.mesh = mesh
        self.cell = cell
        self.cells: dict[tuple[int, int, int], array.array] = {}
        for i in range(mesh.vertex_count):
            x, y, z = mesh.vertex(i)
            key = (int(x // cell), int(y // cell), int(z // cell))
            bucket = self.cells.get(key)
            if bucket is None:
                bucket = array.array("i")
                self.cells[key] = bucket
            bucket.append(i)

    def nearest(self, q: tuple[float, float, float]) -> float:
        """Exact distance from ``q`` to the nearest indexed vertex."""
        cx, cy, cz = (int(q[0] // self.cell), int(q[1] // self.cell), int(q[2] // self.cell))
        best = math.inf
        ring = 0
        while True:
            # Scan the full box of the current ring (simple and correct;
            # the box grows quadratically but the loop exits as soon as
            # the exactness condition below is met — usually ring <= 2).
            for ix in range(cx - ring, cx + ring + 1):
                for iy in range(cy - ring, cy + ring + 1):
                    for iz in range(cz - ring, cz + ring + 1):
                        bucket = self.cells.get((ix, iy, iz))
                        if not bucket:
                            continue
                        vertices = self.mesh.vertices
                        for i in bucket:
                            j = i * 3
                            dx = vertices[j] - q[0]
                            dy = vertices[j + 1] - q[1]
                            dz = vertices[j + 2] - q[2]
                            d = dx * dx + dy * dy + dz * dz
                            if d < best:
                                best = d
            best_dist = math.sqrt(best)
            if best_dist <= ring * self.cell:
                # Any nearer vertex would sit in a scanned cell: exact.
                return best_dist
            ring += 1


def _bbox_diagonal(mesh: MeshData) -> float:
    xs = mesh.vertices[0::3]
    ys = mesh.vertices[1::3]
    zs = mesh.vertices[2::3]
    return math.sqrt(
        (max(xs) - min(xs)) ** 2 + (max(ys) - min(ys)) ** 2 + (max(zs) - min(zs)) ** 2
    )


def total_area(mesh: MeshData) -> float:
    """The triangle-soup area (Heron), one pass, degenerate = 0."""
    total = 0.0
    t = mesh.triangles
    v = mesh.vertices
    for i in range(0, len(t), 3):
        ax, ay, az = v[t[i] * 3], v[t[i] * 3 + 1], v[t[i] * 3 + 2]
        bx, by, bz = v[t[i + 1] * 3], v[t[i + 1] * 3 + 1], v[t[i + 1] * 3 + 2]
        cx, cy, cz = v[t[i + 2] * 3], v[t[i + 2] * 3 + 1], v[t[i + 2] * 3 + 2]
        abx, aby, abz = bx - ax, by - ay, bz - az
        acx, acy, acz = cx - ax, cy - ay, cz - az
        bcx, bcy, bcz = cx - bx, cy - by, cz - bz
        la = math.sqrt(abx * abx + aby * aby + abz * abz)
        lb = math.sqrt(acx * acx + acy * acy + acz * acz)
        lc = math.sqrt(bcx * bcx + bcy * bcy + bcz * bcz)
        s = (la + lb + lc) / 2.0
        q = s * (s - la) * (s - lb) * (s - lc)
        total += math.sqrt(q) if q > 0 else 0.0
    return total


def directed_distances(source: MeshData, target_grid: VertexGrid) -> tuple[array.array, float, float]:
    """Every source vertex's exact nearest-target distance: the array
    (for the p95), the mean (chamfer) and the max (Hausdorff)."""
    distances = array.array("d")
    total = 0.0
    peak = 0.0
    vertices = source.vertices
    for i in range(source.vertex_count):
        j = i * 3
        d = target_grid.nearest((vertices[j], vertices[j + 1], vertices[j + 2]))
        distances.append(d)
        total += d
        if d > peak:
            peak = d
    return distances, (total / len(distances) if distances else 0.0), peak


def percentile(sorted_values: array.array, fraction: float) -> float:
    """The nearest-rank percentile of a sorted distance array."""
    if not sorted_values:
        return 0.0
    index = max(0, math.ceil(fraction * len(sorted_values)) - 1)
    return sorted_values[index]


# --- the per-pair normalization (W24) ----------------------------------------


class NormalizationUncertain(ValueError):
    """Auto normalization could not resolve a confident factor: the
    caller turns this into the ``normalization-uncertain`` refusal, so
    an un-confident pair fails loudly instead of comparing garbage."""

    def __init__(self, detail: str, raw_ratio: float | None) -> None:
        super().__init__(detail)
        self.raw_ratio = raw_ratio


def resolve_ref_scale(catpart_diag: float, reference_diag: float, mode: str) -> tuple[float, dict]:
    """The deterministic per-pair factor resolution.

    ``factor`` multiplies the REFERENCE mesh, so metrics land in the
    CATPart's units (Dodge: the reference is cm, the file mm — factor
    10 puts the reference at the file's numeric scale and the squared
    ``area_unit_factor`` 100 removes the cm²-vs-mm² area mismatch).
    ``auto`` infers the factor from the bbox diagonals and snaps it to
    ``AUTO_CANDIDATES`` within ``AUTO_TOLERANCE``; anything else raises
    :class:`NormalizationUncertain`. Forced ``1``/``10`` skip the
    confidence window (the operator owns the override; the measured
    diagonal ratio still travels in the record) and both report
    everything they apply.
    """
    raw = catpart_diag / reference_diag if catpart_diag > 0.0 and reference_diag > 0.0 else None
    if mode == "1" or mode == "10":
        factor = float(mode)
        return factor, {
            "resolution": "forced",
            "basis": "explicit-flag",
            "factor": factor,
            "area_unit_factor": factor * factor,
            "catpart_diagonal": catpart_diag,
            "reference_diagonal": reference_diag,
            "raw_diagonal_ratio": raw,
        }
    if mode != "auto":
        raise ValueError(f"unknown ref-scale mode: {mode!r}")
    if raw is None:
        raise NormalizationUncertain(
            "auto normalization needs positive bbox diagonals; a mesh "
            f"diagonal is {catpart_diag if catpart_diag <= 0 else reference_diag}",
            None,
        )
    best = min(AUTO_CANDIDATES, key=lambda candidate: abs(raw - candidate) / candidate)
    deviation = abs(raw - best) / best
    if deviation > AUTO_TOLERANCE:
        raise NormalizationUncertain(
            f"bbox-diagonal ratio {raw:.6f} sits {deviation:.1%} from the nearest "
            f"candidate {best} (candidates {AUTO_CANDIDATES} at ±{AUTO_TOLERANCE:.0%}); "
            "pass --ref-scale 1 or 10 to force the pairing",
            raw,
        )
    return best, {
        "resolution": "auto",
        "basis": "bbox-diagonal",
        "factor": best,
        "area_unit_factor": best * best,
        "catpart_diagonal": catpart_diag,
        "reference_diagonal": reference_diag,
        "raw_diagonal_ratio": raw,
        "candidate_deviation": deviation,
        "tolerance": AUTO_TOLERANCE,
    }


def scale_mesh(mesh: MeshData, factor: float) -> None:
    """In-place uniform vertex scaling (the normalization is applied to
    the reference mesh; in-place array mutation keeps the streaming
    memory shape — no copy of the vertex block)."""
    vertices = mesh.vertices
    for i in range(len(vertices)):
        vertices[i] *= factor


# --- the pair measurement ---------------------------------------------------


def measure_pair(
    catpart_path: Path,
    reference_path: Path,
    cell_size: float | None = None,
    ref_scale: str = "1",
) -> dict:
    """One full comparison: export the CATPart (the shipped seam), read
    the reference, resolve the per-pair normalization (W24), compute
    the metrics, return the outcome record.

    With ``ref_scale="1"`` (the default) nothing is scaled and every
    record equals the pre-W24 pairing. ``"auto"``/``"10"`` scale the
    REFERENCE by the resolved linear factor, so distances land in the
    CATPart's units; ``area_ratio`` is then the corrected ratio (the
    as-read one travels as ``area_ratio_raw``), and the factor plus its
    basis are REPORTED in the ``normalization`` block — never applied
    silently. An un-confident ``auto`` resolution is the named
    ``normalization-uncertain`` refusal (exit-code semantics carried by
    :func:`main`), never a guessed factor.

    Every non-metric outcome (export failure, empty mesh, STEP
    reference, unreadable reference, uncertain normalization) is a
    named outcome; the record always states which side is missing so a
    merge report cannot mistake a refusal for a passing delta.
    """
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="ground-truth-ply-") as scratch:
        ply_path = Path(scratch) / "catpart.ply"
        try:
            build_export(catpart_path, ply_path)
        except ExportError as exc:
            return {
                "outcome": OUTCOME_EXPORT_FAILURE,
                "error_class": exc.error_class,
                "detail": exc.detail,
                "catpart": str(catpart_path),
                "reference": str(reference_path),
            }
        except Exception as exc:  # noqa: BLE001 - the exporter's own contract
            return {
                "outcome": OUTCOME_EXPORT_FAILURE,
                "error_class": "export-crash",
                "detail": f"{type(exc).__name__}: {exc}",
                "catpart": str(catpart_path),
                "reference": str(reference_path),
            }
        catpart_mesh = _read_binary_le_ply(ply_path)

    if catpart_mesh.vertex_count == 0:
        return {
            "outcome": OUTCOME_EMPTY_MESH,
            "side": "catpart",
            "catpart": str(catpart_path),
            "reference": str(reference_path),
        }
    try:
        reference_mesh = read_reference_mesh(reference_path)
    except ValueError as exc:
        if reference_path.suffix.lower() == ".step" or reference_path.suffix.lower() == ".stp":
            return {
                "outcome": OUTCOME_STEP_REFUSED,
                "detail": str(exc),
                "catpart": str(catpart_path),
                "reference": str(reference_path),
            }
        return {
            "outcome": OUTCOME_UNREADABLE_REFERENCE,
            "detail": str(exc),
            "catpart": str(catpart_path),
            "reference": str(reference_path),
        }
    if reference_mesh.vertex_count == 0:
        return {
            "outcome": OUTCOME_EMPTY_MESH,
            "side": "reference",
            "catpart": str(catpart_path),
            "reference": str(reference_path),
        }

    catpart_diag = _bbox_diagonal(catpart_mesh)
    reference_diag = _bbox_diagonal(reference_mesh)
    try:
        factor, normalization = resolve_ref_scale(catpart_diag, reference_diag, ref_scale)
    except NormalizationUncertain as exc:
        return {
            "outcome": OUTCOME_NORMALIZATION_UNCERTAIN,
            "detail": str(exc),
            "ref_scale_mode": ref_scale,
            "raw_diagonal_ratio": exc.raw_ratio,
            "catpart": str(catpart_path),
            "reference": str(reference_path),
        }
    if factor != 1.0:
        scale_mesh(reference_mesh, factor)

    cell = cell_size if cell_size is not None else _bbox_diagonal(reference_mesh) / CELL_DIVISOR
    grid = VertexGrid(reference_mesh, cell)

    d_ab, chamfer_ab, hausdorff_ab = directed_distances(catpart_mesh, grid)
    d_ab_sorted = sorted(d_ab)
    d_ba, chamfer_ba, hausdorff_ba = directed_distances(reference_mesh, VertexGrid(catpart_mesh, cell))
    d_ba_sorted = sorted(d_ba)

    area_a = total_area(catpart_mesh)
    area_b = total_area(reference_mesh)
    area_unit = factor * factor
    return {
        "outcome": OUTCOME_METRICS,
        "catpart": str(catpart_path),
        "reference": str(reference_path),
        "catpart_vertices": catpart_mesh.vertex_count,
        "catpart_triangles": catpart_mesh.triangle_count,
        "reference_vertices": reference_mesh.vertex_count,
        "reference_triangles": reference_mesh.triangle_count,
        "area_catpart": area_a,
        "area_reference": area_b,
        "area_ratio": area_a / area_b if area_b else None,
        "area_ratio_raw": area_a / (area_b / area_unit) if area_b else None,
        "ref_scale_mode": ref_scale,
        "ref_scale_factor": factor,
        "area_unit_factor": area_unit,
        "raw_diagonal_ratio": normalization["raw_diagonal_ratio"],
        "normalization": normalization,
        "chamfer_ab": chamfer_ab,
        "chamfer_ba": chamfer_ba,
        "chamfer": (chamfer_ab + chamfer_ba) / 2.0,
        "hausdorff_ab_max": hausdorff_ab,
        "hausdorff_ba_max": hausdorff_ba,
        "hausdorff_max": max(hausdorff_ab, hausdorff_ba),
        "hausdorff_ab_p95": percentile(d_ab_sorted, 0.95),
        "hausdorff_ba_p95": percentile(d_ba_sorted, 0.95),
        "hausdorff_p95": max(percentile(d_ab_sorted, 0.95), percentile(d_ba_sorted, 0.95)),
        "cell_size": cell,
        "exact_nearest": True,
        "wall_seconds": round(time.monotonic() - started, 3),
        "peak_rss_mib": round(getrusage(RUSAGE_SELF).ru_maxrss / 1024, 1),
    }


# --- the selftest (the negative-fixture rule) -------------------------------

_SELFTEST_CUBE_TRIANGLES = (
    (0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7),
    (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
    (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7),
)


def _cube_mesh(scale: float = 1.0, shift: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> MeshData:
    corners = [
        (0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
        (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1),
    ]
    mesh = MeshData()
    for x, y, z in corners:
        mesh.vertices.extend(((x + shift[0]) * scale, (y + shift[1]) * scale, (z + shift[2]) * scale))
    for tri in _SELFTEST_CUBE_TRIANGLES:
        mesh.triangles.extend(tri)
    return mesh


def run_selftest() -> list[str]:
    """The pinned edges, on synthetic fixtures: identical meshes -> all
    zeros; translated -> Hausdorff == the shift; scaled 2x -> area_ratio
    == 4; the density blind spot; auto normalization infers x10 on a
    x10 pair (collapsing it to Hausdorff 0), refuses a ratio no
    candidate explains, and the forced mode reports its override.
    Returns the failure lines (empty = pass)."""
    failures: list[str] = []
    base = _cube_mesh()

    identical = _cube_mesh()
    grid = VertexGrid(identical, 0.25)
    d, mean, peak = directed_distances(base, grid)
    if peak > SELFTEST_TOL or abs(mean) > SELFTEST_TOL:
        failures.append(f"identical meshes must give 0 distances: mean={mean} max={peak}")
    ratio = total_area(base) / total_area(identical)
    if abs(ratio - 1.0) > SELFTEST_TOL:
        failures.append(f"identical meshes must give area_ratio 1.0: {ratio}")

    shifted = _cube_mesh(shift=(1.0, 0.0, 0.0))
    grid = VertexGrid(shifted, 0.25)
    _, _, peak = directed_distances(base, grid)
    if abs(peak - 1.0) > SELFTEST_TOL:
        failures.append(f"unit-shifted cube must give Hausdorff 1.0: {peak}")

    scaled = _cube_mesh(scale=2.0)
    ratio = total_area(scaled) / total_area(base)
    if abs(ratio - 4.0) > SELFTEST_TOL:
        failures.append(f"2x-scaled cube must give area_ratio 4.0: {ratio}")

    # The stated non-discrimination edge, pinned as a negative fixture:
    # a density-changed reference (same corner vertices, quadruple
    # triangle count) passes vertex Hausdorff AND is caught by area.
    dense = MeshData()
    dense.vertices.extend(base.vertices)  # same vertex set
    dense.triangles.extend(base.triangles)
    dense.triangles.extend(base.triangles)  # degenerate double-listing: area doubles, vertices identical
    _, _, peak = directed_distances(base, VertexGrid(dense, 0.25))
    if peak > SELFTEST_TOL:
        failures.append("vertex-identical density change must pass Hausdorff (this IS the blind spot)")
    if abs(total_area(dense) / total_area(base) - 2.0) > SELFTEST_TOL:
        failures.append("double-listed triangles must double the area (the area_ratio catch)")

    # The W24 normalization edges: auto infers the x10 reference scale
    # (the area unit travels as its square), the normalized pair
    # collapses to zero distance, a ratio no candidate explains is the
    # named refusal, and the forced mode reports its override.
    big, small = _cube_mesh(scale=10.0), _cube_mesh()
    factor, info = resolve_ref_scale(_bbox_diagonal(big), _bbox_diagonal(small), "auto")
    if factor != 10.0 or info["area_unit_factor"] != 100.0:
        failures.append(f"auto must infer 10 with area unit 100 on a x10 pair: {info}")
    scale_mesh(small, factor)
    _, mean, peak = directed_distances(big, VertexGrid(small, _bbox_diagonal(big) / CELL_DIVISOR))
    if peak > SELFTEST_TOL or abs(mean) > SELFTEST_TOL:
        failures.append(f"the x10 pair must collapse to 0 after normalization: mean={mean} max={peak}")

    try:
        resolve_ref_scale(_bbox_diagonal(_cube_mesh(scale=2.7)), _bbox_diagonal(base), "auto")
        failures.append("auto must refuse a diagonal ratio no candidate explains")
    except NormalizationUncertain:
        pass

    forced_factor, forced_info = resolve_ref_scale(
        _bbox_diagonal(_cube_mesh(scale=10.0)), _bbox_diagonal(_cube_mesh()), "10"
    )
    if (
        forced_factor != 10.0
        or forced_info["resolution"] != "forced"
        or abs(forced_info["raw_diagonal_ratio"] - 10.0) > SELFTEST_TOL
    ):
        failures.append(f"forced 10 must report the override and the measured ratio: {forced_info}")
    return failures


# --- the CLI ----------------------------------------------------------------

BATCH_COLUMNS = ("catpart_path", "reference_path", "outcome", "error_class", "area_ratio",
                 "chamfer", "chamfer_ab", "chamfer_ba", "hausdorff_max", "hausdorff_ab_max",
                 "hausdorff_ba_max", "hausdorff_p95", "hausdorff_ab_p95", "hausdorff_ba_p95",
                 "catpart_vertices", "catpart_triangles", "reference_vertices",
                 "reference_triangles", "cell_size", "wall_seconds", "peak_rss_mib",
                 "ref_scale_mode", "ref_scale_factor", "area_unit_factor",
                 "raw_diagonal_ratio", "area_ratio_raw")


def _append_csv_row(csv_path: Path, record: dict) -> None:
    fresh = not csv_path.is_file()
    with csv_path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=BATCH_COLUMNS, extrasaction="ignore")
        if fresh:
            writer.writeheader()
        writer.writerow({key: record.get(key, "") for key in BATCH_COLUMNS})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="benchmark_ground_truth",
        description="Reproducible .CATPart vs .STL/.OBJ ground-truth fidelity (streaming, exact vertex-set metrics).",
    )
    parser.add_argument("--catpart", type=Path, help="the .CATPart under test")
    parser.add_argument("--reference", type=Path, help="the reference .STL/.OBJ mesh")
    parser.add_argument("--cell-size", type=float, default=None, help="voxel cell override (default: reference bbox diagonal / 128)")
    parser.add_argument(
        "--ref-scale",
        choices=("auto", "1", "10"),
        default="1",
        help="per-pair normalization: scale the REFERENCE by the linear factor "
        "(auto infers it from the bbox diagonals and reports it; 1 = raw pairing; "
        "an un-confident auto ratio refuses as normalization-uncertain, exit 2)",
    )
    parser.add_argument("--batch", type=Path, help="pairs CSV (catpart_path,reference_path) streamed row by row")
    parser.add_argument("--csv", type=Path, default=None, help="append one metrics row per pair here")
    parser.add_argument("--selftest", action="store_true", help="run the pinned synthetic edges and exit")
    args = parser.parse_args(argv)

    if args.selftest:
        failures = run_selftest()
        for line in failures:
            print(f"selftest FAIL: {line}", file=sys.stderr)
        print(f"selftest: {'FAIL' if failures else 'ok'} (8 pinned edges)")
        return 1 if failures else 0

    pairs: list[tuple[Path, Path]] = []
    if args.batch is not None:
        with args.batch.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                pairs.append((Path(row["catpart_path"]), Path(row["reference_path"])))
    elif args.catpart is not None and args.reference is not None:
        pairs.append((args.catpart, args.reference))
    else:
        parser.error("need --catpart + --reference, or --batch, or --selftest")

    exit_code = 0
    for catpart_path, reference_path in pairs:
        if reference_path.suffix.lower() in (".step", ".stp"):
            record = {
                "outcome": OUTCOME_STEP_REFUSED,
                "detail": "STEP is B-rep, not tessellation: name a tessellated reference (.STL/.OBJ)",
                "catpart": str(catpart_path),
                "reference": str(reference_path),
            }
            exit_code = 2
        else:
            record = measure_pair(catpart_path, reference_path, args.cell_size, args.ref_scale)
            if record["outcome"] != OUTCOME_METRICS:
                exit_code = 2
        if args.csv is not None:
            _append_csv_row(args.csv, record)
        print(json.dumps(record, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
