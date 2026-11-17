# Evidence: CGM exact-model container decode — identity, object dictionary, NURBS payload ceiling (Ticket #57, BR5, Spec G #47)

**Date**: 2026-11-17
**Status**: COMPLETE (structural decode + NURBS ceiling; record-stream framing parked)
**Target Ticket**: Ticket #57 (`BR5: CGM exact model & freeform NURBS stream parser`)
**Parent Spec**: Spec G #47 (Phase 7, B-rep / L3 fitness)
**Method**: Byte-level RE over the L2-pass population (1,089 files), `scripts/triage/decode_brep_cgm_nurbs.py` + `src/catpart/brep/cgm_nurbs.py`; worked examples byte-verified on `07a57767` (R21, 41,491 B), `1d4214e5` (R19, 230,423 B), `17930bab` (R20, 375,670,078 B), `13bb5c0c` (R21, 190,164,863 B).

---

## 1. Executive Summary

BR5 resolves its four constructs as follows (outcome table; every figure traces to [`data/br5-cgm-nurbs-claims.csv`](data/br5-cgm-nurbs-claims.csv)):

| Construct | Outcome | Corpus rate (L2-pass) |
| :--- | :--- | :--- |
| `TOP-01` Solid/Body | **Decoded (structural carrier)** | 1,089/1,089 = 1.000 |
| `TOP-02` Lump | **Open (parked)** — carrier-only | 0 discriminating rows |
| `CRV-06` NURBS/BSpline Curve | **Open (parked)** — payload framing | 0.000 content signatures |
| `SRF-08` NURBS/BSpline Surface | **Open (parked)** — payload framing | 0.000 content signatures |
| `CONT_CGMGEOM` (carrier, BR1 vocabulary) | **Decoded**: identity + object dictionary | 1,089/1,089 identity; 1,082/1,089 dictionaries |

Two results matter beyond the table:

