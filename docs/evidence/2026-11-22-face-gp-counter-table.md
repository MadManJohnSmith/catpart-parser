# Evidence: the `0x50` counter-table sub-records — the second face-gp framing (w4, 2026-11-22)

**Date**: 2026-11-22
**Status**: COMPLETE. The `0x50` sub-records the shipped face-gp route
ignored ("a different counter framing") decode under a pinned law:
**kind 0** at the same `+57` header, the `u16be` stream at `+74` —
`3 * N_tris` values, a **u16be count table** (one count per strip, then
one per fan), then the concatenated values — with byte-exact closures
at `rel_len - 1` on **100/100** measured sub-records. The same strict
gate (the framing's kind, closure, mult-3 in-bounds indices, no
repeated-index triangle, self-manifold) admits 84 of them; folded with
the `0x51` members they raise the route to **14 fires** (13 baseline
fires kept or gained, **0 regressions**) with **1 new fire**
(`CAAPstPad1_2`, L2 fail → pass). Parity Python = Rust is **PLY
byte-identical on 49/49** measured parts.
**Scope**: the 44-carrier face-gp population (the `bagrep-probe.csv`
rows with sub-records + the `CAAMaiUserToolDatabase` extras +
`p1`/`p2`/`CAAMaiToolEditionCustomization`, the files the shipped
census missed) — the whole population the face-gp route can fire on.
**Method**: shipped module `src/catpart/geometry/face_gp.py` (the
counter-table decode + the either-kind sub-record framing), Rust port
`port/src/geometry/face_gp.rs`; sweep
`docs/evidence/data/w4-face-gp-sweep.csv` (one row per firing part);
claims `docs/evidence/data/w4-face-gp-counter-table-claims.csv`
(`FG2-01`..`FG2-08`).
**Later update (same day)**: the honest open-rate re-measure —
§5 of [2026-11-22-feature-tree.md](2026-11-22-feature-tree.md) carries
the combined w4 numbers.

---

## 1. Executive summary

| Measurement | Value |
| :--- | ---: |
| `0x50` sub-records in the carriers' `CATSurfacicRep` spans | **100** (89 census files' + p1/p2/ToolEdition's) |
| … closing byte-exact under the counter-table law | **100/100** |
| … admitted by the strict gate | **84** |
| Full-corpus fires (1,762 available parts) | **14** (13 baseline + `CAAPstPad1_2` new) |
| Regressions (a baseline fire losing triangles) | **0** |
| Held-out fires | **0** |
| Baseline fires that gain triangles | **8** |
| Parity (Python = Rust) over the carriers + neighbors | **49/49** PLY byte-identical |
| Projected L2 dev | 1138/1381 = 0.8240 → **1139/1381 = 0.8248** (+1) |
| The one open framing (before the first class record) | **445 sub-records, documented negative** (§4) |

## 2. The pinned law

A `0x50` sub-record (pattern `30 04 04 ff ff ff d2 d2` + flag `0x50`)
decodes:

