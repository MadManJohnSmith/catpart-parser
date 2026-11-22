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
CATPart-side signal. ``--selftest`` pins all three edges on synthetic
fixtures (the negative-fixture rule) and is what CI runs.

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

#: The voxel grid's default cell: the reference bbox diagonal / this.
CELL_DIVISOR = 128

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
    'solid'). ASCII vertices are deduplicated by rounding key so the
    per-facet duplication does not triple the vertex set."""
    mesh = MeshData()
    size = path.stat().st_size
    with path.open("rb") as fh:
        head = fh.read(84)
        if len(head) == 84:
            (count,) = struct.unpack("<I", head[80:84])
            if size == 84 + 50 * count:
                raw = fh.read(50 * count)
                verts: dict[tuple[int, int, int], int] = {}
                for i in range(count):
                    record = raw[i * 50 : (i + 1) * 50]
                    xyz = struct.unpack("<12f", record[:48])
                    for j in (3, 6, 9):
                        mesh.triangles.append(_stl_vertex(mesh, verts, xyz[j : j + 3]))
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
    """OBJ: ``v x y z`` vertices (kept in order), ``f a/b/c ...`` faces
    with 1-based (possibly negative) indices, n-gons fan-triangulated."""
    mesh = MeshData()
    raw_vertices: list[tuple[float, float, float]] = []
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            parts = line.split()
            if len(parts) >= 4 and parts[0] == "v":
                raw_vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
            elif len(parts) >= 4 and parts[0] == "f":
                indices = []
                for token in parts[1:]:
                    field = token.split("/")[0]
                    i = int(field)
                    i = len(raw_vertices) + i + 1 if i < 0 else i - 1
                    indices.append(i)
                for k in range(1, len(indices) - 1):
                    mesh.triangles.extend((indices[0], indices[k], indices[k + 1]))
    for xyz in raw_vertices:
        mesh.vertices.extend(xyz)
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


# --- the pair measurement ---------------------------------------------------


def measure_pair(catpart_path: Path, reference_path: Path, cell_size: float | None = None) -> dict:
    """One full comparison: export the CATPart (the shipped seam), read
    the reference, compute the metrics, return the outcome record.

    Every non-metric outcome (export failure, empty mesh, STEP
    reference) is a named outcome with exit-code semantics carried by
    :func:`main`; the record always states which side is missing so a
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

    cell = cell_size if cell_size is not None else _bbox_diagonal(reference_mesh) / CELL_DIVISOR
    grid = VertexGrid(reference_mesh, cell)

    d_ab, chamfer_ab, hausdorff_ab = directed_distances(catpart_mesh, grid)
    d_ab_sorted = sorted(d_ab)
    d_ba, chamfer_ba, hausdorff_ba = directed_distances(reference_mesh, VertexGrid(catpart_mesh, cell))
    d_ba_sorted = sorted(d_ba)

    area_a = total_area(catpart_mesh)
    area_b = total_area(reference_mesh)
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
    == 4. Returns the failure lines (empty = pass)."""
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
    return failures


# --- the CLI ----------------------------------------------------------------

BATCH_COLUMNS = ("catpart_path", "reference_path", "outcome", "error_class", "area_ratio",
                 "chamfer", "chamfer_ab", "chamfer_ba", "hausdorff_max", "hausdorff_ab_max",
                 "hausdorff_ba_max", "hausdorff_p95", "hausdorff_ab_p95", "hausdorff_ba_p95",
                 "catpart_vertices", "catpart_triangles", "reference_vertices",
                 "reference_triangles", "cell_size", "wall_seconds", "peak_rss_mib")


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
    parser.add_argument("--batch", type=Path, help="pairs CSV (catpart_path,reference_path) streamed row by row")
    parser.add_argument("--csv", type=Path, default=None, help="append one metrics row per pair here")
    parser.add_argument("--selftest", action="store_true", help="run the pinned synthetic edges and exit")
    args = parser.parse_args(argv)

    if args.selftest:
        failures = run_selftest()
        for line in failures:
            print(f"selftest FAIL: {line}", file=sys.stderr)
        print(f"selftest: {'FAIL' if failures else 'ok'} (5 pinned edges)")
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
            record = measure_pair(catpart_path, reference_path, args.cell_size)
            if record["outcome"] != OUTCOME_METRICS:
                exit_code = 2
        if args.csv is not None:
            _append_csv_row(args.csv, record)
        print(json.dumps(record, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
