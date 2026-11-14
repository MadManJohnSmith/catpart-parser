//! The **Port** (GLOSSARY): the decode pipeline of the Python reference
//! `src/catpart/` reproduced in Rust. The Phase 5 design authority is
//! `docs/specs/phase5-viewer-spec.md` — sections cited below are its
//! sections, the way Python docstrings cite evidence notes.
//!
//! # Layout (spec §2.1)
//!
//! One crate, two targets: the `rlib` compiles native — the Fidelity
//! harness drives it through the native CLI seam (§2.4, V1) — and the
//! `cdylib` compiles `wasm32-unknown-unknown` — what the viewer ships
//! (§5). Same code proves Fidelity natively and ships to the browser.
//! Modules mirror the Python package 1:1 so review can walk them side
//! by side and the harness can name the seam per module:
//!
//! | Python (reference)              | Rust (`port/src/`)      | Notes |
//! | ------------------------------- | ----------------------- | ----- |
//! | `catpart/header.py`             | `header.rs`             | 32-byte header, H1 law |
//! | `catpart/containers.py`         | `containers.rs`         | B1 records, kind law |
//! | `catpart/trailer.py`            | `trailer.rs`            | A..G dwords, CB__END |
//! | `catpart/version.py`            | `version.rs`            | CNEXTINFOS detection |
//! | `catpart/identity.py`           | `identity.rs`           | document_name (C3) |
//! | `catpart/geometry/store.py`     | `geometry/store.rs`     | G1 + stage-3a/12 probes |
//! | `catpart/geometry/pool.py`      | `geometry/pool.rs`      | G2, `01 06` groups |
//! | `catpart/geometry/facets.py`    | `geometry/facets.rs`    | G3 tiling + soup |
//! | `catpart/geometry/mesh.py`      | `geometry/mesh.rs`      | invariants |
//! | `catpart/geometry/ply.py`       | `geometry/ply.rs`       | binary-LE PLY writer |
//! | `catpart/geometry/errors.py`    | `geometry/errors.rs`    | classified error seam |
//! | `catpart/geometry/export.py`    | `geometry/export.rs`    | orchestration + recovery |
//! | `catpart/geometry/composite.py` | `geometry/composite.rs` | the whale (§10.2) |
//!
//! Every Rust module's doc header cites the same evidence notes its
//! Python twin cites (ADR-0002's docstring discipline, carried over).
//!
//! # The numeric contract (spec §2.2 — the Fidelity keystone)
//!
//! The decode is bit-exact by construction only if the port preserves
//! the Python reference's float behavior. The port MUST:
//!
//! 1. Load coordinates as f32 and widen to f64 once, at load; all
//!    arithmetic in f64, never f32 (f32 rounding at a different point
//!    flips exact-equality decisions).
//! 2. Preserve operation order and expression shape verbatim from the
//!    Python — no reassociation, no factoring: `a*b - c*d` stays
//!    exactly that.
//! 3. **No fused multiply-add.** Rust never applies fast-math on
//!    stable — but `clippy::suboptimal_flops` *suggests* `mul_add` for
//!    `a*b ± c*d` patterns, and accepting that suggestion changes
//!    rounding and breaks exact-equality decisions (the
//!    degenerate-triangle tuple equality at `facets.py:decode_soup`,
//!    `_nice`'s `1e9` bound, `NOISE_REL` matching).
//! 4. Copy every tolerance/equality constant verbatim (`1e9`, `1e-6`,
//!    `1e7`, `2e-3`, `1e-5`, `0`) — including exact `==` comparisons
//!    that a "robustness" refactor would replace with epsilon tests.
//!
//! ## Lint policy pinned at V0 (ticket #51)
//!
//! The crate is gated with `cargo clippy -D warnings` (CI and
//! `scripts/check.sh` mirror it) — the ruff analog of §7 step 3. The
//! one deliberate carve-out: **only the decode modules** (the files of
//! the §2.1 mapping above; not this file, not `geometry/mod.rs`, not
//! the future `bin/fidelity-cli.rs`) carry
//! `#![allow(clippy::suboptimal_flops)]`, each with the reason at the
//! attribute. That allow does not license any other suppression: no
//! fast-math, no other `allow`, no `expect`, no `#[rustfmt::skip]`
//! near arithmetic. And the harness (V1) must run before any "clippy
//! cleanup" is allowed near the decode modules (§10 risk 1).
//!
//! Two facts verified empirically on the pinned toolchain
//! (rustc/clippy 1.99.1, 2026-11-13, ticket #51):
//!
//! - `clippy::suboptimal_flops` is **not** in clippy's default set on
//!   1.99.1: `cargo clippy -- -D warnings` does not emit mul_add
//!   suggestions today, on any module. The gate is therefore already
//!   mul_add-suggestion-free; the allows stand so the carve-out is
//!   correct the day that changes (a clippy release promoting the
//!   lint into the default set, or an explicit
//!   `-W clippy::suboptimal_flops` pass).
//! - A module-level `#![allow(...)]` beats a command-line `-D`: under
//!   `-D clippy::suboptimal_flops` the decode modules stay clean
//!   while every other module errors. The allow placement (decode
//!   modules only) is what makes the carve-out work if the default
//!   set ever carries the lint.
//!
//! # Dependencies (spec §2.1/§2.3)
//!
//! `wasm-bindgen` (+ `wasm-bindgen-test` dev) — the boundary and the
//! headless WASM tests (V4); `serde` + `serde_json` — the summary
//! structs mirroring `export-summary-v1.json` / schema-v1 (field
//! declaration order = Python dict construction order). No other
//! runtime crates. Toolchain pinned by `port/rust-toolchain.toml`.
//!
//! # V0 status (ticket #51)
//!
//! Skeleton only: every module of the mapping is a documented stub
//! (doc header + empty body). Bodies land with V1 (L1 slice + harness,
//! #40), V2 (non-composite geometry, #41) and V3 (composite, #42).

pub mod containers;
pub mod geometry;
pub mod header;
pub mod identity;
pub mod trailer;
pub mod version;
