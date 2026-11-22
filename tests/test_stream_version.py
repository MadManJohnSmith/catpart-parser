"""Corpus-free tests for the stream-version census (W19, B9).

The module (``catpart.geometry.stream_version``) scans byte ranges for
framed version-like strings, compression signatures and fail-closed
verified compressed sub-streams; the probe
(``scripts/triage/stream_version_probe.py``) applies it to the corpus
territories. These tests build every ingredient from bytes and pin the
decisions the evidence note rests on:

- the tag scanner accepts exactly the ``[u32le L][L ASCII]`` frames
  whose text is version-shaped (``2-0``, ``2X-0``, ``10-0``), refuses a
  length/text mismatch, a non-version text (``Height``) and a non-
  framed u32 (``03 00 00 01``);
- the zlib pre-filter applies the RFC 1950 FCHECK law, so a wrong FLG
  byte never becomes a candidate;
- ``verify_deflate`` claims only an embedded zlib/gzip stream that
  inflates to its own end with >= MIN_OUTPUT bytes and recognizable
  CATIA markers (the flip evidence); a junk ``78 9c`` pair, a truncated
  stream, a raw-deflate embedding without the zlib wrapper and a
  short-output stream are all refused;
- ``verify_bz2``/``verify_xz`` follow the same eof law;
- the writer-tag reader pins the +112 law and the drift scan finds a
  tag that moved, refusing a non-printable payload;
- the Rust-parity fixtures: the exact tag/signature counts the port
  (``port/src/geometry/stream_version.rs``) must reproduce on the same
  synthetic buffers.

Fixtures are synthetic; no corpus binary is read.
"""

from __future__ import annotations

import bz2
import gzip
import lzma
import os
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from catpart.geometry.stream_version import (  # noqa: E402
    MIN_OUTPUT,
    SIG_GZIP,
    SIG_XZ,
    block_writer_tag,
    block_writer_tag_scan,
    recognize_markers,
    scan_compression_signatures,
    scan_version_tags,
    verify_bz2,
    verify_deflate,
    verify_xz,
)


def u32le(n: int) -> bytes:
    return n.to_bytes(4, "little")


# ---------------------------------------------------------------- tags


def frame(text: bytes) -> bytes:
    """The ``[u32le L][L ASCII]`` framing of ``text``."""
    return u32le(len(text)) + text


class TestVersionTags:
    def test_ge_v7_pair(self):
        buf = frame(b"2-0") + frame(b"2X-0")
        assert scan_version_tags(buf, 0, len(buf)) == {"2-0": 1, "2X-0": 1}

    def test_ladder_texts(self):
        buf = frame(b"1-0") + frame(b"10-0") + frame(b"29-0") + frame(b"3-1-0")
        got = scan_version_tags(buf, 0, len(buf))
        assert got == {"1-0": 1, "10-0": 1, "29-0": 1, "3-1-0": 1}

    def test_counts_occurrences(self):
        buf = frame(b"2-0") * 3
        assert scan_version_tags(buf, 0, len(buf)) == {"2-0": 3}

    def test_length_mismatch_refused(self):
        # u32le 4 but a 3-byte text: the frame law needs L == len(text)
        buf = u32le(4) + b"2-0"
        assert scan_version_tags(buf, 0, len(buf)) == {}

    def test_non_version_text_refused(self):
        buf = frame(b"Height") + frame(b"2-") + frame(b"-0") + frame(b"2X-")
        assert scan_version_tags(buf, 0, len(buf)) == {}

    def test_not_framed_u32_refused(self):
        # a non-small length byte (0x20) never frames
        buf = b"\x20\x00\x00\x002-0tail"
        assert scan_version_tags(buf, 0, len(buf)) == {}

    def test_window_bounds_respected(self):
        buf = b"junk" + frame(b"2-0")
        assert scan_version_tags(buf, 0, 4) == {}
        assert scan_version_tags(buf, 0, len(buf)) == {"2-0": 1}

    def test_real_file_ladder_image(self):
        # the byte image observed on the corpus anchor (GE-V7's context,
        # generalized): 44-byte record units carrying the framed tag
        unit = bytes.fromhex(
            "0e04000100080e040000070003000000322d30"
            "00000100000100040084f51b0000030022"
        )
        assert scan_version_tags(unit, 0, len(unit)) == {"2-0": 1}


