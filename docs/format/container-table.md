# 3. Container-name table records, kind law, container-tree resolution

Parsed by `catpart.containers` (schema v1: `containers[]` with `name`,
`parent_name`, `table_id`, `index`, `stream_id`, `weight`, `guid`, and
the file-level `kind`).

Evidence: [2026-11-07-container-table-and-trailer.md](../evidence/2026-11-07-container-table-and-trailer.md)
("Container-name table record format"; per-record sample in
`docs/evidence/data/container-table-records-sample.csv`),
[2026-11-07-container-kind-law.md](../evidence/2026-11-07-container-kind-law.md)
(verified by `scripts/triage/verify_kind_law.py`),
[2026-11-08-container-tree.md](../evidence/2026-11-08-container-tree.md)
(verified by `scripts/triage/verify_container_tree.py`; per-file rows in
`docs/evidence/data/container-tree-scan.csv`) and the B5 differential
([2026-11-08-r19-r21-differential.md](../evidence/2026-11-08-r19-r21-differential.md)).

Scope: 19300 records on 1810/1818 magic-verified files parse under the
model with zero rejected anchor positions; 8 files (small
`unknown`-version CAA documents) have no table at all. Records are
located by the anchor dword `02 00 81 20` (little-endian
`0x20810002`) at record offset S+32 and validated against the full
model before being reported; the scan covers the evidence-validated
first 2 MB of the file, starting after the header. Claim IDs are the
differential CSV's IDs where they exist.

## 3.1 Record layout (all multi-byte fields little-endian)

| ID | Offset | Field | Claim | Label | Scope |
|---|---|---|---|---|---|
| TB-found | S+32 | anchor (f9) | the anchor dword `02 00 81 20` locates every record; 19300 records on 1810 files parse with zero rejected anchor positions corpus-wide. | established | 1810 with-table files, buckets V5R15-R32 + unknown |
| (f1) | S+0 | f1 (`stream_id`) | stream-position value; the join key with the (unparsed) directory table (law D1, 3.3). Reported as `stream_id`. | established (measured) + open (semantics) | 19300 records |
| TB-f2-weights | S+4 | f2 (`weight`) | per-record weight: 11 (9455 recs), 12 (4930), 13 (3070), 21 (1198), then rarer values (22, 14, 25, 33, ...; large values only outside leading groups). Precision over B1 (container-tree note): the 1198 weight-21 rows are the `AppliCont` rows of table 0x00040001, and `AppliCont` also sits in 0x00030001 in 235 files (weight 11) — the f2 vocabulary is as measured; its semantics are unproven. Reported as `weight`. | established (vocabulary) + open (semantics) | 19300 records |
| TB-f3-vocabulary | S+8 | f3 (`table_id`) | exactly three values corpus-wide (19300/19300): `0x00030001` (17488 recs), `0x00040001` (1441 rows — 1198 of them the `AppliCont` row, 243 others: `CATProdCont` 99, `CATCompoundCont` 62, `CATFeatLocalRef` 21, `CGMGeom` 21, `CATMFBRP` 18, ...), `0x00050001` (371). Reported as `table_id`. | established | corpus, unchanged on R19/R21 |
| (idx) | S+12 | idx (`index`) | 1-based index within the table id (skips observed). Reported as `index`. | established | 19300 records |
| T3 | S+16, S+20, S+28 | f5, f6, f8 | f5 == `0x006c0001`, f6 == 2, f8 == 0 — held on every parsed record by construction of the validator. Validated, not reported. | established | 19300/19300 |
| (f7) | S+24 | f7 | small value: 0 (15219), 1 (1876), 8, 2, 9, 10, 11, 12, 3, ...; one row carries `0x01000000`. Semantics unproven. Not reported. | open | 19300 records |
| TB-f10-law (T1) | S+36 | f10 | f10 == ceil((len(name1) + len(name2) + 2)/8) + 1 — 19300/19300 (100%); 106/106 R19 and 64/64 R21 sample records. The names area is zero-padded to a multiple of 8; the padding bytes verified zero. Validated, not reported. | established | corpus |
| (names) | S+40 | names | `name1 00 name2 00`, printable ASCII. name1 is the container's name (reported as `name`); name2 is a base-class/secondary-name annotation with an exactly-5-value corpus-wide vocabulary (`CATContainer` 63.8%, `CATFeatCont` 26.0%, `CATProdCont` 8.3%, `CATSiMuGenCont` 1.6%, `CATDrwCont` 0.2%) — see 3.4. Reported as `parent_name`. | established | corpus |
| T3 | then 8 | tail | constant `03 00 f7 00 03 00 00 00`. Validated, not reported. | established | 19300/19300 |
| (guid) | then 16 | GUID | per-record object id, reported lowercase-hex as `guid`. The last u16 increases across rows within a table (e.g. 0x417d, 0x4180, 0x4182, ...); the pattern is not validated corpus-wide. | established (reported) + open (internals) | corpus |

