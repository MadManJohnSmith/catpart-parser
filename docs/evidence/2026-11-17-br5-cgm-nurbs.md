# Evidence: CGM exact-model container decode — identity, object dictionary, NURBS payload ceiling (Ticket #57, BR5, Spec G #47)

**Date**: 2026-11-17 (review corrections 2026-11-18)
**Status**: COMPLETE (structural decode + numeric NURBS ceiling; record-stream framing not decoded)
**Target Ticket**: Ticket #57 (`BR5: CGM exact model & freeform NURBS stream parser`)
**Parent Spec**: Spec G #47 (Phase 7, B-rep / L3 fitness)
**Method**: Byte-level RE over the L2-pass population (1,089 files), `scripts/triage/decode_brep_cgm_nurbs.py` + `src/catpart/brep/cgm_nurbs.py`; worked examples byte-verified on `07a57767` (R21, 41,491 B), `1d4214e5` (R19, 230,423 B), `8d34ab85` (R21, 42,269 B), `17930bab` (R20, 375,670,078 B). Every figure below is a row of [`data/br5-cgm-nurbs-claims.csv`](data/br5-cgm-nurbs-claims.csv) or arithmetic on row fields; each row carries a `label` (fact / inference / unknown).

---

## 1. Executive Summary

BR5 resolves its four constructs in the ticket's two states only — decoded, or documented negative with a numeric ceiling. There is no third "open/parked" row:

| Construct | Outcome | Corpus measurement |
| :--- | :--- | :--- |
| `TOP-01` Solid/Body | **Decoded (structural carrier)** | 1,089/1,089 (BR5-04a/b) |
| `TOP-02` Lump | **Documented negative (ceiling only)** | 0 record classes isolated (BR5-06a, observations=0); ceiling BR5-06b |
| `CRV-06` NURBS/BSpline Curve | **Documented negative (ceiling only)** | 0/1,089 content signatures (BR5-03a/b); ceiling BR5-06d |
| `SRF-08` NURBS/BSpline Surface | **Documented negative (ceiling only)** | 0/1,089 content signatures (BR5-03a/b); ceiling BR5-06d |
| `CONT_CGMGEOM` (carrier, BR1 vocabulary) | **Decoded**: identity + object dictionary | 1,089/1,089 identity (BR5-01a); 1,089/1,089 dictionaries (BR5-02a); 8,998,657 id references (BR5-02b) |

Two results matter beyond the table:

