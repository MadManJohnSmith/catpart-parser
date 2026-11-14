//! The nested store's vertex pool (G2 model) — the port of the Python
//! reference module ``catpart.geometry.pool``
//! (``src/catpart/geometry/pool.py``), per spec §2.1 of
//! ``docs/specs/phase5-viewer-spec.md`` (G2, the ``01 06`` groups).
//!
//! V0 (ticket #51): stub — the body lands with the non-composite
//! geometry slice (V2, ticket #41). The Python twin's docstring
//! carries the group wrapper, the P1g count escape and the
//! interleaved f32le triplets; this port cites, never restates.
//!
//! Evidence (the same citations the twin's docstring carries):
//!
//! - ``docs/evidence/2026-11-09-vertex-pool.md`` (the G2 model: the
//!   ``01 06`` groups, P1g/P2/P2g/P3, the composite-space sub-kinds)
//!
//! Numeric contract (spec §2.2): decode module — coordinates load as
//! f32 and widen to f64 once, at load; the
//! ``clippy::suboptimal_flops`` allow below is the pinned carve-out
//! (mul_add changes rounding and flips exact-equality decisions); see
//! the crate docs in ``../lib.rs`` for the full policy.
#![allow(clippy::suboptimal_flops)]
