# W7-B — head_ia parity + Ducati Motor degenerates + the 7 official failures

**Branch**: `marathon/w7b-head-ia` (base dae7dd1 = W7 speed-oracle + the
eb9c983/e4cb87a/d8554e0 geometry-counter lineage). **Host**: TARDIS.
**Anti-OOM**: `CARGO_BUILD_JOBS=2 RUSTFLAGS="-C debuginfo=0"`; pytest 1
process; `free -m` before heavy jobs.

## Objectives (order fixed by the Orquestador)

1. Close the last Python≡Rust divergence of the official corpus
   (1,413/1,413): `head_ia` gives 61 declines on Python, 62 on Rust —
   diagnose (vote/tiebreak, candidate order, or the CLI counter) with a
   minimal reproducible case.
2. `Motor.CATPart` (Ducati): 23 degenerate triangles → FAIL. Fix WITHOUT
   relaxing `MAX_DEGENERATE_TRIANGLES = 0` or `manifold`.
3. The 7 remaining official-corpus geometric failures (5 `not-manifold`
   + 2 `degenerate`): same criterion.

## Data inventory

The official corpus is NOT on TARDIS (`/home/alan/catpart-parser/corpus`
absent). The Orquestador sent a micro-batch by HTTP (Gallyfrey):
`w7b-micro.tar`, sha256
`7cd7e547d186d35c40111b11b0fadd7ad80fe3a59b7ea41245ce11b88e417724`
(641 MB), extracted at `/tmp/w7b/`. Contents:

- `corpus/Apoloo13/ASE_III/diseño_3d/moldes/head/head_ia.CATPart`
  (231 MB, sha256 ae85fae7…)
- `corpus/Apoloo13/ASE_III/diseño_3d/modelos_originales/head_ia.CATPart`
  (24 MB, sha256 ccbb7862…)
- `Motor.CATPart` (Ducati, 53 MB, 23 degenerados)
- The 7 official geometric failures (5 not-manifold + 2 degenerate):
  - `corpus/hssnadr/.../LedStrips_Smooth.CATPart` (190 MB, 33 degenerados)
  - `corpus/hssnadr/.../LedStrips_5V_final.CATPart`
  - `corpus/hssnadr/.../M3x16_CHC.CATPart`
  - `corpus/hssnadr/.../M4x10_Poelier.CATPart`
  - `corpus/Dictor/HaneulMyo/model/Guntle.ver5.CATPart`
  - `corpus/Apoloo13/ASE_III/diseño_3d/frente/frente_&_UPPER_teeth.CATPart`
  - `corpus/povdoigt/SP-02/CATIA/CATIA_vol/_NPart#194321.CATPart`

Files needed and received (per the Orquestador's micro-lote message of
2026-11-22): both `head_ia` twins, `Motor.CATPart`, and the 7 failure
files. Nothing else missing for the three objectives; the full 1,413-file
corpus stays with the Orquestador (the parity sweep 1,413/1,413 is
re-run there after the fix lands).

## Log

- 2026-11-22: worktree `~/marathon-wt/w7b` created from
  `origin/marathon/w7b-head-ia` (dae7dd1). Base check: d8554e0 (the
  double-accumulated `extended_members_filtered` fix) IS an ancestor of
  dae7dd1, so the W1 lineage's counter fix is already in. Micro-batch
  downloaded from Gallyfrey (Tailscale route; sha256 verified
  `7cd7e547…417724`, 641 MB) → `/tmp/w7b/` (10 files: both head_ia,
  Motor, and the 7+1 failure files).

### Objective 1 — head_ia parity (CLOSED, patch handed off)

- Root cause: `facets::facet_headers` (Rust) kept 6-byte candidates
  whose bytes carry `ff` at BOTH +4 and +5; the Python twin's
  `header_len==6` filter (ff-first over 4,5,6) drops them. One phantom
  header at 229,648,727 in the 231 MB twin's store flipped the width
  vote of the record at 229,647,190 (u8 vs u24be) → 62-vs-61 declines,
  533-vs-503 filtered members, +352 triangles. Probe:
  `scripts/triage/w7b_facet_ff4_probe.py`.
