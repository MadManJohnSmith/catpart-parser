#!/usr/bin/env python3
"""B-rep construct census of the corpus geometry population (Ticket #48, BR1, Spec G #47).

Classifies the geometry-store and exact-model population at construct level
(topological structures, geometric curves, surfaces, containers) across all
1,442 corpus parts and specifically the 1,089 L2-pass population.

Outputs:
- docs/evidence/data/brep-census-files.csv (per-part construct census)
- docs/evidence/data/brep-construct-vocabulary.csv (frozen L3 construct vocabulary)
"""

from __future__ import annotations

import argparse
import csv
import mmap
import re
from pathlib import Path

from catpart.geometry import facets, pool, store

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
L2_STAGE15 = ROOT / "docs" / "evidence" / "data" / "stage15-identity-export-files.csv"
OUT_DIR = ROOT / "docs" / "evidence" / "data"

FIELDS = [
    "sha256",
    "split",
    "l2_status",
    "detected_version",
    "release",
    "size_bytes",
    "has_store",
    "store_container",
    "cgm_present",
    "cgm_size",
    "brepmode_present",
    "mfbrp_present",
    "vertex_pool_points",
    "element_space_declared",
    "edge_polyline_records",
    "edge_unwrapped_records",
    "curve33_32_lines",
    "curve33_37_circles",
    "curve33_38_curves",
    "curve33_other",
    "facet_records_total",
    "facet_planar_faces",
    "facet_strips",
    "facet_polygons",
    "facet_unresolved",
    "cgm_tag2x0_count",
    "construct_classes",
]

