# Composite exporter: B2/B3 variant parts (#50)

Date: 2026-11-18
Base: `ac70db8` (main; recovery branch `t3/b2-b3-variant-parts`, WIP
`5e31b67` + salvage merge)
Status: **implemented (Python + Rust, port-parity verified), 3/3 target
parts export manifold, full-corpus A/B clean (0 pass→fail, 0 export
loss, 0 manifold regressions). The gate steps are verified; the single
`scripts/check.sh` run could not finish on this shared machine (the
port-fixture pin's `cargo build` waits on the shared package-cache
lock, and the server restarted mid-run — see §5).**

Claims: `docs/evidence/data/b2-b3-claims.csv`
A/B data: `docs/evidence/data/b2-b3-ab.csv` (one row per manifest part:
before/after export, L2 status, counts, invariants, stage, changed flag)
Reproduce: `PYTHONPATH=src .venv/bin/python -m pytest -q
tests/test_composite_export.py`; the A/B is
`scripts/triage/ab_identity_export.py` over the pre-change tree
(`git archive ac70db8`) and this tree, same interpreter and corpus.

## 1. The law

**B3 — the rep node precedes its pool wrapper.** In a per-rep composite
store the `01 06` pool group whose wrapper FOLLOWS a list node belongs to
that node; the pairing is positional (`_rep_node_positions`: the last
token-bearing node before the group's wrapper), not by decoded index. A
node already claimed by an earlier group cannot re-list a second pool
(`None` → fail-closed); there is no "first node after the wrapper"
fallback. A rep's record territory is `[region_end, next token node)`, so
an undecodable rep's records are never attributed to its predecessor.

*Incidence.* Measured read-only over the 1,036 located composite stores
(1,442 manifest parts): 2,175 `01 06` groups (174 stores carry more than
one), all with a preceding token node; that node absorbs the group on
2,149 (the 26 misses are partial/unexported reps, named per rep). The
first node AFTER the wrapper absorbs 2 of 1,186 and in both cases the
preceding node absorbs too — "after" is never the reading.

**B2 — the per-rep node law ladder.** `_decode_rep_node` tries the
committed table layout first (so every already-decoded rep keeps its
reading), then the stage-8 extent / raw-array / flat laws with the rep's
OWN pool group as the flat law's absorption reference. A multi-rep
store's pool spans every rep, so the store-level pool can never re-list
in one region; the twins' table walk therefore rejects (`shape 2 needs 1
f32 word, 0 left of the declared 67`) and the ladder falls to the flat
law, which is what exports them.

*Correction of record (review).* The salvaged WIP commit also carried a
**one-word-shortfall acceptance** in `decode_region` (`sum(shapes) ==
write_count + 1` → extend the region). The final commit **removed it**:
the region bound is already enforced by `layout()` and the walk
(`pos + 4*shape <= region_end`, `pos == region_end`), the ladder recovers
the twins without widening the region, and accepting a short count is the
less safe reading. The relation fires on exactly the two twins
(`TolerantSweepDev0 416d14fd`, `TolerantSweepDev1 434d4bb4`), and in both
cases the extended table reading absorbs **neither** pool group (0 of 8
for each rep) while the flat law absorbs 8 of 8 — the arithmetic
coincidence is the flat header misread, not a table region. No separate
B2-only population is claimed; B2 is the ladder, B3 is the pairing law.

## 2. Incidence on the target parts

| part | pre-WIP (`ac70db8`) | post |
|---|---|---|
| `TolerantSweepDev0` `416d14fd` | `undecoded-variant`: table walk overruns at element 25 | `identity-mixedwrite-reps`, flat 2/2 reps |
| `TolerantSweepDev1` `434d4bb4` | same | `identity-mixedwrite-reps`, flat 2/2 reps |
| `CAAGsiStartVolumeForBoolean` `4902c650` | `undecoded-variant: node list does not re-list the pool: 82 of 86 pool vertices absent` | `identity-per-rep`, all 8/8 reps |

The twins are the mixed-write population: their 8-vertex groups re-list
8/8 in their own flat region (26+91 and 26+92 elements; write counts
78+273 and 78+276) and 0/8 against the other rep's. The third exports
all eight reps and absorbs all 86 pool vertices; its 49 facet records are
the per-rep territories' records. Its rep laws are mixed:

- rep 0: committed table, write count 130 (the zero-block extent reading
  selects extent 1 for the same node);
- reps 1 and 5: flat, write counts 252 and 11,916 (the B2 ladder);
- reps 2, 3, 4, 6, 7: committed table, write counts 18, 260, 221, 18, 68.

**B3 applies to the third, and so does the B2 ladder** (reps 1 and 5).
Before the fix its per-rep path exported no rep at all: the index shift
paired rep 0 with the wrong node, and rep 2's `0x42` references 42..83
(its own 84-element space) were read against rep 0's 66.

## 3. Results

| part | vertices | triangles | manifold | boundary edges |
|---|---|---|---|---|
| `TolerantSweepDev0` | 117 | 24 | yes | 26 (open shell, G3 F6) |
| `TolerantSweepDev1` | 118 | 32 | yes | 36 (open shell) |
| `CAAGsiStartVolumeForBoolean` | 4352 | 554 | yes | 184 (open shell) |

All three: Python and the Rust port agree on the parsed summary AND on
byte-identical PLY output (the same check as
`test_primary_seam_port_parity_on_the_flips`, whose 15-part differential
also includes the changed seam flips and stays green).

Fixture repair: the WIP moved the two multi-rep builders to the measured
order but left `_composite_raw_store` and `_composite_table_overshoot_store`
pool-first, so the mixed-write assertions failed closed. Both now build
node → records → pool, the measured order; no assertion was relaxed.

## 4. Full-corpus A/B

Baseline is the pre-change tree at `ac70db8` (`git archive` into a temp
path, corpus read-only), same interpreter and corpus. One row per
manifest part in `docs/evidence/data/b2-b3-ab.csv`.

| measure | baseline | post |
|---|---|---|
| exports | 1,173 | 1,176 |
| L2 gate pass | 1,135 | 1,141 |
| dev L2 pass / 1,381 | 1,078 | 1,084 |
| held-out L2 pass / 61 | 57 | 57 |

Safety: **0 pass→fail, 0 export loss, 0 manifold regressions**. Three
parts gain an export (the three targets) and six flip to L2 pass: the
three targets plus `4d1b6c35` (LedStrips_WorkFile), `545707b9`
(Test_trappe) and `995383c2` (DB25_08) — all three were already exports
whose per-rep geometry the pairing/ladder repair completes, and all three
become manifold. 36 exported parts change vertex/triangle counts; none
loses its status (three flip to pass, the other 33 keep their pass/fail
result) and none regresses manifold. Every changed row is flagged in the
A/B CSV.

## 5. Gate

Each `scripts/check.sh` step was run in this worktree's own `.venv` (the
shared primary venv points at the newer main tree, so it cannot serve the
port pin):

- `ruff check .` clean;
- pytest: 85 composite tests + the 15-part primary-seam port differential;
  every other test file passes (the optional local Chromium screenshot
  pin was not exercised here — its Playwright launch is environment-bound,
  is skipped in CI, and is unrelated to this change);
- claims-CSV quoting clean (68 files, 14,490 rows);
- `cargo build --locked` native and wasm32, `cargo fmt --check`,
  `cargo clippy --locked -- -D warnings`, `cargo test --locked`
  (159 unit + 6 integration) all green;
- `wasm-pack build --target web --release` and `wasm-pack test --node`
  green; `port/pkg` and `site/viewer/pkg` byte-identical;
- the Node suites pass file-by-file (the concurrent `node --test
  tests/*.mjs` invocation is timing-sensitive on this shared machine:
  the per-file runs are green).

The full `scripts/check.sh` stop could not complete here: its pytest
phase includes the port-fixture pin, whose `cargo build --release` waits
on the shared cargo package-cache lock held by unrelated jobs on this
machine, and the server restarted the run twice. Port parity itself is
verified directly on the changed population (§3: 3 targets + 6 changed
seam flips, equal summaries and byte-identical PLY) and by the 15-part
`test_primary_seam_port_parity_on_the_flips` (green, 69 s).
