"""Stream-level version-tag and compression census (W19, B9).

The nested-store locator (``catpart.geometry.store``) and the decode
families read fixed byte signatures — the ``V5_CFV2\\0`` store header,
the ``CATIA_V5 CB0001\\0`` catalog magic, the ``10 24 04``/``01 06``
pool wrappers, the ``01 <marker>`` facet headers. B9 asks the question
the store level cannot answer: do some writer generations carry a
*stream-level* alternate version header or a *compressed sub-stream*
that such fixed-magic scanning walks past?

The GE-V7 candidate tags (``docs/format/geometry.md`` 6.3) are the one
version-like stream artifact documented so far: little-endian framed
strings ``[u32le L]"2-0"`` / ``[u32le L]"2X-0"`` inside ``CGMGeom``
regions, 4/44 files on the 81-file scan, "a candidate discriminator for
a future CGM-stream ticket". This module is that ticket's
classification core: it scans byte ranges for

- **version tags** — every ``[u32le L][L ASCII]`` frame whose text is
  version-shaped (``2-0``, ``2X-0``, ``10-0``, ...), counted per text
  (:func:`scan_version_tags`);
- **compression signatures** — zlib/gzip/bzip2/xz/lzma/lz4/zstd/snappy
  header images (:func:`scan_compression_signatures`), each verified
  fail-closed before any claim (:func:`verify_deflate`,
  :func:`verify_bz2`, :func:`verify_xz` — a candidate that does not
  decompress is never reported as compressed);
- **stream heads** — the per-block writer tag at block+112
  (``36 08 "FINJPL  "`` on the bulk-stream anchors,
  ``docs/evidence/2026-11-19-bulk-stream.md`` §2) that a writer
  generation could vary (:func:`block_writer_tag`).

What the scanner does and does not discriminate (the census rule from
``docs/agents/dispatch-recipes.md``):

- the zlib pre-filter accepts only CMF = ``0x78`` (32 KiB window) with
  a valid FCHECK byte — a deflate stream carried under another window
  size is NOT discriminated by this census;
- raw-LZMA candidates (``5D 00 00``) are counted as signatures, never
  as verified streams (no length law to verify against);
- lz4/zstd/snappy/bzip2/xz are signature-presence only (no stdlib
  decoder below the count level except bzip2/xz, which do verify);
- ``verify_*`` requires a full bounded decompression that reaches its
  own end (``eof``) with output >= :data:`MIN_OUTPUT` — a mid-payload
  ``78 9c`` byte pair on incompressible data, a truncated stream or a
  wrong-checksum embedding fails the law instead of being reported. A
  stream larger than the :data:`MAX_WINDOW` window cannot verify
  (documented miss, fail-closed).

The functions are pure byte scans over ``data[lo:hi]`` (no corpus
knowledge, no state), usable on ``bytes`` or a read-only ``mmap.mmap``.
The synthetic fixtures in ``tests/test_stream_version.py`` and the
Rust port (``port/src/geometry/stream_version.rs``) pin the same laws;
the deflate/bz2/xz verification arms are stdlib-only and stay
Python-side (the port ships no compression crate — port/Cargo.toml §2.1).
"""

from __future__ import annotations

import bz2
import lzma
import re
import zlib
from dataclasses import dataclass, field

#: A version-shaped tag text: digits, an optional X/x generation letter,
#: one to three dash-separated numeric suffixes. ``2-0``, ``2X-0``,
#: ``10-0``, ``3-1-0`` all match; ``Height``, ``2-``, ``-0`` do not.
VERSION_TAG_TEXT_RE = re.compile(rb"^\d{1,2}[Xx]?(-\d+){1,3}$")

#: The framing scan: ``[u32le L][L printable ASCII]`` — one length byte
#: in 1..20, three zero bytes, then exactly ``L`` printable bytes. The
#: regex finds only the 4-byte frame prefix; the text is then read at
#: its exact length ``L`` (a greedy printable match would over-extend a
#: tag followed by ASCII — ``[3]"2-0"junk`` must read ``2-0``, not
#: ``2-0junk``). The shape filter turns candidates into tags.
_TAG_PREFIX_RE = re.compile(rb"[\x01-\x14]\x00\x00\x00")
MAX_TAG_TEXT = 20

