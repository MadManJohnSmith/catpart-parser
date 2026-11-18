#!/usr/bin/env python3
"""BR6 topology graph + STEP export corpus decoder (Ticket #58, Spec G #47).

Builds the contract's graph (``catpart.brep.graph``) over the manifest's
part population and measures, per part:

1. the graph: store class, node counts per kind, status, closed shells;
2. the invariants (``catpart.brep.graph.check_invariants``): the
   load-bearing loop-segment pairing law per closed shell, and every
   graph's violation codes;
3. the STEP export in both face modes (``catpart.brep.step_export``),
   with a caller-supplied ``MM`` (no model unit exists — U2 0/108) and
   the assumed lump accepted, so the refusal class is the *graph*'s
   property, not the unit/lump policy;
4. determinism: one graph rendered twice, byte-identical, digest
   recorded.

Every figure the evidence note cites is a row of
docs/evidence/data/br6-graph-claims.csv written here. Corpus binaries are
read READ-ONLY from the main checkout (``--corpus-root``); nothing is
copied into the repo.

The 76 closed shells are the shell slice's population (BR6S-13). This
run measures them, it does not redefine them; the loop-segment pairing
statistic is the F7 law (graph edges are loop segments, never triangles),
so a shell closed by the triangle law can still fail the B-rep pairing.

Detector honesty: ``--selftest`` runs the synthetic roster with no corpus
(design §6); the script never decodes the composite element space, so
``skipped_refs`` stays 0 and BR4 §1's 78,255 is cited, not re-derived.

Reproduction (deterministic, manifest order, stdlib only):
    LD_LIBRARY_PATH=/usr/lib python -I scripts/triage/decode_brep_graph.py \\
        --selftest
    LD_LIBRARY_PATH=/usr/lib python -I scripts/triage/decode_brep_graph.py \\
        --out docs/evidence/data/br6-graph-claims.csv
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import struct
import sys
from collections import Counter
from pathlib import Path

from catpart.brep import graph as G
from catpart.brep import step_export as S
from catpart.geometry import facets, store

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "manifests" / "corpus-manifest.csv"
OUT_DIR = REPO_ROOT / "docs" / "evidence" / "data"
DEFAULT_CORPUS_ROOT = "/home/alan/Documents/Repos/catpart-parser"

CLAIMS_FIELDS = [
    "claim",
    "statement",
    "label",
    "scope",
    "release",
    "observations",
    "passes",
    "rate",
    "value",
]

EXACT_OPTIONS = S.StepOptions(
    face_mode="exact", length_unit="MM", accept_assumed_lump=True
)
FACET_OPTIONS = S.StepOptions(
    face_mode="facet", length_unit="MM", accept_assumed_lump=True
)


# --------------------------------------------------------------------
# Synthetic roster (no corpus)
# --------------------------------------------------------------------

CUBE = [
    (0.0, 0.0, 0.0),
    (1.0, 0.0, 0.0),
    (1.0, 1.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, 0.0, 1.0),
    (1.0, 0.0, 1.0),
    (1.0, 1.0, 1.0),
    (0.0, 1.0, 1.0),
]
CUBE_FACES = [
    (0x4C, (0, 3, 2, 1), (0.0, 0.0, -1.0)),
    (0x4C, (4, 5, 6, 7), (0.0, 0.0, 1.0)),
    (0x4C, (0, 1, 5, 4), (0.0, -1.0, 0.0)),
    (0x4C, (1, 2, 6, 5), (1.0, 0.0, 0.0)),
    (0x4C, (2, 3, 7, 6), (0.0, 1.0, 0.0)),
    (0x4C, (3, 0, 4, 7), (-1.0, 0.0, 0.0)),
]


def _f32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


def _store(points, faces):
    points = [tuple(_f32(c) for c in point) for point in points]
    lex = facets.lex_rank_map(points)
    rank = {walk: r for r, walk in enumerate(lex)}
    data = bytearray()
    data += b"\x10\x24\x04\xff\xff\x00\x00\x00" + b"\x01\x06" + bytes([len(points)])
    for point in points:
        data += b"\x05\x08\x01" + struct.pack("<fff", *point)
    for marker, refs, normal in faces:
        data += b"\x01" + bytes([marker]) + b"\x01\xff" + struct.pack("<I", len(refs))
        if marker in facets.NORMAL_MARKERS_ALL:
            data += struct.pack("<fff", *normal)
        data += bytes([len(refs)])
        data += bytes(rank.get(ref, ref) for ref in refs)
    data = bytes(data)
    span = store.StoreSpan(
        block_start=0,
        origin=0,
        origin_kind=store.ORIGIN_KIND_BLOCK,
        body_lo=0,
        body_hi=len(data),
        catalog_len=0,
        container="synthetic",
        tail_law=store.TAIL_LAW_SHIPPED,
    )
    return data, span


def selftest() -> list[str]:
    """The corpus-free roster (design §6). Returns failure strings."""
    failures: list[str] = []

    def check(name, condition, detail=""):
        if not condition:
            failures.append(f"{name}: {detail}")

    data, span = _store(CUBE, CUBE_FACES)
    cube = G.build_store_graph(data, span)
    check("cube.status", cube.status == G.STATUS_COMPLETE, cube.status)
    check(
        "cube.counts",
        (cube.completeness.face, cube.completeness.loop, cube.completeness.edge,
         cube.completeness.vertex) == (6, 6, 12, 8),
        cube.completeness,
    )
    check("cube.invariants", G.check_invariants(cube) == (), G.check_invariants(cube))
    exact = S.render_step(cube, options=EXACT_OPTIONS)
    facet = S.render_step(cube, options=FACET_OPTIONS)
    check("cube.exact", exact.entity_counts.get("ADVANCED_FACE") == 6, exact.entity_counts)
    check("cube.facet", facet.entity_counts.get("ADVANCED_FACE") == 12, facet.entity_counts)
    check("cube.deterministic", S.render_step(cube, options=FACET_OPTIONS).sha256 == facet.sha256)
    for banned in ("B_SPLINE", "TOROIDAL_SURFACE", "CONICAL_SURFACE"):
        check(f"cube.no_{banned}", banned not in exact.text and banned not in facet.text)

    patched = S.render_step(cube, options=S.StepOptions(face_mode="exact", strict=False))
    check(
        "cube.lump_assumed",
        {v.code for v in patched.refused} == {"lump-assumed", "unit-undetermined"},
        {v.code for v in patched.refused},
    )

    # One-use loop segment: the F7 law fails on a sheet.
    sheet = _store(
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 1.0, 0.0)],
        [(0x4C, (0, 1, 2), (0.0, 0.0, 1.0)), (0x4C, (1, 3, 2), (0.0, 0.0, 1.0))],
    )
    sheet_graph = G.build_store_graph(*sheet)
    codes = {
        v.code for v in G.check_invariants(sheet_graph)
    }
    check("sheet.edge_use_pair", "edge-use-pair" in codes, codes)
    sheet_refused = S.render_step(
        sheet_graph, options=dataclasses.replace(EXACT_OPTIONS, strict=False)
    )
    sheet_codes = {violation.code for violation in sheet_refused.refused}
    check("sheet.shell_not_brep_paired", "shell-not-brep-paired" in sheet_codes, sheet_codes)
    check("sheet.shell_open", "shell-open" in sheet_codes, sheet_codes)

    # Composite store: element space is not remapped.
    composite_data, composite_span = _store(CUBE, CUBE_FACES)
    composite_data += b"\x10\x24\x04\xff\xff\x00\x00\x00" + b"\x01\x02"
    composite_span = store.StoreSpan(
        block_start=0,
        origin=0,
        origin_kind=store.ORIGIN_KIND_BLOCK,
        body_lo=0,
        body_hi=len(composite_data),
        catalog_len=0,
        container="synthetic",
        tail_law=store.TAIL_LAW_SHIPPED,
    )
    composite = G.build_store_graph(composite_data, composite_span)
    check("composite.index", composite.index_space == G.INDEX_COMPOSITE, composite.index_space)
    check(
        "composite.no_geometry",
        composite.completeness.vertex == 0 and composite.completeness.shell == 0,
    )
    return failures


# --------------------------------------------------------------------
# Corpus run
# --------------------------------------------------------------------


def _shell_pairing(graph, shell_id) -> tuple[int, int, int]:
    """Loop-segment uses of one shell: (unpaired, one-use, max uses).

    Counted over the assembled graph (no byte decode): the F7 law says an
    edge is the undirected pair of loop corner slots and a B-rep-paired
    shell uses each exactly twice.
    """
    face_ids = {
        arc.child for arc in graph.arcs if arc.kind == G.ARC_SHELL_FACE and arc.parent == shell_id
    }
    loop_ids = {
        arc.child for arc in graph.arcs if arc.kind == G.ARC_FACE_LOOP and arc.parent in face_ids
    }
    uses: Counter = Counter()
    for arc in graph.arcs:
        if arc.kind == G.ARC_LOOP_EDGE and arc.parent in loop_ids:
            uses[arc.child] += 1
    unpaired = sum(1 for count in uses.values() if count != 2)
    one_use = sum(1 for count in uses.values() if count == 1)
    return unpaired, one_use, max(uses.values(), default=0)


def audit_part(path: str) -> dict:
    """One part's graph + export audit (counters feeding the claims)."""
    out = {
        "has_store": False,
        "index_space": "none",
        "status": "",
        "closed_shells": 0,
        "shells": 0,
        "nodes": Counter(),
        "violations": Counter(),
        "closed_unpaired": 0,
        "closed_with_one_use": 0,
        "exact": "",
        "facet": "",
        "unknown": 0,
        "skipped_refs": 0,
        "bodies": 0,
        "lumps": 0,
        "unknown_nodes": 0,
        "ring_faces": 0,
        "closed_shell_face_records": 0,
        "closed_shells_ring_only": 0,
        "closed_shells_with_excluded": 0,
        "excluded_faces_total": 0,
        "excluded_faces_in_closed_shells": 0,
        "structural_graphs": 0,
        "digest": "",
    }
    graph = G.build_part_graph(path)
    out["has_store"] = bool(graph.nodes)
    out["index_space"] = graph.index_space
    out["status"] = graph.status
    out["nodes"] = Counter(node.id.kind for node in graph.nodes)
    out["unknown"] = graph.completeness.unknown
    out["skipped_refs"] = graph.completeness.skipped_refs
    out["bodies"] = graph.completeness.body
    out["lumps"] = graph.completeness.lump
    out["unknown_nodes"] = sum(
        1
        for node in graph.nodes
        if node.provenance.export_label == "unknown" or node.status == "unknown"
    )
    for violation in G.check_invariants(graph):
        out["violations"][violation.code] += 1
    structural = {"no-orphan", "index-space-homogeneous", "determinism", "arc-kind-table"}
    if structural & set(out["violations"]):
        out["structural_graphs"] = 1
    out["excluded_faces_total"] = graph.completeness.excluded_faces
    face_marker = {
        node.id: node.data.marker for node in graph.nodes if node.id.kind == G.NODE_FACE
    }
    for node in graph.nodes:
        if node.id.kind != G.NODE_SHELL:
            continue
        out["shells"] += 1
        attached = [
            arc.child
            for arc in graph.arcs
            if arc.kind == G.ARC_SHELL_FACE and arc.parent == node.id
        ]
        markers = [face_marker[face] for face in attached]
        out["ring_faces"] += sum(1 for marker in markers if marker == 0x4C)
        if getattr(node.data, "status", "") != "closed-manifold":
            continue
        out["closed_shells"] += 1
        out["closed_shell_face_records"] += len(node.data.face_offsets)
        if markers and all(marker == 0x4C for marker in markers):
            out["closed_shells_ring_only"] += 1
        excluded_here = len(node.data.face_offsets) - len(attached)
        if excluded_here:
            out["closed_shells_with_excluded"] += 1
            out["excluded_faces_in_closed_shells"] += excluded_here
        unpaired, one_use, _worst = _shell_pairing(graph, node.id)
        if unpaired:
            out["closed_unpaired"] += 1
        if one_use:
            out["closed_with_one_use"] += 1

    for mode, options, key in (
        ("exact", EXACT_OPTIONS, "exact"),
        ("facet", FACET_OPTIONS, "facet"),
    ):
        export = S.render_step(graph, options=dataclasses.replace(options, strict=False))
        if export.refused:
            out[key] = export.refused[0].code
        else:
            out[key] = "ok"
            if not out["digest"]:
                again = S.render_step(graph, options=options)
                if again.sha256 == export.sha256:
                    out["digest"] = export.sha256
    return out


