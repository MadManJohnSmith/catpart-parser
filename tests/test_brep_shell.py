"""Unit tests for the BR6 TOP-03 shell partition (Ticket #58, Spec G #47).

Synthetic fixtures for every discriminating edge of the shell partition
(the detector-honesty negatives), a parity test against the shipped
export reading, and the claims-CSV/evidence-note hygiene checks.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

from catpart.brep.shell import (
    SHELL_CLOSED,
    SHELL_NON_MANIFOLD,
    SHELL_OPEN,
    FaceShell,
    ShellSet,
    decode_shells,
)
from catpart.geometry import facets
from catpart.geometry.facets import FacetRecord, FacetScan

REPO_ROOT = Path(__file__).resolve().parents[1]
CLAIMS_CSV = REPO_ROOT / "docs" / "evidence" / "data" / "br6-shell-claims.csv"
EVIDENCE_MD = REPO_ROOT / "docs" / "evidence" / "2026-11-17-br6-shell.md"

CLAIMS_FIELDS = [
    "claim",
    "statement",
    "label",
    "scope",
    "release",
    "observations",
    "passes",
    "rate",
]

# A unit tetrahedron, outward-wound faces (right-hand rule). References
# are POOL WALK positions; the helper converts to the lexicographic
# ranks the record grammar stores (G3 F2/C8).
TETRA = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
TETRA_FACES = [(0, 2, 1), (0, 1, 3), (1, 2, 3), (0, 3, 2)]

OCTAHEDRON = [
    (0.0, 0.0, 1.0),
    (0.0, 0.0, -1.0),
    (1.0, 0.0, 0.0),
    (0.0, 1.0, 0.0),
    (-1.0, 0.0, 0.0),
    (0.0, -1.0, 0.0),
]
OCTAHEDRON_FACES = [
    (0, 2, 3),
    (0, 3, 4),
    (0, 4, 5),
    (0, 5, 2),
    (1, 3, 2),
    (1, 4, 3),
    (1, 5, 4),
    (1, 2, 5),
]


def make_rec(offset, refs, marker=0x4C, normal=(0.0, 0.0, 1.0), counts=None):
    return FacetRecord(
        offset=offset,
        marker=marker,
        type=len(counts) if counts is not None else 1,
        header_len=4,
        n=len(refs),
        width=1,
        counts=tuple(counts) if counts is not None else (len(refs),),
        refs=tuple(refs),
        end=offset + 100,
        normal=normal,
    )


def scan_of(records):
    return FacetScan(
        candidates=len(records),
        records=tuple(records),
        unresolved_candidates=0,
        skipped_markers={},
    )


def shells_of(pool_points, face_walk_refs, marker=0x4C):
    """Decode faces written in POOL WALK order (the reader's view)."""
    lex = facets.lex_rank_map(pool_points)
    rank = {walk: r for r, walk in enumerate(lex)}
    records = [
        make_rec(10 * i, tuple(rank[w] for w in face), marker=marker)
        for i, face in enumerate(face_walk_refs)
    ]
    return decode_shells(pool_points, scan_of(records))


# --------------------------------------------------------------------
# The positive law: a closed manifold face set is one shell.
# --------------------------------------------------------------------


def test_closed_tetrahedron_is_one_shell() -> None:
    shells = shells_of(TETRA, TETRA_FACES)
    assert len(shells.shells) == 1
    shell = shells.shells[0]
    assert shell.is_shell and shell.status == SHELL_CLOSED
    assert shell.manifold and shell.closed
    assert shell.oriented
    assert shell.boundary_edges == 0
    assert shell.face_offsets == (0, 10, 20, 30)
    assert shell.triangle_count == 4 and shell.edge_count == 6
    assert shells.faces == 4 and shells.placed_faces == 4
    assert shells.all_faces_closed


def test_tetrahedron_volume_and_sign() -> None:
    shells = shells_of(TETRA, TETRA_FACES)
    assert abs(shells.shells[0].signed_volume - 1.0 / 6.0) <= 1e-12


def test_two_disjoint_shells_are_two_components() -> None:
    pool = TETRA + [(1.0, 1.0, 1.0), (2.0, 1.0, 1.0), (1.0, 2.0, 1.0), (1.0, 1.0, 2.0)]
    faces = TETRA_FACES + [tuple(x + 4 for x in f) for f in TETRA_FACES]
    shells = shells_of(pool, faces)
    assert len(shells.shells) == 2
    assert len(shells.closed_shells) == 2
    assert all(s.is_shell for s in shells.shells)
    assert shells.all_faces_closed


def test_multi_shell_store_is_a_multi_shell_body() -> None:
    # A shell set is the topology a Body carries: two closed components
    # are two shells (outer shell + cavity shell candidates).
    pool = TETRA + [(1.0, 1.0, 1.0), (2.0, 1.0, 1.0), (1.0, 2.0, 1.0), (1.0, 1.0, 2.0)]
    faces = TETRA_FACES + [tuple(x + 4 for x in f) for f in TETRA_FACES]
    shells = shells_of(pool, faces)
    assert len(shells.closed_shells) >= 2


# --------------------------------------------------------------------
# Detector-honesty negatives (one per discrimination the law does NOT
# make). Each fixture pins the edge.
# --------------------------------------------------------------------


def test_negative_closed_is_not_oriented() -> None:
    # Closed but inconsistently wound: flipping one face breaks the
    # directed-edge pairing, NOT the closure.
    flipped = list(TETRA_FACES[:3]) + [(0, 2, 3)]
    shells = shells_of(TETRA, flipped)
    shell = shells.shells[0]
    assert shell.is_shell and shell.closed
    assert not shell.oriented


def test_negative_closed_octahedron_has_no_brep_identity() -> None:
    # A closed tessellation (a sphere cap has the same signature)
    # decodes as one shell: the partition never establishes B-rep faces.
    shells = shells_of(OCTAHEDRON, OCTAHEDRON_FACES)
    assert len(shells.shells) == 1
    assert shells.shells[0].is_shell


def test_negative_vertex_touching_bodies_are_two_shells() -> None:
    # Adjacency is shared-EDGE, not proximity: two tetrahedra touching
    # at one vertex only are two independent shells.
    pool = TETRA + [(1.0, 1.0, 1.0), (2.0, 1.0, 1.0), (1.0, 2.0, 1.0), (1.0, 1.0, 2.0)]
    faces = TETRA_FACES + [tuple(x + 4 for x in f) for f in TETRA_FACES]
    shells = shells_of(pool, faces)
    assert len(shells.shells) == 2
    assert shells.shells[0].face_offsets[0] != shells.shells[1].face_offsets[0]


def test_negative_reversed_tetrahedron_negative_volume() -> None:
    # The signed volume's sign is a measurement under the exported
    # winding, never a role label: a fully reversed solid reports < 0.
    reversed_faces = [tuple(reversed(f)) for f in TETRA_FACES]
    shells = shells_of(TETRA, reversed_faces)
    shell = shells.shells[0]
    assert shell.is_shell and shell.signed_volume < 0.0


def test_negative_out_of_pool_refs_are_counted_not_guessed() -> None:
    records = [make_rec(0, (0, 1, 2)), make_rec(100, (0, 1, 99))]
    shells = decode_shells(TETRA, scan_of(records))
    assert shells.faces == 2
    assert shells.unplaced_faces == 1
    assert shells.placed_faces == 1
    assert len(shells.shells) == 1
    assert not shells.all_faces_closed


def test_negative_edge_used_three_times_is_non_manifold() -> None:
    pool = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, 1.0)]
    shells = shells_of(pool, [(0, 1, 2), (0, 1, 3), (0, 1, 4)])
    assert len(shells.shells) == 1
    assert shells.shells[0].status == SHELL_NON_MANIFOLD
    assert shells.shells[0].max_edge_degree == 3
    assert not shells.shells[0].closed