#: Valid zlib header pairs with CMF = 0x78 (32 KiB window): every FLG
#: with ``(0x78 << 8 | flg) % 31 == 0`` (RFC 1950 FCHECK). Detector
#: limit, stated in the module docstring: other CMF values are not
#: scanned.
ZLIB_CMF = 0x78
ZLIB_FLG_VALID = frozenset(
    b for b in range(256) if (ZLIB_CMF << 8 | b) % 31 == 0
)

#: Fixed header images of the other codecs, scanned as signature
#: presence. gzip = magic + deflate method (CM=8); bzip2 requires the
#: block magic right after the level digit (``1AY&SY`` = pi); raw-LZMA
#: candidates carry the common properties byte 0x5D (lc 3, lp 0, pb 2).
SIG_GZIP = b"\x1f\x8b\x08"
SIG_BZIP2 = re.compile(rb"BZh[1-9]\x31\x41\x59\x26\x53\x59")
SIG_XZ = b"\xfd7zXZ\x00"
SIG_LZMA_RAW = b"\x5d\x00\x00"
SIG_LZ4_FRAME = b"\x04\x22\x4d\x18"
SIG_ZSTD = b"\x28\xb5\x2f\xfd"
SIG_SNAPPY = b"\xff\x06\x00\x00sNaPpY"

#: Deflate verification: the smallest output the fail-closed law accepts
#: (a random ``78 9c`` pair producing 8 garbage bytes is not a stream)
#: and the largest input window consumed per candidate.
MIN_OUTPUT = 256
MAX_WINDOW = 4 * 1024 * 1024
MAX_OUTPUT = 16 * 1024 * 1024

#: Known CATIA/CGM markers recognized inside a byte buffer (the
#: decode families' own signatures). A verified compressed stream whose
#: output carries any of these is a candidate flip: content the
#: fixed-magic scanner reads past as opaque that decompresses to
#: something a shipped law could decode.
CATIA_MARKERS: tuple[tuple[str, bytes], ...] = (
    ("pool_wrapper", b"\x10\x24\x04\xff\xff\x00\x00\x00"),
    ("pool_group", b"\x01\x06"),
    ("facet_header", b"\x01\x41"),
    ("vertex_record", b"\x05\x08\x01"),
    ("e5_record", b"\xe5\x0d"),
    ("ab_frame", b"\xa5\x03\x34"),
    ("cb_catalog", b"CATIA_V5 CB0001\x00"),
    ("cb_end", b"CB__END\x00"),
    ("storage_block", b"\x34\x12CATStorageProperty"),
    ("store_header", b"V5_CFV2\x00"),
)


@dataclass(frozen=True)
class VerifiedStream:
    """One fail-closed verified compressed sub-stream.

    ``codec`` is ``zlib``/``gzip``/``bz2``/``xz``; ``consumed`` is the
    input bytes the decompressor accepted, ``output`` the bytes it
    produced (capped at :data:`MAX_OUTPUT`), ``eof`` whether the stream
    reached its own end inside the window, and ``markers`` the CATIA
    marker counts of the (capped) output — the flip evidence.
    """

    codec: str
    position: int
    consumed: int
    output: int
    eof: bool
    markers: dict[str, int] = field(default_factory=dict)


def scan_version_tags(data, lo: int, hi: int) -> dict[str, int]:
    """Count framed version-shaped strings in ``data[lo:hi]``.

    Every ``[u32le L][L ASCII]`` frame whose text is version-shaped
    (:data:`VERSION_TAG_TEXT_RE`) increments its decoded text; the text
    is read at its exact length ``L`` (see :data:`_TAG_PREFIX_RE`). The
    GE-V7 tags are the ``"2-0"``/``"2X-0"`` rows of this census; the
    function reports every other generation string the same framing
    carries. Overlapping frames do not occur (the length byte pins the
    text); a text counts once per occurrence.
    """
    counts: dict[str, int] = {}
    for m in _TAG_PREFIX_RE.finditer(data, lo, hi):
        length = data[m.start()]
        start = m.start() + 4
        end = start + length
        if end > hi:
            continue
        text = data[start:end]
        if all(0x20 <= b <= 0x7E for b in text) and VERSION_TAG_TEXT_RE.match(text):
            key = bytes(text).decode("ascii")
            counts[key] = counts.get(key, 0) + 1
    return counts


