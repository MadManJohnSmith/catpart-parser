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
