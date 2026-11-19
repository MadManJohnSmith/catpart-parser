# Evidence: the CGM record grid at the framing bar (decisive probe, Ticket #57 follow-up)

**Date**: 2026-11-18
**Status**: COMPLETE (decisive negative at **both** bounds: with BR5's id-range guard the grammar frames 18.57% of the 128 no-facet regions' body bytes and **0/128 tile exactly**; even unguarded the upper bound is 32.10% with three single-record regions, each of which is the guard's own swallow, and no numeric array exists anywhere in the region)
**Target**: the open question left by BR5 (`docs/evidence/2026-11-17-br5-cgm-nurbs.md`): whether the `CGMGeom` region's non-dictionary bytes are a record grid that can be framed exactly.
**Method**: byte-level probe over the no-pool population, `scripts/triage/probe_cgm_record_grid.py`; corpus-free test `tests/test_cgm_record_grid.py`; claims `docs/evidence/data/cgm-grid-claims.csv` (`CG-01`..`CG-16`). Read-only over the corpus; `src/` and the exporter are untouched.

---

## 1. Executive summary

Three measurements, one verdict. The grammar is reported at **both bounds** because the difference between them is itself the finding: with BR5's id-range value law on the id list (the shipped law) and without it (the widest reach the two families can have).

| Measurement | Anchor `80aad8d8` | 128 guarded (**shipped law**) | 128 unguarded (**upper bound**) | 131 guarded | 3 facet carriers (control) |
| :--- | ---: | ---: | ---: | ---: | ---: |
| CGM region | 327,334 B | 1,205,008 B | 1,205,008 B | 1,216,278 B | 11,270 B |
| Preamble | 290 B | 23,676 B | 23,898 B | 23,960 B | 284 B |
| Framed | 130,535 B | **219,321 B** | 379,113 B | 220,178 B | 857 B |
| Residue | 196,509 B | 962,011 B | 801,997 B | 972,140 B | 10,129 B |
| Coverage | **0.3991** | **0.1857** | 0.3210 | 0.1847 | 0.0780 |
| Exact tiling (residue 0) | **no** | **0/128** | 3/128 (all degenerate) | 0/131 | 0/3 |
| Regions with no runnable grid | n/a | **113/128** | 86/128 | 115/131 | 2/3 |
| f64 triples (raw / guarded) | 0 / 0 | 1 / 0 | 1 / 0 | 1 / 0 | 0 / 0 |
| f32 triples (raw / guarded) | 768 / 11 | 2,174 / 215 | 2,174 / 215 | 2,215 / 220 | 41 / 5 |
| Knot runs / weight runs | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |

The population is stage-13's own split (CG-08, CG-08b, CG-08c): the **128** are the no-pool stores with **no facet geometry** (`strip_records` empty or 0); the three facet carriers are a control. The identity is arithmetically confirmed: the carriers' CGM regions are 3,636 + 2,585 + 5,049 = 11,270 B and 1,216,278 − 11,270 = **1,205,008 B**, the brief's 128-region total. The 131-row aggregate is the union of the two.

The two bounds differ by exactly the guard's footprint (`CG-16`): **31 of 128 files are reframed**, **159,792 B** of "framed" bytes disappear when the id-range law is applied (159,149 B of swallowed records + 643 B of preamble shift), the longest single swallow is **13,325 B** from a 2-byte u16 count, and 18 u16 + 13 u32 records are refused. It moves **27 files from "has a grid" to "no runnable grid"** (86 → 113) — files that only "had a grid" because a count field read off payload bytes was believed. No file gains a grid from the guard: it only removes them.

**Verdict: STOP.** The grammar does **not** reach the bar (`>= 0.99` coverage with **0** residue) at either bound. Guarded, the anchor frames 39.91%, the 128 frame 18.57%, **no region tiles exactly**, and 113 of 128 regions contain no runnable grid at all — the 0.25/0.5/0.75 coverage quartiles are 0.0000 / 0.0000 / 0.0000, so the median *and* upper-quartile region frames nothing. Unguarded, the three "exact" regions are each a single 1,037-1,039 B "record" whose 256-id list carries 72-75 ids at or above 2**28: that is the swallow the guard exists to refuse, not a tiling.

Independently, the numeric scan is empty across the **whole** region (framed bodies *and* residue): zero f64 triples, zero knot runs, zero weight runs on all 128 (CG-10, CG-11). The f32 residual is accounted for by value (§5) and is a file-header constant and fixed-point ladders, not coordinates.

So the CGM region cannot yield the exact solids: what frames is dictionary/metadata, what does not frame is a further record stream whose length law is not in the bytes we model, and no coordinate/knot/weight array exists in either part.

---

## 2. The two-family grammar

The probe requires a region to tile from the end of the identity preamble to the region end with **zero residue**. The grammar is tried in a fixed order: id-run u32 → companion → id-run u16 (the u16 read last so a shifted re-read cannot swallow a companion — the BR5 width-gate hazard).

**Family `idrun`** (the shipped object dictionary record, unchanged):
`[k 00 04 00][u32 x][u8 flag][u32|u16 count][count x u32 ids][00 00]`

**Family `companion`** (the 31-byte companion and its length law):

```
+0x00  u32   marker = 0x00040001
+0x04  u32   x
+0x08  u8    flag                 (0, 1, 2 observed)
+0x09  u8    00
+0x0a  u32   words[flag+1]       (flag+1 opaque u32 words)
+...   u16   count = 2           (fixed by the length law)
+...   2 u32 ids                 (the second is the type word)
+...   u8    00                   (closing byte)
+...   6 B   opaque trailer       (not interpreted)
```

Total length = `31 + 4*flag` (31 / 35 / 39 B for flag 0 / 1 / 2; 43 / 47 for flag 3 / 4, unobserved and therefore not claimed). The last id is the record's **type word** — the task's `0x38`/`0x40` family, observed as the full ladder `0x28 0x2c 0x30 0x34 0x38 0x3c 0x40 0x44` in the anchor (CG-04).

**The id-list validation.** An id-run's ids are object ids, and BR5 establishes the shipped value law: no id at or above `2**28` (largest observed 106,878). The probe applies that law to the id list of *both* count widths. It is not cosmetic: a count read off a shifted byte boundary otherwise consumes payload bytes as ids and stops on a chance `00 00`, which is how a 2-byte field becomes a 13 KB "record" (§4, CG-16). The anchor's tiling is bit-identical with and without the guard (its largest id is 94,801), so the two bounds only diverge on the stores where the hazard fires.

**Field table, anchor head** (`files/` offset, block-relative; CG-03):

| family | offset | length | marker | x | flag | count | ids | type |
| :--- | ---: | ---: | :--- | ---: | ---: | ---: | :--- | ---: |
| idrun32 | 290 | 35 | 0x02 | 0x9 | 0x00 | 5 | 3 4 5 6 7 | 0x7 |
| companion | 325 | 31 | 0x01 | 0x3 | 0x00 | 2 | 8 56 | 0x38 |
| idrun32 | 356 | 35 | 0x02 | 0xb | 0x00 | 5 | 9 10 11 12 13 | 0xd |
| companion | 391 | 31 | 0x01 | 0x29 | 0x00 | 2 | 14 56 | 0x38 |
| idrun32 | 422 | 35 | 0x02 | 0xd | 0x00 | 5 | 15 16 17 18 19 | 0x13 |
| companion | 457 | 31 | 0x01 | 0x4f | 0x00 | 2 | 20 64 | 0x40 |
| idrun32 | 488 | 43 | 0x02 | 0x4b | 0x00 | 7 | 22 23 24 25 26 27 28 | 0x1c |
| companion | 531 | 31 | 0x01 | 0x73 | 0x00 | 2 | 29 64 | 0x40 |

This reproduces the brief's head deltas exactly: 35 B id-run + 31 B companion = 66 B marker-to-marker; 43 B id-run + 31 = 74; 47 B id-run + 31 = 78. The 31 B slab is the companion; 43/47 are *id-run* records of 7/8 ids, not companions. (Correcting the brief's shorthand: the companion family observed is 31/35/39 B, not 31/43/47.)

