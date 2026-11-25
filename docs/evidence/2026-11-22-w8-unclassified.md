# W8 — the `fail-unclassified` Top-1 is closed; the residual names itself

Base: dae7dd1 (W7 final). Branch: `marathon/w8-unclassified`. Corpus
availability on this host: the official corpus re-downloaded corpus-wide
(1,380 hash-verified `.CATPart` parts); the submarine 757-file snapshot
is NOT on this host — only the W5 oracle subset (55 parts, 137 MB,
`/tmp/w5`), so submarine-wide numbers come from the committed W7 parity
CSVs, not a fresh full run. Claim status follows the dispatch template:
**fact** (byte/probe evidence, reproduction given) / **inference**
(labeled) / **unknown** (reopening criterion named).

## 1. The W6 Top-1 is a stale label, not a residue (FACT)

W6's `top-targets.md` row 1 — 366 `fail-unclassified`, 1.09M triangles,
529 MB — was computed from `bench-submarine/m1_files.csv`, the W1-era
bench whose rows carry no `error_class`/`failed_check` naming columns
(`w6_build_features.py` reuses it verbatim: "all already committed on
this branch, no parser invocation here"). Every submarine failure was
therefore labeled `fail-unclassified` regardless of cause.

At base dae7dd1 the per-file harness names every failure
(`runner.py::_score_export` records `failed_check`; `ExportError`
carries `error_class`), and the label law
(`status != pass` with BOTH naming fields empty) yields **zero rows**:

- all 13 committed fitness reports (2026-11-07 → 2026-11-21, 1,824
  files each): 0 unclassified;
- the W7 parity CSVs (`w7-parity-claims-{python,fast,rust}-sub757.csv`,
  757 submarine files × 3 engines): 0 unclassified;
- the committed census tool first-hand over the same inputs
  (`scripts/triage/w8_unclassified_census.py census`): 3,713 rows, 0
  unclassified (`data/w8-unclassified-census.csv`);
- first-hand export-gate run at base over the local 55-part subset:
  pass 33 / not-manifold 17 / empty-mesh 3 / degenerate 2 / 0
  unclassified.

Where the 366 went (submarine, python engine rows): 277
`check:not-manifold` (637,431 tris), 19 `check:degenerate-triangles`
(43,372), 13 `check:empty-mesh` (0), 2 errors, and the rest flipped to
pass (446 pass rows today, 1,142,159 tris — the named-fail mass is 311
files / 680,803 tris). The Top-1 mass is fully owned by named families:
**not-manifold → W1-B handoff**, **empty-mesh → W3 handoff**,
**degenerate-triangles → the facets emission guard**,
**missing-geometry-store → closed negative** (CATCGRCont).

Reopen criterion: any future harness row with `status` ∉ {pass,
unavailable-on-disk} and both `error_class` and `failed_check` empty.
The census tool re-derives the label from any parity CSV or fitness
report — run `... census --parity-csv <file> --out <csv>`.

## 2. Taxonomy by binary signature (the brief's step 1, measured corpus-wide)

`w8_unclassified_census.py taxonomy` clusters every `.CATPart` by the
brief's signature: detected version, container-table shape (block count
+ names hash), per-located-store body signature (body size bucket, pool
groups via the exporter's own pool scan, wrapper sub-kinds,
facet-candidate bucket, first header at `body_lo`) — the store walk
mirrors `_export_store_data` verbatim (named probes, then stage-12
`other-container`, early stop on a located family). The corpus-wide run
mmaps each file flat (anti-OOM: the 375 MB moldes part stays
page-cached). Rows: `data/w8-unclassified-clusters.csv` — 1,435 files
(1,380 hash-verified corpus parts + the 55-part W5 submarine subset;
the 3.5 GB snapshot is not on this host, so the submarine-wide
taxonomy stays OPEN — completing it is `rglob` the snapshot dir through
the same tool). 725 clusters; ranked by residual ROI (files x triangles
over FAILING members only; zero-mesh failures rank files x 1):

- The top failing clusters are single-file W1-B handoffs:
  `check:degenerate-triangles` 1 file x 224,435 tris (V5R21,
  LedStrips-class store, 1 pool + `01 02` edge group + `ff 4e`
  composite space) and four `check:not-manifold` singles (2,984 /
  2,242 / 1,702 / 15,860 tris) — all with pools + composite-space
  wrappers, all W1-B territory.
- Submarine subset (55 files, V5R26SP0HF0): one located store per file,
  recovered through the stage-12 `other-container` family from
  **CATProdCont** blocks (`store_recovery` names it on every summary;
  Bitt.CATPart reproduced first-hand). The located bodies carry **no
  `01 06` pool wrapper and no `01 02` edge group** (kinds empty, pools
  0) with 1–>64 facet-header candidates — the exports ride the
  stage-13 second-chance element-space route (the stage-13 note's
  corpus behavior, re-observed). Cluster splits are body-size ×
  facet-candidate buckets; the biggest is 8 files × 95,192 tris.
