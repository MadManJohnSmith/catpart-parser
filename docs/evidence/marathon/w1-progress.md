# W1 marathon progress (composite/facets/vote/mesh/pool) — round v3

Branch `marathon/w1-composite`, base d8554e0. Worker W1.
Bench state dir (not committed): `~/.local/state/catpart-parser/marathon-w1/`.

## Baseline (measured before any code change)

Command (streaming, 1 process, PLY discarded):

    python -B baseline_probe.py <snapshot> <worktree> --out-dir out-baseline --commit d8554e0

CSV `out-baseline/m1_files.csv`, JSON `out-baseline/m1_summary.json`
(bench state dir; the committed evidence CSVs land under
`docs/evidence/data/` per unit below).

- total 757 parts; L2 pass **446 (58.92%)**
- failed checks: **not-manifold 277**, empty-mesh 13, degenerate-triangles 19
- total triangles 1,822,962
- warning classes on the 277: primary-loop-manifold-kept 277,
  primary-loop-manifold-declined 263, open-shell 250,
  duplicate-triangles-dedup-declined 245, extended-header-geometry-declined 227

Per-file breakdown of the 277: `MB-Frames-middle-centr-YL/YR` (2 parts),
`acc-Cont-Lft` (1 part) — the brief's "71%" figure is NOT the per-part
share (3/277 = 1.1%); it must refer to a different denominator (edges or
duplicated triangles), recorded here as an ambiguity to resolve against
the Orquestador's census.

## Hypothesis 1 — the 1,004 bytes post-payload[1860] (acc-Cont-Lft)

Byte evidence (probe scripts in bench state dir `probe/`, payloads saved
as `probe/accl_payload.bin`, `probe/mbyl_payload.bin`):

- Store span [0x405f0, 0x5eb8c); list node payload 2,864 B at file
  0x4068b; `layout(payload, 220)` = table 55 B, write_count 440, region
  [100, 1860). Element space: 110 slots shape-0 (full f32 triple) +
  110 slots shape-2 (z-only) = 220 elements = 110 (x,y) positions x 2
  z-levels (z = 1517.8618 / 1541.9352, planar band).
- Tail = payload[1860:] = **1,004 bytes**, structure:

  1. `ff b8 01 00 00` — P1g-escaped count **440** (= the first region's
     write_count).
  2. 880 B = 440 u16le values = 220 u32 words where every word carries
     ONE i16 (the other half 0) and the words come in 110 identical
     pairs. The 110 distinct i16 values form an **antisymmetric
     sequence**: `vals[109-k] == -vals[k]` exactly (range ±12..±23,161),
     i.e. a there-and-back delta stream whose total sum is 0.
  3. 104 B of `11/22/33` bytes (2-bit-ish filler pattern), then
     `00 00 00 | cd cc 4c 3e` (f32le 0.2) + `00 04 02 0a 06`. The same
     9-byte pattern `cd cc 4c 3e 00 04 02 0a 06` also appears at file
     0x52557, immediately before the facet record at 0x5255e.

- Cross-check MB-Frames-middle-centr-YL: elem_decl=682, write_count
  1026 (342 full triples + 340 skips), tail 3,475 B starting with the
  SAME `ff`-escaped count **1320**, then the same duplicated-i16 u16
  stream (values in the HIGH half here: (0, v) pairs; sign blocks
  --++), ending in small ascending u16 values (55, 57, ..., 166) —
  index-like. So the tail family exists across the Submarino
  (`tail_count` census: `out-census/census.jsonl`).

- NO committed law decodes the tail: table/raw/flat/mixedwrite all
  decline it (the store itself exports through identity-table-walk).

- The record at file **0x5255e** (`01 42 11 ff`, n=97, ty=17 counts
  [5,5,5,5,9,5,5,9,5,5,5,5,5,5,5,5,9]): its u16be ref block ends at
  0x52639 == the NEXT header (an extended 0x47 record) — **exact
  tiling**, so the width vote already prefers u16be; the refs reach
  **255 > elem_decl-1 = 219** (10 refs: 223, 227, 227, 232, 237, 237,
  244, 251, 253, 255), so the #66 post-vote refs gate declines the whole
  record and its triangles are lost. The u8 reading of the same block
  is 0-heavy garbage (alternating 0/value — the brief's "96 u8 salen
  permutados"; n=97 here).

- 36 elements (220..255) are needed; the tail carries 110 i16 values =
  36 triples + 2 leftover under the triple split, but the antisymmetry
  reversal point (index 54/55) is NOT 3-aligned, so the triple reading
  is inconsistent. No fixed-point scale maps the 110 values onto the
  first region's x/y/z or their deltas (searched 1/8..1/512 plus ratio
  medians; max err never below ~180 at any scale; pair sums ±19..24
  recur without a law).

