"""Pin: the committed wasm-test fixture data matches the generator.

Phase 5 spec §7 step 6 (V4, ticket #43): CI runs the shipped WASM
artifact headlessly on a small fixture subset; the subset's bytes are
the committed generated source ``port/tests/fixtures/mod.rs``
(``scripts/gen_wasm_fixture_data.py`` — committed binaries carrying the
``V5_CFV2`` magic are impossible, the A2 binary guard). This pin
re-runs the generator and requires the committed file byte-identical:
the generator is a pure function of ``tests/fixtures_gen.py``, so any
fixture-law change must regenerate the data explicitly — the wasm
subset can never silently drift from the generator the fixture-mode
Fidelity harness drives.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATOR = REPO_ROOT / "scripts" / "gen_wasm_fixture_data.py"
COMMITTED = REPO_ROOT / "port" / "tests" / "fixtures" / "mod.rs"


def test_committed_wasm_fixture_data_is_fresh(tmp_path: Path) -> None:
    assert COMMITTED.is_file(), "the generated data file must be committed"
    out = tmp_path / "mod.rs"
    proc = subprocess.run(
        [sys.executable, str(GENERATOR), "--out", str(out)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert proc.returncode == 0, f"the generator failed: {proc.stderr}"
    assert out.read_bytes() == COMMITTED.read_bytes(), (
        "port/tests/fixtures/mod.rs is stale: run "
        "`python scripts/gen_wasm_fixture_data.py` and commit the result "
        "(the generator is a pure function of tests/fixtures_gen.py)"
    )


def test_subset_covers_canonical_and_the_classified_classes() -> None:
    """The §7 step 6 subset shape: canonical store + corrupted variants.

    Pinned by reading the generator's SUBSET (the same table the
    generated file's doc comments name) so a trimmed subset fails here,
    not only at the next wasm-pack run.
    """
    spec = importlib.util.spec_from_file_location("gen_wasm_fixture_data", GENERATOR)
    assert spec is not None and spec.loader is not None
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    variants = {variant for _, variant, _ in gen.SUBSET}
    assert None in variants or "geometry" in variants, (
        "the subset must include the canonical store"
    )
    for expected in (
        "geometry-bad-nested-magic",  # missing-geometry-store
        "geometry-truncated-pool",  # malformed-pool-group
        "geometry-nan-coords",  # malformed-pool-vertex
        "geometry-out-of-range-refs",  # undecoded-variant
        "short-file",  # the inspect crash-class refusal
    ):
        assert expected in variants, f"the subset must include {expected!r}"
    assert COMMITTED.read_text(encoding="utf-8").count("pub const") == len(gen.SUBSET)
