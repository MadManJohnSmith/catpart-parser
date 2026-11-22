"""Corpus-free tests for the analytic availability scanner (W11, B8).

The evidence note (``docs/evidence/2026-11-22-w11-analytic-surfaces.md``)
rests on a measured negative: the ``undecoded-variant`` population
carries no direct analytic surface record — no per-part ``01 56`` plane
object, no axis+radius block, no NURBS payload, no ``a5 03 34`` frame —
and cross-measured, no E5 class-``0x00e7`` record either (that census
ran W3's committed probe; not re-derived here). These tests build every
detector ingredient from bytes and pin the discriminating edges:

- the template plane law fires on the measured default direction pairs
  and on nothing else (a different unit pair is a per-part plane);
- the object-stream span walk splits records at the three observed
  headers and drops coincidental ``ff ff 02 00`` occurrences;
- the axis+radius shape census accepts a real unit axis and refuses
  the measured 2^-k fixed-point alias family;
- the A/B frame law (bulk-stream §3.1) closes frames at both families,
  refuses the ``b1`` family byte, and clusters only chained runs;
- the NURBS knot detector accepts a synthetic knot vector and refuses
  the u32-chain alias and the too-short/too-uniform runs.

Fixtures are synthetic; no corpus binary is read.
"""

from __future__ import annotations

import struct

import pytest

from catpart.geometry.analytic import (
    TEMPLATE_PLANE_UV,
    VERDICT_NO_ANALYTIC,
    analytic_shape_candidates,
    bulk_clusters,
    f32_values,
    knot_runs,
    parse_frame,
    plane_records,
    weight_runs,
)


def plane_body(object_id: int, payload: bytes) -> bytes:
    """One ``01 56`` object record laid out as the corpus measures it."""
    return (
        b"\xff\xff\x02\x00\x01\x56"
        + struct.pack("<I", object_id)
        + bytes(14)
        + payload
        + b"\x00\x00\x14\x04\xff\xff\xff\xff\xff"
    )


TEMPLATE_PAIR = TEMPLATE_PLANE_UV[0]
OTHER_PAIR = struct.pack("<3f", 0.6, 0.8, 0.0) + struct.pack("<3f", 0.8, -0.6, 0.0)


class TestTemplatePlaneLaw:
    def test_the_measured_template_pair_flags_a_plane(self):
        body = bytes(8) + plane_body(34, TEMPLATE_PAIR + struct.pack("<f", 15.0))
        records = plane_records(body, 0, len(body))
        assert len(records) == 1
        assert records[0].object_id == 34
        assert records[0].is_template

    def test_the_second_measured_template_pair_flags_too(self):
        body = plane_body(67, TEMPLATE_PLANE_UV[1] + struct.pack("<f", 10.0))
        records = plane_records(body, 0, len(body))
        assert len(records) == 1
        assert records[0].is_template

    def test_a_different_unit_pair_is_per_part(self):
        body = plane_body(7, OTHER_PAIR + struct.pack("<f", 3.5))
        records = plane_records(body, 0, len(body))
        assert len(records) == 1
        assert not records[0].is_template

    def test_a_coincidental_object_header_does_not_split_a_record(self):
        # ``ff ff 02 00`` followed by a non-class byte is not a record:
        # the plane payload itself carries such a run and must not be cut.
        payload = b"\xff\xff\x02\x00\x09\x09" + TEMPLATE_PAIR
        body = plane_body(1, payload)
        records = plane_records(body, 0, len(body))
        assert len(records) == 1
        assert records[0].is_template


class TestShapeCensus:
    def test_a_real_unit_axis_with_radius_is_accepted(self):
        hits = analytic_shape_candidates([0.6, 0.8, 0.0, 5.0])
        assert hits["cylinder"].count == 1
        assert hits["cylinder"].distinct == 1
        assert hits["cone"].count == 1

    def test_the_fixed_point_alias_family_is_refused(self):
        # the measured 550.000 alias: exact 2^-k components + 1.0
        ladder = [2.0**-13, 1.0, 2.0**-11, 1.0] * 4
        hits = analytic_shape_candidates(ladder)
        assert hits["cylinder"].count == 0
        assert hits["cone"].count == 0

    def test_out_of_band_radii_are_refused(self):
        assert analytic_shape_candidates([0.6, 0.8, 0.0, 1e-4])["cylinder"].count == 0
        assert analytic_shape_candidates([0.6, 0.8, 0.0, 1e7])["cylinder"].count == 0

    def test_repeated_tuples_inflate_count_not_distinct(self):
        hits = analytic_shape_candidates([0.6, 0.8, 0.0, 5.0] * 3)
        assert hits["cylinder"].count == 3
        assert hits["cylinder"].distinct == 1

    def test_f32_census_reads_one_value_per_window(self):
        body = struct.pack("<4f", 0.6, 0.8, 0.0, 5.0) + bytes(3)
        values = f32_values(body)
        assert values == pytest.approx([0.6, 0.8, 5.0])


