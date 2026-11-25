#!/usr/bin/env python3
"""W6 visual-QA sweep: select borderline meshes, export PLYs, render views.

Selection (the "used_written" rank = triangle_count + display_points +
display_segments from the W6 features JSONL — low writes are the
borderline cases where spaghetti/missing faces hide):
- corpus: the 50 parts with the lowest used_written (any family);
- Submarino: 25 lowest used_written among pass + 25 among non-pass.

Renders are the stdlib orthographic flat-shaded raster of the decoded PLY
(the G3 render_sanity_close seam — three views, PNG via zlib), NOT the
WASM viewer: no wasm-pack, no Chromium, no playwright during laya runs.
PLY export uses :func:`catpart.geometry.export.build_export` in-process
(the ``catpart-export`` seam) under an interpreter where ``catpart`` is
importable at the baseline commit; one file at a time with gc.

Usage:
  /path/to/venv/bin/python -B scripts/triage/w6_render_meshes.py \\
      --features ~/.local/state/catpart-parser/w6-laya/features.jsonl \\
      --out-dir ~/.local/state/catpart-parser/w6-laya/visual \\
      [--submarine-root <snapshot dir>]
"""

from __future__ import annotations

import argparse
import gc
import json
import struct
import sys
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_SUB_ROOT = Path.home() / (
    ".local/state/catpart-parser/bench-submarine/snapshot/"
    "submarine-ssk-tr-1700-s42-ara-san-juan-1.snapshot.20"
)
MAX_FILE_BYTES = 15 * 1024 * 1024  # anti-OOM: never load >15 MB parts


# ---- stdlib raster (verbatim seam from ~/.local/state/catpart-parser/
# render_sanity_close.py, the G3 close-sequence renders)


def parse_ply(path):
    with open(path, "rb") as fh:
        header = []
        while True:
            line = fh.readline().decode("ascii", "replace").strip()
            header.append(line)
            if line == "end_header":
                break
        if not (header and header[0] == "ply" and "binary_little_endian" in header[1]):
            raise ValueError(f"not a binary LE ply: {path}")
        elems = []
        for line in header:
            if line.startswith("element "):
                _, name, count = line.split()
                elems.append([name, int(count)])
        verts, tris = [], []
        for name, count in elems:
            if name == "vertex":
                for _ in range(count):
                    verts.append(struct.unpack("<3f", fh.read(12)))
            elif name == "face":
                for _ in range(count):
                    n = struct.unpack("<B", fh.read(1))[0]
                    idx = struct.unpack(f"<{n}i", fh.read(4 * n))
                    for k in range(1, n - 1):
                        tris.append((idx[0], idx[k], idx[k + 1]))
            else:
                raise ValueError(f"unknown element {name}")
    return verts, tris


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def render(verts, tris, view, size=480):
    if view == "front":
        R, U = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)
    elif view == "top":
        R, U = (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)
    else:
        R, U = (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)
    D = _cross(R, U)
    pts = [[_dot(v, R), _dot(v, U), _dot(v, D)] for v in verts]
    used = sorted({i for t in tris for i in t})
    if not used:
        return None  # nothing triangle-referenced to frame
    remap = {old: new for new, old in enumerate(used)}
    pts = [pts[i] for i in used]
    tris = [[remap[i] for i in t] for t in tris]

    def clamp(axis):
        vals = sorted(p[axis] for p in pts)
        k = max(0, int(len(vals) * 0.02))
        lo_v, hi_v = vals[k], vals[max(k, len(vals) - 1 - k)]
        span = (hi_v - lo_v) or 1.0
        pad = span * 0.05
        return lo_v - pad, hi_v + pad

    lo = tuple(clamp(a)[0] for a in range(3))
    hi = tuple(clamp(a)[1] for a in range(3))
    for p in pts:
        for a in range(3):
            p[a] = min(max(p[a], lo[a]), hi[a])
    span = max(hi[0] - lo[0], hi[1] - lo[1]) or 1.0
    scale = (size - 20) / span
    ox = (size - (hi[0] - lo[0]) * scale) / 2
    oy = (size - (hi[1] - lo[1]) * scale) / 2

    L = (0.4, 0.5, 0.77)
    tris_px = []
    for t in tris:
        a, b, c = pts[t[0]], pts[t[1]], pts[t[2]]
        n = _cross(_sub(b, a), _sub(c, a))
        ln = (n[0] ** 2 + n[1] ** 2 + n[2] ** 2) ** 0.5 or 1.0
        depth = (a[2] + b[2] + c[2]) / 3
        shade = abs(_dot(n, L)) / ln
        g = int(60 + 170 * shade)
        tris_px.append(
            (
                depth,
                [((p[0] - lo[0]) * scale + ox, size - ((p[1] - lo[1]) * scale + oy)) for p in (a, b, c)],
                (g, g, min(255, g + 12)),
            )
        )
    tris_px.sort(key=lambda x: -x[0])

    buf = bytearray([30, 34, 40]) * (size * size)
    for _, poly, col in tris_px:
        ys_ = [p[1] for p in poly]
        y0, y1 = max(0, int(min(ys_))), min(size - 1, int(max(ys_)) + 1)
        for y in range(y0, y1 + 1):
            xints = []
            for i in range(3):
                p1, p2 = poly[i], poly[(i + 1) % 3]
                if (p1[1] <= y <= p2[1]) or (p2[1] <= y <= p1[1]):
                    if p2[1] != p1[1]:
                        xints.append(p1[0] + (y - p1[1]) * (p2[0] - p1[0]) / (p2[1] - p1[1]))
            if len(xints) < 2:
                continue
            x0, x1 = sorted(xints)[:2]
            for x in range(max(0, int(x0)), min(size - 1, int(x1) + 1)):
                o = (y * size + x) * 3
                buf[o : o + 3] = bytes(col)
    raw = b"".join(b"\x00" + bytes(buf[y * size * 3 : (y + 1) * size * 3]) for y in range(size))

    def chunk(typ, data):
        c = struct.pack(">I", len(data)) + typ + data
        return c + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")


