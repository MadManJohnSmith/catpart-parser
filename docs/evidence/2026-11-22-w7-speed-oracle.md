# Evidence: W7 speed oracle — the native-engine fitness fast path, the fast gate and the ground-truth harness

**Date**: 2026-11-22
**Status**: COMPLETE for the three dispatched hypotheses. Every figure
below is a row of [w7-speed-claims.csv](data/w7-speed-claims.csv),
[w7-gate-claims.csv](data/w7-gate-claims.csv) or one of the per-file
[w7-parity-claims-*.csv](data/) artifacts, or a measured run reproduced
by section 6's commands.
**Scope**: `src/catpart/fitness/`, `scripts/benchmark_ground_truth.py`,
`scripts/check-fast.sh` (NEW — `scripts/check.sh` untouched), their
tests, this evidence tree. `src/catpart/geometry/`, `src/catpart/product/`
and their ports are untouched (the fast path DRIVES the shipped
`fidelity-cli` binary; it imports no geometry code beyond the runner's
existing seams).
**Shipped code**: `src/catpart/fitness/speed.py` (new), `src/catpart/fitness/runner.py`
(`run_fitness`'s `engine` parameter — default `python`, byte-for-byte
historical), `scripts/check-fast.sh` (new), `scripts/benchmark_ground_truth.py` (new).
**Branch**: `marathon/w7-speed-oracle` (base d8554e0), TARDIS.

---

## 1. Executive summary

| Fact | Verdict | Anchor measurement |
| :--- | :--- | :--- |
| The fitness workload's cost is the L2 export, not L1 | **Closed.** In-process Python: 1.17 s L1 vs 292.6 s L2 over the 757-file submarine corpus — L2 is 99.6% of the sweep. | `w7-speed-claims.csv` row `submarino-757/python/cold` |
| The port binary is a drop-in fast engine | **Closed.** `fast` engine (Python L1 + `fidelity-cli export` L2): 19.8 s — **14.9x** the Python sweep on the submarine corpus, **9.8x** on the 762-file candidates corpus (11 GB, five giant stores), with the sweep parent process flat (55.0 MiB peak vs 267.9 MiB on the submarine; 227.3 MiB vs **5323.0 MiB** on the candidates). | `w7-speed-claims.csv` rows `*/fast/cold` |
| Results are identical | **Closed.** Zero divergences vs Python on the full decision surface (classification, detected_version, kind, L2 status/error_class/failed_check/counts/warning-classes) over all 757 + all 762 real files — the five giant stores included (a 2.72M-vertex export agrees per-file) — for both native engines. | `w7-parity-claims-{python,fast,rust}-sub757.csv` + the `compare` runs of section 6 |
| The cache makes re-evaluation near-free | **Closed.** Warm `(file_sha256, code_digest)` cache: 1.03 s for the whole corpus (hashing still pays; the digest invalidated itself when this note's comparator fix changed `speed.py`). | `w7-speed-claims.csv` row `submarino-757/fast/warm` |
| A <15 s fast gate exists; the full gate is untouched | **Closed.** `scripts/check-fast.sh`: 4.15 s, 107 tests, loud-fail on a missing port binary. `check.sh` byte-identical to base. | `w7-gate-claims.csv` |
| Ground truth is reproducible per merge | **Closed.** `benchmark_ground_truth.py`: exact vertex-set Chamfer/Hausdorff/area_ratio, end-to-end zero on identical geometry (the shipped export vs its own mesh as STL), STEP refused by name, blind spot pinned. | `tests/test_benchmark_ground_truth.py` (11 tests) + section 5 |

## 2. Hypothesis 1 — the native-engine fast path

### 2.1 What the L2 dominance means

The measured breakdown on the submarine corpus (757 V5 files, 3.5 GB,
all `clean`, L2 446 pass / 311 fail — every engine agrees):

- **Python (before)**: 294.7 s wall, of which L1 1.17 s and L2 292.6 s
  (99.6%); peak RSS 267.9 MiB (the parent's mesh building drives it);
  389 ms/file.
- **fast (after)**: 19.8 s wall — L2 17.6 s through the port binary,
  L1 1.15 s in-process (a subprocess spawn for the fast L1 would LOSE:
  Python in-process inspect is 1.7 ms/file vs ~2.4 ms for a
  `fidelity-cli inspect` round trip); peak RSS 55.0 MiB parent and
  55.0 MiB child (transient per-file, not concurrent).
- **rust (both phases native)**: 22.7 s — same L2, L1 pays the spawn.
  Kept as the prototype the brief asked to measure; `fast` is the
  recommended sweep engine.
- **fast warm cache**: 1.03 s (757/757 hits) — the SHA-256 hashing of
  3.5 GB (0.95 s) is the floor; nothing else runs.

### 2.2 The engines and the gates that do not move

Three engines, one classification contract
(`src/catpart/fitness/speed.py::engine_seams`):

- `python` — the runner's own seams, unchanged (the existing
  monkeypatch-based tests keep faking the seam where they always did).
- `rust` — `fidelity-cli inspect` + `export` subprocesses; the runner's
  schema validation, minimal invariants and L2 sanity gate run on the
  port's outputs exactly as on Python's.
- `fast` — Python L1 + Rust L2.

The port's exit-1 classified failures carry the same vocabulary at the
same raise sites as the Python contract (`bin/fidelity-cli.rs`'s
documented seam law), so `_measure_l2`-shaped records come out of both
engines; any non-0/1 exit is recorded as the crash/export-crash class
with a `harness:` detail — a broken seam can never silently become
clean data, and one broken file never aborts a sweep.

`run_fitness` gained `engine: str = "python"`; the default path is
byte-for-byte historical (pinned by the whole pre-existing suite). The
speed oracle's cache is deliberately NOT consumed by `run_fitness`: it
stores the reduced per-file record, and the runner's committed report
carries the full inspect document (`container_names` and all).

### 2.3 The incremental cache

`CodeCache` is an append-only JSONL keyed `(file_sha256, code_digest)`.
The digest is the SHA-256 over `speed.py` + `runner.py` +
`invariants.py` + the port binary's bytes: a rebuilt decoder, a changed
gate or a changed seam invalidates every entry at once — no
stale-result window outlives the change that would make one. The
digest's self-invalidation was exercised live during this ticket: the
comparator's prose fix (2.4) changed `speed.py`, and the next sweep
re-ran all 757 files (the pre-fix cache went unused). Cache hits still
pay the file digest — it IS the key — so a warm sweep costs ~1 ms/file
on this corpus, all of it hashing.

### 2.4 Equivalence, and the prose finding

The comparator diffs the decision surface only. The first full-corpus
comparison reported 80 divergences — all of them the `detail` PROSE of
the `primary-loop-relist-skip` warning: the Python exporter says "and
carrying no degenerate-triangle skips at all", the port says "and the
candidate carrying no degenerate-triangle skips at all". That is
exactly the field the Fidelity contract declares never-compared
(spec §3.2: "`detail` is never compared byte-wise"), and the runner's
aggregates read `w["class"]` only. The comparator now carries the
warning CLASSES (the decision surface), drops the prose, and the
committed parity CSVs store the class list. Post-fix: **0 divergences**
over 757 files for BOTH native engines — `w7-parity-claims-*.csv` are
the per-file rows (prose-free; the `error` detail column was dropped
for the same reason).

The finding is a DATA point for the Fidelity harness's corpus mode (it
only compares fixture-mode summaries byte-wise; on this corpus the
twins' wording diverges for this warning class). No action on the port
— the contract says prose need not match.

### 2.5 Streaming and RAM

`run_sweep` holds ONE file in flight: its CSV row is written and
flushed before the next file is touched (a killed sweep leaves a
prefix-complete CSV — pinned by a test that kills the sweep mid-run),
and only aggregates stay in memory. Peak RSS is measured via
`getrusage`, not estimated: parent 55.0 MiB peak on the 3.5 GB corpus
(33.4 MiB when the run is warm-cache-only) and 227.3 MiB on the
candidates corpus; the child's peak is one file's decode (55 MiB on
~5 MiB stores; section 4 for the 198 MiB store). The per-run cache
lives at `--cache` (default: a temp path) — a scratch artifact, never
committed.

## 3. Hypothesis 2 — fast gate vs full gate

`scripts/check-fast.sh` (NEW; `check.sh` untouched, verified byte-identical
to base `d8554e0` in this tree):

- **Covers**: `ruff check .`; the fitness seams' unit tests (runner, L2,
  history, L3) + `test_cli_inspect.py` + the claims-CSV quoting checker;
  and ENGINE PARITY over the A2 fixture variants through the REAL
  release `fidelity-cli` (`test_fitness_speed.py`, ~2 s).