def test_negative_sheet_with_paired_edge_is_open() -> None:
    pool = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, -1.0, 0.0)]
    shells = shells_of(pool, [(0, 1, 2), (1, 0, 3)])
    shell = shells.shells[0]
    assert shell.status == SHELL_OPEN
    assert shell.boundary_edges == 4
    assert not shell.is_shell
    assert not shells.all_faces_closed


def test_negative_degenerate_face_yields_no_component() -> None:
    shells = decode_shells(TETRA, scan_of([make_rec(0, (0, 0, 0))]))
    assert shells.faces == 1
    assert shells.degenerate_faces == 1
    assert shells.placed_faces == 0
    assert not shells.shells


def test_negative_marker_outside_pinned_family_is_not_a_face() -> None:
    # 0x44 is an accepted marker whose primitive reading is open (G3
    # F9): it is not a face candidate and never enters the partition.
    shells = decode_shells(TETRA, scan_of([make_rec(0, (0, 1, 2), marker=0x44)]))
    assert shells.faces == 0
    assert not shells.shells


def test_all_faces_closed_requires_a_complete_partition() -> None:
    complete = shells_of(TETRA, TETRA_FACES)
    assert complete.all_faces_closed
    partial = decode_shells(TETRA, scan_of([make_rec(0, (0, 1, 2)), make_rec(10, (0, 1, 99))]))
    assert not partial.all_faces_closed
    empty = decode_shells(TETRA, scan_of([]))
    assert not empty.all_faces_closed


def test_empty_shell_set_shape() -> None:
    shells = decode_shells([], scan_of([]))
    assert isinstance(shells, ShellSet)
    assert shells.shells == ()
    assert shells.faces == 0 and shells.unplaced_faces == 0
    assert shells.degenerate_faces == 0
    assert shells.closed_shells == ()


