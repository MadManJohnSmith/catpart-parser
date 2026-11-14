"""Fixture-mode Fidelity pin — the gate slot for the Port (Phase 5).

Spec: docs/specs/phase5-viewer-spec.md §4 (the Fidelity harness, fixture
mode) and §7 step 5 (the harness as a pytest pin: native Port vs Python
reference over the A2 synthetic fixtures, wired into the gate as this
module).

V1 (ticket #40): the pin is live. The A2 fixture population is
generated in-process via ``tests/fixtures_gen.py``, both
implementations run as subprocesses (the shipped seams — no in-process
imports), and the diff is the harness's own §3.2 comparison:
inspect-document parsed equality on every fixture that parses, error
class equality on the ones that refuse (``short-file`` → the ``crash``
class on both sides). The corrupted variants are all in the compared
population and each one is pinned to have been exercised.

The harness lives in ``scripts/fidelity_run.py`` — imported by file
path (the ``publish_fitness.py`` convention: a standalone stdlib
script, not package code) so fixture mode and corpus mode share one
diff implementation.
"""

from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "fidelity_run.py"


def load_harness():
    spec = importlib.util.spec_from_file_location("fidelity_run", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fidelity = load_harness()


def test_port_fidelity_fixture_mode(tmp_path: Path) -> None:
    """Native Port ≡ Python reference over the A2 fixtures (spec §4).

    Runs the harness's fixture mode against this worktree's own seams:
    the ``catpart-inspect`` console script next to the running
    interpreter and the release ``fidelity-cli`` the harness builds.
    The gate is green exactly when every compared row is a ``match`` —
    any output mismatch, error-class mismatch or harness-level failure
    fails the pin (§3.2: a harness-level failure never counts as a
    match).
    """
    csv_path = tmp_path / "fidelity-fixture-claims.csv"
    note_path = tmp_path / "fixture-note.md"
    code = fidelity.main([
        "--fixtures",
        "--csv",
        str(csv_path),
        "--note",
        str(note_path),
    ])
    assert code == 0, "the fixture-mode Fidelity run reported non-match rows (see stderr)"
    with csv_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows, "the fixture mode produced no rows"
    outcomes = {row["outcome"] for row in rows}
    assert outcomes == {"match"}, f"non-match outcomes in the fixture run: {outcomes}"
    # The corrupted variants were exercised (the acceptance's "incl.
    # corrupted variants"): every A2 variant appears in the compared
    # population at least once.
    gen = fidelity.load_fixtures_gen()
    compared = {row["row_id"].split("|")[0] for row in rows}
    for variant in (*gen.VALID_VARIANTS, *gen.CORRUPTED_VARIANTS):
        name = "canonical" if variant is None else variant
        assert name in compared, f"A2 variant {variant!r} missing from the fixture-mode population"
    # The fail-closed arm was exercised too: the short-file refusal
    # compared as the same class on both sides (crash == crash).
    refusals = [row for row in rows if row["python_exit"] == "1"]
    assert refusals, "the fixture run never exercised the fail-closed refusal path"
    assert all(
        row["python_error_class"] == "crash" and row["port_error_class"] == "crash"
        for row in refusals
    ), "the port's refusal classes diverge from the Python side's crash class"
