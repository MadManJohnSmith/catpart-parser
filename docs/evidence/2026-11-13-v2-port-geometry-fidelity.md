# Phase 5 V2 (ticket #41): the non-composite geometry port + the export Fidelity slice

**Status: implemented on the V2 worktree branch, 2026-11-13; coordinator
review pending.** Design authority: `docs/specs/phase5-viewer-spec.md` —
this note cites §2.1 (module mapping), §2.2 (the numeric contract, the
keystone), §2.3 (the error-class vocabulary), §2.4 (the native CLI
seam), §3.1/§3.2 (populations + diff definition), §4 (harness design,
"the stage CSVs name the per-family stores") and §6 V2 (ticket scope);
the ticket is #41, the harness it extends is V1 (#40). Nothing is
merged or pushed: commits live on the worktree branch only.

This note's run-level figures (population, outcomes, wall-clock) are
the ones the harness itself writes into its figures block on each run
(commands below); the curated prose around them was reviewed against
the CSVs before committing — every figure traces to
`docs/evidence/data/v2-fidelity-l2-claims.csv`,
`docs/evidence/data/v2-fidelity-fixture-claims.csv`, or a committed
artifact named here (#37, prose-traceability). The per-stage re-run
counts (the stage grind's discipline at port speed) are recorded in
this note's stage table and in the per-stage commit messages; the
stage CSVs themselves lived in pytest/tmp convention and are
summarized by the committed final artifacts.

## What landed

The non-composite geometry slice, ported 1:1 from the Python twins
(operation order and expression shape preserved; every fail-closed arm
included; each module's doc header carries the twin's own evidence
citations per §2.1 and ADR-0002's discipline):

- `port/src/geometry/errors.rs` — the classified-failure seam (the
  kebab vocabulary single-sourced as constants; raise sites 1:1).
- `port/src/geometry/store.rs` — G1 + the stage-3a/12 recovery probes
  (N2 validation, N3 overshoot search, the relaxed tail families
  fail-closed, the header-less variant, the N6 trailer laws). Python
  buffer semantics mirrored exactly: `slice_clamped` (Python slicing
  clamps), `find`/`find_all` (`bytes.find` incl. clamped end bounds
  and the overlapping resume at hit+1), `ascii_replace`
  (`decode("ascii","replace")` byte-for-byte).
- `port/src/geometry/pool.rs` — G2 groups (P1g escape, the count
  sanity windows, P2g/P3 fail-closed) with **THE widening point**: the
  vertex records load f32 and widen to f64 once, at load; everything
  downstream is f64.
- `port/src/geometry/facets.rs` — G3 (the STRIP_RE scan mirrored with
  finditer's exact resume-at-end + endpos semantics, the (width, k)
  tiling law with the twin's lazy-ref computation and tuple-rank
  tie-breaks, the clean-store width vote, the lex-rank map as Python's
  stable sort — IEEE comparisons, ties keep walk order; `total_cmp`
  deliberately NOT used, it orders -0.0 < 0.0 where Python sorts
  equal) and `decode_soup` with **the keystone**: the degenerate test
  is tuple equality against `(0.0, 0.0, 0.0)` on
  `cross(sub(b, a), sub(c, a))`, argument order and expression shape
  verbatim, no mul_add.
- `port/src/geometry/mesh.rs`, `port/src/geometry/ply.rs` — the
  invariants (Counter semantics via HashMaps; missing reverse
  direction = 0) and the byte-exact binary-LE PLY writer (the f64 ->
  f32 write-back is exact: the pool holds exact f32 widenings).
- `port/src/geometry/export.rs` — the orchestration (the
  stdcont/xdoclink/seebody/other-container candidate walk, the first
  exportable store wins, the first classification re-raised; recovery
  provenance on failures and successes; the schema-v1 summary with
  field declaration order = the Python dict construction order). The
  twin's `_self_check` has no port counterpart: the typed struct IS
  the schema shape (no JSON-schema dependency; §2.1's minimal deps) —
  a shape divergence would surface as a Fidelity mismatch.
- `port/src/bin/fidelity-cli.rs` — export mode (§2.4): file path +
  PLY path arguments, the summary JSON on stdout, the PLY written only
  after the whole store decodes (failures leave no partial output),
  the classified error line with exit 1, usage exit 2.
- `scripts/fidelity_run.py` — the export diff (§3.2: summary
  parsed-document equality + PLY byte-identical + `error_class`
  equality on double refusals, the Python class parsed too) and the
  V2 sample bias (below).
- `tests/fixtures_gen.py` — three new non-composite parity shapes
  (the harness-gap fixtures, below).
- `tests/test_port_fidelity.py` — the gate pin grows the V2
  assertions (both slices covered, every geometry variant in the
  export matrix, no composite-family variant in it, L1 refusals
  crash==crash, L2 refusals class-equal within the errors.py
  vocabulary, `ply_equal` true exactly on exporting rows).

## Decisions recorded (dated, with alternatives)

1. **The V2 composite exclusion (the ticket's hard stop) has two
   layers, and both are needed** (2026-11-13, V2). Sample time: the
   stage-15 roster (`docs/evidence/data/stage15-identity-export-files.csv`,
   `element_decl > 0`) names the composite-family stores — the corpus
   cross-tab: 1,442 part rows, **1,061 composite-family** (977
   composite-path passes + 84 composite-path fails), leaving **381
   comparable rows** (112 clean passes + 144 undecoded-variant + 125
   missing-geometry-store). The roster is the ONLY signal that works
   at sample time: the accepted report's L2 records carry the warnings
   array, and 269 of the 977 composite-path passes carry NO
   composite-only warning class (a warning-based flag would have
   missed them). Run time: the Python export summary's additive
   `composite` key (the twin emits it on every composite-path decode)
   is the authoritative marker — a Python success carrying it with a
   port refusal is the outcome `excluded-composite-path`, named
   per-row in the note, never a match and never a mismatch (§3.2
   discipline). The port's composite arms fail closed with the twin's
   own class (`undecoded-variant`), so composite-path REFUSALS compare
   as error-class-equal matches — the hard stop's other allowed shape.
   In the acceptance run the exclusion fired **0 times** (the roster
   removed the whole family at sample time; the run-time check stayed
   armed as the truth). Rejected: sampling proportionally over all
   parts (74% of rows would be excluded, leaving the comparison
   meaningless) and inventing a port-side composite decode stub (the
   hard stop forbids it; V3 owns the whale).
2. **The V2 sample bias** (2026-11-13, V2): `--slice l2 --sample
   stratified:N` loads the stage-15 roster, verifies every part row is
   covered (fail-closed on a stale roster), excludes the composite
   family, and stratifies the remaining pool over the §4 axis
   (detected_version × split × export outcome class) with a seat
   weight of 3 on the fail-closed classes (`undecoded-variant`,
   `missing-geometry-store`, the malformed-* families) — a stratum
   occupies that many slots in the round-wise priority list, so per
   round it receives that many seats while quota lasts. Within a
   stratum the picks are evenly spaced over the sha256-sorted rows —
   no RNG; the same N yields the same sample.
3. **Panics mirror the twin's unclassified crashes** (2026-11-13, V2).
   The twin has two unclassified crash arms on the export path — the
   empty-file `mmap` `ValueError` and past-EOF `IndexError`s (e.g. a
   wrapper at the body's very end) — which exit 1 with a traceback and
   no error-class JSON. The port mirrors them as panics (outside the
   0/1 seam contract), which the harness records as harness-level
   failures — never matches, never silent (§3.2). No corpus part and
   no fixture reaches either arm (the accepted run carries no crash
   rows); the arms exist so a divergence there is loud, not absent.
4. **The L2 refusal comparison parses BOTH sides' classes** (2026-11-13,
   V2). The L1 harness normalizes the Python exit 1 to `crash`
   structurally (V1 decision 1); the export seam's exit 1 carries the
   real geometry vocabulary, so the harness now parses the Python
   stderr JSON line too — a Python exit 1 without a class line is a
   harness-level failure, never a match.

## Corrections (dated, never massaged)

- **2026-11-13: the pool group's count field is not `len(vertices)` —
  caught by the Python gate pin.** The u16be fixture's P1g
  generalization first wrote `_p1g_count(len(vertices))`, which
  clobbered the `geometry-truncated-pool` corruption: its count field
  must STAY 8 while only 6 records precede the facet region (the G2
  P2g violation under test); with the field at 6 the pool decodes and
  the fixture degrades to `undecoded-variant` —
  `test_corrupted_variants_classified[geometry-truncated-pool...]`
  failed at seed 5. Fix: the field is 300 (ff-escaped) on the u16be
  variant and 8 everywhere else. The gate doing its job on the
  fixture side.

## Fixture-mode parity (§4 fixture mode, the gate)

- Population: **292 fixtures = 238 L1 rows + 54 L2 export rows** — the
  L1 matrix as at V1 (every A2 variant incl. the composite-law
  families: inspect parity holds — inspect does not decode geometry),
  plus the export matrix: all 23 geometry-bearing variants (the
  canonical store, the three new parity shapes, the recovery variants,
  the corrupted classes) at seeds 0 and 7, plus the store-less shapes
  (`None`, `dual-region` and the plain corrupted families) which
  refuse `missing-geometry-store` / exercise the short-file path. The
  composite-law and unrouted-elementspace variants are excluded from
  the export matrix (V3 scope, #42 — named in the note).
  (Arithmetic corrected 2026-11-14 per review F2, ticket #41: the
  draft said 235+57; the committed CSV says 238 L1 + 54 L2 = 292 —
  #37: prose traces to the CSV.)
- Command (repo root, this worktree):

  ```
  .venv/bin/python scripts/fidelity_run.py --fixtures \
      --csv docs/evidence/data/v2-fidelity-fixture-claims.csv \
      --note /tmp/v2-fixture-auto.md   # figures restated here
  ```

- Result: **292/292 match** — summary parsed-document equality + PLY
  byte-identical on every exporting fixture (including all recovery
  variants' `store_recovery` records); every corrupted variant
  class-equal (`missing-geometry-store` / `undecoded-variant` ×4 /
  `malformed-pool-vertex` / `malformed-pool-group` /
  `malformed-store-header` ×2 / the composite-gate refusals). The pin
  is the gate test `tests/test_port_fidelity.py`, green in the full
  gate run. The CSV is committed (V1's fixture CSV lived in pytest's
  tmp; V2 commits it — the export slice is an acceptance artifact).

## Corpus runs (§4 corpus mode, local-only per ADR-0003)

- The acceptance run (the biased L2 sample):

  ```
  .venv/bin/python scripts/fidelity_run.py --slice l2 --sample stratified:120 \
      --csv docs/evidence/data/v2-fidelity-l2-claims.csv \
      --note /tmp/v2-l2-auto.md   # figures restated here
  ```

- CSV: `docs/evidence/data/v2-fidelity-l2-claims.csv` — named for the
  `*claims*.csv` glob (hygiene checker coverage verified by the gate).
  Column 0 (`row_id`) is the sha256.
- Population (all figures from the CSV): **120 part rows** — 116 dev,
  4 held-out; sampled by export outcome class: **73 undecoded-variant,
  32 pass, 15 missing-geometry-store (12 sampled + the 3
  not-exported rows refusing `missing-geometry-store` class-equal), 0
  composite-family rows** (the roster excluded 1,061 of 1,442 parts;
  the pool was 381).
- Result: **120/120 match; 0 output-mismatch; 0 error-class-mismatch;
  0 harness-level failures; 0 excluded rows** (§3.2: every row is a
  match by evidence). The 32 exporting rows compared summary
  parsed-document equality AND PLY byte-identity (`ply_equal=true` on
  all 32, from the CSV); the 88 refusal rows compared `error_class`
  equality (73 `undecoded-variant` + 15 `missing-geometry-store`,
  python == port on every row, from the CSV).
- Wall-clock (measured, never estimated): full-command wall-clock as
  invoked **8.1 s** (includes the release build check); subprocess
  time totals from the CSV **python 7.7 s, port 0.3 s** — Python
  dominates, as §4's budget basis expects. WITHIN the §4 per-ticket
  budget (≤ 15 min at N=100) by ~110×.
- The L1 regression run on the final state (the stage discipline's
  closing re-run): `--slice l1 --sample stratified:120` → **120/120
  match** (CSV in tmp, not committed; the committed fixture CSV's 235
  L1 rows are the committed L1 artifact).

## Per-stage harness re-runs (the stage grind's discipline at port speed)

Each porting stage ended with a harness re-run before its commit
(counts also recorded in the per-stage commit messages; stages 1-3
ran `--slice l1` because export mode landed at stage 4):

| Stage | Commit | Fixture mode | Corpus L1 sample | cargo tests |
| ----- | ------ | ------------ | ---------------- | ----------- |
| 1. errors + store + pool | `4b1b010` | 229/229 | 120/120 | 49 |
| 2. facets + mesh + ply | `4bca371` | 229/229 | 120/120 | 70 |
| 3. export orchestration | `be97781` | 229/229 | 120/120 | 84 |
| 4. fidelity-cli export mode | `23666f3` | — (seam smoke: 20/20 fixture variants + 3/3 non-composite corpus parts) | — | 84 |
| 5. harness export diff + bias | `1065fdc` | 277/277 | pilot l2 N=30: 30/30 | 84 |
| 6a. harness-gap fixtures | `170d92c` | 292/292 | — | 84 |
| final (this note) | — | 292/292 | l1 120/120, l2 120/120 | 84 |

The stage-4 seam smoke (in the commit message) found the two
warning-free composite-path exports the roster later excluded — the
observation that motivated decision 1's two-layer design.

## The harness-gap fixtures (deliverable 4: decision paths with no fixture)

The first export-parity pass left four non-composite decision paths
unexercised by fixtures; three new `GEOMETRY_VARIANTS` cover all four
(`tests/fixtures_gen.py`, named per the existing convention; parity
verified against the Python seam at both seeds before commit):

- `geometry-u16be-facets` — the F1w clean-store width law (u16be refs,
  the u8 count windows poisoned by the first ref's high byte, the
  unanimous exact-tile vote) AND the P1g ff-escaped pool count (> 255,
  the u32le escape). 300 vertices, exports 12 triangles +
  `unused-pool-vertices`.
- `geometry-degenerate-cross` — the `(0.0, 0.0, 0.0)` tuple-equality
  degenerate arm: a 9th pool vertex collinear on the z=0 face's
  diagonal, the strip re-threaded through it — three DISTINCT
  vertices, exactly-zero cross product, skipped (the open-shell
  fixture's repeated-vertex record never reaches this arm). Exports
  with `degenerate-triangles-skipped` + `open-shell`.
  **(Correction 2026-11-14, review F1, ticket #41: as landed this
  fixture did NOT export** — `pool_count_field` stayed 8 while
  `pool_walk` grew to 9 records, so the walk stopped at 8, the
  re-threaded ranks landed beyond the pool, and BOTH twins refused
  `undecoded-variant` identically ("facet references beyond the pool:
  max ref 8 >= pool size 8") — parity intact, the seam arm untested.
  Fix: the count field states 9 for this variant
  (`tests/fixtures_gen.py`, coordinator commit). Verified post-fix:
  the fixture exports — 9 vertices, 12 triangles,
  `degenerate_triangle_count` 1, the two warnings above — and the
  port's PLY is byte-identical at the seam (the fixture-mode CSV's
  `geometry-degenerate-cross ... |l2` rows: `outcome=match`,
  `ply_equal=true`). The §2.2 keystone arm is now seam-covered; the
  committed fixture CSV regenerated accordingly.)
- `geometry-second-store-exports` — the candidate walk: two
  `CATStdCont` blocks, the first store's tail matching neither
  recovery family (the shipped `malformed-store-header` rejection),
  the second canonical → `store_ordinal = 1`, the rejection never
  surfaces.

The fourth gap (the exact-tie narrower-width rule inside
`parse_facet_record`) is pinned by the Rust unit test
(`narrower_width_wins_exact_ties`, the `[2, 0, 0]` count construction)
— a fixture for it would need a record whose BOTH width parses tile
exactly, which the corpus's clean stores do not exhibit; the unit pin
is the honest scope.

## §4 budget check (declared target, measured against)

- Target (§4): per-ticket sample runs ≤ 15 min at N=100; full
  dual-slice run ≤ 2 h.
- Measured: **8.1 s full wall-clock at N=120** (l2, biased) and
  **16.5 s** for the 292-row fixture run — within the per-ticket
  budget by ~110×. No correction needed; the target stands as
  written.

## Gate (scripts/check.sh mirror of ci.yml)

- ruff: clean (whole tree).
- pytest: **366 passed, 7 skipped** (the V1 counts unchanged in shape;
  the fixture pin's assertions grew to the V2 set within the same
  test).
- cargo: build native ✓, build wasm32-unknown-unknown ✓, fmt --check ✓,
  clippy -D warnings ✓, test ✓ (**84 Rust-internal tests**, up from 31
  at V1 — the geometry modules' decision-path pins).

## Scope discipline (the HARD STOP)

`port/src/geometry/composite.rs` remains the V0 stub — no composite
decode, no composite fixtures in the export matrix, no WASM entries
(V4), no viewer, no spec/`src-catpart`/fitness changes (the Python
reference untouched — §3.3's rule; the fitness rows unchanged). Corpus
binaries never committed; the corpus itself was consumed read-only via
the repo-root `corpus` symlink (gitignored), never left the machine.
The V2 sample's composite-store rows appear exactly as the hard stop
allows: error_class-equal refusals (73 `undecoded-variant` rows in the
acceptance CSV include the composite-gate refusals) or excluded (0
rows fired; the rule armed and named).
