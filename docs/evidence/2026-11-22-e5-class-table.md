# Evidence: the `e5 0d` Class Table — the writer tail's token grammar and the exact-surface class (2026-11-22)

**Date**: 2026-11-22
**Status**: COMPLETE for the class-table algebra (the writer tail's token
grammar, the class vocabulary, and the `0x00e7` exact-surface record);
**shipped** as the E5-surface route; **candidate** for one membership rate;
**blocked** for the submarine 3-lane variant (no snapshot on this host).
**Target**: the two items the E5 bulk-dialect note left named
(`2026-11-19-e5-dialect.md` §3.1 "the writer block's class table is not
decoded" and §5.3(1) "decode the payload tag encoding").
**Method**: corpus probe `scripts/triage/probe_e5_class_table.py`
(`--selftest` pins the discriminating edges; `--ab --baseline-src` runs the
no-regret A/B); shipped decoder `src/catpart/geometry/surface.py`
(`parse_e5_surface`, `e5_pole_data`, `e5_surface_frames`, the scan fold) +
`src/catpart/geometry/grid.py` (`e5_records`) + the Rust twins; tests
`tests/test_e5_surface.py` (15) and `port/src/geometry/surface.rs` tests
(+7). Read-only over the corpus; no binary committed.

---

## 1. Executive summary

The writer-block tail is a **token stream** and the E5 record vocabulary is
a **typed object graph**; inside it, class `0x00e7` carries **exact
B-spline surfaces** under the compact head's pole law.  The shipped route
evaluates and tessellates them, which upgrades the E5 dialect's "point nets
with a measured shape" into exact surfaces and opens parts that had no
other carrier.

| measurement | value |
| :--- | ---: |
| sha-valid corpus files (this host) | 1,755 / 1,824 manifest rows |
| writer-block regions carrying a tail | 735 (CT-01) |
| writer tails that tokenize cleanly | **712/735 = 96.87 %** (CT-01) |
| tail refs hitting the region's own ids | ref1 103/147 · ref2 1,337/2,128 · ref3 219/257 (CT-02) |
| files carrying class `0x00e7` | 268 |
| `0x00e7` records / parsed / plausible | 11,554 / **11,520 (99.71 %)** / **11,478 (99.64 %)** (CT-03/04) |
| pole markers `00 00` / `01 00` | 10,723 / 797 |
| marker tail laws | plain 10,578/10,723 = 98.65 % · rational **797/797 = 100 %** (CT-05) |
| non-square orientation (battery sample, 332 nets) | v-major 291 · both 41 · u-major **0** (CT-06) |
| battery pass (tested sample) | 417/439 = 94.99 % (CT-07); no-facet records 189/189 tessellate (CT-08) |
| corpus A/B (d8554e0 vs branch, **379** changed-candidate files) | **342 identical · 37 changed · 0 regressions · 0 error-class changes** |
| … of which display → mesh flips | **15** (all dev split; L2 dev 1,138 → 1,153 = 82.40 % → **83.49 %**) |
| Python vs Rust PLY (16 no-facet E5 parts) | **16/16 byte-identical** |

**Verdict.** The Class Table algebra closes: the tail is a reference list
written in the payload's own tag grammar, and the frequent classes resolve
to record schemas — `0x0096` = one reference + an 8-f64 body, `0x000d` =
three references, `0x000e` = three references + three weighted scalars,
`0x01fe`/`0x01ff` = one/five references, `0x00c8` = matrix + limits, and
`0x00e7` = the exact-surface record decoded below.  The brief's "perfiles
pareados → superficie reglada, cilindros/planos analíticos" is the
`(poles_v × poles_u)` net itself: degree-(3,1) surfaces (9,104 records)
sweep a 2-pole straight section along a cubic rail — analytic cylinders and
planes — and the rational `01 00` markers carry arc weights (1.0, 0.7071,
0.6667 on the worked record).

## 2. The writer tail's token grammar

The tail sits between the writer block's name and the first `e5 0d`
marker.  Measured over the corpus (claim `CT-01`), it tokenizes as:

| token | bytes | reading |
| :--- | :--- | :--- |
| opener | `03 <u8>` | pair (measured arg `00`) |
| second stamp | `11 <u32le=len> <ascii>` | a second release stamp ("  R207-JMA:122008") |
| small ref | `08 <u8>` | 1-byte reference |
| ref | `18 <u16le>` | 2-byte reference |
| wide ref | `38 <u24le>` | 3-byte reference |
| flags | `80..ff` | sub-tags (arity tags in payloads, §3) |
| end | `17 <u8>` | terminator, arg `00`/`01` |

The reference values are **record ids**: `ref3` (`38 <u24le>`) hits the
owning region's id set at (CT-02.ref3), `ref2` at (CT-02.ref2) — the
misses are references to ids living in the file's other regions, not noise
(the E5 note's §5.3(1) candidate is confirmed for the wide form and
rate-candidate for the narrow forms).  The grammar closes on
(corpus rate) of tails; the residue is the 3 regions with no content-start
writer block (`2026-11-19-e5-dialect.md` §2) and mid-stream writer blocks,
which this probe does not re-scan.

## 3. The class table

Per-class census (`e5-class-families.csv`, families in ≥ 10 files): the
payloads are typed records whose leading tag is an **arity tag**
(`0x80 | n` = "n references follow", each reference `08/18/38`-tagged),
followed by the class's own f64 body:

| class | records | files | payload shape census (top) |
| :--- | ---: | ---: | :--- |
| `0x000e` (14) | 561,952 | 876 | opaque 449,585 · index 111,633 |
| `0x0096` (150) | 405,436 | 876 | f64 334,571 · opaque 50,183 |
| `0x01ff` (511) | 296,663 | 876 | opaque 293,174 · text 3,489 |
| `0x01fe` (510) | 219,473 | 876 | opaque |
| `0x000d` (13) | 219,463 | 876 | opaque 217,651 |
| `0x00e7` (231) | 11,554 | 268 | f64 11,241 — **exact-surface record** (§4) |

The object graph reading: `0x000d` = a 3-reference node (triangle of
vertex refs), `0x000e` = the same node with three weighted scalars,
`0x01fe` = a 1-reference back-pointer, `0x01ff` = a 5-reference node —
and `0x0209` = a 25-reference loop with per-reference direction flags
(`01 00` forward / `ff ff` reverse).  The reference ids the tail carries
are the graph's roots.

## 4. The `0x00e7` exact-surface record

Layout (measured; the decoder is the shipped
`surface.parse_e5_surface`):

```
0x80 | deg_v:u32 | a:u32 | b:u32 | n_v:u32 | q:u32
     | knots_v f64[n_v]    strictly increasing
     | mults_v u32[n_v]    each >= 1
     | deg_u:u32 | a2:u32 | b2:u32 | n_u:u32 | q2:u32
     | knots_u f64[n_u]    strictly increasing
     | mults_u u32[n_u]    each >= 1
     | 00 00 | 01 00       pole marker: plain / rational
     | pole net            v-major outer, 24 B per pole
     | tail                148 B law (not a closure gate)
```

- **Pole law**: `poles = sum(mult) - degree - 1` per direction — the
  compact head's law (`2026-11-21-surface-compact-head.md`) with u32
  fields.  The worked record `backshell_F` id 556: knots 6, mults
  `[6,3,3,3,3,6]` (sum 24), degree 5 → 18 poles; net = 324 = 18×18
  triples, exactly the committed E5 census' 18×18 grid.
- **Marker law**: `00 00` = non-rational, tail `== 148` on the family;
  `01 00` = rational, `tail - 8*poles == 148` (the weights follow the
  coordinate net in the same v-major order).  Both hold on the population
  (CT-05).  The rational weights are arc weights (1.0, 0.7071, 0.6667 on
  the worked record) — the analytic cylinders/cones of the brief.
- **Orientation**: the net is **v-major outer** — pole `(i, j)` at
  `net + 24*(j*poles_u + i)`; consecutive `poles_u` triples are the
  u-polygon at a fixed v.  Pinned by the battery: on the no-facet
  population's non-square nets, 85 evaluate *only* under this reading and
  **0** only under the u-major transpose (CT-06; square nets evaluate
  under both and take the pinned reading).
- **The `a`/`b`/`q` slots** are a measured vocabulary (a=b=0 on all but a
  handful of records; q in 0..5, mirrored between lanes: `(0,0)`
  11,267 / `(2,2)` 171 / others < 40).  They do **not** gate the decode;
  the validators are the knot monotonicity, the multiplicity law and the
  net-fit closure (net_span failures: 3/11,554).
- **Tail**: 148 B on 98.65 % of the plain records (142/150/152 on the rest) — a law,
  not a closure gate; the grid is predicted by the head and validated by
  the net (`2026-11-21-surface-compact-head.md`'s precedent).
- **Degrees**: `(3,1)` × 9,104 dominates (a 2-pole straight section swept
  along a cubic rail — the analytic cylinder/plane family), then
  `(3,3)` × 751, `(5,5)` × 465, `(5,4)` × 347, `(1,2)` × 266.

## 5. The shipped route and the no-regret law

`surface.scan_part` runs the E5 records **after** the `a5 03 34` frames
under the same battery (corner poles, finiteness, hull, folds, scale,
plausibility — the compact branch's chord-length-band exemption applies:
`arc_applicable = False`).  The fold law is **no-regret**: the E5 records
join the totals and the mesh **only when at least one E5 surface
tessellated**; with nothing tessellated the E5 census rides on additive
`e5_*` scan fields alone and the totals, the mesh and the route decision
are exactly the pre-E5 ones.  Consequences, by construction:

- a part whose E5 surfaces all refuse falls through exactly as before
  (grid route, face-gp route, display route — `hair-dryer`'s 20 records
  are the implausible-net family and would stay display if none parsed;
  with the shipped pole band — no lower floor, the a5 route's own
  convention — they parse and mesh);
- a part with working facet stores never reaches the fallback seam
  (facet path wins, output byte-identical);
- `80aad8d8`/`d7ed0772` (a5-priority prefixes) carry no `0x00e7` records —
  untouched.

**Corpus A/B** (`e5-surface-ab.csv`, baseline `d8554e0` via
`--baseline-src`): over the exact changed-candidate set — every E5-bearing
file (268) plus every no-facet part (111 further files; 379 total) — the
branch exports 342 files **byte-identically** and improves 37: 22
candidate-grid → exact-surface upgrades where the mesh stays and grows,
and **15 display → mesh flips** (all `dev` split; no held-out file is in
the changed set), with **0 regressions** — no triangle-count drop and no
error-class change on any row.  Expected L2 dev: 1,138 → 1,153
(82.40 % → 83.49 %); held-out flat 57/61 by construction.

## 6. Parity

The Rust twin mirrors the decoder, the scan fold and the export prose
expression-for-expression (the twin's `e5_pole_data` is the same v-major
read; `scan_part` folds under the same no-regret law; `export.rs` names
the a5+E5 split with the same conditionals).  Python vs Rust
`fidelity-cli export` over the 16 no-facet E5-bearing parts: **16/16
byte-identical PLY** (sha256-compared), summaries equal including the new
`e5_*` fields.

## 7. What stays open (named negatives)

| span | status | reopening criterion |
| :--- | :--- | :--- |
| 3-lane compact head (10 frames, 2 submarine parts) + the folds-failing `MB-Mani-H` | **blocked** — the TR-1700 snapshot is not on this host and its URL/sha256s were never committed | the snapshot or the 2 `BW-hatch-*` parts restored |
| tail ref1/ref2 misses (refs to ids outside the region) | candidate — a file-level id graph would close them | a probe pass joining ids across all of a file's regions |
| `a`/`b`/`q` slot semantics | measured vocabulary, not interpreted | a record family where they vary with geometry |
| the 148 B tail's content (limits/params) | not interpreted | not needed for evaluation |
| the 397 implausible nets | partial (mixed data: partial-record unions) | a per-record trim law |

## 8. Detector honesty

- **What "the algebra closed" means**: the tail grammar and the `0x00e7`
  layout are measured from bytes with the reproduction command below;
  the other classes' schemas in §3 are measured on sampled records
  (2-3 records per class per file in the probe's sample budget), stated
  as measured schemas, not proven grammars.
- **What does not discriminate**: the class census counts records by
  their declared `class:u16le` — it does not prove a class's schema is
  unique across writer versions; the arity-tag reading (`0x80|n`) is
  pinned by the exact-closure test on the 0xe7 decoder and by the
  sampled records, not proven corpus-wide for every class.
- **The orientation pin** rests on the battery, not on a stored flag:
  85 non-square nets evaluate only v-major, 0 only u-major.  A square net
  (e.g. 18×18) is orientation-ambiguous by symmetry and takes the pinned
  reading.
- **The no-regret law is structural**, not statistical: the fold happens
  only when a tessellated patch exists; the A/B verifies it on the exact
  changed-candidate set, whose completeness follows from the seam (a
  file's export can only differ when the fallback runs and E5 records
  participate or the grid census feeds it).
- **Selftest**: `--selftest` pins 6 edges (1 positive, 4 E5 negatives,
  tail +/-) as committed synthetic fixtures.

## 9. Reproduce

```bash
cd ~/marathon-wt/w3
.venv/bin/python -B -I scripts/triage/probe_e5_class_table.py --selftest
.venv/bin/python -B -I scripts/triage/probe_e5_class_table.py            # census -> CSVs
.venv/bin/python -B -I scripts/triage/probe_e5_class_table.py --ab \
    --baseline-src /home/alan/catpart-parser/src                          # A/B -> CSV
.venv/bin/python -m pytest tests/test_e5_surface.py -q
(cd port && cargo test --lib geometry::surface)
```

The census pass streams (mmap, read-only, `gc` per file); the A/B runs the
baseline exporter in a subprocess per file.  The corpus on this host was
re-downloaded from the manifest sources (1,755/1,824 sha-valid; 68 files
changed upstream and are excluded from every denominator here).