1. `kind, N_tris, N_strips, N_fans` as `4 × u32le` at `+57` — the same
   header the `0x51` framing carries, with **kind 0** (every measured
   sub-record carries kind 0; `0x51` carries kind 3; the gate takes the
   framing's kind);
2. one pad word at `+73`, then the `u16be` stream at **`+74`**:
   `3 * N_tris` values (the independent triangles), then the **count
   table** — one `u16be` count per strip, then one per fan (header
   order) — then the table's values **concatenated in the same order**;
3. strips decode through their sliding windows `(j, j+1, j+2)`, fans
   from their first vertex — the same primitive laws as `0x51`, with
   the count delivered by the table instead of per-strip `u32be`
   headers;
4. the reads close byte-exact at `rel_len - 1` (the trailing dangling
   byte — the same closure law `0x51` obeys); every value is
   `3 * vertex_id` into the span's declared array.

**The either-kind sub-record framing.** The writer emits `0x50`/`0x51`
**interleaved** inside a `CATSurfacicRep` span (CAKhw 33 × `0x50` +
17 × `0x51`; CAAMai 11 + 6; Plate 4 + 5). A sub-record's extent ends at
the **next sub-record of either kind**: the shipped `0x51`-only framing
ran a `0x51` span across the interleaved `0x50` bytes and could not
close (CAKhw @236932: `closed = false` with `rel_len = 270`, `closed =
true` with `rel_len = 177` under the either-kind framing — 16 gated
triangles it refused before). Every baseline fire keeps or gains under
the corrected framing; none loses a gated member.

## 3. What the corpus does

The full-corpus sweep (1,762 available parts of 1,824 manifest rows;
62 unavailable — §5) with the shipped `face_gp.scan_part`:

| Part | baseline | now | movement |
| :--- | ---: | ---: | :--- |
| `CAAPstPad1_1` | 56 | 112 | gain (+56, the 0x50 strip) |
| `CAAMaiToolEditionCustomization` | 154 | 418 | gain |
| `Plate` | 64 | 100 | gain |
| `CAAPstFunnel` | 14 | 30 | gain |
| `CAAKhwRuleBaseCreate` / `Read` | 25 | 559 | gain (both spans) |
| `CAAMaiUserToolDatabaseCustomization` | 154 | 560 | gain |
| `Screw` | 42 | 102 | gain (5 × 0x50 strips + strips of triangles) |
| `Pad`, `CAAPstHull`, `CAASamplePart`, `p1`, `p2` | 4/5/2/4/2 | unchanged | (their 0x50 records refuse the gate or absent) |
| **`CAAPstPad1_2`** | 0 (L2 fail, empty-mesh) | **30** | **new fire, fail → pass** |

Every folded mesh stays manifold (the per-sub-record gate + the
assembly guard are the same construction-guarantees as before), the
degenerate count stays 0, and the physicality ratios stay part-scale
(Screw 0.877, Plate 1.101, `CAAPstPad1_2` 0.173; CAKhw's fuller
coverage reaches 2.2–2.5 — a mesh covering more of the part's bbox
surface, not an anomaly; the ratio is `area / bbox_diag²` and a
box-like part's surface exceeds `diag²`). **Held-out: 0 fires.**

**Parity**: Python `catpart-export` vs Rust `fidelity-cli` over the
44-carrier population + the non-firing pattern-bearing neighbors:
**49/49 PLY byte-identical, summaries parsed-document equal**. The
unchanged fires keep their committed PLY hashes (`Pad 129ebbb6…`,
`CAAPstHull 149a9aa5…`, `CAASamplePart 2fc65f49…`, `p1 fcf8c2ac…`,
`p2 537bef20…`) and the non-firing neighbors keep the empty display
PLY (`14d36fb0…`). The new `bagrep_face_gp` block fields
(`sub_records_counter`, `sub_records_counter_gated`) ride additively.

## 4. The one open framing — documented negative

445 sub-records (217 × `0x50`, 228 × `0x51`, in 33 files) sit **before
the first class record** (in the unnamed payload regions the census
documented). Extending the scan there has **no pairing law**: pairing
each no-span run with the largest clean declared array in a 4 MB
pre-record window gates **0 of 445** — 32 of the 33 files carry no
clean declared array in the window at all, and the one window with an
array (`AnalysisMechfeat`, 21 points) gates 0 sub-records. The census's
point arrays live there but fail the face-gp envelope (denormal clouds
and non-finite tails — the refusal the 2026-11-21 note already named).
Claim `FG2-07`; no second attempt (the pairing arm itself is empty).

## 5. The fitness-run caveat (honest scope)

A committed fitness run **cannot execute honestly on this host**: the
corpus's `Apoloo13/ASE_III` files (69 manifest rows, 62 `kind=part`
dev) changed upstream after the 2026-11-07 freeze and are
unrecoverable — the repo's history verifies **7/69** manifest shas at
best (the writer force-pushed; 40 commits probed). A run here would
record 60 baseline L2 passes as `unavailable` (counted not-pass,
`runner.py` §"unavailable rows count as not clean") and be **rejected
spuriously**. The no-regret evidence is therefore carried by the sweep
+ parity above: the change is scan-local (the face-gp route, behind
three earlier routes), the fire set only grows (13 kept + 1 new, 0
regressions, 0 held-out), and every changed row re-verifies
manifold/degenerate/bbox by construction. **Projected L2 dev
1139/1381 = 0.8248** (+1: `CAAPstPad1_2`), held-out flat.

## 6. Reproduction

```bash
export LD_LIBRARY_PATH=/usr/lib:${LD_LIBRARY_PATH:-} TMPDIR=/home/alan/.cache/t3-tmp
# the subset download (the named populations) or full:
python3 -I scripts/triage/download_corpus_subset.py            # everything missing
# the full-corpus sweep (the fires table):
.venv/bin/python - <<'PY'   # scan_part over the manifest's part rows
PY
# the counter-table micro-check (any carrier):
.venv/bin/python -I scripts/triage/probe_d2d2_section_dump.py Plate
```

Deterministic: manifest order, no randomness; the sweep CSV is
byte-identical across runs.

## 7. Files

- `src/catpart/geometry/face_gp.py` + `port/src/geometry/face_gp.rs` —
  the two framings, the either-kind extents, the per-framing kind gate.
- `docs/evidence/data/w4-face-gp-sweep.csv` — the fires table.
- `docs/evidence/data/w4-face-gp-counter-table-claims.csv` — `FG2-01`..`FG2-08`.
