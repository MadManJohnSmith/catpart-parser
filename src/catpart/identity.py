"""The CATIA identity block: the save-time document name (schema v1).

Evidence: docs/evidence/2026-11-08-units-names-probe.md (C3 phase A,
ticket #25) and
docs/evidence/2026-11-07-container-payload-layout.md ("The CATIA
identity block"). Exactly one CATStorageProperty block per file is
named ``CATIA`` with a 16-zero-byte GUID slot (claim D1, 108/108 on the
R15-R24 probe sample; B3: 114/114) — a file-identity property block
whose name2 field carries the *save-time document file name* whenever
that field is non-empty (40/108 sample files; always with the
.CATPart/.CATProduct extension, D4 40/40). The stored name is the
save-time name, not the current file name: it equals the manifest
basename on 37/40 present cases, and the 3 exceptions are renamed files
keeping the old name (``Geometrical Bundle1.CATProduct`` with a space
vs the current ``GeometricalBundle1.CATProduct``) — the field is
reported as-is and never used as the current basename.

Walk model (claim D2, 108/108: the walk completes on every identity
block of the sample). From the block start ``b``:

- ``34 12 "CATStorageProperty" 80 01 00 00 00 00 22 <u8> 00 00 00 34
  01 01 00 34 10 "CATUnicodeString"`` — the B3 block header; the
  ``CATUnicodeString`` marker is located within the first 64 bytes.
- name1: ``34 <len> <ascii>`` at marker+16, terminated by a C3b follow
  byte (``0x9f`` or a type-tag byte); the identity block's name1 is
  exactly ``CATIA``.
- name2: ``a0 02 00 00 00 00 34 <len> <ascii> <C3b follow byte>``.
  Empty field: ``34 00 9f``.

Every element is bounds-checked and the walk never raises: a file with
no identity block, with more than one, or with a malformed walk
yields ``None`` (the corpus never shows these — D1/D2 — so ``None`` is
also the honest "not documented for this file" value). Presence is
version-dependent in the corpus: the name is carried only by pre-R20
files of the probe sample (R15 8/9 ... R19 5/16, R20-R24 0/43); the
field stays null on files that lack it.

The unit-system side of the phase A probe is a **documented negative**
(no unit-system structure exists in the two decoded territories), so
this module parses names only — there is deliberately no units field
(docs/format/payload-blocks.md, section 5.3).
"""

from __future__ import annotations

BLOCK_TAG = b"\x34\x12"
STORAGE_WORD = b"CATStorageProperty"
UNICODE_STRING = b"CATUnicodeString"
#: The 6-byte property-name header preceding each tag34 name length.
NAME_HEADER6 = b"\xa0\x02\x00\x00\x00\x00"
NAME_TAG = 0x34
IDENTITY_NAME = b"CATIA"

#: C3b follow bytes that terminate a tag34 name (0x9f or a type tag).
TERMINATORS = frozenset((0x80, 0x9F, 0xA0, 0xE0))

_MARKER_WINDOW = 64  # CATUnicodeString sits within the block header
_NAME_LIMIT = 255  # tag34 lengths are u8


def parse_document_name(data) -> str | None:
    """Return the save-time document name carried by the identity block.

    ``data`` is any bytes-like buffer supporting ``find`` and slicing
    (``bytes`` or a read-only :class:`mmap.mmap`). The whole file is
    scanned for storage blocks (the identity block sits in the early
    property area, but claim D1 was measured whole-file). Returns
    ``None`` when the file carries no identity block, more than one, or
    when the name2 field is empty or its walk fails — never raises on
    malformed input.
    """
    blocks = []
    pos = data.find(STORAGE_WORD)
    while pos >= 0:
        blk = pos - 2 if data[pos - 2 : pos] == BLOCK_TAG else pos
        if _read_name1(data, blk) == IDENTITY_NAME:
            blocks.append(blk)
            if len(blocks) > 1:
                return None  # D1: exactly one identity block; never guess
        pos = data.find(STORAGE_WORD, pos + 1)
    if not blocks:
        return None
    return _read_name2(data, blocks[0])


def _read_name1(buf, blk: int) -> bytes | None:
    """name1 of the storage block at ``blk``, or ``None`` if malformed."""
    bi = buf.find(UNICODE_STRING, blk, blk + _MARKER_WINDOW)
    if bi < 0 or bi + 24 > len(buf):
        return None
    if buf[bi + 16 : bi + 22] != NAME_HEADER6 or buf[bi + 22] != NAME_TAG:
        return None
    ln = buf[bi + 23]
    p = bi + 24 + ln
    if ln == 0 or p >= len(buf) or buf[p] not in TERMINATORS:
        return None
    try:
        decoded = bytes(buf[bi + 24 : p]).decode("ascii")
    except UnicodeDecodeError:
        return None
    return decoded.encode("ascii") if decoded.isprintable() else None


def _read_name2(buf, blk: int) -> str | None:
    """name2 of the identity block at ``blk``; ``None`` when absent/malformed."""
    bi = buf.find(UNICODE_STRING, blk, blk + _MARKER_WINDOW)
    if bi < 0 or bi + 24 > len(buf):
        return None
    if buf[bi + 16 : bi + 22] != NAME_HEADER6 or buf[bi + 22] != NAME_TAG:
        return None
    p = bi + 24 + buf[bi + 23]
    if p + 8 >= len(buf) or buf[p] not in TERMINATORS:
        return None
    if buf[p + 1 : p + 7] != NAME_HEADER6 or buf[p + 7] != NAME_TAG:
        return None
    ln2 = buf[p + 8]
    end = p + 9 + ln2
    if end >= len(buf) or buf[end] not in TERMINATORS:
        return None
    if ln2 == 0:
        return None
    try:
        decoded = bytes(buf[p + 9 : end]).decode("ascii")
    except UnicodeDecodeError:
        return None
    return decoded if decoded.isprintable() else None
