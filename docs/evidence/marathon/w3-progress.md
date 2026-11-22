# W3 progress — marathon v3 (`marathon/w3-e5-algebra`, base d8554e0)

**Worker**: W3. **Exclusive files**: `src/catpart/geometry/{grid,surface}.py`,
`port/src/geometry/{grid,surface}.rs`, their tests, `docs/evidence/`.
**This file**: the Orchestrator's channel — hypotheses, commands, metrics,
negatives, next step. Updated per coherent unit.

## Baseline (2026-11-22, d8554e0)

- Worktree `~/marathon-wt/w3` on `marathon/w3-e5-algebra` @ d8554e0; venv
  `.venv` (pytest 8.x), `PYTHONPATH=$PWD/src` import verified.
- **Corpus**: not present on this host; re-downloaded from the manifest
  sources with `scripts/triage/redownload_corpus.py`:
  **1,755/1,824 files sha256-valid on disk** (1 download failure,
  68 hash-mismatch = sources changed upstream; those 68 are excluded from
  any corpus-wide claim denominator). The 128-part E5 grid population
  (grid-meshing-parts.csv) is complete on disk.
- **Submarine snapshot** (`bench-submarine`, the 94 `no-evaluable-surface`
  parts and the 10 3-lane frames): NOT on this host, no committed source
  URL (`2026-11-21-surface-compact-head.md` says corpus read-only, no
  binary committed). H2's 3-lane decode is blocked on the bytes; see
  negatives below.
- Baseline metrics (from `2026-11-20-t1-grid-relaxation-t2-display.md` and
  the latest fitness reports on main): L2 dev **1,113 (80.59 %)**, held-out
  flat 57/61, open 1,412/1,442 = 97.92 %, MESH 1,178.

## Hypothesis 1 — the `e5 0d` Class Table algebra (IN PROGRESS)

**Claim being tested** (from `2026-11-19-e5-dialect.md` §3.1/§5.3(1)): the
writer-block tail is a token stream, not noise; and the frequent
`class:u16le` values correlate with payload geometry roles (knot lanes,
multiplicity lists, pole grids) so that the E5 dialect's payload encoding
becomes readable.

**Measured so far (scratch probe over the first 118 downloaded files, 69
writer regions)** — the tail grammar is a token stream ending `17 <00|01>`:

| token | reading (hypothesis to validate corpus-wide) |
| --- | --- |
| `03 00` | opener pair (34/69 regions so far) |
| `11 <u32le=17> "  R207-JMA:122008"` | a second release stamp, u32le-length-prefixed (2 regions) |
| `08 <u8>` | small reference (1-byte arg) |
| `18 <u16le>` | reference (2-byte arg; E5 note §5.3(1) candidate: record id) |
| `38 <u24le>` (or `38 <u16le> <u8>`) | wide reference (3-byte arg) |
| `80..ff` singles | flag/sub-tag bytes (`81`,`82`,`83 a9 cf`,`84`,`85`,`8c`,`89 a9 cf`,`92`,`80`,`dd`,`e7`,`f4` observed) |
| `17 00` / `17 01` | terminator |

Worked id-membership: `CAACafSearch` tail refs 128..744 ascending
(`08 80 08 92 … 18 e8 02`); `CorrugateTube10-2` refs 470, 21,098..22,256
(its ids run into the tens of thousands); `attribut` `08 8f` = 143 = its
record count. Next: the corpus-wide membership test (refs ∈ record ids?),
then the class↔payload algebra.

## Commands

```bash
cd ~/marathon-wt/w3
.venv/bin/python -I scripts/triage/redownload_corpus.py "$PWD"   # corpus
# (scratch probes live in /tmp/w3-analysis until they land as committed evidence)
```

## Negatives (documented, with reopening criteria)

1. **H2-3lane (blocked, not refuted)**: the 10 3-lane `a5 03 34` frames
   (2 parts) and the 94-part bench live in the TR-1700 snapshot, which is
   not on this host and has no committed source. Reopens when the snapshot
   or the 2 `BW-hatch-*` parts are restored (sha256s not committed either —
   the S2 diagnostic was session-state). Synthetic-only decode would guess
   the grammar; the no-guessing rule stands.
