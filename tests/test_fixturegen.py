"""A2 acceptance tests (#12): seeded determinism, variant coverage,
and the repository binary guard (legal posture — manifests only)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from catpart.fitness.runner import _classify_file
from fixtures_gen import (
    CORRUPTED_VARIANTS,
    KIND_RECORDS,
    MAGIC,
    VALID_VARIANTS,
    build_fixture,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


# --- determinism (AC: same seed, same bytes) ---------------------------

def test_same_seed_same_bytes(tmp_path: Path) -> None:
    a = build_fixture("part", seed=42)
    b = build_fixture("part", seed=42)
    assert a == b


def test_different_seed_different_bytes() -> None:
    # The seed drives GUIDs/payload/padding; the skeleton stays genuine.
    assert build_fixture("part", seed=1) != build_fixture("part", seed=2)


def test_skeleton_laws_survive_seeding() -> None:
    for seed in (0, 1, 7):
        data = build_fixture("part", seed=seed)
        assert data[:8] == MAGIC
        assert data[16:24] == b"\xff" * 8
        assert data.endswith(build_fixture("part", seed=seed)[-36:])  # trailer stable
        assert data[-8:] == b"CB__END\x00"


def test_unknown_kind_or_variant_rejected() -> None:
    with pytest.raises(ValueError):
        build_fixture("widget")
    with pytest.raises(ValueError):
        build_fixture("part", variant="shredded")


# --- valid shapes parse clean (AC: structurally genuine) ---------------

@pytest.mark.parametrize("kind", sorted(KIND_RECORDS))
@pytest.mark.parametrize("variant", [None, "dual-region"])
def test_valid_variants_classify_clean(kind: str, variant: str | None, tmp_path: Path) -> None:
    path = tmp_path / f"sample{seed_name(kind, variant)}.CATPart"
    path.write_bytes(build_fixture(kind, seed=3, variant=variant))
    classification, error, output = _classify_file(path)
    assert classification == "clean", error
    assert output is not None
    assert output["kind"] == kind


def seed_name(kind: str, variant: str | None) -> str:
    return f"_{kind}" + (f"_{variant}" if variant else "")


# --- corrupted variants cover the failure classes (AC) -----------------

def test_bad_magic_is_missing_invariant(tmp_path: Path) -> None:
    path = tmp_path / "bad.CATPart"
    path.write_bytes(build_fixture("part", seed=5, variant="bad-magic"))
    classification, error, _ = _classify_file(path)
    assert classification == "missing-invariant"
    assert "magic-v5-cfv2" in (error or "")


def test_oversized_dword_is_missing_invariant(tmp_path: Path) -> None:
    path = tmp_path / "big.CATPart"
    path.write_bytes(build_fixture("part", seed=5, variant="oversized-dword"))
    classification, error, _ = _classify_file(path)
    assert classification == "missing-invariant"
    assert "header-dword-below-file-size" in (error or "")


def test_truncated_table_breaks_h1_chain(tmp_path: Path) -> None:
    # Cut mid-record with dword12 re-patched but the trailer's G stale:
    # the H1 chain breaks (tail-region-chain). A chain-consistent
    # truncation would be clean — partial tables are legitimate (B1).
    path = tmp_path / "cut.CATPart"
    path.write_bytes(build_fixture("part", seed=5, variant="truncated-table"))
    classification, error, output = _classify_file(path)
    assert classification == "missing-invariant"
    assert "tail-region-chain" in (error or "")
    assert output is not None  # parser still reports, never crashes


def test_short_file_is_crash(tmp_path: Path) -> None:
    # Below the 32-byte header the parser refuses: the crash class
    # (corpus junk behavior, #26).
    path = tmp_path / "short.CATPart"
    path.write_bytes(build_fixture("part", seed=5, variant="short-file"))
    classification, error, output = _classify_file(path)
    assert classification == "crash"
    assert output is None and error  # exception type preserved in the error


def test_missing_trailer_stays_clean(tmp_path: Path) -> None:
    # Legitimate corpus shape (262 no-trailer files): parser reports
    # trailer: null and the fixture is not penalized.
    path = tmp_path / "notrailer.CATPart"
    path.write_bytes(build_fixture("part", seed=5, variant="missing-trailer"))
    classification, error, output = _classify_file(path)
    assert classification == "clean", error
    assert output is not None and output["trailer"] is None


def test_junk_payload_stays_clean(tmp_path: Path) -> None:
    # The payload region is opaque to L1: random filler must not fail.
    path = tmp_path / "junk.CATPart"
    path.write_bytes(build_fixture("part", seed=5, variant="junk-payload"))
    classification, error, _ = _classify_file(path)
    assert classification == "clean", error


def test_document_name_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "named.CATPart"
    path.write_bytes(build_fixture("part", seed=9, document_name="sample.CATPart"))
    classification, error, output = _classify_file(path)
    assert classification == "clean", error
    assert output is not None and output["document_name"] == "sample.CATPart"


def test_all_variant_names_covered() -> None:
    # Guard the taxonomy: every advertised variant is buildable.
    for variant in CORRUPTED_VARIANTS + VALID_VARIANTS:
        assert isinstance(build_fixture("part", seed=0, variant=variant), bytes)


# --- repository binary guard (AC: legal posture, manifests only) -------

def _tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return [REPO_ROOT / p for p in out.stdout.decode().split("\0") if p]


def test_no_real_catia_binaries_staged() -> None:
    """No tracked file may be (or start with) a real CATIA V5 container.

    The corpus lives outside the repo (gitignored); evidence notes and
    manifests carry digests instead of bytes. Catches both wrong-path
    staging (a .CATPart file) and wrong-content staging (a renamed
    binary whose first 8 bytes are the V5_CFV2 magic).
    """
    suspicious_suffixes = {
        ".catpart",
        ".catproduct",
        ".catshape",
        ".catdrawing",
        ".cgr",
        ".model",
    }
    for path in _tracked_files():
        assert path.suffix.lower() not in suspicious_suffixes, f"staged binary: {path}"
        if path.is_file() and path.stat().st_size >= 8:
            with open(path, "rb") as fh:
                assert fh.read(8) != MAGIC, f"staged CATIA bytes: {path}"


def _pytest_entry_point_present() -> None:
    # The generator is test-only by design; this assert documents it.
    assert "tests" in str(Path(__file__)), "fixtures_gen must live with the tests"


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__]))
