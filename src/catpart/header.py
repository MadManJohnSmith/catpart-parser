"""Parse the 32-byte outer header of CATIA V5 ``.CATPart``/``.CATProduct`` files.

Evidence: docs/evidence/2026-11-07-container-triage.md ("Outer container
structure"), consistent across all 1818 magic-verified corpus files:

- bytes 0-8:   magic ``56 35 5F 43 46 56 32 00`` — ASCII ``V5_CFV2\\0``.
- bytes 8-12:  dword, **big-endian**, always < file size (``size - dword``
  has median 10280, p25-p75 9308-11694, min 3138). Its semantics are an
  open question, so schema v0 reports the value as-is.
- bytes 12-16: small varying dword, never ``0xFFFFFFFF`` (0/1818).
- bytes 16-24: eight ``0xFF`` bytes in 1672/1818 (92.0%) of files.
- bytes 24-32: zeros in all examined samples.

Schema v0 (ticket #11) reports only the magic string and the header
dword; the remaining fields land with later tickets. The magic is
reported as observed — it is *not* verified here, because 6 corpus files
are known to lack it and the tool must still describe them.
"""

from __future__ import annotations

import dataclasses

HEADER_SIZE = 32
MAGIC_SIZE = 8


@dataclasses.dataclass(frozen=True)
class HeaderInfo:
    """The schema-v0 subset of the outer header (bytes 0-12)."""

    magic: str
    header_dword: int


def parse_header(head: bytes) -> HeaderInfo:
    """Parse the first :data:`HEADER_SIZE` bytes of a file.

    ``magic`` is the ASCII (latin-1) decoding of bytes 0-8 with trailing
    NUL bytes stripped; ``header_dword`` is the big-endian uint32 at
    bytes 8-12.

    Raises :class:`ValueError` when fewer than 32 bytes are available:
    the 32-byte header is the smallest documented structure, and a
    shorter buffer is not a CATIA V5 container (ticket #14 classifies
    such truncations as failures).
    """
    if len(head) < HEADER_SIZE:
        raise ValueError(
            f"not a CATIA V5 container: header needs {HEADER_SIZE} bytes, got {len(head)}"
        )
    magic = head[:MAGIC_SIZE].rstrip(b"\x00").decode("latin-1")
    header_dword = int.from_bytes(head[8:12], "big")
    return HeaderInfo(magic=magic, header_dword=header_dword)