class TestFrameLaw:
    def an_a_frame(self, payload: bytes) -> bytes:
        return (
            bytes([0xA5, 0x03, 0x34])
            + struct.pack("<I", len(payload))
            + b"\x0f"
            + payload
        )

    def a_b_frame(self, payload: bytes) -> bytes:
        return bytes([0xB2, 0x03, 0x06, len(payload), 0x5A]) + payload

    def test_an_a_family_frame_closes(self):
        frame = self.an_a_frame(b"payload")
        parsed = parse_frame(frame, 0, len(frame))
        assert parsed is not None
        assert parsed[:3] == ("A", 1, 0x34)
        assert parsed[3] == len(frame)

    def test_a_b_family_frame_closes(self):
        frame = self.a_b_frame(b"xy")
        parsed = parse_frame(frame, 0, len(frame))
        assert parsed is not None
        assert parsed[:3] == ("B", 1, 0x06)
        assert parsed[3] == len(frame)

    def test_the_b1_family_byte_is_refused(self):
        frame = b"\xb1\x03\x06\x02\x5Axy"
        assert parse_frame(frame, 0, len(frame)) is None

    def test_a_wrong_flag_is_refused(self):
        frame = bytes([0xB2, 0x04, 0x06, 2, 0x5A]) + b"xy"
        assert parse_frame(frame, 0, len(frame)) is None

    def test_clusters_need_three_chained_frames(self):
        stream = self.a_b_frame(b"ab") + self.a_b_frame(b"cd") + self.a_b_frame(b"ef")
        clusters, classes = bulk_clusters(stream, 0, len(stream))
        assert len(clusters) == 1
        assert clusters[0] == (0, len(stream))
        assert sum(c.count for c in classes) == 3

    def test_a_two_frame_run_is_not_a_cluster(self):
        stream = self.a_b_frame(b"ab") + self.a_b_frame(b"cd") + bytes(4)
        clusters, _classes = bulk_clusters(stream, 0, len(stream))
        assert clusters == []


class TestNurbsSignatures:
    def knot_vector(self, knots: list[float]) -> bytes:
        return b"".join(struct.pack("<d", k) for k in knots)

    def test_a_real_knot_vector_is_accepted(self):
        # 10 knots, non-decreasing, 5 distinct values, 5 repeats
        knots = [0.0, 0.0, 0.25, 0.5, 0.5, 0.75, 1.0, 1.0, 1.0, 1.0]
        data = self.knot_vector(knots)
        runs = knot_runs(data, 0, len(data))
        assert len(runs) == 1
        assert runs[0].count == 10
        assert runs[0].distinct == 5
        assert runs[0].repeats == 5

    def test_a_u32_chain_alias_is_refused(self):
        # a u32le array misread as f64 chains: word k's high half equals
        # word k+1's low half. The shipped guards refuse this family
        # (chain-fraction >= 0.75 here, and the repeated halves trip the
        # repeat bar too — the chain edge itself is pinned by the
        # cgm_nurbs BR5 tests); this fixture pins the corpus behavior.
        halves = [
            0x11111111,
            0x41600000,
            0x41600000,
            0x4163D70A,
            0x4163D70A,
            0x4167AE14,
            0x4167AE14,
            0x416B851F,
            0x416B851F,
            0x416F5C28,
            0x416F5C28,
            0x416F5C29,
            0x416F5C29,
            0x416F5C2A,
            0x416F5C2A,
            0x416F5C2B,
        ]
        data = b"".join(struct.pack("<I", v) for v in halves)
        words = [data[k * 4 : k * 4 + 4] for k in range(len(halves))]
        chained = sum(
            1
            for a, b in zip(words, words[1:])
            if a == b
        )
        # the fixture genuinely chains: halves[i] == halves[i+1] on the
        # repeated pairs, so every adjacent f64 word shares the seam
        assert chained >= 6
        assert knot_runs(data, 0, len(data)) == ()

    def test_a_short_or_uniform_run_is_refused(self):
        assert knot_runs(self.knot_vector([0.1, 0.2, 0.3]), 0, 24) == ()
        uniform = self.knot_vector([0.5] * 10)
        assert knot_runs(uniform, 0, len(uniform)) == ()

    def test_weight_runs_need_four_ones(self):
        three = self.knot_vector([1.0, 1.0, 1.0])
        four = self.knot_vector([1.0, 1.0, 1.0, 1.0])
        assert weight_runs(three, 0, len(three), 4) == ()
        assert weight_runs(four, 0, len(four), 4) == ((0, 4),)

    def test_the_denormal_band_is_excluded(self):
        # (0, 1e-8) values alias integer index arrays; they break runs —
        # with both halves below the 8-value bar nothing qualifies
        denorm = self.knot_vector([0.0, 1e-9, 0.25, 0.5, 0.5, 0.75, 1.0, 1.0, 1.0])
        runs = knot_runs(denorm, 0, len(denorm))
        assert runs == ()
        # the same vector without the denormal qualifies (the guard, not
        # the shape, made the difference)
        clean = self.knot_vector([0.0, 0.25, 0.5, 0.5, 0.75, 1.0, 1.0, 1.0])
        assert len(knot_runs(clean, 0, len(clean))) == 1


class TestVerdictVocabulary:
    def test_the_two_template_pairs_are_distinct_measured_bytes(self):
        assert len(TEMPLATE_PLANE_UV) == 2
        assert TEMPLATE_PLANE_UV[0] != TEMPLATE_PLANE_UV[1]

    def test_the_no_analytic_verdict_word(self):
        assert VERDICT_NO_ANALYTIC == "no-evaluable-analytic-surface"