def run_corpus(args) -> list[list[str]]:
    corpus_root = Path(args.corpus_root)
    with MANIFEST.open() as handle:
        parts = [row for row in csv.DictReader(handle) if row["kind"] == "part"]
    parts.sort(key=lambda row: row["sha256"])
    if args.sha16:
        parts = [row for row in parts if row["sha256"].startswith(tuple(args.sha16))]
    if args.limit:
        parts = parts[: args.limit]
    print(f"BR6 graph + STEP decode over {len(parts)} parts (root: {corpus_root})")

    totals = Counter()
    nodes = Counter()
    exact_classes = Counter()
    facet_classes = Counter()
    digest = ""
    digest_sha16 = ""
    for index, row in enumerate(parts, 1):
        path = corpus_root / row["local_path"]
        try:
            audit = audit_part(str(path))
        except Exception as exc:  # upstream verdict keeps its named class
            totals["error"] += 1
            print(f"  ! {row['sha256'][:16]}: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        totals["parts"] += 1
        totals["with_store"] += 1 if audit["has_store"] else 0
        totals["composite"] += 1 if audit["index_space"] == G.INDEX_COMPOSITE else 0
        totals["complete"] += 1 if audit["status"] == G.STATUS_COMPLETE else 0
        totals["with_closed_shell"] += 1 if audit["closed_shells"] else 0
        totals["closed_shells"] += audit["closed_shells"]
        totals["closed_unpaired"] += audit["closed_unpaired"]
        totals["closed_with_one_use"] += audit["closed_with_one_use"]
        totals["no_violation_graphs"] += 1 if not audit["violations"] else 0
        totals["violation_codes"] += sum(audit["violations"].values())
        totals["unknown"] += audit["unknown"]
        totals["skipped_refs"] += audit["skipped_refs"]
        totals["bodies"] += audit["bodies"]
        totals["lumps"] += audit["lumps"]
        totals["unknown_nodes"] += audit["unknown_nodes"]
        totals["ring_faces"] += audit["ring_faces"]
        totals["closed_shell_face_records"] += audit["closed_shell_face_records"]
        totals["closed_shells_ring_only"] += audit["closed_shells_ring_only"]
        totals["closed_shells_with_excluded"] += audit["closed_shells_with_excluded"]
        totals["excluded_faces"] += audit["excluded_faces_total"]
        totals["excluded_faces_in_closed_shells"] += audit["excluded_faces_in_closed_shells"]
        totals["structural_graphs"] += audit["structural_graphs"]
        nodes.update(audit["nodes"])
        if audit["exact"] == "ok":
            totals["exact_ok"] += 1
        else:
            exact_classes[audit["exact"]] += 1
        if audit["facet"] == "ok":
            totals["facet_ok"] += 1
        else:
            facet_classes[audit["facet"]] += 1
        if audit["digest"] and not digest:
            digest = audit["digest"]
            digest_sha16 = row["sha256"][:16]
        if index % 200 == 0:
            print(f"  ... {index}/{len(parts)}")
        if args.include_sha16:
            print(f"  {row['sha256'][:16]} status={audit['status']} exact={audit['exact']} facet={audit['facet']}")

    if digest:
        again = audit_part(str(corpus_root / next(
            row["local_path"] for row in parts if row["sha256"].startswith(digest_sha16)
        )))
        if again["digest"] and again["digest"] != digest:
            print(
                f"  ! determinism drift: {digest_sha16} {digest} -> {again['digest']}",
                file=sys.stderr,
            )
            digest = ""
    observed = totals["parts"]
    rows: list[list[str]] = []

    def value_row(claim, statement, label, value):
        rows.append(
            [claim, statement, label, "located graphs", "all", "1", "1", "1.0", str(value)]
        )

    def rate_row(claim, statement, label, observations, passes, scope="corpus parts"):
        rate = (passes / observations) if observations else 0.0
        rows.append(
            [
                claim,
                statement,
                label,
                scope,
                "all",
                str(observations),
                str(passes),
                f"{rate:.6g}",
                "",
            ]
        )

    rate_row(
        "BR6G-01_parts_with_closed_shell",
        "parts whose graph decodes >= 1 closed shell (anchor BR6S-04 = 66)",
        "fact",
        observed,
        totals["with_closed_shell"],
    )
    rate_row(
        "BR6G-02_parts_complete",
        "parts whose graph is status=complete (all_faces_closed with no excluded face "
        "family and no unknown record; anchor BR6S-10 = 66)",
        "fact",
        observed,
        totals["complete"],
    )
    value_row(
        "BR6G-03a_body_nodes",
        "body nodes over the corpus graphs (one body per located store is an "
        "assumption, BR5-04a/b)",
        "fact",
        nodes["body"],
    )
    value_row(
        "BR6G-03b_lump_nodes",
        "lump nodes over the corpus graphs (all export_label=assumed)",
        "fact",
        nodes["lump"],
    )
    value_row("BR6G-03c_shell_nodes", "shell nodes (all components, open included)", "fact", nodes["shell"])
    value_row("BR6G-03d_face_nodes", "face nodes (normal-bearing planar family only)", "fact", nodes["face"])
    value_row("BR6G-03e_loop_nodes", "loop nodes", "fact", nodes["loop"])
    value_row("BR6G-03f_edge_nodes", "edge nodes (loop segments, never triangle chords)", "fact", nodes["edge"])
    value_row("BR6G-03g_vertex_nodes", "vertex nodes (pool slots, no welding)", "fact", nodes["vertex"])
    rate_row(
        "BR6G-04_composite_parts",
        "parts whose first located store is composite (index_space=composite-element; "
        "anchor BR6S-08 = 1,036 stores)",
        "fact",
        observed,
        totals["composite"],
    )
    rate_row(
        "BR6G-05a_graphs_without_violations",
        "graphs for which check_invariants returns no violation",
        "fact",
        observed,
        totals["no_violation_graphs"],
    )
    rate_row(
        "BR6G-05b_closed_shells_brep_paired",
        "closed shells whose loop segments are each used exactly twice (the F7 "
        "B-rep pairing law, distinct from the triangle closure)",
        "fact",
        totals["closed_shells"],
        totals["closed_shells"] - totals["closed_unpaired"],
        scope="closed shells",
    )
    rate_row(
        "BR6G-05c_closed_shells_with_one_use_segment",
        "closed shells carrying at least one loop segment used once",
        "fact",
        totals["closed_shells"],
        totals["closed_with_one_use"],
        scope="closed shells",
    )
    rate_row(
        "BR6G-06a_exact_mode_success_parts",
        "parts whose graph exports in exact mode with caller-supplied MM and the "
        "assumed lump accepted (expected 0/76 closed shells, published pre-run)",
        "fact",
        observed,
        totals["exact_ok"],
    )
    for class_name in S.REFUSAL_ORDER:
        rate_row(
            f"BR6G-06b_exact_refusal_{class_name}",
            f"parts whose exact-mode render raises {class_name} (strict order's first class)",
            "fact",
            observed,
            exact_classes.get(class_name, 0),
        )
    rate_row(
        "BR6G-07a_facet_mode_success_parts",
        "parts whose graph exports in facet mode (the default mode)",
        "fact",
        observed,
        totals["facet_ok"],
    )
    rate_row(
        "BR6G-07b_facet_refused_parts",
        "parts whose facet-mode render is refused for any class",
        "fact",
        observed,
        sum(facet_classes.values()),
    )
    rate_row(
        "BR6G-05d_graphs_with_structural_violations",
        "graphs with any construction-guarantee violation (no-orphan, "
        "index-space-homogeneous, determinism, arc-kind-table)",
        "fact",
        observed,
        totals["structural_graphs"],
    )
    for class_name in S.REFUSAL_ORDER:
        rate_row(
            f"BR6G-07c_facet_refusal_{class_name}",
            f"parts whose facet-mode render raises {class_name} (strict order's first class)",
            "fact",
            observed,
            facet_classes.get(class_name, 0),
        )
    rows.append(
        [
            "BR6G-08_determinism_renders",
            f"same graph rendered twice byte-identically (sha16 {digest_sha16 or 'none'}; "
            f"sha256 {digest or 'none'})",
            "fact",
            "first facet-mode success in manifest order",
            "all",
            "2",
            "2" if digest else "0",
            "1.0" if digest else "0.0",
            "2",
        ]
    )
    value_row(
        "BR6G-09a_unread_records",
        "accepted records outside the face families counted in completeness.unknown "
        "(the 0x44 class; anchor BR6S-22 = 708)",
        "fact",
        totals["unknown"],
    )
    value_row(
        "BR6G-09b_skipped_refs_total",
        "completeness.skipped_refs summed over the corpus graphs (the composite "
        "element space is not decoded; BR4's 78,255 is cited, not re-derived)",
        "fact",
        totals["skipped_refs"],
    )
    rate_row(
        "BR6G-10a_lumps_per_body",
        "lump nodes per body node (the derived-single-lump assumption)",
        "fact",
        totals["bodies"],
        totals["lumps"],
        scope="body nodes",
    )
    value_row(
        "BR6G-10b_unknown_nodes_emitted",
        "unknown-labelled nodes in the assembled graphs (must be 0; unknown records "
        "are counted, never noded)",
        "fact",
        totals["unknown_nodes"],
    )
    value_row(
        "BR6G-11a_ring_face_nodes",
        "face nodes on the 0x4c ring marker (the family exact mode needs)",
        "fact",
        totals["ring_faces"],
    )
    value_row(
        "BR6G-11b_closed_shell_face_records",
        "face records belonging to the closed shells (all markers)",
        "fact",
        totals["closed_shell_face_records"],
    )
    value_row(
        "BR6G-11c_closed_shells_ring_only",
        "closed shells whose every attached face record is a 0x4c ring (the only "
        "shape exact mode could emit)",
        "fact",
        totals["closed_shells_ring_only"],
    )
    value_row(
        "BR6G-11d_excluded_faces",
        "component face records with no FaceNode producer (0x41/0x42, no 12B normal)",
        "fact",
        totals["excluded_faces"],
    )
    value_row(
        "BR6G-11e_excluded_faces_in_closed_shells",
        "the same records that sit inside a closed shell (face-family-unread)",
        "fact",
        totals["excluded_faces_in_closed_shells"],
    )
    value_row(
        "BR6G-11f_closed_shells_with_excluded_faces",
        "closed shells carrying at least one record with no FaceNode producer",
        "fact",
        totals["closed_shells_with_excluded"],
    )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-root", default=DEFAULT_CORPUS_ROOT)
    parser.add_argument("--out", default=str(OUT_DIR / "br6-graph-claims.csv"))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--sha16", action="append", default=[])
    parser.add_argument("--include-sha16", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        failures = selftest()
        for failure in failures:
            print(f"SELFTEST FAIL {failure}")
        print(f"selftest: {len(failures)} failure(s)")
        return 1 if failures else 0

    rows = run_corpus(args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(CLAIMS_FIELDS)
        writer.writerows(rows)
    print(f"wrote {out} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
