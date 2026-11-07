"""Parse the trailer terminating a CATIA V5 ``.CATPart``/``.CATProduct`` file.

Evidence: docs/evidence/2026-11-07-container-table-and-trailer.md
("Trailer"). The trailer is the last 36 bytes of a file ending with
``CB__END\\0`` (``43 42 5F 5F 45 4E 44 00``): seven **big-endian**
dwords plus the 8-byte marker. Corpus rates on the 1556 CB__END-ending
files:

- A (size-36): constant ``0x00000001`` — 1556/1556.
- B (size-32): absolute file offset of the writer registration block —
  byte-proven as a pointer (it moves by exactly the file-size delta
  between near-identical saves); the block itself validates on
  1553/1556 (the 3 failures are dual-region files).
- C (size-28), D (size-24): a pair stored twice, equal on every file
  (1556/1556); value file-dependent (``0x000000e7`` is the mode),
  semantics unproven.
- E (size-20): 0 on 1555/1556 (the one exception is a dual-region file).
- F (size-16): 0 (1378 files), 1 (177), 2 (1); semantics unproven.
- G (size-12): == header dword12 == size - dword8 (law H1) — the
  length of the ``CATIA_V5 CB0001\\0`` tail region.

The writer registration block at offset B is
``[tag 0x4d|0x4e][u32le 17]"DASSAULT-SYSTEMES"[u32le 5]"CATIA"[u32le
6]"041803"`` (41 bytes); tag ``0x4e`` on most R15-R18 and R21 files,
``0x4d`` on most R19/R20 and R23+ files; the tag's meaning and the
``041803`` code are open questions.

Files not ending with ``CB__END\\0`` (262/1818, including the dual-region
files without a CB__END tail) have no trailer: :func:`parse_trailer`
returns ``None``. Trailer *fields* are never validated here — they are
reported as-is; the clean-parse invariants enforce the corpus-wide laws.
"""

from __future__ import annotations

import dataclasses

TRAILER_SIZE = 36
MARKER = b"CB__END\x00"

_REGISTRATION_SIZE = 41
_REGISTRATION_TAGS = (0x4D, 0x4E)
_REGISTRATION_COMPANY = b"DASSAULT-SYSTEMES"
_REGISTRATION_PRODUCT = b"CATIA"
_REGISTRATION_CODE = b"041803"


@dataclasses.dataclass(frozen=True)
class RegistrationInfo:
    """The writer registration block at trailer field B (B1 evidence)."""

    tag: str
    company: str
    product: str
    code: str

    def to_json(self) -> dict:
        return {
            "tag": self.tag,
            "company": self.company,
            "product": self.product,
            "code": self.code,
        }


@dataclasses.dataclass(frozen=True)
class TrailerInfo:
    """The seven trailer dwords plus the decoded registration block."""

    a: int
    registration_offset: int
    c: int
    d: int
    e: int
    f: int
    tail_region_length: int
    registration: RegistrationInfo | None

    def to_json(self) -> dict:
        return {
            "a": self.a,
            "registration_offset": self.registration_offset,
            "c": self.c,
            "d": self.d,
            "e": self.e,
            "f": self.f,
            "tail_region_length": self.tail_region_length,
            "registration": (
                None if self.registration is None else self.registration.to_json()
            ),
        }


def parse_registration(data, offset: int) -> RegistrationInfo | None:
    """Decode the registration block at ``offset``, or ``None``.

    ``data`` is any bytes-like buffer supporting slicing. The block must
    match the documented 41-byte pattern byte-exact (tag 0x4d/0x4e and
    the three length-prefixed strings); anything else — including an
    offset that would run past the buffer — yields ``None`` (the 3/1556
    corpus failures are reported, not repaired).
    """
    if offset < 0:
        return None
    block = bytes(data[offset : offset + _REGISTRATION_SIZE])
    if len(block) < _REGISTRATION_SIZE or block[0] not in _REGISTRATION_TAGS:
        return None

    def le(start: int) -> int:
        return int.from_bytes(block[start : start + 4], "little")

    if le(1) != 17 or block[5:22] != _REGISTRATION_COMPANY:
        return None
    if le(22) != 5 or block[26:31] != _REGISTRATION_PRODUCT:
        return None
    if le(31) != 6 or block[35:41] != _REGISTRATION_CODE:
        return None
    return RegistrationInfo(
        tag=chr(block[0]),
        company=_REGISTRATION_COMPANY.decode("ascii"),
        product=_REGISTRATION_PRODUCT.decode("ascii"),
        code=_REGISTRATION_CODE.decode("ascii"),
    )


def parse_trailer(data) -> TrailerInfo | None:
    """Parse the trailer of ``data``, or ``None`` when there is none.

    ``data`` is any bytes-like buffer supporting slicing and ``len()``
    (``bytes`` or a read-only :class:`mmap.mmap`). The trailer exists
    when the buffer ends with the ``CB__END\\0`` marker and carries the
    full 36-byte model; the seven dwords are big-endian.
    """
    size = len(data)
    if size < TRAILER_SIZE or bytes(data[size - 8 : size]) != MARKER:
        return None
    base = size - TRAILER_SIZE
    dwords = tuple(
        int.from_bytes(data[base + 4 * i : base + 4 * i + 4], "big") for i in range(7)
    )
    a, registration_offset, c, d, e, f, tail_region_length = dwords
    return TrailerInfo(
        a=a,
        registration_offset=registration_offset,
        c=c,
        d=d,
        e=e,
        f=f,
        tail_region_length=tail_region_length,
        registration=parse_registration(data, registration_offset),
    )