Worked example (`0018baa84f3bff6b`, the `CATProdCont` record at
S = 0x91c): f1 = 16, f2 = 11, f3 = `0x00030001`, idx = 1, f5 =
`0x006c0001`, f6 = 2, f7 = 0, f8 = 0, f9 = `0x20810002` @0x93c, f10 = 4
@0x940, names `CATProdCont\0CATFeatCont\0` @0x944-0x95b (24 B, no pad),
tail `0300f700 03000000` @0x95c, GUID @0x964-0x973
(`00000000 00001ae0 6991af79 00000dba`). Full record: 88 bytes; next
record at 0x974.

**Record size (law T2)** = `64 + 8*ceil((len(name1) + len(name2) + 2)/8)`;
the next record starts immediately after the GUID.

## 3.2 Contiguity, satellite blobs, exception families

| ID | Claim | Label | Scope |
|---|---|---|---|
| TB-contiguous | records form strictly contiguous chains (no satellite or open gaps) on 1428/1810 files (0.787 R19 / 0.942 R20 / 0.746 R21); gap structure identical in kind on both lines. | established | 1810 with-table files |
| TB-satellite | satellite blobs sit between records on 382 files (20.5% R19 / 24.5% R21 of table files): a second record family starting `04 00 c0 20` (e.g. the `V5USERID` row: `04 00 c0 20 0a 00 00 00 01 00 00 00 00 00 00 00 "V5USERID" ...` at 0x86c-0x8bb of F09VP) or `04 00 fc 3f`; 350 satellite + 205 unclassified gap instances. | established | 382 files |
| (distributed) | a distributed table (26/1810 files, span > 64 KB, mostly `unknown`-version CAA products with embedded documents): name records appear next to their embedded documents throughout the file while the directory group covers only the leading rows. | established (observed family) | 26 files |
| (drifted keys) | drifted join keys (3 files, one family): a directory row's d6 references a value absent from the table (e.g. a V5R21 CAAclean part with d6 = 100/d7 = 95 against a bound row f1 = 70). | established (observed family) | 3 files |
| (no table) | 8/1818 files have no table: small `unknown`-version B31CAADoc files (5 products of 12-13 KB, one 66 KB product, two parts of ~100 KB). | established (observed family) | 8 files |

## 3.3 Directory table **(documented, not parsed)**

Immediately before the name records sits a directory of 40-byte records
(one per row, in the same order). The parser skips it deliberately — no
L1 output field needs it. Field sketch (worked examples only, B1): d0
low u16 varies with high u16 `0x00bf`; d1 == `0x2e`; d2 == 0; d3
usually `0xe7000200` (varies — not an identification constant); d4 ==
`0x01000000 | k` (k = 1..N); d5 cumulative counter; d6 join key; d7 ==
d6; d8 two u16 values; d9 == 0. 4-byte arrays (the subsequent records'
f1 sequence, second u16 `0x1a00`) follow some directory records; the
anchor scan skips them as gaps.

