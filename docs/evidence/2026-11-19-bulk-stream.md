# Evidence: the pre-CGM bulk stream — A/B frame law and f64 pole nets (2026-11-19)

**Date**: 2026-11-19
**Status**: COMPLETE for the two anchors (frame law measured, numeric payload decoded as point nets); **partial** for the population (three content dialects, only one framed here)
**Target**: the open question left by the CGM grid probe (`docs/evidence/2026-11-18-cgm-grid-probe.md` §7): recover the *class-header law* for the bulk that precedes `CGMGeom`.
**Method**: byte-level probe over the no-facet population, `scripts/triage/probe_bulk_stream.py`; corpus-free tests `tests/test_bulk_stream.py` (20); claims `docs/evidence/data/bulk-stream-claims.csv` (`BS-01`..`BS-19`). Read-only over the corpus; `src/` and the exporter are untouched.

---

## 1. Executive summary

The bulk is the **`CATPrtCont` storage block's content stream** — not the CGM region. On the two largest no-facet parts it is 2,142,026 B and 1,382,225 B; over the 128 no-facet parts it is **10,950,647 B** (`BS-10`, the brief's "~11.17 MB" order of magnitude; the 0.2 MB difference is a boundary-definition difference not resolved here).

Three measurements, one verdict:

| Measurement | `80aad8d8` | `d7ed0772` | 128 no-facet | 3 facet carriers (control) |
| :--- | ---: | ---: | ---: | ---: |
| `CATPrtCont` region | 2,142,026 B | 1,382,225 B | 10,950,647 B | 48,953 B |
| Content stream (after the metadata table) | 2,141,186 B | 1,381,385 B | 10,861,978 B | 46,733 B |
| Metadata tables parsed and tile-exact | 1/1 | 1/1 | **128/128** | 3/3 |
| Frame clusters / frames | 8 / 26,248 | 7 / 2,959 | 33 / 67,564 | 0 / 0 |
| Framed bytes (coverage of content) | 1,970,597 (**0.9203**) | 1,259,155 (**0.9115**) | 4,683,142 (0.4312) | 0 (0.0000) |
| Framed **+ f64 allocations** (accounted) | 2,110,270 (**0.9856**) | 1,348,695 (**0.9763**) | 4,912,355 (0.4523) | 0 |
| `a5 03 34` marker frames | 70 | 36 | 106 | 0 |
| … with a tail-closed pole grid | 66 | 17 | **83** (2 files) | 0 |
| Pole points decoded | 41,820 | 18,468 | **60,288** | 0 |
| Content-prefix f64 allocation | 756 points, 36×21, **validated** | 2,268-double run, **merged, not one net** | 6/128 regions | 0 |
| Content dialect (head) | object-stream | object-stream | 19 object-stream / 103 E5 / 4 f64-net / 2 other | — |

**Verdict.** The bulk **does** frame under a two-family length law, and it **does** carry exact-geometry coordinates as f64 pole nets. The frames tile in contiguous clusters with **zero residue inside each cluster**; the stream *as a whole* does not tile with one grammar because the format interleaves **unframed f64 allocations** (and one text allocation, plus the footer) between record clusters. Adding the allocations bounds 98.56% / 97.63% of the two anchors' content; what remains is measurable, not noise.

This is the answer to the CGM probe's next step: the class header exists (`<family byte> <flag> <class> <length> <token>`), the bulk carries coordinates, and the **exact solids are reachable from the `CATPrtCont` stream, not from the `CGMGeom` dictionary**.

The framing law itself is public documentation, not a corpus invention: the A/B family frame is documented in the cadmpeg CATIA V5 format specification (CC-BY-4.0, `docs/formats/catia.md` §6). This probe's contribution is the **corpus measurement**: which families/widths/flags occur, how far they tile, and what the residue is made of.

No span of the bulk is compressed: across all 128 regions **no 4 KiB window exceeds 7.9 bits/byte** (`BS-19`), and the high-entropy bands are f64 payload, not an opaque codec.

---

## 2. Region anatomy — both bases

