# Evidence: the L2 grind's failure census, classified to root cause (2026-11-10)

Ticket #34 (G6, spec D #28), stage 1 of the grind: classify **all 1,381
dev parts and all 61 held-out parts** of the L2 population into
root-cause classes with byte evidence, and derive the ceiling arithmetic
toward the 80% bar (1,105 passes). Scope discipline: **analysis only** —
no decode implementation, no fitness writes, no publication; the decode
dispatch is a separate, follow-on ticket informed by this table. The
accepted L2 baseline
(`fitness/reports/20261110T172440Z-3ea53d.json`: 76/1,381 = 5.50%; 963
undecoded-variant, 313 missing-geometry-store, 29 malformed-store-header;
held-out 61 undecoded-variant) is the object being explained.

Method: `scripts/triage/classify_l2_grind.py` (committed with this
note) replays the shipped export seam
(`catpart.geometry.export._export_data`, the exact code path the fitness
runner scores, read-only) over the L2 population — manifest
`kind=part`, splits dev + held-out — and audits every failure around
that seam: G1's region taxonomy
(`scripts/triage/decode_nested_store.py`, reused unchanged), the pool
wrapper sub-kind census, the facet-marker census, an analysis-only
refs-beyond measurement on composite bodies (the shipped gate raises
before it there), byte-level anatomy of every tail-validation failure,
and a recovery probe that runs the shipped locate law — and, for
malformed probes, the relaxed tail law — over the `CATXDocLinkCont` and
`CATSeeBodyCont` regions the locator never visits. The replay agrees
with the baseline report on **all 1,442 parts (0 mismatches, 0 audit
errors)**, so every subclass below partitions the baseline's own
classes. Two consecutive full runs produce byte-identical CSVs
(md5-verified). Data: `docs/evidence/data/l2-grind-classification.csv`
(one row per part, 50 byte-evidence fields).

Labels: **fact** = byte-measured here and reproducible from the CSV;
**inference** = interpretation of measured bytes, named as such;
**unknown** = open, carried forward. Byte offsets are absolute file
offsets unless marked origin-relative.

## 1. The census (fact)

| root class | dev | rate | held-out | baseline class it partitions |
|---|---|---|---|---|
| pass | 76 | 0.055 | 0 | pass (76) |
| composite-space | 878 | 0.636 | 61 | undecoded-variant (939 with held-out) |
| refs-beyond-pool | 30 | 0.022 | 0 | undecoded-variant |
| poolless-store | 55 | 0.040 | 0 | undecoded-variant |
| malformed-store-header | 29 | 0.021 | 0 | malformed-store-header |
| missing-store | 313 | 0.227 | 0 | missing-geometry-store |
| total | 1,381 | 1.000 | 61 | 1,442 |

Classification covers 100% of the population with per-part evidence
(acceptance asked >= 99%). Message-level decomposition of the 963+61
undecoded-variant: composite-gate 939, no-pool 55, refs-beyond 30.

## 2. Reconciliation with G1 and the baseline (fact, with one unknown)

- **The populations compose exactly.** G1 scanned 1,377 dev parts
  (manifest `magic_ok=yes`); the fitness L2 population is manifest
  `kind=part` without the magic filter = 1,381. The 4 excluded parts
  (230b0591, 521f08e3, 6cab1344, bafb33e5 — `magic_ok=no`) are all
  **missing-store / no_stdcont** here (region survey: no CATStdCont
  block), so G1's tables need no correction — its scope was 4 parts
  narrower.
- **The 1,068 attempted = G1's 1,068 stores.** The fitness locator
  reaches 1,068 of 1,381 (77.3%): 76 pass + 963 undecoded-variant enter
  the decode, 29 more have a header the tail law rejects. G1 measured
  the same 1,068 as 1,056 header-variant + 12 header-less stores; this
  census reproduces both (CSV `origin_kind`-equivalent columns; the 29
  rejected are all header-variant, section 5).
- **G1's N10 miss taxonomy = the 313, family for family**: 204
  no_stdcont (G1) + 4 magic_ok=no = 208; none_in_region 63;
  next_block_store 34; embedded_doc 8. Sum 313 (fact).
