# Evidence: the `CATSurfacicRep` patch sub-records as the **CAT3DFaceGP** mesh (2026-11-21)

**Date**: 2026-11-21
**Status**: COMPLETE. The patch sub-record stream is a real decoded mesh (not an inference): the `0x51` sub-records carry `CAT3DFaceGP` patch data under a pinned byte law, the strict per-sub-record gate plus the in-order assembly (unordered dedup + the incremental `_mesh_safe` guard) produce a manifold mesh on every firing record, and the route opens **13 dev parts** (1,124 → 1,137 L2 dev) with **0 held-out movement**. Parity Python = Rust is **PLY byte-identical** on every firing part and every pattern-bearing neighbor.
**Target**: issue **#63** (T5, part of the #50 L2 residuals — bagrep.md §6 named the stream, the probes pinned the layout; the approved design implemented here).
**Method**: shipped module `src/catpart/geometry/face_gp.py`, export wiring in `src/catpart/geometry/export.py` (`_face_gp_fallback`, between the grid route and the display carriers), Rust port `port/src/geometry/face_gp.rs` + `port/src/geometry/export.rs`; probes `scripts/triage/probe_t63_face_gp.py` (comment 3, 2026-11-20) and `scripts/triage/probe_t63_pairing.py` (the pairing refinement); corpus-free tests `tests/test_face_gp.py` (14) and the port's `face_gp.rs` unit tests (10); claims `docs/evidence/data/bagrep-face-gp-claims.csv` (`FG-01`..`FG-07`); summary block `bagrep_face_gp` on schema `export-summary-v1.json` (additive).

---

## 1. Executive summary

