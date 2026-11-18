"""Unit tests for the BR2 planar face/loop/plane decode (Ticket #54, Spec G #47).

Synthetic fixtures for every discriminating edge of the three BR2
constructs (the detector-honesty negatives) plus the claims-CSV/evidence
hygiene checks.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import struct
from pathlib import Path

from catpart.brep.planar import (
    FACE_COUNT_VARIANT,
    FACE_NO_LOOPS,
    FACE_OK,
    FACE_OUT_OF_POOL,
    PLANE_TOL_REL,
    UNIT_NORM_TOL,
    count_structure,
    decode_planar_face,
    fit_plane,
    newell_normal,
    normal_unit_deviation,
    record_true_loops,
)
from catpart.geometry.facets import FacetRecord, parse_facet_record

REPO_ROOT = Path(__file__).resolve().parents[1]
CLAIMS_CSV = REPO_ROOT / "docs" / "evidence" / "data" / "br2-planar-claims.csv"
EVIDENCE_MD = REPO_ROOT / "docs" / "evidence" / "2026-11-17-br2-planar-loops.md"
DECODER = REPO_ROOT / "scripts" / "triage" / "decode_brep_planar.py"

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


def make_rec(marker, ty, counts, refs, normal, width=1, header_len=4, offset=0):
    return FacetRecord(
        offset=offset,
        marker=marker,
        type=ty,
        header_len=header_len,
        n=len(refs),
        width=width,
        counts=tuple(counts),
        refs=tuple(refs),
        end=offset + 100,
        normal=normal,
    )


# A CCW-from-+z unit square (walk order); refs below use the identity
# lex map (ref == walk position).
CCW_SQUARE = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
IDENTITY_LEX = [0, 1, 2, 3]


def test_ring_face_coplanar_and_oriented() -> None:
    rec = make_rec(0x4C, 1, (4,), (0, 1, 2, 3), (0.0, 0.0, 1.0))
    face = decode_planar_face(CCW_SQUARE, IDENTITY_LEX, rec)
    assert face.status == FACE_OK
    assert face.plane is not None and face.plane.coplanar
    assert face.plane.max_dev == 0.0
    assert face.oriented is True
    assert face.loop_readings[0].kind == "ring"
    assert face.loop_readings[0].closed_cycle is True


def test_strip_face_coplanar_and_oriented() -> None:
    # A strip segment over the same square: refs zig-zag, flip law gives
    # CCW triangles seen from +z.
    rec = make_rec(0x4A, 1, (4,), (0, 1, 3, 2), (0.0, 0.0, 1.0))
    face = decode_planar_face(CCW_SQUARE, IDENTITY_LEX, rec)
    assert face.status == FACE_OK
    assert face.plane is not None and face.plane.coplanar
    assert face.oriented is True
    assert face.loop_readings[0].kind == "strip"
    assert face.loop_readings[0].closed_cycle is None


def test_plane_offset_is_derived() -> None:
    # The record stores no offset: d comes from the loop vertices.
    pts = [(0.0, 0.0, 2.0), (1.0, 0.0, 2.0), (1.0, 1.0, 2.0)]
    eq = fit_plane(pts, (0.0, 0.0, 1.0))
    assert eq is not None
    assert abs(eq.offset + 2.0) <= 1e-12
    assert eq.coplanar


def test_negative_non_coplanar_points_rejected() -> None:
    # SRF-01 discriminating edge: the stored normal is a plane normal but
    # the points span several z planes (a curved-surface patch stamped
    # with one facet normal) — the plane validation must FAIL.
    pool = [
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (1.0, 1.0, 3.0),
        (0.0, 1.0, 3.0),
        (0.0, 0.0, 9.0),
        (1.0, 0.0, 9.0),
    ]
    rec = make_rec(0x4A, 1, (6,), (0, 1, 2, 3, 4, 5), (0.0, 0.0, 1.0))
    face = decode_planar_face(pool, [0, 1, 2, 3, 4, 5], rec)
    assert face.status == FACE_OK
    assert face.plane is not None
    assert not face.plane.coplanar


def test_negative_reversed_ring_not_oriented() -> None:
    rec = make_rec(0x4C, 1, (4,), (3, 2, 1, 0), (0.0, 0.0, 1.0))
    face = decode_planar_face(CCW_SQUARE, IDENTITY_LEX, rec)
    assert face.status == FACE_OK
    assert face.oriented is False


def test_count_structure_u8_and_u16be() -> None:
    # u8 counts: one byte per loop, ty == len(counts).
    rec_u8 = make_rec(0x4A, 2, (3, 7), tuple(range(10)), (0.0, 0.0, 1.0))
    cs = count_structure(rec_u8)
    assert cs is not None and cs.count_width == 1 and cs.lengths == (3, 7)
    assert record_true_loops(rec_u8) == [(0, 1, 2), (3, 4, 5, 6, 7, 8, 9)]

    # u16be counts on a u8-ref record (the corpus's 02ee1544 pattern):
    # bytes (0, 4) read as ONE length-4 loop, not a phantom empty + 4.
    rec_u16 = make_rec(0x4A, 1, (0, 4), (0, 1, 2, 3), (0.0, 0.0, 1.0))
    cs = count_structure(rec_u16)
    assert cs is not None and cs.count_width == 2 and cs.lengths == (4,)
    assert record_true_loops(rec_u16) == [(0, 1, 2, 3)]


def test_count_structure_u16_counts_over_u16_refs() -> None:
    # The count width must not be read off the ref width in EITHER
    # direction: u16be counts over u16be references is the same one loop.
    rec = make_rec(0x4A, 1, (0, 4), (0, 1, 2, 3), (0.0, 0.0, 1.0), width=2)
    cs = count_structure(rec)
    assert cs is not None and cs.count_width == 2 and cs.lengths == (4,)
    assert record_true_loops(rec) == [(0, 1, 2, 3)]


def test_negative_count_variant_not_guessed() -> None:
    # TOP-05 discriminating edge: ty=1 but two nonzero count bytes —
    # neither the u8 law (len != ty) nor the u16be law (nonzero high
    # byte) applies: the loop structure is NOT established.
    rec = make_rec(0x4A, 1, (2, 2), (0, 1, 2, 3), (0.0, 0.0, 1.0))
    assert count_structure(rec) is None
    face = decode_planar_face(CCW_SQUARE, IDENTITY_LEX, rec)
    assert face.status == FACE_COUNT_VARIANT
    assert face.plane is None


def test_negative_non_tiling_record_rejected() -> None:
    # F1 tiling edge: the count byte promises 4 refs but only 3 bytes
    # fit before the next record boundary — no (width, k) parse tiles.
    data = (
        b"\x01\x4a\x01\xff"
        + struct.pack("<I", 4)
        + struct.pack("<fff", 0.0, 0.0, 1.0)
        + b"\x04\x00\x00\x00"
    )
    assert parse_facet_record(data, 0, len(data), len(data)) is None


def test_negative_non_unit_normal_flagged() -> None:
    assert abs(normal_unit_deviation((0.0, 0.0, 2.0)) - 1.0) <= 1e-9
    assert abs(normal_unit_deviation((0.0, 0.0, 1.0))) <= UNIT_NORM_TOL


def test_negative_marker_blind_face_record() -> None:
    # TOP-04's declared non-discrimination, with a fixture: a normal-less
    # 0x42 record with in-pool refs decodes as an "ok" face carrying no
    # normal and no plane. "record == planar face" is a geometric reading,
    # so the status cannot separate a face from any other accepted 01
    # [41-4f] record.
    rec = make_rec(0x42, 1, (3,), (0, 1, 2), None)
    face = decode_planar_face(CCW_SQUARE, IDENTITY_LEX, rec)
    assert face.status == FACE_OK
    assert face.normal is None and face.plane is None and face.oriented is None


def test_negative_marker_blindness_across_markers() -> None:
    # 0x42 and 0x44 differ only in the marker byte (neither carries a
    # normal): every decoded field but the marker must agree.
    face_42 = decode_planar_face(CCW_SQUARE, IDENTITY_LEX, make_rec(0x42, 1, (3,), (0, 1, 2), None))
    face_44 = decode_planar_face(CCW_SQUARE, IDENTITY_LEX, make_rec(0x44, 1, (3,), (0, 1, 2), None))
    assert face_42.marker != face_44.marker
    assert _decode_signature(face_42) == _decode_signature(face_44)


def _decode_signature(face):
    return (
        face.status,
        face.loop_count,
        face.header_len,
        face.ref_width,
        face.count_width,
        face.loops,
        face.normal,
        face.plane,
        face.oriented,
        face.loop_readings,
    )


def test_no_loops_status_pinned() -> None:
    # FACE_NO_LOOPS is unreachable on the corpus (BR2-25: 0/118,807
    # accepted records have ty == 0), so this fixture is its only witness:
    # a grammar-legal ty=0 record must never report as an ok face.
    rec = make_rec(0x4A, 0, (), (), (0.0, 0.0, 1.0))
    face = decode_planar_face(CCW_SQUARE, IDENTITY_LEX, rec)
    assert face.status == FACE_NO_LOOPS
    assert face.plane is None


def test_negative_out_of_pool_refs_not_validated() -> None:
    # The composite index space (G3 F8): refs beyond the pool leave the
    # geometry undecidable — no plane, no orientation, no guessing.
    rec = make_rec(0x4A, 1, (4,), (0, 1, 2, 99), (0.0, 0.0, 1.0))
    face = decode_planar_face(CCW_SQUARE, IDENTITY_LEX, rec)
    assert face.status == FACE_OUT_OF_POOL
    assert face.plane is None and face.oriented is None


def test_newell_normal_direction() -> None:
    nv = newell_normal(CCW_SQUARE)
    assert nv[2] > 0.0
    nv_rev = newell_normal(list(reversed(CCW_SQUARE)))
    assert nv_rev[2] < 0.0


def test_plane_tolerance_is_relative_to_scale() -> None:
    pts_big = [(0.0, 0.0, 40000.0), (1.0, 0.0, 40000.0), (1.0, 1.0, 40000.0)]
    eq = fit_plane(pts_big, (0.0, 0.0, 1.0))
    assert eq is not None and eq.tol == PLANE_TOL_REL * 40000.0
    assert eq.coplanar  # exact-plane points stay coplanar at any scale


def test_br2_claims_csv_exists_and_parses() -> None:
    assert CLAIMS_CSV.is_file(), f"missing {CLAIMS_CSV}"
    with CLAIMS_CSV.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows, "claims CSV is empty"
    header = rows[0]
    assert header == CLAIMS_FIELDS
    ids = [row[0] for row in rows[1:]]
    assert len(ids) == len(set(ids)), "duplicate claim ids"
    for row in rows[1:]:
        assert len(row) == len(header), f"ragged row: {row}"
        assert row[0].startswith("BR2-"), f"claim id field 0: {row[0]}"
        rate = float(row[7])
        if "rate column carries the value" not in row[1]:
            assert 0.0 <= rate <= 1.0, f"rate out of range: {row}"
        assert row[2] in {"fact", "inference", "candidate", "unknown"}, row


def test_br2_audit_rows_are_committed() -> None:
    # Ticket #54 post-merge audit: every figure the note's prose cites has
    # a row. These ids carry the audit's corrections; dropping one breaks
    # the provenance chain, so they are pinned here.
    with CLAIMS_CSV.open(newline="", encoding="utf-8") as f:
        ids = {row["claim"] for row in csv.DictReader(f)}
    for claim in (
        "BR2-07b_triangle_list_share_resolved",
        "BR2-07c_law_excluding_triangle_list",
        "BR2-07d_face_count_variant",
        "BR2-07e_normal_bearing_variants",
        "BR2-08b_u16_count_over_u8_ref",
        "BR2-08c_u16_count_stores",
        "BR2-12d_spread_pass_max_rel",
        "BR2-12e_spread_fail_min_rel",
        "BR2-18b_0x49_n_equals_3ty",
        "BR2-21_cop_fail_stores_named",
        "BR2-21b_cop_fail_faces_named",
        "BR2-22_signneg_stores_named",
        "BR2-22b_signneg_faces_named",
        "BR2-25_zero_loop_records",
        "BR2-26_normal_less_strip_loops",
    ):
        assert claim in ids, f"missing audit row {claim}"


def test_filtered_runs_never_target_the_committed_claims_csv() -> None:
    # Audit B1: the documented reproduction command must not be able to
    # replace the all-corpus CSV with a filtered run (the Phase-5-retro
    # clobber failure mode).
    spec = importlib.util.spec_from_file_location("decode_brep_planar", DECODER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    full = module.claims_filename(argparse.Namespace(sha16=[], limit=0))
    assert full == CLAIMS_CSV.name
    sha = module.claims_filename(argparse.Namespace(sha16=["bd79fa8e"], limit=0))
    assert sha == "br2-planar-claims-sha16-bd79fa8e.csv"
    limit = module.claims_filename(argparse.Namespace(sha16=[], limit=1))
    assert limit == "br2-planar-claims-limit-1.csv"
    assert CLAIMS_CSV.name not in (sha, limit)


def test_br2_evidence_note_exists_and_cites_artifacts() -> None:
    assert EVIDENCE_MD.is_file(), f"missing {EVIDENCE_MD}"
    content = EVIDENCE_MD.read_text(encoding="utf-8")
    assert "br2-planar-claims.csv" in content
    assert "TOP-04" in content and "TOP-05" in content and "SRF-01" in content
    # both-bases byte offsets appear (e.g. the 12B normal at +0x08 (8d))
    assert "+0x08 (8d)" in content
    # detector honesty lines per construct
    assert "does NOT discriminate" in content
    # the audit's corrected figures are cited from committed rows, not prose
    for row in ("BR2-07b", "BR2-07c", "BR2-07d", "BR2-12d", "BR2-12e", "BR2-18b", "BR2-21b", "BR2-22b"):
        assert row in content, f"note does not cite {row}"
    # the superseded pass/fail bound (p95 read as the pass boundary) is gone
    assert "3e-5 of tol" not in content