- **What G1 actually measured on presence** (its claims CSV): 1,068 /
  1,173 = **0.910 of CATStdCont-carrying dev parts** carry a store =
  1,068/1,377 = **0.776 of all dev parts**; header variant 1,056/1,173 =
  0.900; per-release among-CATStdCont rates 0.64 (R23, 7/11) - 1.00,
  with the main lines R15-R21 at 0.848 (R17, 39/46) - 0.974 (R20) and
  R19 504/538 = 0.937.
- **The handoff's ~0.82-0.93 presence band: unknown provenance** — no
  single committed number equals it. Closest measured candidates: 0.900
  (N1h header variant), 0.910 (N1 among-stdcont), (1,068+95)/1,377 =
  0.845 (all-dev stores + the CATSeeBodyCont stores G1 counted
  separately), or the 0.848-0.937 spread of the main release lines.
  Inference: the band reads like a per-release or per-denominator range
  of the same measurement; the planning conclusion is invariant across
  all of them — presence among *store-carrying containers* is ~0.9 but
  the *population* denominator carries the 208 no-CATStdCont parts
  (15.1%) plus 105 store-less CATStdCont regions, which is what caps
  the located population at 77.3% and makes the locator lever mandatory
  (#35's planning fact, confirmed below).

## 3. composite-space — 878 dev + 61 held-out (fact; interior structure unknown)

The shipped gate fires on pool-wrapper sub-kinds (`10 24 04 ff ff 00 00
00` + sub-kind): `01 02` edge group and/or `ff ..` trailer opener (G3
F8). Decomposition:

- **Triggers (dev):** edge-group only 516 (58.8%), edge group + opener
  both 322 (36.7%), opener only 40 (4.6%). Held-out: edge-group 32,
  both 29.
- **How the trigger fires — structural, not refs-based (fact):** the
  gate tests the sub-kind bytes only. Under an analysis-only bypass
  (scan_facets on the composite body, exactly G3's method), facet refs
  exceed the pool on **785/878 = 0.894** (F8 measured 793/889 = 0.892
  on its 1,068-store scope — reproduced). So on 93 stores the gate
  fires with refs inside the pool; the composite claim there rests on
  the structure below, not on refs.
- **The `01 02` edge tables (fact):** 838 dev stores carry edge groups;
  681 of them walk `02 02 (u16be)(u16be)` 6-byte records under a count
  byte at +10 (ff escapes to u32le — the pool groups' P1g convention,
  now observed on edge groups too): **154,342 edge records total**, and
  on **651/681** the maximum edge endpoint is >= the pool size —
  independent byte evidence that the edge table indexes a larger vertex
  space. The other 157 edge groups carry different `02 0X` record forms
  (worked byte form `01 02 | 08 | 02 03 00 04 06 ...` on 026d67260073
  at 28,785) — undecoded (unknown).
  - Case 0018baa8 (R19): kinds `0102, 0106, ff24`; pool 164 vertices;
    edge table 70 records, max endpoint 569; facet refs max 569 —
    both the edge space and the facet refs exceed the pool.
  - Case 02ee15440279: `01 02 | ff 92 01 00 00 | 02 02 02 de 02 dd ...`
    — ff-escaped count 402 records, endpoints inside a 1,536 pool.
- **A sub-kind family beyond the gate (fact, new evidence):** across
  the audited stores the non-pool sub-kinds are `0000` (599 store rows
  = 539 composite-space dev + 25 refs-beyond dev + 35 held-out),
  `0001` (59), `0101` (11), `00ff` (11), plus a rare tail (`e700` 6,
  `7500` 4, `ed00` 3, `9c00` 2, `3f01` 2). **None of these sub-kinds
  ever appears on a passing store** (0/76) — they are markers of the
  same undecoded reference space, of which the gate currently knows two
  members. This extends F8's vocabulary claim (dated addition, section
  8).
- **Content variants, labeled (fact):** B4's "float64 store"
  086a4effaab7 (R20, 4.58 MB store) is a member of this class: kinds
  `0106, ff70`, pool 916 vertices, **zero facet records**, opener
  u32le = 67,696 (the trailer-named region's length, the N7d payload —
  G2's C6 reclassification stands; its float64 impression is confined
  to the opener-named region, still undecoded: unknown whether
  compressed or float64).
- **Held-out (fact):** all 61 are this class (refs beyond pool on
  61/61 under analysis) — the composite decode lifts held-out 0 -> up
  to 61, satisfying no-regret trivially.

Inference: "composite decode" (L1) is one decode problem — a reference
space larger than the `01 06` pool, signposted by a family of sub-kind
bytes — not 878 separate variants. Its interior (edge-table forms,
opener-named regions, the `0000`/`0001` groups' content) is the next
dispatch's territory and is left undecoded here.

## 4. refs-beyond-pool — 30 dev (fact)

Every one of the 30 carries a non-standard sub-kind beside its pool:
`0000` (24), `9c00` (2), `7500`, `00ff`, `31ff`, `6200` (1 each);
**none is pool-only**. Pool sizes 4-168; max facet refs 9-27,263; 15/30
are R21. Case 0ae8c3e7 (R21): kinds `0106, 0000`, pool 48, max ref 641,
markers 0x42 x16 + 0x4c x2. Case 531350af (a recovery probe, section
6): pool 6, refs to 255 — the parsed refs are u8-width values in 0..255
(inference: consistent with a wider index space or a ref-width
variant; unknown).

Inference: this class is the composite space falling through the gate's
vocabulary, not a separate "second element source" mystery — G3 open
question 2's "second pool form" is not needed to explain any of the 30.
Lever L3 is therefore the same decode problem as L1 with a wider
sub-kind vocabulary.

## 5. malformed-store-header — 29 dev, all two G1-documented families (fact)

Every rejection happens at the tail validation (`validate_catalog_tail`)
with a valid header (ff x 8 / zeros x 8 / sane dwords / catalog magic
all pass). Byte anatomy:

- **dword8-overshoot, 11 parts** (G1 correction C3's exact family, k =
  5, 9 x2, 13 x5, 14, 28 x2; R16 x8, R17 x2, R20 x1): the header's
  dword8 overshoots the catalog magic by k, and the shipped tail
  `[cb, j+d8n+d12n)` inherits the same overshoot, running k bytes past
  the catalog's `CB__END`, so `tail[-8:] != CB__END` rejects a tail
  that is otherwise valid (C == D, G == dword12 all hold). Case
  278015fe3d3d603d (R16): header j=53,417, d8n=7,379, d12n=2,704,
  cb=60,787, k=9; the true tail ends `... 00 0a 90 CB__END 00` at
  63,491 and the shipped tail ends at 63,500.
- **padded-tail, 18 parts** (G1's padded-tail variant; all `unknown`
  release; cntA 4-11): dword12 = 3,072 (x8) / 4,096 (x10) but the
  catalog's true trailer sits **inside** the tail — `CB__END` followed
  by **1,604-2,034 B of all-zero padding** up to the dword12 length —
  so the tail's last 8 bytes are zeros, not `CB__END`. Case
  00198dd9de8caadf: header j=20,525, d12n=3,072, cb=22,306, `CB__END`
  at 23,336, 2,034 zero bytes follow.
- **G1's `header_invalid` family: 0 corpus hits — confirmed** (the
  shipped locator's stricter tail law, not a new malformed form, is
  what fires).
- **Recoverable? (fact + inference):** both families are located by a
  strictly weaker-but-principled law — read the tail from the catalog
  magic with length dword12 (overshoot), or end the tail at its
  `CB__END` (padded). The post-fix content classes: the 11 overshoot
  bodies are **composite**, the 18 padded bodies are **poolless**
  (zero wrappers). Inference: a locate fix recovers all 29 into the
  attempted pool but **zero of them pass immediately** — 11 need L1,
  18 need the poolless answer. The fix is a cap-raiser, not a
  pass-lever by itself.

The same two families account for **68 more rejections on the recovery
side** (section 6): seebody/xdoc probes that raise malformed under the
shipped law are 52 overshoot + 16 padded, with post-fix content classes
**clean 36, poolless 20, composite 12**.

## 6. missing-store — 313 dev: the mandatory lever, measured (fact)

G1's N10 families + a live recovery probe (the shipped locate law, then
the relaxed tail law, over `CATXDocLinkCont` and `CATSeeBodyCont`
regions — containers the locator never visits):

