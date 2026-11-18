# BR6 — B-rep topology graph + STEP export: interface design (pre-implementation)

**Date**: 2026-11-18 · **Ticket**: #58 (BR6) · **Parent**: Spec G #47 · **Base**: `a17b019` (the BR6 shell slice merged; the brief's `d16d5e9` predates `src/catpart/brep/shell.py`). **Status**: design only, no code. This note fixes interfaces, provenance, the STEP subset, invariants and artifact names. Counts are committed claims-CSV rows cited by id; anything not committed is marked **unverified**.

Consumed, not re-derived (pointers only): [BR2](../evidence/2026-11-17-br2-planar-loops.md), [BR3](../evidence/2026-11-17-br3-curves.md), [BR4](../evidence/2026-11-17-br4-quadrics.md), [BR5](../evidence/2026-11-17-br5-cgm-nurbs.md), [BR6 shell](../evidence/2026-11-17-br6-shell.md); `src/catpart/brep/{planar,curves,quadrics,cgm_nurbs,shell}.py`; `docs/evidence/data/brep-construct-vocabulary.csv`; units negative: [units-names-probe](../evidence/2026-11-08-units-names-probe.md) (U2 0/108).

## 1. Node / edge model

Seven node kinds, one per vocabulary topology row. Nothing else becomes a node: a triangle, a curve record or a CGM id is data on, or a reading of, an existing node.

| node | produced by (existing call) | claim basis | index space | label |
| :--- | :--- | :--- | :--- | :--- |
| `body` | `cgm_nurbs.top01_carrier` → `BodyCarrier` | BR5-04a, BR5-04b | `none` | `inference` — container/root structure, not body semantics (BR5 §4) |
| `lump` | **no decoder** (BR5-06a, `observations=0`) | BR5-06a | `none` | `derived` — one per body, `basis="BR5-06a"` |
| `shell` | `shell.decode_shells` → `FaceShell` | BR6S-13 closed / BR6S-14 open / BR6S-15 non-manifold | `pool` | `derived` — no stored record (BR6S-22/23, BR6 §5) |
| `face` | `planar.decode_planar_face` → `DecodedPlanarFace` | BR2-01, BR2-03; placed BR6S-19; unplaced BR6S-20 | `pool` \| `composite-element` | `fact` (record decode), `inference` (record==face, BR2 §5) |
| `loop` | `DecodedPlanarFace.loops` (`record_true_loops`) | BR2-07; closure BR2-15 / BR2-16 | as its face | `fact` (delimitation), `reading` (closure) |
| `edge` | derived from the face's **triangle** edges (`facets.decode_soup`) | BR6S-13, BR6S-16 | `pool` | `derived` — tessellation chord, never a B-rep curve |
| `vertex` | `pool.PoolGroup` / `curves.scan_vertex_pool` | T07_pool_count_law | `pool` | `fact` (coordinate), `unknown` (topological identity) |

```python
@dataclass(frozen=True)
class Provenance:              # mandatory on every node AND every arc
    decoder: str               # "planar"|"curves"|"quadrics"|"cgm_nurbs"|"shell"|"derived"|"user"
    construct: str             # vocabulary id, e.g. "TOP-03", "SRF-01"
    claim: str                 # base claims id, e.g. "BR2-10", "BR6S-13", "BR5-06a"
    label: str                 # "fact"|"inference"|"derived"|"reading"|"unknown"|"user"
    index_space: str           # "pool"|"composite-element"|"none"
    detail: str = ""           # one line: why this label

@dataclass(frozen=True)
class Arc:
    kind: str                           # "body-lump"|"lump-shell"|"shell-face"|"face-loop"|"loop-edge"|"edge-vertex"
    parent: NodeId; child: NodeId       # NodeId(kind: str, index: int) — index = store order per kind
    orientation: bool | None            # loop-edge only: True = traversed edge.start -> edge.end
    provenance: Provenance              # the child's provenance, copied — never re-invented
```

`index_space` is the honesty axis and is never inherited silently: `pool` = lexicographic ranks into the flattened pool (G3 F2/C8); `composite-element` = element indices of the decoded list-node region (stage-3d identity law, BR4 §2.1), skip slots included; `none` = a byte carrier with no coordinates. Two nodes of one shell may not disagree (§5.5). `orientation` exists only on `loop-edge` — it is the winding evidence (BR6S-16) per use; `edge-vertex` arcs are implicit in `EdgeData.start/end`, materialised for the renderer. Cardinality: Body→Lump 1..1 (derived-lump policy); Lump→Shell 1..n (3 pool-only stores carry ≥2 closed shells, BR6S-11); Shell→Face, Face→Loop (= `ty`, BR2 §3), Loop→Edge (one use per segment) 1..n; Edge→Vertex exactly 2.

