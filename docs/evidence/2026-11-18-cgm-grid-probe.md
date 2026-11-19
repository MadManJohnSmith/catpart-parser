# Evidence: the CGM record grid is not frameable (decisive probe, Ticket #57 follow-up)

**Date**: 2026-11-18
**Status**: COMPLETE (decisive negative: the two-family grammar tiles 32% of the no-pool CGM region and no numeric array is present)
**Target**: the open question left by BR5 (`docs/evidence/2026-11-17-br5-cgm-nurbs.md`): whether the `CGMGeom` region's non-dictionary bytes are a record grid that can be framed exactly.
**Method**: byte-level probe over the no-pool population, `scripts/triage/probe_cgm_record_grid.py`; corpus-free unit test `tests/test_cgm_record_grid.py`; claims `docs/evidence/data/cgm-grid-claims.csv` (12 rows, `CG-01`..`CG-12`). Read-only over the corpus; `src/` and the exporter are untouched.

---

## 1. Executive summary

Two measurements, one verdict:

| Measurement | Anchor `80aad8d8` | No-pool population |
| :--- | :--- | :--- |
| CGM region | 327,334 B (`[3,707,055, 4,034,389)`) | 1,216,278 B over 131 regions |
| Two-family grammar coverage | 130,535 B = **0.3991** | 379,970 B = **0.3187** |
| Residue | 196,509 B = 0.6009 | 812,126 B = 0.6813 |
| Exact tiling (residue 0) | **no** | **3/131**, all degenerate single-record regions |
| Regions with no grid start | n/a | **88/131** |
| f64 triples (raw / guarded) | 0 / 0 | 1 / 0 |
| f32 triples (raw / guarded) | 768 / 11 | 2,215 / 220 |
| Knot runs / weight runs | 0 / 0 | 0 / 0 |

The brief's 128-file figure is the 131-row no-pool family minus three regions whose sizes sum to 11,270 B: `1,216,278 - 11,270 = 1,205,008 B`, exactly the brief's byte total (CG-08b). The 128-row aggregate is framed 376,784 / residue 804,488 / coverage 0.3190.

**Verdict: STOP.** The two-family grammar does **not** tile the region — not partially by accident, but structurally: 88 of 131 regions contain no runnable grid at all, and the first refusal in the anchor opens a different record shape. There is also no numeric array in what does frame. The CGM region cannot yield the exact solids, and closing the remaining 68% is open-ended record-class reverse engineering, not a framing law. §§6-7 name the two counterexamples and the smallest next step.

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

**Field table, anchor head** (`files/ offset`, block-relative; CG-03):

| family | offset | length | marker | x | flag | count | ids | type |
| :--- | ---: | ---: | :--- | ---: | ---: | ---: | :--- | :--- |
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
- Grid: preamble 290 B, **4,425 records** (2,213 `idrun32` + 2,212 `companion`), framed 130,535 B, residue 196,509 B, coverage **0.3991**, exact **no** (CG-03).
- Companion flags: 0 = 2,050, 1 = 81, 2 = 81 (CG-04) → the length law's whole observed range.
- First refusal: region offset **130,825** (abs 3,837,880), residue head `01 00 04 00 77 db 05 00 ...` (CG-05). This is a 42-byte record of a shape the grammar does not describe; see §6.

The anchor's 40% is the best case in the family: it is the largest region and the only one whose head is a clean 1:1 id-run/companion alternation.

---

## 4. Population

Population = the `no-pool` family of `docs/evidence/data/stage13-elementspace-census.csv` (`CG-08`):

- 131 regions, 1,216,278 B; preamble 24,182 B; framed 379,970 B; residue 812,126 B; coverage **0.3187**.
- Per-file outcome: **exact 3, partial 40, no grid 88** (`CG-09`); coverage quartiles 0.0000 / 0.0000 / 0.3642 — the median region frames nothing.
- The three "exact" rows are degenerate: `54b043d4` (1,543 B, preamble 504, one 1,039-B id-run), `d665cd12` (11,153 B, preamble 10,116, one 1,037-B id-run), `f3862d22` (1,543 B, same shape). Exact tiling occurs only where a single record swallows the body.
- The brief's 128 subset (`CG-08b`): 1,205,008 B, preamble 23,736, framed 376,784, residue 804,488, coverage 0.3190.

The 88 no-grid regions refuse at offset 0 with the identity preamble's own head `34 12 34 41` (`34 12` + `4A`): no record of either family starts a runnable grid anywhere in the region. Fourteen more refuse at a `k 00 04 00` marker that is neither family; the rest at assorted bytes.

---

## 5. Numeric scan

Scan design: every framed record body and the whole region are scanned for (a) f64 and f32 coordinate triples, (b) knot vectors, (c) weight runs.