| family | parts | recovery probe outcome |
|---|---|---|
| no_stdcont (incl. 4 magic_ok=no) | 208 | 29 seebody-located; 67 seebody-malformed (relaxed-law recoverable); 112 no store |
| none_in_region | 63 | 4 seebody-located; 1 xdoclink-malformed; 58 no store |
| next_block_store | 34 | 34 xdoclink-located (shipped-law recoverable) |
| embedded_doc | 8 | no store (outer-style catalogs, N10) |

- **135/313 parts carry a real V5_CFV2 store the current pipeline
  misses** (fact): 67 locate under the shipped law on a non-CATStdCont
  container + 68 more under the relaxed tail law. Content classes
  (fact): composite 70, **clean 36**, poolless 21, refs-beyond 8. The
  36 clean stores locate and pass the exporter's structural gates
  under the relaxed law + container extension (their pools decode and
  every facet ref sits inside the pool; triangle production itself is
  stage-2 work).
  - Case 01f2a48c9151197e (next_block): CATStdCont region 697 B with no
    markers; the store sits in the `CATXDocLinkCont` region [110,357,
    116,641): header d12n=2,690 valid, wrappers `0102, 0106, 0000`
    (composite). Same shape on 0520840350b47894.
  - Case 03efd6080619e549 (no_stdcont): no CATStdCont block at all; the
    `CATSeeBodyCont` region [379,642, 388,637) carries a full store
    (header d12n=2,690, wrappers `0106, 0001`).
  - Case 152159176ca8d58d (no_stdcont): seebody region 291,111 B,
    wrappers `0102, 0106, 0000` — a large composite recovery.