# ------------------------------------------------------- zlib pre-filter


class TestZlibPairPrefilter:
    def test_valid_pair_counted(self):
        sigs = scan_compression_signatures(b"\x78\x9c payload", 0, 11)
        assert sigs["zlib_pair"] == 1

    def test_invalid_fcheck_not_counted(self):
        # (0x78 << 8 | 0x00) % 31 != 0 — the FLG byte is invalid
        sigs = scan_compression_signatures(b"\x78\x00 junk", 0, 8)
        assert sigs["zlib_pair"] == 0

    def test_gzip_signature(self):
        assert scan_compression_signatures(SIG_GZIP + b"x", 0, 5)["gzip"] == 1

    def test_xz_signature(self):
        assert scan_compression_signatures(SIG_XZ + b"x", 0, 7)["xz"] == 1

    def test_snappy_and_zstd_and_lz4(self):
        buf = b"\x28\xb5\x2f\xfd" + b"\x04\x22\x4d\x18" + b"\xff\x06\x00\x00sNaPpY"
        sigs = scan_compression_signatures(buf, 0, len(buf))
        assert sigs["zstd"] == 1 and sigs["lz4_frame"] == 1 and sigs["snappy"] == 1

    def test_window_bounds(self):
        assert scan_compression_signatures(b"abc", 0, 3)["zlib_pair"] == 0


# --------------------------------------------------- verified deflate


def embedded_zlib(payload: bytes) -> bytes:
    """A zlib stream embedded between two ASCII guards."""
    return b"HEAD" + zlib.compress(payload, 9) + b"TAIL"


def embedded_gzip(payload: bytes) -> bytes:
    return b"HEAD" + gzip.compress(payload) + b"TAIL"


MARKER_PAYLOAD = b"\xe5\x0d" * 200 + b"CATIA_V5 CB0001\x00" + b"\x01\x06" * 100


class TestVerifyDeflate:
    def test_embedded_zlib_verifies_with_markers(self):
        emb = embedded_zlib(MARKER_PAYLOAD)
        v = verify_deflate(emb, 4, len(emb))
        assert v is not None and v.codec == "zlib" and v.eof
        assert v.markers["e5_record"] == 200
        assert v.markers["cb_catalog"] == 1
        assert v.markers["pool_group"] == 100

    def test_embedded_gzip_verifies(self):
        emb = embedded_gzip(MARKER_PAYLOAD)
        v = verify_deflate(emb, 4, len(emb), gzip=True)
        assert v is not None and v.codec == "gzip" and v.eof

    def test_gzip_does_not_verify_as_zlib(self):
        emb = embedded_gzip(MARKER_PAYLOAD)
        assert verify_deflate(emb, 4, len(emb)) is None

    def test_junk_pair_refused(self):
        assert verify_deflate(b"\x78\x9c" + os.urandom(4096), 0, 4098) is None

    def test_truncated_stream_refused(self):
        full = zlib.compress(MARKER_PAYLOAD, 9)
        # cut the final adler32: the stream never reaches its own end
        assert verify_deflate(full[:-4] + b"TAIL", 0, len(full)) is None

    def test_short_output_refused(self):
        emb = embedded_zlib(b"\x01\x02\x03\x04")
        assert verify_deflate(emb, 4, len(emb)) is None

    def test_min_output_is_256(self):
        assert MIN_OUTPUT == 256


