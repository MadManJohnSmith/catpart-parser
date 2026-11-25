"""Compact ``CATSeeBodyCont`` CAT3DFaceGP decoder (W26 C06, 2026-11-24).

The official ``empty-mesh`` parts carry a compact face-GP stream inside
``CATSeeBodyCont`` / ``CATBRepModeContainer`` regions: a declared vertex
region whose 2-bit LCP table writes only the coordinates that changed
since the previous vertex, followed immediately by ``0x51`` face-GP (and
``0x50`` counter-table) records over that node's own element space.  The
nested-store route finds no 01 06 pool in these parts, so the regular
composite, facet, surface, grid and CATSurfacicRep routes all stay empty;
this module decodes the compact stream directly.

Format law (verified byte-exact on the W26 C06 samples; the corpus-wide
census is in ``docs/evidence/2026-11-24-seebody-compact-face-gp.md``):

1. The vertex region opens inside a ``04 04 fd ff`` node with a
   ``ff ff 02 00 <n_floats@P1g>`` token (``n_verts = n_floats // 3``),
   a header containing ``a5 d4 68 53`` (preceded by ``sag=0.2f`` and
   ``angle=pi/4``), ``ceil(n_verts / 4)`` bytes of the 2-bit LCP table
   (``SHAPES = {0: 3, 1: 0, 2: 1, 3: 2}``: full write, keep, only
   ``z``, only ``y``/``z``), a ``u32le write_count`` that must equal
   ``sum(SHAPES[v])`` (the strict walk-exact gate), and
   ``write_count * f32le`` coordinate words.
2. ``0x51`` records: optional ``[0x20|0x30] 04 04 ff ff <B><G><R>``
   graphic attribute header, ``51``, ``u32le id``, ``02 00 33 32``,
   40B bbox/sphere, ``u16be kind == 3``, ``3 * u8`` counts
   (N_tris, N_strips, N_fans), an 8B normal block, ``3 * N_tris``
   refs, then per strip/fan a width-matched count and refs, then ``00``.
3. ``0x50`` records: the same optional color header, ``50``,
   ``u32le id``, 2B, 40B bbox/sphere, ``u16be kind == 0``, the
   counts, 2B flag, refs/counts as above, then ``00``.
4. Reference width is 1 (u8) when ``n_verts <= 255``, 2 (u16be)
   otherwise.  A reference to a written element resolves directly; a
   reference to a missing element resolves to the immediately preceding
   written element (the LCP keep-slot convention).

Fail-closed: a node that does not walk exact is skipped, a record that
does not close byte-exact is not emitted, every emitted member passes the
incremental :class:`catpart.geometry.mesh.EdgeGuard`, and the whole scan
returns ``None`` unless the merged triangle soup is non-empty and
manifold.  ``tri_colors`` carries the per-triangle native CATIA BGR
decoded to RGB (``<B><G><R>`` header bytes read back as ``(R, G, B)``),
defaulting to the CATIA V5 lavender-gray ``(210, 210, 255)``.
"""

from __future__ import annotations

import dataclasses
import re
import struct

from catpart.geometry import composite, mesh

SOURCE = "seebody-compact-face-gp"

SHAPES = {0: 3, 1: 0, 2: 1, 3: 2}
DEFAULT_COLOR = (210, 210, 255)
#: Walk-exact node bound (anti-OOM): the declared vertex count must stay
#: inside a part-scale envelope before the LCP table's slot list is built.
MAX_VERTS = 3_000_000
_TAG_51_RE = re.compile(rb"\x02\x00\x33\x32")
_TAG_50_RE = re.compile(rb"[\x20\x30]\x04\x04\xff\xff.{3}\x50", re.DOTALL)
_TERM_RE = re.compile(rb"[\x20\x30]\x04\x04\xff\xff.{3}\x00", re.DOTALL)


@dataclasses.dataclass(frozen=True)
class SeeBodyScan:
    """One part's compact see-body decode."""

    vertices: tuple[tuple[float, float, float], ...]
    triangles: tuple[tuple[int, int, int], ...]
    tri_colors: tuple[tuple[int, int, int], ...]
    nodes: int
    records_total: int
    records_exact_close: int
    records_accepted: int
    degenerate_filtered: int


def _read_p1g(data: bytes, p: int) -> tuple[int, int]:
    if data[p] == 0xFF:
        return int.from_bytes(data[p + 1 : p + 5], "little"), p + 5
    return data[p], p + 1


