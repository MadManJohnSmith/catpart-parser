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

V2 (ticket #41): the pin grows the export slice — the harness's fixture
matrix runs BOTH slices by default (``--slice both``): the L1 inspect
rows as at V1, plus the L2 export comparison (summary parsed-document
equality + PLY byte-identical + error_class equality, §3.2) over the
geometry-bearing A2 variants (the canonical store, the recovery
variants, the corrupted classes) and the store-less refusal shapes.
The composite-law and unrouted-elementspace variants stay in the L1
matrix (inspect parity holds — inspect does not decode geometry) and
are excluded from the export matrix: their composite decode is V3
(#42), the ticket's hard stop.

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
    the ``catpart-inspect``/``catpart-export`` console scripts next to
    the running interpreter and the release ``fidelity-cli`` the
    harness builds. The gate is green exactly when every compared row
    is a ``match`` — any output mismatch, error-class mismatch or
    harness-level failure fails the pin (§3.2: a harness-level failure
    never counts as a match).
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

    l1_rows = [row for row in rows if row["row_id"].endswith("|l1")]
    l2_rows = [row for row in rows if row["row_id"].endswith("|l2")]
    assert l1_rows and l2_rows, "the fixture run must cover both slices (the V2 gate)"

    gen = fidelity.load_fixtures_gen()
    # The corrupted variants were exercised (the acceptance's "incl.
    # corrupted variants"): every A2 variant appears in the compared
    # L1 population at least once.
    compared = {row["row_id"].rsplit("|", 1)[0].split("|")[0] for row in l1_rows}
    for variant in (*gen.VALID_VARIANTS, *gen.CORRUPTED_VARIANTS):
        name = "canonical" if variant is None else variant
        assert name in compared, f"A2 variant {variant!r} missing from the fixture-mode population"
    # The L2 export matrix covers every geometry-bearing variant (the
    # canonical store, the recovery variants, the corrupted classes)
    # and none of the composite-family variants (V3 scope, #42).
    export_variants = {row["row_id"].rsplit("|", 1)[0].split("|")[0] for row in l2_rows}
    composite_family = set(gen.COMPOSITE_VARIANTS)
    for variant in set(gen.GEOMETRY_VARIANTS):
        assert variant in export_variants, f"geometry variant {variant!r} missing from the export matrix"
    for variant in composite_family:
        assert variant not in export_variants, (
            f"composite-family variant {variant!r} must not be in the V2 export matrix (V3, #42)"
        )
    # The fail-closed arms were exercised on both slices: the L1
    # refusal classes are the crash class; the L2 refusal classes are
    # the geometry vocabulary (never invented, never finer).
    l1_refusals = [row for row in l1_rows if row["python_exit"] == "1"]
    assert l1_refusals, "the fixture run never exercised the L1 fail-closed path"
    assert all(
        row["python_error_class"] == "crash" and row["port_error_class"] == "crash"
        for row in l1_refusals
    ), "the port's L1 refusal classes diverge from the Python side's crash class"
    l2_refusals = [row for row in l2_rows if row["python_exit"] == "1"]
    assert l2_refusals, "the fixture run never exercised the L2 fail-closed path"
    known_classes = {
        "missing-geometry-store",
        "undecoded-variant",
        "malformed-store-header",
        "malformed-pool-group",
        "malformed-pool-vertex",
        "unreadable-file",
        "io-error",
    }
    for row in l2_refusals:
        assert row["python_error_class"] == row["port_error_class"], (
            f"the L2 refusal classes diverge on {row['row_id']}: "
            f"{row['python_error_class']} vs {row['port_error_class']}"
        )
        assert row["python_error_class"] in known_classes, (
            f"an invented or finer error class on {row['row_id']}: {row['python_error_class']}"
        )
    # The export slice's PLY equality flag is set exactly on the
    # exporting rows (byte-identical, §3.2) and blank on refusals.
    assert all(row["ply_equal"] == "true" for row in l2_rows if row["python_exit"] == "0"), (
        "an exporting fixture row without a PLY byte-identity pass"
    )
    assert all(row["ply_equal"] == "" for row in l2_rows if row["python_exit"] == "1"), (
        "a refused fixture row with a PLY comparison it cannot have"
    )
