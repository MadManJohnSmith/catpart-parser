//! The composite index space decoded under the recovered identity law
//! (G6) — the port of the Python reference module
//! ``catpart.geometry.composite``
//! (``src/catpart/geometry/composite.py``, 1,916 lines — "the whale",
//! 55% of the geometry package, spec §10.2), per spec §2.1 of
//! ``docs/specs/phase5-viewer-spec.md``.
//!
//! V0 (ticket #51): stub — the body lands with V3 (ticket #42), in
//! the spec's internal stage order (walk + per-rep -> raw-array +
//! mixedwrite -> dup-pin + dedup + curve exposure), each stage ending
//! with a harness re-run. The Python twin's docstring carries the
//! landed model (P1t table, U1 table semantics, M2b element identity,
//! the E0-b dup-pin law as relaxed stage 15, the width rank incl.
//! u24be, the raw-array and mixedwrite laws, the fail-closed ladder);
//! this port cites, never restates.
//!
//! Evidence (the same citations the twin's docstring carries):
//!
//! - ``docs/evidence/2026-11-10-node-streams.md`` (the stage-3b/3d
//!   decode; the "Stage 4a-residue" raw-array section)
//! - ``docs/evidence/2026-11-11-per-rep-and-width-laws.md`` (R10/R11
//!   — the u24be width entry, 13bb5c0c byte-verified)
//! - ``docs/evidence/2026-11-12-curve-entry-analysis.md`` (section 5,
//!   claims row ``U4-stage5-recommendation`` — the E0-b dup-pin law's
//!   restricted analysis basis, + the stage-9-baseline recompute
//!   addendum)
//! - ``docs/evidence/2026-11-12-mixedwrite-reps.md`` and
//!   ``docs/evidence/2026-11-12-stage9-integration.md`` (the
//!   mixedwrite composition and the amended declaration)
//! - ``docs/evidence/2026-11-13-stage14-export-failures.md``
//!   (section 2 — the stage-15 relaxation measurement, owner decision
//!   handoff cont. 23)
//! - ``docs/evidence/data/residue-raw-scan.csv`` (raw-array rates)
//! - ``docs/evidence/data/stage9-absorption-probe.csv`` (the amended
//!   declaration basis, committed before the A/B)
//!
//! Numeric contract (spec §2.2): decode module — the densest
//! arithmetic surface of the port (the cross-product degenerate test,
//! the raw-array ``_nice``/nicety predicates, the plane law's
//! ``PLANE_TOL = 2e-3`` coplanarity, ``NOISE_REL = 1e-5`` re-listing
//! matching with the exact ``max(1.0, abs(...), ...)`` scale). All of
//! it is IEEE-exact ``+ - * /`` and comparisons on f64 widened once
//! from f32; expression shape copies the Python verbatim. The
//! ``clippy::suboptimal_flops`` allow below is the pinned carve-out —
//! mul_add changes rounding and flips exactly such exact-equality
//! decisions; see the crate docs in ``../lib.rs`` for the full
//! policy.
#![allow(clippy::suboptimal_flops)]
