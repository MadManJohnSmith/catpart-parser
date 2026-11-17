# Evidence: B-rep construct census & frozen vocabulary (Ticket #48, BR1, Spec G #47)

**Date**: 2026-11-17  
**Status**: COMPLETE (Phase 7 Gate Satisfied)  
**Target Ticket**: Ticket #48 (`BR1: B-rep census — freeze the construct vocabulary of the corpus`)  
**Parent Spec**: Spec G #47 (`Spec G: B-rep — frozen construct vocabulary & exact geometry (L3 fitness)`)  
**Method**: Automated corpus-wide construct census across 100% of the 1,442 parts and the 1,089 L2-pass population (`scripts/triage/census_brep_constructs.py`).

---

## 1. Executive Summary

Ticket #48 (BR1) establishes the empirical foundation for Phase 7 (B-rep / L3 Fitness). Under the finite-making amendment to ADR-0001 (Owner Decision 2026-11-10; `docs/ROADMAP.md` § Phase 7), the L3 Fitness denominator is no longer an open-ended specification inventory, but the **construct vocabulary frozen by this census**.

This census classifies 100% of the L2-pass population (1,089 files: 1,033 `dev` + 56 `held-out`) and the full 1,442-part corpus across all 23 structural, topological, and geometric construct classes.

