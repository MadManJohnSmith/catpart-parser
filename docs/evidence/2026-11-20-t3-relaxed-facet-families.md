# Evidence: T3 — the relaxed facet families 0x44/0x41 admitted under the strict guard — 2026-11-20

**Status**: COMPLETE. Shipped at the strict-guard level; the fitness row
`20261120T192800Z-c3cb79` is **rejected** by the letter of the no-regret rule
(nothing rose — see below) while every regression bar holds at zero. Ticket
#61.

**Structural fact (T3 micro-probe, 2026-11-20)**: 226/226 carrier records
(0x44: 217 in 98 files, 0x41: 9 in 26 files) parse under the SAME (width, k)
tiling law as the exported families — header_len=4 on all, types 1/2, widths
1/2, counts tiling, refs in pool range. The only delta vs 0x42: no 12-B
normal carrier (the NORMAL_MARKERS_ALL set excludes them) and the families
live in composite-body parts. The export's refusal was a semantics gate
(G3 open questions 3-5), not a parsing gap.

**Implementation** (`composite.py` + Rust twin):

- `RELAXED_SHORT_MARKERS = (0x44, 0x41)`; the records run in a SECOND pass
  of `_triangulate` / `triangulate`, so the base pass stays byte-identical
  to the pre-T3 behavior (the relaxed loops never touch the base pass's
  edge budget — measured: the walk-shift triangle losses of the naive
  single-pass admission, e.g. Board 3,276 → 2,703, are gone).
- Each relaxed loop enters only under the STRICT mesh guard — no seam-area
  exception — so every fold keeps every edge at ≤ 2 uses and a
  base-manifold mesh stays manifold by construction.
- The extended-family degenerate precondition: a relaxed loop carrying a
  degenerate emission is declined WHOLE and its skip is never counted — the
  corpus invariant `degenerate_triangle_count == 0` on passing parts is
  preserved by construction (the naive admission produced 5–107 degenerate
  skips and 15 pass → fail flips; with the precondition: 0).
- Skip-bearing relaxed loops join the dup-pin weld input, whose own strict
  incremental guard applies unchanged.
- The admitted families leave `skipped_markers`, so the
  `unresolved-facet-family` warning names only the truly-open families.
  Counters `relaxed_loops_accepted` / `relaxed_loops_declined` ride the
  composite summary block (both keys whenever either is nonzero — pinned by
  the port-parity test).

**Measured effect over the 115 carrier files** (Python, base = the same
build with `RELAXED_SHORT_MARKERS = ()`):

| Metric | Value |
| --- | --- |
| Files with a triangle delta | **55** |
| Extra triangles | **+701** |
| Extra area | **+191,338 mm²** |
| Manifold regressions | **0** |
| L2 status flips (corpus-wide, report diff) | **0** |
| Degenerate-triangle delta on passing parts | **0** |

Top gains: head_ia (ccbb7862) +126,790 mm², head_hueca_x1.5 (ab1c7b09)
+32,859 mm², head_ia (ae85fae7) +18,436 mm², Disc-2DL +7,049 mm²,
TouchRows_Solders +120 tris / +4,226 mm² — whole surfaces the composite
body carried that the pinned families never reached.

**Fitness**: `20261120T192800Z-c3cb79` — L2 dev 1,113/1,381 (flat), held-out
57/61 (flat), L1 flat, L3 23/23 → **rejected** by the no-regret letter
("no comparable split regressed and at least one comparable level's Dev
rose" — nothing rose). The L2 rate counts pass/fail coverage; a
triangle-richness gain on already-passing parts is invisible to it. The row
stays in the append-only history (precedent: the two committed rejected rows
of 2026-11-07/08); the accepted baseline and every site pin remain at
`20261120T183229Z-d503ff`.

**Tests**: the port-parity flips test re-pinned (44e63faa 2,516 → 2,520;
6ab9e107 850 → 844, the stage-15 dedup dropping relaxed duplicates;
a61588e5 2,986 → 3,017) with PLY byte-identity; the new corpus-gated
`test_relaxed_families_export_under_the_strict_guard` pins the counters,
manifold and degenerate invariants on a 0x44 carrier.
