#!/bin/sh
# Local merge gate (ticket #38): mirrors .github/workflows/ci.yml —
# pinned ruff + pytest over the corpus-free suite — before history
# reaches main. CI remains the authority; this script is the local copy
# of the same checks (see dispatch-recipes.md hard rules).
set -e
cd "$(git rev-parse --show-toplevel)"
if [ -x .venv/bin/python ]; then
  PY=.venv/bin/python
  RUFF=.venv/bin/ruff
else
  PY=python3
  RUFF=ruff
fi
echo "check: ruff check ."
"$RUFF" check .
echo "check: pytest -q"
"$PY" -m pytest -q
