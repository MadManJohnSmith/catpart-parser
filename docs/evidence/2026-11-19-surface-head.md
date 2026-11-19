# Evidence: the `a5 03 34` surface head — knot lanes and the degree-5 pole net (2026-11-19)

**Date**: 2026-11-19
**Status**: COMPLETE for the head grammar (63/83 tail-closed frames decode, 60 of them evaluate); **partial** for the population (20 frames are a second, smaller grammar; 3 decoded frames do not evaluate and are named)
**Target**: the named ambiguity in `docs/evidence/2026-11-19-bulk-stream.md` §4.4: the 182-byte payload prefix of the class-`0x34` surface record. The bulk probe proved a *pole net*; this probe turns it into an *evaluable surface*.
**Method**: byte-level probe `scripts/triage/probe_surface_head.py`; corpus-free tests `tests/test_surface_head.py` (23); claims `docs/evidence/data/surface-head-claims.csv` (`SH-01`..`SH-15`). Read-only over the corpus; `src/` and the exporter are untouched.

---

## 1. Executive summary

The prefix is a **self-delimiting record with two knot lanes**. Its lengths are the distinct-knot counts (one more than each direction's span count); its lanes are those knot vectors; and the pole net that follows is exactly `3·n_u` by `3·n_v`. From those two counts the degree is *derived*, not assumed: **degree 5, interior multiplicity 3, C2**, knots `[u0]×6 + interior×3 + [un]×6`. The record is then a fully evaluable non-rational B-spline surface.

| Measurement | `80aad8d8` | `d7ed0772` | 83 tail-closed frames |
| :--- | ---: | ---: | ---: |
| `a5 03 34` marker frames | 70 | 36 | 106 |
| … with a tail-closed grid | 66 | 17 | 83 |
| … decoded by the two-lane head | **46** | **17** | **63 (0.7590)** |
| … the 12-triple plane subtype | 20 | 0 | 20 |
| Pole points in decoded frames | 41,580 | 18,468 | 60,048 (+240 plane = 60,288) |
| Head predicts the grid offset | 46/46 | 17/17 | **63/63** |
| Grid law `points = 9·n_u·n_v` | 46/46 | 17/17 | **63/63** |
| Degree census: only `(5, 3)` fits | 46/46 | 17/17 | **63/63** |
| Corners reproduce the corner poles | 46/46 | 17/17 | **63/63** (residual 8.2e-16 rel.) |
| Finite and inside the pole hull | 46/46 | 17/17 | **63/63** |
| No folded normal, model scale, chord-length knots | 46/46 | 14/17 | **60/63 (0.9524)** |
| **Evaluable surfaces** | **46** | **14** | **60/83 (0.7229)** |

**Verdict.** The head **pins**. Every tail-closed frame either decodes to the two-lane grammar (63) or to a smaller, separately-grammared plane record (20); none is unparsed. Of the decoded frames, 60 evaluate into surfaces whose corner poles are reproduced exactly, that stay finite and inside their pole hull, whose knot span matches the pole-polygon arc length to within 2%, and whose normal field has no fold. The three that resist are **all in `d7ed0772`** and are named in §6: two carry a ~1 km coordinate scale and one has no station-constant pole order.

---

## 2. The head layout — both bases

Worked frame: the first surface record of `80aad8d8` (`510.000_NOTE A.CATPart`, V5R21SP0HF0). The `CATPrtCont` block starts at **1,565,029**; the frame starts at **1,584,389** (`block+19,360`); its payload starts at **1,584,397** (`block+19,368`).

| payload+ | abs | block+ | width | field | value |
| ---: | ---: | ---: | :--- | :--- | :--- |
| 0 | 1,584,397 | 19,368 | u32le | record tag | `5` (constant, 83/83) |
| 4 | 1,584,401 | 19,372 | u32le | `n_u` (u lane length) | `12` |
| 8 | 1,584,405 | 19,376 | u8 | subtype byte | `0` |
| 9 | 1,584,406 | 19,377 | u32le | `mode_u` (retained) | `2` |
| 13 | 1,584,410 | 19,381 | f64le×12 | `knots_u` | −770.550 … 3,962.768 |
| 109 | 1,584,506 | 19,477 | u8 | second lane tag | `1` |
| 110 | 1,584,507 | 19,478 | u32le | record tag | `5` |
| 114 | 1,584,511 | 19,482 | u32le | `n_v` (v lane length) | `7` |
| 118 | 1,584,515 | 19,486 | u8 | subtype byte | `0` |
| 119 | 1,584,516 | 19,487 | u32le | `mode_v` | `2` |
| 123 | 1,584,520 | 19,491 | f64le×7 | `knots_v` | −85.585 … 1,413.011 |
| 179 | 1,584,576 | 19,547 | 3 B | closing bytes | `01 00 00` |
| **182** | **1,584,579** | **19,550** | f64le×756 | **pole net, 36×21** | 18,144 B |
| 18,326 | 1,602,723 | 37,694 | 152 B | tail (bulk probe's closure law) | not decoded |
| 18,478 | 1,602,875 | 37,846 | — | payload end = next frame start | — |

The head is therefore `30 + 8·(n_u + n_v)` bytes: `13` for the u block, `1 + 13` for the v block, `8·(n_u+n_v)` for the lanes, and `3` closing bytes. The second anchor's first frame (`payload` abs **471,428** = `block+99,425`, block 372,003) has `n_u = n_v = 11`, head 206 B, grid at abs **471,634** (`block+99,631`), 33×33 poles, and a 154-byte tail.

**The head is self-delimiting.** On 63/63 decoded frames the offset the head predicts for the pole grid is the same offset the bulk probe's *value* scan found (`SH-05`), and the closing bytes plus the 152/154-byte tail band must both match before a head is accepted. The grid is never searched for.

### 2.1 The second grammar (20 frames, not a failure of this one)

Twenty frames of `80aad8d8` carry a 12-triple grid in a 4×3 arrangement and a 54-byte prefix whose subtype byte is `4`, not `0`, and whose `mode` is `0` (`SH-09`). Their payload is 494 B = 54 + 288 + 152. They are the "planes" of the population: `points = 12` is not `9·n_u·n_v` for any integer pair, so the two-lane law cannot describe them and this probe does not force it. They hold 240 of the 60,288 points; the bulk probe's `BS-12` total is `60,048 + 240`.

---

## 3. Law 1 — the pole counts

The grid holds exactly `9·n_u·n_v` f64 triples on 63/63 frames (`SH-13`). With `n_u = 12, n_v = 7` that is `36 × 21 = 756`, the shape the bulk probe measured geometrically. Seven distinct `(n_u, n_v)` pairs occur:

| `n_u`×`n_v` | frames | poles | knots u/v |
| ---: | ---: | ---: | ---: |
| 12×7 | 13 | 36×21 | 42 / 27 |
| 13×7 | 15 | 39×21 | 45 / 27 |
| 8×6 | 2 | 24×18 | 30 / 24 |
| 11×11 | 25 | 33×33 | 39 / 39 |
| 17×11 | 2 | 51×33 | 57 / 39 |
| 16×7 | 5 | 48×21 | 54 / 27 |
| 16×10 | 1 | 48×30 | 54 / 36 |

Two independent confirmations:

- **The value scan agrees.** The bulk probe factorises a net by the largest row length whose rows are station-constant. On 60/63 decoded frames that independent factorisation is *exactly* `(3n_u, 3n_v)` (`SH-07`). The three exceptions are the three frames that fail evaluation (§6).
- **The head resolves the scan's ambiguity.** Three frames are factorised by the value scan as `84×12`, `121×9` and `96×15`; those are the same point counts under a finer row split (`1008`, `1089`, `1440`). The head's counts say `48×21`, `33×33`, `48×30` — and on those three the head's reading is the one that *does not* evaluate, which is how the disagreement was caught rather than smoothed over.

---

## 4. Law 2 — the degree, derived

A clamped B-spline of degree `d` with interior multiplicity `m` and `n` distinct knots has `s = n − 1` spans and

```
poles = (d + 1) + m·(s − 1) = (d + 1) + m·(n − 2)
knots = poles + d + 1
```

Requiring `poles = 3n` **at one constant degree for every frame** leaves exactly one solution (`SH-12`, 32 hypotheses tested, `d = 1..8`, `m = 1..4`):

```
(d + 1) + m·(n − 2) = 3n   ⟺   (d, m) = (5, 3)
```

Within `m = 3` the pole count is `3n + (d − 5)`, so the degree is pinned monotonically; every `m ≠ 3` forces a degree that depends on `n` (`m = 2` needs `d = n + 3`, `m = 1` needs `d = 2n + 1`, `m = 4` needs `d = 7 − n`).

The knot vector is then `[u0]×6, u1×3, …, u_{n−2}×3, [u_{n−1}]×6`: length `3n + 6`, poles `3n`, continuity `5 − 3 = 2`. Both lanes are strictly increasing on 63/63 frames (940 + 382 lane entries, `SH-03`), which a knot vector must be.

**The alternative reading is refuted by the data, not only by arithmetic.** If the lane were the *span* count with one knot implicit, `(d = 2, m = 3)` would also give `3n` poles — but multiplicity 3 at degree 2 is `C−1`: every span an independent quadratic Bézier segment, so each span's last pole must coincide with the next span's first or the surface is torn. Measured on the 63 decoded nets: **0** coincident seam rows and **0** coincident seam columns (`SH-12`). A degree-5, multiplicity-3 net predicts exactly that, and the poles deliver it.

**A third, independent confirmation** (`SH-06`): the u knot span equals the pole-polygon arc length within 2% on every in-scale frame (ratios 0.984 … 1.001). A chord-length knot vector must do that; a mis-assigned lane would not.

---

## 5. Evaluation and validation

The probe evaluates the decoded surface with a Cox-de Boor basis over the built knot vectors and checks four things that a wrong decode breaks:

| check | what it proves | result |
| :--- | :--- | :--- |
| corner residual | a clamped surface reproduces its corner poles | **≤ 8.2e-16** of the diagonal on 63/63 |
| finiteness | every sample on a 21×21 parameter lattice is finite | 63/63 |
| pole hull | a B-spline surface lies in the convex hull of its poles | 0 violations on 63/63 |
| fold | cells sharing a parameter edge never reverse normals | 0 folds on 60/63 |

There is **no seam to self-intersect**: the decode is one tensor-product patch, C2 across every interior knot, so the boundary and the interior are continuous by construction; the fold test replaces the seam test that a multi-patch reading would need.

The evaluated surface is geometrically sane: the first `80aad8d8` surface spans x 4,230.600 … 8,946.979, y −1,067.150 … 1,312.302, z −174.813 … 1,113.647 mm — the same box the pole net occupies (the surface is inside it) — and the `d7ed0772` first surface spans 4,880.132 … 9,948.901 × 604.284 … 1,349.125 × 12.172 … 356.575 mm. The surface-to-pole distance at the knot lattice is 6–11% of the net's diagonal (median 0.0939): a genuine degree-5 pole net hugs its surface, and the three frames whose nets do not are the three that fail.

---

## 6. What resists, and the next probe

Three of the 63 decoded frames do not evaluate (`SH-15`). All three are in `d7ed0772`, the anchor whose numeric allocations the bulk probe already reported as **merged** (`BS-03`):

| frame (abs) | `n_u`×`n_v` | `mode` | folds | max coordinate | knot span / pole arc |
| ---: | :---: | :---: | ---: | ---: | ---: |
| 669,430 | 16×7 | (3,2) | 214 | 993,043 mm | 9.0e-4 |
| 1,271,468 | 11×11 | (4,3) | 100 | 993,043 mm | 9.0e-4 |
| 1,416,850 | 16×10 | (3,4) | 59 | 9,529 mm | 63.7 |

Named blocker, per frame, in the order the fields resist:

1. **Two frames carry a kilometre scale.** Their pole coordinates reach `9.93e5` mm — 1,000× the model envelope every other frame sits in — and their knot lanes are *identical* to the in-scale nets of the same `(n_u, n_v)`. So the head is fine and the **numeric run is not one surface's poles**: the same merged-allocation failure the bulk prefix shows. The next probe is the one the bulk note already names: the allocation↔frame join law (`BS-09` shows one copy is bit-identical), which would tell us whether these runs are several nets concatenated.
2. **One frame has no station-constant pole order.** Its rows are not constant in any axis (the best row split, `C=9`, still spreads 0.5% of x and 25-30% of y and z), so it is not in the swept order the other 60 are. Its knot span is `63.7×` its pole-polygon arc length, so the lanes and the net are not in the same parameter space. The next probe is an *ordering* test: try the 3-ways the same 1,440 triples can be laid out (row-major, column-major, and the per-span transpose) and score each by fold count and arc ratio — the same yardstick this probe uses, so a pass is not a re-labelling.

Everything else is decoded: the `mode` field (values `2`, `3`, `4`, per direction, `{(2,2):30, (3,2):5, (4,3):25, (4,4):2, (3,4):1}`) is **retained, not interpreted** — it does not correlate with `n_u`, `n_v`, the tail, or the folding, and assigning it a meaning is the next distinguishable question after the three frames above. The 152/154-byte tail, the three closing bytes, and the plane subtype's own head are likewise measured but not interpreted.

---

## 7. Fit rate

- **Head grammar: 63/83 = 0.7590** of tail-closed frames (100% of the two-lane ones; the other 20 are a second grammar, not a parse failure).
- **Grid law and degree law: 63/63 = 1.0000** of decoded frames.
- **Evaluable surface: 60/63 = 0.9524** of decoded frames, **60/83 = 0.7229** of all tail-closed frames.

---

## 8. Reproduction

```bash
export LD_LIBRARY_PATH=/usr/lib:${LD_LIBRARY_PATH:-}
.venv/bin/python -I scripts/triage/probe_surface_head.py --anchor 80aad8d8
.venv/bin/python -I scripts/triage/probe_surface_head.py
.venv/bin/python -m pytest tests/test_surface_head.py -q
```

The probe writes `docs/evidence/data/surface-head-claims.csv` (23 rows: `SH-01`..`SH-09` per anchor, `SH-10`..`SH-15` population). Deterministic; `mmap` + read-only; ~8 s. It reuses `probe_bulk_stream` only for region/frame/net discovery, so the head is decoded against the same 83 frames the bulk note measured.

---

## 9. Detector honesty

- **The degree is inferred, not read.** The head carries no degree field. `(5, 3)` is the unique constant-degree solution of the count law; the alternative `(2, 3)` reading is refuted by the zero coincident seam poles, and the chord-length check agrees. A format where the degree lives outside this record would look the same, so what is claimed is *a degree-5 surface consistent with every frame*, not "the file says degree 5".
- **What "evaluable" means here.** Exact corner poles, finite samples, hull containment, no fold at 1/20-domain steps, model scale, and a chord-length knot span. That is a validation of the *decode*, not a comparison against the CAD kernel: no ground-truth surface exists in this corpus.
- **`mode` is not interpreted.** Its two values per frame are retained with their offsets; no meaning is assigned, and no other class byte is claimed.
- **The plane subtype is not decoded.** Twenty frames are reported as a second grammar with their measured layout (54 B, subtype byte 4, 12 triples, 494 B payload) and excluded from the two-lane rates rather than counted as misses or as fits.
- **The three resisting frames are counted as failures**, not filtered: the usable rate is stated over all 63 decoded frames and over all 83 tail-closed frames.
- **The value scan is not replaced.** The probe cross-checks its prediction against the bulk probe's independent geometric factorisation and reports the three disagreements instead of forcing agreement.
- **No export claim.** This is the payload grammar only: `src/` and the exporter are untouched, and nothing here says the exporter should read these surfaces yet — the allocation↔frame join and the E5 dialect remain open.
