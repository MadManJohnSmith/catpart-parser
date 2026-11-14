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
# V4 (ticket #43, spec §7 step 6): the shipped-artifact steps mirror
# ci.yml's port job — wasm-pack pinned 0.15.1 (recorded on the ticket
# per §2.1). The build goes to a check dir OUTSIDE the committed pkg/
# (port/pkg/ + site/viewer/pkg/ are reviewed artifacts; refreshing them
# is a deliberate maintainer step, never a gate side effect). The Node
# tests RUN the shipped artifact on the §7 fixture subset. Playwright
# stays LOCAL (scripts/viewer_acceptance.py — never CI, §7).
if ! command -v wasm-pack >/dev/null 2>&1; then
  echo "check: FAIL — wasm-pack not found. From V4 it is a required dev" >&2
  echo "        dependency for these steps (spec §7 step 6; ticket #43)." >&2
  echo "        Install the pinned release:" >&2
  echo "        curl -sSLO https://github.com/wasm-bindgen/wasm-pack/releases/download/v0.15.1/wasm-pack-v0.15.1-x86_64-unknown-linux-musl.tar.gz" >&2
  echo "        (sha256 410101009739b9d01c7d5affaaad6e9c9a24b4cba6791a4805db8e89b9bf7af2;" >&2
  echo "        untar and put wasm-pack on PATH)." >&2
  exit 1
fi
echo "check: wasm-pack build --target web --release (check dir)"
wasm-pack build --target web --release --out-dir target/wasm-pack-check
echo "check: wasm-pack test --node (the shipped artifact runs)"
wasm-pack test --node
# V4 review F1 (ticket #43, 2026-11-14): the two committed pkg copies
# must never drift — the shipped viewer (site/viewer/pkg/, what
# gh-pages serves verbatim) stays byte-identical to the built crate
# (port/pkg/). Refresh both together or neither.
echo "check: pkg sync (port/pkg vs site/viewer/pkg)"
cd "$(git rev-parse --show-toplevel)"
diff -q -r port/pkg site/viewer/pkg || {
  echo "check: FAIL — port/pkg and site/viewer/pkg have diverged." >&2
  echo "        Rebuild with wasm-pack and refresh BOTH copies together," >&2
  echo "        or neither." >&2
  exit 1
}