## 2. `src/catpart/brep/graph.py` — public API

```python
INDEX_POOL, INDEX_COMPOSITE, INDEX_NONE = "pool", "composite-element", "none"

@dataclass(frozen=True)
class StoreRef: local_path: str; container: str; body_lo: int; body_hi: int; sha256: str | None = None

@dataclass(frozen=True)
class GraphPolicy:
    derive_single_lump: bool = True      # False -> status "lump-undecoded", no shells attached
    include_open_shells: bool = True     # False -> only closed components become ShellNodes
    coherent_face_surface: bool = True   # False -> FaceData.surface is never assigned

@dataclass(frozen=True)
class SurfaceReading:                    # the whole supported surface set
    entity: str                          # "PLANE" | "CYLINDRICAL_SURFACE"
    normal: Point3 | None; offset: float | None                            # PLANE: n, derived d
    axis: Point3 | None; axis_point: Point3 | None; radius: float | None   # cylinder
    label: str; claim: str               # "BR2-10" / SRF-02 row; "candidate" for a torus escape

@dataclass(frozen=True)
class Node:
    id: NodeId; provenance: Provenance
    data: BodyData|LumpData|ShellData|FaceData|LoopData|EdgeData|VertexData
    status: str                          # "ok"|"unplaced"|"degenerate"|"unknown"|"unsupported"

@dataclass(frozen=True)
class Completeness:                      # counts only — rates live in the claims CSV
    body: int; lump: int; shell: int; shell_closed: int; face: int; face_placed: int
    face_unplaced: int; loop: int; edge: int; vertex: int; unknown: int
    skipped_refs: int; excluded_loops: int

@dataclass(frozen=True)
class BodyGraph:
    nodes: tuple[Node, ...]; arcs: tuple[Arc, ...]; store: StoreRef
    policy: GraphPolicy; completeness: Completeness
    annotations: tuple[str, ...]         # every derived/assumed fact, one line each
    status: str                          # "complete"|"unverified"|"lump-undecoded"

def build_store_graph(data, span: StoreSpan, *, policy: GraphPolicy = GraphPolicy()) -> BodyGraph
def build_part_graph(path, *, policy: GraphPolicy = GraphPolicy()) -> BodyGraph
def check_invariants(graph: BodyGraph) -> tuple[Violation, ...]
```

`build_part_graph` locates the store (`store.locate_store`, the exporter's probe order) and delegates to `build_store_graph`, the only assembler. The builder **calls** shipped functions: `facets.scan_facets` (record walk) and `facets.decode_soup` (primitive reading — the shell partition's own input, BR6 §3.1), with no local strip/ring law; `planar.decode_planar_faces` for faces/loops/plane, reading `PlaneEquation.offset` rather than recomputing the derived `d` (BR2 §4); `shell.decode_shells` for components, copying `FaceShell` fields into `ShellData` instead of re-walking; `quadrics.classify_strip_patch` per strip loop, **only** to decide `FaceData.surface`; `cgm_nurbs.top01_carrier` (body), `pool.scan_pool_groups` (vertex coordinates) and `composite.decode_region` (`composite-element` space, skip slots `None`).

`FaceData.surface` follows a **coherence rule**: PLANE iff the record's plane passes (BR2-10) and every loop fits `planar`/`degenerate`; CYLINDRICAL_SURFACE iff every loop of the face fits `cylinder` with one axis (within `TOL_PATCH`) and one radius; otherwise `None` plus an annotation naming the disagreeing loops. A cone/sphere/pencil fit never becomes a face surface — BR4 §4 records "no face-level grouping".

## 3. Constructs with no decoder that can feed the graph