- **178/313 are genuinely store-less for this architecture** (fact):
  112 no_stdcont + 58 none_in_region + 8 embedded_doc with no
  V5_CFV2/CB0001 marker in any CATStdCont/seebody/xdoc region. The
  whole-file V5_CFV2 hit on 174 of them is the **outer header's own
  magic at offset 0** (the outer file header shares `V5_CFV2\0`) — not
  evidence of a missed store. Cases: 009cc605 (region 903 B, empty
  signature); cb3c7762 (region 795,072 B with no marker — large raw
  content, undecoded); 022523b4 (embedded_doc: an outer-style catalog
  at 176,966 inside the CATStdCont region, N10's CAA family); 084841b3
  (no_stdcont with an 8,648 B seebody region carrying no store).
- **G1's 95-store seebody claim, refined (correction, section 8):** G1
  counted `CATSeeBodyCont` regions carrying a nested header store on
  95/1,377 parts (first-seebody-block probe). This census probes every
  seebody block per part: **100 parts** carry V5_CFV2 in some seebody
  region (29+67 no_stdcont + 4 none_in_region), of which 33 locate
  under the shipped law, 67 reject as overshoot/padded (recoverable),
  and 0 are absent. Plus 1 xdoclink-flagged none_in_region part whose
  store rejects (overshoot/padded family). The G1 number was a
  first-block undercount, not a wrong model.
- **Embedded-doc 8 and none_in_region 58: genuinely not stores** (fact
  for the marker absence; inference for "not recoverable by the locate
  law" — their catalogs are outer-style (X0 = 94, `Cont_*` names, G1
  N10) and their regions carry no store markers to relax onto).

**The ceiling answer (fact + arithmetic):** the bar needs >= 66
recoveries without the malformed fix, >= 37 with it (#35's framing and
section 7); measured candidates = **135 >= 66** — the mandatory lever
is *feasible*, but its pass yield depends on the content levers (74 of
the 135 are composite, 36 clean, 21 poolless, 8 refs-beyond).

## 7. The ceiling table and the combination arithmetic (fact + arithmetic)