1. **The CGMGeom block region is the CGM object dictionary, not the geometry payload.** It decodes as a property preamble (identity record) plus object id-run records; corpus-wide it carries **zero** NURBS payload signatures (BR5-03a/b: 0/1,089).
2. **Detector-honesty correction to BR1**: the census labels `GEOM_CURV_NURBS`/`GEOM_SURF_NURBS` from `cgm_present` alone (`scripts/triage/census_brep_constructs.py:383-384` — every CGMGeom-carrying file gets both NURBS labels, the source of the frozen vocabulary's 100% rates). The content-based detector measures **0.000** (BR5-03c). The census's 100% is a carrier-presence label; the content rate is the honest number until a payload decode lands.

## 2. The CGM container identity record (BR5-01, decoded)

Byte layout of the `CGMGeom` block region's preamble (worked example `07a57767`, block at 15860 (0x3df4); offsets block-relative, both bases):

- **Writer id** `FINJPL  ` (8 B ASCII, space-padded) at block-relative `+0x6a (106d)` — observed `+0x69 (105d)`/`+0x6a (106d)` across the sample (varies ±1 with the preceding `9f 36 08` frame bytes). Rate: 1,089/1,089 = 1.000 (BR5-01b).
- **Identity name fields** (UTF-16LE): `CATStorageProperty`, then the container name `Cont_<hex>` (e.g. `07a57767`: `Cont_4ab1dbcf_2dac_5f11b2db_42be` at `+0x150 (336d)`). The byte unit preceding `Cont_` varies (`42` 'B', `34` '4', `32` '2') — field structure (type byte), not name content. Rate: 1,089/1,089 = 1.000 (BR5-01c).
- **Vendor footer**: `DASSAULT-SYSTEMES` + `CATIA` + a release token matching `[0-3][0-9][0-9]{4}[A-Z]` (worked example: `041803P`). Rate: 1,089/1,089 = 1.000 (BR5-01d).
- **Full identity** (all three elements): 1,089/1,089 = 1.000 (BR5-01a), on every sampled release bucket (R19 482, R20 147, R21 269, unk 35 — all 1.000).

**Detector honesty**: the identity parser extracts elements by content (no structural length fields trusted); it does NOT validate the GUID slot semantics, does not join the `Cont_` name to a tail-catalog region (B4 recorded that join fails 0/19), and does not discriminate which `Cont_*` naming variant maps to which sub-container role.

## 3. The object dictionary (BR5-02, decoded)

After the preamble, the CGMGeom region is a record stream of three classes:

1. **Object id-run records** (decoded): `[u32le marker 0x0004000k]` (bytes `k 00 04 00`, k = 2..15) + `[u32le x][u8 flag]` + count + `count` u32le ids + `00 00` terminator. Two count-width forms, both byte-verified:
   - u32le count (R20/R21 sample; e.g. `07a57767` at region `+0x6e (110d)`: `02 00 04 00 | 09 00 00 00 | 00 | 05 00 00 00 | ids 3,4,5,6,7 | 00 00`);
   - u16le count (R19 sample; `1d4214e5` at abs `0x2ba82 (179074d)`: `09 00 04 00 | 09 00 00 00 | 00 | 05 00 | ids 3,4,5,6,7 | 00 00`). The u16 fallback applies only when the u32 count cannot describe any record in the remaining span (the shifted-parse negative fixture pins this edge).
   The largest run: `17930bab` marker-5 record with count = 106,912 sequential ids from 0x1f (count field `60 a1 01 00` = 0x1a160). Validation: terminator `00 00`, ids < 2^28.
2. **Marker-1 offset records** (counted, not decoded): `01 00 04 00 <u32le x> 00 00 02 00 <u32le b> <u32le c> 00 <4-byte guid> <u16le d>` — the identity/offset shape observed interleaved with id-runs; a second tail-region shape (`01 00 04 00 <off> ... 03 00 04 00 ...` per-object entries) exists and is parked. Corpus total: 3,100,590 marker-1 records (BR5-02c).
3. **`XX-0` version-tag reference records**: `[u16le ctr][u32le off]"12-0"/"22-0"/"23-0"..."` cycles — 70,148 tags on 9/1,089 files = 0.0083 (BR5-05), consistent with B4's GE-V7 content-dependence claim; the large-dictionary files (`13bb5c0c`: 8,499 tags) carry the dense reference cycles.

**Rates**: 1,082/1,089 files carry ≥1 validated id-run = 0.9936 (BR5-02a; R19 0.9979, R20 0.9864, R21 0.9851, unk 1.000). Total decoded objects: 5,076,186 (BR5-02b); single-file maximum 872,438 (`17930bab`, the dental mold). Corpus marker-1 offset records: 3,100,590 (BR5-02c). The 7 files without validated runs carry dictionary structures whose record shapes reject all validated forms (the marker-8 flag-1 shape with mid-list `00 00` anomalies — parked, see §6).

**Detector honesty**: the id-run decode does NOT interpret `x`/`flag`/marker-k semantics (candidate: owner object / grouping), does not decode the marker-1 offset shapes, and does not join dictionary objects to the record-stream bulk (the `x` fields look like stream offsets — unverified, not claimed).

## 4. TOP-01 Solid/Body — decoded at the structural carrier (BR5-04)

The census's TOPO_BODY signature ("`CATSeeBodyCont` block & store root") decodes with the committed locator law (`catpart.geometry.store.locate_store`, the exporter's probe order `CATStdCont` → `CATXDocLinkCont` → `CATSeeBodyCont` → other-container):

- `CATSeeBodyCont` block present: 1,089/1,089 = 1.000 (BR5-04a).
- Nested store root located: 1,089/1,089 = 1.000 (BR5-04b) — `stdcont` is the mass family; the worked example `01f2a48c` located through `xdoclink`.
- CGM side: the identity record of §2 anchors the exact-model container on every part.

**Detector honesty**: this is a structural-carrier decode — it proves container/root structure, not body topology semantics. The body/lump *record* semantics (what makes a CGM object a solid body vs a lump) live in the record-stream bulk and are not decoded; nothing here discriminates body count, lump boundaries, or orientation.

## 5. TOP-02 Lump — open (parked)

No committed detector discriminates lump records. The census classifies `TOPO_LUMP` with the same trigger as `TOPO_BODY` (store root or CGM presence) — it cannot separate the two, and BR5's dictionary decode does not reach object-record semantics. Ceiling arithmetic: the lump boundary records (per the census signature, "lump boundary records in store & CGM") must be object-level records in the CGM stream (bulk territory) and/or store structures outside the decoded pool/facet grammar; with the record framing parked (§6) the lump record class cannot be isolated this ticket. Rate rows: BR5-06a = 0.000 (no discriminating rows exist). The re-entry belongs to a follow-up with the record-stream framing.

## 6. CRV-06 / SRF-08 NURBS — open (parked) with ceiling arithmetic

**What is measured (the ceiling):**