- Second divergence found in the same sweep: the Rust
  `identity-table-walk` and `identity-raw-array` paths dropped
  `relaxed_loops_accepted/declined` (Guntle, M3x16 — PLYs identical,
  key presence differed).
- Patch 001 + 004 fix both; verified: head_ia 231 MB and 24 MB
  byte-identical PLYs, semantically identical summaries. Evidence:
  [2026-11-22-w7b-head-ia-parity.md](../2026-11-22-w7b-head-ia-parity.md).

### Objectives 2+3 — Motor + the official geometric failures (CLOSED, patches handed off)

- Motor's 23 degenerates = two 0x42 records whose u8 winner is a
  half-read of a u16 stream; the wider candidate was excluded because
  FALSE strip headers inside the record's own ref bytes truncated
  `nxt`. Same class: NPart194321 (3 degenerates, u24be at width 3).
  Fix = the #65 exact-tiling exception extended to the short form +
  the merged-boundary exact slot (patch 002). Motor 23→0 PASS,
  NPart 3→0 PASS.
- M4x10 + frente: the exact slot missed facet-header tiles (u16be
  ending exactly ON a 0x47). Same patch fixes both → PASS.
- Guntle / M3x16 / LedStrips_5V: full rank ties picked the narrower
  half-read; the kept over-use loop broke manifold. Patch 003 flips
  the width tiebreak to prefer wider. All three → PASS.
- The short-form law change is corpus-wide: the Orquestador's 1,413
  re-run is the validator; patch 003 is a one-line revert if it
  regresses. Evidence:
  [2026-11-22-w7b-degenerate-manifold-fixes.md](../2026-11-22-w7b-degenerate-manifold-fixes.md).

### Final sweep (all patches, both engines, 10/10 files)

| file | L2 (pre) | L2 (post) | parity |
| :--- | :--- | :--- | :--- |
| head_ia 231 MB | PASS (62 vs 61 declines) | PASS, 649,136 tri (+8,767), boundary 5,482 (−2,349) | ply=I json=I |
| head_ia 24 MB | PASS | PASS (byte-unchanged) | ply=I json=I |
| Motor | FAIL degenerate (23) | **PASS**, 0 | ply=I json=I |
| NPart194321 | FAIL degenerate (3) | **PASS**, 0 | ply=I json=I |
| Guntle.ver5 | FAIL not-manifold | **PASS** (3,093 tri) | ply=I json=I |
| LedStrips_5V | FAIL not-manifold | **PASS** (16,130 tri) | ply=I json=I |
| M3x16_CHC | FAIL not-manifold | **PASS** | ply=I json=I |
| M4x10_Poelier | FAIL not-manifold | **PASS** (2,426 tri) | ply=I json=I |
| frente_&_UPPER_teeth | FAIL not-manifold | **PASS** (66,444 tri) | ply=I json=I |
| LedStrips_Smooth | FAIL degenerate (33) | **PASS**, 229,732 tri (+5,297), boundary 38,888 (−27,385) | ply=I json=I |

Gates: `check-fast` OK (107 tests, engine-parity pins included),
`test_port_fidelity.py` full matrix OK, composite export suite
95 passed / 5 skipped, port composite unit tests 24 passed.
`MAX_DEGENERATE_TRIANGLES = 0` and the manifold gate: untouched.

Handoff patches (`scripts/triage/w7b-handoff/`, verified to apply
cleanly on dae7dd1 and to reconstruct the verified tree exactly):
`001-facet-headers-ff-at-plus4.patch` (facets.rs),
`002-short-form-exact-exception.patch` (composite.py+composite.rs),
`003-vote-ties-prefer-wider.patch` (vote.py+vote.rs),
`004-relaxed-counters-table-walk.patch` (composite.rs).
The W1-B integration applies all four; the sources in THIS branch stay
at base (composite/facets/vote are W1-B's exclusive territory).