Worked anchor `80aad8d8` (`510.000_NOTE A.CATPart`, V5R21SP0HF0, 4,196,403 B). Offsets are block-relative (`block+`) and absolute file offsets; the block starts at **1,565,029** (`BS-01`).

| block+ | abs | size | field | evidence |
| ---: | ---: | ---: | :--- | :--- |
| 0 | 1,565,029 | 112 | `34 12 "CATStorageProperty" ... 34 0a "CATPrtCont" 9f` block header | `BS-01` |
| 112 | 1,565,141 | 8 | `36 08 "FINJPL  "` writer tag | byte-verified |
| 112..644 | … | 532 | project-flags attribute preamble (`CATProjectFlags`, opaque slot stream) | not decoded |
| **644** | **1,565,673** | 12 | **metadata table header (BE)**: `total_size=196`, `identity=23`, `count=3` | `BS-02` |
| 656 | 1,565,685 | 48 | record 1: id 26, type 2, 34 B — `00 03 "CATPropertySets" 00 00` | `BS-02` |
| 704 | 1,565,733 | 54 | record 2: id 25, type 2, 40 B — `00 03 "CATStorageProperty" 00 00` | `BS-02` |
| 758 | 1,565,787 | 82 | record 3: id 24, type 2, 68 B — `"Cont_50f58d0d_1ae0_63f47193_33d25" 00 00` | `BS-02` |
| **840** | **1,565,869** | 18,144 | **content prefix**: 756 f64le triples (36×21 pole net) | `BS-03`, `BS-09` |
| 18,984 | 1,584,013 | 2,094,144 | 8 frame clusters / 26,248 frames (1,970,597 B framed) interleaved with 8 allocations | `BS-04` |
| 2,113,128 | 3,678,157 | 28,898 | footer region; `DASSAULT-SYSTEMES` at block+2,141,905 (abs 3,706,934) | byte-verified |

The second anchor (`512.000_NOTE A.CATPart`, V5R21SP0HF0, 1,876,884 B, block 372,003) has the **same** anatomy: metadata table at block+644, 196 B, 3 records (ids 29/28/27), content at block+840 (`BS-01`, `BS-02`). The two preambles differ only in the `Cont_` name characters and in the four **identity** words (header 23 → 26, records 26/25/24 → 29/28/27 — all +3, tracking the three-character-longer name); the layout and the `total_size` are identical. The identity is therefore content-derived, not a constant.

**Metadata table layout** (`BS-02`, both anchors, tile-exact):

| offset | type | field |
| ---: | :--- | :--- |
| +0 | u32be | `total_size` (196) |
| +4 | u32be | `identity` (23 on `80aad8d8`, 26 on `d7ed0772` — content-derived) |
| +8 | u32be | `count` (3) |
| +12 | — | `count` records: `size:u32be`, `identity:u32be`, `value_type:u16be`, `value_bytes:u32be`, value; `size == 14 + value_bytes`, records close at `total_size` |
| value (type 2) | — | `00 03` + UTF-16BE text + `00 00` for the two property names; bare UTF-16BE + NUL for the `Cont_` content name |

This table is what makes `content_start` **derived** rather than guessed: the last record names the stream, and the content begins at the table's end (`block+840` on both anchors).

---

## 3. The frame law

### 3.1 Grammar

Two families, distinguished by the first byte; the header-token width `W` is the difference from the family base:

```
A family (u32 length):  byte0 = 0xA4 + W   (a5/a6/a7/a8 ⇒ W 1..4)
  +1 flag (0x03 / 0x13 / 0x83)
  +2 class
  +3 payload_len:u32le
  +7 header_token[W]
  payload @ +7+W      next @ +7+W+payload_len

B family (u8 length):   byte0 = 0xB1 + W   (b2/b3/b4/b5 ⇒ W 1..4)
  +1 flag (0x03 / 0x13 / 0x83)
  +2 class
  +3 payload_len:u8
  +4 header_token[W]
  payload @ +4+W      next @ +4+W+payload_len
```

The header token is **retained, not interpreted**: it is not a per-record id and does not select the payload grammar. A frame is *framed* when its length closes on the next frame; the class byte is a vocabulary value, not a proven type.