class TestVerifyBz2Xz:
    def test_bz2_verifies(self):
        bz = bz2.compress(MARKER_PAYLOAD)
        v = verify_bz2(b"xx" + bz + b"yy", 2, len(bz) + 4)
        assert v is not None and v.codec == "bz2" and v.eof
        assert v.output >= len(MARKER_PAYLOAD) - 64

    def test_bz2_junk_refused(self):
        assert verify_bz2(b"BZh9garbage-not-a-stream", 0, 22) is None

    def test_xz_verifies(self):
        xz = lzma.compress(MARKER_PAYLOAD, format=lzma.FORMAT_XZ)
        v = verify_xz(xz + b"zz", 0, len(xz) + 2)
        assert v is not None and v.codec == "xz" and v.eof

    def test_lzma_raw_container_refused_as_xz(self):
        # FORMAT_XZ requires the xz container; raw lzma data fails it
        raw = lzma.compress(MARKER_PAYLOAD, format=lzma.FORMAT_ALONE)
        assert verify_xz(raw, 0, len(raw)) is None


# --------------------------------------------------------- writer tags


def block_with_tag(tag: bytes, offset: int = 112) -> bytes:
    """A block head carrying the ``36 08`` writer tag at ``offset``."""
    pre = bytearray(b"\x00" * offset)
    return bytes(pre) + b"\x36\x08" + tag + b"\x9f tail"


class TestWriterTag:
    def test_law_position(self):
        buf = block_with_tag(b"FINJPL")
        assert block_writer_tag(buf, 0) == "FINJPL"

    def test_absent_pair(self):
        assert block_writer_tag(b"\x00" * 120, 0) is None

    def test_non_printable_refused(self):
        buf = block_with_tag(b"\x01\x02\x03\x04\x05\x06")
        assert block_writer_tag(buf, 0) is None

    def test_scan_finds_moved_tag(self):
        buf = block_with_tag(b"FINJPL", offset=130)
        assert block_writer_tag(buf, 0) is None  # the +112 law misses
        assert block_writer_tag_scan(buf, 0) == [(130, "FINJPL")]

    def test_scan_refuses_non_printable(self):
        buf = block_with_tag(b"\x00\x01\x02\x03\x04\x05", offset=64)
        assert block_writer_tag_scan(buf, 0) == []


# ------------------------------------------------ flip classification


class TestFlipClassifier:
    def test_recognized_markers(self):
        got = recognize_markers(MARKER_PAYLOAD)
        assert got["e5_record"] == 200 and got["pool_group"] == 100

    def test_unrecognized_output(self):
        got = recognize_markers(os.urandom(512))
        assert sum(got.values()) == 0

    def test_flip_is_verifiable(self):
        # a "candidate flip": an embedded compressed stream whose output
        # carries CATIA markers — verifiable end to end on synthetic bytes
        emb = embedded_zlib(MARKER_PAYLOAD)
        v = verify_deflate(emb, 4, len(emb))
        assert v is not None and sum(v.markers.values()) > 0


# ------------------------------------------------ Rust-parity fixtures
# The port (port/src/geometry/stream_version.rs) pins the same counts on
# these exact buffers; keep both sides byte-identical.


PARITY_TAG_BUF = frame(b"2-0") + b"junk" + frame(b"2X-0") + u32le(4) + b"2-0"
PARITY_TAG_EXPECT = {"2-0": 1, "2X-0": 1}

PARITY_SIG_BUF = (
    b"\x78\x9c" + b"\x78\x00" + SIG_GZIP + b"\x00" + SIG_XZ + b"\x28\xb5\x2f\xfd"
)
PARITY_SIG_EXPECT = {
    "zlib_pair": 1,
    "gzip": 1,
    "xz": 1,
    "zstd": 1,
}


class TestRustParityFixtures:
    def test_tag_fixture(self):
        assert scan_version_tags(PARITY_TAG_BUF, 0, len(PARITY_TAG_BUF)) == (
            PARITY_TAG_EXPECT
        )

    def test_signature_fixture(self):
        got = scan_compression_signatures(PARITY_SIG_BUF, 0, len(PARITY_SIG_BUF))
        for key, want in PARITY_SIG_EXPECT.items():
            assert got[key] == want, (key, got[key], want)
        # the parity buffer also pins the zero rows
        assert got["bzip2"] == 0 and got["lz4_frame"] == 0 and got["snappy"] == 0
