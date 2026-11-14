#!/bin/bash
# Local merge gate (ticket #38): mirrors .github/workflows/ci.yml —
# pinned ruff + pytest over the corpus-free suite, plus the port/
# crate's cargo steps (Phase 5 spec §7, ticket #51) — before history
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
    echo "        Set up first: python -m venv .venv && .venv/bin/pip install -e '.[test,lint]'" >&2
    echo "        ('.[test]' alone misses the pinned ruff — review F3, ticket #51)." >&2
    exit 1
  }
fi
echo "check: PY=$PY RUFF=$RUFF"
echo "check: ruff check ."
"$RUFF" check .
echo "check: pytest -q"
"$PY" -m pytest -q
# Port crate (Phase 5 spec §7, ticket #51): the cargo steps mirror
# ci.yml's port job, same order. From V0 the Rust toolchain is a
# REQUIRED dev dependency — a machine without it fails the gate
# loudly here exactly as the CI job would fail; nothing skips
# silently.
if ! command -v cargo >/dev/null 2>&1; then
  echo "check: FAIL — cargo not found. From V0 the Rust toolchain is a" >&2
  echo "        required dev dependency (spec §7; ticket #51). Install" >&2
  echo "        rustup, then run 'rustup toolchain install' inside port/" >&2
  echo "        (port/rust-toolchain.toml pins channel, components and" >&2
  echo "        the wasm32 target)." >&2
  exit 1
fi
cd port
echo "check: cargo build (native)"
cargo build --locked
echo "check: cargo build (wasm32-unknown-unknown)"
cargo build --locked --target wasm32-unknown-unknown
echo "check: cargo fmt --check (port)"
cargo fmt --check
echo "check: cargo clippy -D warnings (port)"
cargo clippy --locked -- -D warnings
echo "check: cargo test (port)"
cargo test --locked