### 3.2 What the walk measures

Both anchors frame in **contiguous clusters**. Anchor `80aad8d8` (`BS-04`; block-relative):

| # | cluster start | cluster end | frames | bytes |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 18,984 | 155,909 | 881 | 136,925 |
| 2 | 174,681 | 529,904 | 5,463 | 355,223 |
| 3 | 556,040 | 687,949 | 134 | 131,909 |
| 4 | 710,346 | 825,791 | 361 | 115,445 |
| 5 | 826,649 | 1,067,518 | 1,524 | 240,869 |
| 6 | 1,107,910 | 1,272,642 | 469 | 164,732 |
| 7 | 1,285,616 | 1,885,934 | 11,991 | 600,318 |
| 8 | 1,887,952 | 2,113,128 | 5,425 | 225,176 |

Every cluster closes exactly on its own end; each is followed by a non-frame run. Family/width census (`BS-04`): `B1` 23,734, `B2` 1,243, `B3` 910, `B4` 37, `A1` 321, `A2` 3. Flags: `0x03` 24,029, `0x13` 2,214, `0x83` 5. Class vocabulary (top): `0x06` 3,880, `0x5d` 3,547, `0x05` 3,544, `0x18` 2,412, `0x5b` 2,196, `0x5e` 1,974, `0x27` 1,081, `0x5c` 972, `0x64` 906, `0x25` 605, `0x23` 598, `0x24` 566, `0x20` 529.

Anchor `d7ed0772` (`BS-04`): 7 clusters, 2,959 frames, 1,259,155 B (0.9115); widths `B1` 2,553, `B2` 149, `B3` 97, `A1` 149, `A3` 7, `B4` 4; the same class head.

### 3.3 The residue, classified

The gaps between clusters are **not noise** (`BS-05`, `BS-18`). Anchor `80aad8d8` gaps (bytes): `18,144`, `18,772`, `26,136`, `22,397`, `858`, `40,392`, `12,974`, `2,018`, `28,898`.

- **Seven of nine** are dominated (≥80%) by one f64 run: the content prefix (18,144 = 756×24, §4.1), and six inter-cluster allocations (18,772 / 26,136 / 22,397 / 40,392 / 12,974 / 858 bytes; several start at a 4-byte phase, e.g. `+4`, so the array is not 8-aligned to the block). The `40,392`-byte gap is exactly **1,683 triples**, the pole count of one of the anchor's `a5 03 34` records — the allocations are copies of the same nets.
- **One** (`2,018` B) is a text allocation: `01 7f ab 20 | 12 00 00 00 "2011Spring@3ds.com" …` (u32le-framed strings).
- **One** (`28,898` B) is the footer region: vendor footer `DASSAULT-SYSTEMES` / `CATIA` / `041803P` and zero padding, plus the trailing nested block records.