1. **The CGMGeom region is the CGM object dictionary, not the geometry payload.** It decodes as a property preamble (identity record) plus object id-run records; corpus-wide the decoded region (151,999,604 B) carries **zero** NURBS payload signatures (BR5-03a/b: 0/1,089) while validated id-run records frame 50,486,667 B (0.3321, BR5-02d).
2. **Detector-honesty correction to BR1**: the census labels `GEOM_CURV_NURBS`/`GEOM_SURF_NURBS` from `cgm_present` alone (`scripts/triage/census_brep_constructs.py:383-384` — every CGMGeom-carrying file gets both NURBS labels, the source of the frozen vocabulary's 100% rates). The content-based detector measures **0.000** (BR5-03c). The census's 100% is a carrier-presence label; the content rate is the honest number.

**Reading the ceiling rows.** Rows with a `ceiling:` prefix carry byte arithmetic in `detail`; their `observations`/`passes` count the population files the ceiling is defined on (1,089), not detections. Rows with `observations=0` are the no-detector rows: no rate exists, so the `rate` field is empty. Rows that carry counts or anchors rather than a per-file rate (BR5-02b, 02c, 03d, 07d, 07e, 08) leave `observations`/`passes`/`rate` empty and state `metric=none` (or `policy=`) in `detail` — a blank means "not a rate", never "zero". Nothing in this note is a third state: a construct either has a decoded model or a measured ceiling on what was not decoded.

## 2. The CGM container identity record (BR5-01, decoded)

Byte layout of the `CGMGeom` block region's preamble (worked example `07a57767`, block at 15860 (0x3df4); offsets block-relative, both bases):

- **Writer id** `FINJPL  ` (8 B ASCII, space-padded) at `+0x6a (106d)`: 1,089/1,089 files, value 106 on every one (BR5-01b). (fact)
- **Identity name fields** (UTF-16LE): `CATStorageProperty`, then the container name `Cont_<hex>` (e.g. `07a57767`: `Cont_4ab1dbcf_2dac_5f11b2db_42be`) at `+0xc3 (195d)` on 1,081/1,089 files. The other eight sit at block-relative 3055, 4042, 5255, 9758, 11431, 14781, 15749 and 19630 (BR5-01c). The u16le unit immediately before `Cont_` is `2 * len(name) + 2` on 1,089/1,089 — the UTF-16 byte length plus its 2-byte terminator (`0x42` for the 32-character `07a57767` name), not a type byte. (fact)
- **Vendor footer**: `DASSAULT-SYSTEMES` + `CATIA` + a 7-byte token matching `[0-3][0-9][0-9]{4}[A-Z]`; the observed token is `041803P` on 1,089/1,089 (BR5-01d). Because it is constant it is a writer build stamp, not a release discriminator — the manifest's `detected_version` is. The footer's block-relative offset is content-dependent, not a layout constant: the most frequent offset is 22,244 B on 24 of 1,089 files, and the worked example `07a57767` has it at `+1374 (0x55e)` with `CATIA` at `+1395` (BR5-01d histogram; BR5-08 anchor row). `+392` holds `00 23 00 00` on `07a57767` and is a fixture artefact, not a footer offset (§9 A2). (fact + inference)
- **Full identity** (writer + name + footer): 1,089/1,089 = 1.000 (BR5-01a), on every release bucket (R15 11, R16 59, R17 40, R18 14, R19 482, R20 147, R21 269, R23 13, R24 14, R25 1, R26 2, R28 1, R32 1, unk 35 — all 1.0).

**Detector honesty**: the identity parser extracts every element by content (no structural length fields trusted), which is also why the eight non-195 names are found rather than missed. It does NOT validate the GUID slot semantics, does NOT join the `Cont_` name to a tail-catalog region (B4 recorded that join fails 0/19), and does NOT discriminate which `Cont_*` naming variant maps to which sub-container role. (unknown)

## 3. The object dictionary (BR5-02, decoded)

After the preamble, the CGMGeom region is a record stream. The parse is payload- and terminator-discriminated, not marker-discriminated: **every** `k 00 04 00` candidate (k = 0..15 observed) is parsed as an id-run first, and only a k=1 candidate whose id-list parse fails is counted as a marker-1 record. The marker byte is not treated as a type. (fact)

1. **Object id-run records** (decoded): `[u32le 0x0004000k][u32le x][u8 flag][count][count u32le ids][00 00]`. Two count widths exist and both validate by their closing terminator:
   - u32le count, e.g. `07a57767` at region `+0x120 (288d)`: `02 00 04 00 | 09 00 00 00 | 00 | 05 00 00 00 | ids 3,4,5,6,7 | 00 00`; `8d34ab85` at `+0x120` carries the identical record with marker `01`.
   - u16le count, e.g. `1d4214e5` at abs `0x2ba84 (178,820d)`, region `+274`: `09 00 04 00 | 09 00 00 00 | 00 | 05 00 | ids 3,4,5,6,7 | 00 00`. This is a per-record width variant, present in 1,089/1,089 files on every release bucket (BR5-02f) — not an R19-only form; 1,050,878 of the 1,106,253 id-run records are u16 (0.9499, BR5-02f `u16_records`). (fact)
   The u16 read is attempted only when the u32 count cannot describe a record in the remaining span. That gate blocks the shifted re-read (a u32 record whose terminator fails must not validate as u16; pinned by the shifted-parse negative fixture) and costs recall: wherever the u32 re-read still fits the span — from 786,467 B remaining for the smallest shape (count 5, first id 3) — the u16 form is unreachable. 23 CGM regions sit at or above that threshold (124,411,157 B); the measured cost is 5,833 id refs: the ungated local width policy decodes 9,004,490 against the shipped 8,998,657 (0.065%) (BR5-02e). (fact for the measurement; the gate is a deliberate trade-off)
   - **Largest run**: `17930bab`, marker `05`, count field `60 a1 01 00` = 0x1a160 = **106,848** sequential ids from 31, last 106,878 (BR5-02b detail; the byte reading is pinned in `tests/test_brep_cgm_nurbs.py`). The dental mold's 1,552,108 id references are the corpus maximum (BR5-02b).
2. **Marker-1 records that fail the id-list parse** (counted, not decoded): 2,071,639 (BR5-02c). Their field layout is **not established**: the earlier "offset record" label was marker-based, so it is withdrawn rather than reasserted. (unknown)
3. **`XX-0` version-tag reference records**: 70,148 tags on 9/1,089 files = 0.0083 (BR5-05), consistent with B4's GE-V7 content-dependence claim. The dense file is `50cd280f` with 68,707 tags (0.9795 of the total); the rest are `8269ca4e` 992, `ba6ae0de` 132, `f393cea8` 99, `e8c4fe20` 77, `34aebc45` 45, `6489ed16` 36, `0a64c44c` 30, `5de8b8fc` 30. `13bb5c0c` is **out of population** (L2 fail, not-manifold), so the earlier "8,499 tags on `13bb5c0c`" attribution was wrong on both counts and is withdrawn. (fact)

**Rates**: 1,089/1,089 files carry ≥1 validated id-run = 1.0 (BR5-02a; every release bucket 1.0), after the k-dispatch fix — the seven files that previously failed were the k=0/k=1 record shapes. 1,106,253 id-run records, 8,998,657 **id references** (positions in id lists, repeats included — not distinct object count; the per-object records list e.g. `(self, 28, 2)`, so list lengths repeat ids) (BR5-02b, an aggregate row with no per-file rate). The committed draft's total was the same sum under the k=2..15 dispatch, so the increase is added id-list positions from the k=0/k=1 records, not a change of metric. (fact)

**Detector honesty**: the id-run decode does NOT interpret `x`/`flag`/marker-k semantics (candidate: owner object / grouping), does not decode the marker-1 shapes, and does not join dictionary ids to the record-stream bulk (the `x` fields look like stream offsets — unverified, not claimed). (unknown)

## 4. TOP-01 Solid/Body — decoded at the structural carrier (BR5-04)

The census's TOPO_BODY signature ("`CATSeeBodyCont` block & store root") decodes with the committed locator law (`catpart.geometry.store.locate_store`, the exporter's probe order `CATStdCont` → `CATXDocLinkCont` → `CATSeeBodyCont` → other-container):