def scan_compression_signatures(data, lo: int, hi: int) -> dict[str, int]:
    """Count compression-header images in ``data[lo:hi]``.

    Signature presence, never a compression claim — the verified arm is
    :func:`verify_deflate`/:func:`verify_bz2`/:func:`verify_xz`. The
    zlib count is the valid-pair count (CMF ``0x78`` + FCHECK law);
    raw-LZMA ``5D 00 00`` is the highest-false-positive row and is
    reported as a candidate count only.
    """
    counts: dict[str, int] = {}
    view = data[lo:hi]
    counts["zlib_pair"] = _count_zlib_pairs(view)
    counts["gzip"] = _count_fixed(view, SIG_GZIP)
    counts["bzip2"] = len(SIG_BZIP2.findall(view))
    counts["xz"] = _count_fixed(view, SIG_XZ)
    counts["lzma_raw"] = _count_fixed(view, SIG_LZMA_RAW)
    counts["lz4_frame"] = _count_fixed(view, SIG_LZ4_FRAME)
    counts["zstd"] = _count_fixed(view, SIG_ZSTD)
    counts["snappy"] = _count_fixed(view, SIG_SNAPPY)
    return counts


def _count_zlib_pairs(view) -> int:
    """Valid ``78``-CMF header pairs in ``view`` (FCHECK law, RFC 1950)."""
    n = 0
    i = view.find(ZLIB_CMF.to_bytes(1, "big"))
    while i >= 0:
        if i + 1 < len(view) and view[i + 1] in ZLIB_FLG_VALID:
            n += 1
            i += 2
        else:
            i += 1
        i = view.find(ZLIB_CMF.to_bytes(1, "big"), i)
    return n


def _count_fixed(view, sig: bytes) -> int:
    n = 0
    i = view.find(sig)
    while i >= 0:
        n += 1
        i = view.find(sig, i + 1)
    return n


def _recognize(buf: bytes) -> dict[str, int]:
    """CATIA marker counts of ``buf`` (the flip-evidence classifier)."""
    return {
        name: _count_fixed(buf, sig)
        for name, sig in CATIA_MARKERS
    }


def recognize_markers(buf) -> dict[str, int]:
    """Public marker census of ``buf`` (also used on uncompressed spans)."""
    return _recognize(bytes(buf))


def verify_deflate(data, pos: int, hi: int, gzip: bool = False) -> VerifiedStream | None:
    """Fail-closed deflate verification at ``data[pos:hi]``.

    Tries zlib (``wbits=15``) or gzip (``wbits=31``) decompression from
    ``pos`` over a bounded window (:data:`MAX_WINDOW` in, :data:`MAX_OUTPUT`
    out). A stream verifies when it produces at least :data:`MIN_OUTPUT`
    bytes and reaches its own end (``eof`` — header, deflate blocks and
    check value all consumed); anything else (exception, short output,
    truncated or garbage-extended stream) returns ``None`` and the
    candidate stays a signature, never a claim.
    """
    window = bytes(data[pos : min(hi, pos + MAX_WINDOW)])
    if len(window) < 2:
        return None
    dec = zlib.decompressobj(wbits=31 if gzip else 15)
    out = bytearray()
    try:
        out += dec.decompress(window, MAX_OUTPUT)
        while len(out) < MAX_OUTPUT and not dec.eof and dec.unconsumed_tail:
            chunk = dec.decompress(dec.unconsumed_tail, MAX_OUTPUT - len(out))
            if not chunk:
                break
            out += chunk
        # eof only: the tail past the stream end landed in unused_data.
        consumed = len(window) - len(dec.unused_data)
    except zlib.error:
        return None
    if len(out) < MIN_OUTPUT or not dec.eof:
        return None
    return VerifiedStream(
        codec="gzip" if gzip else "zlib",
        position=pos,
        consumed=consumed,
        output=len(out),
        eof=bool(dec.eof),
        markers=_recognize(bytes(out[: MAX_OUTPUT])),
    )


