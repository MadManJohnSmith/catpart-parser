"""Parse the 32-byte outer header of CATIA V5 ``.CATPart``/``.CATProduct`` files.

Evidence: docs/evidence/2026-11-07-container-triage.md ("Outer container
structure"), consistent across all 1818 magic-verified corpus files, plus
docs/evidence/2026-11-07-container-table-and-trailer.md (the B1 note) for
the dword12 chain law and the dual-region variant:

- bytes 0-8:   magic ``56 35 5F 43 46 56 32 00`` — ASCII ``V5_CFV2\\0``.
- bytes 8-12:  dword8, **big-endian**, always < file size (``size - dword8``
  has median 10280, p25-p75 9308-11694, min 3138). Law H1 (B1 note,
  1556/1556 CB__END-ending files) decodes it as the start offset of the
  ``CATIA_V5 CB0001\\0`` tail region; the value is reported as-is.
- bytes 12-16: dword12, **big-endian**, small varying value, never
  ``0xFFFFFFFF`` (0/1818). Law H1: dword8 + dword12 == file size and
  dword12 == trailer G on CB__END-ending files — the tail region's length.
- bytes 16-24: eight ``0xFF`` bytes in 1672/1818 (92.0%) of files. The
  146 exceptions are the dual-region variant (B1 note): a distinct writer
  generation whose header continues as two more big-endian dwords —
  dword16 at 16-20 (the offset of an additional ``CATIA_V5 CB0001\\0``
  region in 143/146) and dword20 at 20-24 (semantics unproven).
- bytes 24-32: zeros in all examined samples (not parsed).

The magic is reported as observed — it is *not* verified here, because 6
corpus files are known to lack it and the tool must still describe them;
the clean-parse invariant (``catpart.fitness.invariants``) enforces it.
"""

from __future__ import annotations

import dataclasses

HEADER_SIZE = 32
MAGIC_SIZE = 8

#: Bytes 16-24 of a standard-generation header (Phase 1 evidence: 1672/1818).
FF8 = b"\xff" * 8


@dataclasses.dataclass(frozen=True)
class HeaderInfo:
    """The documented fields of the outer header (bytes 0-32).

    ``header_dword16``/``header_dword20`` are ``None`` on the standard
    ff x8 generation, where bytes 16-24 are the marker itself rather
    than dwords.
    """

    magic: str
    header_dword: int
    header_dword12: int
    ff8_at_16_24: bool
    header_dword16: int | None
    header_dword20: int | None


def parse_header(head: bytes) -> HeaderInfo:
    """Parse the first :data:`HEADER_SIZE` bytes of a file.

    ``magic`` is the ASCII (latin-1) decoding of bytes 0-8 with trailing
    NUL bytes stripped; the dwords are big-endian uint32s (dword8 at
    bytes 8-12, dword12 at 12-16, and — dual-region variant only —
    dword16 at 16-20 and dword20 at 20-24).

    Raises :class:`ValueError` when fewer than 32 bytes are available:
    the 32-byte header is the smallest documented structure, and a
    shorter buffer is not a CATIA V5 container (the fitness runner
    classifies such truncations as crashes).
    """
    if len(head) < HEADER_SIZE:
        raise ValueError(
            f"not a CATIA V5 container: header needs {HEADER_SIZE} bytes, got {len(head)}"
        )
    magic = head[:MAGIC_SIZE].rstrip(b"\x00").decode("latin-1")
    header_dword = int.from_bytes(head[8:12], "big")
    header_dword12 = int.from_bytes(head[12:16], "big")
    ff8 = head[16:24] == FF8
    header_dword16: int | None = None
    header_dword20: int | None = None
    if not ff8:
        header_dword16 = int.from_bytes(head[16:20], "big")
        header_dword20 = int.from_bytes(head[20:24], "big")
    return HeaderInfo(
        magic=magic,
        header_dword=header_dword,
        header_dword12=header_dword12,
        ff8_at_16_24=ff8,
        header_dword16=header_dword16,
        header_dword20=header_dword20,
    )