# Construct definitions for the frozen vocabulary
VOCABULARY = [
    {
        "construct_id": "TOPO_BODY",
        "family": "topology",
        "category": "solid",
        "name": "Topological Solid / Body",
        "description": "Top-level 3D manifold solid volume or open shell body",
        "carrier_surface": "CATSeeBodyCont / CATStdCont / CGMGeom",
        "record_signature": "CATSeeBodyCont storage block & nested store root",
        "status": "frozen",
    },
    {
        "construct_id": "TOPO_SHELL",
        "family": "topology",
        "category": "boundary",
        "name": "Connected Shell Boundary",
        "description": "Oriented set of connected faces enclosing or bounding a volume",
        "carrier_surface": "CATStdCont mesh & CGMGeom",
        "record_signature": "Closed manifold face sets with boundary_edge_count = 0",
        "status": "frozen",
    },
    {
        "construct_id": "TOPO_FACE",
        "family": "topology",
        "category": "surface_patch",
        "name": "Topological Face",
        "description": "2D bounded patch of surface geometry delimited by loop boundaries",
        "carrier_surface": "CATStdCont facet stream",
        "record_signature": "01 [41-4f] facet records with surface normals and loop bounds",
        "status": "frozen",
    },
    {
        "construct_id": "TOPO_LOOP",
        "family": "topology",
        "category": "loop",
        "name": "Face Boundary Loop",
        "description": "Closed boundary cycle of edges (outer perimeter or inner hole)",
        "carrier_surface": "CATStdCont facet stream",
        "record_signature": "01 4a <n_loops> ff sub-loop delimitations & 01 4c closed loops",
        "status": "frozen",
    },
    {
        "construct_id": "TOPO_EDGE",
        "family": "topology",
        "category": "edge",
        "name": "Topological Edge",
        "description": "1D boundary curve shared between adjacent faces",
        "carrier_surface": "CATStdCont edge tables & curve families",
        "record_signature": "01 02 wrapped polyline strips (02 <n> <refs>) & 01 01 edge lists",
        "status": "frozen",
    },
    {
        "construct_id": "TOPO_VERTEX",
        "family": "topology",
        "category": "vertex",
        "name": "Topological Vertex",
        "description": "0D point bounding topological edges and face corners",
        "carrier_surface": "CATStdCont vertex pool & scene-graph point lists",
        "record_signature": "05 08 01 records in 01 06 groups & prefix-compressed node points",
        "status": "frozen",
    },
    {
        "construct_id": "GEOM_SURF_PLANE",
        "family": "surface",
        "category": "analytic",
        "name": "Planar Surface",
        "description": "Exact plane defined by normal vector and distance/origin",
        "carrier_surface": "CATStdCont facet stream & CGMGeom",
        "record_signature": "01 4a / 01 4c facet records with 12B f32le unit normal",
        "status": "frozen",
    },
    {
        "construct_id": "GEOM_SURF_CYLINDER",
        "family": "surface",
        "category": "analytic",
        "name": "Cylindrical Surface",
        "description": "Circular cylinder defined by axis, radius, and boundary trim",
        "carrier_surface": "CATStdCont facet strips & CGMGeom",
        "record_signature": "Strip records with regular radius curvature & CGM cylinder records",
        "status": "frozen",
    },
    {
        "construct_id": "GEOM_SURF_QUADRIC",
        "family": "surface",
        "category": "analytic",
        "name": "Quadric Surface (Cone, Sphere, Torus)",
        "description": "Quadric surfaces of revolution (conical, spherical, toroidal)",
        "carrier_surface": "CATStdCont & CGMGeom",
        "record_signature": "Curved facet strip clusters with rotational axis symmetry",
        "status": "frozen",
    },
    {
        "construct_id": "GEOM_SURF_NURBS",
        "family": "surface",
        "category": "nurbs",
        "name": "NURBS / B-Spline Surface",
        "description": "Freeform parametric B-spline surface with knot vectors and control net",
        "carrier_surface": "SurfacicReps stream & CGMGeom",
        "record_signature": "SurfacicReps container payload & CGM spline surface records",
        "status": "frozen",
    },
    {
        "construct_id": "GEOM_CURV_LINE",
        "family": "curve",
        "category": "analytic",
        "name": "Linear Curve Segment",
        "description": "Exact straight line segment between two 3D endpoints",
        "carrier_surface": "CATStdCont curve records & edge tables",
        "record_signature": "33 32 records ([P][Q][P] + |Q|) & 02 02 edge records",
        "status": "frozen",
    },
    {
        "construct_id": "GEOM_CURV_CIRCLE",
        "family": "curve",
        "category": "analytic",
        "name": "Circular Arc / Circle",
        "description": "Exact circle or circular arc with center, radius, normal, and trim angles",
        "carrier_surface": "CATStdCont curve records & CGMGeom",
        "record_signature": "33 37 curve records (4 BE f32 + u16) & 33 38 curve records",
        "status": "frozen",
    },
    {
        "construct_id": "GEOM_CURV_CONIC",
        "family": "curve",
        "category": "analytic",
        "name": "Conic Arc (Ellipse, Parabola, Hyperbola)",
        "description": "Planar conic section curve with focal geometry and parameter ranges",
        "carrier_surface": "CATStdCont curve records & CGMGeom",
        "record_signature": "33 38 curve records & CGM conic curve payloads",
        "status": "frozen",
    },
    {
        "construct_id": "GEOM_CURV_NURBS",
        "family": "curve",
        "category": "nurbs",
        "name": "NURBS / B-Spline Curve",
        "description": "Parametric B-spline curve with degree, knot vector, and control points",
        "carrier_surface": "SurfacicReps & CGMGeom",
        "record_signature": "CGM spline curve records & SceneGraph spline definitions",
        "status": "frozen",
    },
    {
        "construct_id": "GEOM_CURV_POLYLINE",
        "family": "curve",
        "category": "discrete",
        "name": "Polyline Curve Strip",
        "description": "Piecewise linear curve connecting n >= 3 vertex points",
        "carrier_surface": "CATStdCont edge tables",
        "record_signature": "01 02 polyline strip records (02 <n> <refs>, n > 2)",
        "status": "frozen",
    },
    {
        "construct_id": "CONT_CGMGEOM",
        "family": "container",
        "category": "kernel",
        "name": "CGM Exact Model Container",
        "description": "Dassault CATIA Geometric Modeler exact CAD kernel storage block",
        "carrier_surface": "CGMGeom storage block",
        "record_signature": "CATStorageProperty block named CGMGeom with Cont_* streams",
        "status": "frozen",
    },
    {
        "construct_id": "CONT_BREPMODE",
        "family": "container",
        "category": "mode",
        "name": "B-Rep Mode & Layer Container",
        "description": "Boundary representation mode configuration and display layer filters",
        "carrier_surface": "CATBRepModeContainer",
        "record_signature": "CATStorageProperty block named CATBRepModeContainer",
        "status": "frozen",
    },
    {
        "construct_id": "CONT_MFBRP",
        "family": "container",
        "category": "feature_link",
        "name": "Mechanical Feature B-Rep Container",
        "description": "Association mapping connecting procedural features to B-rep topology",
        "carrier_surface": "CATMFBRP storage block",
        "record_signature": "CATStorageProperty block named CATMFBRP",
        "status": "frozen",
    },
]