def verify_bz2(data, pos: int, hi: int) -> VerifiedStream | None:
    """Fail-closed bzip2 verification at ``data[pos:hi]`` (same law)."""
    window = bytes(data[pos : min(hi, pos + MAX_WINDOW)])
    dec = bz2.BZ2Decompressor()
    try:
        out = dec.decompress(window, MAX_OUTPUT)
    except (OSError, ValueError):
        return None
    if len(out) < MIN_OUTPUT or not dec.eof:
        return None
    return VerifiedStream(
        codec="bz2",
        position=pos,
        consumed=len(window) - len(dec.unused_data),
        output=len(out),
        eof=bool(dec.eof),
        markers=_recognize(bytes(out[:MAX_OUTPUT])),
    )


def verify_xz(data, pos: int, hi: int) -> VerifiedStream | None:
    """Fail-closed xz/ lzma-container verification at ``data[pos:hi]``."""
    window = bytes(data[pos : min(hi, pos + MAX_WINDOW)])
    dec = lzma.LZMADecompressor(format=lzma.FORMAT_XZ)
    try:
        out = dec.decompress(window, MAX_OUTPUT)
    except lzma.LZMAError:
        return None
    if len(out) < MIN_OUTPUT or not dec.eof:
        return None
    return VerifiedStream(
        codec="xz",
        position=pos,
        consumed=len(window) - len(dec.unused_data),
        output=len(out),
        eof=bool(dec.eof),
        markers=_recognize(bytes(out[:MAX_OUTPUT])),
    )


def block_writer_tag(data, blk: int) -> str | None:
    """The writer tag at ``blk+112`` (``36 08 "FINJPL  "`` law).

    Reads the 8 bytes the bulk-stream note documents at block+112
    (``docs/evidence/2026-11-19-bulk-stream.md`` §2): a ``36 08`` pair
    followed by 6 printable bytes. Returns ``None`` when the pair is
    absent (a block whose preamble is shorter/longer than the law —
    itself a header-shape fact the census reports).
    """
    head = bytes(data[blk + 112 : blk + 120])
    if len(head) == 8 and head[:2] == b"\x36\x08" and all(
        0x20 <= b <= 0x7E for b in head[2:]
    ):
        return head[2:8].decode("ascii")
    return None


#: The writer-tag scan window and hit cap of :func:`block_writer_tag_scan`.
WRITER_TAG_WINDOW = 512
WRITER_TAG_HITS = 16


def block_writer_tag_scan(data, blk: int) -> list[tuple[int, str]]:
    """Every ``36 08`` + 6-printable tag in ``[blk, blk+512)``.

    The +112 position is one writer layout (the bulk anchors'); the
    census needs the drift feature, not one pinned offset: where the
    tag sits and what it says, per block family. Bounded to
    :data:`WRITER_TAG_HITS` hits; a tag text is kept only when all six
    bytes are printable (the ``36 08`` pair alone is a frequent payload
    coincidence).
    """
    end = blk + WRITER_TAG_WINDOW
    out: list[tuple[int, str]] = []
    i = data.find(b"\x36\x08", blk, end - 8)
    while i >= 0 and len(out) < WRITER_TAG_HITS:
        six = bytes(data[i + 2 : i + 8])
        if len(six) == 6 and all(0x20 <= b <= 0x7E for b in six):
            out.append((i - blk, six.decode("ascii")))
        i = data.find(b"\x36\x08", i + 1, end - 8)
    return out


@dataclass
class StreamCensus:
    """Per-file aggregation the probe writes (one CSV row per territory).

    ``tags``/``signatures`` are per-territory dicts (territory ->
    text/count maps); ``verified`` the fail-closed streams found in any
    territory; ``writer_tags`` the block+112 tag histogram (family ->
    tag -> count); ``store_spans``/``store_errors`` the locator outcome
    per probe family.
    """

    territories: dict[str, tuple[int, int]] = field(default_factory=dict)
    tags: dict[str, dict[str, int]] = field(default_factory=dict)
    signatures: dict[str, dict[str, int]] = field(default_factory=dict)
    verified: list[VerifiedStream] = field(default_factory=list)
    writer_tags: dict[str, dict[str, int]] = field(default_factory=dict)
    store_spans: dict[str, int] = field(default_factory=dict)
    store_errors: dict[str, int] = field(default_factory=dict)
    no_store_files: int = 0