- The 10 official `error:undecoded-variant` files (37–84 KB CAA
  fixtures): all share ONE signature — a located, validated
  `CATStdCont` store whose body is 648–2,575 B with **zero pool
  groups, zero wrapper markers, zero facet candidates** (10/10
  measured first-hand, sha-verified downloads).
- A 5-file `check:empty-mesh` cluster shares the empty-payload store
  body behind a `CATSeeBodyCont` probe — their exports are
  vertices-only through the second-chance route (0 triangles), a
  related but distinct family the empty-geometry law does NOT rename
  (their stores still export; renaming would misstate an exporting
  store as empty).

## 3. The W8 law: `empty-geometry-store` (the brief's step 2, in-territory cluster)

The 10-file cluster is the one residual cluster that is (a) ≥5 files
with a shared binary signature, (b) not a closed negative (its error
family is `undecoded-variant`, not `missing-geometry-store`; no
`CATCGRCont` walk involved), (c) not W1-B/W2-B/W3 territory (no
composite/facets/mesh/brep/surface code touched). Its honest family:
**a store that locates and validates but carries no geometry payload of
any pinned kind** — there is nothing to decode, so `undecoded-variant`
("a variant the decode families do not cover") is the wrong name.

Law (`src/catpart/geometry/unclassified.py` + twin
`port/src/geometry/unclassified.rs`, wired at the no-pool raise in
`export.{py,rs}`):

- fires ONLY on the no-pool decline arm (flattened pool empty), when
  `kinds == []` AND facet candidates == 0 AND pool groups == 0;
- any wrapper marker or facet candidate keeps `undecoded-variant`
  verbatim (fail-closed: a body with markers is a real variant gap);
- the stage-13 second-chance route runs unchanged after the error
  object is constructed — every store that exports still exports
  (row-identical), the object is discarded on success.

Flip (claim rate): **10/10** official `error:undecoded-variant` →
`error:empty-geometry-store` (first-hand rerun of all ten; detail cites
the signature + the evidence note). The submarine file
`LS-seg-22.CATPart` (the 757-corpus's single `undecoded-variant`) is
not on this host: fail-closed, it keeps its base class unless its
decline store matches the empty-payload signature — measured when the
snapshot is available (unknown, reopen with the same tool).

Parity: the fidelity fixture-mode pin gains the
`geometry-empty-body` fixture (empty store body) — Python ≡ Rust on the
class (same refusal row, both engines), in the committed vocabulary
checks (`test_port_fidelity.py` known_classes, `errors.rs` vocabulary
test). Full gates green: ruff, pytest (972 passed), cargo
fmt/clippy/test (230 lib + integration), wasm32 build clean, claims-CSV
quoting.

## 4. Corpus-wide sweep at HEAD (FACT, this host)

`/tmp/w8-sweep.py` (stdlib, one file in RAM, PLY → /dev/null; parts
>50 MB take their committed-report verdict instead of a first-hand
decode — anti-OOM guard) over the 1,380 hash-verified corpus parts at
HEAD, committed as `data/w8-corpus-sweep-w8.csv` (source column names
`head-decode` vs `report-d2c9ff`). The sha256-join against the d2c9ff
fitness report: 1,380 joined, **1,369 identical, 10 moves = exactly the
`undecoded-variant → empty-geometry-store` flips**, 1 move = a sweep
harness artifact (the script's degenerate threshold was `>10` while the
gate pins `MAX_DEGENERATE_TRIANGLES = 0`; the file's decode counts are
byte-identical: 51,369 tris / 3 degenerate — not a code regression).
Zero classification regressions.

## 5. Open questions carried forward

- Submarine-wide taxonomy: still pending (host gap, not an analysis
  gap); the LS-seg-22 flip itself closed 2026-11-25 (see the later
  update below).
- The empty-geometry-store parts' geometry, if any, lives outside the
  nested stream store (CGM B-rep containers — the W2 handoff's
  territory); two of the ten carry a large CATCGRCont block, and the
  CATCGRCont walk stays a closed negative per the wave coordinator.

## Later update (2026-11-25)

The snapshot is available in this checkout. `LS-seg-22.CATPart` now
exports a closed **614-vertex / 1,156-triangle** mesh through
`identity-multiregion` (18 reps, 0 degenerate, 0 boundary edges), so
the `undecoded-variant` flip is closed. The Submarino-wide taxonomy
re-run remains pending.
