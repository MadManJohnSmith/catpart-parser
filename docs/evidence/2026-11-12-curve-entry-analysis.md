# Evidence: curve-entry (U4) corpus analysis, twin verification and the stage-5 rule (2026-11-12)

Ticket #34 (G6, stage 4a-residue, bounded analysis ticket; re-dispatch).
The stage-4a delegate was interrupted after its corpus run
(`curve-entries-files.csv`, 1,443 lines, committed byte-identical from
`t3/stage-4a-wip` @ `3d45133`) and before any analysis; a first
re-dispatch (branch `t3/stage-4a-residue-analysis` @ `fa8b8d0`) was
canceled by the owner mid-validation and its WIP is preserved.  THIS
note re-runs everything in its own worktree off main `6e97ebd`: every
number below comes from runs executed here (reproduction commands in
§7).  From the canceled draft only the scripts were reused
(`analyze_curve_entries.py` with one added summary section,
`probe_curve_entry_twins.py` with its 78-store validation list — which
this run finished: the list covers all 20 outcome classes, §1); the
draft's *figures* are not used anywhere.

**Baseline.**  The export join uses the CURRENT post-3a
`identity-export-files.csv` @ `6e97ebd` (the 2026-11-12 stage-5
pre-step regeneration): **exports 859, composite 747, L2 gate pass 782
(dev 734 — the accepted fitness row's figure; held-out 48), missing 178,
malformed 0, undecoded 405**.  The canceled draft measured against the
pre-3a lineage (753/677/686) — its population split and E0 exposure are
superseded by §2/§5 here.  Nothing in this note is a fitness projection.

Labels: **fact** = measured here, reproducible from a cited command;
**inference** = interpretation of measured data, named as such;
**candidate** = plausible, not measured; **unknown** = open.

## 0. Artifacts

| file | what |
|---|---|
| `scripts/triage/decode_curve_entries.py` | the U4 decoder, byte-identical to `3d45133` (`cmp` against `git show`) |
| `docs/evidence/data/curve-entries-files.csv` | its corpus run, recovered **byte-identical** (`git show 3d45133:... \| cmp`) |
| `scripts/triage/analyze_curve_entries.py` | pure-CSV analysis (no corpus access) |
| `docs/evidence/data/curve-entries-analysis-stores.csv` | 949 rows, one per composite store with a list node |
| `docs/evidence/data/curve-entries-analysis-summary.csv` | 145 `section,key,value` rows |
| `scripts/triage/probe_curve_entry_twins.py` | `--validate` (78-file re-run, both modes) and `--twins` (twin + fail-loop probes) |
| `docs/evidence/data/curve-entries-validation.csv` | 78 rows, per-file reproduction verdict |
| `docs/evidence/data/curve-entries-twin-probe.csv` | 162 `probe,subject,metric,value` rows |
| `docs/evidence/data/curve-entries-claims.csv` | claims rows (schema of `stage4b-claims.csv`) |

## 1. Reproducibility — both modes, zero drift (fact)

Method: the 78-store validation subset (`VALIDATION_SHA16` in
`probe_curve_entry_twins.py`), selected deterministically, re-runs BOTH
committed measurements through their own scripts into scratch dirs and
compares every row byte-for-byte.  The list covers **every outcome
class of the post-3a classification — 20 classes, 2-8 files each**
(exported big/small × pass / empty-mesh / not-manifold /
degenerate-triangles × with/without curve-entry loops, fail-closed
big/small × walk-exact/walk-mismatch, non-composite exported /
missing-geometry-store / undecoded-variant, decoder audit-error), i.e.
far more than the 25-file mixed-class bar.

    python3 -I scripts/triage/probe_curve_entry_twins.py --validate

| check | result |
|---|---|
| `decode_curve_entries.py` re-run vs the committed corpus run | **78/78 rows identical** (committed file itself `cmp`-identical to `3d45133`) |
| `ab_identity_export.py` re-run vs the committed post-3a census | **78/78 rows identical, zero drift** |

The interrupted-canceled draft had reported 10/10 drift on rows whose
census class was `malformed-store-header`.  That drift does not exist
at this baseline: it compared a **pre-3a** committed census against
post-3a code — a lineage artifact, resolved by the 2026-11-12
regeneration (`53ea4df`/`6e97ebd`).  The post-3a census reproduces from
this tree exactly; there is no stale-census class left (the analysis'
`stale-3a` flag machinery is vacuous at this baseline: 0 rows).

## 2. Population and distribution of curve-entry loops (fact)

    python3 -I scripts/triage/analyze_curve_entries.py

**Population: 949 composite stores with a locatable list node** (289
small, 660 big; dev 888, held-out 61) of the 1,442 parts.  Against the
post-3a baseline: **681 export** (216 small + 465 big; every one
walk-exact) and **268 fail closed** (73 small + 195 big).

**66 composite exports are decoder-blind (new at this baseline — fact).**
The census counts 747 composite exports, but the decoder population
covers only 681 of them: 66 exports have no decoder measurement at all
(strict store locator finds no body → no list node → `node_form`
empty).  Cross-check against the pre-3a census (`fa8b8d0`'s committed
`identity-export-files.csv`): all 66 were `missing-geometry-store` /
`export_ok=0` there, and **zero** composite exports were blind at
pre-3a — they are exactly the **stage-3a locator-recovery exports** (66
missing recovered), whose store bodies the decoder's strict locator
does not reach.  The recovery made the seam stronger than the triage
decoder's own front door.  Consequences, measured:

| decoder-blind exports (66) | value |
|---|---|
| with >= 1 dropped curve-entry loop (census `loops_curve_entry`) | 24 |
| dropped loops total | 210 |
| L2 pass / fail | 57 / 9 |
| empty-mesh with dropped loops (E0 candidates, battery unknown) | 3 (`4540eacc`, `d4a67129`, `f97b4c86`) |

The planarity battery says nothing about the 66.  Arithmetic guard:
measured L2 pass 613 (471 with + 142 without dropped loops) + 57 blind
= 670 = 782 total − 112 clean (non-composite) exports.

**Skip slots and curve-entry loops, exported stores** (the loops the
`curve-entry-loops-unexported` rule drops are countable only here):

| scope | stores | with skip slots | with >=1 dropped loop | dropped loops per store (min / q1 / med / q3 / max) | sum |
|---|---|---|---|---|---|
| small | 216 | 128 | 125 (57.9%) | 0 / 0 / 2 / 4 / 41 | 713 |
| big | 465 | 417 | 393 (84.5%) | 0 / 2 / 14 / 60 / 40,606 | 72,262 |
| all | 681 | 545 | **518 (76.1%)** | 0 / 1 / 6 / 31 / 40,606 | **72,975** |

- Loop-referenced skip slots (decoder `skips_dup_prev`): **179,639 of
  507,442 skip slots on exported stores (35.4%)**; the rest are
  referenced by no facet loop and — by construction — enter no loop and
  no triangle.
- Concentration: the top-3 stores carry **44,394 of 72,975 (60.8%)** —
  `13bb5c0c` 40,606 (the stage-4b u24be width-gap store, a not-manifold
  export), `4429e5a8` 2,144 and `64d646b1` 1,644 (both pass).
- Split: dev 470 of 631 exported carry dropped loops; held-out 48 of 50
  (46 pass, 2 fail).
- **Coverage of the dropped loops by the planarity battery (fact):**
  only normal-carrying loops are coplanarity-testable.  The battery
  tests **6,981 of 72,975 (9.6%)**; per exported store with dropped
  loops (518): coverage *full* 16, *partial* 270, *none* 232 (163
  further exported stores have no dropped loops).  The untested ~90%
  are mostly normal-less `0x42` strips, which no planarity arbiter in
  hand can reach.

**Fail-closed stores (268).**  192 have skip slots; 132 have >= 1
battery-tested skip-referencing loop (10,752 loops).  Their
dropped-loop count is **not measurable** (no export summary) and their
battery numbers are **not dup-law evidence** (decode wrong or
incomplete: skipref coplanar 1,624 / nonplanar 3,146 = 0.34, *control*
0.67 there vs 0.97 on exported stores).  What matters for stage 5:
the 4b laws (per-rep decode, width extension) and the 4a-residue
raw-array law will move some of the 268 into the exported set and
bring their curve-entry loops with them (**unknown** how many).

## 3. The dup law at corpus scale (fact + inference)

The decoder pins every loop-referenced skip slot to the bit-exact
coordinates of the preceding written element (the dup law) and re-runs
the planarity battery.  All 681 exported stores are walk-exact:

| scope | stores | skip-ref coplanar / nonplanar | rate | control |
|---|---|---|---|---|
| all exported | 681 | 3,769 / 3,337 | 0.530 | 0.966 |
| minus `13bb5c0c`, `cf7394ee` | 679 | 3,279 / 151 | **0.956** | 0.989 |
| minus 2, L2-pass only | 613 | 2,708 / 138 | 0.952 | 0.994 |
| minus 2, small form | 216 | 221 / 0 | 1.000 | 0.997 |
| minus 2, big form | 463 | 3,058 / 151 | 0.953 | 0.987 |
| minus 2, baseline-clean stores (control has 0 nonplanar) | 236 | 2,511 / 96 | 0.963 | 1.000 |

- **Fact:** the two defect stores account for 3,186 of the 3,337 raw
  failures (`13bb5c0c` 3,070 — its records tile at u24be per the
  stage-4b note, so its loop lists are mis-parsed; `cf7394ee` 116).
  Without them the dup law holds on 95.6% of tested loops against a
  98.9% control; 41 baseline-clean stores still carry one
  non-coplanar skip-referencing loop.
- **Inference (pin-independence, validation stores):** 52
  skip-referencing loops fail on the 5 validation stores that have any.
  For 38 the loop's *written-only* points are already non-coplanar
  (pin-independent: loop parse / width / multi-plane), for 14 fewer
  than two written points remain (untestable), for **0** are the
  written points coplanar; and **0/52** are rescued by any alternative
  pin (next written, prev-prev, or a per-slot choice among them).  The
  4.4% residual is consistent with the control's loop-level error, not
  with a wrong dup target — measured on 5 stores, not corpus-wide.
- **Fact (what the battery cannot see):** 90.4% of the dropped loops
  carry no normal; the battery says nothing about them.  Their only
  arbiter in hand is the twin invariance of §4 (one pair).

## 4. The interrupted turn's twin findings (026d6726 / e254a37e)

    python3 -I scripts/triage/probe_curve_entry_twins.py --twins

(all numbers from `curve-entries-twin-probe.csv`, under the decoder's
own pins — no new pin rule).

| interrupted-turn finding | verdict | evidence (this run) |
|---|---|---|
| The two stores are one part saved twice | **fact** | both: 124 elements (98 written + 26 skips), 24 curve records, 5 facet records, 8 edge records of sizes 3 3 9 2 2 2 2 9; x-offset exactly −50.0; 92/95 index-aligned written elements equal after the offset; skip sets differ in 3 slots (026d `1 8 29` / e254a37e `5 7 28`) and the 3 mismatching written indices (2, 3, 4) are the region where the skip slot moved |
| The edge tables decode as BREP edges: profile polylines, floor rings, verticals | **fact** for the shapes, **inference** for "BREP" | under the pins all 4 rings (n = 9) have z-spread 0 and radius spread <= 1.9e-5 about r = 2.36 (e254a37e's rings are 8/9 and 9/9 skip slots); all 8 verticals (n = 2) have dxy = 0; profiles (n = 3) run z 2.1 -> 2.3975 -> 2.855 or 2.81 |
| On the twins the same BREP edges reference different copies (mesh quality differs between saves) | **fact** | edge-referenced skip slots **11 vs 19**; ring records reference **7/9** written copies on 026d6726 vs **1/9 and 0/9** on e254a37e; facet-strip skip references **14 vs 28** (strip 0: 4 vs 10 of 18) |
| **Cross-twin invariance of the dup pins** (stated by the interrupted turn's successor probes; re-verified) | **fact (n = 1 pair)** | the pinned coordinate sequence of **every** facet record (4 normal-less `0x42` strips + the `0x4a`) matches its twin counterpart element-for-element after the offset: **118/118 positions**, covering 42 skip references (14 + 28) the planarity battery cannot test |
| The planarity battery is insensitive to the mid/dup choice (normal loops reference only z=2.1-ring slots, dups on both twins) | **half confirmed, half refuted** | confirmed: normal-carrying loops touch only slots 1/91/123 (026d) and 28/91/123 (e254a37e), all z = 2.1 dups; unreferenced slots are never tested.  **Refuted as "insensitive"**: on the slots it does touch, the dup pin passes **3/3 and 5/5** loops, next-written **1/3 and 0/5**, mid-where-eligible **1/3 and 0/5** — the battery discriminates dup from mid/next wherever a loop references the slot |
| The committed rule is conservative and correct for the stated test | **confirmed, with a sharper reason** | §5 |

Two further facts the interrupted turn did not state (re-verified from
this run's probe CSV):

- **The "mid" label is the "unreferenced" label (fact, by
  construction).**  026d6726's 14 `mid` slots (6 12 15 22 25 43 46 73
  76 95 98 105 108 114) are **14/14 loop-referenced dups at the z =
  2.81 ring on e254a37e** (same indices).  Whether those slots on
  026d6726 sit at the mid-ring z = 2.855 (the U4-M claim) or at z =
  2.81 is **not decided by any test in hand**; the twin reading favours
  2.81 (inference, n = 1 pair).  Corroboration: e254a37e's all-written
  profile ends at z = 2.81 while its mid-pinned mirror ends at z =
  2.855 — a 0.045 asymmetry the dup reading removes.  **U4-M (mid-ring
  law) is demoted to candidate / unsupported.**
- **The mid/dup question cannot affect an exported triangle (fact, by
  construction).**  A `mid` slot is by definition referenced by no
  facet loop, so it enters no loop and no triangle; the exporter never
  needs it.  Only the dup pin of loop-referenced slots matters for the
  mesh.

Fail-loop probe (the dup law's residual): 52 failing skip-referencing
loops on the 5 validation stores = 38 pin-independent + 14 untestable
+ 0 written-coplanar; **0/52 rescued by any alternative pin**; 5 more
loops on `02ff71f5` reference beyond the rep-0 element space
(multi-rep store) and stay excluded.

## 5. Recommendation for stage 5 (inference, from §2-§4)

**Keep the conservative non-export rule as the stage-5 default.**
Reasons, each measured above:

1. The rule is not what fails the stores that carry it: of the 518
   exported stores with dropped loops, **471 pass L2** (the gate needs a
   non-empty manifold mesh; it does not require closure).  Relaxing the
   rule cannot raise those; it can only risk flipping them (more
   triangles from unverified loops → a non-manifold edge): **471
   passing stores are the downside exposure**, 8 of them
   battery-covered.
2. 90.4% of the dropped loops are not testable by the planarity
   battery, and on the tested ones the dup law is 95.6% vs a 98.9%
   control — good, not law-grade.
3. The only pin-independent arbiter (twin invariance) exists for one
   pair; the corpus has **77 (pool, element, skips, records)-signature
   families of >= 2 stores (196 stores, 49 with skip slots)** that
   could host the same test — **candidate**, not measured.
4. The mid law is moot for export (§4) and unsupported anyway.

**Defined optional subset (E0), monotone-safe by construction.**  If
stage 5 wants any curve-entry export, restrict it to:

> a store that decodes and exports under the current rules **and**
> whose current export fails the L2 gate with `empty-mesh` **and** that
> has >= 1 dropped curve-entry loop: export those loops with each skip
> slot welded to the written vertex of its immediately preceding
> written element (the dup pin; no new vertices).

Why this is safe for L2 membership: E0 stores already fail L2, so the
change can only move a store from fail to pass (or leave it failing) —
**no store of the 782 passes can regress**.  Exposure (fact,
`curve-entries-analysis-stores.csv`, measured at the post-3a census):

| tier | stores | detail |
|---|---|---|
| E0 candidates, decoder-measured (empty-mesh with >= 1 dropped loop) | **21** | 18 big / 3 small; 20 dev / 1 held-out (`1b1ae784`); 140 dropped loops in total |
| E0-b, battery-supported (every dropped loop normal-carrying and coplanar under the pin) | **4** | `2fca9bc4`, `4ad53b87`, `4ae0392d`, `505bbe1f` |
| E0 with a nonplanar tested loop | 1 | `3dff4d93` (full coverage, 1 of 2 nonplanar) — exclude |
| E0 partial coverage / none | 4 / 12 | geometry unverified; membership gain would be gate-only evidence |
| E0 census-scope extras (decoder-blind, battery unknown) | **3** | `4540eacc`, `d4a67129`, `f97b4c86` — the stage-3a recovery's own empty-mesh exports; include only with the same gate-only caveat |
| not touched: empty-mesh with **no** dropped loop | 16 | the rule is not their cause |
| not touched: not-manifold with dropped loops | 26 | stage-4b's root cause is the width-law gaps (u24be + plane tiebreak), not the rule |

- **Decision for the coordinator:** include E0-b (4 stores) if any
  curve-entry export lands; include the other 17 measured + 3 blind
  only if a gate-only membership gain on unverified geometry is
  acceptable — the L2 gate would reward it, the planarity battery
  cannot confirm it.  Three E0 stores (`2fca9bc4`, `3dff4d93`,
  `505bbe1f`) have skip slots == written points (`elem_decl = 2 ×
  skips`; every written point has a dup copy and the loops reference
  only the dups), which makes the weld the natural reading there
  (inference; the property does NOT hold on `4ad53b87`/`4ae0392d`).
- **Not recommended:** a store-level "all tested loops coplanar"
  subset (226 stores qualify minus the two defect stores; 205 of them
  already pass L2, 13 fail not-manifold, 8 fail empty-mesh): it mostly
  touches the population that cannot gain and can lose.
- **Order of operations (unmeasured):** the 4b laws (per-rep decode,
  u24be width + plane tiebreak) and the 4a-residue raw-array law will
  move fail-closed stores into the exported set and change which
  stores are empty-mesh; **recompute E0 after the stage-5 integration**
  with `analyze_curve_entries.py` against the new census, then decide.
  Whether welding vs keeping separate dup vertices changes the
  manifold flag is **unmeasured** (the seam today indexes written
  points only).

## 6. Limits and unknowns

- The decoder population covers 681 of the 747 composite exports: the
  66 stage-3a locator-recovery exports are blind to the strict locator
  (§2) — they carry census-only counters (210 dropped loops) and no
  battery measurement.  E0 census-scope is 24; battery-annotated E0 is
  21.
- The dup-law rate is battery-based (normal loops only); the
  pin-independence probe covers 5 stores; the twin invariance covers 1
  pair; 5 loops on `02ff71f5` reference beyond the rep-0 element space
  and are excluded from the probe (multi-rep store).
- Unknown: whether a dup slot's coordinates stay bit-exact when the
  same vertex is shared by more than two faces (the anchors have
  <= 2 copies).
- Unknown: the 33 32/33 36 record semantics (unchanged from the
  decoder docstring).
- The analysis is CSV-composable by construction
  (`analyze_curve_entries.py` reads only the two committed
  measurements); the validation and twin probes are the only corpus
  re-runs (78 files + 7 named stores + 5 fail-loop stores), per the
  bounded-dispatch scope.

## 7. Reproduction (all deterministic; CSVs byte-identical across runs)

    ln -s /home/alan/Documents/Repos/catpart-parser/corpus corpus   # gitignored, read-only
    git show 3d45133:docs/evidence/data/curve-entries-files.csv | cmp - docs/evidence/data/curve-entries-files.csv
    python3 -I scripts/triage/analyze_curve_entries.py              # §2, §3, §5 tables
    python3 -I scripts/triage/probe_curve_entry_twins.py --validate # §1, both modes
    python3 -I scripts/triage/probe_curve_entry_twins.py --twins    # §3 pin-independence, §4
    # decoder on the anchors (NOTE: keep --out-dir OUT of the repo, the
    # default would overwrite the committed corpus CSV):
    python3 -I scripts/triage/decode_curve_entries.py \
      --include-sha16 026d6726007381a9,e254a37e2ba6902c --out-dir /tmp/u4-anchors

## 2026-11-12 stage-5-baseline recompute (coordinator, dated)

E0 re-derived against the stage-5 baseline
(`stage5-identity-export-files.csv`, the 1,011-export row): **24
stores — membership unchanged** vs the list above (21 candidates
incl. the 4 battery-supported + 3 census-scope blind). The newly
exported per-rep stores contribute no empty-mesh-with-dropped-loops
members. The stage-6 raw-array integration is the next mover of the
fail-closed set; E0 stays gated on that recompute per
`U4-stage5-recommendation`. Join (both CSVs committed):

```
python3 -I -c "import csv; ab={r['sha256']:r for r in csv.DictReader(open('docs/evidence/data/stage5-identity-export-files.csv'))}; print(sum(1 for r in ab.values() if r['export_ok']=='1' and 'empty-mesh' in (r['failed_check'] or '') and int(r['loops_curve_entry'] or 0)>0))"
```

-> 24.

## 2026-11-12 stage-9-baseline recompute (stage-10 implementation pre-step, dated)

E0 re-derived against the CURRENT stage-9 baseline
(`stage9-identity-export-files.csv`, the accepted fitness row's 1,120
exports; join per the pattern above):

```
python3 -I -c "import csv; ab={r['sha256']:r for r in csv.DictReader(open('docs/evidence/data/stage9-identity-export-files.csv'))}; print(sum(1 for r in ab.values() if r['export_ok']=='1' and 'empty-mesh' in (r['failed_check'] or '') and int(r['loops_curve_entry'] or 0)>0))"
```

-> **26 stores (25 dev + 1 held-out `1b1ae784`)** = the stage-5 24
UNCHANGED + **2 NEW members from the stage-9 mixed-write exports**
(`4dfef8f2`, `65eb023d`, both stage `identity-mixedwrite-reps`); 0
members lost.  The 4 battery-supported E0-b stores remain empty-mesh
with unchanged dropped-loop counts (`2fca9bc4` 2, `4ad53b87` 1,
`4ae0392d` 1, `505bbe1f` 2) — E0-b is stable across stages 5->9.

**The law-level predicate is supported (fact, pre-declaration probe,
2026-11-12).**  The E0-b criterion (battery coverage full AND zero
nonplanar — the `e0_battery_supported` column's definition, ported to
`composite._e0b_dup_pin`) evaluated LIVE on the exporter's own decode
of every current member selects **exactly the 4 named stores**:
`2fca9bc4` 2/2, `4ad53b87` 1/1, `4ae0392d` 1/1, `505bbe1f` 2/2
normal-carrying AND coplanar under the dup pin.  Every other member
keeps the conservative rule: 19 carry at least one normal-less
(untestable) dropped loop — including the 3 former census-scope-blind
stores (`4540eacc`, `d4a67129`, `f97b4c86`; the live evaluation closes
their battery-unknown gap: normal-less, untestable) and the 2 new
mixed-write members — and `3dff4d93` carries a nonplanar pinned loop.
The live predicate matches the committed
`e0_battery_supported` classification on every store the analysis
measured.  **Implementation choice (named per the dispatch): the
law-level predicate, NOT a digest gate** — the committed analysis
supports it (it selects exactly E0-b at this baseline), and a digest
gate would freeze the corpus instead of the law.  The U4-M mid law
stays DEMOTED/unsupported and is not implemented; the battery
discriminates dup from next/mid wherever a loop references a slot
(section 4).