**Status: OPEN after 2 documented attempts (numeric scale search,
triple/delta integration). Reopening criterion: a second store whose
tail decodes under one candidate reading against an independent ground
truth (e.g. a pool-absorbing store), or the Orquestador's census
naming the writer's law.** The structural facts above (escaped count =
region word count, duplicated i16 stream, antisymmetry, the 0.2f
separator) are the pinned observations any law must reproduce.

## Hypothesis 2 — anti-half-read u8-over-u16be (implemented, unit 1)

Mechanism verified on acc-Cont-Lft 0x5255e (above). Census over all 757
parts (`out-census/census.jsonl`; claims rows in
`docs/evidence/data/marathon-w1-half-read-claims.csv`):

- **385 of 757 parts** carry the tail structure (ff-escaped count after
  the declared region).
- 95,150 records whose u16be parse tiles exactly and is in-bounds
  (367 files — already resolved correctly by the width vote).
- **12,542 records whose u16be parse tiles exactly but is OOB**
  (118 files) — declined by the #66 gate, surface lost.
- **1,299 half-read records** (49 files: 1,192 on 0x42, 74 on 0x4a,
  30 on 0x4c, 3 on 0x44) — the u8 0-heavy reading.
- Cross with the L2 results: **86 of the 277 not-manifold parts** carry
  OOB u16be events; 41 of them carry the half-read signature; 0 parts
  carry ONLY the half-read signature (both classes co-occur).

The two corruption modes share one root cause (the truncated element
space) and differ in what the current decode does with the bytes:

1. exact-tile u16be → the record is declined (surface lost);
2. gap-edge u16be (or a false internal header truncating the span, so
   the u16be candidate is not even offered) → the u8 reading WINS the
   OOB tiebreak → **the permuted 0/value garbage exports as false
   surface**.

### The unit-1 change (fail-closed, no guessing)

`composite.parse_strip_records` gains the anti-half-read decline on
BOTH sides (Python `src/catpart/geometry/composite.py`, port
`port/src/geometry/composite.rs`): a width-1 winner with n >= 8 whose
ref block has **every even byte 0x00** (the u16be high-half signature)
and whose u16be re-reading leaves the element space (>= 1 ref >=
element_count) is a u16 stream the declared space cannot resolve — the
record is declined instead of exporting the u8 garbage. Bounds-guarded
(`end + n <= hi`); the in-bounds re-read case is NOT declined
(negative control in the tests).

Byte-verified effect on the trigger file: acc-Cont-Lft flips
not-manifold → **pass** (triangles 1,405 → 563, degenerates 35 → 0;
the garbage strip loops were the over-use source).

Tests: `tests/test_composite_export.py::test_composite_u8_winner_over_a_truncated_u16be_stream_is_declined`
(byte-for-byte 0x5255e block) + the in-bounds negative control; port
twins `u8_winner_over_a_truncated_u16be_stream_is_declined` /
`u8_record_with_in_bounds_u16be_reread_still_exports`. Parity:
`fidelity-cli` release build vs the Python seam on 5 affected Submarino
parts — PLY bytes identical (acc-Cont-Lft, BW-Motor-W, MB-mesada-82,
MD-Battery-charging-A1, VM-Periscope_17). clippy --all-targets: no new
warnings (13 pre-existing at the base); cargo fmt clean.

Submarino before/after: measured in the run below (out-h2 vs
out-baseline).

## Hypothesis 1 — the tail law: negatives recorded, reopening criteria

Two documented attempts (the numeric scale search; the triple/delta
integration + pair readings A/B): no fixed-point scale (1/8..1/512)
maps the 110 antisymmetric values onto the first region's coordinates
or their deltas; the (dx,dy)/(dy,dx) pair readings produce degenerate
line-collapsed bands; the (v,0,v) triple reading drifts z outside the
band. The structural facts any law must reproduce: tail_count ==
the region's word count (440 == write_count; 1320 vs 1026 on MB-YL —
NOT equal there, an unresolved constraint), the duplicated-i16 stream
(each value twice at 4-u16 stride, zeros between), exact antisymmetry
(vals[109-k] == -vals[k], total sum 0), the 104B `11/22/33` block,
and the `f32 0.2 + 00 04 02 0a 06` separator (present at both the
payload tail and file 0x52557).

Reopening criterion: an independent ground truth (a pool-absorbing
store whose tail decodes against its pool, or the Orquestador's census
naming the writer's law). The extension implied by the census (refs to
655 over elem_decl 220 with tail_count 440: 220 + 440 = 660) is the
quantitative target the law must hit.
