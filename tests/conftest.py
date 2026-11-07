"""Shared test fixtures: synthetic CATIA V5-shaped files.

The real corpus is gitignored and never present in CI (Spec A #8, ADR-0003),
so every test builds its own minimal, structurally genuine fixture here.
The layouts mirror the byte-level facts in
docs/evidence/2026-11-07-container-triage.md; ticket A2 (#12) replaces this
ad-hoc builder with the committed deterministic fixture generator.

Structural facts exercised by ``build_catpart`` (evidence note, byte ranges):

- 32-byte header: magic ``V5_CFV2\\0`` (bytes 0-8), big-endian dword
  (bytes 8-12), small dword (bytes 12-16), eight ``0xFF`` bytes (bytes
  16-24), zeros (bytes 24-32).
- Plaintext container-name table records: a small little-endian dword
  followed by one or two NUL-terminated ASCII names (record format is an
  open question; the fixture only mimics the observed shape).
- CNEXTINFOS version-marker line after the table region.
- Trailer ending with ``CB__END\\0``.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

MAGIC = b"V5_CFV2\x00"
CNEXTINFOS_LINE = (
    b"NOTHING-CNEXTINFOS-UpdateVersion-StreamBlock-SafeEarlyBlock-"
    b"StrongEarly&V5R21SP0HF0 built on 01-15-2014.20.00"
)
TRAILER = b"CB__END\x00"

# Names from the evidence note's container-name table, in the order a small
# product-like fixture presents them.
EXAMPLE_TABLE_NAMES = (
    "CameraStartupContainer",
    "CATFeatCont",
    "CATProdCont",
    "CGMGeom",
    "CATContainer",
    "V5USERID",
)


def _name_record(*names: str) -> bytes:
    """One table record as observed: small dword, then NUL-terminated names."""
    blob = b"".join(name.encode("ascii") + b"\x00" for name in names)
    return struct.pack("<I", 2 + len(names)) + blob


def build_catpart(
    *,
    magic: bytes = MAGIC,
    header_dword: int = 0x0001_0000,
    table_names: tuple[str, ...] = EXAMPLE_TABLE_NAMES,
    with_marker: bool = True,
    with_trailer: bool = True,
    payload: bytes = b"\x12\x34\x56\x78" * 8,
    pad_before_table: int = 0x700,
) -> bytes:
    """Assemble a minimal, structurally genuine CATIA V5-shaped file."""
    header = magic[:8].ljust(8, b"\x00")
    header += struct.pack(">I", header_dword)
    header += struct.pack("<I", 0x0000_1FA4)  # small dword, bytes 12-16
    header += b"\xff" * 8  # bytes 16-24
    header += b"\x00" * 8  # bytes 24-32
    assert len(header) == 32

    parts = [header, b"\x00" * pad_before_table]
    if table_names:
        # Two names per record, as observed in the corpus table region.
        for i in range(0, len(table_names), 2):
            parts.append(_name_record(*table_names[i : i + 2]))
    if with_marker:
        parts.append(b"\x00\x00\x00\x00" + CNEXTINFOS_LINE)
    parts.append(payload)
    if with_trailer:
        parts.append(b"\x00\x00\x00\x00" + TRAILER)
    return b"".join(parts)


@pytest.fixture(name="build_catpart")
def build_catpart_fixture():
    return build_catpart


@pytest.fixture(name="catpart_file")
def catpart_file_fixture(tmp_path: Path, build_catpart):
    """A valid-shaped synthetic .CATPart on disk."""
    path = tmp_path / "sample.CATPart"
    path.write_bytes(build_catpart())
    return path