def _find_cgr_nodes(data: bytes):
    nodes = []
    pos = 0
    n = len(data)
    while True:
        npos = data.find(b"\x04\x04\xfd\xff", pos)
        if npos < 0:
            break
        tok = data.find(b"\xff\xff\x02\x00", npos + 4, min(n, npos + 64))
        if tok >= 0 and tok + 5 <= n:
            try:
                n_floats, p2 = _read_p1g(data, tok + 4)
            except (IndexError, struct.error):
                pos = npos + 4
                continue
            if n_floats > 0 and n_floats % 3 == 0 and n_floats // 3 <= MAX_VERTS:
                n_verts = n_floats // 3
                sig = data.find(b"\xa5\xd4\x68\x53", p2, min(n, p2 + 32))
                if sig >= 0:
                    tab_start = sig + 5
                    tab_len = (n_verts + 3) // 4
                    wc_pos = tab_start + tab_len
                    if wc_pos + 4 <= n:
                        wc = int.from_bytes(data[wc_pos : wc_pos + 4], "little")
                        slots = []
                        for i in range(tab_start, tab_start + tab_len):
                            b = data[i]
                            slots += [
                                (b >> 0) & 3,
                                (b >> 2) & 3,
                                (b >> 4) & 3,
                                (b >> 6) & 3,
                            ]
                        slots = slots[:n_verts]
                        if wc == sum(SHAPES[v] for v in slots) and wc_pos + 4 + 4 * wc <= n:
                            fp = wc_pos + 4
                            x = y = z = 0.0
                            elems = []
                            ok = True
                            for v in slots:
                                sh = SHAPES[v]
                                if sh == 0:
                                    elems.append((v, None))
                                    continue
                                if sh == 3:
                                    x, y, z = struct.unpack_from("<fff", data, fp)
                                    fp += 12
                                elif sh == 2:
                                    y, z = struct.unpack_from("<ff", data, fp)
                                    fp += 8
                                else:
                                    (z,) = struct.unpack_from("<f", data, fp)
                                    fp += 4
                                if not (composite._nice(x) and composite._nice(y) and composite._nice(z)):
                                    ok = False
                                    break
                                elems.append((v, (x, y, z)))
                            if ok:
                                nodes.append((npos, n_verts, fp, elems))
        pos = npos + 4
    return nodes