| need | status | graph behaviour |
| :--- | :--- | :--- |
| Lump (TOP-02) | no detector (BR5-06a, `observations=0`) | **derived-and-labelled**: one lump per body; never counted decoded |
| Edge record (TOP-06) | `EdgeGroup`/`PolylineList` decode (T06_edge_presence 1,224/1,442) but no face binding, element-space binding not discriminated (BR3 §4) | edges derived from triangle incidence; edge groups kept as `graph.edge_table`, satisfying no invariant, emitting no `EDGE_CURVE` |
| Vertex identity (TOP-07) | slots exact (T07_pool_count_law 1,927/1,927 L2; 2,326/2,326 corpus); identity/order/duplicates not discriminated (BR3 §4) | vertex = pool slot; no welding, no dedup (stated limitation) |
| Curve→edge binding (CRV-01/02/03/07/08) | payloads decoded, bound to nothing | line chords only; analytic curves never emitted |
| Cone/sphere face surface (SRF-03/04) | per-loop fits only, no face binding (BR4 §4) | `surface=None`, `status="unsupported"`, refusal `surface-unbound` |
| Torus/revolution/extrusion (SRF-05/06/07) | documented-open / candidate (BR4 §3) | never emitted; a torus-equator cylinder stays `label="candidate"` |
| NURBS (CRV-06/SRF-08) | documented negative, 0/1,089 (BR5-03a/b) | no `B_SPLINE_*` code path exists |
| Shell record (TOP-03) | documented negative (BR6S-22/22b/23, BR6 §5) | derived partition only |

Fail-closed vs derived-and-labelled is decided **here**, per construct, not by the implementer: `derived` only where a committed row names the negative; otherwise `unknown`, which blocks export.

## 4. STEP export contract (`src/catpart/brep/step_export.py`)

```python
SUPPORTED_ENTITIES = frozenset({...})    # §4.1, pinned by a test

@dataclass(frozen=True)
class StepOptions:
    schema: str = "AP214"                # "AP203" | "AP214"
    face_mode: str = "exact"             # "exact" | "facet"   (§4.3)
    strict: bool = True
    outer_shell: NodeId | None = None    # §4.4
    length_unit: str | None = None       # e.g. "MM"; None -> refusal (§4.5)

@dataclass(frozen=True)
class StepExport:
    text: str; sha256: str; entity_counts: dict[str, int]
    annotations: tuple[str, ...]; refused: tuple[Violation, ...]

def render_step(graph, *, options: StepOptions = StepOptions(), header: StepHeader | None = None) -> StepExport
def write_step(graph, path, *, options: StepOptions = StepOptions()) -> StepExport
```

`render_step` returns text (byte-stability and every negative fixture are testable without the filesystem). Failures raise `catpart.geometry.errors.ExportError(error_class, detail)`; the `detail` cites the violated row id.

