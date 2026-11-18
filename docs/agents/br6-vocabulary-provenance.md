# BR6 pre-work — provenance audit of the frozen L3 denominator

**Date** 2026-11-18 · **Repo** main @ `d16d5e9` · **Scope** read-only audit of [`brep-construct-vocabulary.csv`](../../evidence/data/brep-construct-vocabulary.csv) (23 rows, committed `df02b7d`).
**Method** re-ran the committed census with `--out-dir /tmp/opencode/census-out`; re-derived every frozen count
from [`brep-census-files.csv`](../../evidence/data/brep-census-files.csv) (1,442 rows, 1,089 `l2_status=pass`);
cross-read the BR1–BR5 claims CSVs. Nothing in the tree was modified.

## 0. Finding

The frozen CSV has **no committed generator at all** — not only the 8 rows BR3/BR4 flagged. The committed census
script writes an **18-row vocabulary in a different schema** (`construct_id` = `TOPO_*|GEOM_*|CONT_*`, 12 fields,
[`census_brep_constructs.py:487-506`](../../../scripts/triage/census_brep_constructs.py)L487); the frozen file is 23 rows
in the 9-field schema that [`tests/test_brep_vocabulary.py:14-24`](../../../tests/test_brep_vocabulary.py)L14 pins. Both
landed in the same commit and never changed (`git log --oneline -- <both>` → `df02b7d` only). What *is* reproducible is
the **census** CSV (byte-identical re-run, §2.1) and, from its columns, **15 of the 23** frozen counts; the other 8 have
no generator, no claims row, and L2 rates not even expressible as `k/1089` at the 4-dp precision the generator uses
([`census_brep_constructs.py:476`](../../../scripts/triage/census_brep_constructs.py)L476).

## 1. Every one of the 23 rows

`count`/`rate` are frozen `corpus_occurrences` (over 1,442) and `rate_l2_pass` (over 1,089). Census columns by
letter: G `has_store`, I `cgm_present`, M `vertex_pool_points`, N `element_space_declared`, O `edge_polyline_records`,
P `edge_unwrapped_records`, Q `curve33_32_lines`, R `curve33_37_circles`, S `curve33_38_curves`, U `facet_records_total`,
V `facet_planar_faces`, W `facet_strips`, X `facet_polygons`; `br3:`/`br4:`/`br2:`/`br5:` are `<file>-claims.csv` lines.

| # | id (frozen line) | count / rate | regenerated exactly by | drift recorded in |
|---|---|---|---|---|
| 1 | TOP-01 (`:2`) | 1435 / 1.0 | census I `cgm_present` (= G∨I); `br1:7` | — |
| 2 | TOP-02 (`:3`) | 1435 / 1.0 | **same predicate as TOP-01** — no lump class exists | `br5:81` BR5-06a (no record-level detector) |
| 3 | TOP-03 (`:4`) | 1133 / 0.9982 | census U `facet_records_total>0` (emitted with TOPO_FACE); `br1:4` | — |
| 4 | TOP-04 (`:5`) | 1133 / 0.9982 | census U; `br2:2,4`, `br1:4` | — |
| 5 | TOP-05 (`:6`) | 895 / 0.786 | census V∨X; `br2:3,5`, `br1:5` | — |
| 6 | TOP-06 (`:7`) | 1311 / 1.0 | census O∨P∨Q; `br3:48` | — |
| 7 | TOP-07 (`:8`) | 1282 / 1.0 | census N>0 alone (M⊆N); `br3:46` | — |
| 8 | CRV-01 (`:9`) | 1231 / 0.9853 | census Q∨O; `br3:50`, `br1:6` | — |
| 9 | CRV-02 (`:10`) | 1077 / 0.8503 | census R>0; `br3:52` | — |
| 10 | CRV-03 (`:11`) | 357 / 0.2874 | census S>0 — **whole conic class, not ellipses**; `br3:54` | — (label caveat §3) |
| 11 | CRV-04 (`:12`) | 214 / 0.182 | **nothing** — no column or column pair (§2.3) | `br3:72` C04_parabola_ceiling; `2026-11-17-br3-curves.md:79`, `:114` §6.3 |
| 12 | CRV-05 (`:13`) | 143 / 0.115 | **nothing** (§2.3) | `br3:74` C05_hyperbola_ceiling; same note lines |
| 13 | CRV-06 (`:14`) | 1435 / 1.0 | census I only (class emitted on `cgm_present`, `census…py:384`) | `br5:70` BR5-03c (0/1089 content), `br5:83` BR5-06c |
| 14 | CRV-07 (`:15`) | 996 / 0.8365 | census O>0; `br3:56` | — (proper n>2 reading is 366, `br3` C07_polyline_strips) |
| 15 | CRV-08 (`:16`) | 1280 / 0.975 | **nothing** (§2.3; incidental match §2.4) | `br3:70` C08_trim_presence (969); `2026-11-17-br3-curves.md:88` |
| 16 | SRF-01 (`:17`) | 895 / 0.786 | census V∨X; `br2:3,5` | — |
| 17 | SRF-02 (`:18`) | 1128 / 0.9972 | census W `facet_strips>0`; `br4:2-3` | `2026-11-17-br4-quadrics.md:130` (strip presence, not cylinders) |
| 18 | SRF-03 (`:19`) | 542 / 0.465 | **nothing** — census emits one `GEOM_SURF_QUADRIC` | `br4:4` SRF-03_frozen_generator_drift; `2026-11-17-br4-quadrics.md:129` §6.1 |
| 19 | SRF-04 (`:20`) | 412 / 0.354 | **nothing** | `br4:5` |
| 20 | SRF-05 (`:21`) | 320 / 0.275 | **nothing** | `br4:6` |
| 21 | SRF-06 (`:22`) | 680 / 0.582 | **nothing** | `br4:7` |
| 22 | SRF-07 (`:23`) | 890 / 0.795 | **nothing** | `br4:8` |
| 23 | SRF-08 (`:24`) | 1435 / 1.0 | census I `cgm_present` only | `br5:70`, `br5:83` (0/1089 content) |

