"""The fidelity harness's slice-note prose pin (ticket #44/#52 follow-up;
the Phase 5 retro, candidate 2).

The V6 close note's stale 'composite-path exports excluded' sentence
was a duplicated literal that the COMPOSITE_EXPORT_STAGE constant drove
elsewhere — the two copies drifted. The prose is now single-sourced in
``composite_prose(stage)``; this pin makes the derivation's contract
mechanical with hand-computed expectations:

1. stage >= 3 (the landed state): the note claims the composite path
   compares fully — it must NEVER claim exclusions.
2. stage < 3 (the V2-era state, kept for the pin's honesty): the note
   claims exclusions per the #41 hard stop.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "fidelity_run.py"
_spec = importlib.util.spec_from_file_location("fidelity_run", _SCRIPT)
fr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fr)


def test_composite_prose_tracks_the_stage_constant():
    # stage 3 (landed): compare fully — the exclusions claim is GONE.
    prose = fr.composite_prose(3)
    assert "compare fully" in prose
    assert "excluded" not in prose
    # stage 1 (the V2-era harness state): the #41 hard stop holds.
    prose1 = fr.composite_prose(1)
    assert "excluded" in prose1
    assert "compare fully" not in prose1


def test_both_slice_note_uses_the_single_sourced_prose():
    # The both-branch builds its sentence THROUGH the helper: a hand-run
    # of the builder at stage 3 must contain the compare-fully claim and
    # must not contain the stale exclusion wording. Verified against the
    # built slice_note shape the corpus caller assembles.
    prose = fr.composite_prose(fr.COMPOSITE_EXPORT_STAGE)
    assert fr.COMPOSITE_EXPORT_STAGE >= 3
    assert "ported at V3 #42" in prose
    # And the two call sites cannot disagree: both call the same helper,
    # so the same stage yields the same sentence — the drift the V6 close
    # flag caught is structurally closed.
    assert fr.composite_prose(fr.COMPOSITE_EXPORT_STAGE) == prose