The bag-rep family's last hiding place for real connectivity holds real geometry. Inside a `CATSurfacicRep` class record, the byte pattern `30 04 04 ff ff ff d2 d2` + flag `0x51` opens a patch sub-record carrying a `CAT3DFaceGP` mesh: a kind/counts header at `+57`, a `u16be` index stream after the first `ff 7f` / `01 80` marker, indexed into the record's **declared f32 point array** — whose floats start **one word after the count** (the finding that un-scrambled the probe coordinates and made every array's cleanliness decidable).

With the approved design's strict gate (byte-exact closure, `mult-3` in-bounds indices, no repeated-index triangle, self-manifold) and the in-order assembly (unordered-triangle dedup, first copy wins + the incremental `_mesh_safe` guard), the route fires on **13 corpus parts — all dev, all currently `fail`** — and never on the held-out split:

| Measurement | whole corpus (1,442 parts) |
| :--- | ---: |
| Parts whose face-gp route fires (>= 1 folded triangle) | **13** (all dev) |
| … currently-L2-fail parts that flip | **13** |
| Projected L2 dev | 1,124/1,381 = 0.8139 → **1,137/1,381 = 0.8233** (+0.94 pp) |
| Projected L2 held-out | 57/61 — **flat** |
| Triangles over the 13 parts | **497** (56+154+64+14+25+154+4+5+42+2+2+4+25) |
| Physicality ratio `area / bbox_diag^2` over the fires | 0.35 – 1.09 (all part-scale, all sane) |
| Guard refusals / dedup drops on the corpus | 0 / 0 |
| BLANK → MESH | **CAAMaiUserToolDatabaseCustomization** (+ CAAMaiToolEditionCustomization, the same geometry in the sibling file) |

(The committed fitness run's table is §6.)

## 2. The pinned law

### 2.1 The class-record framing (file-wide)

A bag-rep class record opens at a `u32le` length prefix preceding its name — `CAT3DBagRep` (11) or `CATSurfacicRep` (14) — found anywhere in the file (the probe's boundary law, BOTH names, so a span ends at the next record of either kind). The route walks the `CATSurfacicRep` spans only; on the corpus every carrier's sub-records live there, and scanning both vs surfacic-only measured identical (the design text says `CATSurfacicRep`).

### 2.2 The declared point array — one word after the count

The record's index space is its **largest declared f32 array** (the pairing probe's law): a count-first `u32le` count (`9 <= count <= 3_000_000`, `count % 3 == 0`) whose floats start at `count + 8` — **one non-coordinate word sits between the count and the data**. Measured on every clean array: at the count-adjacent start each array leads with a denormal non-coordinate word (bit patterns 10/18/…); shifted one word, the arrays are fully clean (Plate 118 points, Screw 76, CAAPstPad1_1 118, CAAMai 286, CAKhw 187/417, p1 46). This is the correction that turned the probe's scrambled coordinates into the real part-scale ones.

**Array gates** (fail-closed, whole array):
- candidate filter (bounded head, the probe's): first 96 words finite with `|w| < 1e9`, non-zero share >= 1/2, no constant run over 64 words;
- **full-array coordinate envelope**: every word finite, part-scale (`|w| <= 1e5`, the display envelope's ceiling `grid.COORD_CEIL`), and not denormal junk (`w == 0` or `|w| >= 1e-30`). The corpus's junk arrays are denormal clouds (1e-38..1e-45) and non-finite tails (CAASamplePart's 38-point junk, p2's 3,840-point framing with 2,142 huge + 30 non-finite words, CAAMaiToolEdition's 6,982-point framing — all refused by this gate, all of which the scale-invariant physicality ratio of the earlier probes could not see); the real arrays' sub-floor values are rounding artifacts at 5.7e-14 / 7.3e-15, two-plus orders above the denormal range, so the envelope accepts them.

### 2.3 The `0x51` sub-record decode

`0x50` carries a different counter framing and `0x00` is a boundary artifact — both ignored. The `0x51` sub-record (pattern `30 04 04 ff ff ff d2 d2` + flag):

- `+57..+72`: `kind, N_tris, N_strips, N_fans` as `4 x u32le`; kind **3** = the face GP (all measured sub-records carry kind 3; the gate refuses the rest);
- the stream starts after the FIRST `ff 7f` / `01 80` marker at `>= +73` (earliest of the two; at `+73` when neither appears);
- `N_tris` independent triangles: `3 * N_tris` `u16be` indices;
- `N_strips` strips: `count:u32be` + `count` `u16be` values, windows `(j, j+1, j+2)`;
- `N_fans` fans: `count:u32be` + `count` `u16be` values, triangles `(v0, vj, vj+1)`;
- `v = idx // 3` into the declared array.

The `u16be` framing is the measured one (the t7 `u16le`/stride-3 reading is the parity artifact comment: at the marker-anchored offsets the values read big-endian).

### 2.4 The strict per-sub-record gate (the approved design)

A sub-record is admitted only when EVERY test holds:
1. **byte-exact closure** — the reads end at `pos == rel_len - 1` (the trailing dangling byte; `rel_len` runs to the next `0x51` opening or the span end);
2. **kind 3**;
3. **every raw index `mult-3`** (`idx % 3 == 0` — the writer encodes `3 * vertex_id`);
4. **in-bounds** — `v = idx // 3 < N_declared` (the paired array's point count);
5. **no repeated-index triangle** (`a != b != c != a`) — the pairing probe's degenerate arm. Zero-area triangles with DISTINCT indices (the writer's duplicate pinned coordinates — e.g. Plate's 3 slivers in the 30-triangle stream, CAAMai's one collinear pin) ride as decoded: no skip convention fires and the summary's `degenerate_triangle_count` stays 0 (the route's warning names this explicitly). The alternative reading (refuse any zero-area triangle) would drop the anchors' largest patch streams (Plate 64 → 4 triangles, CAAMai 154 → 4) and contradicts the design's "the 7 close completely";
6. **self-manifold** — every undirected edge of the sub-record's own triangles used at most twice (boundary edges legitimate, G3 F6).

### 2.5 The assembly

Per record, the gated members fold IN ORDER:
- **unordered-triangle dedup**: a triangle whose sorted triple was already folded is dropped (first copy wins, its winding kept — the composite stage-15 lever). The dedup keys and the edge histogram update only on ACCEPT (a refused member leaves no trace);
- **the incremental `_mesh_safe` guard** (composite.py's 2026-11-18 lever, verbatim semantics): a member whose candidate edges would push any undirected edge past two uses is refused WHOLE, histogram and keys untouched (fail-closed, deterministic in sub-record order).

Spans fold independently (disjoint index spaces — one declared array each) and concatenate in file order with index offsets. Measured on the corpus: 0 guard refusals, 0 dedup drops — the gate is doing the work; the levers exist as the design's fail-closed arms (and fire on synthetic fixtures in the tests).

## 3. The route's place in the pipeline

Facet stores → `a5 03 34` B-spline surfaces → structured E5 grids → **face-gp patches (new, `bagrep-face-gp-meshed`)** → display carriers. The route fires only when every earlier route produced nothing; a part with no gated sub-records / no clean array / no folded triangle falls through to the display carriers with its summary byte-identical. The store path's vertices-only success is replaced when the face-gp mesh exists (triangles carry strictly more information than the empty-mesh vertices-only export).

## 4. Corpus measurement (pre-implementation probes + the shipped scan)

The shipped `face_gp.scan_part` re-measured over all 1,442 manifest parts (4.6 s total) reproduces the design-verbatim probe exactly — 13 fires, identical triangle counts:

| Part (split) | before | triangles | vertices | gated/subs | records | ratio area/bbox² | PLY sha256 (Python = Rust) |
| :--- | :--- | ---: | ---: | :--- | ---: | ---: | :--- |
| `CAAPstPad1_1` (dev, DISPLAY) | empty-mesh | 56 | 118 | 1/2 | 1 | 0.3608 | `728ac989d8b0373433feb8cc…` |
| `CAAMaiToolEditionCustomization` (dev, DISPLAY) | empty-mesh | 154 | 286 | 3/6 | 1 | 0.6783 | `99643da66f414ad279de764f…` |
| `Plate` (dev, DISPLAY) | empty-mesh | 64 | 118 | 4/5 | 1 | 1.0904 | `3e6eaae326387287621acfeb…` |
| `CAAPstFunnel` (dev, DISPLAY) | empty-mesh | 14 | 32 | 1/2 | 1 | 0.4064 | `1daa3c29986208531cba7527…` |
| `CAAKhwRuleBaseCreate` (dev, DISPLAY) | empty-mesh | 25 | 604 | 4/17 | 2 | 0.8706 | `ac641bf445e00c48069fe9c3…` |
| `CAAMaiUserToolDatabaseCustomization` (dev, **BLANK**) | missing-geometry-store | 154 | 286 | 3/6 | 1 | 0.6783 | `99643da66f414ad279de764f…` |
| `Pad` (dev, DISPLAY) | empty-mesh | 4 | 16 | 2/5 | 1 | 0.4081 | `129ebbb60cf570a8c0d87e10…` |
| `CAAPstHull` (dev, DISPLAY) | empty-mesh | 5 | 24 | 2/6 | 1 | 0.3485 | `149a9aa545d221a0356f6cf9…` |
| `Screw` (dev, DISPLAY) | empty-mesh | 42 | 76 | 2/3 | 1 | 0.4936 | `5bdfcac61520b662958e7022…` |
| `CAASamplePart` (dev, DISPLAY) | empty-mesh | 2 | 20 | 1/5 | 1 | 0.4762 | `2fc65f493572b4f9004a8dd1…` |
| `p2` (dev, DISPLAY) | empty-mesh | 2 | 19 | 1/5 | 1 | 0.4592 | `537bef206fbaf5f23876571f…` |
| `p1` (dev, DISPLAY) | empty-mesh | 4 | 46 | 2/7 | 1 | 0.4047 | `fcf8c2ac83e2ac3c7c3daff8…` |
| `CAAKhwRuleBaseRead` (dev, DISPLAY) | empty-mesh | 25 | 604 | 4/17 | 2 | 0.8706 | `ac641bf445e00c48069fe9c3…` |

Notes:
- the two CAAMai files are siblings carrying the same geometry: byte-identical PLYs (`99643da6…`), as are the two CAKhw files (`ac641bf4…`) — internal parity checks on the decode;
- `CAAPstPad1_2` (dev, DISPLAY) stays closed: 2 sub-records, both not byte-exact (the gate refuses; fall-through to display unchanged);
- the non-firing carriers with sub-records (rod_3d, Part_ToolMotion, piston_3d, fix_3d, driver_3d, DumpToolPath*, Ehi_*, Nuts*, …) fall through unchanged — their PLY is the empty display PLY (`14d36fb0…`), Python = Rust.

## 5. Parity (Python = Rust)

`fidelity-cli export` vs `catpart-export` over the 13 firing parts + 6 pattern-bearing neighbors that must NOT change (**19/19: PLY byte-identical, summary parsed-document identical**, details §4's table):

| Part family | PLY | summary |
| :--- | :--- | :--- |
| 13 firing parts (Plate, Screw, CAAPst*, Pad, CAKhw*, CAAMai*, p1, p2, CAASamplePart) | byte-identical | identical |
| 6 non-firing pattern-bearing parts (CAAPstPad1_2, rod_3d, Part_ToolMotion, piston_3d, fix_3d, driver_3d) | byte-identical (empty display PLY) | identical |

Plus the corpus-free fixture suites (`tests/test_face_gp.py` 14 tests; `face_gp.rs` 10 unit tests) and the Fidelity fixture matrix (§7 below).

## 6. The committed fitness run

Run `20261121T022927Z-cfb51d` (committed to `fitness/history.jsonl`, report `fitness/reports/20261121T022927Z-cfb51d.json`), **accepted under no-regret** (`dev_rose: true`, `held_out_fell: false`, `l2_dev_rose: true`, `l2_held_out_fell: false`; baseline `20261120T221222Z-6aa551`):

| Scalar | before (`…b2f7d8`, the #65 probe row) | after (`…cfb51d`, this run) | movement |
| :--- | ---: | ---: | :--- |
| L1 dev | 1,745/1,751 = 0.9966 | 1,745/1,751 = 0.9966 | flat |
| L1 held-out | 73/73 = 1.0000 | 73/73 = 1.0000 | flat |
| **L2 dev** | 1,124/1,381 = 0.8139 | **1,137/1,381 = 0.8233** | **+13** (+0.94 pp) |
| L2 held-out | 57/61 = 0.9344 | 57/61 = 0.9344 | **flat** |
| L3 | 23/23 = 1.0000 | 23/23 = 1.0000 | flat |

Exactly **13 row changes** corpus-wide — every one a `fail → pass` flip among the §4 firing parts (12 `empty-mesh` DISPLAY rows and the `CAAMaiUserToolDatabaseCustomization` **BLANK** row, `missing-geometry-store` → MESH with 154 triangles / 286 vertices). Every flipped row's mesh is `manifold: true` with `failed_check: null`. No other row changed: the pre-face-gp outputs are byte-identical (§5's non-firing neighbors).

## 7. Decisions and fail-closed arms

- **kind 3 gate**: measured neutral on the corpus (every `0x51` sub-record carries kind 3); kept as the design's header law.
- **degenerate reading**: repeated INDEX (the probe's verdict arm), not zero area — §2.4 item 5 documents why.
- **the array envelope** (`|w| <= 1e5`, denormals refused, all-finite required): the shipped hardening over the probe's head-only check — it is what refuses the junk arrays (§2.2) and it keeps the bbox finite (the PLY/JSON contracts).
- **no-regret**: the route sits behind three earlier routes and only ever turns a `fail` row into a pass (13 dev flips) or leaves every byte identical; held-out untouched.