Dev population 1,381; bar = 1,105 passes (80.01%). Located caps: **A =
1,039** (75.2%, today), **B = 1,068** (77.3%, + the 29 malformed via
the relaxed tail law), **C = 1,203** (87.0%, + the 135 recoveries; the
178 store-less parts are unreachable for this architecture). 1,203 =
every V5_CFV2 store corpus-wide (G1's 1,068 + 135), a closed loop with
G1.

Levers (pass ceiling if fully solved; class pools = located + recovery
+ malformed-postfix):

| lever | mechanism | class pool | ceiling |
|---|---|---|---|
| L1 composite decode | decode the composite reference space (edge tables, opener regions, `0000`/`0001` groups) | 878 + 70 + 11 = 959 | +959 |
| L2 poolless answer | geometry (if any) in wrapper-less bodies | 55 + 21 + 18 = 94 | +94, **yield uncertain** (0/94 name SurfacicReps; 46 small + 7 large carry no strips at all — they may legitimately have no tessellation) |
| L3 refs-beyond decode | widen the composite vocabulary (`0000`, `9c00`, ...) — same problem as L1 | 30 + 8 = 38 | +38 |
| L4 stdcont-malformed locate fix | G1's two documented variants (section 5) | 29 | 0 alone; +29 via L1/L2 |
| L5 recovery extension | probe seebody/xdoc containers + relaxed tail law | 135 | +36 alone; +135 via L1/L2/L3 |

Pass ceilings by lever set (all classes assumed solved for the levers
that are on):

| lever set | passes | verdict |
|---|---|---|
| {L1} | 954 | below bar |
| {L1,L2} | 1,009 | below bar |
| {L1,L2,L3} | 1,039 | below bar = located cap A |
| {L1,L5} | 1,060 | below bar |
| {L1,L4,L5} | 1,071 | below bar |
| {L1,L2,L5} | **1,136** | **REACHES (margin 31)** |
| {L1,L3,L4,L5} | **1,109** | **REACHES (margin 4)** |
| {L1,L2,L4,L5} | 1,165 | reaches |
| {L1,L2,L3,L5} | 1,174 | reaches = cap C minus the 29 |
| {L1,L2,L3,L4,L5} | 1,203 | absolute ceiling (87.0%) |

**Which levers are required (fact, arithmetic):**

- **L1 composite decode: REQUIRED.** Without it every other lever
  maxes at 244 (76 pass + 94 poolless + 38 refs-beyond + 36 clean
  recoveries).
- **L5 recovery extension: REQUIRED.** Without it the cap is 1,068 <
  1,105 — the #35 planning fact, reconfirmed: even a perfect decode of
  everything currently located caps at 75.2%, and with the malformed
  fix at 77.3%.
- **A third content lever is REQUIRED** ({L1,L5} = 1,060 < 1,105):
  L2 (poolless, +76 with recoveries, margin 31) or L3+L4 (refs +
  malformed fix, margin 4). The minimal single third lever is L2; the
  safest plan per the margins is {L1,L2,L3,L5} (margin 69), with L4 as
  optional insurance.
- **#35's "two levers, not one" reconciled:** correct at its scope —
  it assumed perfect decode (L1+L2+L3 = the 1,039 cap) plus >= 66
  recoveries; measured candidates 135 >= 66 with the frame's ceiling at
  1,039 + 135 = 1,174. The refinement from this census: because 74/135
  recoveries pass under L1 alone and 8 need L3, 21 need L2, the
  two *families* (decode, locate) still need **three concrete levers**
  to clear 1,105 under the minimal accounting. No contradiction; a
  sharpening.
- **Held-out no-regret:** held-out failures are 61/61 composite-space;
  L1 lifts 0 -> up to 61 while dev only rises. No lever under
  consideration can lower any split.

## 8. Corrections and dated additions to existing notes (none massaged)

1. **2026-11-10, G1 note section 6 secondary claim ("`CATSeeBodyCont`
   regions carry their own nested header store on 95/1,377 parts"):**
   undercounted by a first-block probe — probing every seebody block
   per part gives **100/1,377** (this census, section 6). G1's model
   stands; its probe scope widens. (The 95 appears in the handoff band
   arithmetic in section 2 as 0.845 — recomputed on 100 it is
   (1,068+100)/1,377 = 0.848; the band conclusion is unchanged.)
2. **2026-11-10, G3 facet-semantics note F8 (vocabulary):** F8 named
   `01 02` edge groups + `ff`-openers as the composite-space markers.
   This census adds, as new byte evidence (not a correction): the
   non-pool sub-kind family `0000` (599 store rows), `0001` (59),
   `0101` (11), `00ff` (11), rare tail — **never present on a passing
   store** — and the P1g ff-escape count convention on edge tables.
   F8's measured totals reproduce **exactly** at fitness scope: its
   1,068-store dev scope = this census's 1,039 located + 29
   tail-rejected; its 889 composite stores = 878 gate-fired + 11
   dword8-overshoot bodies (post-fix composite, section 5); its 179
   clean stores = 76 pass + 55 poolless + 30 refs-beyond + 18
   padded-tail bodies (post-fix poolless). Its
   793/889 refs-beyond vs this census's 785/878: the scopes differ by
   the 11 overshoot bodies, which this census classifies but does not
   refs-measure (they are malformed under the shipped law).
3. **2026-11-10, G2 vertex-pool note P8 (3/1,377 strips-without-pool):**
   consistent at fitness scope — 2 of the 55 poolless stores carry
   STRIP_RE candidate headers (fac22ea: 20 candidates). The counts
   measure different things (G2: verified records; this census: header
   candidates); no correction.
4. **No corrections to G1's counts were needed:** 1,056/12/63/34/8/204
   and the 11-member overshoot family (k = 5..28) + 18-member
   padded-tail family reproduce exactly at fitness scope.

## 9. Claims

| claim | statement | rate | label |
|---|---|---|---|
| C1 | replay of the shipped seam reproduces the baseline report's L2 class on every L2 part | 1,442/1,442 | fact |
| C2 | census composition (section 1 table) | 1,381 dev + 61 held-out | fact |
| C3 | missing-313 = G1's N10 taxonomy + the 4 magic_ok=no parts | 208+63+34+8 = 313 | fact |
| C4 | composite triggers: edge 516 / both 322 / opener 40 (dev) | 878 | fact |
| C5 | refs-beyond under analysis on composite bodies | 785/878 = 0.894 | fact (analysis-only measurement) |
| C6 | edge tables: 681 stores walk 02 02 records (154,342); 651/681 endpoints >= pool; 157 other `02 0X` forms | 838 edge-carrying | fact / interior unknown |
| C7 | sub-kind family `0000`/`0001`/`0101`/`00ff`/rare never on passing stores | 0/76 passes | fact |
| C8 | refs-beyond 30 all carry non-standard sub-kinds (none pool-only) | 30/30 | fact |
| C9 | malformed-29 = overshoot 11 + padded 18, both G1-documented; zero pass on locate fix alone (postfix: composite 11, poolless 18) | 29/29 | fact |
| C10 | missing-313: 135 carry a missed store (67 shipped-law + 68 relaxed-law; composite 70 / clean 36 / poolless 21 / refs-beyond 8) | 135/313 = 0.431 | fact |
| C11 | 178/313 genuinely store-less (no region markers; whole-file V5_CFV2 = outer magic) | 178/313 | fact |
| C12 | seebody-store population 100/1,377 (G1 said 95, first-block probe) | 100 parts | fact (correction 1) |
| C13 | located caps A/B/C = 1,039 / 1,068 / 1,203 (75.2% / 77.3% / 87.0%) | — | fact |
| C14 | required levers: L1, L5, and one of {L2, L3+L4}; minimal reaching sets {L1,L2,L5} = 1,136, {L1,L3,L4,L5} = 1,109 | — | fact (arithmetic on measured pools) |
| C15 | poolless bodies carry decodable geometry | 0 established | unknown |
| C16 | composite-space interior semantics (edge forms, opener regions, 0000/0001 content) | — | unknown (next dispatch) |
| C17 | handoff ~0.82-0.93 band provenance | — | unknown (G1's measured denominators: 0.776 / 0.845 / 0.910; planning-invariant) |

## 10. Reproduction

```
# full census (deterministic; two runs byte-identical, md5-verified;
# ~50 s wall clock; needs the worktree venv for the catpart replay)
.venv/bin/python -I scripts/triage/classify_l2_grind.py

# byte-level store-signature survey for selected parts (the deep sample:
# the 21 parts behind the section 3/5/6 case studies)
.venv/bin/python -I scripts/triage/classify_l2_grind.py --deep \
  --include-sha16 0018baa84f3bff6b,02ee154402795740,026d6726007381a9,\
086a4effaab79779,0ae8c3e7dd3e74ad,01bd888df54c2790,498edddda534e60c,\
fac22ea3ee861d6d,278015fe3d3d603d,00198dd9de8caadf,01f2a48c9151197e,\
0520840350b47894,137b897fc0c276e3,152159176ca8d58d,03efd6080619e549,\
084841b3a2068a72,009cc6056fb040b9,cb3c7762e15af2cf,022523b419c2ad6e,\
05d3ebd19ddc8043,01d289f459924d13
```

Outputs: `docs/evidence/data/l2-grind-classification.csv` (committed;
one row per L2 part) and the summary on stdout. Corpus binaries are not
committed (corpus symlinked read-only). The analysis-only measurements
(C5's refs check on composite bodies; the relaxed-law probes) never
modify the shipped decode: `src/` is imported read-only and this ticket
changes no decoder, exporter, or fitness code.