Adding only the f64 allocations to the framed bytes accounts for **2,110,270 / 2,141,186 = 0.9856** of the content (`BS-18`); the text allocation and footer are the rest. Anchor `d7ed0772`: **1,348,695 / 1,381,385 = 0.9763`; here 4/8 gaps reach the 80% bar but 6/8 contain an f64 net (the allocations carry a small non-f64 prefix/suffix: e.g. 10,368 B gap with a 5,904 B run).

**So the honest tiling statement is:** each cluster tiles **exactly** (zero residue) under the A/B law; the content stream as a whole does **not** tile under it, because the format stores coordinate allocations outside the frame ranges. The allocation boundaries are two-sided and structural (previous record end / next record start), not lookahead-fitted lengths.

### 3.4 Entropy profile

4 KiB-window Shannon entropy (`BS-19`) separates the three territories and rules out compression:

| span | min | median | max | windows > 7.9 b/B |
| :--- | ---: | ---: | ---: | ---: |
| `80aad8d8` content | 3.32 | 7.27 | 7.61 | 0 |
| `80aad8d8` framed clusters (mean) | — | — | 6.99 | — |
| `80aad8d8` gaps (mean) | — | — | 7.06 | — |
| `d7ed0772` content | 4.36 | 7.42 | 7.64 | 0 |
| `d7ed0772` framed clusters (mean) | — | — | 7.56 | — |
| `d7ed0772` gaps (mean) | — | — | 7.23 | — |
| 128 regions | mean median 4.50 | — | — | **0 files** |

The low minima are the metadata/preambles; the high bands are f64 payload (~7.5 b/B, what IEEE doubles look like). **No 4 KiB window anywhere in the 128-region bulk exceeds 7.9 b/B**, so the bulk is not a compressed stream: the 6 MB that frames nothing is not zlib/opaque — it is typed data this probe has not framed (E5) or unframed allocations.

---

## 4. The numeric payload

### 4.1 The content-prefix allocation (block+840)

Anchor `80aad8d8` (`BS-03`, `BS-09`): 18,144 B = **756 f64le triples**, immediately after the metadata table. Decoded as a rectangular pole net:

- shape **36 rows × 21 columns**; the station coordinate is **x** (mean within-row range / global span = **1.3e-4**, bar 1e-2); stations are **monotone** (4,231.1 → 8,947.0 mm); rows are open profiles (mean first-to-last distance 2,347.5 mm), so the net is a swept grid, not a closed tube.
- AABB: x 4,230.600..8,946.979, y −1,067.150..1,312.302, z −174.813..1,113.647 (mm).
- **Bit-identical** to the pole grid inside the first `a5 03 34` frame of the same file (`BS-09`, 18,144/18,144 bytes identical).

Anchor `d7ed0772` (`BS-03`): the prefix run is **2,268 doubles** (6,805 f64 = 54,432 B of the 58,904 B gap), but it is a **merged allocation, not one net**: its x stations run 1,866.9 → 402,995.7 mm (non-monotone) and the AABB reaches −993,043 mm. The probe reports it as not validated (`passes=0`) rather than fitting a grid.

### 4.2 The `a5 03 34` surface frame

The pole net is not only an unframed prefix: it is the **payload of a class-`0x34` A-family frame** (a5, width 1, flag 0x03). Worked example (`BS-08`), both bases:

| block+ | abs | size | field |
| ---: | ---: | ---: | :--- |
| 19,360 | 1,584,389 | 8 | frame header: `a5 03 34 2e 48 00 00 0f` (family a5/W1, flag 0x03, class 0x34, `payload_len=18,478`, token `0x0f`) |
| 19,368 | 1,584,397 | 182 | payload prefix (not decoded; see §4.4) |
| **19,550** | **1,584,579** | **18,144** | **pole grid**: 756 f64le triples, 36×21, same values as §4.1 |
| 37,694 | 1,603,723 | 152 | payload tail (not decoded); next frame starts at block+37,846 |

Validation across the anchors (`BS-06`, `BS-07`): `80aad8d8` has **70** marker-class `a5 03 34` frames, of which **66** close on the same 152/154-byte tail and carry a pole grid (**46** pass both the rectangular-spread and 100 m model-scale bars); `d7ed0772` has **36** marker frames, **17** tail-closed, **15** validated. Point counts observed: 12, 432, 756, 789, 819, 1,008, 1,089, 1,260, 1,440, 1,683 (and merged runs). Grid factorisations: 36×21, 33×33, 48×21, 1089-point 33×33, etc.

### 4.3 Validation performed (not assumed)

- **Finite / in-band**: every point is finite; the band is `[-1e6, 1e6]` mm with an exact-zero allowance (a profile crossing the origin must not split the run; the denormal band below 1e-3 is still excluded because integer arrays alias there).
- **Rectangularity**: the largest divisor `cols` whose rows are near-constant in one axis (mean within-row range ≤ 1% of the axis span) is reported with its spread; the 36×21 net scores 1.3e-4.
- **Station monotonicity**: the 756-point net's 36 stations are monotone; the anchor-2 merged run is not (reported, not fitted).
- **Model scale**: coordinates must stay inside 100 m; that is what flags the anchor-2 merged run and four large-scale grids.
- **Tail closure**: a surface grid must end exactly 152 or 154 bytes before the frame end — the two tails measured on every clean record. This two-sided rule is what prevents zero padding in the tail from extending a point count.

### 4.4 What is *not* decoded (named ambiguity)

The 182-byte payload prefix of `a5 03 34` is **not decoded**. Measured fields only:

| payload+ | width | value in the worked example | status |
| ---: | ---: | :--- | :--- |
| +0 | u32le | `5` — constant on **all 83** tail-closed frames | fact |
| +4 | u32le | 12 (11..17 observed) — correlates with grid rows/3 on several records (36→12, 39→13, 33→11, 48→16) | candidate |
| +8 | u8 | `0` | fact |
| +9 | u32le | 2/3/4 (V-lane count?) | candidate |
| +13 | f64le lane | knot-like values (823.4, 1,278.0, 1,497.9, 2,034.8, 3,343.8, … — not normalized to [0,1]) | unknown |
| +182 | f64le[3×756] | pole grid | **decoded** |
| end−152 | bytes | tail (limits/parameterisation per the public spec) | not decoded |

Consequence: the probe yields a **control-point net (a point set)**, not an evaluable NURBS surface. Degrees, knot vectors, weights and current limits are present in the prefix/tail but are not read here; the public spec's payload description (degrees/K as compact integers, knots as f64, mode byte, pole grid, tail) is **not yet matched** by the corpus bytes at the documented offsets — that mismatch is the next RE target (§5.2).

### 4.5 Smallest decoder (anchor → point set)

```python
def point_net(data, frame_start):
    """Decode one a5 03 34 frame's pole grid (see probe for the full form)."""
    assert data[frame_start] == 0xA5 and data[frame_start + 2] == 0x34
    payload_len = int.from_bytes(data[frame_start + 3:frame_start + 7], "little")
    payload = frame_start + 8                      # 7-byte header + W=1 token
    end = payload + payload_len
    count, start = longest_f64_run(data, payload, end)   # maximal finite, in-band run
    n = count // 3
    for tail in (152, 154):                        # measured closure law
        if (end - tail - start) % 24 == 0:
            n = (end - tail - start) // 24
            break
    return [struct.unpack_from("<3d", data, start + 24 * i) for i in range(n)]
