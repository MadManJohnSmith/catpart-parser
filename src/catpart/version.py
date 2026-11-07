"""Per-file version detection via the embedded CNEXTINFOS release marker.

Evidence: docs/evidence/2026-11-07-container-triage.md ("Per-file version
marker"). The marker is plaintext near the container-name table
(~0xb00-0xde0 in the Phase 1 deep sample), of the documented form::

    NOTHING-CNEXTINFOS-UpdateVersion-StreamBlock-SafeEarlyBlock-StrongEarly&V5RxxSPxHFx built ...

The release token (``V5RxxSPxxHFxx``, e.g. ``V5R19SP0HF0``) is the
detected version. The evidence note records naive ``V5 Rxx`` patterns as
a negative result: only this CNEXTINFOS-anchored form is a marker, so a
release token counts only when ``CNEXTINFOS`` occurs within the 128
bytes preceding it (the documented line carries it 64 bytes back).
Corpus check (1818 magic_ok files, Phase 1 evidence): the anchored rule
returns the same file, window and token as the unanchored scan that
produced the evidence counts, with 0 differences.

Windowing mirrors the evidence scan exactly: search the first 8 KB
(1402/1818 files, 77.1%); files with no match there fall back to the
first 64 KB (+78, total 1480/1818 = 81.4%); everything else lands in the
``unknown`` bucket (338 files, map decision on ticket #4). A token
straddling the 8 KB boundary is missed by the truncated primary window
and recovered by the fallback, matching the scan's counting rule.
"""

from __future__ import annotations

import mmap
import re
from typing import Literal

UNKNOWN = "unknown"

PRIMARY_WINDOW = 8192
FALLBACK_WINDOW = 65536

#: Prefix bytes of the documented marker line (CNEXTINFOS start to the
#: release token start): "CNEXTINFOS-UpdateVersion-StreamBlock-"
#: "SafeEarlyBlock-StrongEarly&" is 64 bytes; 128 leaves headroom for
#: line-form variation while still anchoring the token to the line.
_ANCHOR = b"CNEXTINFOS"
_ANCHOR_SPAN = 128

_VERSION_RE = re.compile(rb"V5R(\d{2})SP(\d+)HF(\d+)")

Window = Literal["8k", "64k", "unknown"]


def detect_version(data: mmap.mmap | bytes) -> str:
    """Return the release marker in ``data``, or :data:`UNKNOWN`.

    ``data`` is any bytes-like buffer supporting slicing (``bytes`` or a
    read-only :class:`mmap.mmap`): the primary 8 KB window first, then
    the 64 KB fallback window, else :data:`UNKNOWN`. Within a window the
    first anchored token wins (the marker line repeats across saves; the
    evidence distribution is the leftmost token, header_scan.py rule).
    """
    return detect_version_with_window(data)[0]


def detect_version_with_window(data: mmap.mmap | bytes) -> tuple[str, Window]:
    """:func:`detect_version` plus the window that produced it.

    Returns ``(version, window)`` with ``window`` in ``{"8k", "64k",
    "unknown"}`` — the bucket split behind the evidence counts (1402 in
    8 KB, +78 in the 64 KB fallback, 338 unknown). The manifest-backfill
    script reports this split.
    """
    for name, window in (("8k", PRIMARY_WINDOW), ("64k", FALLBACK_WINDOW)):
        view = data[:window]
        for match in _VERSION_RE.finditer(view):
            head_start = max(0, match.start() - _ANCHOR_SPAN)
            if _ANCHOR in view[head_start : match.start()]:
                return match.group(0).decode("ascii"), name
    return UNKNOWN, "unknown"