# ---- selection


def select(features_path: Path, sub_root: Path) -> list[dict]:
    """Stratified risk-surface selection for the visual sweep.

    v1 lesson: literal lowest-writes selection fills with empty rows
    (nothing written -> nothing to look at). Spaghetti (acc-Cont-Lft type)
    lives in mesh-bearing not-manifold keeps; missing faces hide in
    minimal-but-passing meshes. Batches cover that surface with clean
    controls on both sides.
    """
    recs = [json.loads(l) for l in features_path.read_text().splitlines() if l.strip()]
    corpus = [r for r in recs if r["source"] == "corpus" and r["size_bytes"] <= MAX_FILE_BYTES]
    sub = [r for r in recs if r["source"] == "submarine" and r["size_bytes"] <= MAX_FILE_BYTES]

    picked: list[dict] = []

    def take(pool, key, n, batch):
        for r in sorted(pool, key=key, reverse=True)[:n]:
            picked.append(dict(r, batch=batch))

    # Submarino: spaghetti suspects first (mesh-bearing manifold keeps),
    # force-including the reference case.
    acc = [r for r in sub if r["path"].endswith("acc-Cont-Lft.CATPart")]
    mesh_fails = [
        r
        for r in sub
        if r["failed_check"] == "not-manifold" and (r["triangle_count"] or 0) > 0 and r not in acc
    ]
    take(mesh_fails, lambda r: r["triangle_count"], 14, "sub-spaghetti-suspect")
    picked += [dict(r, batch="sub-spaghetti-suspect") for r in acc]
    take(
        [r for r in sub if r["failed_check"] == "degenerate-triangles"],
        lambda r: r["degenerate_triangle_count"],
        10,
        "sub-degenerate",
    )
    warned_pass = [r for r in sub if r["l2_status"] == "pass" and r["warnings"]]
    take(warned_pass, lambda r: len(r["warnings"]), 15, "sub-warned-pass")
    clean_pass = [r for r in sub if r["l2_status"] == "pass" and not r["warnings"]]
    take(clean_pass, lambda r: r["triangle_count"], 10, "sub-clean-pass")

    # Corpus: minimal-but-passing meshes (missing-face suspects), display
    # rows, big passes as solid controls, and the error families.
    tiny_pass = [
        r for r in corpus if r["l2_status"] == "pass" and 0 < (r["triangle_count"] or 0) <= 200
    ]
    take(tiny_pass, lambda r: -r["triangle_count"], 15, "corpus-tiny-pass")
    display = [r for r in corpus if r["failed_check"] == "empty-mesh"]
    take(display, lambda r: (r["display_points"] or 0) + (r["display_segments"] or 0), 10, "corpus-display")
    big_pass = [r for r in corpus if r["l2_status"] == "pass" and (r["triangle_count"] or 0) > 0]
    take(big_pass, lambda r: r["triangle_count"], 15, "corpus-big-pass")
    errors = [r for r in corpus if r["error_class"]]
    take(errors, lambda r: r["size_bytes"], 10, "corpus-error")

    for r in picked:
        if r["source"] == "submarine":
            r["abs_path"] = str(sub_root / r["path"])
    return picked


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--features", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path.home() / ".local/state/catpart-parser/w6-laya/visual")
    ap.add_argument("--submarine-root", type=Path, default=DEFAULT_SUB_ROOT)
    ap.add_argument(
        "--corpus-root",
        type=Path,
        default=REPO / "corpus",  # corpus binaries are never committed; pass
        # the parent checkout's corpus/ when sweeping from a worktree
    )
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    ply_dir = args.out_dir / "ply"
    png_dir = args.out_dir / "png"
    ply_dir.mkdir(exist_ok=True)
    png_dir.mkdir(exist_ok=True)

    picked = select(args.features, args.submarine_root)
    print(f"selected {len(picked)} meshes "
          f"({sum(1 for r in picked if r['batch'].startswith('corpus'))} corpus, "
          f"{sum(1 for r in picked if r['batch'].startswith('sub'))} submarine)", flush=True)

    # in-process export (the catpart-export seam); catpart importable here
    from catpart.geometry.export import build_export

    manifest_path = args.out_dir / "manifest.jsonl"
    with open(manifest_path, "w", encoding="utf-8") as mout:
        for i, r in enumerate(picked, 1):
            if r["source"] == "submarine" and not Path(r["abs_path"]).exists():
                print(f"  skip (missing): {r['path']}", flush=True)
                continue
            stem = f"{r['batch']}-{i:03d}"
            ply_path = ply_dir / f"{stem}.ply"
            rec = {
                "stem": stem,
                "batch": r["batch"],
                "source": r["source"],
                "path": r["path"],
                "fail_family": r["fail_family"],
                "l2_status": r["l2_status"],
                "triangle_count": r["triangle_count"],
                "display_points": r["display_points"],
                "display_segments": r["display_segments"],
                "warnings": r["warnings"],
                "size_bytes": r["size_bytes"],
            }
            try:
                if r["source"] == "submarine":
                    summary = build_export(Path(r["abs_path"]), ply_path)
                else:
                    summary = build_export(args.corpus_root / (r["local_path"] or f"corpus/{r['path']}"), ply_path)
                rec["export_triangles"] = summary.get("triangle_count")
                rec["export_error"] = None
            except Exception as exc:  # noqa: BLE001 — evidence note, not a crash
                rec["export_error"] = f"{type(exc).__name__}: {exc}"
                mout.write(json.dumps(rec, ensure_ascii=False) + "\n")
                print(f"  [{i}/{len(picked)}] export failed {r['path']}: {rec['export_error']}", flush=True)
                gc.collect()
                continue
            verts = tris = None
            views_ok = []
            try:
                verts, tris = parse_ply(ply_path)
                for view in ("front", "top", "side"):
                    png = render(verts, tris, view)
                    if png:
                        (png_dir / f"{stem}-{view}.png").write_bytes(png)
                        views_ok.append(view)
                rec["views"] = views_ok
                rec["ply_vertices"] = len(verts)
                rec["ply_triangles"] = len(tris)
            except Exception as exc:  # noqa: BLE001
                rec["views"] = []
                rec["render_error"] = f"{type(exc).__name__}: {exc}"
            del verts, tris
            gc.collect()
            mout.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(f"  [{i}/{len(picked)}] {stem} {r['path']} tris={rec.get('ply_triangles')} views={rec.get('views')}", flush=True)
    print(f"manifest -> {manifest_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
