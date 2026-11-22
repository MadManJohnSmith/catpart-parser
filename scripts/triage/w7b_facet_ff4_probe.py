#!/usr/bin/env python3
"""W7-B triage probe: the facet_headers ff-at-+4 divergence (the head_ia
61/62-decline root cause, 2026-11-22).

The twins disagree on 6-byte facet-header candidates whose bytes carry
``ff`` at BOTH +4 and +5 (``01 [41-4f] . . ff ff``):

- Python ``facets.facet_headers`` matches the record with
  ``FACET_HEADER_RE`` (the 6-byte alternative needs ``ff`` at +5) but
  filters with ``header_len(data, m.start()) == 6`` — and
  ``header_len`` derives the length ff-first over (4, 5, 6), so ``ff``
  at +4 wins and the position is DROPPED (it is a 5-byte variant
  there, the observed 0x4b/0x4e gap form).
- The Rust ``facets::facet_headers`` decides via ``header_form_len``
  (+3, then +5 — it never consults +4) and keeps the position as a
  6-byte candidate.

A kept position is never a record (``parse_extended_facet_records``
re-derives ``header_len == 6`` and skips it), but it corrupts the
candidate-boundary bookkeeping: ``nxt``/``nxt_eff``/``exact`` see a
phantom header, so a width vote can flip (the head_ia record at
229,647,190 voted u8 on Python, u24be on Rust — the +1 decline, the
+352 triangles and the 61/62 counters of the corpus-wide divergence).

The probe scans one file's composite regions with BOTH twins' discovery
semantics and reports every position where they differ. Exit 0 with no
diffs (parity), exit 1 with diffs printed (the Rust side would keep
positions Python drops).

Usage: python3 scripts/triage/w7b_facet_ff4_probe.py <file.catpart>
"""

import re
import sys

FACET_HEADER_RE = re.compile(rb"\x01[\x41-\x4f](?:.\xff|...\xff)", re.DOTALL)


def header_len(data: bytes, o: int) -> int | None:
    """The twin's facets.header_len: the first of (4, 5, 6) whose byte
    is ``ff``."""
    for length in (4, 5, 6):
        if data[o + length - 1] == 0xFF:
            return length
    return None


def facet_headers_py(data: bytes, lo: int, hi: int) -> list[int]:
    """Python semantics: FACET_HEADER_RE matches, filtered to
    ``header_len == 6``."""
    return [
        m.start()
        for m in FACET_HEADER_RE.finditer(data, lo, hi)
        if header_len(data, m.start()) == 6
    ]


def _form_len(data: bytes, i: int, hi: int) -> int | None:
    """Rust ``header_form_len`` verbatim: +3, then +5 — never +4."""
    if i + 4 > hi or data[i] != 0x01 or not (0x41 <= data[i + 1] <= 0x4F):
        return None
    if data[i + 3] == 0xFF:
        return 4
    if i + 6 <= hi and data[i + 5] == 0xFF:
        return 6
    return None


def facet_headers_rs(data: bytes, lo: int, hi: int) -> list[int]:
    """Rust semantics (pre-fix): the leftmost scan consuming 4/6 bytes."""
    out: list[int] = []
    i = lo
    while i + 4 <= hi:
        f = _form_len(data, i, hi)
        if f == 6:
            out.append(i)
            i += 6
        elif f is not None:
            i += f
        else:
            i += 1
    return out


def main() -> int:
    path = sys.argv[1]
    data = open(path, "rb").read()
    # The divergence only matters inside composite facet regions; a
    # whole-file scan over-approximates (report + region note), which is
    # enough to localize the phantom boundaries for the decoder logs.
    lo, hi = 0, len(data)
    py = facet_headers_py(data, lo, hi)
    rs = facet_headers_rs(data, lo, hi)
    only_rs = sorted(set(rs) - set(py))
    only_py = sorted(set(py) - set(rs))
    for p in only_rs:
        print(f"RS-ONLY {p}: {data[p:p + 6].hex(' ')}  "
              f"(ff at +4: {data[p + 4] == 0xFF}, ff at +5: {data[p + 5] == 0xFF})")
    for p in only_py:
        print(f"PY-ONLY {p}: {data[p:p + 6].hex(' ')}")
    print(f"py={len(py)} rs={len(rs)} rs-only={len(only_rs)} py-only={len(only_py)}")
    return 1 if (only_rs or only_py) else 0


if __name__ == "__main__":
    sys.exit(main())