**Unprovenanced (8): CRV-04, CRV-05, CRV-08, SRF-03, SRF-04, SRF-05, SRF-06, SRF-07.** The drift rows in
`br4:4-8` cite `cgm_present` (1,435/1,442 = 0.995146) as what the census actually measures — no competing per-class
number exists.

## 2. Re-derivation (do not trust the note prose)

### 2.1 The census itself is clean
`diff` against the committed `brep-census-files.csv` → **byte-identical** (1,442 rows), and the script reports
`L2-pass population: 1089 files (dev: 1033, held-out: 56)`: the columns are trustworthy provenance, only the
vocabulary file sits outside the generator.

### 2.2 The 15 tie-outs are exact, not approximate
Each reproduces count and L2 rate with no slack: TOP-05 895/1,442 and 856/1,089 = `0.786042` → `0.786`;
CRV-01 1,231 and 1,073/1,089 = `0.985308` → `0.9853`; SRF-02 1,128 and 1,086/1,089 = `0.997245` → `0.9972`.
For all 15 an integer `n` satisfies `round(n/1089, 4)` = the frozen string — the generator's exact formula.

### 2.3 The 8 unprovenanced rows fail two independent tests
1. **No column reproduces the count.** All 20 single-column predicates and all 190 pair-OR combinations were
   tested against 1,442 rows: no match for 214, 143, 542, 412, 320, 680, 890 (§2.4 covers 1280).
2. **The rate is not `round(k/1089, 4)`.** Substituting each frozen rate for the tie-out test gives **no integer
   `n`** at 4 dp; the rows are only consistent after rounding to 3 dp, and two are ambiguous there:

| id | frozen rate | nearest `n/1089` | at 4 dp | integer `n` at 3 dp |
|---|---|---|---|---|
| CRV-04 | 0.182 | 198/1089 = 0.18182 | 0.1818 ✗ | 198 |
| CRV-05 | 0.115 | 125/1089 = 0.11478 | 0.1148 ✗ | 125 |
| CRV-08 | 0.975 | 1062/1089 = 0.97521 | 0.9752 ✗ | 1062 |
| SRF-03 | 0.465 | 506/1089 = 0.46465 | 0.4646 ✗ | 506 |
| SRF-04 | 0.354 | 385/1089 = 0.35353 | 0.3535 ✗ | 385 or 386 |
| SRF-05 | 0.275 | 299/1089 = 0.27456 | 0.2746 ✗ | 299 or 300 |
| SRF-06 | 0.582 | 634/1089 = 0.58219 | 0.5822 ✗ | 634 |
| SRF-07 | 0.795 | 866/1089 = 0.79522 | 0.7952 ✗ | 866 |

   An unknown denominator or a hand-rounded estimate produced these cells; they cannot be output of the committed
   generator on any integer count over the stated 1,089-file population.

### 2.4 Internal arithmetic tell (new)
The three conic rows are not a partition: CRV-03 = **357** (all `33 38` carriers) **and** CRV-04 + CRV-05 = 214 +
143 = **357** — 714 claims against a 357-file carrier set. `br3:72,74` read `214+143=357` as "reconstructing the
ceiling", but that ceiling is `C03_census_presence` (357, reproducible); the split is an attribution no field
supports (`2026-11-17-br3-curves.md:77`). SRF-03..07 show the same overlap (542+412+320+680+890 = 2,844 > 1,442).
One incidental match is *not* provenance: `vertex_pool_points>0 | curve33_other>0` equals 1,280 (CRV-08), but
across 8 targets × 210 tests one coincidence is expected, it is in no committed detector, and it has no
relation to a trimmed curve.