- The CGMGeom dictionary regions carry **zero** NURBS payload signatures corpus-wide: knot-array signature 0/1,089 (BR5-03a), in-region rational-weight signature 0/1,089 (BR5-03b), on every release bucket. The dictionary is pure structure.
- A 96 MB window of the `17930bab` bulk (the record-stream territory before the CGM block) carries **zero** knot/weight signatures, and the whole-file weight scan found none. The exact-model record stream does not store knots/weights as plain little-endian f64 at any even byte phase (the scan walks all four phases; odd-start arrays are a named residual limitation).
- No compression signature either: zlib magic byte-pairs in the `17930bab` bulk appear at chance rates (each of `78 01`/`78 9c`/`78 da`/`78 5e` ≈ 33-35k occurrences over 337 MB ≈ the 4/65536 random expectation ≈ 20.6k; one attempted decompress failed with `incorrect data check`). The stream's encoding is neither plain f64 nor zlib — it is record-structured with an open encoding (B4's 7.5 bits/byte density observation stands).
- The `b2 03` record family (B4's observation) is confirmed in the bulk with f64 coordinate payloads in ±-symmetric pairs (e.g. `13bb5c0c` abs 0xb6480 (745,088d): `19 2d 44 54 fb 21 19 40` = +6.286 and `... 29 40` = +13.286 axis pairs) — but its framing resisted tiling under all tested length-field hypotheses (the ~20-minute park rule).

**What is parked (the ambiguity, named):** the record-stream framing of the unnamed bulk. Without it, the NURBS record classes (curve/surface, degree, knots, control points, weights) cannot be located — so CRV-06/SRF-08 stay open with the ceiling above, not documented-negatives of absence: freeform parts (the dental mold's ~872k dictionary objects) must carry surface definitions somewhere in that stream.

**Detector honesty (the content-based detector, `cgm_nurbs.nurbs_signatures`)**: a knot-array signature = ≥ 8 non-decreasing finite f64 in [0, 1e7) with ≥ 3 distinct values, ≥ 1 repeat, chain-fraction < 0.75 (u32-alias guard) and the (0, 1e-8) denormal band excluded (second alias guard); a weight signature = ≥ 4 consecutive exact f64 1.0. What it does NOT discriminate: it does not prove a flagged array belongs to a NURBS record (no record framing), does not distinguish rational from non-rational splines (non-rational splines store no weight array — a zero weight rate is not evidence of zero splines), does not distinguish curve knots from surface knots, and its value floor (1e-8) assumes normalized parameter ranges. The synthetic negative fixtures (`tests/test_brep_cgm_nurbs.py`): u32-alias array (chain guard), denormal-aliased index array (band cut), strictly-increasing array (no multiplicity), transform-style 1.0 pair (weight threshold), and the corpus-shaped no-signature dictionary.

**Census coupling (detector honesty correction, to be re-entered by BR1's owner or a follow-up)**: `brep-census-files.csv`'s `construct_classes` labels `GEOM_SURF_NURBS`/`GEOM_CURV_NURBS` on every CGMGeom-carrying file (census script lines 383-384), producing the frozen vocabulary's 100% rates. The content-based rate is 0.000 (BR5-03c). The 100% rows measure carrier presence; they do not measure NURBS content. Not re-implemented here (census file is outside BR5's ownership).

**Sibling couplings — state only, not advanced:**
- BR2's parked composite-index-space normals (19,509/54,265 out-of-pool): BR5's dictionary decode provides no composite index space; not advanced.
- BR4's parked 125 composite stores / CGM tab-cyl discrimination / revolution scope / torus parameters on CGM construction records: the construction records live in the parked record stream; not advanced.
- BR3's parked CRV-04/05 conic type on a CGMGeom cross-check of the `33 38` 2-B payload trailer: the `33 38` records are nested-store (CATStdCont) territory; BR5's CGM decode does not reach them; not advanced.

## 7. Reproduction

```bash
export LD_LIBRARY_PATH=/usr/lib:${LD_LIBRARY_PATH:-}
.venv/bin/python -I scripts/triage/decode_brep_cgm_nurbs.py \
  --corpus-root /home/alan/Documents/Repos/catpart-parser
```

Outputs `docs/evidence/data/br5-cgm-nurbs-claims.csv` (58 rows: per-release + corpus-wide). Tests: `.venv/bin/python -m pytest tests/test_brep_cgm_nurbs.py -q` (22 passed).
