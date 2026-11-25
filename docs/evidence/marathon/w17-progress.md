# W17 marathon progress (the 00 00 00 01 container family — W10's head-record negative) — round v1

Branch `marathon/w17-head-record`, base 6cfa4da (W10's multi-region
law + seam included). Worker W17, 2026-11-22. Bench state dir (not
committed): `~/.local/state/catpart-parser/w17/`. Every figure traces
to the committed probes named below.

## Scope caveat, measured first

The Submarino snapshot
(`submarine-ssk-tr-1700-s42-ara-san-juan-1.snapshot.20`, 757 parts)
is NOT present on this host — `~/Downloads/` is empty, no snapshot
directory on any mount (the W10-era bench state
`~/.local/state/catpart-parser/w10/` is gone too). Available: the W5
oracle subset (`/tmp/w5/w5-oracle-subset/.../Submarine-Tr-1700-S42-
Catia/`, 254 files, 55 `.CATPart`s) and the public corpus
(`/home/alan/catpart-parser/corpus/`, 1,956 `.CATPart`s). **The four
named container-family parts — LS-Valv-75, LS-Muzzle, BW-Proa-A01B75,
BW-chain-vertical — are not on disk**, so their recoveries are
projected from W10's committed measurements (below), not re-measured
here. The family's decode law is validated on the 4 container
instances the local files carry (the same byte signature, the same
record laws, the same triangulation gate).

## H1 — the container decode law (CLOSED)

W10's negative: the head-window records sit INSIDE the payloads of
walk-FAILING token nodes whose layouts decode under no table-start
shift 0..8, with `00 00 00 01` at the counts end (the named
"second layout family"). Measured (`scripts/triage/
probe_w17_container_scan.py` + `probe_w17_container_decode.py`):

