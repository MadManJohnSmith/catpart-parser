# ADR-0002: Parser implementation is Python first

The project's engine is AI-agent sessions hill-climbing on fitness (ADR-0001),
so iteration velocity of the grind outweighs runtime performance for L1/L2.
The parser lives in Python — one src-layout package (`src/catpart/`), CLI
`catpart-inspect` as a console script, core stdlib-only (`struct`, zero
dependencies, Python ≥3.11) so no agent session is blocked installing
anything. The fitness runner is also Python (ADR-0001), which keeps one
runtime. If L3 (B-rep, files up to 375 MB) demands it, hot modules are
rewritten then — that would be a new decision with its own ADR, not a
planned migration.

## Considered Options

- Rust from the start: rejected — per-cycle compilation slows the grind and
  the structural-exploration ecosystem is slower for agents.
- Planned Python→Rust migration at L1: rejected — migrations are rarely
  free and double the stabilization work.
- Loose modules without a package: rejected — the installable CLI and the
  versioned JSON schema already require packaging.

## Consequences

- Distribution story is `pip install -e .` during development; PyPI
  publication deferred to Phase 3 acceptance.
- Parser docstrings cite the evidence note and byte ranges that justify
  each structure they parse.
