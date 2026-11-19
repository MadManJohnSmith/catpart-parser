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
