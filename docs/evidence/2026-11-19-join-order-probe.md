# Evidence: the residual `a5 03 34` frames — join, order, and the subtype-4 patch head (2026-11-19)

**Date**: 2026-11-19
**Status**: COMPLETE. The five BLANK `no-evaluable-surface` rows are a **second record subtype**, not the two-lane grammar and not an allocation/order failure; its head pins on every frame, the five parts evaluate and tessellate, and the manifest open rate rises from **1,367/1,436 = 95.19%** to **1,372/1,436 = 95.54%** (+5 parts, +0.35 pp).
**Target**: the five report rows that carry `a5 03 34` marker frames but export nothing (`no-evaluable-surface`): `58ed8b28…` (PINZA_DERECHA), `6c6a2e9f…` (PINZA_IZQUIERDA), `8e8500b1…` (ENGRANAJE_SERVO), `b4fd22e3…` (CAASddCreateMember), `d523721f…` (MPU6050_Clone).
**Method**: byte-level probe `scripts/triage/probe_join_order.py`; shipped evaluator `src/catpart/geometry/surface.py`, Rust port `port/src/geometry/surface.rs`; corpus-free tests `tests/test_surface_tessellation.py` (22) and the port's `surface.rs` unit tests (6); claims `docs/evidence/data/join-order-claims.csv` (`JO-01`..`JO-08`) and the post-patch open-rate rows `docs/evidence/data/open-rate-after-patch.csv`. Read-only over the corpus.

---

## 1. Executive summary

The surface-head note named two candidate laws for the three frames that resist **inside** the `d7ed0772` anchor: an allocation↔frame **join** law and a pole **ordering** law. This probe tests both, exactly as asked, and both are refuted as explanations of the five BLANK parts. Those parts have **no content-prefix allocation at all**, and the stored order is already the winning order: row-major is evaluable on **1,391/1,391** frames, column-major on **50/1,391**, the per-span transpose on **18/1,391**.

What actually blocks them is the **head**: every one of their 1,396 marker frames is subtype `4`, not the two-lane subtype `0`. The subtype-4 record is a **patch** whose second lane stores its own degree; it decodes and pins on **1,396/1,396** frames (5 refused later for non-positive weights). The five parts then export 264,096 triangles over 157,199 vertices.

| Measurement | Five BLANK parts |
| :--- | ---: |
| `a5 03 34` marker frames | **1,396** |
| Heads decoded by the subtype-4 grammar | **1,396** (`1.0000`) |
| … with a finite pole net and sane weights | **1,391** |
| … evaluable (corner poles, folds, hull, scale, chord-length) | **1,391** (`1.0000`) |
| Surfaces tessellated | **1,391** |
| Triangles / vertices | **264,096 / 157,199** |
| Parts opened (MESH) | **5/5** |
| Join law inputs (prefix allocations) | **0/5** |
| Order law: row-major wins | **1,391/1,391** |

**Verdict.** The five BLANK rows are recovered by a **new head grammar**, not by a join or ordering law. The join probe is retained because it is the measurement that ruled those laws out, and because it reproduces `BS-09` on the control anchor (`80aad8d8`: the prefix is exactly one frame net).

| Open rate | Before | After | Delta |
| :--- | ---: | ---: | ---: |
| MESH | 1,158 (80.64%) | **1,163 (80.99%)** | +5 |
| DISPLAY | 209 (14.55%) | 209 (14.55%) | 0 |
| BLANK | 69 (4.81%) | **64 (4.46%)** | −5 |
| **Open (MESH+DISPLAY)** | **1,367 (95.19%)** | **1,372 (95.54%)** | **+5 / +0.35 pp** |

---

## 2. The join hypothesis — no input on the five

The hypothesis: the content-prefix allocation (`BS-03`) is the same pole run as a frame's grid, and a law maps allocation index to frame. The probe measures, per part, the allocation's byte length and offset and compares it with every decoded head's predicted grid by exact length and bit identity.

| Part | Prefix allocation | Relation to a frame grid |
| :--- | ---: | :--- |
| `58ed8b28…` | none (`prefix=None`) | — |
| `6c6a2e9f…` | none | — |
| `8e8500b1…` | none | — |
| `b4fd22e3…` | none | — |
| `d523721f…` | none | — |
| `d7ed0772…` (control) | 54,432 B at `block+840` | **no** frame's net is a bit-prefix; the run is merged (`BS-03`) |
| `80aad8d8…` (control) | 18,144 B at `block+840` | **bit-identical** to frame abs `3,563,129`'s grid, 1 copy (`BS-09` reproduced) |