| ID | Law | Claim | Label | Scope |
|---|---|---|---|---|
| TB-dir-count (L4) | count | directory count == name-record count — 0.974 R19 (632/649) vs 0.989 R21 (351/355); exceptions are subset directories, the same failure mode on both lines. | established | table files, both lines |
| TB-dir-join (L5/D1) | join | the directory d6 multiset joins the records' f1 — 0.988 R19 / 0.983 R21 (subset form); as an exact bijection 1702/1810 = 94.0% corpus-wide. The binding is the shared value, not record order. | established | table files |
| TB-dir-cum (L6/D2) | cumulative | d5 == 1 + cumulative f2 over the records that precede the bound record, in table order — 1702/1810 (94.0%); holds wherever L4 holds. | established | bijection files |
| TB-dir-d7 (L7/D3) | d7 | d7 == d6 — 1712/1810 (94.6%). | established | table files |
| (field sketch) | layout | the d0-d9 sketch above is measured on worked examples (F09VP, `0018baa84f3bff6b` at 0x65c-0x814) and carries no corpus-wide rate. | candidate | worked examples only |

Worked example (same file): directory rows k = 1..10 with d5 = 1, 22,
34, 45, 56, 67, 78, 90, 103, 114 and d6 = f1 sequence 1, 7, 16, 21, 26,
31, 36, 41, 46, 51; the f2 weights of rows 1..9 (21, 12, 11, 11, 11,
11, 12, 13, 11) reproduce d5 exactly as prefix sums.

## 3.4 Kind law (K1)

TB-kind-law **(established, zero disagreements)**: among the 1810
with-table files, `CATPrtCont` among the record names <=> part
(1436/1436 with-table parts); `CATProdCont`/`CATMechProdCont` without
`CATPrtCont` <=> product (374/374 with-table products; 2 parts carry
`CATMechProdCont` next to `CATPrtCont` — the part name decides); no
table => kind `unknown` (8 files). Both directions hold: no part lacks
`CATPrtCont`, no product carries it, every with-table file carries one
of the two. 100% on R19/R20/R21 (649/649, 189/189, 355/355). Reported
as `kind`.

## 3.5 Container tree — the documented negative (decision, final)

TREE-resolve **(established, negative)**: the candidate assembly law —
records form a connected hierarchy via `parent_name` (child's name2 =
parent's name1), rooted at `AppliCont`/`CATContainer`-style roots —
**fails corpus-wide**: 1699/19300 records (8.8%) have a `parent_name`
matching a same-file `name1`; 0/1810 files resolve fully (also 0/649
R19 and 0/355 R21 — the negative holds identically on both lines;
record-level resolution 9.4% R19 / 8.1% R20 / 9.1% R21). The
`parent_name` vocabulary is exactly 5 values corpus-wide, and its two
dominant members (`CATContainer` 63.8%, `CATFeatCont` 26.0%) appear 0
times as `name1` — they are class labels, never records. Where a
parent_name does resolve it always has exactly one candidate record (0
ambiguous resolutions corpus-wide), but 158 of the 1699 resolving
records have their unique candidate strictly after them in file order,
so even the resolving edges carry no consistent before-child ordering;
and 138/1810 files repeat a name1 value, so name-based node identity is
not unique in general. `AppliCont` is not a root under this relation:
all 1433 `AppliCont` rows carry parent_name `CATContainer`
(unresolved); 377/1810 files have no `AppliCont` row at all; its
position varies.

**Ticket #24 resolution (2026-11-08, final)**: documented negative. No
tree model is implemented and the parser emits no tree field — the
evidence rule ("a structure without a documented claim is not
implemented", Spec C) forbids inventing a hierarchy the name table does
not carry. `containers[]` (3.1) is the L1 container inventory and
already carries `parent_name` as measured (the GLOSSARY's feature-tree
term: "There is no instance hierarchy; `parent_name` is a base-class
annotation, not a within-file parent pointer"). A real
instance-hierarchy claim (e.g. the directory table's d5 = 1 +
cumsum(f2) ordering law, or product-region properties) would be a new
B-branch ticket documenting it here first.