**The family is the raw-array family's continuation.** The committed
stage-4a raw-array fixture already carries the same 4-byte tail field
(`tests/fixtures_gen.py::_composite_raw_node_payload` calls it "the
observed 4-B form"); the container nodes continue PAST the trail
escape instead of ending at it.  Payload layout:

    [29-B header][ff ff 02 00 01][c1][c2]["00 00 00 01"]
    [c1 raw f32 triples — the node's OWN point region]
    [P1g count = 2*c2][c2 four-byte edge entries (XX 00 00 YY) — undecoded middle]
    [facet records — the W10 head records]

Measured on the 4 local instances (one per part, all inside the
CATProdCont store span):

| part | node | c1 | c2 | window nice | window x-asc | trail byte | records | ext recs | tris | manifold | closed |
|---|---|---|---|---|---|---|---|---|---|---|---|
| spoke | 0x10c91 | 12 | 8 | 1.000 | 0.909 | 0x10 = 2*c2 | 4 (0x42/0x4A) | 0 | 12 | yes | open (b=12) |
| Clocke-pf-Spl | 0xeec2c | 146 | 100 | 1.000 | 0.993 | 0xc8 = 2*c2 | 43 (0x42/0x4A) | 2 | 282 | yes | open (b=8) |
| ntu-57YL | 0x2d31a | 156 | 156 | 1.000 | 1.000 | ff + u32le 312 = 2*c2 | 4 (0x42) | 2 | 312 | yes | **closed, oriented (b=0)** |
| acc-Cont-Lft | 0x5149c | 256 | 256 | 1.000 | 1.000 | ff + u32le 512 = 2*c2 | 1 (0x42 k=17 w=2) | 5 | 504 | yes | open (b=12) |

- the count after the window is `2*c2` in all four (P1g-escaped when
  2*c2 >= 255) — the candidate reading of the middle (c2 four-byte
  entries); the entries' content is NOT decoded (refs against c1 do
  not fit; candidate structure, not claimed law);
- the records parse with the COMMITTED record laws
  (`parse_strip_records` + `parse_extended_facet_records`) against the
  container's OWN c1, 0 out-of-bounds in all four, and triangulate
  through the committed `_triangulate` manifold with **0 degenerate
  emissions** — the W10 head records are the failing nodes' OWN
  surface, exactly as W10's negative named;
- prepending them to rep 0 (W10's `probe_u2_adopt` outcome) was the
  MISATTRIBUTION: the records index the container's space, not rep
  0's — against rep 0's smaller space the parse misresolves and emits
  the 11 degenerates W10 measured on LS-Valv-75.

**Later update (2026-11-25)**: on `acc-Cont-Lft` this container rep is
node 5 of 13. The full per-rep reading is now 13 reps / 6,602
triangles / manifold / 0 degenerate / 12 boundary edges; the single-rep
emission still passes L2 with 563 triangles (node 0's territory), so
the multi-region route is not adopted. See
[2026-11-25-acc-cont-lft-single-rep.md](../2026-11-25-acc-cont-lft-single-rep.md).

## The law landed (units)

1. **The multi-region scan's container second chance**
   (`_container_decode` / port `container_decode`): a walk-FAILING
   token node whose counts end carries `00 00 00 01` decodes as its
   own rep — c1 raw f32 triples under the walk's own finite/plausible
   predicate (`_nice`), window end = counts_end + 4 + 12*c1 bounded by
   the payload.  Fail-closed: no marker, window overrun, or one
   implausible coordinate — the node stays skipped (the original walk
   failure).  A node no law decodes keeps W1-B's behavior unchanged.
2. **The container rep's records parse from INSIDE its payload**
   (the rep loop's `parse_lo = npos + 4 + container_window_end`; port
   twin in `mr_emit_reps`): the middle bytes are skipped by the record
   parsers' own header scan — the same skip the single-rep reading's
   record window runs — and the adoption gate (merged manifold + 0
   degenerate) is what makes the reading safe to attempt, not the
   middle's silence.  The container's territory beyond its payload
   carries no records of its own (`walk_end = len(payload)`).
3. **The head guard's law is unchanged outside container payloads**:
   node 0 being a container attributes its interior (the guard parses
   only `[lo, node 0 + 4)`); a record on non-container head bytes —
   e.g. inside a walk-failing node no law decodes — still declines
   (`{n} surviving record(s) precede node 0's region end`, unchanged).
   The `multiregion_container_reps` info field names the count.

Route scope unchanged: the multi-region second chance fires only on
the not-manifold non-empty residue (the committed call-site gate), so
every passer's decode cost and bytes are unchanged unless its own
pre-route emission was not-manifold (the W1-B incidence class).

## Measured effect (local, 55-part oracle subset + corpus)

**The Submarino A/B (757 parts) is not runnable here**; the local
measurements:

- **Container incidence**: 4 of the 55 oracle `.CATPart`s carry
  container nodes (the table above).  Full-corpus incidence sweep
  (`probe_w17_container_incidence.py`, first located store per file,
  no export): **127 of 1,956 public-corpus files carry container
  nodes, 259 container nodes in total, ALL 259 decode under the law —
  0 declines** (`docs/evidence/data/
  marathon-w17-container-incidence.csv`).  The family is corpus-wide,
  not a Submarino quirk: document-heavy repos (Multi-branchable1 ×9
  nodes, Document ×8) and PCB exports (BottomCopper ×5) carry the
  same signature.
- **Byte A/B, oracle subset (55 parts, base 6cfa4da vs head)**:
  PLY sha256 equal on **54/55**; the one difference is the DESIGNED
  adoption: ntu-57YL's container rep (its closed 312-triangle shell
  was silently missing) — 528 vtx/736 tris -> 684 vtx/1048 tris,
  0 degenerate, boundary 288 -> 288 (the container adds a closed
  component), 12 reps -> 13 (`multiregion_container_reps = 1`),
  class pass -> pass.  0 class changes, 0 new degenerates, 0
  timeouts.
- **Parity PLY byte-identical Py=Rust** (release `fidelity-cli
  export` vs `build_export`, sha256): the 4 container parts (spoke,
  Clocke-pf-Spl, ntu-57YL, acc-Cont-Lft) + the W1-B control
  (MB-Frames-middle-centr-YL) — 5/5 equal at head.
- **Projected effect on the named parts** (from W10's committed
  measurements, NOT re-measured — the files are absent):
  LS-Valv-75 (the 3-rep merge manifold + clean; the 3 head records
  are the failing nodes' surface): the containers decode as reps and
  the head guard passes them -> the adoption gate's input changes
  from "declined: 3 surviving records" to a merged 4-rep mesh whose
  per-rep readings are each manifold+clean — the ~5 recoveries W10's
  criterion named.  LS-Muzzle (36 degenerate per-rep emissions) and
  BW-Proa-A01B75 (58): the degenerates came from misattributed
  surface — the container's own space removes the misattribution;
  whether the merged mesh adopts is decided by the gate per store.
  BW-chain-vertical (30+ failing 304-element period nodes): the
  containers decode per node; the ≥2-decodable-nodes gate needs the
  store's walk-exact nodes W10 measured (the 4/31 seam skips) —
  unchanged.

## Tests, gates

- Python: `test_composite_multiregion_container_adopts_own_space`
  (two-node body: table rep + container rep over disjoint spaces,
  adopted, `multiregion_container_reps == 1`, 10/10 triangle split),
  `..._head_guard_keeps_skip_node_records` (a walk-failing node no law
  decodes keeps its records unattributed — the guard still declines),
  `..._head_records_attributed` (records inside a container payload
  are the container's own — the guard passes them).  Fixture builder
  `tests/fixtures_gen.py::_container_node_payload`.
- Port twins: `multiregion_container_adopts_own_space` constructs the
  same bytes function-level (`mr_container_payload`); `container_decode`
  + the guard split + `mr_emit_reps`' parse-start mirror the scan
  fallback.  `multiregion_container_reps` on `CompositeInfo`.
- Gates: ruff clean (repo-wide); pytest **949 passed / 22 skipped**
  (1 process; the skips are environmental — playwright absent, the
  corpus-gated fixtures' corpus paths, console scripts not installed);
  cargo test **231 passed**; cargo fmt clean; clippy -D warnings
  clean; the release fidelity-cli builds.

## Second front — the U4 emission law adopted (W16's handoff)

W16 validated the U4 skip-slot coordinate law on the bench-external
targets and handed the EMISSION change to this lane
(`docs/evidence/2026-11-22-u4-skip-coordinate-law.md` §4: the
degenerate-emission class of dropped loops — the writer's
degenerate-quad convention `(P, X, P, Y)` — has battery-TRUE dup pins
and real surface recoverable under the G3 F7 skip convention).  The
law module landed by cherry-pick (`curves.py` / `curves.rs` / tests /
the A4 runner, 59ae58c — W16's files untouched upstream); the emission
change lives here:

- **the weld splits instead of refusing**
  (`_e0b_dup_pin` / port `e0b_dup_pin`): a dropped loop with a
  degenerate emission used to be refused WHOLE; now
  `_loop_triangles_split` (the identical enumeration, winding flip and
  G3 F7 predicate as `_loop_triangles` — repeated coordinates or the
  exactly-zero cross, winding-invariant) names the collapsed triangles,
  the real remainder welds behind the SAME incremental mesh guard
  (`EdgeGuard.admit`, all-or-nothing on the real set), and the
  split-off count joins the store's degenerate count (the primary
  strips' own convention).  A loop whose every triangle collapses has
  nothing real to weld and stays dropped (the fail-closed arm).
- **tests**: `test_composite_e0b_degenerate_quad_split_welds_real_
  remainder` (the fixture's pinned quad is (P1, P0, P1, P3): triangle
  (1,0,1) collapses, (3,1,0) welds, `degenerate_triangle_count == 0`,
  `curve_entry_split_skips == 1`, manifold; the OLD law dropped both
  — red under the pre-change behavior); port twin
  `dup_pin_degenerate_quad_splits_the_real_remainder` + the
  nothing-real arm.  The port's `multiregion_container_reps` JSON key
  skips None (the fixture-mode Fidelity key-set gate caught the
  divergence).
- **measured A/B (this host)**: the W16 targets (Motor/Audi/Vulcan)
  are absent here — the gains are NOT re-measured; the 0-regression
  side is measured at final head (both fronts):
  - the oracle subset's byte A/B is **54/55 PLY sha-identical** with
    the single diff the container front's designed ntu-57YL adoption
    (above) — the U4 split changes NO oracle part;
  - the official-corpus hit-file A/B (163 rows over the 127
    container-bearing files): **0 class changes, 2 byte changes,
    both DESIGNED GAINS, both deg-0 and Py=Rust parity-OK** —
    moldes/head/head.CATPart 12,523 -> 12,526 tris (`curve_entry_
    split_skips` 18) and povdoigt's SOIC-8 U5Q5 4,521 -> 4,525
    (split 8), each pass -> pass with the L2 degenerate count at 0.
    BOTH byte changes are the U4 front's — the container front
    changes NO hit-file export (their stores either pass through the
    pre-route emission or the container reps do not change the
    merged outcome); its local effect stays the oracle's ntu-57YL
    adoption, and the named Submarino recoveries are projected (the
    files are absent, above).
- **the accounting gate the A/B caught (and its fix)**: the first
  split draft counted the split-off collapsed halves into the store's
  `degenerate_triangle_count` — the L2 gate reads that counter at
  `MAX_DEGENERATE_TRIANGLES = 0` (fitness/runner.py:280, "any skipped
  degenerate triangle is anomalous") and the two gain parts would
  have flipped pass -> degenerate-triangles.  The collapsed half of a
  dup-pinned quad is NOT an emission: the collapse arises from the
  DUP PIN (two loop positions resolve to one written vertex) — the
  writer never emitted a degenerate facet.  The split-off count
  carries its own stat (`split_skips` on the weld's DupPin result,
  `curve_entry_split_skips` on the info, Py + port, absent when 0)
  and the L2 counter keeps the corpus invariant degenerate ==
  0 on passing parts BY CONSTRUCTION (the relaxed-loops pass's own
  precondition, composite.py's T3 comment).
- **W16's measured gains, unchanged from their note** (not
  re-measurable here, cited for the record): Motor 121 tris /
  5,534 mm²; Audi 761 / 13.59M mm²; Vulcan 22,421 / 19.03M mm² gross.

## Reopening criteria

1. The Submarino snapshot returns to a host: run the 757-part A/B +
   the named-4 measurements above; the law's projections become
   measured or falsified there.
2. The container middle (`2*c2`-counted, four-byte entries): decode
   law wanted; its records' neighborhood (right before the first
   facet record) is committed as gap dumps in the bench state dir
   (`gaps/*.gapdump.txt` — regenerated by
   `probe_w17_container_gap.py`).
3. Stores whose EVERY node is a container (no walk-exact table rep):
   the scan now admits a container-only body where >= 2 nodes decode;
   a store with <2 decodable nodes stays not-family.  BW-chain-
   vertical's exact node mix decides whether this arm matters.
4. The corpus A/B on the 127 hit files (base vs head export classes
   and PLY bytes): the heavy tail (files up to 375 MB) makes the full
   sweep slow; it ran serialized (the anti-OOM rule).  The
   oracle-subset byte A/B above is complete; the hit-file A/B lands
   in the bench state dir (`ab-hits-{base,head}.csv`).