- **Measured**: 4.15 s wall, 107 passed (warm checkout; first run on a
  cold tree pays one `cargo build --release --locked`, the same build
  the fixture-mode fidelity test pays inside the full gate).
- **Does NOT cover** (stated in the script header; `check.sh` remains
  the only pre-push authority): the full dual-slice fixture-mode
  fidelity matrix (`test_port_fidelity.py`, 60 s measured — it drives
  both shipped seams over every fixture twice and diffs PLY bytes),
  every cargo step (build native + wasm32, fmt, clippy -D warnings,
  cargo test), wasm-pack --node, the pkg sync, node --test, Playwright
  acceptance, and the rest of the Python suite (966 tests, 49.9 s).
- **Fail-closed**: no release binary + no cargo ⇒ exit 1 with the build
  command, never a silent skip (the dispatch-recipes hard rule).

## 4. The giant files (the OOM-risk case, measured)

The candidates corpus is the submarine's 757 files PLUS five
single-part vehicles whose stores dwarf the submarine's (198/98/52/48/14
MiB; up to 2.72M vertices). Corpus-level (`w7-speed-claims.csv` rows
`candidatos-762/*`):

- **Python (before)**: 765.1 s wall (1004 ms/file); peak RSS
  **5323.0 MiB in the parent process** — on a host with 15.4 GiB RAM
  and ~5-6 GiB free at run time, i.e. the in-process Python fitness
  evaluation of this corpus is one concurrent marathon job away from
  an OOM kill. This is the anti-OOM case the brief warned about,
  measured.