`JO-02`/`JO-08`. The five BLANK parts have no allocation to join, so no join law can be the recovery. The control confirms the probe's join test is live rather than trivially negative: it finds the known one-copy identity on `80aad8d8` and the known merged run on `d7ed0772`.

The two `~993 m` control frames are still what the surface-head note said they are: frames `669,430` and `1,271,468` carry knot lanes **bit-identical** to in-scale nets (identical lane groups in `JO` census: `{669430, 634559, 1390529, 1635299}` and the 11×11 group), while their poles reach `993,043 mm` and their fold counts are `214` and `100` with arc ratios `9.4e-4`/`9.0e-4`. They remain refused; the join law that would split those runs is still open and is **not** needed for the five BLANK parts.

---

## 3. The order hypothesis — row-major already wins

The hypothesis: the in-scale frame whose `knot span / pole arc` is `63.7×` is stored in a different pole order. The probe scores the same flat triples under three layouts with the head note's own battery (corner residual, fold count, chord-length ratio, hull, scale):

| Population | row-major | column-major | per-span 3×3 transpose |
| :--- | ---: | ---: | ---: |
| five BLANK parts (1,391 scored) | **1,391** | 50 | 18 |
| `d7ed0772` control (17 frames) | **14** | 0 | 0 |

`JO-03`/`JO-06`. Row-major is not merely acceptable: it is the only layout that leaves every frame evaluable in the BLANK population. The `d7ed0772` control reproduces the note's `14/17` and shows the three refusals are not order failures — `669,430` and `1,271,468` have in-scale lanes with kilometre poles, and `1,416,850`'s lanes are **contaminated at the clamped ends**:

```
1,416,850 u lane: -1001210.714, -770.986, …, 4433.803, 993571.011, 1191570.026   (16 entries)
  634,559 u lane:    -3142.508, -770.986, …, 4433.803,   5053.375,    6397.346   (16 entries)
```

The interior values agree to rounding; the first and last two do not, which is exactly the `63.7×` span. No permutation of the poles repairs a wrong lane. That frame stays refused and is named, not filtered.

---

## 4. The subtype-4 patch head

Worked frame: `58ed8b28…` `PINZA_DERECHA`, marker abs **314,177**, payload abs **314,185**, payload length **782**. Every offset is payload-relative.

| payload+ | width | field | value |
| ---: | :--- | :--- | :--- |
| 0 | u32le | record tag | `5` |
| 4 | u32le | `n_u` | `2` |
| 8 | u8 | subtype | `4` |
| 9 | f64le×`n_u` | `knots_u` | `0.000000 … 4.542916` |
| 25 | u8 | lane tag | `1` |
| 26 | u32le | `degree_v` | `2` |
| 30 | u32le | `n_v` | `2` |
| 34 | u8 | subtype | `4` |
| 35 | f64le×`n_v` | `knots_v` | `3.857846 … 4.662770` |
| 51 | u8 | rational | `1` |
| 52 | 2 B | closing | `00 00` |
| **54** | f64le×18×3 | pole coordinates, `6×3` | 432 B |
| 486 | f64le×18 | weights (rational only) | `1.0` / `0.859444` |
| 630 | 152 B | tail | measured closure |

The head is `26 + 8·(n_u + n_v)` bytes for the patch grammar (54 here), versus the two-lane `30 + 8·(n_u + n_v)`. The differences that matter: the u lane has **no mode field**, the second lane stores the v **degree**, and the closing middle byte selects the rational layout. The tail is 152 on all 1,396 frames.

### 4.1 The pole law

The u direction is degree 5 with interior multiplicity 3 in every frame (as in the two-lane grammar), so `poles_u = 3·n_u`. The v direction is clamped at the stored degree with the same multiplicity, so:

```
poles_v = (degree_v + 1) + 3·(n_v − 2)
```

Both shapes observed across the five parts fit, with no residual:

| `n_u` | `degree_v` | `n_v` | poles | rational | frames |
| ---: | ---: | ---: | :--- | :--- | ---: |
| 2 | 2 | 2 | 6×3 = 18 | yes | 1,008 |
| 2 | 4 | 2 | 6×5 = 30 | yes | 18 |
| 2 | 1 | 2 | 6×2 = 12 | no | 18 |
| 2 | 3 | 2 | 6×4 = 24 | no | 52 |
| 2 | 5 | 2 | 6×6 = 36 | no | 37 |
| 2 | 5 | 6 | 6×18 = 108 | no | 20 |
| 2 | 5 | 8 | 6×24 = 144 | no | 16 |
| 4 | 4 | 2 | 12×5 = 60 | yes | 2 |
| 5 | 5 | 11 | 15×33 = 495 | no | 5 |
| 12 | 5 | 9 | 36×27 = 972 | no | 5 |

`JO-05`/`JO-07`. With `degree_v = 5` the law collapses to `3n_u × 3n_v`, the two-lane count law; the subtype-4 grammar is therefore a strict superset of the degree-5 family, which is why the control `80aad8d8`'s 20 plane frames (previously "a second, smaller grammar", `SH-09`) now decode as `6×2` patches.

### 4.2 Rational layout and the fail-closed weight gate

The closing middle byte is `1` on the frames whose net is followed by `poles_u·poles_v` weights (coordinates stay 24 B/pole; the weight array adds 8 B/pole) and `0` on non-rational ones. Rational weights are standard NURBS weights and must be **finite and strictly positive**; a net whose weight array is zero, negative, non-finite or non-numeric is refused before evaluation. That gate rejects exactly **5** of the 1,396 frames (1 in `58ed8b28`, 3 in `6c6a2e9f`, 1 in `8e8500b1`), each of which carries a metadata-shaped byte run where the weight array should be (the run contains `fe ff fe ff` and repeated knot values, not one weight per pole). The remaining 1,391 decode.

Coordinates are evaluated as plain control points with the weight array beside them (`Σ wᵢwⱼ Pᵢⱼ / Σ wᵢwⱼ`), which is the layout the bytes carry; the alternative (pre-divided homogeneous coordinates) is not asserted and would change the corner values, so it is refused rather than guessed.

---

## 5. Evaluation and tessellation

The five parts, through the shipped `catpart.geometry.surface.scan_part`:

| Part | frames | decoded | evaluable | tessellated | triangles | vertices |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| `58ed8b28…` PINZA_DERECHA | 395 | 394 | 394 | **394** | 45,824 | 29,114 |
| `6c6a2e9f…` PINZA_IZQUIERDA | 639 | 636 | 636 | **636** | 73,824 | 46,916 |
| `8e8500b1…` ENGRANAJE_SERVO | 350 | 349 | 349 | **349** | 87,360 | 51,429 |
| `b4fd22e3…` CAASddCreateMember | 10 | 10 | 10 | **10** | 56,320 | 29,290 |
| `d523721f…` MPU6050_Clone | 2 | 2 | 2 | **2** | 768 | 450 |
| **total** | **1,396** | **1,391** | **1,391** | **1,391** | **264,096** | **157,199** |

The battery on the accepted rows: corner residual ≤ `2.7e-15` of the net diagonal, `0` folds, `0` hull violations, arc ratios `0.945 … 1.053`, every patch manifold and open (a tensor sheet by construction). Five rows are refused by the weight gate (§4.2), never exported.

