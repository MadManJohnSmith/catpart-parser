"""Corpus-free tests for the compact ``a5 03 34`` head (2026-11-21).

The submarine snapshot's 94 ``no-evaluable-surface`` parts carry a third
grammar under the same marker.  It has no subtype field: each lane block
stores ``(degree << 2) | 1``, ``(knot_count << 2) | 1`` and either implicit
clamped multiplicities (``0x0c``) or an explicit vector (``0x04``), then the
knots, then ``0x01``/``0x05`` and the ``poles_u × poles_v`` f64 triples.
These tests pin:

- the lane tokens, the pole law ``sum(mult) - degree - 1`` and the grid
  offset predicted by the head (textbook hex of two measured frames);
- the tail is *not* a closure law for this grammar (0, 141 and 3597 bytes
  all decode), while the legacy 152/154 law stays in force.

Fixtures are synthetic; no corpus binary is read.
"""

from __future__ import annotations

import struct

import pytest

from catpart.geometry import surface


def f64(*values: float) -> bytes:
    return b"".join(struct.pack("<d", value) for value in values)


def compact_lane(
    degree: int,
    knots: tuple[float, ...],
    mult: tuple[int, ...] | None = None,
) -> bytes:
    """One compact lane block; an explicit vector when ``mult`` is given."""
    marker = surface.COMPACT_KNOTS_IMPLICIT if mult is None else surface.COMPACT_KNOTS_EXPLICIT
    out = bytes([(degree << 2) | 1, (len(knots) << 2) | 1, marker]) + f64(*knots)
    if mult is not None:
        out += bytes([(count << 2) | 1 for count in mult])
    return out


def compact_head(
    degree_u: int = 3,
    knots_u: tuple[float, ...] = (0.0, 1.0),
    mult_u: tuple[int, ...] | None = None,
    degree_v: int = 1,
    knots_v: tuple[float, ...] = (0.0, 1.0),
    mult_v: tuple[int, ...] | None = None,
    pole_marker: int = 0x01,
) -> bytes:
    return (
        compact_lane(degree_u, knots_u, mult_u)
        + compact_lane(degree_v, knots_v, mult_v)
        + bytes([pole_marker])
    )


def compact_poles(poles_u: int, poles_v: int, scale: float = 10.0):
    return [
        [(scale * i, scale * j, 0.0) for j in range(poles_v)]
        for i in range(poles_u)
    ]


def pole_bytes(poles) -> bytes:
    return b"".join(f64(*point) for row in poles for point in row)


def compact_payload(
    head: bytes | None = None,
    poles=None,
    tail: int = 141,
    **kwargs,
) -> bytes:
    if head is None:
        head = compact_head(**kwargs)
    if poles is None:
        # The default head's law: 3+1+(2-2) = 4 poles in u, 1+1 = 2 in v.
        poles = compact_poles(4, 2)
    return head + pole_bytes(poles) + bytes(tail)


# --------------------------------------------------------------- head


def test_compact_head_pins_the_lane_tokens_and_the_pole_law() -> None:
    blob = compact_payload()
    head = surface.parse_surface_head(blob, 0, len(blob))
    assert head is not None
    assert head.subtype == surface.SUBTYPE_COMPACT
    assert (head.degree_u, head.degree_v) == (3, 1)
    assert (head.n_u, head.n_v) == (2, 2)
    assert head.mult_u == (4, 4)
    assert head.mult_v == (2, 2)
    assert (head.poles_u, head.poles_v) == (4, 2)
    assert head.points == 8
    assert head.head_bytes == 2 * (3 + 16) + 1
    assert head.grid == head.head_bytes
    assert head.tail == 141
    assert head.lanes_monotone
    assert head.knots == ((0.0,) * 4 + (1.0,) * 4, (0.0,) * 2 + (1.0,) * 2)


