# W19 progress — marathon wave 4, branch `marathon/w19-stream-version`

Base: `647f324` (main with W1-B/W10/W4/W9/patches). Owner: W19 (B9 —
versionado y compresión no explorada de streams CATCGM).

## Unit 1 — the stream-version census (B9 complete)

**Commit**: this one. Evidence:
[2026-11-22-w19-stream-version.md](../2026-11-22-w19-stream-version.md).
Claims: `docs/evidence/data/stream-version-claims.csv` (SV-01..SV-16).
Data: `stream-version-files.csv` (4,314 rows), `stream-version-tags.csv`
(125 texts × major). Population: 1,438 part rows (sha256 order), 0 probe
failures, ~40 min.

**Delivered**:

- `src/catpart/geometry/stream_version.py` — the fail-closed census
  core: exact-length framed tag scan (the `[u32le L][L ASCII]` law),
  zlib FCHECK pre-filter, gzip/bzip2/xz/raw-LZMA/lz4/zstd/snappy
  signatures, eof-law deflate/bz2/xz verification, the `36 08` writer
  tag at +112 and its drift scan. Ported (scan arms) 1:1 to
  `port/src/geometry/stream_version.rs` (no compression crate in the
  port — the verify arms stay Python-side, documented asymmetry).
- `scripts/triage/stream_version_probe.py` — the corpus census (three
  territories: CGMGeom regions, CATPrtCont regions, store bodies; the
  shipped locator walk for spans/rejections).
- `tests/test_stream_version.py` — 35 corpus-free tests incl. the
  greedy-over-extension regression and the Rust-parity fixtures.
- Port tests: 7 (`cargo test geometry::stream_version`).

**Findings (B9 verdict)**:

1. **0 verified compressed sub-streams corpus-wide** (fail-closed eof
   law; zlib head + length-framed + gzip/bzip2/xz candidates). The
   scanner skips no compressed content at the stream level. BS-19's
   entropy negative extended corpus-wide with verification.
2. **No alternate stream/writer header**: `FINJPL` on 15,786/15,786
   blocks all majors (the +112 pin is a ~10% minority law — offsets
   drift with the preamble; the TEXT never varies); `2X-0` = 0
   corpus-wide (GE-V7's second arm refuted).
3. **The GE-V7 tags generalize**: a 125-text generation-string
   vocabulary — the `N-0` ladder (N=1..29; R21 carries 137,691
   occurrences; R17/R19/R20 sparse; R15/R16/R18/R23-R32 zero) and the
   reversed `0-N` family (N ≤ 59, R18-R23+unknown). Content-dependent,
   not writer-version-deterministic.
4. **17 auxiliary store headers, all V5R19SP5HF0**: ff×8/zeros×8 valid,
   `dword12` = the document-catalog tail length (N6-validates 17/17 —
   new law); `dword8` pointer law OPEN after 2 attempts (reopen
   criterion recorded). Zero file-level flips (all 17 files open via
   their real stores).
5. The no-store population (121 files, all `unknown` version) is
   unchanged — the missing-store note's bag-rep class.

**STOP**: B9 is delivered as the taxonomy + rates + the two byte laws +
the open-pointer negative. The CGM record stream's own decode (the
~44-B dictionary units and the unframed residue) stays with the
cgm-grid probe's §7 verdict — that decode is NOT part of B9's scope.
Reopen criteria: (a) SV-15's `dword8` pointer law; (b) a corpus file
with a verified compressed territory (none today); (c) a writer tag
text other than `FINJPL` (none today).

## Environment notes

- The worktree venv: `.venv` created in-worktree (`python3 -m venv
  .venv && .venv/bin/pip install -e '.[test,lint]'`); `python -B` maps
  to `.venv/bin/python -I` in the probe/test commands.
- Anti-OOM honored: single-process pytest, single mmap at a time,
  bounded verification budget, `gc.collect()` every 100 files;
  `CARGO_BUILD_JOBS=1 RUSTFLAGS="-C debuginfo=0"` for the cargo steps.
- No subagents; all work executed directly in this thread.

## Gate status (honest, 2026-11-22)

`scripts/check.sh` steps, this branch at base 647f324 + unit 1:

- ruff: **PASS**; pytest: **PASS** (1,038 passed, 21 skipped — the
  corpus-free suite + 35 new); claims-CSV quoting: **PASS** (106 files);
  cargo build native + wasm32: **PASS**; `cargo test --lib`: **PASS**
  (259 = 252 base + 7 port tests).
- `cargo fmt --check` and `cargo clippy -D warnings`: **RED AT BASE**
  under the host toolchain (rustc/clippy 1.99.0 — a version newer than
  the gate's; verified by `git stash`: **34 clippy errors** and 3
  rustfmt diffs in `face_gp.rs` at clean base, across
  display/composite/export/face_gp/mesh/ply/store/transforms — W16/W15/
  W17-owned files this task must not touch). After the two clippy fixes
  in the new `stream_version.rs` (collapsible-if, `is_multiple_of`), the
  base-red errors count is unchanged by W19: **0 in W19's files** (the
  new module passes fmt + clippy; `cargo fmt` was scoped to the new
  file with `--edition 2024` and the accidental face_gp.rs reformat it
  caused was reverted before commit). CI remains the authority; the
  drift is recorded here for the coordinator (other workers will hit
  it if they `rustup component add rustfmt clippy` on this host).
