# BR6 — B-rep topology graph + STEP export: interface design

**Date**: 2026-11-18 · **Ticket**: #58 (BR6) · **Parent**: Spec G #47 ·
**Base**: `a17b019` (the BR6 shell slice merged; the brief's `d16d5e9`
predates `src/catpart/brep/shell.py`). **Status**: design of record,
implemented as written by `src/catpart/brep/{graph,step_export}.py`.
**Revision**: 2026-11-18, after the independent design review's F1–F14.
The pre-review text was unsound in four measured ways (F1 exact mode
unsatisfiable, F2 ring loops cannot fit the strip classifier, F7 edge
source, F3/F4/F5 provenance and assumption labelling); this note is the
contract, and the code matches it.

Counts are committed claims-CSV rows cited by id. Numbers from other
families: BR2/BR3/BR4/BR5/BR6S rows and BR4's anchor rows; anything not
committed is marked **unverified**.

Consumed, not re-derived (pointers only): [BR2](../evidence/2026-11-17-br2-planar-loops.md),
[BR3](../evidence/2026-11-17-br3-curves.md), [BR4](../evidence/2026-11-17-br4-quadrics.md),
[BR5](../evidence/2026-11-17-br5-cgm-nurbs.md), [BR6 shell](../evidence/2026-11-17-br6-shell.md);
`src/catpart/brep/{planar,curves,quadrics,cgm_nurbs,shell}.py`;
`docs/evidence/data/brep-construct-vocabulary.csv`; units negative:
[units-names-probe](../evidence/2026-11-08-units-names-probe.md) (U2 0/108).

## 1. Node / edge model

Seven node kinds, one per vocabulary topology row. Nothing else becomes a
node: a triangle, a curve record or a CGM id is data on, or a reading of,
an existing node.

| node | produced by (existing call) | claim basis | index space | labels (`export_label`) |
| :--- | :--- | :--- | :--- | :--- |
| `body` | `cgm_nurbs.top01_carrier` → `BodyCarrier` | BR5-04a, BR5-04b | `none` | `("inference",)` |
| `lump` | **no decoder** (BR5-06a, `observations=0`) | BR5-06a | `none` | `("assumed",)` — **blocks export** until `accept_assumed_lump` |
| `shell` | `shell.decode_shells` → `FaceShell` | BR6S-13 closed / BR6S-14 open / BR6S-15 non-manifold | `pool` | `("derived",)` |
| `face` | `planar.decode_planar_face` on `planar.PLANAR_NORMAL_MARKERS` (0x49/0x4a/0x4c) | BR2-01; placed BR6S-19 | `pool` | `("fact","inference")` |
| `loop` | `DecodedPlanarFace.loop_readings` / `record_true_loops` | BR2-07; closure BR2-15 / BR2-16 | as its face | `("fact","reading")` |
| `edge` | **loop segments** of the face loops | BR2-15 ring / BR2-16 strip; BR6S-13 | `pool` | `("derived",)` |
| `vertex` | `pool.scan_pool_groups` slots | T07_pool_count_law | `pool` | `("fact","unknown")` |