## 3. Consequence for L3

**The headline is unaffected.** ADR-0001/ROADMAP define L3 as **construct coverage — decoded or negatived**
([`docs/adr/0001-fitness-protocol.md:5`](../../adr/0001-fitness-protocol.md)L5,
[`docs/ROADMAP.md:227-247`](../../ROADMAP.md)L227): 100 % of the frozen vocabulary resolved, corpus rate
"reported alongside and never gates". Row coverage is count-free, so a wrong `corpus_occurrences` cell changes no
verdict. **What does lean**, all avoidably:

1. **The 8 unprovenanced `corpus_occurrences` / `rate_l2_pass` cells** — if BR6's L3 table reuses BR1's table
   shape ([`2026-11-17-br1-brep-census.md:28-52`](../../evidence/2026-11-17-br1-brep-census.md)L28), rows
   **CRV-04, CRV-05, CRV-08, SRF-03, SRF-04, SRF-05, SRF-06, SRF-07** carry numbers no artifact produces.
2. **BR3's ceiling statement text** — `br3:72,74` embed "frozen arithmetic 214+143=357" in the claim statement.
   The verdict (`documented-open`) rests on the reproducible 357, so it survives; the embedded split does not.
3. **Rows whose number is provenanced but produced by a detector that does not measure the named construct** —
   a mis-scoped denominator: **TOP-02** (1,435 = body/CGM presence, `br5:81`), **CRV-06** and **SRF-08** (1,435 =
   `cgm_present`; BR5 measures the content at **0/1,089**, `br5:70`, `br5:83`), **CRV-03** (357 = every conic
   carrier; no ellipse discriminator, `2026-11-17-br3-curves.md:73-74`). These four rows must not report their
   frozen rate as a decode rate.

No L3 verdict in BR2–BR5 currently depends on an unprovenanced number: SRF-03's "decoded" rests on 4 files/12
loops (`br4:22`), SRF-04's on 93 files (`br4:34`), SRF-05/06's on the 67,919-loop bound (`br4:54`), SRF-07's on 388 (`br4:36`),
CRV-08's on `C08_trim_presence` (969) — all independent of the frozen cells.

## 4. Recommendation

**Freeze as-is, with a disclosure column — do not re-freeze now.**

1. Add a `provenance` column (`census-column` / `unprovenanced`) plus a "Provenance" section naming the 15
   predicates and the 8 gaps. That is a data-file change: its own ticket, not a hand-edit.
2. Add a mechanical guard so the gap cannot silently become fact: assert the 15 tie-outs against
   `brep-census-files.csv` and pin the 8 rows as `unprovenanced` (today the test checks only schema, row inventory,
   `0 ≤ rate ≤ 1` and `len == 23` — `tests/test_brep_vocabulary.py:96-114`).
3. In the L3 table, report per row either the construct-level decode count (BR2–BR5 rows) or `unprovenanced`;
   never the frozen count. Keep the frozen rate out of every decode column.

**Why not re-freeze.** Re-deriving the denominator from the committed generator yields **18 rows**, not 23:
TOP-01+TOP-02 → `TOPO_BODY`; CRV-03+CRV-04+CRV-05 → `GEOM_CURV_CONIC`; SRF-03..07 → `GEOM_SURF_QUADRIC`;
CRV-08 has **no class at all** and would be deleted; and `CONT_CGMGEOM`/`CONT_BREPMODE`/`CONT_MFBRP` — which the
frozen 23 omit — would appear. That shrinks L3 coverage 23 → 18, erases two independently established outcomes
(SRF-03 and SRF-04 decoded separately; CRV-04/CRV-05 documented-open separately) and deletes the only row carrying
CRV-08's candidate evidence. It destroys evidence rather than creating it: the generator cannot split a quadric or
a conic, so re-freezing swaps 8 unknown numbers for 1 coarser true one. Changing a frozen denominator is a
STOP-and-report owner decision under [`docs/agents/dispatch-recipes.md:240-262`](../../agents/dispatch-recipes.md)L240)
and the 2026-11-10 amendment ([`docs/ROADMAP.md:231`](../../ROADMAP.md)L231), not a BR6 side effect. If the owner
wants a provenanced table later, the correct form is 23 rows with the 8 cells **blank + `unprovenanced`**, not 18.

## 5. Reproduction

```bash
export LD_LIBRARY_PATH=/usr/lib:${LD_LIBRARY_PATH:-}
.venv/bin/python scripts/triage/census_brep_constructs.py --out-dir /tmp/opencode/census-out  # 18 rows; census byte-identical
python3 /tmp/opencode/audit.py   # 15 tie-outs; 20 singles + 190 pair-OR tests against the 8 counts
python3 /tmp/opencode/rates2.py  # k/1089 test at 4 dp vs 3 dp   (scratch, uncommitted, read-only on the tree)
```