2. **Corpus download hash-mismatch (68 files)**: source repos changed
   upstream since the manifest froze. Excluded from denominators; no code
   effect.

## Unit 1 (committed b5e14d2) — the E5 Class Table algebra CLOSED

**The `e5 0d` class `0x00e7` payload is an exact B-spline surface** — the
compact head's pole law with u32 fields (measured, shipped decoder):

```
0x80 | deg_v:u32 | a:u32 | b:u32 | n_v:u32 | q:u32 | knots_v f64[n] | mults_v u32[n]
    | deg_u:u32 | a2 | b2 | n_u:u32 | q2 | knots_u | mults_u
    | 00 00 | 01 00        pole marker: plain / rational
    | pole net             v-major outer, pole (i,j) at net + 24*(j*poles_u + i)
    | tail                 148 B law (01 00 records: tail - 8*poles == 148 = weights)
```

Corpus rates (1,755 sha-valid files, 268 E5-bearing): parse 11,520/11,554
= 99.7 %; plausible net 11,123/11,520 = 96.6 %; markers 0000×10,723 /
0100×797; both marker families close the 148 B tail law at ~100 %.
Orientation pinned: on the no-facet battery population 85 non-square nets
evaluate ONLY v-major, 0 only u-major, 82 (square) both.

**Route** (shipped, Python+Rust): `surface.scan_part` runs E5 records
after the a5 frames under the same battery; folds into totals+mesh ONLY
when ≥1 E5 surface tessellated (no-regret). `grid.e5_records` = the
admitted-run walk. Export prose/summary name the a5+E5 split only when E5
participates — additive schema (additionalProperties: true).

**Corpus A/B (d8554e0 vs branch)** over the exact changed-candidate set
(380 files = E5-bearing ∪ no-facet): 343 byte-identical, 37 improved
(21 candidate-grid → exact-surface upgrades, **16 display → mesh flips**,
L2 dev 1,138 → **1,153-1,154 expected**, 82.40 % → ~83.5 %), **0
regressions**. Held-out untouched by construction (no held-out file in the
changed set — verified per-row in the A/B CSV split column).
Python = Rust PLY **byte-identical on all 16 no-facet E5 parts**.

**Tests**: `tests/test_e5_surface.py` (15) + 7 Rust tests; ruff clean,
clippy `-D warnings` clean, rustfmt clean; suite: 88 targeted + fidelity
pins green. Probe `scripts/triage/probe_e5_class_table.py` (selftest 6/6).

## H2 residue close-out

- **bdd7ec87's non-monotone prefix grid**: superseded — the E5 route now
  owns the part with 18 exact surfaces; the prefix candidate is no longer
  consulted for output (the grid route no longer runs there).
- **80aad8d8 / d7ed0772 non-uniform prefixes**: a5-priority parts, no 0xe7
  records; their prefix grids were never consulted (a5 priority) and stay
  refused under the conservative law — unchanged by design.
- **The 3-lane compact-head variant (10 frames, 2 parts) + the 1/94
  fold-failing part**: BLOCKED, not refuted — the TR-1700 snapshot is not
  on this host and its URL/sha256s were never committed (S2 diagnostic was
  session-state). Reopens the moment the snapshot or the 2 BW-hatch parts
  are restored.

## Final (2026-11-22) — pushed d8554e0..bd823b2

All four commits on `origin/marathon/w3-e5-algebra`: baseline (bda6b19),
the E5-surface route (b5e14d2), progress (894b467), evidence (bd823b2).
Committed census + A/B supersede every scratch figure: CT rows in
`docs/evidence/data/e5-class-table-claims.csv`, the per-class table in
`e5-class-families.csv`, the no-regret A/B in `e5-surface-ab.csv`
(379 changed-candidate files: 342 identical, 37 improved = 22 upgrades +
**15 dev display→mesh flips**, 0 regressions, 0 error-class changes).
Expected L2 dev **1,138 → 1,153 (82.40 % → 83.49 %)**; held-out flat by
construction (no held-out file in the changed set). Full suite 959 passed
/ 1 environmental failure (corpus-gated composite test; the pinned
`lengua_original.CATPart` changed upstream — unrelated to this branch).
NOTE: the token request card was opened for pushes, but the push
succeeded with the environment's own credentials — no secret consumed.