def test_compact_head_decodes_the_measured_frame_hex() -> None:
    # ST-Stern-ins.CATPart frame 0x5a56, payload 0x5a5e (372 B): 0d 09 0c is
    # degree 3 / 2 knots / implicit, then 0.0, 1.0, then 05 09 0c is
    # degree 1 / 2 knots / implicit, then 0x01 opens the 4 x 2 net.
    head = bytes.fromhex(
        "0d090c 0000000000000000 000000000000f03f"
        "05090c 0000000000000000 000000000000f03f 01"
    )
    blob = head + pole_bytes(compact_poles(4, 2)) + bytes(141)
    decoded = surface.parse_surface_head(blob, 0, len(blob))
    assert decoded is not None
    assert (decoded.degree_u, decoded.degree_v) == (3, 1)
    assert (decoded.n_u, decoded.n_v) == (2, 2)
    assert decoded.mult_u == (4, 4)
    assert decoded.mult_v == (2, 2)
    assert (decoded.poles_u, decoded.poles_v) == (4, 2)
    assert decoded.grid == 0x27
    assert decoded.head_bytes == 39
    assert decoded.tail == 141
    assert decoded.knots_u == (0.0, 1.0)
    assert decoded.knots_v == (0.0, 1.0)


def test_compact_explicit_multiplicity_vector() -> None:
    # BW-Hull-Bow-YL.CATPart frame 0x6f2e (1711 B): 15 0d 04 is degree 5,
    # 3 knots, explicit; the knots are followed by 19 05 19 = (6, 1, 6).
    head = bytes.fromhex(
        "150d04"
        "8109a7b5e046843f bf59b59d1683e13f cae236e9ffffef3f 190519"
        "150d0c"
        "0000000000000000 000000000000e03f 000000000000f03f"
        "01"
    )
    blob = head + pole_bytes(compact_poles(7, 7)) + bytes(477)
    decoded = surface.parse_surface_head(blob, 0, len(blob))
    assert decoded is not None
    assert (decoded.degree_u, decoded.degree_v) == (5, 5)
    assert decoded.mult_u == (6, 1, 6)
    assert decoded.mult_v == (6, 1, 6)
    assert (decoded.poles_u, decoded.poles_v) == (7, 7)
    assert decoded.head_bytes == 58
    assert decoded.tail == 477
    # sum(mult) - degree - 1 == (degree + 1) + (n - 2) for the clamped form.
    assert decoded.poles_u == sum(decoded.mult_u) - decoded.degree_u - 1


@pytest.mark.parametrize("tail", [0, 141, 185, 3597])
def test_compact_tail_is_not_a_closure_law(tail: int) -> None:
    blob = compact_payload(tail=tail)
    head = surface.parse_surface_head(blob, 0, len(blob))
    assert head is not None
    assert head.tail == tail


@pytest.mark.parametrize("marker", [0x01, 0x05])
def test_compact_accepts_the_two_measured_pole_markers(marker: int) -> None:
    blob = compact_payload(pole_marker=marker)
    assert surface.parse_surface_head(blob, 0, len(blob)) is not None


def test_compact_refuses_a_foreign_pole_marker() -> None:
    blob = compact_payload(pole_marker=0x0F)
    assert surface.parse_surface_head(blob, 0, len(blob)) is None


def test_compact_refuses_a_broken_lane() -> None:
    # A multiplicity token must be (mult << 2) | 1; 0x02 is not a token.
    head = bytearray(compact_head(mult_u=(4, 4)))
    head[3 + 16 + 1] = 0x02  # second u multiplicity byte
    blob = bytes(head) + pole_bytes(compact_poles(4, 2)) + bytes(141)
    assert surface.parse_surface_head(blob, 0, len(blob)) is None
    non_monotone = compact_payload(knots_u=(0.0, 0.0))
    assert surface.parse_surface_head(non_monotone, 0, len(non_monotone)) is None
    overrun = compact_payload()[:-141 - 8]
    assert surface.parse_surface_head(overrun, 0, len(overrun)) is None