---

## 3. Anchor `80aad8d8`

`510.000_NOTE A.CATPart` (R21, 4,196,403 B), block `CGMGeom` at 3,707,055, region end 4,034,389, size 327,334 B (CG-01). Identity: `FINJPL  ` at +106, `Cont_50f58d0d_1ae0_63f47193_33d27`.

- Raw marker census: `01 00 04 00` 7,293; `02 00 04 00` 127 (CG-02) — the brief's counts, reproduced.
- Grid: preamble 290 B, **4,425 records** (2,213 `idrun32` + 2,212 `companion`), framed 130,535 B, residue 196,509 B, coverage **0.3991**, exact **no** (CG-03). Identical with and without the id-range guard: the anchor contains no shifted count read that the guard removes.
- Companion flags: 0 = 2,050, 1 = 81, 2 = 81 (CG-04) → the length law's whole observed range.
- First refusal: region offset **130,825** (abs 3,837,880), residue head `01 00 04 00 77 db 05 00 ...` (CG-05). This is a 42-byte record of a shape the grammar does not describe; see §6.

The anchor's 40% is the best case among the large regions (§4 shows the two regions slightly above it): it is the largest region and its head is a clean 1:1 id-run/companion alternation.

---

## 4. Population

Population = the `no-pool` family of `docs/evidence/data/stage13-elementspace-census.csv`, split by `strip_records` exactly as stage 13 splits it (`docs/evidence/2026-11-13-stage13-elementspace.md` §3): **3 facet carriers** (`66049cf3`, `bf350820`, `fac22ea3`) and **128 stores with no facet records**. The brief's "128 no-pool parts" is the no-facet set (CG-08); the 131-row aggregate is reported alongside for continuity with stage 13 (CG-08b).

