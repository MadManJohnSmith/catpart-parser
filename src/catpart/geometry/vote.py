"""The facet-record ref-width vote and its battery (G3 stage-5 law).

ONE ranking for every candidate parse of every facet-record family —
the short-form strip records (u8/u16be/u24be, relaxed u16le for the
0x41/0x44 primitive), the extended 6-byte headers (0x47/0x4f) and the
P1g-escaped second pass (#64).  The law (stage-3b rule, extended
2026-11-11 stage 4b; the #62/#65/#66 amendments): each viable
(width, counts) parse of a record is scored by the tuple

    (exact tiling, out-of-bounds refs, repeated refs, non-coplanar
    normal-carrying loops, u16-over-u8, endian, width, counts length)

and the minimum wins; the winner's refs must then resolve in-bounds
(the #66 fail-closed post-vote gate — a record whose winning parse
leaves the element space is NOT this family).  Before #76 the
short-form vote ranked ``repeats`` above ``oob`` and never re-checked
the winner against the element space, so a big-endian misread could win
and reach ``_triangulate`` (the Audi R8 ``IndexError``); this module is
the single rank those amendments apply to, so the families cannot
drift apart again.

The scoring battery (the loop plane law and the U4-D dup-pin weld
targets) lives here too: the same battery scores a candidate's
skip-bearing loops on their dup-pinned coordinates during the vote
(the 2026-11-18 gap-edge width choice) and validates a dropped loop at
emission time (:func:`catpart.geometry.composite._e0b_dup_pin`).
"""

from __future__ import annotations

import dataclasses
import struct

#: Plane tolerance of the committed loop battery (stage 3b): the
#: per-coordinate normal distance bound; f32 coordinate rounding ~1e-4.
PLANE_TOL = 2e-3

_F32 = struct.Struct("<f")

# Candidate endians: ``little`` selects the u16 little-endian reading
# (#66, the relaxed 0x41/0x44 primitive); everything else is big-endian.


def f32_at(data, pos: int) -> float:
    """One little-endian f32 (the stored normals' coordinate type)."""
    return _F32.unpack_from(data, pos)[0]


def loop_plane_status(loop, normal, elements):
    """Coplanarity of one fully-resolved loop against the record's
    stored normal (the stage-3b battery criterion; ported from the
    stage-4b width re-test, ``not_manifold_audit.py``).  Returns
    ``("coplanar", 0.0)`` or ``("nonplanar", max_distance)``."""
    nn = (normal[0] ** 2 + normal[1] ** 2 + normal[2] ** 2) ** 0.5
    if nn == 0:
        return "nonplanar", 0.0
    pts = [elements[r][1] for r in loop]
    p0 = pts[0]
    worst = 0.0
    for p in pts[1:]:
        d = (
            (p[0] - p0[0]) * normal[0]
            + (p[1] - p0[1]) * normal[1]
            + (p[2] - p0[2]) * normal[2]
        ) / nn
        if abs(d) > worst:
            worst = abs(d)
        if abs(d) > PLANE_TOL:
            return "nonplanar", abs(d)
    return "coplanar", worst


def dup_pin_map(elements, loop):
    """The dup-pin weld targets for one loop — ``{skip_slot: written
    element}`` for every referenced skip slot — or ``None`` when a
    referenced skip slot has no preceding written element (unpinnable:
    the weld's fail-closed arm).

    The U4-D dup law (ported from the stage-4a decoder's ``dup_prev``,
    decode_curve_entries.py — not re-derived): a loop-referenced skip
    slot carries the bit-exact coordinates of the written vertex of its
    immediately preceding written element (the per-face copy — no new
    vertices)."""
    pin: dict[int, int] = {}
    for r in loop:
        if elements[r][1] is not None:
            continue
        j = r - 1
        while j >= 0 and elements[j][1] is None:
            j -= 1
        if j < 0:
            return None
        pin[r] = j
    return pin


def read_refs(data, start: int, n: int, width: int, little: bool):
    """``n`` refs of ``width`` bytes each at ``start`` (u8, u16be,
    u24be — or u16le for the relaxed primitive's ``little`` arm)."""
    if width == 1:
        return [data[start + j] for j in range(n)]
    if width == 2 and little:
        return [
            int.from_bytes(data[start + 2 * j : start + 2 * j + 2], "little")
            for j in range(n)
        ]
    return [
        int.from_bytes(data[start + width * j : start + width * (j + 1)], "big")
        for j in range(n)
    ]


def groups_repeat(refs, tri_count: int, counts):
    """Repeated references within a triangle (the first ``3 * tri_count``
    refs in 3-groups) or within a counts-delimited loop — the misread
    detector.  A legitimate record never repeats; the escaped-form
    family's strip joins are the #64 exception (repeats RANKED)."""
    for start in range(0, 3 * tri_count, 3):
        if len(set(refs[start : start + 3])) < 3:
            return True
    off = 3 * tri_count
    for c in counts:
        if c > 0 and len(set(refs[off : off + c])) < c:
            return True
        off += c
    return False


def refs_oob(refs, element_count) -> bool:
    """Any reference beyond the element space (the candidate's OOB
    rank slot; the #66 post-vote gate declines an OOB winner)."""
    return element_count is not None and any(r >= element_count for r in refs)