**F7 — edges are loop segments, never triangle chords.** The shipped
`facets.decode_soup` reading is retained only for facet-mode triangles
(`FaceData.triangles`, lex-rank triples). An edge is the undirected pair
of corner slots of one consecutive loop segment (`planar.record_true_loops`
inside the face decode): rings (0x4c) close last→first, strips (0x49/0x4a)
do not. This is a *different* law from `shell.decode_shells`' triangle
closure; §5 keeps them apart (BR6S-16 counts directed **triangle** edges,
not loop segments — the pre-review note's category error).

```python
@dataclass(frozen=True)
class Provenance:               # mandatory on every node AND every arc
    decoder: str                # planar|curves|quadrics|cgm_nurbs|shell|facets|pool|composite|derived|user
    construct: str              # vocabulary id, e.g. "TOP-03", "SRF-01"
    claim: str                  # committed claims id, e.g. "BR2-10", "BR6S-13"
    labels: tuple[str, ...]     # every applicable label (F3)
    export_label: str           # the one that gates export; must be in labels
    index_space: str            # pool|composite-element|none
    scope: str                  # the cited row's scope (checked against index_space)
    unit: str                   # model|none|caller-supplied
    anchor: str                 # byte/store anchor, e.g. "record+0x52d2"
    detail: str = ""            # one line: why these labels
```

`export_label` semantics: `fact` (measured field), `inference` (reading of
a measured field), `derived` (computed by a committed law), `reading`
(assertion not byte-measured), `candidate` (a reading with a documented
escape), `assumed` (no evidence for the claim; blocks export),
`unknown` (no reading; blocks export), `user` (caller-supplied).
`no-guess` refuses `unknown` everywhere; `assumed` is declared and blocks
export per construct (`lump-assumed`).

```python
@dataclass(frozen=True)
class Arc:
    kind: str                           # body-lump|lump-shell|shell-face|face-loop|loop-edge|edge-vertex
    parent: NodeId; child: NodeId       # NodeId(kind, index); index = store order per kind
    orientation: bool | None            # loop-edge only: True = traversed edge.start -> edge.end
    provenance: Provenance              # the law that made THIS arc (F11), never the child's
```

`index_space` is the honesty axis and is never inherited: `pool` =
lexicographic ranks into the flattened pool (G3 F2/C8); `composite-element`
= element indices of the decoded list-node region (BR4 §2.1) — **never
materialised by this slice** (no composite element decode; no node carries
it in a built graph); `none` = a byte or store carrier with no coordinates.
`orientation` exists only on `loop-edge`.

**Tuple and id laws (F12).** `nodes` is ordered by kind order
(`body,lump,shell,face,loop,edge,vertex`) then by `index`; `arcs` by arc
kind order, then parent index, child index, orientation (`None,-1`).
Indices are dense `0..n-1` per kind in creation order. Face indices follow
the shell order (`decode_shells`' deterministic component order) then the
component's `face_offsets`. Loop indices follow face order then loop
order. Vertex indices sort by pool lex rank ascending; edge indices by
`(min rank, max rank)`. `EdgeData.start/end` are vertex node indices;
`FaceData.record_offset` is the byte anchor and the offset→face map is the
builder's own dict (store order, never recomputed).

Cardinality: Body→Lump 1..1 (assumed derivation); Lump→Shell 1..n;
Shell→Face, Face→Loop (= `ty`), Loop→Edge (one use per segment) 1..n;
Edge→Vertex exactly 2.

## 2. `src/catpart/brep/graph.py` — public API

```python
INDEX_POOL, INDEX_COMPOSITE, INDEX_NONE = "pool", "composite-element", "none"

@dataclass(frozen=True)
class StoreRef: local_path: str; container: str; body_lo: int; body_hi: int; sha256: str | None = None

@dataclass(frozen=True)
class GraphPolicy:
    derive_single_lump: bool = True     # False -> "lump-undecoded", no lump/shell subtree
    include_open_shells: bool = True    # False -> only closed components become ShellNodes
    coherent_face_surface: bool = True  # False -> FaceData.surface is never assigned

@dataclass(frozen=True)
class SurfaceReading:
    entity: str                          # "PLANE" | "CYLINDRICAL_SURFACE"
    label: str                           # "candidate" for both (F2 symmetry)
    claim: str                           # "BR2-10" (plane) / "SRF-02" (cylinder)
    normal: Point3 | None; offset: float | None                              # plane
    axis: Point3 | None; axis_point: Point3 | None; radius: float | None     # cylinder
    detail: str = ""

@dataclass(frozen=True)
class FaceData:
    record_offset: int; marker: int; loop_count: int
    triangles: tuple[tuple[int,int,int], ...]     # lex ranks; facet mode only
    surface: SurfaceReading | None
    surface_labels: tuple[str, ...]               # per-loop PatchFit labels
    surface_disagreement: bool
    count_variant: bool                           # loop delimitation not established
    oriented: bool | None

@dataclass(frozen=True)
class Node: id: NodeId; provenance: Provenance; data: <kind>Data; status: str

@dataclass(frozen=True)
class Completeness:                    # counts only — rates live in the claims CSV
    body: int; lump: int; shell: int; shell_closed: int; face: int; face_placed: int
    face_unplaced: int; loop: int; edge: int; vertex: int; unknown: int
    skipped_refs: int; excluded_loops: int
    excluded_shells: int = 0           # F13: policy-excluded components
    excluded_faces: int = 0            # F13: records with no FaceNode producer

@dataclass(frozen=True)
class BodyGraph:
    nodes: tuple[Node, ...]; arcs: tuple[Arc, ...]; store: StoreRef
    policy: GraphPolicy; completeness: Completeness
    annotations: tuple[str, ...]       # every derived/assumed/excluded fact, one line each
    status: str                        # "complete"|"unverified"|"lump-undecoded"
    index_space: str = INDEX_NONE      # the store's reference space (F5/F9)

def build_store_graph(data, span: StoreSpan, *, policy: GraphPolicy = GraphPolicy()) -> BodyGraph
def build_part_graph(path, *, policy: GraphPolicy = GraphPolicy()) -> BodyGraph
def check_invariants(graph: BodyGraph) -> tuple[Violation, ...]
```

`build_part_graph` locates the store with **the exporter's probe order**
(`stdcont` → `xdoclink` → `seebody` → every remaining valid block) and
delegates to `build_store_graph`, the only assembler. A part with no
validated store is **not an error**: it yields a graph with no body,
`status="unverified"`, `index_space="none"`, and the sha256 on its
`StoreRef` (the documented 125-of-1,442 no-store population; §4.6
`body-no-shell`).

The builder **calls** shipped functions: `facets.scan_facets` (record
walk, `clean_store=True` on pool-only stores — the F1w store-width
context), `planar.decode_planar_face` (the shipped surface is singular;
`decode_planar_faces` does not exist), `planar.record_true_loops` (inside
the face decode), `facets.decode_soup` (one-record slice — facet
triangles only, never edges), `quadrics.classify_strip_patch` per strip
loop (only to decide `FaceData.surface`), `quadrics.fit_cylinder` (only
for the cylinder's perpendicular foot), `shell.decode_shells` (components,
`FaceShell` fields copied), `cgm_nurbs.top01_carrier`, and
`pool.scan_pool_groups` / `pool.has_composite_space`.

**Surface coherence rule (F2).** Rings and strips follow different laws:

- Ring family (`0x4c`): the record's stored plane is the only surface
  evidence (BR2-10 coplanarity, BR2-06 unit normal). `classify_strip_patch`
  is never called on ring refs — it is a strip law and would label them
  `degenerate` (3 refs) or `pencil-noncyl` (4+); that is construction, not
  geometry.
- Strip family (`0x49`/`0x4a`): `classify_strip_patch` per loop. PLANE iff
  every loop is `planar`/`degenerate` **and** the record plane passes.
  CYLINDRICAL_SURFACE iff every loop is `cylinder` with one axis
  (`|cos| >= CYL_AXIS_COS_MIN = 0.999` — an angular test, because the
  fit's residual is a length) and one radius (`|Δr| <= CYL_RADIUS_REL_TOL =
  1e-2` relative). The axis point is `fit_cylinder`'s perpendicular foot;
  its axial component is unconstrained (BR4 §2.2) and does not change the
  surface.
- Anything else is `surface=None`: cone/sphere/pencil/curved fits never
  become a face surface (BR4 §4: no face-level grouping). Mixed loop
  labels set `surface_disagreement`.
- Both supported surfaces are `label="candidate"`: a planar patch may be a
  curved surface's tessellation (SRF-01) and a torus band is a valid
  cylinder at either equator (SRF-05's upper bound). Same escape class,
  same label (F2).

Status: `complete` iff every placed face closes (`all_faces_closed`), no
record was excluded by the face family, and no unknown record exists;
`unverified` otherwise, with the reason in `annotations`; `lump-undecoded`
when `derive_single_lump=False`.

**Raise boundary (F14).** `build_*` never raise on incomplete or
inconsistent *input* (they degrade to `status="unverified"` and record
why), but a shipped decoder's `ExportError` (`malformed-pool-group`,
`malformed-pool-vertex`, `malformed-store-header`, `unreadable-file`)
propagates unchanged: this layer does not wrap, rename or swallow it.

## 3. Constructs with no decoder that can feed the graph

| need | status | graph behaviour |
| :--- | :--- | :--- |
| Lump (TOP-02) | no detector (BR5-06a, `observations=0`) — **not a cardinality statement** | **assumed**: one lump per body, `export_label="assumed"`, blocks export (`lump-assumed`) until `StepOptions.accept_assumed_lump` (F4) |
| Body count (TOP-01) | BR5-04a/b prove container/root, not a count | exactly one body per located store is a declared **assumption** in the provenance detail (F5); it does not gate export on its own |
| Edge record (TOP-06) | `EdgeGroup`/`PolylineList` decode but bind to no face (BR3 §4) | edges are loop segments; no `EDGE_CURVE` record is read |
| Vertex identity (TOP-07) | slots exact (T07_pool_count_law) | vertex = pool slot; no welding, no dedup, identity `unknown` in `labels` |
| Curve→edge binding | payloads decoded, bound to nothing | line chords of the decoded loops only; analytic curves never emitted |
| Cone/sphere face surface (SRF-03/04) | per-loop fits, no face binding (BR4 §4) | `surface=None`, refusal `surface-unbound` |
| Torus/revolution/extrusion (SRF-05/06/07) | documented-open / candidate | never emitted; a torus-equator cylinder stays `label="candidate"`; SRF-06 has no separable signature |
| NURBS (CRV-06/SRF-08) | documented negative, 0/1,089 (BR5-03a/b) | no `B_SPLINE_*` code path exists |
| Shell record (TOP-03) | documented negative (BR6S-22b/23) | derived partition only |
| Composite element space | undecoded (BR6S-08/BR6S-23) | body + assumed lump only; 0 vertices, 0 shells, `status="unverified"`, refusal `index-space-unplaceable`; never remapped |
| 0x44 unread records | open primitive reading (BR6S-22) | counted in `Completeness.unknown`, `label="unknown"`, no node |

## 4. STEP export contract (`src/catpart/brep/step_export.py`)

```python
SUPPORTED_ENTITIES = frozenset({...})    # §4.1, pinned by a test

@dataclass(frozen=True)
class StepOptions:
    schema: str = "AP214"                # "AP203" | "AP214"
    face_mode: str = "facet"             # "facet" (default, F1) | "exact"
    strict: bool = True                  # §4.6
    outer_shell: NodeId | None = None    # §4.4
    length_unit: str | None = None       # "MM"|"CM"|"M"; None -> unit-undetermined
    accept_assumed_lump: bool = False    # F4: the lump assumption is the caller's

@dataclass(frozen=True)
class StepHeader: name: str = ""; time_stamp: str = ""

@dataclass(frozen=True)
class StepExport:
    text: str; sha256: str; entity_counts: dict[str, int]
    annotations: tuple[str, ...]; refused: tuple[Violation, ...]

def render_step(graph, *, options: StepOptions = StepOptions(), header: StepHeader | None = None) -> StepExport
def write_step(graph, path, *, options: StepOptions = StepOptions(), header: StepHeader | None = None) -> StepExport
```

`render_step` returns text (byte-stability and every negative fixture are
corpus-free). A refused graph never yields text; `write_step` therefore
never writes an empty or partial file.

**4.1 Emitted subset.** `MANIFOLD_SOLID_BREP`, `CLOSED_SHELL`,
`ADVANCED_FACE`, `FACE_OUTER_BOUND`, `EDGE_LOOP`, `ORIENTED_EDGE`,
`EDGE_CURVE`, `LINE`, `VECTOR`, `CARTESIAN_POINT`, `VERTEX_POINT`,
`DIRECTION`, `AXIS2_PLACEMENT_3D`, `PLANE`, `CYLINDRICAL_SURFACE`, the
mandatory context/units chain (`GEOMETRIC_REPRESENTATION_CONTEXT(3)`,
`GLOBAL_UNIT_ASSIGNED_CONTEXT`, `LENGTH_UNIT`, `SI_UNIT`,
`CONVERSION_BASED_UNIT`, `UNCERTAINTY_MEASURE_WITH_UNIT`), plus
`BREP_WITH_VOIDS` only under §4.4. Mapping: Body→`MANIFOLD_SOLID_BREP`,
Shell→`CLOSED_SHELL`, Face→`ADVANCED_FACE`, Loop→`EDGE_LOOP`+
`FACE_OUTER_BOUND`, Edge→`EDGE_CURVE` over two `VERTEX_POINT`s,
Vertex→`CARTESIAN_POINT`+`VERTEX_POINT`. The lump has no entity in this
subset, so its assumed status costs nothing in the file — it costs the
refusal instead. **There is no product structure** (no `PRODUCT`,
`SHAPE_REPRESENTATION`, `APPLICATION_CONTEXT`): the file is the
contract's B-rep subset, not a schema-valid AP214 part, and the first
`FILE_DESCRIPTION` line says so.

**4.2 Measured vs not emitted.** Emitted from measured data: vertex
coordinates (pool f32, `.9g` — deterministic f32 round-trip); plane normal
+ derived offset (BR2-06, BR2-10), with the placement location `−d·n`
annotated as derived; cylinder axis/radius from `PatchFit` (SRF-02) and
the fit's perpendicular foot; triangle windings (facet mode).
**Not emitted, by evidence**: `B_SPLINE_CURVE/SURFACE_WITH_KNOTS`
(BR5-03a/b 0/1,089); `TOROIDAL_SURFACE` (no discriminator, BR4 §3);
`CONICAL_SURFACE`, `SPHERICAL_SURFACE`, `SURFACE_OF_REVOLUTION`,
`SURFACE_OF_LINEAR_EXTRUSION` (decoded per-loop, unbound to faces). Each
is a named refusal, never a silent plane substitution.

**4.3 Face modes (F1).**

- `facet` is the **default**. One `ADVANCED_FACE` per decoded triangle,
  `PLANE` through its three points, three-edge loop; the face name carries
  `derived_from face[k]`. It is complete over any closed shell the graph
  can represent, and it is the only mode with measurable corpus coverage.
- `exact` needs one **closed-cycle** loop — a `0x4c` ring with `ty == 1`
  (BR2-15's 6,462 is a **loop** count, not a face count) — and a PLANE
  decided from that record's stored normal. Therefore a
  `CYLINDRICAL_SURFACE` is **unreachable in exact mode** (a ring's surface
  is the record plane): it is refused `unsupported-surface`, not silently
  translated. Strip faces (open polylines, BR2-16) are refused
  `loop-role-undecided` in exact mode. **Predicted exact-mode corpus
  success: 0/76 closed shells** — the count of closed shells whose every
  face is a 0x4c ring (`BR6G-11c`); published before the run and measured
  as such.
- `ty > 1` is refused (`loop-role-undecided`) in **both** modes: no byte
  marks outer vs inner (BR2 §3, BR2-09). This slice has no role-assignment
  API; a caller-supplied role would be `label="user"`, never a fact.
- A face whose loop delimitation is not established (`count_variant`, the
  BR2-07d class) is refused `face-count-variant` in both modes: the
  triangle geometry survives, the loop structure does not.

**4.4 Shell role.** Every closed shell measures **positive** signed
volume (BR6S-17 76/76, BR6S-18 0), so sign does not identify a cavity.
With >1 closed shell the exporter refuses (`shell-role-undecided`) unless
`outer_shell` is given; then it is the `MANIFOLD_SOLID_BREP` outer shell
and the rest are `BREP_WITH_VOIDS` (label `user`).

**4.5 Header, units, fail-closed.** `FILE_DESCRIPTION` (one line naming
this note + the face mode), `FILE_NAME(name, time_stamp, ('catpart',),
('catpart',), 'catpart brep graph', 'catpart', '')`,
`FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'))` (AP214) or
`FILE_SCHEMA(('CONFIG_CONTROL_DESIGN'))` (AP203) — ISO 10303 identifiers,
**not** corpus-verified. `time_stamp` is caller-supplied (default empty)
so two runs are byte-identical. **Units are a documented negative** (U2
0/108): `length_unit=None` raises `unit-undetermined`; a supplied
`MM`/`CM`/`M` is emitted as `SI_UNIT(prefix,.METRE.)` and annotated
`/* UNIT: caller-supplied <X>; no model unit system decoded (U2 0/108) */`.
`CONVERSION_BASED_UNIT` is in the supported set for a non-SI caller unit,
but no conversion is decoded, so an unknown unit refuses rather than
inventing a factor. The uncertainty is `LENGTH_MEASURE(1.E-7)` in the
supplied unit. **Float format (F12)**: one `_real(value, digits)` —
`-0.0 -> "0."`, always a decimal point, exponent as `E<n>` without `+` or
leading zeros; 9 significant digits for pool f32, 12 for derived doubles.

**4.6 Strictness and refusal classes.** `strict=True` (default) raises
`catpart.geometry.errors.ExportError(error_class, detail)` with the
first refusal in §4.6 order; `strict=False` returns a `StepExport` with
`text=""` and the full `refused` tuple. `refused` maps §5 violations to
classes and holds every export-level refusal. The order is specific-first
(index-space, lump-undecoded, body-no-shell, unknown, provenance,
face-family, count-variant, face-unplaced, shell-*, vertex, surface-*,
loop-role, shell-role, lump-assumed, unit, structure).

Export refusal classes (20): `index-space-unplaceable`, `body-no-shell`,
`lump-undecoded`, `lump-assumed`, `unknown-node`, `provenance-incomplete`,
`face-family-unread`, `face-count-variant`, `face-unplaced`, `shell-open`,
`shell-non-manifold`, `shell-not-oriented`, `shell-not-brep-paired`,
`vertex-not-shared`, `surface-disagreement`, `surface-unbound`,
`unsupported-surface`, `loop-role-undecided`, `shell-role-undecided`,
`unit-undetermined`. Graph-structure refusals (3, not renamed by the
export list): `no-orphan`, `determinism`, `arc-kind-table`.
`edge-not-used-twice` from the pre-review list is **renamed**
`shell-not-brep-paired`: the law it names is the loop-segment pairing, and
the triangle-closure role belongs to `shell-open`/`shell-non-manifold`.

`PatchFit.label → refusal` (F9): `planar` → PLANE (record plane gate);
`cylinder` → CYLINDRICAL_SURFACE (exact: `unsupported-surface`);
`cone`, `sphere`, `curved-unclassified` → `surface-unbound`;
`pencil-noncyl` → `unsupported-surface`; `degenerate` → `face-unplaced`;
mixed labels → `surface-disagreement`.

**Mode filtering.** `exact` and `facet` share the structural refusals
(§5 guarantees, shell status, face family, count-variant, loop roles,
unit, assumed lump). The **loop-segment** laws (`edge-use-pair` and
loop-segment `orientation`) are exact-mode refusals
(`shell-not-brep-paired`); facet mode checks the triangle closure through
`ShellData.status` and `ShellData.oriented` and does not use the graph's
edges.

## 5. Invariants

Four are **load-bearing tests** (negative fixtures per discrimination);
four are **construction guarantees** the builder is expected to keep
(F8: they were vacuous as tests, so they are stated as guarantees and
still reported by `check_invariants`).

Load-bearing:

1. **edge-use-pair** — in a shell every undirected loop segment is used
   exactly twice (F7's law; the corpus expectation, published pre-run, is
   **0/76** closed shells paired and **76/76** with a one-use segment).
   Test: cube passes; open sheet fails; a removed loop-edge arc fails.
2. **orientation** — no directed loop segment is traversed twice.
   Test: inward-wound face; a flipped loop-edge arc.
3. **provenance-complete** — every node, surface claim and arc carries
   the full `Provenance`; `decoder`/`unit`/`index_space`/`export_label`
   are vocabulary members; `export_label ∈ labels`; `claim` resolves to a
   committed `docs/evidence/data/br*claims*.csv` row
   (`row.claim == id or row.claim.startswith(id + "_")`); `scope` is one
   of that claim's row scopes; **scope must not contradict index_space**
   (a composite-scope row cannot justify a pool node, and vice versa) and
   a row naming a unit cannot justify model-unit geometry. The allowlist
   **excludes `br6-graph-claims.csv`** (F6: this note cannot justify its
   own graph). Test: a fabricated id fails; a composite-scope row on a
   pool vertex fails.
4. **no-guess** — `unknown` never reaches a file; `derived`/`assumed`
   require a stated basis in `detail`. Test: an unknown label fails;
   the assumed lump fails until accepted.

Construction guarantees:

5. **no-orphan** — every non-body node is reachable from a body; loops
   have a face use, edges a loop use, vertices an edge.
6. **index-space-homogeneous** — one shell's vertices share one
   index_space (in practice: no composite node is ever attached).
7. **determinism** — dense per-kind ids in store order; two renders of
   one graph are byte-identical (`sha256` equal, no wall clock).
8. **arc-kind-table** — kinds follow §1, parent/child kinds match, and
   the graph is acyclic.

`check_invariants` returns `Violation(code, node, detail, arc=None)` and
never raises, including on hand-built malformed graphs (`arc` is the index
into `graph.arcs`; `node=None`/`arc=None` names the graph itself).
`render_step` turns the set into refusals.

## 6. Test plan and required artifacts

`tests/test_brep_graph.py` (synthetic, no corpus): the cube (1 body, 1
assumed lump, 1 closed shell, 6 faces, 6 loops, 12 loop-segment edges, 8
vertices, all invariants clean); tetrahedron; open sheet (1); inward-wound
cube (2); detached face (5, no-orphan); duplicate-coordinate slots (pool
slot ≠ topological vertex); out-of-pool ref (counted, no vertex); agreeing
cylinder band → CYLINDRICAL_SURFACE; disagreeing loops →
`surface-disagreement`; cone band → no face surface; `ty=2` ring →
`loop-role-undecided` in both modes; count-variant record →
`face-count-variant`; composite store → `unverified`, 0 shells/vertices;
0x42 record in a shell → `face-family-unread`; assumed lump refused and
accepted; no-store part → `body-no-shell`; two closed shells →
`shell-role-undecided` + `BREP_WITH_VOIDS`; fabricated claim and
scope-conflict → `provenance-incomplete`; unknown label → `unknown-node`;
one fixture per remaining refusal class; STEP: `SUPPORTED_ENTITIES`
pinned, exact vs facet counts, round-trip entity counts and reference
resolution, determinism digest, AP203/AP214, float format (`-0`, exponent),
no `B_SPLINE`/`TOROIDAL_SURFACE` text, `write_step` never writes a
refusal.

Artifacts: `docs/evidence/2026-11-18-br6-graph.md` and
`docs/evidence/data/br6-graph-claims.csv` (prefix `BR6G-`, same columns as
the family: `claim,statement,label,scope,release,observations,passes,rate,value`):
BR6G-01 parts with a closed shell; BR6G-02 complete graphs; BR6G-03a..g
node counts; BR6G-04 composite parts; BR6G-05a..d invariant rates;
BR6G-06a/b exact-mode success + per-refusal-class counts; BR6G-07a..c
facet-mode success + refusals; BR6G-08 determinism digest (the sha256
lives in the statement because the family's `value` column is numeric;
`value=2` is the number of byte-identical renders); BR6G-09 unread
records and skipped refs; BR6G-10 lumps per body and unknown nodes
emitted; BR6G-11a..f the face-family/exact-mode anchors (ring faces,
closed-shell face records, ring-only shells, excluded faces).

`scripts/triage/decode_brep_graph.py`: `--selftest` (the synthetic roster
above), `--sha16`/`--include-sha16`, `--limit`, `--corpus-root`, and
`--out` passed explicitly (regeneration rule). The run is deterministic:
same manifest order, same rows, verified by a second run.

L3 counting rule (unchanged): a construct is **resolved** iff a committed
decoder *or* a documented negative covers it; `candidate` is not resolved.
Denominator = the 23 frozen vocabulary rows, never their per-class counts
(BR3 §6.3, BR4 §6.1). `scalars.L3` is reported, never gating (ROADMAP
Phase 7); no-regret keeps comparing L1/L2 only.

## 7. Detector honesty — what this graph does not decode

1. **Composite index space** — 1,036/1,317 stores (BR6S-08), 116,057 face
   candidates (BR6S-23). Rule: body + assumed lump, 0 vertices, 0 shells,
   `status="unverified"`, refusal `index-space-unplaceable`. Never remapped
   onto pool ranks. `skipped_refs`/`excluded_loops` stay 0 and BR4's
   exclusion rows are cited, not re-derived.
2. **`0x44` unread** — the `unknown` class: counted, `label="unknown"`, no
   node (BR6S-22).
3. **Face family** — FaceNodes exist only for 0x49/0x4a/0x4c (the 12B
   normal). A component carrying a 0x41/0x42 record has no FaceNode for
   it: `Completeness.excluded_faces`, and the export refuses
   `face-family-unread`. The corpus's closed shells carry 3 such records
   in 2 shells (BR6G-11e/11f), which is why BR6G-02 is 2 below BR6S-10.
4. **Loop segments ≠ triangle edges** — the pairing law fails on the
   corpus's strip shells (BR6G-05b/c) although their triangle closure
   holds (BR6S-13); exact mode is therefore 0/76 by construction, not by
   a decoder bug.
5. **Record ≠ face, closed ≠ B-rep, chord ≠ curve** — BR2 §5, BR6 §7.
   Such nodes carry `derived`/`inference`, and the first `FILE_DESCRIPTION`
   line names this note plus the face mode, so no consumer reads a faceted
   shell as an exact B-rep.

**Unverified, not committed**: the ISO 10303 schema identifier strings;
the corpus length unit (a negative); the cylinder axial determinacy as a
STEP placement (harmless for the surface, not corpus-measured); the
CYLINDRICAL_SURFACE writer path (unreachable in both modes under the
loop-family rule; kept because §4.1 pins the entity set).
