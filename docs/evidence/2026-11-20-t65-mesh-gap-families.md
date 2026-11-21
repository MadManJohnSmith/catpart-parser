# T65: the last MESH gap families (2026-11-20, Python + Rust)

Ticket #65 (part of #50). Probe: `scripts/triage/probe_top10_mesh_gap_dump.py`
(read-only; run outputs in `~/.local/state/catpart-parser/`).

## The three families behind the composite-mesh gaps

The probe re-derives the top-10 MESH residue: every composite store's
`STRIP_RE`/extended/escaped candidate headers that no committed law
accepts, framed as gap clusters between accepted record spans.

### 1-A — the short-form cap (`MAX_LOOP_COUNTS 0..16`)

The Trappe_Parachute gap records (2 per file; 1,057–5,360 B clusters)
are `01 42 <ty> ff` + `u32le n` + a count table of exactly `ty` u8
entries summing to `n` (`01 42 22 ff | 4f 02 00 00 | 0f 0d 05 11 …` —
34 counts sum 591). Every one parses at `(w2, k=ty)` in-bounds; 5 of 8
exact-tile; the other 3 carry trailing non-candidate bytes (a second,
unframed record family — left open here).

Corpus census (`--census-42`): **565 unresolved 0x42 candidates on 77
parts parse ONLY at k > 16; 379 of them exact-tiling + in-bounds**
(min-k distribution: mode 29 ×127, 17 ×90, 18 ×82, 19 ×76, 20 ×71 …
max 50). The cap was their only blocker.

### 1-B — `hlen == 6` with a P1g counts table

The povdoigt `_NPart#194287` / `SP02_ALPHA5_SEPA2_MINI_RESSORTS` gap
(the 282 KB copies; 46,835 B) = exactly 2 `0x47` records
(`01 47 9f cf 04 ff | 20 27 00 00 | 05 ff 00 02 00 00 ff 01 02 …`):
plain u8 header (`ty=159 b3=207 b4=4`, zero header escapes), `n=10016`,
but **the counts table escapes via read_counts** (16 of 211, 22 of 220
counts are `ff + u32le` — `ff 00 02 00 00` = 512). The #62 raw-u8
counts law breaks n-law (+6,951 / +9,755); the #64 escaped pass skips
`hlen == 6` candidates — the record fell between the two passes. Under
P1g: n-law exact (gap 0), w2 **exact-tiling** to 233251/259769,
in-bounds, repeats are legitimate strip joins (the #64 rank semantic).

Boundary detail: MINI_RESSORTS carries two `01 4f .. ff` STRIP_RE
matches INSIDE the second 0x47's ref block (236028, 237038; junk under
every law) — the exact-tiling vote must skip internal unresolved
candidates and never swallow an accepted record.

### 1-C — a u16be counts table

The CAAEwrFilter `BundleSegment3` gap (3,729 B) = 2 `0x47` records with
a plain u8 header and a **u16be counts table** (`01 47 12 11 01 ff |
ff 02 00 00 | 00 3c 00 3a …` — 18 counts of 2 bytes; u16be 60, 58, 60,
5, 41, 7, 9, 51, 9, 59, 59, 45, 14, 57, 57, 57, 57, 8 summing to 713 =
767 − 3·18). Both exact-tile at w2 in-bounds. The `0x43` record (573 B)
stays open: `hlen=6` outside `(0x47, 0x4f)`, `n@+6` junk under every
standard reading, 14 clean f32le words from +7 (part-scale XYZ triples)
then non-clean — a family with explicit points, not pinned here.

### The zero gate (the measured regression)

Raising the cap alone regressed `CAAGsiStartVolume` (L2 pass →
not-manifold): its k=16 **u16be** count table misreads as 32 u8 counts
(`[0, 72, 0, 72, …]` — a zero at every other entry) that sum to n and
exact-tile, and the per-rep route emitted the misread's loops (6
over-using edges kept by the seam's >1% area rule). Every corpus record
the extension admits carries a **zero-free** table (all 124 measured:
Trappe ×8, 13bb5c0c ×120, 545707b9 ×2); a strip writer never emits an
empty loop. The k extension past the #34-era base (16) is therefore
zero-gated; `k ≤ 16` keeps the shipped behavior byte-exact (the corpus
does carry zero counts on accepted k≤16 records — 358 on 13bb5c0c
alone).

## The law (both twins)

- `MAX_LOOP_COUNTS` 16 → 64, the extension zero-gated
  (`k > 16` requires a zero-free count table).
- The extended law's counts-table reading chain: **u8 → P1g → u16be**,
  each fallback tried only when the previous reading fails the counts
  law (byte-identical for every store the #62 law handled); fallback
  variants rank repeats instead of disqualifying them (the #64
  semantic); the winner passes the same in-bounds gate and the
  emission keeps the per-record `_mesh_safe` guard.
- The exact-tiling exception: a width whose end runs past the next
  candidate header is viable only when the record ends exactly on a
  later candidate header (`_nxt_eff`) and swallows no already-accepted
  record (`shipped_spans` + the law's own accepts; the committed u8
  path's semantics are provably unchanged — with `end ≤ nxt` the
  effective boundary degenerates to `nxt`).

## Measured outcome

- The 4 named files export manifold with the new records: Trappe ALPHA
  1,050 tris (2× 0x42 k=34), _NPart/MINI 21,661 tris each (2× 0x47 P1g),
  BundleSegment3 1,402 tris (2× 0x47 u16be). Python ≡ Rust PLY
  byte-identical on all four.
- Six pinned corpus stores gain records (13bb5c0c +8,660 from 120
  k=17/18 0x42 records, 4abf3eea +42, c9fdd852 +359, d31ea2c1 +59,
  545707b9 +712 from 2 k=25 0x42 records, b912cbef +1,589, 4902c650
  +7,866 from 2 extended records) — all still manifold, all in-bounds.
- Fitness: see the history row appended with this ticket.