- **fast (after)**: 77.8 s (**9.8x**); parent 227.3 MiB flat, child
  peak 1194.0 MiB (the single 198 MiB store's native decode,
  transient, freed between files).
- **rust (both phases)**: 81.3 s (**9.4x**); parent 32.9 MiB, child
  1197.0 MiB.

Per-file on the giants (L2 seconds, python → fast): Aston 198 MiB /
2.72M verts 378.7 → 41.6 (**9.1x**); Ducati 2.0M verts 57.5 → 11.8;
Audi 20.7 → 2.9; Dodge 27.4 → 1.4 (**19.6x**); McLaren 9.9 → 0.12.
The L2 records agree per-file across engines on every giant (same
vertex/triangle counts, same status) — parity holds on the monsters.

Anti-OOM environment used throughout TARDIS: `CARGO_BUILD_JOBS=2`,
`RUSTFLAGS="-C debuginfo=0"`; `free -m` checked before every heavy run.

## 5. Hypothesis 3 — the ground-truth harness

`scripts/benchmark_ground_truth.py`: one reproducible
`.CATPart` ↔ `.STL`/`.OBJ` comparison per merge.

- Metrics: `area_ratio` (streaming Heron pass per mesh), `chamfer`
  (symmetric mean directed distance, both directions reported), and
  `hausdorff_max`/`hausdorff_p95` (symmetric = max of the two directed
  values, each direction reported). Nearest-vertex distance is EXACT
  for the vertex sets: a uniform voxel grid (cell = reference bbox
  diagonal / 128, `--cell-size` override) with ring-outward search
  until the found best cannot be beaten by an unscanned cell — an
  approximation in NEITHER direction.
- What the harness does NOT discriminate (stated once, pinned as a
  negative fixture): vertex-set sampling only — a reference differing
  only in interior triangle density passes Hausdorff/Chamfer and is
  caught ONLY by `area_ratio`; normals/orientation are never compared.
- `.STEP` reference: refused BY NAME (exit 2,
  `step-reference-unsupported`) — STEP is B-rep, not tessellation; a
  "STEP comparison" here would fabricate a mesh.
- `--selftest` pins five edges on synthetic fixtures (the
  negative-fixture rule): identical meshes → 0 everywhere; unit shift
  → Hausdorff exactly 1.0; 2x scale → `area_ratio` exactly 4.0; the
  density blind spot → Hausdorff 0 with area 2x; the area catch.
- `tests/test_benchmark_ground_truth.py` (11 tests) proves the harness
  END TO END: the shipped export's PLY (a real geometry-bearing
  fixture through `build_export`) converted to binary STL measures
  `hausdorff_max = 0`, `chamfer = 0`, `area_ratio = 1` against the
  same `.CATPart`; a 1-unit-shifted reference shows up as Hausdorff
  ≥ 1 A→B; a store-less CATPart is the named `missing-geometry-store`
  outcome; batch mode streams one CSV row per pair.

## 6. Reproduction

```
# the sweep (any engine; --limit N for a subset)
.venv/bin/python -B -m catpart.fitness.speed sweep \
  --root <corpus-root> --engine fast --csv /tmp/sweep.csv --cache /tmp/cache.jsonl

# the equivalence proof (exit 0 = zero divergences)
.venv/bin/python -B -m catpart.fitness.speed compare /tmp/python.csv /tmp/fast.csv

# the fast gate / the full gate
./scripts/check-fast.sh
./scripts/check.sh

# the ground-truth harness (single pair / batch / selftest)
.venv/bin/python -B scripts/benchmark_ground_truth.py --catpart F.CATPart --reference R.stl
.venv/bin/python -B scripts/benchmark_ground_truth.py --batch pairs.csv --csv out.csv
.venv/bin/python -B scripts/benchmark_ground_truth.py --selftest
```

Engine timings vary with store mix; the classifier/L2-record equality
claim does not (it is pinned per-file by the committed parity CSVs and
re-proven by every `compare` run's exit 0).

## 7. Artifacts

| Artifact | What it pins |
| :--- | :--- |
| `data/w7-speed-claims.csv` | the before/after table: corpus × engine × cache state, wall/phase seconds, ms/file, peak RSS, speedup, cache hits, classification and L2 counters |
| `data/w7-parity-claims-python-sub757.csv` | per-file rows, Python engine, submarine corpus (prose-free) |
| `data/w7-parity-claims-fast-sub757.csv` | per-file rows, `fast` engine — zero divergences vs the Python rows |
| `data/w7-parity-claims-rust-sub757.csv` | per-file rows, `rust` engine — zero divergences vs the Python rows |
| `data/w7-gate-claims.csv` | the gate timings: check-fast 4.15 s / 107 vs the full Python suite 49.9 s / 966+21skipped |
| `tests/test_fitness_speed.py` | the pinned contracts: engine parity (fixtures + mini manifest), cache semantics, streaming prefix-completeness, digest binding |
| `tests/test_benchmark_ground_truth.py` | the ground-truth harness's pinned edges incl. the end-to-end zero |