```

With `frame_start = 1,584,389` this returns 756 points in 36 rows of 21 (the §4.1 net). The committed probe adds the rectangularity/scale/monotonicity report.

---

## 5. Population, verdict, next step

### 5.1 Population

The 128 no-facet parts (`BS-10`..`BS-17`):

- **Bulk**: 10,950,647 B, 10,861,978 B of content; metadata tables parse and tile on **128/128**.
- **Dialects** (`BS-16`, by content head): **object-stream 19** (A/B frames; includes both anchors), **E5 103** (content opens with a `01`-framed stream header carrying the writer version, e.g. `01 70 15 00 00 0c 00 00 00 "V5R11-TCX:XP"`, then `e5 0d` records), **f64-net 4** (a pure coordinate allocation, e.g. `bdd7ec87`, `d665cd12`), **other 2**.
- **Object-stream subset** (`BS-17`): 4,985,817 B content, 4,683,142 B framed (**0.9393**), 4,912,355 B accounted (**0.9853**); 83 tail-closed `a5 03 34` grids carrying **60,288 pole points**.
- **Control** (`BS-15`): the three facet carriers carry 48,953 B of `CATPrtCont` region, **0** frames and **0** surface frames — the bulk is not a facet-carrier artefact.
- **Overall framed fraction is 0.4312** (`BS-11`) only because 103/128 regions are the E5 dialect, which this probe does not frame; mixing dialects into one denominator would misstate both.

### 5.2 Verdict

- **Framing law: decoded and measured.** The A/B family frame (class header + length + token) tiles every record cluster exactly on both anchors; residue inside a cluster is zero.
- **Numeric payload: present.** f64 coordinate pole nets exist both as unframed content allocations and inside `a5 03 34` frames; the 756-point net is a 36×21 swept grid whose axes and scale validate.
- **Consequence for the tickets**: the exact solids are **not** in the `CGMGeom` dictionary (CGM probe, unchanged) — they are in the `CATPrtCont` object stream that precedes it. The "0/128 exact solids" blocker now has a concrete carrier and a concrete point-set decoder.
- **Ambiguity named**: the surface prefix/tail semantics are undecoded (§4.4), so what is proven is a *pole net*, not a *NURBS evaluation*. The E5 dialect (103/128) is untouched.

### 5.3 Smallest next probe (not taken here)

1. **Decode the `a5 03 34` payload head** with the two anchors in hand: the 182-byte prefix has a constant `u32 5`, a count at +4 that tracks `rows/3`, and a knot-like f64 lane at +13. The smallest probe is a *format-fit*: take the 83 tail-closed frames, extract `(payload+0, +4, +9, +13-lane, points, rows, cols, tail)`, and test whether `rows = 3·k + 3` / `cols = degV+1` for a single `(degree, multiplicity)` law. If it fits, the knots become readable and the surface evaluable. If it does not, report the mismatch against the public spec's documented payload.
2. **Frame the E5 dialect** (`e5 0d` records after the `01` stream header) — that is 103/128 of the population and ~6 MB of the bulk. The anchors already show the entry point: the `01`-framed header ends with the writer string and the first `e5 0d` marker follows; the next probe should recover `e5 0d <class> <length>` by the same "close on the next record" test.
3. **Join the two representations**: the prefix allocation duplicates the first surface grid bit-for-bit (`BS-09`). A join law (allocation index ↔ `a5 03 34` frame) would let the exporter read one copy and verify the other.

---

## 6. Reproduction

```bash
export LD_LIBRARY_PATH=/usr/lib:${LD_LIBRARY_PATH:-}
.venv/bin/python -I scripts/triage/probe_bulk_stream.py --anchor 80aad8d8 --no-population
.venv/bin/python -I scripts/triage/probe_bulk_stream.py
.venv/bin/python -m pytest tests/test_bulk_stream.py -q
```

The probe writes `docs/evidence/data/bulk-stream-claims.csv` (30 rows: 19 claim ids — the anchor ids `BS-01`..`BS-09`, `BS-18`, `BS-19` appear once per anchor, `BS-10`..`BS-17` are population rows). Deterministic; `mmap` + read-only; ~6 s for the population. The metadata table parser validates tiling and the `Cont_` name before accepting a content start, so a failure shows up as a `BS-02` miss rather than a silent offset.

---

## 7. Detector honesty

- **Source of the grammar.** The A/B frame law is taken from the public cadmpeg CATIA specification (CC-BY-4.0) as a *hypothesis* and then measured on this corpus. The probe does not import that project and does not claim its wider model (BREP spines, E5, `7C08` graphs). What is committed here is the corpus measurement, the metadata-table validation, the pole-net decoder and the residue classification.
- **What "framed" means.** A frame is counted when its length lands exactly on the next frame; the payload is *framed*, not *decoded*. The header token is retained and not interpreted. Classes are a vocabulary, not proven types.
- **What "accounted" means.** Framed bytes plus the gaps whose ≥80% is one f64 run. The bar is stated, and the detail names the raw gap sizes so a reader can recompute with another bar. It is not a claim that the allocation's first/last bytes are coordinates.
- **The grid boundary is two-sided.** Start = the end of the run that begins at the content start (prefix) or at the payload start (surface); end = the frame end minus a measured 152/154-byte tail. Zero padding in a tail cannot extend the count. A run without a tail (the prefix, or a merged allocation) is reported as found, and its `ok` flag says whether it validated.
- **What "validated net" means.** Rectangular (spread ≤ 1% of the axis span), model-scale (|coordinate| ≤ 100 m), monotone stations, finite values. The 36×21 anchor net passes all four; the anchor-2 prefix run passes none of the structural ones and is reported as merged rather than fitted.
- **What is not claimed.** No degree, knot vector, weight or surface evaluation is claimed. No semantic meaning is assigned to classes 0x05/0x06/0x18/0x20/0x23/0x25/0x27/0x5b/0x5c/0x5d/0x5e/0x64. The E5 dialect is not framed. The 0.2 MB difference from the brief's "~11.17 MB" is not resolved.
