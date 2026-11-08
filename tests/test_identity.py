"""The CATIA identity block seam: ``catpart.identity.parse_document_name``.

Ticket #25 Phase B emission of the only name structure Phase A
documented: the save-time document file name in the CATIA identity
block's name2 (docs/evidence/2026-11-08-units-names-probe.md, claims
D1/D2/D3/D4; B3's identity-block paragraph). The unit-system side of
the probe is a documented negative, so no units field exists.

The fixtures below assemble the identity block byte-exactly as observed
(B3 header layout + probe walk): ``34 12 "CATStorageProperty" 80 01 00
00 00 00 22 0c 00 00 00 34 01 01 00 34 10 "CATUnicodeString" a0 02 00
00 00 00 34 05 "CATIA" 9f`` then the name2 field
``a0 02 00 00 00 00 34 <len> <ascii> 9f`` (empty: ``34 00 9f``), then
the ``3b 10`` marker with 16 zero bytes and a trailing ``9f``.
"""

from __future__ import annotations

import catpart.identity as identity
from conftest import catia_identity_block as identity_block


def other_block(name1: bytes = b"CATProdCont") -> bytes:
    """A non-identity storage block (same layout, other doc type)."""
    block = b"\x34\x12" + b"CATStorageProperty"
    block += b"\x80\x01\x00\x00\x00\x00\x22\x0c\x00\x00\x00"
    block += b"\x34\x01\x01\x00" + b"\x34\x10" + b"CATUnicodeString"
    block += b"\xa0\x02\x00\x00\x00\x00\x34" + bytes([len(name1)])
    block += name1 + b"\x9f"
    block += b"\xa0\x02\x00\x00\x00\x00\x34\x00" + b"\x9f"
    block += b"\x3b\x10" + bytes(8) + bytes(range(16)) + b"\x9f"
    return block


def test_returns_the_save_time_document_name() -> None:
    data = other_block() + identity_block(
        b"SP02_ALPHA5_SEPA2_RETENUE_ROULEMENT.CATPart"
    )
    assert (
        identity.parse_document_name(data)
        == "SP02_ALPHA5_SEPA2_RETENUE_ROULEMENT.CATPart"
    )


def test_empty_name2_field_is_null() -> None:
    # The 68/108 sample files whose identity block has no name2
    # (``34 00 9f``), including every R20+ file of the sample.
    assert identity.parse_document_name(identity_block()) is None


def test_no_identity_block_is_null() -> None:
    assert identity.parse_document_name(other_block() + other_block()) is None
    assert identity.parse_document_name(b"") is None


def test_two_identity_blocks_are_null() -> None:
    # D1 says exactly one per file; a second one is undocumented, so the
    # honest value is null (never guess between candidates).
    data = identity_block(b"A.CATPart") + identity_block(b"B.CATPart")
    assert identity.parse_document_name(data) is None


def test_malformed_walk_is_null() -> None:
    # Terminator byte replaced: the C3b framing no longer verifies.
    bad = bytearray(identity_block(b"X.CATPart"))
    bi = bad.find(b"CATIA") + 5
    bad[bi] = 0x01  # not a C3b follow byte
    assert identity.parse_document_name(bytes(bad)) is None
    # name1 no longer CATIA: not an identity block.
    other = bytearray(identity_block(b"X.CATPart"))
    ci = other.find(b"CATIA")
    other[ci + 3] = ord("X")  # CATX...
    assert identity.parse_document_name(bytes(other)) is None


def test_truncated_buffer_never_raises() -> None:
    full = identity_block(b"Sample.CATPart")
    term = full.find(b"Sample.CATPart") + len(b"Sample.CATPart")
    for cut in range(0, len(full)):
        result = identity.parse_document_name(full[:cut])
        # The walk is either incomplete (null) or, when the cut keeps
        # every byte up to and including the name2 terminator, complete.
        assert result is None or result == "Sample.CATPart"
        if cut <= term:
            assert result is None


def test_non_ascii_name2_is_null() -> None:
    bad = bytearray(identity_block(b"Sample.CATPart"))
    bad[bad.find(b"Sample.CATPart")] = 0xC3  # non-ASCII byte inside name2
    assert identity.parse_document_name(bytes(bad)) is None
