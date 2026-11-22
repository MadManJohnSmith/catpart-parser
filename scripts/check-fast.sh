#!/bin/bash
# The fast gate (marathon W7, speed oracle): lint + the critical-subset
# unit tests + engine parity over the A2 fixture variants, in <15 s on
# a warm checkout. A dev-loop tool for the marathon runners — NOT the
# pre-push gate.
#
# What it covers (and what it does not):
#
# COVERED:
#   - ruff check . (the same pinned lint the full gate runs);
#   - the fitness seams' unit tests (runner, L2, history, L3) and the
#     CLI-inspect console contract;
#   - ENGINE PARITY over the A2 fixture variants: the native engines
#     (rust/fast) vs the python reference through the REAL release
#     fidelity-cli binary (tests/test_fitness_speed.py) — classification,
#     detected_version, kind and the full L2 record, zero divergences;
#   - the claims-CSV quoting checker.
#
# NOT COVERED (check.sh remains the only pre-push authority):
#   - the FULL dual-slice fixture-mode fidelity matrix
#     (tests/test_port_fidelity.py, ~60 s: the harness drives both
#     shipped seams over every fixture twice and diffs the PLY bytes);
#   - the cargo steps (build native + wasm32, fmt, clippy -D warnings,
#     cargo test), wasm-pack --node, the pkg sync, node --test, the
#     Playwright acceptance — every port-side check;
#   - the rest of the Python suite (containers, geometry, brep,
#     composite, export, bulk, ...).
#
# The engine-parity pins need the release fidelity-cli binary. On a cold
# checkout the FIRST run pays one `cargo build --release --locked`
# (minutes at CARGO_BUILD_JOBS=2); afterwards the build is a no-op and
# the gate stays <15 s. No binary + no cargo => FAIL with the build
# command, never a silent skip (the dispatch-recipes hard rule).
set -e -o pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [ -x .venv/bin/python ]; then
  PY=.venv/bin/python
  RUFF=.venv/bin/ruff
else
  PY=python3
  RUFF=ruff
  "$PY" -c "import catpart" 2>/dev/null || {
    echo "check-fast: FAIL — no .venv here and the system python3 cannot import catpart." >&2
    echo "            Set up first: python -m venv .venv && .venv/bin/pip install -e '.[test,lint]'" >&2
    exit 1
  }
fi
echo "check-fast: PY=$PY RUFF=$RUFF"
echo "check-fast: ruff check ."
"$RUFF" check .
echo "check-fast: pytest -q (critical subset, 1 process)"
"$PY" -m pytest -q -p no:cacheprovider \
  tests/test_fitness_speed.py \
  tests/test_fitness_runner.py \
  tests/test_fitness_l2.py \
  tests/test_cli_inspect.py \
  tests/test_claims_csv_quoting.py
echo "check-fast: claims CSV quoting"
"$PY" scripts/triage/check_claims_csv_quoting.py
echo "check-fast: OK (fast gate; check.sh remains the pre-push authority)"