**4.1 Emitted subset.** `MANIFOLD_SOLID_BREP`, `CLOSED_SHELL`, `ADVANCED_FACE`, `FACE_OUTER_BOUND`, `EDGE_LOOP`, `ORIENTED_EDGE`, `EDGE_CURVE`, `LINE`, `VECTOR`, `CARTESIAN_POINT`, `VERTEX_POINT`, `DIRECTION`, `AXIS2_PLACEMENT_3D`, `PLANE`, `CYLINDRICAL_SURFACE`, plus the mandatory context/units chain (`GEOMETRIC_REPRESENTATION_CONTEXT(3)`, `GLOBAL_UNIT_ASSIGNED_CONTEXT`, `LENGTH_UNIT`, `SI_UNIT`, `CONVERSION_BASED_UNIT`, `UNCERTAINTY_MEASURE_WITH_UNIT`). `BREP_WITH_VOIDS` only under §4.4. Mapping: Body→`MANIFOLD_SOLID_BREP`, Shell→`CLOSED_SHELL`, Face→`ADVANCED_FACE`, Loop→`EDGE_LOOP`+`FACE_OUTER_BOUND`, Edge→`EDGE_CURVE` over two `VERTEX_POINT`s, Vertex→`CARTESIAN_POINT`+`VERTEX_POINT`. The lump has no entity in this subset (it is the graph's grouping), so its derived status costs nothing in the file.

**4.2 Measured vs not emitted.** Emitted from measured data: vertex coordinates (pool f32, formatted `.9g` — deterministic f32 round-trip); plane normal + derived offset (BR2-06, BR2-10), with the placement location `−d·n` annotated as derived; cylinder axis/radius from `PatchFit` (SRF-02), axis point = the fit's perpendicular foot (the axial component is unconstrained, BR4 §2.2 — the surface is invariant to it, so this is not a guess); triangle windings (BR6S-16). **Not emitted, by evidence**: `B_SPLINE_CURVE/SURFACE_WITH_KNOTS` (BR5-03a/b 0/1,089); `TOROIDAL_SURFACE` (no discriminator, BR4 §3); `CONICAL_SURFACE`, `SPHERICAL_SURFACE`, `SURFACE_OF_REVOLUTION`, `SURFACE_OF_LINEAR_EXTRUSION` (decoded per-loop, unbound to faces). Each is a named refusal, never a silent plane substitution.

**4.3 Face modes.** `exact` needs one **closed-cycle** loop and a decided surface — in practice a `0x4c` ring with `ty == 1` (BR2-15: 6,462 rings; closure is a reading) plus an agreeing PLANE/CYLINDRICAL_SURFACE. Strip faces have open polylines, not boundary cycles (BR2-16: 51,673 strip loops), so refusing them is the honest consequence of "no boundary-cycle byte". `facet` (opt-in) emits one `ADVANCED_FACE` per triangle, PLANE through its 3 points, 3-edge loop, each carrying `derived_from` = its graph face `NodeId`; it is complete over any closed shell and is what makes a coverage claim meaningful. `ty > 1` is refused (`loop-role-undecided`) in both modes unless the caller assigns roles: no byte marks outer vs inner (BR2 §3), and 2,331/54,265 normal-bearing records are multi-loop (BR2-09). A caller-supplied role is `label="user"`, never a fact.

**4.4 Shell role.** Every closed shell measures **positive** signed volume (BR6S-17 76/76, BR6S-18 0), so sign does not identify a cavity. With >1 closed shell (3 stores, BR6S-11) the exporter refuses (`shell-role-undecided`) unless `outer_shell` is given; then it is the `MANIFOLD_SOLID_BREP` outer shell and the rest are `BREP_WITH_VOIDS` (label `user`).

**4.5 Header, units, fail-closed.** `FILE_DESCRIPTION` (one line naming this note + the face mode), `FILE_NAME(name, time_stamp, ('catpart',), ('catpart',), 'catpart brep graph', 'catpart', '')`, `FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'))` (AP214) or `FILE_SCHEMA(('CONFIG_CONTROL_DESIGN'))` (AP203) — ISO 10303 identifiers, **not** corpus-verified. `time_stamp` is caller-supplied (default empty) so two runs are byte-identical. **Units are a documented negative** (A1 negative, U2 0/108): no measured length unit, so `length_unit=None` raises `unit-undetermined`; a supplied unit is emitted and also written as `/* UNIT: caller-supplied <X>; no model unit system decoded (U2 0/108) */`. Refusal classes: `index-space-unplaceable`, `face-unplaced`, `shell-open`, `shell-non-manifold`, `shell-not-oriented`, `loop-role-undecided`, `surface-unbound`, `unsupported-surface`, `lump-undecoded`, `unknown-node`, `provenance-incomplete`, `edge-not-used-twice`, `vertex-not-shared`, `unit-undetermined`, `shell-role-undecided`.

## 5. Invariants (each testable corpus-free)

1. **edge-not-used-twice** — in a closed shell every undirected edge has exactly two loop-edge uses; no boundary edge. Test: tetrahedron passes, open sheet fails. Re-checked at render (the shell's `closed` flag is not trusted).
2. **shell-not-oriented** — every interior edge traversed once per direction (no directed edge twice). Test: inward-flipped tetrahedron face.
3. **no-orphan-node** — every non-body node reachable from a body; every loop has a face, every edge ≥1 use, every vertex ≥1 edge; vertices exist only for referenced pool ranks, so unreferenced points cannot orphan. Test: detached face.
4. **provenance-incomplete** — every node/arc has all four provenance facts, and `claim` matches a committed row (`row.claim == id or row.claim.startswith(id + "_")`) across `docs/evidence/data/br*claims.csv`. That allowlist test is corpus-free, and a fabricated id cannot pass it.
5. **index-space-homogeneous** — one shell's vertices share one `index_space`. Test: a face with one out-of-pool ref is `unplaced` and contributes no vertex (531 such records, BR6S-20).
6. **no-guess** — `unknown` nodes never reach a file; `derived` only with a row naming the negative. Test: an `unknown` lump-like node fails strict render; relabelled `derived` + basis `BR5-06a` renders.
7. **deterministic** — same input, byte-identical text (sha256 equal over two renders, no wall clock, ids from store order). Test: two renders, compare digests.
8. **arc-kind-table** — parent/child kinds follow §1 and the graph is acyclic. Test: an illegal arc is rejected at construction.

`check_invariants` returns `Violation(code, node, detail)` and never raises; `render_step` turns the set into refusals. `build_*` never raise on incomplete input — they degrade to `status="unverified"` and record why; upstream decoder raises keep their named error.

## 6. Test plan and required artifacts

`tests/test_brep_graph.py` (synthetic, no corpus): a cube of 6 `0x4c` `ty=1` rings → 1 body, 1 derived lump, 1 closed shell, 6 faces, 6 loops, 12 edges, 8 vertices; tetrahedron; open sheet (inv 1); inward-wound cube (2); detached face (3); duplicate-coordinate vertices → open shell (pins "pool slot ≠ topological vertex"); out-of-pool ref (5); `ty=2` ring (refusal); agreeing cylinder band → `CYLINDRICAL_SURFACE`; disagreeing loops → `surface-disagreement`; `composite-element` store → `unverified`, zero shells; unknown node (6); bad arc (8); a node whose `claim` is a fabricated id fails the allowlist (4). `tests/test_brep_step_export.py`: `SUPPORTED_ENTITIES` pinned exactly to §4.1; `exact` vs `facet` counts on the cube; one fixture per refusal code; `unit-undetermined` and the unit comment; determinism digest (7); AP203/AP214 `FILE_SCHEMA`; a text scan asserting no `B_SPLINE`/`TOROIDAL_SURFACE`.

Artifacts (ticket #58 §Files): `docs/evidence/2026-11-17-br6-graph-l3.md` (dated section `2026-11-18` inside it if the sibling note's date is kept); `docs/evidence/data/br6-graph-claims.csv`, prefix `BR6G-`, same columns as the family (`claim,statement,label,scope,release,observations,passes,rate[,value]`): `BR6G-01` graphs with ≥1 closed shell (anchor BR6S-04 = 66); `BR6G-02` `all_faces_closed` stores (BR6S-10 = 66); `BR6G-03a..e` node counts per kind (value rows); `BR6G-04` composite `unverified` stores (BR6S-08 = 1,036); `BR6G-05` invariant rates or violation counts; `BR6G-06` `exact`-mode successes + per-refusal-class counts; `BR6G-07` `facet`-mode successes; `BR6G-08` determinism sha256 (value row); `BR6G-09` excluded `0x44` (BR6S-22 = 708) and skipped refs (BR4 78,255); `BR6G-10` derived lumps vs bodies, and `unknown` nodes emitted (must be 0). `docs/evidence/data/br6-l3-claims.csv`, prefix `BR6L-`. `scripts/triage/decode_brep_graph.py` with `--selftest` (the roster above) and `--sha16`/`--include-sha16`; output paths passed explicitly (regeneration rule).

**L3 counting rule fixed here** (the number stays uncommitted until the run): a construct is **resolved** iff a committed decoder *or* a documented negative covers it; `candidate` is not resolved. Denominator = the 23 frozen rows keyed by `construct_id`, never their per-class counts — BR3 §6.3 and BR4 §6.1 record that CRV-04/05/08 and SRF-03..07's frozen counts have no committed generator. The row lands as `scalars.L3 = {"resolved","total","candidate","documented_negative","rate"}`, reported and never gating (ROADMAP Phase 7); no-regret keeps comparing L1/L2 only.

## 7. Open risks — and the labelling rule that keeps them honest

1. **Composite index space** — 1,036/1,317 stores (BR6S-08, BR2-20), 116,057 face candidates (BR6S-23); BR5 landed without one. Rule: nodes are `index_space="composite-element"`, which is unplaceable → 0 vertices, 0 shells, `status="unverified"`, STEP refusal. Never remapped onto pool ranks.
2. **`0x44` unread** — 708 records, all composite, 318/708 past the pool end (BR6S-22/22b/22d), no primitive reading (G3 F9). Rule: counted in `completeness.unknown`, `label="unknown"`, no node.
3. **90,451 excluded loops** — 78,255 skip-ref over 637 files + 12,196 beyond element space over 59 files (BR4 §1, `composite_loops_excluded_share` 0.576437 of 156,914). Rule: every loop count is accompanied by `excluded_loops`/`skipped_refs`; never stated as a total.
4. **Torus/revolution ambiguity** — a torus band is a valid cylinder at either equator and planar at the pole (BR4 §3's five escapes; SRF-05's bound is the whole classified total, 67,919 loops). Rule: `CYLINDRICAL_SURFACE` carries `label="candidate"` + SRF-05's upper-bound claim; SRF-06 is never emitted (no separable signature), SRF-07 stays candidate.
5. **Record≠face, closed≠B-rep, chord≠curve** — BR2 §5, BR6 §7 (closed-octahedron fixture), §3 here. Rule: such nodes are `derived`/`inference`, and the first `FILE_DESCRIPTION` line names the note plus the face mode, so no consumer reads a faceted shell as an exact B-rep.

**Unverified, not committed**: the ISO 10303 schema identifier strings; the corpus length unit (a negative); cylinder axial determinacy as a STEP placement (harmless for the surface, not corpus-measured); how many parts export in either face mode (the run's rows, not this note).