The model-scale gate is per grammar: `≤ 1e5 mm` (100 m) for the two-lane grammar, `≤ 1e6 mm` (the bulk probe's model band) for a patch. The `b4fd22e3` patch is coherent at `211,500 mm` with arc ratio `1.004`; the `~993 m` merged two-lane frames are still refused by their folds and arc, so the wider patch band does not reopen them.

The **`80aad8d8` collateral** is real and countable: its 20 subtype-4 plane frames now decode (`6×2` patches) and tessellate, taking that part from 46 to 66 surfaces and from 68,304 to 68,464 triangles. The two-lane counts (`46/46`, `14/17`, `60/63`) are unchanged.

---

## 6. Python ↔ Rust parity

The port mirrors the grammar and the numeric loop. On the seven corpus parts (the five recovered plus both anchors) the PLY is byte-identical and the parsed summary identical:

| Part | triangles | PLY sha256 (both implementations) |
| :--- | ---: | :--- |
| `58ed8b28…` | 45,824 | `2f9a7eccf6758bc6…` |
| `6c6a2e9f…` | 73,824 | `8b4ac9ec25092fab…` |
| `8e8500b1…` | 87,360 | `f7eb2ffbdba2597e…` |
| `b4fd22e3…` | 56,320 | `41772d64a4cac884…` |
| `d523721f…` | 768 | `2608979192cdc3d4…` |
| `80aad8d8…` | 68,464 | `676909d9800f50dc…` |
| `d7ed0772…` | 17,728 | `92f2490187ad9961…` (unchanged) |

One numeric seam had to be aligned for parity: Python's `math.dist` uses CPython's overflow-safe scaling and can differ from the port's `sqrt(dx²+dy²+dz²)` in the last bit. The shipped module now uses the plain expression everywhere the port does (`_distance`), because the PLY tolerance is derived from the bbox diagonal; without it the `8e8500b1` summary's `tolerance_min` differed in the last bit while the PLY happened to match. The fix is expression-level, not a tolerance change, and `d7ed0772`'s PLY hash is unchanged.

The fixture-mode Fidelity pin (`tests/test_port_fidelity.py`) runs both new fixtures (`geometry-surface-patch`, `geometry-surface-patch-rational`) and passes.

---

## 7. Fit and open rate

- Patch head: **1,396/1,396 = 1.0000** of the five parts' marker frames.
- Pole law, both directions: **1,391/1,391 = 1.0000** decodable nets.
- Evaluable and tessellated: **1,391/1,391 = 1.0000**.
- Parts opened: **5/5**.

The whole-manifest open rate, measured by `scripts/triage/probe_open_rate.py` after the change (`docs/evidence/data/open-rate-after-patch.csv`, 1,436 rows):

| | Before | After |
| :--- | ---: | ---: |
| MESH | 1,158 (80.64%) | 1,163 (80.99%) |
| DISPLAY | 209 (14.55%) | 209 (14.55%) |
| BLANK | 69 (4.81%) | 64 (4.46%) |
| **Open** | **1,367 (95.19%)** | **1,372 (95.54%)** |
| dev open | 1,306/1,375 (94.98%) | 1,311/1,375 (95.35%) |
| held-out open | 61/61 (100%) | 61/61 (100%) |

The cross-table moves exactly the five `no-evaluable-surface` rows to MESH; no other row changes class. The BLANK remainder is `48 missing-geometry-store + 16 undecoded-variant`, all with no display carrier.

---

## 8. Detector honesty

- **The join law is not recovered.** The probe shows only that it has no input on the five parts and reproduces the known control relation. The `d7ed0772` merged prefix (54,432 B) is still unsplit, and the two `~993 m` frames remain refused.
- **The order law is refuted for the five, not proven absent.** Row-major wins 1,391/1,391; a square net can accept the column-major reading too (50 cases), so the measurement is a decisive preference, not a uniqueness proof. The one `63.7×` frame is a contaminated lane, not a permutation.
- **The patch grammar is inferred from counts and geometry.** The stored degree is read; the u degree 5 is inherited from the two-lane law, not stored. The rational flag is read from the closing byte and corroborated by a weight array whose values are ~1 and whose count equals the pole count. No CAD kernel ground truth exists.
- **Five frames are refused on weights.** They are counted as refusals, not filtered, and the per-part positive counts are reported above.
- **The model band is per grammar.** A patch is admitted to 1 km; the two `~993 m` merged two-lane frames stay refused by folds and arc. That is a stated widening, not a silent one.
- **`80aad8d8` changes.** Its 20 subtype-4 plane frames now tessellate. The old surface-tessellation note's `60/60`, `46`, and `68,304` figures describe the two-lane grammar only and are superseded for that part by §5.

---

## 9. Reproduction

```bash
export LD_LIBRARY_PATH=/usr/lib:${LD_LIBRARY_PATH:-}
export TMPDIR=/home/alan/.cache/t3-tmp
.venv/bin/python -I scripts/triage/probe_join_order.py
.venv/bin/python -I scripts/triage/probe_join_order.py --anchor d7ed0772
.venv/bin/python -I scripts/triage/probe_join_order.py --anchor 80aad8d8
.venv/bin/python -m pytest tests/test_surface_tessellation.py -q
(cd port && cargo test --quiet)
```

The probe writes `docs/evidence/data/join-order-claims.csv` (JO-01..JO-08; per-part rows plus the population row). Deterministic; `mmap` + read-only; ~55 s for the five parts. The open-rate rows are `docs/evidence/data/open-rate-after-patch.csv` (1,436 rows, the post-patch run; the pre-patch artifact stays `open-rate-files.csv`).
