"""The curve-entry (U4) skip-slot coordinate law and the ``33 3X`` curve records.

A4 (W16, marathon wave 4, 2026-11-22): the coordinate law of the
composite point region's skip slots — the elements the 2-bit table
marks ``1`` (no f32 words, composite.py) that facet loops reference as
vertices.  Every claim below is measured; the reproduction commands
live in ``docs/evidence/marathon/w16-progress.md`` and the committed
runner is ``scripts/triage/measure_u4_skip_law.py``.

- **The law (U4-D, dup-prev; established)**: a skip slot's coordinates
  are the BIT-EXACT coordinates of its immediately preceding written
  element — the per-face tessellation copy of the shared vertex the
  writer emitted just before the entry (the stage-4a decoder law,
  docs/evidence/2026-11-12-curve-entry-analysis.md section 3).
  Measured at this stage on the bench-external targets: **zero
  unpinnable slots** (every skip has a preceding written element) and
  every normal-carrying skip-referencing loop coplanar under the pin
  (Motor 669/669, Audi R8 8,992/8,992 first-pass unique; the corpus
  battery 95.6% minus the two defect stores, loc. cit.).
- **Hypothesis 1 (offset into neighbouring curve records /
  polylines) is refuted as a coordinate SOURCE and confirmed as
  CORROBORATION**: the ``33 3X`` records of the curve node following
  the list node carry per-curve data (18-30 B: a circle needs 18 B; a
  9-point ring discretization needs 108 B — the records cannot carry
  per-slot coordinates), and the edge polylines reference the same
  skip slots the facet loops do, tiling the same rings through the
  dup copies (the twin probes, loc. cit. section 4: 118/118 pinned
  positions invariant across the two saves).
- **Hypothesis 2 (inline compressed coordinate) is refuted**: the
  point region consumes exactly the declared write count on every
  walk-exact store (the table law), so no words are hidden in the
  region; the list node's trailing region is index/structure data
  (quantized u16 runs, not f32 triples — 026d6726: 568 B vs the
  312 B the 26 skips would need as triples, U2 stays open but holds
  no coordinates).
- **What the dropped loops actually are (the A4 finding)**: the
  ``curve-entry-loops-unexported`` population decomposes into
  (a) **degenerate-emission refusals** — dup-pinned loops one of whose
  strip triangles collapses (the writer's own degenerate-quad
  convention, e.g. ``(P, X, P, Y)`` = triangle ``(X, P, Y)``): their
  real surface is recoverable by the same G3 F7 skip-degenerate
  convention the primary path already applies
  (:func:`split_loop_triangles`); measured: Motor 11 loops -> 30
  triangles / 1,279 mm², Audi R8 20 loops -> 53 triangles /
  2,098,407 mm² (~5% of the part's mesh area);
  (b) **mesh-guard refusals** (edge over-use in the assembled mesh) —
  topology, not coordinates: no alternative pin changes them (the
  pin-independence probe, loc. cit. section 3: 0/52 rescued);
  (c) **declined extended-header records' skip-bearing members** —
  the 0x47/0x4f record-level decline, likewise not a coordinate
  question.  The weld lives in composite.py (W17's surface): this
  module provides the law the exporter consumes, not the emission.

The ``33 3X`` record model below is the stage-4a decoder's
(``scripts/triage/decode_curve_entries.py``, byte-measured on the
anchors): 7-B header ``<u8 a><u8 b><u16le id><00><u16le len>`` +
family ``33 3X`` + ``len`` payload bytes; ``33 37`` = 4 BE f32
``(cx, cy, cz, r)`` + 2-B trailer; ``33 33`` = 6 BE f32 (mid-ring,
``r`` negative on the anchors); ``33 38`` = 7 BE f32 + 2-B trailer;
``33 32`` = 2-B payload + 40-B f32le ``[P][Q][P]+|Q|`` block;
``33 36`` = 2-B payload.  Families beyond the geometry accessors stay
open (the decoder docstring's "point semantics beyond 33 37/33 33" —
unchanged).
"""

from __future__ import annotations

import math
import struct

#: Loop-coplanarity tolerance against a record's stored normal (the
#: weld battery's constant, composite.py — mirrored here so the law's
#: callers agree without importing the exporter).
PLANE_TOL = 2e-3

#: |distance(vertex, center) - |r||| tolerance for the ring
#: cross-check (f32 rounding; the stage-4a decoder's R_TOL).
R_TOL = 5e-3

_FAMILIES = (0x32, 0x33, 0x36, 0x37, 0x38)

_BE_F32 = struct.Struct(">f")
_F32 = struct.Struct("<f")
_U16LE = struct.Struct("<H")


