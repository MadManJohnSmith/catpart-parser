# Evidence: the U4 skip-slot coordinate law measured on the bench-external targets (2026-11-22)

A4 (W16, marathon wave 4, Gallyfrey, branch `marathon/w16-u4-curve-loops`
@ base `339525a`).  Question (backlog A4): do the composite point
region's skip slots (U4) point by deterministic offset into
neighbouring curve records/polylines, or carry inline compressed
coordinates, such that the loops dropped today under
`curve-entry-loops-unexported` can be exported?

Labels: **fact** = measured here with a reproduction command;
**inference** = interpretation; the split follows the house convention.

## 0. Artifacts

| file | what |
|---|---|
| `src/catpart/geometry/curves.py` | the law module: dup pin, battery, degenerate split, `33 3X` walker, ring cross-check |
| `port/src/geometry/curves.rs` | the Rust twin (13 unit tests, clippy clean) |
| `tests/test_curves.py` | 27 synthetic tests (no corpus) |
| `scripts/triage/measure_u4_skip_law.py` | the measurement runner over the shipped decode |
| `docs/evidence/data/u4-skip-law-files.csv` | one row per target part |
| `docs/evidence/data/u4-skip-law-claims.csv` | the claims rows (stage4b schema) |

Targets: Motor 81, Audi R8 629, Vulcan 12,124 dropped loops (the
backlog's numbers; `knurling_screw` 117 is NOT measurable here — the
file is absent from this machine, confirmed by the 2026-11-21
read-only probe in `~/.local/state/catpart-parser/subagents/
knurling-audi-visual/informe.md`; no figures are invented for it).

## 1. The law: U4-D dup-prev is total on the targets (fact)

The committed runner (Motor row) and the streaming re-read of the
session captures (all rows; same loop definition) agree.  Every skip
slot has a preceding written element — **0 unpinnable slots** over
473,801 skips (Motor 5,616 + Audi 22,466 + Vulcan 445,719).  The loop
arithmetic reconciles EXACTLY with the shipped counters on every part:
`skipref_loops == loops_curve_entry_exported + loops_curve_entry`
(Motor 4,073 = 3,992+81; Audi 12,289 = 11,660+629; Vulcan 267,594 =
255,470+12,124).

The battery (coplanarity of normal-carrying skip-ref loops against
their record's stored normal under the dup pin): **Motor 0 nonplanar,
Audi 0, Vulcan 18** — a 0.0045% residual over 401,956 such loops.  The
dup pin IS the coordinate law; no alternative coordinate source is
needed to pin any slot on these parts.

## 2. Hypothesis 1 (offset into neighbouring curve records / polylines): refuted as a source, kept as corroboration (fact)

The `33 3X` curve records (in the token node FOLLOWING the list node,
026d6726 layout: node payload = header + point region + trailing
structure; strip records between; curve node last) are per-CURVE:
18-30 B records (a `33 37` circle = 4 BE f32 + 2-B trailer) cannot
carry per-slot coordinates — a 9-point ring discretization needs
108 B.  The anchor has 24 records vs 26 skips; the record `id` field
takes values 1/2 on the anchor (no skip-index correspondence).  The
edge polylines reference the same skip slots the facet loops do and
tile the same rings through the dup copies (twin invariance 118/118
dup-pinned positions across the two saves, 2026-11-12 note §4).  The
ring cross-check ties records to the WRITTEN rings (corroboration).

## 3. Hypothesis 2 (inline compressed coordinate): refuted (fact)

The point region consumes exactly the declared write count on every
walk-exact store (the table law, unchanged).  The list node's trailing
region is structure, not coordinates: 026d6726's 568 B of quantized
u16 runs vs the 312 B the 26 skips would need as f32 triples.  U2
stays open but holds no coordinates.

## 4. What the dropped loops actually are (fact + inference)

The 12,124 (Vulcan) / 629 (Audi) / 81 (Motor) decompose into
non-coordinate classes:

- **Weld refusals (topology)**: the shipped weld battery + mesh guard
  (Motor units: 35 edge-overuse + 11 degenerate; Audi: 46 + 20) —
  edge over-use is a manifold-assembly decision, not a coordinate
  failure (the pin-independence probe, 2026-11-12 §3: 0/52 rescued by
  any alternative pin).
- **Declined extended-header records** (0x47/0x4f): their skip-bearing
  loops never reach the weld (Audi 584 skip-members in 33 declined
  records; Vulcan 452 records declined).
- **The degenerate-emission class (the A4 finding)**: dup-pinned loops
  one of whose strip triangles collapses — the writer's degenerate-quad
  convention, e.g. `(P, X, P, Y)` = triangle `(X, P, Y)` plus a
  collapsed half.  Their dup pins are TRUE (battery-validated); the
  real surface is recoverable by the same G3 F7 skip-degenerate
  convention the primary strips already apply
  (`curves.split_loop_triangles`).  Measured gross (incl. loops inside
  declined records): Motor 36 loops -> 121 triangles / 5,534 mm²;
  Audi 359 -> 761 / 13,586,895 mm²; Vulcan 3,269 -> 22,421 /
  19,033,923 mm².

**Inference**: an export increase needs the emission law changed (the
weld adopting the per-triangle degenerate split behind the existing
mesh guard), not a coordinate law.  composite.py/vote.py are W17's
surface — the split law lands here as the validated module
(`curves.py`/`curves.rs`) + measurement, ready for integration; the
A/B must re-run the corpus gates (0-regression check) at that point.

## 5. Limits, negatives, reopen criteria

- `knurling_screw` 117: unmeasurable (file absent); reopen when the
  part arrives — the probe machinery (`probe_declined.py`) is ready.
- The session captures were produced by driving the shipped
  `build_export` with `_triangulate` patched to record per-rep
  element spaces; the committed runner measures the same quantities
  directly (Motor row byte-agrees with the capture-derived row).  The
  Audi/Vulcan rows were re-derived from the on-disk captures under the
  strict RAM budget (no `build_export` re-run for parts > 15 MB this
  turn; both capture JSONs are session artifacts, not committed).
- Reopen the coordinate-law question only if a part shows unpinnable
  slots or a battery residual far above 0.005% — neither exists here.

## 6. Reproduction

    # the committed runner (Motor fits the RAM budget):
    .venv/bin/python -I scripts/triage/measure_u4_skip_law.py \
      --out-dir /tmp/u4-plies \
      <datasets>/ducati/Motor.CATPart
    # the capture path (one part at a time; ~240 MB JSON for Vulcan):
    python3 -I probe_capture.py <part> /tmp/x.ply /tmp/x-capture.json
    # the claims/files rows from captures:
    python3 -I rows_from_captures.py   # session artifact, /tmp/w16
