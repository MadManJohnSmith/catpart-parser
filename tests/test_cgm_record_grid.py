"""Corpus-free tests for the CGM record-grid probe (decisive probe, #57).

The probe (``scripts/triage/probe_cgm_record_grid.py``) is the analysis
layer over the CGM record grid; these tests build the two record families
from bytes (no corpus access) and pin the four decisions the evidence note
rests on:

- the two-family grammar's **positive** side: a region built only from
  id-run and companion records tiles exactly (residue 0), so a non-zero
  residue in the corpus is a finding, not a parser artefact;
- its **negative** side: an unrelated record shape is refused and counted
  as residue at the exact offset;
- the companion length law ``31 + 4*flag`` (31/35/39 B for flag 0/1/2);
- the numeric scan discriminates a real coordinate triple / knot run /
  weight run from the corpus's aliases (integer-array power-of-two
  chains, fixed-point ramps, ASCII text).

Fixtures are synthetic; no corpus binary is read.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "triage"))

import probe_cgm_record_grid as probe  # noqa: E402


def u32le(*vals: int) -> bytes:
    return b"".join(struct.pack("<I", v) for v in vals)


def u16le(*vals: int) -> bytes:
    return b"".join(struct.pack("<H", v) for v in vals)


def f64le(*vals: float) -> bytes:
    return b"".join(struct.pack("<d", v) for v in vals)


def idrun(marker: int, x: int, ids: list[int], flag: int = 0, width: int = 32) -> bytes:
    body = bytes([marker, 0, 4, 0]) + u32le(x) + bytes([flag])
    if width == 32:
        body += u32le(len(ids))
    else:
        body += u16le(len(ids))
    body += u32le(*ids) + b"\x00\x00"
    return body


def companion(x: int, flag: int, words: list[int], ids: list[int], type_word: int) -> bytes:
    """A companion record: 31 + 4*flag bytes, layout pinned by the probe.

    The count field is fixed at 2 by the length law, so ``ids`` must name
    exactly one id; ``type_word`` is the second (the 0x38/0x40 word).
    """
    assert len(words) == flag + 1
    assert len(ids) == 1
    body = b"\x01\x00\x04\x00" + u32le(x) + bytes([flag, 0])
    body += u32le(*words) + u16le(2) + u32le(*(ids + [type_word]))
    body += b"\x00" + bytes(range(6))  # opaque 6-byte trailer
    assert len(body) == 31 + 4 * flag
    return body


def part(preamble: bytes, *records: bytes) -> bytes:
    return preamble + b"".join(records)


def test_idrun_u32_and_u16_share_the_frame() -> None:
    w32 = idrun(2, 9, [3, 4, 5])
    w16 = idrun(9, 11, [3, 4, 5], width=16)
    for width, blob in ((32, w32), (16, w16)):
        rec = probe.parse_record(blob, 0, len(blob))
        assert rec is not None
        assert rec.family == f"idrun{width}"
        assert rec.marker == (2 if width == 32 else 9)
        assert rec.count == 3 and rec.ids == (3, 4, 5)
        assert rec.end == len(blob)


def test_idrun_terminator_is_required() -> None:
    blob = bytearray(idrun(1, 9, [3, 4, 5]))
    blob[-1] = 0x01
    assert probe._idrun(bytes(blob), 0, len(blob), 32) is None


def test_id_range_guard_refuses_a_u16_count_over_payload_bytes() -> None:
    """A shifted u16 count that lands on a chance ``00 00`` is not a record.

    The frame is otherwise valid (count + terminator agree), so only the
    id-range value law refuses it; without that law the bytes would be
    framed as one record of "ids" that are payload.
    """
    blob = (
        bytes([1, 0, 4, 0])
        + u32le(9)
        + bytes([0])
        + u16le(3)
        + u32le(0x20000001, 0x10000002, 0x40000003)
        + b"\x00\x00"
    )
    assert len(blob) == 25
    assert probe.parse_record(blob, 0, len(blob)) is not None
    assert probe.parse_record(blob, 0, len(blob), probe.BR5_MAX_ID) is None


def test_id_range_guard_keeps_a_legitimate_u16_record() -> None:
    blob = idrun(9, 11, [3, 4, 5], width=16)
    rec = probe.parse_record(blob, 0, len(blob), probe.BR5_MAX_ID)
    assert rec is not None and rec.ids == (3, 4, 5)


@pytest.mark.parametrize("flag", [0, 1, 2])
def test_companion_length_law(flag: int) -> None:
    blob = companion(
        x=0x29,
        flag=flag,
        words=[0] * (flag + 1),
        ids=[8],
        type_word=0x38,
    )
    assert len(blob) == 31 + 4 * flag
    rec = probe.parse_record(blob, 0, len(blob))
    assert rec is not None
    assert rec.family == "companion"
    assert rec.flag == flag
    assert rec.ids[-1] == 0x38
    assert rec.type_word == 0x38


def test_companion_requires_its_closing_zero_byte() -> None:
    blob = bytearray(companion(x=3, flag=0, words=[0], ids=[8], type_word=0x40))
    blob[24] = 0x01  # the byte between the id list and the trailer
    assert probe.parse_record(bytes(blob), 0, len(blob)) is None


def test_walk_tiles_two_families_exactly() -> None:
    preamble = b"identity-preamble" + bytes(6)
    records = [
        idrun(2, 9, [3, 4, 5]),
        companion(x=3, flag=0, words=[0], ids=[8], type_word=0x38),
        idrun(2, 11, [9, 10, 11, 12, 13, 14, 15]),
        companion(x=0x29, flag=2, words=[7, 0x30, 0], ids=[14], type_word=0x40),
    ]
    data = part(preamble, *records)
    tiling = probe.walk(data, 0, len(data))
    assert tiling.grid_lo == len(preamble)
    assert tiling.preamble == len(preamble)
    assert tiling.framed == len(data) - len(preamble)
    assert tiling.residue == 0
    assert tiling.exact


def test_walk_reports_the_residue_offset_and_head() -> None:
    good = idrun(1, 9, [3, 4, 5])
    another = idrun(1, 11, [7, 8, 9])
    junk = b"\x01\x00\x04\x00\x77\xdb\x05\x00" + bytes(8)  # the anchor's refused form
    data = part(bytes(4), good, another, junk)
    tiling = probe.walk(data, 0, len(data))
    assert not tiling.exact
    assert tiling.residue_lo == len(data) - len(junk)
    assert tiling.residue == len(junk)
    assert probe._residue_head(data, tiling.residue_lo).startswith("01 00 04 00 77 db")


def test_grid_start_skips_the_identity_preamble() -> None:
    preamble = b"FINJPL  " + bytes(12)
    data = part(preamble, idrun(2, 1, [1, 2]), idrun(2, 3, [3, 4]))
    tiling = probe.walk(data, 0, len(data))
    assert tiling.grid_lo == len(preamble)
    assert tiling.exact


def test_numeric_scan_accepts_a_real_triple_and_knots_and_weights() -> None:
    coords = f64le(12.5, -3.25, 7.0, 4.0, 9.5, 1.0)
    knots = f64le(0.0, 0.0, 0.25, 0.5, 0.5, 0.75, 1.0, 1.0, 1.0)
    weights = f64le(1.0, 1.0, 1.0, 1.0, 1.0)
    data = bytes(8) + coords + bytes(8) + knots + bytes(8) + weights + bytes(8)
    scan = probe.numeric_scan(data, 0, len(data))
    assert scan.f64_guarded >= 1
    assert scan.knot_runs >= 1
    assert scan.weight_runs >= 1


def test_numeric_scan_rejects_the_integer_alias_ramps() -> None:
    pow2 = f64le(2048.0, 8192.0, 32768.0, 1024.0, 4096.0, 16384.0)
    ramp = f64le(0.0029296875, 0.0029449462890625, 0.002960205078125)
    ascii_run = b"2024,12.5,7.0"
    data = pow2 + bytes(8) + ramp + bytes(8) + ascii_run + bytes(8)
    scan = probe.numeric_scan(data, 0, len(data))
    assert scan.f64_guarded == 0


def test_framed_scan_covers_only_the_record_bodies() -> None:
    preamble = bytes(4)
    record = idrun(1, 9, [3, 4, 5])
    anchor = idrun(1, 11, [7, 8, 9])
    junk = f64le(1.5, 2.5, 3.5) * 4
    data = part(preamble, record, anchor, junk)
    tiling = probe.walk(data, 0, len(data))
    assert tiling.grid_lo == len(preamble)
    assert tiling.residue == len(junk)
    framed = probe.framed_scan(data, tiling)
    assert framed.f64_guarded == 0


def test_numeric_scan_retains_the_guarded_triples_for_accounting() -> None:
    coords = f64le(12.5, -3.25, 7.0)
    scan = probe.numeric_scan(coords, 0, len(coords))
    assert scan.f64_guarded == len(scan.f64_values) == 1
    assert scan.f64_values == ((12.5, -3.25, 7.0),)


def test_residue_cadence_measures_the_refused_stream() -> None:
    preamble = bytes(4)
    record = idrun(2, 1, [1, 2])
    junk = b"\x01\x00\x04\x00" + bytes(34) + b"\x01\x00\x04\x00" + bytes(34)
    data = part(preamble, record, record, junk)
    tiling = probe.walk(data, 0, len(data))
    assert not tiling.exact
    markers, top = probe.residue_cadence(data, tiling)
    assert markers == 2
    assert top[0] == (38, 1)


def test_split_facet_carriers_follows_strip_records(tmp_path: Path) -> None:
    census = tmp_path / "census.csv"
    census.write_text(
        "sha256,family,strip_records\n"
        "aaaa,no-pool,0\n"
        "bbbb,no-pool,\n"
        "cccc,no-pool,8\n"
        "dddd,stdcont,16\n",
        encoding="utf-8",
    )
    rows = probe._census_rows(census, "no-pool")
    primary, carriers = probe.split_facet_carriers(rows)
    assert primary == ["aaaa", "bbbb"]
    assert carriers == ["cccc"]


def _measurement(**overrides) -> dict:
    base = {
        "sha16": "00000000",
        "bytes": 100,
        "preamble": 10,
        "framed": 40,
        "residue": 50,
        "exact": False,
        "coverage": 0.4,
        "records": 2,
        "f64_raw": 0,
        "f64_guarded": 0,
        "f32_raw": 0,
        "f32_guarded": 0,
        "knot_runs": 0,
        "weight_runs": 0,
        "f32_region_values": (),
        "framed_f64_raw": 0,
        "framed_f64_guarded": 0,
        "framed_f32_raw": 0,
        "framed_f32_guarded": 0,
        "framed_knot_runs": 0,
        "framed_weight_runs": 0,
        "f32_framed_values": (),
    }
    base.update(overrides)
    return base


def test_population_claims_separate_the_128_from_the_control() -> None:
    primary = [_measurement(), _measurement(sha16="11111111", bytes=200, residue=100)]
    carriers = [_measurement(sha16="cccccccc", bytes=50, framed=0, residue=50, records=0)]
    rows = {row[0]: row for row in probe.per_file_claims(primary, carriers, primary, carriers)}
    assert rows["CG-08"][1] == "population:2"
    assert rows["CG-08b"][1] == "population:3"
    assert "bytes=300" in rows["CG-08"][6]
    assert "bytes=350" in rows["CG-08b"][6]
    assert rows["CG-08c"][1] == "population:1"
    assert "residue=150" in rows["CG-08"][6]
    assert rows["CG-08d"][1] == "population:2:unguarded"
    assert rows["CG-08e"][1] == "population:3:unguarded"


def test_footprint_row_prices_what_the_guard_refuses() -> None:
    guarded = [_measurement(framed=40), _measurement(sha16="11111111", framed=0, records=0)]
    upper = [_measurement(framed=120), _measurement(sha16="11111111", framed=80, records=1)]
    footprint = {
        "files": 2,
        "swallowed": 160,
        "by_family": {"idrun16": 1, "idrun32": 1},
        "longest": 80,
        "exact_guarded": 0,
        "exact_unguarded": 1,
        "nogrid_guarded": 1,
        "nogrid_unguarded": 0,
    }
    row = probe._footprint_row(guarded, upper, footprint)
    assert row[0] == "CG-16"
    assert "framed_delta=160" in row[6]
    assert "swallowed=160" in row[6]
    assert "idrun16=1 idrun32=1" in row[6]
    assert "nogrid guarded=1 unguarded=0" in row[6]