- `CATSeeBodyCont` block present: 1,089/1,089 = 1.000 (BR5-04a).
- Nested store root located: 1,089/1,089 = 1.000 (BR5-04b) — `stdcont` is the mass family; the worked example `01f2a48c` located through `xdoclink`.
- CGM side: the identity record of §2 anchors the exact-model container on every part.

**Detector honesty**: this is a structural-carrier decode — it proves container/root structure, not body topology semantics. The body/lump *record* semantics (what makes a CGM object a solid body vs a lump) live in the record-stream bulk and are not decoded; nothing here discriminates body count, lump boundaries, or orientation. (unknown)

## 5. TOP-02 Lump — documented negative (ceiling only)

No committed detector isolates lump records. The census emits no `TOPO_LUMP` label at all; the nearest label, `TOPO_BODY`, cannot separate bodies from lumps (its trigger is `has_store or cgm_present`, `scripts/triage/census_brep_constructs.py:358-359`), and BR5's dictionary decode does not reach object-record semantics. BR5-06a records that fact with `observations=0` — no rate exists, because no detector exists. (fact about the census; unknown about lumps)

**Ceiling arithmetic, per scope** (BR5-06b, BR5-02d, BR5-07a). The two spans the ceiling covers have different scopes, and the CSV row says so (`cgm_scope=corpus`, `bulk_scope=17930babf0fd01a8`):