def loop_plane_penalty(refs, tri_count: int, counts, normal, elements, skips):
    """The battery's non-coplanar loop count for one candidate parse.

    Each counts-delimited loop (the triangles never take the plane
    battery) is tested against the record's stored normal when the
    element space is decoded; a loop landing on skip slots is tested on
    its dup-pinned coordinates (the same battery — the gap-edge width
    choice: a misread is nonplanar there, a real curve loop stays
    coplanar).  Untestable loops (out of the element space, or a skip
    slot with no preceding written element) stay silent."""
    nonplanar = 0
    if normal is None or elements is None:
        return 0
    off = 3 * tri_count
    for c in counts:
        loop = refs[off : off + c]
        off += c
        if not loop:
            continue
        if any(r >= len(elements) for r in loop):
            continue
        if any(r in skips for r in loop):
            pin = dup_pin_map(elements, loop)
            if pin is None:
                continue  # untestable: no battery
            test = [pin.get(r, r) for r in loop]
        else:
            test = loop
        st, _res = loop_plane_status(test, normal, elements)
        if st == "nonplanar":
            nonplanar += 1
    return nonplanar


@dataclasses.dataclass(frozen=True)
class WidthCandidate:
    """One viable (width, endian, counts) parse of a facet record.

    ``exact`` is the caller's boundary law (the short records end at
    the next strip header; the extended family ends exactly on the
    first candidate header at or after ``end`` — the #65 exception).
    ``tri_count`` is the extended family's leading independent
    triangles (0 on the short forms).  ``relaxed_u16`` arms the #66
    u16-over-u8 slot (the 0x41/0x44 primitive) and ``k`` feeds the
    short-form counts-length slot; the extended family leaves both 0.
    """

    width: int
    little: bool
    counts: tuple[int, ...]
    counts_end: int
    end: int
    exact: bool
    tri_count: int = 0
    relaxed_u16: bool = False
    k: int = 0


def _rank_key(candidate: WidthCandidate, oob: bool, repeats: bool, nonplanar: int):
    """The ONE rank tuple (see the module doc).  Every family's vote
    compares candidates through this builder, so a slot-order amendment
    lands on all of them at once (the #76 divergence class)."""
    return (
        0 if candidate.exact else 1,
        1 if oob else 0,
        1 if repeats else 0,
        nonplanar,
        # #66: the relaxed family's pinned primitive is u16
        # (little-endian first); u8 is its compact fallback, so a u16
        # reading that passes the gates outranks a u8 one.  Nothing
        # changes for the other markers (both slots stay 0).
        0 if (not candidate.relaxed_u16 or candidate.width == 2) else 1,
        1 if candidate.little else 0,
        # W7-B (2026-11-22): full ties prefer the WIDER candidate — the
        # narrow preference left the u8 half-read of a u16 stream
        # standing on the ties (Guntle/M3x16/LedStrips_5V's kept
        # over-use loops broke the L2 manifold gate; the wider readings
        # fix all three and keep every micro-batch file at PASS).
        255 - candidate.width,
        candidate.k,
    )


def vote_ref_width(
    data,
    n: int,
    candidates,
    element_count=None,
    normal=None,
    elements=None,
    repeats_ranked: bool = True,
):
    """The width vote over one record's viable candidates.

    Each candidate's refs are read and scored (repeats, OOB, the loop
    plane battery); a repeating candidate is declined outright when
    ``repeats_ranked`` is False (the #62 misread detector on the
    committed extended u8 reading — the #64/#65 fallback readings rank
    repeats instead).  Returns ``(refs, counts, width, end)`` of the
    winning parse, or ``None`` when no candidate survives — including
    the #66 post-vote gate: a winner whose refs leave the element space
    is NOT this family's record.  ``candidates`` may be any iterable;
    ties resolve to the first candidate in iteration order (the callers'
    width-ascending, big-endian-first enumeration)."""
    # The skip map feeds only the loop-plane battery, which is silent
    # without a stored normal: building it for every normal-less record
    # is O(records * elements) on the big stores (the 13bb LedStrips
    # profile). Lazy, never semantic.
    skips = (
        {i for i, (_v, pt) in enumerate(elements) if pt is None}
        if elements is not None and normal is not None
        else None
    )
    best = None
    best_key = None
    for cand in candidates:
        refs = read_refs(data, cand.counts_end, n, cand.width, cand.little)
        repeats = groups_repeat(refs, cand.tri_count, cand.counts)
        if repeats and not repeats_ranked:
            continue
        oob = refs_oob(refs, element_count)
        nonplanar = loop_plane_penalty(
            refs, cand.tri_count, cand.counts, normal, elements, skips
        )
        key = _rank_key(cand, oob, repeats, nonplanar)
        if best is None or key < best_key:
            best = (tuple(refs), cand.counts, cand.width, cand.end)
            best_key = key
    if best is None:
        return None
    refs = best[0]
    if refs_oob(refs, element_count):
        # Fail-closed refs gate (#66, 2026-11-20), the post-vote rule
        # every family shares: the winner's parse leaves the element
        # space, so the bytes are not this family's record.
        return None
    return best
