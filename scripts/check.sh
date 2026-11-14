#!/bin/bash
# Local merge gate (ticket #38): mirrors .github/workflows/ci.yml —
# pinned ruff + pytest over the corpus-free suite — before history
# reaches main. CI remains the authority; this script is the local copy
# of the same checks (see dispatch-recipes.md hard rules).
set -e -o pipefail
cd "$(git rev-parse --show-toplevel)"
if [ -x .venv/bin/python ]; then
  PY=.venv/bin/python
  RUFF=.venv/bin/ruff
else
  PY=python3
  RUFF=ruff
  # A worktree without .venv must not pass silently against the system
  # interpreter (the stage-7 pipe-masking incident; 2026-11-13 retro
  # candidate 8 — the gate exercised a shadow environment and the
  # mismatch surfaced only as a skip-count difference).
  "$PY" -c "import catpart" 2>/dev/null || {
    echo "check: FAIL — no .venv here and the system python3 cannot import catpart." >&2
    echo "        Set up first: python -m venv .venv && .venv/bin/pip install -e '.[test]'" >&2
    exit 1
  }
fi
echo "check: PY=$PY RUFF=$RUFF"
echo "check: ruff check ."
"$RUFF" check .
echo "check: pytest -q"
"$PY" -m pytest -q
