# Evidence: the extended-header facet family (0x47/0x4f) and the escaped facet count

**Date**: 2026-11-18
**Status**: COMPLETE — both facts land; the loop-split law is pinned, so the
discovery + diagnostics stop is not taken. Every figure below is a row of
[br6-extended-header-claims.csv](data/br6-extended-header-claims.csv) or a
row-derived sum, or a measured export of the anchor part reproduced by the
commands in section 8.
**Scope**: composite stores (the identity table walk's element space). The
0x47/0x4f family is a *composite* family: its references are 0-based element
indices, like 0x42/0x4a/0x4c.
**Shipped code**: `src/catpart/geometry/facets.py` (P1g count escape, header
length from the `ff` position), `src/catpart/geometry/composite.py`
(`parse_extended_facet_records`, the `ty`/`b3`/`b4` split, the closed-manifold
weld gate), `src/catpart/geometry/export.py` (the weld warning's detail).
**Rust port** (2026-11-18, same commit family): `port/src/geometry/facets.rs`
and `port/src/geometry/composite.rs` carry the same law, counters and warning
strings; the differential parity table is section 11.
**Probe**: `scripts/triage/probe_extended_header_family.py` (stdlib,
deterministic, manifest order; `--selftest` carries the synthetic positive and
negative fixtures).

---

## 1. Executive summary

| Fact | Verdict | Anchor measurement |
| :--- | :--- | :--- |
| F1 — the escaped facet count | **Landed.** The count position now uses the P1g escape (`ff` + `u32le`), the same encoding `composite.read_count` already applied to the list node's counts. | the Gabarit's two 528-ref 0x42 records parse as one count `(528,)`; each exports 526 triangles, 87.96 mm² (EXTH-11 rows; the pair = 175.92 mm², the ticket's +176) |
| F2 — the extended header family | **Discovered and pinned.** `01 <mk> ty b3 b4 ff` (`ff` at +5): `ty` = independent triangles, `b3 + b4` = the counts-table length, `sum(counts) + 3*ty == n`; first `b3` loops are strips, last `b4` are polygon fans. | 13,300 accepted records over 581 parts; 13,300/13,300 pass the three byte laws; 0x4f b4 loops coplanar 23,356/24,934 (93.7%) |
| Loop-split law | **Pinned** — not stopped at discovery. | the Gabarit's 9 records: 9/9 marker, `b3 + b4`, sum law; three 0x4f faces reproduce `pi*(r_out^2 - r_in^2)` to <2% |
| Gabarit export | **Recovered**: 4,420 → 15,688 triangles; 401.89 → 27,082.12 mm²; open → **closed** manifold; 4,308 → 0 unused vertices | section 4 |

The plate body is the three big 0x4f faces (z = 14, 1, −0.5) plus the 0x47
walls. The decoded solid is **closed, manifold, oriented, 0 boundary edges,
0 degenerate triangles, and every one of the part's 7,816 written points is
referenced**.

## 2. The byte anchor (both bases)

Gabarit store: `povdoigt/SP-02/CATIA/CATIA_vol/Usinage/Gabarit_trou_alu_alpha.CATPart`
(sha256 `76ff90ae…`), body `[323488, 493670)`, `element_decl` 9,213.

| offset (hex / dec) | field |
| :--- | :--- |
| `+0x00 (0d)` | record marker `01` |
| `+0x01 (1d)` | facet marker `mk` (`0x47` or `0x4f`) |
| `+0x02 (2d)` | `ty` — number of independent triangles stored first in the ref block |
| `+0x03 (3d)` | `b3` — leading loops with strip semantics |
| `+0x04 (4d)` | `b4` — trailing loops with closed-polygon semantics |
| `+0x05 (5d)` | form byte `ff` (the extended 6-byte header form) |
| `+0x06 (6d)` | `u32le n` — reference count (`+0x06 (6d)`..`+0x09 (9d)`) |
| `+0x0a (10d)` | 12-B f32le normal — **0x4f only** (0x47 carries none) |
| counts | `b3 + b4` count bytes (one u8 each), summing to `n - 3*ty` |
| refs | `n` × u16be element indices: the first `3*ty` are the independent triangles, the rest the counts-delimited loops |

The Gabarit's 9 records (committed as `EXTH-09_record_anchor` rows; `store`
is the body offset, `end` the last reference byte):

| offset | mk | ty | b3 | b4 | n | counts | refs |
| ---: | :--: | --: | --: | --: | --: | --: | --: |
| 427410 | 0x47 | 198 | 79 | 2 | 1059 | 81 (465) | 594 soup + 465 loop |
| 429619 | 0x47 | 198 | 79 | 2 | 1059 | 81 (465) | 594 soup + 465 loop |
| 431828 | 0x4f | 6 | 70 | 14 | 1210 | 84 (1192) | 18 soup + 1192 loop |
| 434354 | 0x47 | 183 | 27 | 66 | 1422 | 93 (873) | 549 soup + 873 loop |
| 437301 | 0x47 | 183 | 27 | 66 | 1422 | 93 (873) | 549 soup + 873 loop |
| 440682 | 0x47 | 190 | 29 | 68 | 1488 | 97 (918) | 570 soup + 918 loop |
| 443765 | 0x47 | 190 | 29 | 68 | 1488 | 97 (918) | 570 soup + 918 loop |
| 456364 | 0x4f | 66 | 37 | 105 | 2248 | 142 (2050) | 198 soup + 2050 loop |
| 462668 | 0x4f | 47 | 26 | 107 | 2220 | 133 (2079) | 141 soup + 2079 loop |

Why the three header bytes are load-bearing (all four coincidences would have
to be accidental otherwise): `b3 + b4` equals the counts-table length implied
by the header-to-header tiling; `sum(counts) + 3*ty` equals `n`; the 0x4f
records carry a unit normal (`(0, 0, ±1)` on the anchor part, 4,075/4,075
corpus-wide); and the `b3`/`b4` split reproduces the plate's analytic face
areas:

| 0x4f face | plane | analytic `pi*(r_out^2 - r_in^2)` | decoded |
| :--- | :--- | --: | --: |
| 431828 | z = 14, r 51.15..56.00 | 1,634.4 mm² | 1,632.6 mm² |
| 456364 | z = 1, r 17.50..50.15 | 6,940.4 mm² | 6,805.2 mm² |
| 462668 | z = −0.5, r 17.50..56.00 | 8,889.9 mm² | 8,756.1 mm² |

The residual is the degenerate-skip convention (G3 F7): the faces' loops
reference the store's skip slots, and the welded solid loses a handful of
zero-area triangles.

## 3. FACT 1: the escaped facet count

The record at `450320` (and its twin at `451389`):

```
01 42 01 ff | 10 02 00 00 | ff 10 02 00 00 | 23 f3 23 fc ...
header      | n = 528     | count = 528    | refs
```

The count position holds the P1g escape (`ff` + `u32le`), not a raw u8. The
old reader took `ff 10 02 00 00` as `(255, 44, 1, 0, 0)` — a sum of 300
against `n = 528` — so the record failed every `(width, k)` tile and stayed
declared-but-unparsed. The fix applies the escape to the count table in both
readers (`facets.parse_facet_record` and `composite.parse_strip_records`), and
variable-width counts shift the ref start accordingly (`counts_bytes`).

The two records export 526 triangles each, 87.96 mm² each → **175.92 mm²**
(the ticket's +176); the other two escaped-count records (`461458`,
`462063`, `n = 296`) export 294 triangles / 82.47 mm² each
(`EXTH-11_escaped_count_record_*` rows). The escape also re-splits those two
296-ref records from a five-loop raw-u8 reading (`255, 40, 1, 0, 0`) to one
loop of 296; that re-split is what makes the store's assembled mesh close
(section 4).

**Correction to the ticket's expected delta (measured, not massaged):** the
part's *export* delta from the escape fix is larger than +176 because the
correct split changes which loops the weld gate accepts. Measured with the
escape reading reverted and everything else identical: 11,853 triangles /
23,926.36 mm² (open, 2,439 boundary edges) vs 15,688 / 27,082.12 (closed) —
the escaped reading is load-bearing for the closed-mesh weld, not just for
the two records.

## 4. The Gabarit before/after (measured)

| metric | before | after |
| :--- | --: | --: |
| vertices | 7,816 | 7,816 |
| triangles | 4,420 | 15,688 |
| area | 401.89 mm² | **27,082.12 mm²** |
| manifold | true | true |
| closed | false | **true** |
| oriented | false | true |
| boundary edges | 2,590 | 0 |
| degenerate triangles | 0 | 0 |
| unused vertices | 4,308 | 0 |
| `facet_candidates` | 50 | 59 |
| `facet_records` | 48 | 59 |
| `extended_header_records` | absent | 9 |
| `extended_header_triangles` | absent | 7,433 |

The summary is no longer silent about the family: `facet_candidates` 50 → 59
(9 extended headers), `facet_records` 48 → 59, and the composite block carries
`extended_header_records` / `extended_header_triangles`. When the extended
records parse but export nothing, the same fields show `extended_header_triangles
= 0` (the named non-silent diagnostic the ticket asked for; no corpus store
hits that state on the sample).

Area accounting: 401.89 (short records) + 26,245.3 (the 9 extended records,
welded, 9,292 triangles) + 434.9 (the short records' own welded loops) =
27,082.1. The 9 extended records alone carry 26,245 mm² of the plate.

**Why the ticket's ~28,494 target is not reproduced.** 28,494 is ~2,249 mm²
above the extended family's measured 26,245. The decoded solid closes at
27,082 mm² (94.5% of the part's nominal 28,672 mm²); a closed 2-manifold with
every edge used exactly twice cannot be missing a face, so the residual is the
faceted-vs-exact-area difference, not an undecoded surface. The 26,245 figure
is what the pinned law carries; it is reported here as measured, and the
28,494 in the ticket is treated as a projection, not a pin.

## 5. The loop-split law (pinned)

The split is pinned by the header, not by a search:

1. `k = b3 + b4` = the counts-table length (13,300/13,300 corpus records).
2. `sum(counts) = n - 3*ty` (13,300/13,300).
3. The first `3*ty` references are independent triangles; the counts then
   delimit the loops, **first `b3` loops under the strip law (0x42), last
   `b4` under the closed-polygon fan law (0x4c)**.
4. Strip loops are open polylines; polygon loops are rings. The ordered
   assignment is what reproduces the analytic annulus areas (section 2) and
   leaves **0 over-used edges** on the anchor part (every edge in the final
   mesh is used exactly twice).

Evidence against the alternatives, measured on the anchor part
(`EXTH-10_reading_*` rows; skip-slot loops dropped by all three so the
comparison isolates the split):

| reading | triangles | area | edges used > 2× |
| :--- | --: | --: | --: |
| **pinned: b3 strips + b4 polygons** | 7,433 | 23,524.46 mm² | **0** |
| strip-only shortcut (one strip per record) | 11,278 | 60,312.77 mm² | 2,956 |
| all-fan (every loop fan-triangulated) | 7,427 | 142,666.88 mm² | 1,321 |

The strip-only shortcut overdraws the plate 2.6× and the all-fan reading
6.1×; both leave thousands of over-used edges, exactly the failure mode the
ticket flagged. The pinned split is the only one with zero over-used edges,
and with the weld gate it closes (section 4).

**Planar coherence** (the ticket's z=14/1/−0.5 probe): the 0x4f records put
every triangle on one plane, and their `b4` polygon loops are coplanar against
the stored normal 221/221 on the anchor part, 23,356/24,934 (93.7%)
corpus-wide — the non-coplanar remainder is the multi-plane fillet/bevel
content the committed battery already treats as legitimate (stage-3b loop
battery 98.3%).

## 6. The weld gate (why the plate closes)

The 9 records reference the store's skip slots (curve entries) on 542 loops
(the four curve-sample loops of each face plus the short records' 11). The
committed rule drops those loops (`curve-entry-loops-unexported`). On this
store the dropped loops weld to their preceding written vertices (the U4-D dup
law) and the merged mesh is a **closed manifold** — so the weld is accepted
under a new structural gate: on a **non-empty** primary mesh the weld fires
only when the assembled mesh is closed and manifold (every edge used twice, no
boundary). The committed E0 unconditional acceptance is unchanged; every other
store keeps the conservative drop.

This is deliberately stronger than the stage-10/15 E0 rule and narrower than a
general weld: the gate is a geometric invariant, not a store class. The
negative direction is measured — the same code with the escape fix reverted
produces an *open* mesh and the gate declines the weld (23,926 mm², section 3).

## 7. Corpus measurement

`scripts/triage/probe_extended_header_family.py` over the full manifest
(1,442 `kind=part` rows; 59 claims CSVs still parse at header width):

| claim | observations | passes | rate |
| :--- | --: | --: | --: |
| EXTH-01 parts with an extended-header candidate | 1,442 | 732 | 0.5076 |
| EXTH-02 parts with ≥1 accepted record | 1,442 | 581 | 0.4029 |
| EXTH-03 marker in family (0x47/0x4f) | 13,300 | 13,300 | 1.0000 |
| EXTH-04 `b3 + b4` = counts length | 13,300 | 13,300 | 1.0000 |
| EXTH-05 `sum(counts) + 3*ty == n` | 13,300 | 13,300 | 1.0000 |
| EXTH-06 exact tile to the next header | 13,300 | 6,587 | 0.4953 |
| EXTH-07 refs inside the element space | 13,300 | 13,300 | 1.0000 |
| EXTH-08a 0x4f normal unit length | 4,075 | 4,075 | 1.0000 |
| EXTH-08b 0x4f b4 loop coplanar | 24,934 | 23,356 | 0.9367 |

**What this detector does NOT discriminate** (the dispatch-rule line):
- It does not test the 0x47 normal (none is stored): planarity is only
  measurable on 0x4f.
- It does not distinguish "3 independent triangles" from "a 3-ref strip": the
  two are the same primitive by construction.
- It does not validate the 6,713 records that end before the next header (the
  gap bytes between the record end and the next header stay unread;
  `EXTH-06` counts them, it does not explain them).
- It does not pin the `0x47`/`0x4f` *pair* semantics (front/back faces):
  the pairs are congruent in area but have disjoint coordinates, so both are
  exported; no dedup fires.

Synthetic negative fixtures: `probe_extended_header_family.py --selftest`
(bad sum, out-of-range refs) and
`tests/test_facets_tiling.py::test_raw_u8_reading_of_the_escaped_count_would_reject`.

## 8. Export A/B (185-part stratified sample)

Sample: 8 parts per `detected_version` bucket, evenly spaced by size among
parts ≤ 3 MB (185 distinct parts), each exported twice through the seam —
once with `main`'s code, once with this branch — and scored with the single
gate authority `catpart.fitness.runner._score_export`.

| measurement | claim | result |
| :--- | :--- | :--- |
| L2 pass before / after | EXAB-02 / EXAB-03 | 146 / 149 |
| pass → fail flips | EXAB-04 | **0** |
| fail → pass flips | EXAB-05 | **3** (all `empty-mesh` → pass: `CorrugateTube1`, `SpatialLoft-4064E`, `Shell_VStf_005.1`) |
| not-manifold regressions | EXAB-06 | **0** |
| triangle-count changes | EXAB-07 | 30 parts |
| closed-mesh gains | EXAB-08 | 4 parts |

The rows live in
[br6-extended-header-ab-claims.csv](data/br6-extended-header-ab-claims.csv)
(aggregates + one row per changed part).

The 3 fail→pass rows are stores whose previously empty triangulation now has
the extended family's triangles (26, 40, 5,877 triangles).

## 9. Reproduction

```
export LD_LIBRARY_PATH=/usr/lib:$LD_LIBRARY_PATH
# the probe + its synthetic fixtures
python scripts/triage/probe_extended_header_family.py --selftest
python scripts/triage/probe_extended_header_family.py
# the anchor export summary
python -c "
from pathlib import Path
from catpart.geometry.export import build_export
print(build_export(Path('corpus/povdoigt/SP-02/CATIA/CATIA_vol/Usinage/Gabarit_trou_alu_alpha.CATPart'), Path('/tmp/g.ply')))
"
```

## 10. Open / follow-ups

- `docs/format/geometry.md` GE-G1 still states the 4-byte grammar only; the
  extended form belongs there once the format doc's next revision lands
  (kept out of this ticket's file set).
- The 0x47/0x4f *pair* reading (two congruent facets with disjoint
  coordinates) is exported twice by design; a future ticket can pin whether
  the second copy is a front/back face or a writer duplicate (the unordered
  dedup law does not fire — the coordinates differ).
- The gap bytes of the 6,713 non-exact records are unread; `EXTH-06` bounds
  the number but not the content.
- The Rust port now implements the extended family (section 11). The WASM
  fixture subset does not yet carry a synthetic extended-header store (the A2
  generator's variant list is shared with the Python gate); the boundary
  parity is demonstrated on the corpus, and the artifact is rebuilt from the
  ported code.

## 11. Rust port parity (2026-11-18)

The port mirrors the law byte-for-byte: the P1g count reader (escaped
counts), the 6-byte header discovery (`facets::facet_headers`, the regex's
leftmost-non-overlapping order), `composite::parse_extended_facet_records`
(ty / b3 / b4 / `b3+b4` counts / `sum(counts)+3*ty == n` / in-element-space
refs), the `triangulate` split (soup triples first, then b3 strips and b4
polygons), the `welded_mesh_gate` (E0 unconditional, else closed+manifold)
with its `closed-manifold-weld` law string, and the twin's warning text.

**Differential run** (`catpart-export` vs `fidelity-cli export`, the exact
shipped seams, the 185-part sample of section 8; every figure a row of
[br6-extended-header-parity-claims.csv](data/br6-extended-header-parity-claims.csv)):

| measurement | claim | result |
| :--- | :--- | :--- |
| sample parts | EXPAR-01 | 185 |
| outcomes `match` | EXPAR-02 | **185 / 185** |
| mismatches | EXPAR-03 | **0** |
| PLY byte-identical (compared exports) | EXPAR-05 | **152 / 152** |
| summaries dict-identical | EXPAR-06 | **152 / 152** |
| error-class rows (both sides refused, same class) | — | 33 / 33 |
| Rust L2 pass | EXPAR-07 | **149** |
| pass → fail | EXPAR-08 | **0** |
| manifold regressions | EXPAR-09 | **0** |
| fail → pass | EXPAR-10 | 3 |

The 20-part PLY sample is a subset of the 152 byte-compared exports
(EXPAR-04), so it is byte-identical for the same reason. The Gabarit's Rust
export is the same file byte-for-byte: 15,688 triangles, 27,082.12 mm²,
closed manifold, 0 boundary edges, 0 unused vertices, and the summary is
dict-identical (including `extended_header_records = 9`,
`extended_header_triangles = 7,433`, `curve_entry_law = "closed-manifold-weld"`,
`loops_curve_entry_exported = 542`).

One divergence was found and fixed during the differential (not shipped):
the Python raw-array path leaked the internal `extended_triangles` counter
into its summary while the port did not; the counter is now popped on both
sides, so the summary carries only `extended_header_records` /
`extended_header_triangles`.

Reproduction:

```
cargo build --release --manifest-path port/Cargo.toml
.venv/bin/catpart-export  <part> -o /tmp/py.ply > /tmp/py.json
port/target/release/fidelity-cli export <part> /tmp/rs.ply > /tmp/rs.json
cmp /tmp/py.ply /tmp/rs.ply && python -c 'import json,sys; a=json.load(open("/tmp/py.json")); b=json.load(open("/tmp/rs.json")); assert a==b'
```
