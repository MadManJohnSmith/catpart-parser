# Evidence: the composite short-form OOB gate and the 0x41/0x44 primitive

**Date**: 2026-11-20
**Status**: COMPLETE — the six crashers (Audi R8 `IndexError`, five submarine
`KeyError`s) export, the 0x41/0x44 primitive is pinned to **u16 little-endian
with a u8 fallback**, and the two Audi false headers are declined. Every figure
below is a row of
[composite-relaxed-primitive-claims.csv](data/composite-relaxed-primitive-claims.csv)
or a measured export reproduced by section 6's commands.
**Scope**: composite stores (the identity table walk's element space); the
short-form strip records inside them.
**Shipped code**: `src/catpart/geometry/composite.py`
(`parse_strip_records` — the oob-first rank, the post-vote refs gate, the
u16le candidate, the two fail-closed straddle conditions;
`RELAXED_SHORT_MARKERS` — the family note).
**Rust port**: `port/src/geometry/composite.rs` (the same rank tuple, the same
gate, the same two conditions, twin unit tests). `port/pkg` and
`site/viewer/pkg` are NOT rebuilt here — the coordinator refreshes both when
Fase 2 closes (no wasm difference is claimed by this note).
**Probe**: the diagnosis' in-process harnesses
(`/home/alan/.local/state/catpart-parser/subagents/s1-composite-crash-manifold/`,
read-only) plus the repo's own corpus A/B (section 6).

---

## 1. Executive summary

| Fact | Verdict | Anchor measurement |
| :--- | :--- | :--- |
| The crash mechanism | **Closed.** The short-form vote ranked `repeats` above `oob` and re-checked nothing after the vote, so a w2be misread of a 0x41/0x44 record won and reached `_triangulate` with refs past the element space. | 6 records in 6 files: Audi `IndexError` at `_dup_pin_map` (`elements[r]`), five submarine `KeyError: written_rank[r]` in the RELAXED pass |
| The gate | **Symmetric to the extended law**: rank `(exact, oob, repeats, nonplanar, …)` + post-vote "refs must resolve" gate. | Audi R8: 174,297 triangles, 0 degenerate, L2 **pass** with the gate alone (the false header still decoded as a u8 record: +1 triangle) |
| The primitive | **Pinned: u16 little-endian**, u8 the compact fallback, for `0x41/0x44` only. | 8 of the 10 OOB records read in bounds under the primitive (6 u16le, 2 u8); the other 2 are byte patterns, not records |
| The two false headers | **Declined, not decoded.** Audi `0x301e912` and `0x2a3f1b7` sit inside a neighbouring record's u16 stream and their u16 block swallows a real `0x47` (`0x301e92c`: n-law 116 = 3·8+92). | with the primitive + both fail-closed conditions: Audi 174,303 triangles, 0 degenerate, L2 **pass**, neither offset in the accepted records |
| Audi R8 target | **Met.** | 174,303 triangles (diagnosis guard baseline 174,292; the +11 is the recovered u16le geometry), 114,314 vertices, **0** degenerate, L2 **pass** |
| Submarine target | **Met.** | the five `export-crash:KeyError` rows now export: 1300 / 1307 / 1014 / 4601 / 4198 triangles; MD-Running gear-B2 flips to L2 **pass** (+8 manifold triangles vs the gate alone, the diagnosis' repair arm) |
| Corpus A/B | **0 L2 regressions**: 0 pass→fail, 0 degenerate changes, 0 error-class changes over 1,442 parts. 4 parts carry a triangle-count correction (net −83) because their u8 readings were half-reads of u16le streams. | 1,442 parts exported twice (main @ `1f752f0` vs this branch) |
| Rust parity | **Exact** on all six target parts. | same vertex/triangle counts from `fidelity-cli export` |

## 2. The gate (crash law)

`parse_strip_records` used the rank

```
(exact tiling, repeats?, oob?, nonplanar, width, k)
```

and accepted the winner unconditionally. A w2be candidate with no repeated refs
beat an in-bounds candidate with repeats even when every w2be ref was past the
element space; `_triangulate` then indexed with it (`KeyError` in the RELAXED
pass, `IndexError` in `_dup_pin_map` for the mixes that carry skip slots). The
extended-header law already had both halves of the fix (its rank puts `oob`
before `repeats` and its winner is re-checked). #66 makes the short-form law
the same:

- rank `(exact, oob, repeats, nonplanar, u16?, endian?, width, k)`;
- after the vote, a winner whose refs leave the element space is **declined**
  (the record stays unresolved; it never reaches `_triangulate`).

The gate alone removes all six crashes and opens Audi R8 completely
(174,297 triangles, 0 degenerate, L2 pass). It also stops the two Audi false
headers — but for the wrong reason: their committed winner was the OOB w2be
candidate, and with `oob` ranked first their in-bounds u8 reading wins instead
and decodes one bogus triangle. That is what the primitive's second condition
below closes.

## 3. The primitive — byte evidence

The 0x41/0x44 families carry no 12-B normal; #61 admitted them under the
generic tiling law but left the reading unpinned. The ten OOB records the
diagnosis forensically verified read as follows (offsets are absolute in the
cited part; `counts` are the committed table):

| part | offset | mk | n | counts | committed w2be | primitive reading |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Audi R8 | `0x2a3e419` | 0x41 | 6 | [6] | `[64519,774,52487,775,1286,52481]` (3 OOB) | **u16le** `[2044,1539,1997,1795,1541,461]`, 0 OOB |
| Audi R8 | `0x301e912` | 0x41 | 9 | [4,2,3] | 8/9 OOB | **false header** (declined) |
| MB-chair-A | `0x88b70` | 0x44 | 12 | [12,0] | 12/12 OOB | **u16le** `[69,72,73,74,75,76,70,66,65,64,68,328]`, 0 OOB |
| MB-chair-B2 | `0x886c1` | 0x44 | 12 | [12,0] | 12/12 OOB | **u16le** `[57,54,53,52,51,50,56,60,61,62,58,310]`, 0 OOB |
| MB-chair-B2 | `0x8899c` | 0x44 | 12 | [12,0] | 12/12 OOB | **u16le** `[170,167,166,165,164,163,169,173,174,175,171,423]`, 1 OOB (>409) |
| MB-hatch-tapa-MDC | `0x98549` | 0x41 | 27 | [27] | 21/27 OOB | **u8** `[36,29,27,34,…,1]`, 0 OOB (block ends on the next 0x4b header) |
| MB-hatch-tapa-MDC | `0x9897f` | 0x41 | 27 | [27] | 21/27 OOB | **u8**, 0 OOB |
| MD-Running gear-B2 | `0x823ad` | 0x41 | 6 | [6] | 6/6 OOB | **u16le** `[562,647,392,699,648,391]`, 0 OOB |
| MD-Running gear-B2 | `0x830da` | 0x41 | 6 | [6] | 6/6 OOB | **u16le** `[533,645,390,683,646,389]`, 0 OOB |
| MD-Running gear-B4 | `0x828a5` | 0x41 | 6 | [6] | 6/6 OOB | **u16le** `[1818,1848,2359,1973,1847,312]`, 0 OOB |

The u16le values land in the ref cluster of the neighbouring big-endian
records (Audi `2044/1997/1795` against the store's `0x07d0..0x07db` range
2000–2011), which is the independent check that the reading is the truth and
not just an in-bounds coincidence. Eight of the ten records are fully
in bounds under the primitive (6 u16le + 2 u8). MB-chair `0x8899c` is the
one marginal u16le record (423 > 409): the OOB rank keeps its in-bounds u8
reading, so it still exports and is not a crash case. The tenth record is the
Audi false header of section 4.

### 3.1 Why u8 is a fallback and not a tie-breaker

The committed width preference is the narrower one, which would pick the u8
reading whenever it is in bounds — exactly the crashes' failure mode in
reverse (the Audi record's u8 bytes `[252,7,3,6,205,7]` are the low/high bytes
of the u16le refs, all in bounds). The relaxed family's rank therefore prefers
a u16 candidate over a u8 candidate (`0` vs `1` in the `u16?` slot); u8 wins
when both u16 readings are out of space (the 2 MB-hatch records) or when the
u16 candidate is infeasible. The other markers keep the committed rank: their
two slots are constant `0`, so their vote is byte-identical.

## 4. The false headers — the two fail-closed conditions

`0x301e912` is not a record: its bytes are a slice of the preceding record's
u16 stream, and a real extended header follows at `0x301e92c`
(`01 47 08 08 04 ff`, n = 116 = 3·8 + 92, counts 4+4+7+9+5+7+9+15+10+7+7+8 =
92 — exact). The candidate's own u16 block would end at `0x301e92f`, three
bytes past that header, reading its last ref `2119` from the header's
`47 08`. `0x2a3f1b7` is the same shape before a real `0x47` at `0x2a3f1cb`
(n-law exact). Two conditions decline them:

1. **u16le candidates cannot swallow a 6-byte header.** A u16le candidate
   whose block straddles a later extended-header candidate is a misread.
2. **A u8 winner cannot be a half-read of a u16le stream.** If the u8 winner's
   2n-wide block straddles a 6-byte header, reaches at least one whole ref
   past it, and its u16le refs are all in bounds, it is a half-read of that
   stream and the record is declined (the `0x301e912` signature: refs
   `1264/1098/770/903/1008/932/1008/391/2119`, all inside 5,561 elements).

The corpus census that keeps condition 2 from declining real records: over
1,442 parts, only 5 *accepted* relaxed records straddle an extended candidate.
Three are u8 winners — SP02 `0x4934b` (straddles by the single header byte;
`end == h6 + 1`), M3x10 `0x19f5258` (same), tn.1.1.1 `0x215085` (u16le refs
contain one OOB ref under the true pairing, so the u8 reading is not a
complete u16le stream). The other two are w2 winners and unchanged
(TerminalBlockCI `0xa1a1c`, CRYSTAL-SMD `0x4af4b` — both established big-endian
readings whose next extended candidate is a byte pattern inside the refs).
Every verified u16le/u8 record clears its next extended candidate
(`end2 < h6`), so both conditions only touch the two false headers and the one
ambiguous tn record (section 5.2).

## 5. Verification

### 5.1 Targets

| target | result |
| :--- | :--- |
| Audi R8 (`AUDINSKLOPIC_AllCATPart.CATPart`) | **0 crashes**, 174,303 triangles, 114,314 vertices, **0** degenerate, **L2 pass** |
| MB-chair-A | 1,300 triangles, 0 degenerate (L2 fail `not-manifold`, the documented #50 population, pre-existing) |
| MB-chair-B2 | 1,307 triangles, 0 degenerate (same pre-existing class) |
| MB-hatch-tapa-MDC | 1,014 triangles, 0 degenerate (same) |
| MD-Running gear-B2 | 4,601 triangles, **L2 pass** (the +8 manifold recovery of the diagnosis' repair arm) |
| MD-Running gear-B4 | 4,198 triangles, 8 degenerate (pre-existing `degenerate-triangles` failure, unchanged by the gate/primitive attribution) |

### 5.2 Corpus A/B (main `1f752f0` vs this branch, 1,442 parts)

| measure | before | after |
| :--- | :--- | :--- |
| L2 pass | 1,194 of 1,442 parts | identical |
| L2 status changes | — | **0** |
| degenerate-count changes | — | **0** |
| error-class changes | — | **0** |
| triangle count | 7,100,599 | 7,100,516 (−83) |

The four parts whose triangle count moved are the primitive correction, all
L2-stable with identical vertex counts:

| part | triangles | why |
| :--- | :--- | :--- |
| `M3x20_CHC` | 2031 → 2026 | one 0x44 record's u8 reading `[16,51,15,59,20,123,18]` was a half-read; u16le `[4147,3899,5243,4741,4738,4745,4226]` is the stream |
| `M3x30_CHC` | 2711 → 2710 | same shape (`[17,46,16,175,22,1,19]` → `[4398,4271,5633,5021,5019,5023,4517]`) |
| `LQFP-64` | 15587 → 15512 | 18 0x44 records flipped from alternating-zero u8 half-reads (`[0,239,0,196,…]`) to u16le (`[239,196,198,…]`); the corrected loops trade 75 mesh-guard units |
| `tn.1.1.1` | 4348 → 4346 | the ambiguous 0x41 `0x215085` is declined by condition 2 (u8 refs are a half-read; the u16le block crosses a real 0x47); −2 triangles, fail-closed |

The one warning-class change is BUZ-SMD (`curve-entry-loops-unexported` gains
a counted loop when its u16le reading is used instead of the half-read); its
L2 status is unchanged.

### 5.3 Rust parity

`cargo run --bin fidelity-cli -- export <part> <ply>` on the six target parts
returns the Python counts exactly:

| part | Python tri / vert | Rust tri / vert |
| :--- | :--- | :--- |
| Audi R8 | 174303 / 114314 | 174303 / 114314 |
| MB-chair-A | 1300 / 410 | 1300 / 410 |
| MB-chair-B2 | 1307 / 410 | 1307 / 410 |
| MB-hatch-tapa-MDC | 1014 / 1148 | 1014 / 1148 |
| MD-Running gear-B2 | 4601 / 2555 | 4601 / 2555 |
| MD-Running gear-B4 | 4198 / 2562 | 4198 / 2562 |

### 5.4 Tests

- `pytest -q` — 879 passed / 20 skipped before, **884 passed / 20 skipped**
  after (five new tests: the oob-first rank, the all-OOB decline, the u16le
  primitive, the u8 fallback, the false-header half-read).
- `cargo test --locked` — 198 before, **203 after** (the same five cases as
  Rust unit tests).
- `scripts/check.sh` — the local merge gate (pinned ruff, pytest, claims CSV,
  cargo build/fmt/clippy/test, wasm-pack build+test, pkg sync, node) passes.

## 6. Reproduction

```bash
# the crash targets (in-process, the shipped export seam + L2 gate)
.venv/bin/python - <<'PY'
from pathlib import Path
from catpart.geometry.export import build_export
from catpart.fitness.runner import _score_export
p = Path("/home/alan/.local/state/catpart-parser/bench-external/datasets/audi/"
         "AUDINSKLOPIC_AllCATPart.CATPart")
s = build_export(p, Path("/tmp/audi.ply"))
print(s["triangle_count"], s["vertex_count"], s["degenerate_triangle_count"],
      _score_export(s)["status"])
PY

# corpus A/B (1,442 parts, ~7 min per side)
.venv/bin/python /tmp/corpus_ab.py <checkout> /tmp/ab.json

# Rust parity
cd port && cargo run --quiet --bin fidelity-cli -- export <part> /tmp/rust.ply

# the twin unit tests
.venv/bin/python -m pytest -q tests/test_composite_export.py -k "short_vote or relaxed"
cd port && cargo test --locked short_vote relaxed
```