- **Triples**: finite, `1e-3 <= |v| <= 1e6`, at every byte phase. The raw count is reported alongside the count after four alias guards that are *properties of the bytes*, not of the expected answer: an all-printable-ASCII 12-byte window (text), a constant triple, a geometric power-of-two chain (integer arrays read as f32/f64), and an arithmetic ramp whose step is exactly `2**-k` (fixed-point index arrays).
- **Knots and weights**: the shipped `cgm_nurbs.nurbs_signatures` detector (BR5's guards), not a second implementation.

Results (`CG-06`, `CG-07`, `CG-10`, `CG-11`):

| Scope | f64 raw | f64 guarded | f32 raw | f32 guarded | knots | weights |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| anchor region | 0 | 0 | 768 | 11 | 0 | 0 |
| anchor framed bodies | 0 | 0 | 744 | 9 | 0 | 0 |
| population region | 1 | 0 | 2,215 | 220 | 0 | 0 |
| population framed bodies | 0 | 0 | 1,379 | 15 | 0 | 0 |

The guards remove the corpus's aliases and the residuals are accounted for, not waved away:

- **f64: zero.** The single raw in-range population hit is removed by the power-of-two chain guard.
- **f32 residual (region) = 220, 80 distinct**: 124 are the *same* triple in 124/131 files — `(12.1953125, 49.57551574707031, 0.004861869849264622)`, a file-header constant, not geometry; the rest are isolated misalignments. The framed-only residual is 15 hits in the `(2.3e-3, 7.9e-3)` band (`0.007781982421875, 0.0078125, 0.00787353515625` and neighbours), the fixed-point alias the guards do not catch when the centred `2**-k` step breaks monotonicity.
- **One file (`8497f19a`) carries an ASCII/text span inside the CGM block** (`37 2c 30 24 31 30 37` = `7,0$107`), which is what most of its f32 hits decode to. Recorded as a content observation, not geometry.

There is no coordinate array, no knot vector and no rational-weight run in the CGM region of the no-pool parts.

---

## 6. Why the grammar stops (the counterexamples)

The refusal is structural, not a stray byte. Two shapes outside the two families:

1. **Anchor `80aad8d8`, region offset 130,825 (42 B)** — a container-shaped record:
   `01 00 04 00 | 77 db 05 00 | 00 | 00 00 00 00 | 00 | 51 13 00 00 | 03 00 | 03 00 00 00 | 17 00 00 00 | 02 00 00 00 | 00 00 | 00 00 00 00 00 00 00 00`
   It carries a u16 count = 3 and a u32 word `0x1351` before it; no field of the companion law produces this length.
2. **`07d3c70b`, region offset 319 (25 B)** — a companion-shaped record whose prefix is two u32 words and a type, with **no id list**:
   `01 00 04 00 | 03 00 00 00 | 02 | 00 | 07 00 00 00 | 30 00 00 00 | 00 | 18 05 51 3e 78 aa`
   The `31 + 4*flag` law cannot produce 25 B, and the same file contains both this form and the 31-B form.

So the companion family is at least two sub-shapes (with/without the id list), selected by a discriminator not present in `flag` (`0x02` appears in both the 25-B and 39-B forms). Extending the grammar to cover them is class-fitting against the corpus, which is exactly the open-ended bulk RE the ticket set out to rule in or out. It is ruled out.

---

## 7. Verdict

**Exact tiling: no. Numeric array: no. → The CGM region cannot yield exact solids; STOP.**

The two measured facts reinforce each other: the 32% that frames is dictionary/metadata (identity, id-runs, typed companion words, a 6-byte opaque trailer), and the 68% that does not frame is a heterogeneous object stream whose record classes are not described by a two-family law. Even a complete framing of the residue would still leave the numeric scan empty for the framed part.

**Smallest next step, if the question is ever re-opened** (not taken here): treat the region as CATIA's serialized object stream and recover the *class header* law (the field at `+0x09`/`+0x0a` that selects the 25-B vs 31/35/39-B shape), then re-run this probe with a three-family grammar and require zero residue. Without that class discriminator the probe's residue cannot go to zero by fitting record lengths; anything that does is a lookahead heuristic, not a framing law.

---

## 8. Reproduction

```bash
export LD_LIBRARY_PATH=/usr/lib:${LD_LIBRARY_PATH:-}
.venv/bin/python -I scripts/triage/probe_cgm_record_grid.py --anchor 80aad8d8 --no-population
.venv/bin/python -I scripts/triage/probe_cgm_record_grid.py
.venv/bin/python -m pytest tests/test_cgm_record_grid.py -q
```

The probe writes `docs/evidence/data/cgm-grid-claims.csv` and exits 2 when the anchor does not tile exactly (a CI-friendly signal that the decisive negative still holds). Outputs are deterministic; `mmap` + read-only.

---

## 9. Detector honesty

- **What "framed" means.** A record is framed when its bytes fit a family's length law and its closing bytes validate. The companion's 6-byte trailer is **not** interpreted: the family is framed, not decoded. The type word is the last id, not a proven semantic type.
- **What "exact" means.** Preamble (bytes before the first runnable grid start) + contiguous records = region end. Zero residue is required; no lookahead, no gap tolerance, no per-file tuning. `grid_start` demands a record followed by another record (or region end), so a lone false marker cannot become a grid.
- **What the id-run check does not do.** It does not apply BR5's `max_id < 2**28` value guard — that is a value sanity check, not a framing law, and applying it here would understate the grammar's reach. Count + terminator are the validation.
- **What the numeric scan does not do.** It does not prove the absence of geometry in another encoding (f16, fixed-point, compressed, or a transform matrix); it proves the absence of plain f32/f64 coordinate triples, knot vectors and 1.0 weight runs. The four alias guards are named in §5 so the residual can be re-derived.
- **The three "exact" regions are degenerate** and are reported as such; they do not support a tiling claim.
