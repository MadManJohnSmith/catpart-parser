"""Version-marker detection (ticket #13).

Tests cover the three acceptance buckets on synthetic fixtures: marker
within the first 8 KB, marker only beyond 8 KB (64 KB fallback), and no
marker (the ``unknown`` bucket, map decision on ticket #4). Two CLI-level
assertions in test_cli_inspect.py pin the same behavior end to end
through ``catpart-inspect`` JSON.
"""

from __future__ import annotations

import mmap
from pathlib import Path

import pytest

from catpart.version import detect_version, detect_version_with_window


def test_marker_within_8k_window(build_catpart) -> None:
    # The fixture's CNEXTINFOS line sits right after the container-name
    # table (~0x7xx), well inside the 8 KB primary window.
    assert detect_version(build_catpart()) == "V5R21SP0HF0"


def test_window_bucket_reported(build_catpart) -> None:
    # The evidence counts are per window: 1402 in the 8 KB window, +78
    # recovered by the 64 KB fallback, 338 unknown. The script that
    # backfills the manifest reports this split, so the module exposes it.
    assert detect_version_with_window(build_catpart()) == ("V5R21SP0HF0", "8k")
    assert detect_version_with_window(build_catpart(pad_before_table=9000)) == (
        "V5R21SP0HF0",
        "64k",
    )
    assert detect_version_with_window(build_catpart(with_marker=False)) == (
        "unknown",
        "unknown",
    )


def test_marker_only_beyond_8k_falls_back(build_catpart) -> None:
    # +78 corpus files carry the marker past 8 KB; the 64 KB fallback
    # window recovers them. pad_before_table pushes the marker line
    # past byte 8192 while staying under 64 KB.
    data = build_catpart(pad_before_table=9000)
    assert data.find(b"V5R21SP0HF0") > 8192
    assert detect_version(data) == "V5R21SP0HF0"


def test_marker_straddling_8k_boundary_is_recovered() -> None:
    # A token starting before byte 8192 but truncated by the primary
    # window is missed there and recovered by the fallback — the same
    # counting rule as the evidence scan (one such corpus file).
    line = (
        b"NOTHING-CNEXTINFOS-UpdateVersion-StreamBlock-SafeEarlyBlock-"
        b"StrongEarly&V5R24SP1HF0 built"
    )
    # CNEXTINFOS sits 64 bytes before the token; put CNEXTINFOS at 8122
    # so the token starts at 8186 and the primary window cuts it
    # mid-token. The line opens with "NOTHING-" (8 bytes).
    data = b"V5_CFV2\x00" + b"\x00" * (8114 - 8) + line
    assert data.find(b"CNEXTINFOS") == 8122
    token_start = data.find(b"V5R24SP1HF0")
    assert 8186 <= token_start < 8192 < token_start + len(b"V5R24SP1HF0")
    assert detect_version(data) == "V5R24SP1HF0"


def test_bare_token_without_cnextinfos_is_unknown(build_catpart) -> None:
    # Only the CNEXTINFOS-anchored form is a marker (evidence note:
    # naive V5Rxx patterns are a negative result). A release-token-like
    # string elsewhere in the payload must not be detected.
    data = build_catpart(with_marker=False, payload=b"\x00V5R19SP0HF0\x00")
    assert detect_version(data) == "unknown"


def test_first_anchored_marker_wins(build_catpart) -> None:
    # The marker line repeats across saves; the detected version is the
    # first anchored token in the window (the evidence distribution is
    # the leftmost token, header_scan.py rule).
    payload = (
        b"\x00NOTHING-CNEXTINFOS-UpdateVersion-StreamBlock-SafeEarlyBlock-"
        b"StrongEarly&V5R19SP0HF0 built\x00\x00NOTHING-CNEXTINFOS-"
        b"UpdateVersion-StreamBlock-SafeEarlyBlock-StrongEarly&"
        b"V5R24SP1HF0 built\x00"
    )
    assert detect_version(build_catpart(with_marker=False, payload=payload)) == "V5R19SP0HF0"


def test_detect_version_accepts_mmap(build_catpart, tmp_path: Path) -> None:
    # The CLI hands the function a read-only mmap of the whole file.
    path = tmp_path / "sample.CATPart"
    path.write_bytes(build_catpart())
    with open(path, "rb") as fh, mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as data:
        assert detect_version(data) == "V5R21SP0HF0"