- **CGM dictionary region — corpus, 1,089 files**: framed 50,486,667 of 151,999,604 B = 0.3321; the unframed 101,512,937 B (0.6679) is the corpus-wide CGM-side ceiling.
- **Record-stream bulk — one file, `17930bab`**: the measured window is 100,663,296 of 337,242,057 B = 0.2985 (BR5-07a); the remaining 236,578,761 B of that file's bulk is unmeasured (BR5-06b `bulk_uncovered_bytes`).
- Id references located: 8,998,657 (BR5-02b, aggregate); `XX-0` tags located: 70,148 on 9 files (BR5-05).
- Lump record classes isolated: **0** (BR5-06b).

**What the ceiling means** (inference): on `17930bab` the uncovered space is its bulk outside the window, 236,578,761 B, plus the corpus-wide unframed CGM bytes; for the other 1,088 files only their CGM region is measured and their record-stream bulk is unmeasured. Nothing in this measurement says lumps are absent. The re-entry is the record-stream framing (§6), not a new TOP-02 probe.

## 6. CRV-06 / SRF-08 NURBS — documented negative (ceiling only)

**Content signatures (BR5-03a/b/c):** 0/1,089 CGMGeom regions carry a knot-array signature, 0/1,089 carry a weight-1.0 signature — on every release bucket — and the content rate against BR1's carrier label is 0.000. (fact)

**The bulk measurement (BR5-07).** The measured bulk is the `CATPrtCont` region immediately preceding the CGMGeom block of `17930bab` (the dental mold): abs `[56,742, 337,298,799)` = **337,242,057 B** (BR5-07a). The measured window is its first 96 MiB = **100,663,296 B = 0.2985 of the region**; every window figure below is scoped to that span. (fact)