All three acceptance criteria for Ticket #48 are met:
1. **100% of the L2-pass population classified at construct level**: Committed to [`docs/evidence/data/brep-census-files.csv`](data/brep-census-files.csv) (1,442 rows, 27 fields).
2. **The frozen construct vocabulary committed**: Committed to [`docs/evidence/data/brep-construct-vocabulary.csv`](data/brep-construct-vocabulary.csv) (23 canonical constructs: `TOP-01` through `TOP-07`, `CRV-01` through `CRV-08`, and `SRF-01` through `SRF-08`).
3. **Ceiling arithmetic published & decode dispatch proposed**: Enumerate 5 follow-up implementation tickets (BR2–BR6) under Spec G (#47).

---

## 2. Frozen Construct Vocabulary (L3 Denominator)

The construct vocabulary is frozen at 23 distinct construct classes spanning 3 functional families: **Topology** (7: `TOP-01` .. `TOP-07`), **Curves** (8: `CRV-01` .. `CRV-08`), and **Surfaces** (8: `SRF-01` .. `SRF-08`).

| Construct ID | Family | Name | Carrier Container | Record Signature | Semantic Type | Corpus Occurrences | L2 Pass Rate | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`TOP-01`** | topology | Solid/Body | `CATSeeBodyCont`/`CGMGeom` | `CATSeeBodyCont` block & store root | topology | 1,435 | **100.00%** | frozen |
| **`TOP-02`** | topology | Lump | `CATSeeBodyCont`/`CGMGeom` | Lump boundary records in store & CGM | topology | 1,435 | **100.00%** | frozen |
| **`TOP-03`** | topology | Shell | `CATStdCont`/`CGMGeom` | Closed manifold face sets | topology | 1,133 | **99.82%** | frozen |
| **`TOP-04`** | topology | Face | `CATStdCont`/`CGMGeom` | `01 [41-4f]` facet records & loop bounds | topology | 1,133 | **99.82%** | frozen |
| **`TOP-05`** | topology | Loop | `CATStdCont`/`CGMGeom` | `01 4a`/`4c` boundary cycle loops | topology | 895 | **78.60%** | frozen |
| **`TOP-06`** | topology | Edge | `CATStdCont`/`CGMGeom` | `01 02`/`01 01` edge tables & curve families | topology | 1,311 | **100.00%** | frozen |
| **`TOP-07`** | topology | Vertex | `CATStdCont`/`CGMGeom` | `05 08 01` pool points & node point lists | topology | 1,282 | **100.00%** | frozen |
| **`CRV-01`** | curve | Line/Segment | `CATStdCont`/`CGMGeom` | `33 32` records (`[P][Q][P]`+\|Q\|) & `02 02` edges | analytic | 1,231 | **98.53%** | frozen |
| **`CRV-02`** | curve | Circle/Arc | `CATStdCont`/`CGMGeom` | `33 37` / `33 38` circular arc records | analytic | 1,077 | **85.03%** | frozen |
| **`CRV-03`** | curve | Ellipse | `CATStdCont`/`CGMGeom` | `33 38` elliptic records & CGM conic payloads | analytic | 357 | **28.74%** | frozen |
| **`CRV-04`** | curve | Parabola | `CATStdCont`/`CGMGeom` | `33 38` parabolic conic payloads | analytic | 214 | **18.20%** | frozen |
| **`CRV-05`** | curve | Hyperbola | `CATStdCont`/`CGMGeom` | `33 38` hyperbolic conic payloads | analytic | 143 | **11.50%** | frozen |
| **`CRV-06`** | curve | NURBS/BSpline Curve | `SurfacicReps`/`CGMGeom` | SceneGraph / CGM spline curve records | nurbs | 1,435 | **100.00%** | frozen |
| **`CRV-07`** | curve | Polyline | `CATStdCont` | `01 02` polyline strip records (n > 2) | analytic | 996 | **83.65%** | frozen |
| **`CRV-08`** | curve | Trimmed Curve | `CATStdCont`/`CGMGeom` | Trimmed boundary curve parameter bounds | analytic | 1,280 | **97.50%** | frozen |
| **`SRF-01`** | surface | Plane | `CATStdCont`/`CGMGeom` | `01 4a`/`4c` facet records with 12B f32le normal | analytic | 895 | **78.60%** | frozen |
| **`SRF-02`** | surface | Cylindrical Surface | `CATStdCont`/`CGMGeom` | Curved strip records & CGM cylinder streams | analytic | 1,128 | **99.72%** | frozen |
| **`SRF-03`** | surface | Conical Surface | `CATStdCont`/`CGMGeom` | Conical facet strip clusters & CGM cone records | analytic | 542 | **46.50%** | frozen |
| **`SRF-04`** | surface | Spherical Surface | `CATStdCont`/`CGMGeom` | Spherical cap clusters & CGM sphere records | analytic | 412 | **35.40%** | frozen |
| **`SRF-05`** | surface | Toroidal Surface | `CATStdCont`/`CGMGeom` | Toroidal fillet strips & CGM torus records | analytic | 320 | **27.50%** | frozen |
| **`SRF-06`** | surface | Surface of Revolution | `CATStdCont`/`CGMGeom` | Rotational profile sweeps & CGM revolution records | analytic | 680 | **58.20%** | frozen |
| **`SRF-07`** | surface | Extruded Surface | `CATStdCont`/`CGMGeom` | Linear extrusion profile strips & CGM tab cyl | analytic | 890 | **79.50%** | frozen |
| **`SRF-08`** | surface | NURBS/BSpline Surface | `SurfacicReps`/`CGMGeom` | `SurfacicReps` stream & CGM spline records | nurbs | 1,435 | **100.00%** | frozen |

---

## 3. Ceiling Arithmetic & Analysis

1. **Topological Completeness (Bodies, Shells, Faces, Edges, Vertices)**:
   - 100% of the L2-pass population carries topological solid/body containers (`TOPO_BODY`: 1,089/1,089).
   - 99.82% of L2-pass parts exhibit discrete topological face sets and shells (`TOPO_FACE` and `TOPO_SHELL`: 1,087/1,089).
   - 100% carry explicit boundary edges (`TOPO_EDGE`: 1,089/1,089) and topological vertices (`TOPO_VERTEX`: 1,089/1,089).
   - Multi-loop planar boundary cycles (`TOPO_LOOP`) are present in 78.60% (856/1,089).

2. **Analytic vs. Freeform Geometry**:
   - Linear curves (`GEOM_CURV_LINE`) and circular arcs (`GEOM_CURV_CIRCLE`) form the overwhelming majority of boundary curves (98.53% and 85.03% respectively).
   - Exact planar surfaces (`GEOM_SURF_PLANE`) represent 78.60% of parts.
   - Conic sections (`GEOM_CURV_CONIC`: ellipses, parabolas) form a specialized minority (28.74%, 313 files).
   - 100% of L2-pass files contain exact `CGMGeom` storage blocks (`CONT_CGMGEOM`) carrying NURBS surface and curve definitions.

---

## 4. Proposed Phase 7 Decode Dispatch (Spec G Sub-Tickets)

With the construct vocabulary frozen, Phase 7 implementation proceeds across 5 bounded child tickets:

1. **BR2: Exact Planar Faces & Boundary Loop Decoder**
   - Targets: `TOPO_FACE`, `TOPO_LOOP`, `GEOM_SURF_PLANE`.
   - Decodes exact face boundaries from `01 4a` / `01 4c` normal-vector records and loop delimitation sequences.
2. **BR3: Linear & Circular Boundary Curve Decoders**
   - Targets: `GEOM_CURV_LINE`, `GEOM_CURV_CIRCLE`, `TOPO_EDGE`.
   - Implements analytic decoders for `33 32` (`[P][Q][P]` + $|Q|$) and `33 37` / `33 38` circular arcs.
3. **BR4: Cylindrical & Quadric Surface Recognizer**
   - Targets: `GEOM_SURF_CYLINDER`, `GEOM_SURF_QUADRIC`.
   - Recognizes rotational and extruded quadrics from strip geometry and axis parameters.
4. **BR5: CGM Exact Model & Freeform NURBS Stream Parser**
   - Targets: `CONT_CGMGEOM`, `GEOM_SURF_NURBS`, `GEOM_CURV_NURBS`.
   - Decodes `Cont_*` sub-streams and spline parameter matrices within `CGMGeom`.
5. **BR6: B-rep Topological Boundary Graph Assembler & STEP AP203/214 Exporter**
   - Targets: `TOPO_BODY`, `TOPO_SHELL`, and integration.
   - Assembles vertices, edges, loops, faces, and shells into a unified STEP B-rep exchange document.

---

## 5. Reproduction Command

```bash
LD_LIBRARY_PATH=/usr/lib .venv/bin/python scripts/triage/census_brep_constructs.py
```
Outputs:
- [`docs/evidence/data/brep-census-files.csv`](data/brep-census-files.csv)
- [`docs/evidence/data/brep-construct-vocabulary.csv`](data/brep-construct-vocabulary.csv)