def _scan(data: bytes) -> SeeBodyScan | None:
    nodes = _find_cgr_nodes(data)
    if not nodes:
        return None
    all_pts: list[tuple[float, float, float]] = []
    all_tris: list[tuple[int, int, int]] = []
    all_cols: list[tuple[int, int, int]] = []
    tot_recs = tot_exact = tot_acc = tot_degenerate = 0

    for ni, (npos, n_verts, fend, elems) in enumerate(nodes):
        hi = nodes[ni + 1][0] if ni + 1 < len(nodes) else len(data)
        width = 1 if n_verts <= 255 else 2
        events = []
        for m in _TAG_51_RE.finditer(data, fend, hi):
            o = m.start()
            if o >= fend + 5 and data[o - 5] == 0x51 and o + 49 <= hi and data[o + 44 : o + 46] == b"\x00\x03":
                has_col = (
                    o >= fend + 13
                    and data[o - 13] in (0x20, 0x30)
                    and data[o - 12 : o - 8] == b"\x04\x04\xff\xff"
                )
                rstart = o - 13 if has_col else o - 5
                rgb = (data[o - 6], data[o - 7], data[o - 8]) if has_col else None
                events.append((rstart, 0x51, o + 44, rgb))
        for m in _TAG_50_RE.finditer(data, fend, hi):
            o = m.start()
            if o + 15 > hi:
                continue
            extra = int.from_bytes(data[o + 13 : o + 15], "little")
            if extra > 256:
                continue
            kind_off = o + 55 + extra
            if kind_off + 7 <= hi and data[kind_off : kind_off + 2] == b"\x00\x00":
                rgb = (data[o + 7], data[o + 6], data[o + 5])
                events.append((o, 0x50, kind_off, rgb))
        terms = [m.start() for m in _TERM_RE.finditer(data, fend, hi)]
        events.sort()

        written_rank: dict[int, int] = {}
        points: list[tuple[float, float, float]] = []
        for i, (_v, pt) in enumerate(elems):
            if pt is not None:
                written_rank[i] = len(points)
                points.append(pt)

        def _resolve(r: int) -> int | None:
            if r >= n_verts:
                return None
            if elems[r][1] is not None:
                return written_rank[r]
            j = r - 1
            while j >= 0 and elems[j][1] is None:
                j -= 1
            return written_rank[j] if j >= 0 else None

        def _read_ref(p: int) -> tuple[int, int]:
            if width == 1:
                return data[p], p + 1
            return int.from_bytes(data[p : p + 2], "big"), p + 2

        guard = mesh.EdgeGuard()
        node_tris: list[tuple[int, int, int]] = []
        node_cols: list[tuple[int, int, int]] = []
        last_rgb = DEFAULT_COLOR
        tot_recs += len(events)

        for idx, (rstart, flag, kind_off, rgb) in enumerate(events):
            if rgb is not None:
                last_rgb = rgb
            rend = events[idx + 1][0] if idx + 1 < len(events) else hi
            for tm in terms:
                if rstart < tm < rend:
                    rend = tm
                    break
            n_tris = data[kind_off + 2]
            n_strips = data[kind_off + 3]
            n_fans = data[kind_off + 4]
            p = kind_off + 5 + (8 if flag == 0x51 else 2)
            rec_tris: list[tuple[int, int, int]] = []
            rec_degenerate = 0
            ok = True
            for _ in range(n_tris):
                if p + 3 * width > rend:
                    ok = False
                    break
                a, p = _read_ref(p)
                b, p = _read_ref(p)
                c, p = _read_ref(p)
                ra, rb, rc = _resolve(a), _resolve(b), _resolve(c)
                if ra is None or rb is None or rc is None:
                    ok = False
                    break
                if ra != rb and rb != rc and ra != rc:
                    rec_tris.append((ra, rb, rc))
                else:
                    rec_degenerate += 1
            if ok and (n_strips > 0 or n_fans > 0):
                if p + (n_strips + n_fans) * width > rend:
                    ok = False
                else:
                    cnts = []
                    for _ in range(n_strips + n_fans):
                        c = data[p] if width == 1 else int.from_bytes(data[p : p + 2], "big")
                        p += width
                        cnts.append(c)
                    for s_i, c in enumerate(cnts):
                        if c < 3 or p + c * width > rend:
                            ok = False
                            break
                        rloop = []
                        for _j in range(c):
                            r, p = _read_ref(p)
                            rr = _resolve(r)
                            if rr is None:
                                ok = False
                                break
                            rloop.append(rr)
                        if not ok:
                            break
                        kind_m = 0x42 if s_i < n_strips else 0x4C
                        t, degenerate = composite._loop_triangles(kind_m, rloop, points)
                        rec_tris.extend(t)
                        rec_degenerate += degenerate
            if ok and p in (rend, rend - 1):
                tot_exact += 1
            if ok and p in (rend, rend - 1) and rec_tris and guard.admit(rec_tris):
                node_tris.extend(rec_tris)
                node_cols.extend([last_rgb] * len(rec_tris))
                tot_degenerate += rec_degenerate
                tot_acc += 1

        if node_tris:
            base = len(all_pts)
            all_pts.extend(points)
            all_tris.extend((a + base, b + base, c + base) for a, b, c in node_tris)
            all_cols.extend(node_cols)

    if not all_tris or not mesh.mesh_stats(all_tris).manifold:
        return None
    return SeeBodyScan(
        vertices=tuple(all_pts),
        triangles=tuple(all_tris),
        tri_colors=tuple(all_cols),
        nodes=len(nodes),
        records_total=tot_recs,
        records_exact_close=tot_exact,
        records_accepted=tot_acc,
        degenerate_filtered=tot_degenerate,
    )


def scan_part(data: bytes) -> SeeBodyScan | None:
    """Decode a part's compact see-body face-GP nodes, fail-closed."""
    try:
        return _scan(data)
    except (IndexError, struct.error, ValueError):
        return None


def warning_detail(scan: SeeBodyScan) -> str:
    """The summary warning's prose (the counters the scan measured)."""
    detail = (
        f"{scan.nodes} compact see-body node(s), "
        f"{scan.records_accepted}/{scan.records_total} face record(s) "
        f"accepted ({scan.records_exact_close} byte-exact closures), "
        f"{len(scan.vertices)} vertices, {len(scan.triangles)} triangles: "
        "the declared vertex region's 2-bit LCP table walk-exact gate, "
        "the per-record byte-exact closure gate and the incremental "
        "edge guard (docs/evidence/2026-11-24-seebody-compact-face-gp.md)"
    )
    if scan.degenerate_filtered:
        detail += (
            f"; {scan.degenerate_filtered} collapsed (zero-area or "
            "repeated-coordinate) member triangle(s) skipped by the "
            "strip/fan law"
        )
    return detail