- **Knot/weight signatures**: 0 knot runs and 0 weight runs in the 100,663,296 B window (BR5-07b/c); 0 knot runs and 0 weight runs in the whole 375,670,078 B file (BR5-07g). The record stream therefore stores no knots or weights as plain little-endian f64 at an even byte phase in that span; odd-start arrays and non-normalized parameter values stay outside the detector (named limitations). (fact + scope)
- **Guard near misses (BR5-03d, over the 151,999,604 B of CGM region, one count per physical array)**: shipped 0; dropping the chain guard 0; odd byte phases 0; dropping the denormal/value floor 79,583 runs (193,412 counting the four even phases separately, i.e. one array up to four times); the distinct≥2 edge 0 on its own, 560 jointly with the chain guard dropped; weight runs ≥ 2 0. The two live edges are the value floor and the distinct-2/chain pair; the chain guard alone, the odd phases and the weight threshold add nothing at the zero baseline. The 79,583 floor-relaxed runs are denormal-band integer-array aliases — the guard doing its job, not missed knot vectors (fact for the counts; inference for the alias reading).
- **zlib magic pairs**: in the 96 MiB window `78 01`/`78 9c`/`78 da`/`78 5e` occur 1,423/514/454/1,467 times against 1,536.0 expected per pattern — 0.93/0.33/0.30/0.96× chance, i.e. no excess at all (BR5-07d; `excess_bar=2.0x`, 0 of 4 patterns at or above it — an excess bar, not a detection rate). Over the full 337,242,057 B region the same four occur 35,208/33,252/33,175/35,428 against 5,145.9 expected — 6.84/6.46/6.45/6.88× chance, 4 of 4 above the bar (BR5-07e). The excess is real and localized outside the first 96 MiB; the earlier draft's framing (per-pattern counts against the four-pattern *sum* expectation, "chance rates") was an arithmetic error — per-pattern chance is 5,145.9, and each pair is ~6.6× that. (fact)
- **No zlib stream is proven**: 0 of **137,063** magic positions yield any output from a fresh `zlib.decompressobj()` over the first 8 KiB at the position (BR5-07f). Whatever the 6.6× excess is, it is not a zlib stream starting at any of those positions. Trial set limitation: only the four 32 KiB-window CMF/FLG pairs (`78 xx`) are trialled; smaller-window zlib streams are not covered. (fact for the trials; unknown for the excess)
- **The `b2 03` record family** (B4's observation) is present in the bulk, but its field framing is not decoded. Byte-verified example, `13bb5c0c` abs `0xb6470 (746,608d)`: `1b 2d 44 54 fb 21 19 40` = 6.283185307179589 and `19 2d 44 54 fb 21 29 40` = 12.566370614359174 (a near-2π/4π pair: the stored f64s are not exactly 2π/4π — 2π packs to `18 2d 44 54 fb 21 19 40`); the next `b2 03` record marker starts at abs `0xb6488 (746,632d)`. No record layout is claimed. (fact for the bytes; unknown for the structure)

**What is not decoded (the ambiguity, named):** the record-stream framing of the pre-CGM bulk. Without it the NURBS record classes (curve/surface, degree, knots, control points, weights) cannot be located, so CRV-06/SRF-08 carry a measured ceiling rather than an absence claim: freeform parts (the dental mold's 1,552,108 id references) must carry surface definitions somewhere in that stream. (unknown)

**Detector honesty (content-based detector, `cgm_nurbs.nurbs_signatures`)**: a knot-array signature = ≥ 8 non-decreasing finite f64 in [0, 1e7) with ≥ 3 distinct values, ≥ 1 repeat, chain-fraction < 0.75 (u32-alias guard) and the (0, 1e-8) denormal band excluded (second alias guard); a weight signature = ≥ 4 consecutive exact f64 1.0. What it does NOT discriminate: it does not prove a flagged array belongs to a NURBS record (no record framing), does not distinguish rational from non-rational splines (non-rational splines store no weight array — a zero weight rate is not evidence of zero splines), does not distinguish curve knots from surface knots, and its value floor (1e-8) assumes normalized parameter ranges. `knot_guard_sweep` (BR5-03d) turns that honesty line into counts and shows which guards carry the zero; the corpus's answer is the value floor plus the distinct-2/chain pair. The synthetic negative fixtures (`tests/test_brep_cgm_nurbs.py`): u32-alias array (chain guard), denormal-aliased index array (band cut), strictly-increasing array (no multiplicity), transform-style 1.0 pair (weight threshold), the corpus-shaped no-signature dictionary, plus one guard-sweep fixture per live edge.

**Ceiling rows**: BR5-06c records that no record-class detector exists (`observations=0`); BR5-06d carries the numbers: 0 knot-signature files and 0 weight-signature files over 151,999,604 B of CGM region, 0 knot/weight runs in the 100,663,296 B window, 0 knot/weight runs over the whole file. Its `bulk_scope` is `17930bab` alone (§5).

**Census coupling (detector honesty correction, to be re-entered by BR1's owner or a follow-up)**: `brep-census-files.csv`'s `construct_classes` labels `GEOM_SURF_NURBS`/`GEOM_CURV_NURBS` on every CGMGeom-carrying file (census script lines 383-384), producing the frozen vocabulary's 100% rates. The content-based rate is 0.000 (BR5-03c). The 100% rows measure carrier presence; they do not measure NURBS content. Not re-implemented here (census file is outside BR5's ownership).

**Sibling couplings — state only, not advanced:**
- BR2's parked composite-index-space normals: BR5's dictionary decode provides no composite index space; not advanced.
- BR4's parked composite stores / CGM tab-cyl discrimination / revolution scope / torus parameters on CGM construction records: the construction records live in the un-framed record stream; not advanced.
- BR3's parked CRV-04/05 conic type on a CGMGeom cross-check of the `33 38` 2-B payload trailer: the `33 38` records are nested-store (CATStdCont) territory; BR5's CGM decode does not reach them; not advanced.

## 7. Reproduction

```bash
export LD_LIBRARY_PATH=/usr/lib:${LD_LIBRARY_PATH:-}
.venv/bin/python -I scripts/triage/decode_brep_cgm_nurbs.py \
  --corpus-root /home/alan/Documents/Repos/catpart-parser
```

Outputs `docs/evidence/data/br5-cgm-nurbs-claims.csv` (99 rows: per-release + corpus-wide rate rows, numeric ceiling rows, the BR5-07 bulk rows, the BR5-03d guard sweep and the BR5-08 anchor row). The bulk window defaults to `17930bab` and 96 MiB (`--bulk-sha16`, `--bulk-mib`); the corpus binaries are gitignored, so the run is read-only against the main checkout. Tests: `.venv/bin/python -m pytest tests/test_brep_cgm_nurbs.py -q` (30 passed).

## 8. Review corrections (2026-11-18)

The independent review returned FIX with nine blocking findings; this section records each correction. Byte evidence is given for the two findings where the previous text was not merely stale but wrong.

| # | Finding | Change |
| :--- | :--- | :--- |
| B1 | TOP-02/CRV-06/SRF-08 used a third "open (parked)" state and §5 had no numbers | Rows relabelled **Documented negative (ceiling only)**; numeric ceiling rows added (BR5-02d, 02e, 06b, 06d, 07a-g) and cited in §5/§6; no-detector rows now use `observations=0` instead of a 0/1089 rate |
| B2 | k-dispatch restricted id-runs to k=2..15 and treated every `01 00 04 00` as an offset record | `scan_dictionary` parses the id-list shape first for every k in 0..15 and only counts a k=1 record as marker-1 on parse failure; CSV regenerated (1,089/1,089 files, 8,998,657 refs); k=0 and k=1 unit fixtures added |
| B3 | Largest run prose said 106,912 while the bytes say otherwise | Count field `60 a1 01 00` = 0x1a160 = **106,848** (ids 31..106,878) in prose, code comment, CSV detail and unit test |
| B4 | "13bb5c0c: 8,499 tags" was wrong and out of population | Tag attribution rewritten: `50cd280f` 68,707 of 70,148 (0.9795), the nine-file list in BR5-05; `13bb5c0c` labelled out of population (L2 fail, not-manifold) and the attribution withdrawn |
| B5 | The `0xb6480` byte citation was fabricated (wrong offset, wrong bytes, a 2π pattern that occurs nowhere) | Re-derived: 2π/4π pair at abs `0xb6470 (746,608d)`, `b2 03` marker at `0xb6488 (746,632d)`; the quoted bytes are the file's actual bytes |
| B6 | zlib counts were compared to the four-pattern sum expectation | Per-pattern chance (5,145.9 over 337,242,057 B) and the measured ~6.6× excess stated; the 96 MiB window (0.30-0.96×) is reported separately |
| B7 | Bulk/NURBS figures had no committed artifact and the script only scanned the CGM region | `--bulk-sha16`/`--bulk-mib` bulk-window mode added (span, zlib counts window+region, decompress trials, knot/weight scan, whole-file weight scan); BR5-07a-g rows; the unverifiable single-decompress anecdote replaced by 0/137,063 trials |
| B8 | Four offset citations were wrong (`±1` writer, `+0x150` name, `+0x6e` first run, `0x2ba82` u16 marker) | Writer `+0x6a (106d)` on 1,089/1,089; name `+0xc3 (195d)` on 1,081 with the eight outliers listed; first accepted run `07a57767` region `+0x120 (288d)`; u16 record `1d4214e5` abs `0x2ba84 (178,820d)` region `+274`; identity offsets and the +288 run start pinned by unit assertions |
| B9 | The note claimed a shifted-parse negative fixture that did not exist; u16 was described as an R19 form; the u32 gate's recall hole was unstated | `test_shifted_parse_rejected` added (u32 fits, terminator fails, u16 reading would validate → no run under the default policy, and the local policy's acceptance pinned); u16 described as a per-record variant with a committed file rate (BR5-02f); the gate's recall ceiling quantified in BR5-02e and §3 |

Non-blocking items: dead `_CHUNK_F64` and the stale `KnotRun.aliased` docstring removed; one release-token regex pinned (`[0-3][0-9][0-9]{4}[A-Z]`) with a near-miss negative fixture; the unit before `Cont_` documented as `2*len(name)+2` and asserted; the tautological `vendor_offset` assertion replaced by the literal +392 pin (**WITHDRAWN** — +392 is a fixture artefact, see §9 A2); the CSV gained a `label` column (fact / inference / unknown) and `id_refs` replaces "objects" (the metric counts id-list positions).

## 9. Post-merge audit corrections (2026-11-18)

An independent post-merge audit re-derived every headline and returned FIX with five doc/test/claim findings. Each is corrected at the generator or the fixture, then the CSV is regenerated (a hand-edit of the CSV is overwritten by the next run).

| # | Finding | Change |
| :--- | :--- | :--- |
| A1 | The note and BR5-06a said the census classifies `TOPO_LUMP` with the same trigger as `TOPO_BODY` — a fact that does not exist | `TOPO_LUMP` appears nowhere in `scripts/triage/census_brep_constructs.py` or the frozen vocabulary. BR5-06a now reads: the census emits no `TOPO_LUMP` label at all; the nearest label, `TOPO_BODY`, cannot separate bodies from lumps. §5 updated from the generator's row |
| A2 | The `+392` vendor-footer pin was a fixture artefact, presented as the corpus offset | Measured on `07a57767`: block 15860, vendor at `+1374 (0x55e)`, `CATIA` at `+1395`; `+392` holds `00 23 00 00`. The unit assertion is now fixture-local (`vendor_offset >= 0`), the fixture docstring says fixture-local, BR5-01d carries the corpus histogram and BR5-08 the anchor row; the "+392 pin" correction in §8 is withdrawn |
| A3 | A test comment said the u16 count width was accepted in 648/1,089 files | 1,089/1,089 files; 1,050,878 of 1,106,253 id-run records are u16 (0.9499, BR5-02f). Comment fixed |
| A4 | §5's ceiling sentence mixed a corpus-wide CGM figure with one file's bulk and read as corpus-wide | BR5-06b/06d carry `cgm_scope=corpus`, `bulk_scope=17930babf0fd01a8` and `bulk_uncovered_bytes=236578761`; §5 is written per scope (corpus CGM unframed 101,512,937 B; one file's uncovered bulk 236,578,761 B; the other 1,088 files' bulk unmeasured) |
| A5 | The weight-signature 0/1,089 claim was stated "on every release bucket" but only the all-scope row existed | `emit_rel` for BR5-03b added: 14 per-release rows (13 numbered buckets + `unk`), all 0/denominator |

Non-blocking items in the same pass: the knot detector's near misses are quantified on the CGM regions as BR5-03d (shipped 0; chain guard dropped 0; odd phases 0; value floor dropped 79,583, or 193,412 counting the four even phases separately; distinct≥2 0 alone and 560 jointly with the chain guard dropped; weight run ≥ 2 0), with the two live edges and one honesty line in §6; BR5-03d's `detail` states the counting policy so the 79,583/193,412 and 0/560 pairs are not confusable. BR5-07d/07e no longer carry a self-fulfilling `passes`/`rate` (the old `≥ 2.0×` count inverted the word and was undocumented): the columns are blank, `metric=none`, and `excess_bar=2.0x` names the bar. BR5-02b/02c likewise blank the rate columns and say `metric=none; aggregate totals, not a file rate`. BR5-08 is the worked-example byte-anchor row (`+288`, `+274`/abs `0x2ba84`, `0xb6470`/`0xb6488`, block 15860, `+1374`, `+392`'s four bytes), read back from the corpus at run time. `U16_GATE_SPAN`'s comparison uses `>=`, matching the gate's `s + 13 + 4*count + 2 <= hi`. The whole-file knot scan is now reported (0 runs) instead of being computed and discarded.