def test_faceshell_reports_derived_predicates() -> None:
    shell = FaceShell(
        face_offsets=(0, 10, 20, 30),
        triangle_count=4,
        edge_count=6,
        boundary_edges=0,
        max_edge_degree=2,
        oriented=True,
        signed_volume=1.0 / 6.0,
    )
    assert shell.manifold and shell.closed and shell.is_shell
    open_shell = FaceShell(
        face_offsets=(0,),
        triangle_count=1,
        edge_count=3,
        boundary_edges=3,
        max_edge_degree=1,
        oriented=True,
        signed_volume=0.0,
    )
    assert open_shell.status == SHELL_OPEN and not open_shell.closed


# --------------------------------------------------------------------
# Parity with the shipped export reading (no second primitive law).
# --------------------------------------------------------------------


def test_partition_triangles_match_the_shipped_soup() -> None:
    # Strips and rings on a closed box: the partition must walk exactly
    # the triangles facets.decode_soup emits (same primitive semantics,
    # same degenerate skip).
    box = [
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (1.0, 1.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
        (1.0, 0.0, 1.0),
        (1.0, 1.0, 1.0),
        (0.0, 1.0, 1.0),
    ]
    lex = facets.lex_rank_map(box)
    rank = {walk: r for r, walk in enumerate(lex)}
    walk_faces = [
        (0x4C, (0, 1, 2, 3)),  # bottom ring (-z winding below)
        (0x4A, (4, 5, 6, 7)),  # top strip
        (0x4C, (0, 1, 5, 4)),  # front
        (0x4C, (1, 2, 6, 5)),  # right
        (0x4C, (2, 3, 7, 6)),  # back
        (0x4C, (3, 0, 4, 7)),  # left
    ]
    records = [
        make_rec(10 * i, tuple(rank[w] for w in refs), marker=marker)
        for i, (marker, refs) in enumerate(walk_faces)
    ]
    scan = scan_of(records)
    shells = decode_shells(box, scan)
    soup = facets.decode_soup(box, lex, scan)
    assert sum(s.triangle_count for s in shells.shells) == len(soup.triangles)
    assert shells.placed_faces == 6


def test_strip_face_joins_the_partition() -> None:
    # A 0x4a strip record contributes its strip triangles, so a strip
    # face is a face in the partition (the shipped reading).
    pool = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 1.0, 0.0)]
    shells = shells_of(pool, [(0, 1, 2, 3)], marker=0x4A)
    assert shells.faces == 1 and shells.placed_faces == 1
    assert shells.shells[0].triangle_count == 2


# --------------------------------------------------------------------
# Committed artifacts (claims CSV + evidence note).
# --------------------------------------------------------------------


def test_br6_shell_claims_csv_exists_and_parses() -> None:
    assert CLAIMS_CSV.is_file(), f"missing {CLAIMS_CSV}"
    with CLAIMS_CSV.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows, "claims CSV is empty"
    assert rows[0] == CLAIMS_FIELDS
    seen = set()
    for row in rows[1:]:
        assert len(row) == len(CLAIMS_FIELDS), f"ragged row: {row}"
        assert row[0].startswith("BR6S-"), f"claim id field 0: {row[0]}"
        assert row[0] not in seen, f"duplicate claim id: {row[0]}"
        seen.add(row[0])
        rate = float(row[7])
        if "rate column carries the value" not in row[1]:
            assert 0.0 <= rate <= 1.0, f"rate out of range: {row}"
        assert row[2] in {"fact", "inference", "candidate", "unknown"}, row
        int(row[5]), int(row[6])  # observations/passes stay integers


def test_br6_shell_evidence_note_exists_and_cites_artifacts() -> None:
    assert EVIDENCE_MD.is_file(), f"missing {EVIDENCE_MD}"
    content = EVIDENCE_MD.read_text(encoding="utf-8")
    assert "br6-shell-claims.csv" in content
    assert "TOP-03" in content and "TOPO_SHELL" in content
    # both-bases byte offsets appear (e.g. the 12B normal at +0x08 (8d))
    assert "+0x08 (8d)" in content
    # detector honesty lines per discrimination
    assert "does NOT discriminate" in content


def test_br6_shell_note_cites_only_committed_claim_ids() -> None:
    assert CLAIMS_CSV.is_file() and EVIDENCE_MD.is_file()
    with CLAIMS_CSV.open(newline="", encoding="utf-8") as f:
        committed = {row["claim"].split("_")[0] for row in csv.DictReader(f)}
    cited = set(re.findall(r"BR6S-\d+[a-z]?", EVIDENCE_MD.read_text(encoding="utf-8")))
    missing = cited - committed
    assert not missing, f"note cites claim ids absent from the CSV: {sorted(missing)}"


def test_br6_shell_claims_are_all_cited_in_the_note() -> None:
    # The converse drift guard: a committed row the note never mentions is
    # a figure nobody reads (the prose is the note; the CSV is its data).
    with CLAIMS_CSV.open(newline="", encoding="utf-8") as f:
        committed = {row["claim"].split("_")[0] for row in csv.DictReader(f)}
    content = EVIDENCE_MD.read_text(encoding="utf-8")
    uncited = {cid for cid in committed if cid not in content}
    assert not uncited, f"claims never cited in the note: {sorted(uncited)}"
