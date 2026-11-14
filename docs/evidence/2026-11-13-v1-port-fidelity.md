# Phase 5 V1 (ticket #40): the L1 slice port + the Fidelity harness

**Status: implemented on the V1 worktree branch, 2026-11-13; coordinator
review pending.** Design authority: `docs/specs/phase5-viewer-spec.md` —
this note cites §2.1 (module mapping), §2.2 (numeric contract), §2.4
(native CLI seam), §3.1/§3.2 (populations + diff definition), §4
(harness design) and §6 V1 (ticket scope); the ticket is #40, the V0
skeleton it builds on is #51. Nothing is merged or pushed: commits live
on the worktree branch only.

This note's run-level figures (population, outcomes, wall-clock) are
the ones the harness itself writes into its figures block on each run
(command below); the curated prose around them was reviewed against the
CSV before committing — every figure traces to
`docs/evidence/data/v1-fidelity-l1-claims.csv` or to a committed
artifact named here (#37, prose-traceability).

## What landed

The L1 slice, ported 1:1 from the Python twins (operation order and
expression shape preserved; fail-closed arms included; every module's
doc header carries the twin's own evidence citations per §2.1 and
ADR-0002's discipline):

- `port/src/header.rs` — twin `src/catpart/header.py` (32-byte header,
  H1 fields, latin-1 magic decode, the < 32-byte
  [`HeaderError`] refusal).
- `port/src/containers.rs` — twin `src/catpart/containers.py` (B1
  records over the first-2-MB window, laws T1/T3, the kind law K1).
- `port/src/trailer.rs` — twin `src/catpart/trailer.py` (A..G big-endian
  dwords, `CB__END\0`, the 41-byte registration block, byte-exact or
  `None`).
- `port/src/version.rs` — twin `src/catpart/version.py` (CNEXTINFOS
  anchoring within 128 bytes, 8 KB → 64 KB windowing, leftmost anchored
  token, hand-rolled token matcher — the crate carries no regex
  dependency per §2.1).
- `port/src/identity.rs` — twin `src/catpart/identity.py` (C3
  document_name walk, never raises, `None` on absent/duplicate/malformed).
- `port/src/bin/fidelity_cli.rs` — the §2.4 seam, inspect mode only
  (export is V2, #41): file-path argument, the schema-v1 document on
  stdout via serde with **field declaration order = the Python dict
  construction order of `build_inspect_report`**, classified error as
  one JSON line on stderr with exit 1, usage errors exit 2.
- `scripts/fidelity_run.py` — the §4 harness, stdlib-only, dual-mode:
  `--fixtures` (A2 fixtures generated in-process via
  `tests/fixtures_gen.py`, both implementations as subprocesses, the
  same diff code as corpus mode) and default corpus mode (§3.1's
  L1-JSON slice = ALL manifest rows incl. junk; `catpart-inspect` and
  the release `fidelity-cli` driven as subprocesses, one shape for
  both). Flags `--split`, `--slice l1|l2|both` (l2 reports slice-empty
  at V1), `--sample stratified:N`. Outputs: the dated note (figures
  only) + the per-file CSV.
- `tests/test_port_fidelity.py` — the V0 skip-stub replaced by the live
  fixture pin (§7 step 5).

## Decisions recorded (dated, with alternatives)

1. **The L1 error-class vocabulary is the single fitness class
   `crash`** (2026-11-13, V1). The inspect seam's L1-reachable failure
   surface is exactly the two documented file-level refusals of
   `build_inspect_report` (the short-buffer `ValueError` and path-level
   `OSError`), and the Python side's own classification for every one
   of them is `crash` (`src/catpart/fitness/runner.py::_classify_file`:
   "crash covers every exception raised while producing the output";
   the A2 fixture table pins the same mapping — short-file → "the
   `crash` class", `tests/fixtures_gen.py` docstring). `fidelity-cli`
   therefore emits `{"error_class": "crash", "detail": ...}` for both
   refusals; the harness normalizes the Python side's exit 1 to the
   same class structurally (the shipped seam's exit 1), never by
   parsing stderr prose. Rejected: inventing a finer kebab class for
   the short-file refusal (e.g. `header-too-short`) — that class exists
   nowhere in the Python vocabulary, and §3.2's machine contract is
   "the class ... that the fitness classification consumes". The
   collapsed class stays honest because `fidelity-cli` exits 1 ONLY on
   the two documented raise sites: any other port failure panics or
   emits no class line, which the harness records as harness-level
   failure — which never counts as a match (§3.2).
2. **Cargo artifact naming** (2026-11-13, V1): cargo names the §2.4
   binary `fidelity_cli` (underscore), not §4's literal
   `target/release/fidelity-cli` — the `different-binary-name` cargo
   feature is unstable, so the harness resolves both spellings and
   drives `port/target/release/fidelity_cli`. Observation, not a spec
   correction; the seam contract (§2.4) is unaffected.
3. **Stratified sampling rule** (2026-11-13, V1): `--sample
   stratified:N` joins the manifest to the accepted run's report
   (`fitness/history.jsonl` latest accepted row; its `corpus_digest` is
   re-verified against the manifest bytes — a stale basis aborts the
   run) and allocates round-wise proportional seats over
   (detected_version × split × export outcome class) strata — strata in
   descending size order, ties by stratum key, one seat per stratum per
   round; every `magic_ok=no` row is always included (the slice's §3.1
   definition names the junk and the ticket's acceptance requires it;
   6 rows in the current corpus). Within a stratum the picks are
   evenly spaced over the sha256-sorted rows: no RNG, the same N yields
   the same sample.

## Corrections (dated, never massaged)

- **2026-11-13: ceil8 transcription bug, caught by the harness on its
  first fixture-mode run.** The clippy gate (`-D warnings`) flags the
  twin's `((n + 7) // 8) * 8` as a manual ceil-division; the first
  transcription wrote `(n + 7).div_ceil(8) * 8`, which over-rounds the
  names area by one 8-byte slot whenever the name pair is not
  8-aligned (correct: `n.div_ceil(8) * 8`). The release-profile binary
  rejected every record on 8-unaligned fixtures (215/229 non-match on
  the first run — CSV in tmp, not committed); the debug-profile binary
  predated the edit and passed, which is why the unit suite did not
  catch it: its record builder computed the area via the same buggy
  helper (self-consistent). Fix landed with the unit tests re-pinned to
  the twin's literal law values (22 → 24, not 32) so a wrong round-up
  breaks the test instead of passing self-consistently; the fixture
  pin now guards the same class end-to-end at the seam. This is §10
  risk 1's detector doing its job, at integer scale.

- **2026-11-14 (merge fixups, coordinator): two review-driven
  corrections, neither a Fidelity surface change.** (1) The bin file
  renamed `port/src/bin/fidelity_cli.rs` -> `port/src/bin/fidelity-cli.rs`,
  so the artifact is `target/release/fidelity-cli` and §2.4's citation
  is accurate verbatim (decision 2 below is superseded; hyphen bin
  file names build cleanly — no `[[bin]]` section needed; the harness
  already resolved the hyphen spelling first, `fidelity_run.py:157`).
  (2) The post-build stale-binary check in `build_port_bin` is
  unreachable — `cargo build` freshens the artifact mtime even on a
  no-op build, so the check never fired (review F2; the verifier
  utimed the binary to the epoch through the real path and no abort
  fired). The claim "aborts if stale" is dropped: cargo's own rebuild
  is the freshness guarantee, and the missing-binary/build-failure
  aborts remain reachable and pinned. No fixture or corpus row
  changes; gate re-run green after both fixups.

## Fixture-mode parity (§4 fixture mode, the gate)

- Population: 229 fixtures = the A2 variant lists of
  `tests/fixtures_gen.py` (41 valid incl. the canonical shape + 26
  corrupted) swept per `scripts/fidelity_run.py::fixture_matrix` —
  canonical+geometry/composite variants at seeds 0 and 7, plain
  variants at seeds 0-2 × kinds part+product, and every variant once
  more with the C3 identity block present. 458 subprocess runs
  (229 × {python, port}) per gate invocation.
- Result: **229/229 match** — parsed-document equality (§3.2) on every
  fixture that parses, including the corrupted variants; the 7
  short-file refusal rows compare as `crash` == `crash` (decision 1).
  The pin is the gate test `tests/test_port_fidelity.py` (asserts 0
  non-match outcomes, every A2 variant present, and the refusal-class
  parity), green in this worktree's full gate run. The per-invocation
  CSV lives in pytest's tmp (not committed); the committed corpus CSV
  below is the run-level evidence artifact.

## Corpus run (§4 corpus mode, local-only per ADR-0003)

- Command (repo root, the worktree's venv):

  ```
  .venv/bin/python scripts/fidelity_run.py --split all --slice l1 \
      --sample stratified:120 \
      --csv docs/evidence/data/v1-fidelity-l1-claims.csv \
      --note docs/evidence/2026-11-13-v1-port-fidelity.md
  ```

- CSV: `docs/evidence/data/v1-fidelity-l1-claims.csv` — named for the
  `*claims*.csv` glob so `scripts/triage/check_claims_csv_quoting.py`
  covers it from birth (checked: 20 claims CSVs, all rows at header
  width). Column 0 (`row_id`) is the sha256.
- Population (all figures from the CSV): **120 rows** — 82 part, 38
  product; 114 dev, 6 held-out; all 6 `magic_ok=no` junk rows included;
  42 distinct detected_version strata represented.
- Result: **120/120 match; 0 output-mismatch; 0 error-class-mismatch;
  0 harness-level failures** (§3.2: the run is valid — every row is a
  match by evidence). The 11-byte crash row (row
  `4097889236a2af26…`, the corpus's single inspect crash) failed on
  both sides with class `crash` — the fail-closed parity the L1 slice
  requires on garbage.
- Wall-clock (measured, never estimated): in-loop (both subprocess
  passes, CSV `python_seconds`/`port_seconds` sums) **python 6.6 s,
  port 0.6 s**; full-command wall-clock as invoked above **7.4 s**
  (host-measured, includes the release build check). Python dominates,
  as §4's budget basis expects. The run is deterministic: an identical
  re-invocation produced the same 120-row sample (sha256-sorted,
  evenly spaced picks, no RNG) and the same 120/120 match outcome —
  the committed CSV carries that run's timings.

## §4 budget check (declared target, measured against)

- Target (§4): per-ticket sample runs ≤ 15 min at N=100; full dual-slice
  run ≤ 2 h.
- Measured: **7.4 s full wall-clock at N=120** — within the budget by
  ~120× at a larger N. No correction needed; the target stands as
  written. The full-population dual-slice budget (≤ 2 h) is V2+ scope
  (the export slice lands there); extrapolating the L1 pass alone
  (~7 s at N=120 → ~1.8 min at N=1824) suggests it is far inside, but
  that is an extrapolation, not a measurement — recorded as such, not
  as a budget figure.

## Gate (scripts/check.sh mirror of ci.yml)

- ruff: clean (whole tree).
- pytest: **366 passed, 7 skipped** in 17.3 s — the V0 skip-stub
  became a live pass (365 + 8 → 366 + 7, measured on this worktree;
  the fixture pin contributes ~13 s of the total).
- cargo: build native ✓, build wasm32-unknown-unknown ✓, fmt --check ✓,
  clippy -D warnings ✓ (release profile checked too), test ✓ (31
  Rust-internal tests, up from 0 at V0 — the L1 modules' micro tests).
- The gate now covers the port's decode bodies end-to-end through the
  fixture pin: any §2.2 numeric-contract violation that flips an
  integer decision fails it (demonstrated by the ceil8 correction
  above); the float-decision classes land with V2/V3's geometry.

## Scope discipline (the HARD STOP)

Geometry modules (`store`/`pool`/`facets`/`mesh`/`ply`/`errors`/
`export`/`composite`) remain the V0 stubs; no export mode; no WASM
boundary work; no viewer; `src/catpart/` untouched (the reference);
`fitness/` untouched; `docs/evidence/` gained new files only; the spec
untouched. Corpus binaries never committed; the corpus itself was
consumed read-only via the repo-root `corpus` symlink (gitignored),
never left the machine.