**Guarded — the shipped law, the measurement:**

- **128**: 1,205,008 B; preamble 23,676 B; framed 219,321 B; residue 962,011 B; coverage **0.1857**.
- Per-file outcome: **exact 0, partial 15, no grid 113** (CG-09); coverage quartiles 0.0000 / 0.0000 / 0.0000 — the median region frames nothing, and so does the upper quartile.
- **131**: 1,216,278 B; preamble 23,960; framed 220,178; residue 972,140; coverage 0.1847; exact 0, partial 16, no grid 115 (CG-08b).
- **3 carriers** (control): 11,270 B; preamble 284; framed 857; residue 10,129; coverage 0.0780; exact 0, partial 1, no grid 2 (CG-08c). Carrying facet records does not make the CGM region frame.
- The best three regions are `550e4e26` 0.4173 (821 records), `d7ed0772` 0.4037 (991), and the anchor 0.3991 (4,425). **No region reaches 0.99.**

**Unguarded — the upper bound, and what it costs (`CG-08d`, `CG-08e`, `CG-16`):**

- **128**: preamble 23,898 B; framed 379,113 B; residue 801,997 B; coverage 0.3210; exact **3**, partial 39, no grid 86.
- The three "exact" rows are the guard's own counterexample, not a tiling: `54b043d4` (1,543 B, preamble 504, **one** 1,039-B u32 record, count 256, **72** of its ids ≥ 2**28, largest 2,680,038,912), `f3862d22` (identical shape, 72 over-range ids) and `d665cd12` (11,153 B, preamble 10,116, **one** 1,037-B u16 record, count 256, **75** over-range ids). In each case a whole region "tiles exactly" because a count field read off payload bytes swallows the body and lands on a chance `00 00`.
- The guard's footprint: **31 files reframed**, framed delta **159,792 B** (159,149 B of swallowed records + 643 B of preamble shift), longest swallow **13,325 B** (`eaccbb56`, a u16 count of 3,328 read out of payload), refused records **18 u16 + 13 u32**. It moves 27 files from "has a grid" to "no runnable grid" (86 → 113).
- Two more regions sit just under the bar: `eb8df968` 0.9954 and `82de0119` 0.9928, each a legitimate 33-B record followed by the same 7,183-B swallow; with the guard they frame 0.

The guarded aggregates add up exactly: `CG-08` + `CG-08c` = `CG-08b` on bytes (1,205,008 + 11,270 = 1,216,278), preamble (23,676 + 284 = 23,960) and framed (219,321 + 857 = 220,178).

The 113 no-grid regions refuse at offset 0 with the identity preamble's own head `34 12 34 41` (`34 12` + `4A`): no record of either family starts a runnable grid anywhere in the region — either nothing parses, or the only parse is a single record that is not followed by another and does not reach the region end. Fourteen more (of the 131) refuse at a `k 00 04 00` marker that is neither family; the rest at assorted bytes.

---

## 5. Numeric scan

Scan design: every framed record body and the whole region are scanned for (a) f64 and f32 coordinate triples, (b) knot vectors, (c) weight runs.