def parse_curve_records(data, lo: int, hi: int) -> list[dict]:
    """Every ``33 3X`` record behind its 7-B header in ``data[lo:hi]``.

    Returns dicts ``{off, fam, a, b, id, len, payload}``.  A candidate
    is accepted when the family is known, the length is plausible
    (0 < len <= 256) and, for the BE-float families, the leading
    coordinates are finite and pool-scale — compressed streams carry
    ``33 3X`` byte pairs whose 'headers' decode as garbage and must
    not absorb the walk (the stage-4a decoder's sanity rule).
    """
    out: list[dict] = []
    p = lo
    while p < hi - 9:
        if data[p] == 0x33 and data[p + 1] in _FAMILIES:
            ln = int.from_bytes(data[p - 2 : p], "little")
            fam = data[p + 1]
            if 0 < ln <= 256:
                pay = data[p + 2 : p + 2 + ln]
                ok = True
                if fam in (0x33, 0x37, 0x38):
                    nbe = min((ln - 2) // 4, 4)
                    vals = [_BE_F32.unpack_from(pay, 4 * i)[0] for i in range(nbe)]
                    ok = all(math.isfinite(v) and abs(v) < 1e7 for v in vals)
                if ok:
                    out.append({
                        "off": p,
                        "fam": fam,
                        "a": data[p - 7],
                        "b": data[p - 6],
                        "id": int.from_bytes(data[p - 5 : p - 3], "little"),
                        "len": ln,
                        "payload": pay,
                    })
                    p += 2 + ln
                    continue
        p += 1
    return out


def circle_of(rec: dict) -> tuple[float, float, float, float] | None:
    """``(cx, cy, cz, r)`` of a ``33 37``/``33 33`` record, or ``None``."""
    if rec["fam"] not in (0x33, 0x37):
        return None
    nbe = (rec["len"] - 2) // 4
    if (rec["fam"] == 0x33 and nbe < 6) or (rec["fam"] == 0x37 and nbe < 4):
        return None
    v = [_BE_F32.unpack_from(rec["payload"], 4 * i)[0] for i in range(nbe)]
    r = v[5] if rec["fam"] == 0x33 else v[3]
    return v[0], v[1], v[2], r


def line_of(rec: dict) -> tuple[tuple[float, ...], tuple[float, ...]] | None:
    """``(P, Q)`` of a ``33 32`` line record's 40-B f32le block, or ``None``.

    The block reads ``[P][Q][P]+|Q|`` (G2 law): the first triple at
    +0x00 and the second at +0x0C of the payload's float block.
    """
    if rec["fam"] != 0x32 or rec["len"] < 42:
        return None
    vals = struct.unpack_from("<9f", rec["payload"], 2)
    return vals[0:3], vals[3:6]


def pin_skips(elements: list[tuple[int, tuple[float, float, float] | None]]):
    """The U4-D dup law: pin every skip slot to its preceding write.

    ``elements`` is the composite element space in region order
    (``(table_value, point_or_None)``).  Returns
    ``(pins, kinds)`` where ``pins[i]`` is the pinned ``(x, y, z)`` of
    skip ``i`` (``None`` when no preceding written element exists —
    the unpinned class, measured absent on the targets and the corpus
    exported set) and ``kinds[i]`` is ``"dup"``.
    """
    pins: dict[int, tuple[float, float, float]] = {}
    kinds: dict[int, str] = {}
    prev = None
    for i, (_v, pt) in enumerate(elements):
        if pt is not None:
            prev = pt
        else:
            pins[i] = prev
            kinds[i] = "dup"
    return pins, kinds


def unpinned_skips(elements, pins) -> list[int]:
    """Skip slots the dup law cannot pin (no preceding written element)."""
    return [i for i, (_v, pt) in enumerate(elements) if pt is None and pins.get(i) is None]


def loop_pinned_points(loop, elements, pins):
    """Dup-pinned point per reference (``None`` where unresolvable).

    A reference past the element space (or an unpinnable skip) yields
    ``None`` — the caller fails that loop closed, mirroring the weld's
    pinnability gate.
    """
    pts = []
    for r in loop:
        if 0 <= r < len(elements):
            _v, pt = elements[r]
            if pt is not None:
                pts.append(pt)
                continue
            pin = pins.get(r)
            if pin is None:
                return None
            pts.append(pin)
        else:
            return None
    return pts


def plane_residual(points, normal) -> float | None:
    """Max |signed distance| of ``points`` from the plane through
    ``points[0]`` with unit ``normal`` (``None`` for a zero normal)."""
    nn = math.sqrt(sum(n * n for n in normal))
    if nn == 0.0 or not points:
        return None
    p0 = points[0]
    return max(
        abs(sum((q[i] - p0[i]) * normal[i] for i in range(3))) / nn
        for q in points[1:]
    )


def loop_is_battery_supported(normal, pinned_points) -> bool:
    """The weld's battery: no stored normal, or pinned points coplanar.

    Mirrors composite.py's per-loop gate (a normal-less record is
    accepted untested — 90% of the dropped-loop population; a
    normal-carrying one must be coplanar at :data:`PLANE_TOL`).
    """
    if normal is None:
        return True
    res = plane_residual(pinned_points, normal)
    return res is not None and res <= PLANE_TOL


def loop_triangles(mk: int, loop_len: int) -> list[tuple[int, int, int]]:
    """A loop's triangle POSITIONS under its marker family's convention.

    Strips (``0x42``/``0x49``/``0x4a``) fan consecutive triples;
    polygon fans (``0x4c`` and the relaxed ``0x41``/``0x44``
    primitives) fan from the first position.  Positions index the
    loop (0-based), so a loop that references the same element twice
    keeps its two positions distinct — the degenerate split reads the
    pinned coordinates, not the refs.
    """
    if mk in (0x41, 0x44, 0x4C):
        return [(0, i, i + 1) for i in range(1, loop_len - 1)]
    return [(i, i + 1, i + 2) for i in range(loop_len - 2)]


def _tri_is_degenerate(a, b, c) -> bool:
    """The G3 F7 degenerate convention: repeated coordinates or a
    zero-area cross product."""
    if a == b or b == c or a == c:
        return True
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    cx, cy, cz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    return cx == 0.0 and cy == 0.0 and cz == 0.0


def split_loop_triangles(mk: int, loop, pinned_points):
    """Dup-pinned emission with the degenerate split (the A4 law).

    ``pinned_points`` aligns with ``loop`` position-wise (the element
    references' dup-pinned coordinates — :func:`loop_pinned_points`).
    Returns ``(real, degenerate)``: the triangles the writer's
    degenerate-quad convention collapses (a dup pin repeated inside
    the loop, e.g. the quad ``(P, X, P, Y)`` = triangle ``(X, P, Y)``
    plus a collapsed half) are split off instead of refusing the loop
    — the same G3 F7 skip convention the primary strips apply.
    ``real`` carries ``(element_triple, area)``; ``degenerate`` the
    collapsed element triples.  ``None`` coordinates (an unresolvable
    reference) fail the loop closed: everything lands in
    ``degenerate`` with a ``None`` marker triple.
    """
    real = []
    degen = []
    for i, j, k in loop_triangles(mk, len(loop)):
        pa, pb, pc = pinned_points[i], pinned_points[j], pinned_points[k]
        if pa is None or pb is None or pc is None:
            degen.append((loop[i], loop[j], loop[k]))
            continue
        if _tri_is_degenerate(pa, pb, pc):
            degen.append((loop[i], loop[j], loop[k]))
        else:
            real.append(((loop[i], loop[j], loop[k]), _tri_area(pa, pb, pc)))
    return real, degen


def _tri_area(a, b, c) -> float:
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    cx, cy, cz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    return 0.5 * math.sqrt(cx * cx + cy * cy + cz * cz)


def ring_cross_check(records, elements) -> tuple[int, int]:
    """Curve-record corroboration: ``33 37`` circles vs written rings.

    Groups the written points by ``(z, radius-about-the-circles'
    centroid)`` (the stage-4a cross-check) and counts how many circles
    match some written ring within the f32 tolerances.  Returns
    ``(matched, total)`` — the rate says the records describe the same
    curves the dup copies tile (corroboration, not a coordinate
    source).  ``total`` is 0 when the records carry no circles.
    """
    circles = [c for c in (circle_of(r) for r in records) if c is not None]
    if not circles:
        return 0, 0
    written = [pt for _v, pt in elements if pt is not None]
    cx = sum(c[0] for c in circles) / len(circles)
    cy = sum(c[1] for c in circles) / len(circles)
    rings: dict[tuple[float, float], int] = {}
    for p in written:
        key = (round(p[2], 3), round(math.hypot(p[0] - cx, p[1] - cy), 3))
        rings[key] = rings.get(key, 0) + 1
    matched = 0
    for _cx0, _cy0, cz0, r0 in circles:
        for (zr, rr) in rings:
            if abs(zr - cz0) <= 2e-3 and abs(rr - abs(r0)) <= R_TOL:
                matched += 1
                break
    return matched, len(circles)
