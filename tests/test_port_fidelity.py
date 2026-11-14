"""Fixture-mode Fidelity pin — the gate slot for the Port (Phase 5).

Spec: docs/specs/phase5-viewer-spec.md §4 (the Fidelity harness,
fixture mode) and §7 step 5 (the harness as a pytest pin: native Port
vs Python reference over the A2 synthetic fixtures, wired into the
gate as this module).

V0 (ticket #51) lands this module as a skip-pending stub so the gate
slot exists and the count change (7 -> 8 skipped) is deliberate and
documented in the ticket. ``scripts/fidelity_run.py`` (the dual-mode
harness) and the ``fidelity-cli`` native binary arrive with V1
(ticket #40); at that point this test starts comparing real
implementations over the A2 fixtures — inspect document equality on
the canonical and corrupted variants (spec §3.2's diff definitions).
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(
    reason=(
        "V0 stub (ticket #51): the fixture-mode Fidelity harness lands "
        "with V1 (spec §4) — scripts/fidelity_run.py + the fidelity-cli "
        "binary; until then the Port crate has no decode body to compare."
    )
)
def test_port_fidelity_fixture_mode() -> None:
    """V1 fills this in: generate the A2 fixtures in-process via
    ``tests/fixtures_gen.py``, run both implementations over them, and
    diff (spec §4 fixture mode; §3.2 parsed-document equality incl.
    the corrupted variants' error classes)."""