- **Triples**: finite, `1e-3 <= |v| <= 1e6`, at every byte phase. The raw count is reported alongside the count after four alias guards that are *properties of the bytes*, not of the expected answer: an all-printable-ASCII 12-byte window (text), a constant triple, a geometric power-of-two chain (integer arrays read as f32/f64), and an arithmetic ramp whose step is exactly `2**-k` (fixed-point index arrays). Framed bodies are scanned record by record, so a "triple" may not straddle two records.
- **Knots and weights**: the shipped `cgm_nurbs.nurbs_signatures` detector (BR5's guards), not a second implementation.

Results (`CG-06`, `CG-07`, `CG-10`, `CG-11`):

| Scope | f64 raw | f64 guarded | f32 raw | f32 guarded | knots | weights |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| anchor region | 0 | 0 | 768 | 11 | 0 | 0 |
| anchor framed bodies | 0 | 0 | 744 | 9 | 0 | 0 |
| 128 region | 1 | 0 | 2,174 | 215 | 0 | 0 |
| 128 framed bodies (guarded) | 0 | 0 | 1,026 | 9 | 0 | 0 |
| 131 region | 1 | 0 | 2,215 | 220 | 0 | 0 |

The guards remove the corpus's aliases and the residuals are accounted for **by value**, not waved away (`CG-14`, `CG-14b`, `CG-15`):

- **f64: zero guarded.** The single raw in-range 131 hit is removed by the power-of-two chain guard.
- **f32 region (128) = 215 hits, 78 distinct.** 121 of the 215 are the *same* triple in 121/128 files — `(12.1953125, 49.57551574707031, 0.004861869849264622)`, a file-header constant, not geometry (131: 124/124, 80 distinct, CG-14b). The remaining 94 hits are isolated misalignments.
- **f32 framed (128) = 9 hits, 8 distinct — all nine in the anchor** (CG-15). All nine are the `2**-16` fixed-point ladder: six are forward/reverse reads of the three values `0.00233… / 0.00253… / 0.00273…` stepping by `2**-16`, and three are the `0.0078…` triple whose step is `2*2**-16` — the same alias the region scan shows, in the band where the centred step breaks the ramp guard's monotonicity. None is a coordinate triple. (The earlier "header constant inside framed bodies" reading was itself an artefact of unguarded framing; under the guard no framed body carries it.)
- **One file (`8497f19a`) carries an ASCII/text span inside the CGM block** (`37 2c 30 24 31 30 37` = `7,0$107`), which is what most of its f32 hits decode to. Recorded as a content observation, not geometry.

There is no coordinate array, no knot vector and no rational-weight run in the CGM region of the no-pool parts — in the framed bodies or in the residue.

---

## 6. Why the grammar stops (the counterexamples)

The refusal is structural, not a stray byte. Two shapes outside the two families:

1. **Anchor `80aad8d8`, region offset 130,825 (42 B)** — a container-shaped record:
   `01 00 04 00 | 77 db 05 00 | 00 | 00 00 00 00 | 00 | 51 13 00 00 | 03 00 | 03 00 00 00 | 17 00 00 00 | 02 00 00 00 | 00 00 | 00 00 00 00 00 00 00 00`
   It carries a u16 count = 3 and a u32 word `0x1351` before it; no field of the companion law produces this length.
2. **`07d3c70b`, region offset 319 (25 B)** — a companion-shaped record whose prefix is two u32 words and a type, with **no id list**:
   `01 00 04 00 | 03 00 00 00 | 02 | 00 | 07 00 00 00 | 30 00 00 00 | 00 | 18 05 51 3e 78 aa`
   The `31 + 4*flag` law cannot produce 25 B, and the same file contains both this form and the 31-B form.

**The residue is a record stream, not noise** (CG-13). Inside the anchor's 196,509-B residue there are 5,249 `k 00 04 00` markers, and their spacing is regular: 37 B × 1,201, 45 B × 1,187, 38 B × 927, 33 B × 890, 41 B × 384, 11 B × 145, 34 B × 133, 24 B × 126. Consecutive boundaries at 42 / 80 / 118 / 156 / 194 / 227 / 265 / 303 B show a repeating 38-B unit (a 23-B `[01 00 04 00][u32 x][u8 00][u16 count=3][3 u32 ids]` core plus a 10- or 15-B tail) with 33-B and 42-B variants. What the bytes do **not** contain is a field that selects the tail length: the same `count=3` core ends after 10 zero bytes on one record and after 15 structured bytes on the next, and `flag`/`type` do not discriminate (the 25-B and 39-B companion forms share `flag=2`).

So the residue is exactly the "serialized object stream" the class header would describe, and framing it is class-fitting against the corpus: a parser can be made to tile it by trying tail lengths until the next record parses, but that is lookahead, not a framing law. That is the open-ended bulk RE the ticket set out to rule in or out. It is ruled out.

The guard's counterexamples are the same lesson from the other side: where a count field *does* describe a multi-kilobyte span, the span is payload (ids above `2**28`, lengths 13,325 B from a u16 count) and the terminator is chance, not a class header.

---

## 7. Verdict

**Exact tiling: no, at both bounds** — guarded 0.1857 at 128 with **0/128** exact and 113/128 regions framing nothing; even the unguarded upper bound is 0.3210, and its only three "exact" regions are single-record swallows of payload (72-75 over-range ids each). The bar was `>= 0.99` coverage with 0 residue. **Numeric array: no** — 0 f64 triples, 0 knot runs, 0 weight runs over the whole region, framed and residue. **→ The CGM region cannot yield the exact solids; STOP, open-ended bulk RE.**

The two measured facts reinforce each other: the 19-40% that frames is dictionary/metadata (identity, id-runs, typed companion words, a 6-byte opaque trailer), the 60-81% that does not frame is a further regular record stream with no in-record length discriminator, and neither part contains a numeric array. Even a complete framing of the residue would still leave the numeric scan empty, because the scan already covers the residue.

**Smallest next step, if the question is ever re-opened** (not taken here): treat the region as CATIA's serialized object stream and recover the *class header* law — the field that selects the 25-B vs 31/35/39-B companion shape and the 10-B vs 15-B tail of the 38-B unit — then re-run this probe with a three-family grammar and require zero residue at the guarded bound. Without that class discriminator the probe's residue cannot go to zero by fitting record lengths; anything that does is a lookahead heuristic, not a framing law — and the unguarded bound shows what that heuristic looks like when it is mistaken for reach.

---

## 8. Reproduction

```bash
export LD_LIBRARY_PATH=/usr/lib:${LD_LIBRARY_PATH:-}
.venv/bin/python -I scripts/triage/probe_cgm_record_grid.py --anchor 80aad8d8 --no-population
.venv/bin/python -I scripts/triage/probe_cgm_record_grid.py
.venv/bin/python -m pytest tests/test_cgm_record_grid.py -q
```

The probe writes `docs/evidence/data/cgm-grid-claims.csv` and exits 2 when the anchor does not tile exactly (a CI-friendly signal that the decisive negative still holds). The population is split from the census at run time (`strip_records` empty/0 vs not), not from a hardcoded SHA list, and is walked twice (guarded and unguarded, ~4 s total). Outputs are deterministic; `mmap` + read-only.

---

## 9. Detector honesty

- **What "framed" means.** A record is framed when its bytes fit a family's length law and its closing bytes validate. The companion's 6-byte trailer is **not** interpreted: the family is framed, not decoded. The type word is the last id, not a proven semantic type.
- **What "exact" means.** Preamble (bytes before the first runnable grid start) + contiguous records = region end. Zero residue is required; no lookahead, no gap tolerance, no per-file tuning. `grid_start` demands a record followed by another record (or region end), so a lone false marker cannot become a grid.
- **What the id-range guard is (and why both bounds are reported).** BR5's value law: every id in an id-run is below `2**28` (largest shipped id 106,878). It applies to both count widths. It is a value law, not a length law — it does not change how a record is framed, only whether a count field read off payload bytes is believed. It is measured (`CG-16`: 31 files, 159,792 B, longest 13,325 B) rather than asserted, and every aggregate is reported with it (`CG-08`) and without it (`CG-08d`). The guarded number is the measurement; the unguarded one is the upper bound, and it is an upper bound because its "exact" rows are the swallow.
- **What "no numeric array" counts.** The verdict's `numeric_arrays` is `f64 guarded triples + knot runs + weight runs`; the f32 residual is reported separately and accounted by value (§5) because every hit is a header constant or a fixed-point ladder. It does not prove the absence of geometry in another encoding (f16, fixed-point, compressed, or a transform matrix); it proves the absence of plain f64 coordinate triples, knot vectors and 1.0 weight runs.
- **The residue cadence is a diagnostic, not a parse.** §6 counts marker spacings to show the residue is a record stream. It does not claim the 38-B/33-B/42-B shapes are decoded, and no claim in this note depends on their interpretation.
- **The three unguarded "exact" regions are the guard's counterexample**, not a tiling, and are reported as such. No region tiles exactly at the guarded bound.