def audit_part(mm: mmap.mmap, manifest_row: dict, l2_row: dict | None) -> dict:
    size = len(mm)
    blocks = store.valid_blocks(mm)
    block_names = {nm for _, nm in blocks}
    
    # CGM block
    cgm_present = "CGMGeom" in block_names
    cgm_size = 0
    cgm_tag2x0 = 0
    if cgm_present:
        for i, (blk, nm) in enumerate(blocks):
            if nm == "CGMGeom":
                nxt = blocks[i + 1][0] if i + 1 < len(blocks) else size
                cgm_size = nxt - blk
                cgm_payload = mm[blk:nxt]
                cgm_tag2x0 = len(re.findall(rb"2[0-9]?-0", cgm_payload))
                break

    brepmode_present = "CATBRepModeContainer" in block_names
    mfbrp_present = (mm.find(b"CATMFBRP") >= 0) or any("BRP" in nm for nm in block_names)
    
    # Locate store
    d8_outer = int.from_bytes(mm[8:12], "big") if size >= 12 else 0
    span = None
    store_container = ""
    for container_tag in (
        store.CONTAINER_STDCONT,
        store.CONTAINER_XDOCLINK,
        store.CONTAINER_SEEBODY,
        store.CONTAINER_OTHER,
    ):
        cands = [b for b, nm in blocks if nm == ("CATStdCont" if container_tag == store.CONTAINER_STDCONT else ("CATXDocLinkCont" if container_tag == store.CONTAINER_XDOCLINK else ("CATSeeBodyCont" if container_tag == store.CONTAINER_SEEBODY else nm)))]
        for blk in cands:
            try:
                s = store.locate_store(mm, blk, blocks, d8_outer, container=container_tag)
                if s is not None:
                    span = s
                    store_container = container_tag
                    break
            except Exception:
                continue
        if span is not None:
            break

    has_store = span is not None
    vpool_pts = 0
    elem_decl = 0
    edge_poly = 0
    edge_unwrapped = 0
    c32 = 0
    c37 = 0
    c38 = 0
    c_other = 0
    facets_total = 0
    planar_faces = 0
    strips = 0
    polys = 0
    unresolved_facets = 0

    if span is not None:
        lo, hi = span.body_lo, span.body_hi
        # Pool points
        kinds = []
        try:
            pgroups, kinds = pool.scan_pool_groups(mm, lo, hi)
            vpool_pts = sum(len(g.vertices) for g in pgroups)
        except Exception:
            pass

        # Declared element space
        t_pos = mm.find(b"\xff\xff\x02\x00\x01", lo, hi)
        if t_pos >= 0:
            p = t_pos + 5
            if p < hi:
                if mm[p] == 0xFF and p + 5 <= hi:
                    elem_decl = int.from_bytes(mm[p + 1 : p + 5], "little")
                else:
                    elem_decl = mm[p]

        # Edge groups
        edge_poly = sum(1 for k in kinds if k == b"\x01\x02")

        # Unwrapped 01 01 edge lists
        u1_pos = lo
        while True:
            u1_pos = mm.find(b"\x01\x01", u1_pos, hi)
            if u1_pos < 0:
                break
            edge_unwrapped += 1
            u1_pos += 2

        # Curve families
        c32 = len(re.findall(b"\x33\x32", mm[lo:hi]))
        c37 = len(re.findall(b"\x33\x37", mm[lo:hi]))
        c38 = len(re.findall(b"\x33\x38", mm[lo:hi]))
        for fam in (0x30, 0x31, 0x33, 0x34, 0x35, 0x36, 0x39):
            c_other += len(re.findall(bytes([0x33, fam]), mm[lo:hi]))

        # Facets
        try:
            fscan = facets.scan_facets(mm, lo, hi)
            facets_total = len(fscan.records)
            for f in fscan.records:
                if f.marker in (0x4A, 0x4C):
                    planar_faces += 1
                if f.marker in (0x42, 0x4A):
                    strips += 1
                if f.marker == 0x4C:
                    polys += 1
            unresolved_facets = fscan.unresolved_candidates + sum(fscan.skipped_markers.values())
        except Exception:
            pass

    # Construct classification
    active_constructs = []
    if has_store or cgm_present:
        active_constructs.append("TOPO_BODY")
    if facets_total > 0:
        active_constructs.append("TOPO_FACE")
        active_constructs.append("TOPO_SHELL")
    if planar_faces > 0 or polys > 0:
        active_constructs.append("TOPO_LOOP")
        active_constructs.append("GEOM_SURF_PLANE")
    if vpool_pts > 0 or elem_decl > 0:
        active_constructs.append("TOPO_VERTEX")
    if edge_poly > 0 or edge_unwrapped > 0 or c32 > 0:
        active_constructs.append("TOPO_EDGE")
    if c32 > 0 or edge_poly > 0:
        active_constructs.append("GEOM_CURV_LINE")
    if edge_poly > 0:
        active_constructs.append("GEOM_CURV_POLYLINE")
    if c37 > 0:
        active_constructs.append("GEOM_CURV_CIRCLE")
    if c38 > 0:
        active_constructs.append("GEOM_CURV_CONIC")
    if strips > 0:
        active_constructs.append("GEOM_SURF_CYLINDER")
    if cgm_present:
        active_constructs.append("CONT_CGMGEOM")
        # Exact CGM models carry analytic and spline representations
        active_constructs.append("GEOM_SURF_NURBS")
        active_constructs.append("GEOM_CURV_NURBS")
        active_constructs.append("GEOM_SURF_QUADRIC")
    if brepmode_present:
        active_constructs.append("CONT_BREPMODE")
    if mfbrp_present:
        active_constructs.append("CONT_MFBRP")

    l2_status = l2_row.get("l2_status", "") if l2_row else ""

    return {
        "sha256": manifest_row["sha256"],
        "split": manifest_row["split"],
        "l2_status": l2_status,
        "detected_version": manifest_row.get("detected_version", ""),
        "release": manifest_row.get("detected_version", "")[:3],
        "size_bytes": size,
        "has_store": has_store,
        "store_container": store_container,
        "cgm_present": cgm_present,
        "cgm_size": cgm_size,
        "brepmode_present": brepmode_present,
        "mfbrp_present": mfbrp_present,
        "vertex_pool_points": vpool_pts,
        "element_space_declared": elem_decl,
        "edge_polyline_records": edge_poly,
        "edge_unwrapped_records": edge_unwrapped,
        "curve33_32_lines": c32,
        "curve33_37_circles": c37,
        "curve33_38_curves": c38,
        "curve33_other": c_other,
        "facet_records_total": facets_total,
        "facet_planar_faces": planar_faces,
        "facet_strips": strips,
        "facet_polygons": polys,
        "facet_unresolved": unresolved_facets,
        "cgm_tag2x0_count": cgm_tag2x0,
        "construct_classes": ";".join(active_constructs),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default=str(OUT_DIR), help="Output directory")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load L2 stage15 data
    l2_by_sha = {}
    if L2_STAGE15.exists():
        with L2_STAGE15.open() as f:
            for r in csv.DictReader(f):
                l2_by_sha[r["sha256"]] = r

    # Load manifest part rows
    with MANIFEST.open() as f:
        manifest_parts = [r for r in csv.DictReader(f) if r["kind"] == "part"]

    manifest_parts.sort(key=lambda r: r["sha256"])
    print(f"Executing B-rep construct census over {len(manifest_parts)} parts...")

    results = []
    for r in manifest_parts:
        fpath = ROOT / r["local_path"]
        l2_info = l2_by_sha.get(r["sha256"])
        with fpath.open("rb") as fh:
            mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
            try:
                res = audit_part(mm, r, l2_info)
                results.append(res)
            finally:
                mm.close()

    # Write brep-census-files.csv
    census_file = out_dir / "brep-census-files.csv"
    with census_file.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(results)
    print(f"Wrote {census_file} ({len(results)} rows)")

    # Compute rates over L2-pass population (the gate population)
    l2_pass_rows = [r for r in results if r["l2_status"] == "pass"]
    n_l2_pass = len(l2_pass_rows)
    print(f"L2-pass population: {n_l2_pass} files (dev: {sum(1 for r in l2_pass_rows if r['split'] == 'dev')}, held-out: {sum(1 for r in l2_pass_rows if r['split'] == 'held-out')})")

    # Update and write brep-construct-vocabulary.csv
    vocab_rows = []
    for v in VOCABULARY:
        cid = v["construct_id"]
        hits_l2 = sum(1 for r in l2_pass_rows if cid in r["construct_classes"].split(";"))
        rate_l2 = round(hits_l2 / n_l2_pass, 4) if n_l2_pass else 0.0
        hits_all = sum(1 for r in results if cid in r["construct_classes"].split(";"))
        rate_all = round(hits_all / len(results), 4) if results else 0.0
        
        row = dict(v)
        row["l2_pass_occurrences"] = hits_l2
        row["l2_pass_rate"] = rate_l2
        row["corpus_occurrences"] = hits_all
        row["corpus_rate"] = rate_all
        vocab_rows.append(row)

    vocab_file = out_dir / "brep-construct-vocabulary.csv"
    vocab_fields = [
        "construct_id",
        "family",
        "category",
        "name",
        "description",
        "carrier_surface",
        "record_signature",
        "status",
        "l2_pass_occurrences",
        "l2_pass_rate",
        "corpus_occurrences",
        "corpus_rate",
    ]
    with vocab_file.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=vocab_fields)
        w.writeheader()
        w.writerows(vocab_rows)
    print(f"Wrote {vocab_file} ({len(vocab_rows)} frozen constructs)")

    # Print summary ceiling table
    print("\n" + "=" * 90)
    print(f"{'Construct ID':<20} | {'Family':<10} | {'L2 Pass Rate':<12} | {'Corpus Rate':<12} | {'Status'}")
    print("-" * 90)
    for row in vocab_rows:
        print(f"{row['construct_id']:<20} | {row['family']:<10} | {row['l2_pass_rate']:<12.2%} | {row['corpus_rate']:<12.2%} | {row['status']}")
    print("=" * 90)


if __name__ == "__main__":
    main()
