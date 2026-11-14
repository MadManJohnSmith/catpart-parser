//! The nested store's facet records and their primitive semantics
//! (G3) — the port of the Python reference module
//! ``catpart.geometry.facets`` (``src/catpart/geometry/facets.py``),
//! per spec §2.1 of ``docs/specs/phase5-viewer-spec.md`` (G3 tiling +
//! soup).
//!
//! V0 (ticket #51): stub — the body lands with the non-composite
//! geometry slice (V2, ticket #41). The Python twin's docstring
//! carries the record grammar, the tiling law (F1w as corrected), the
//! lex-rank index space and the primitive semantics; this port cites,
//! never restates.
//!
//! Evidence (the same citations the twin's docstring carries):
//!
//! - ``docs/evidence/2026-11-09-facet-semantics.md`` (the G3 model:
//!   F1/F1w/F2/F3/F4/F5/F6/F7/F8/F9/F10; the #35 record-width
//!   correction, 2026-11-10, class-bounded to clean stores)
//!
//! Numeric contract (spec §2.2): decode module — coordinates load as
//! f32 and widen to f64 once, at load; every decision arithmetic is
//! IEEE-exact and the degenerate-triangle test is tuple equality
//! against ``(0.0, 0.0, 0.0)`` on a cross product (``decode_soup``),
//! so the ``clippy::suboptimal_flops`` allow below is the pinned
//! carve-out (mul_add changes rounding and flips exactly such
//! decisions); see the crate docs in ``../lib.rs`` for the full
//! policy.
#![allow(clippy::suboptimal_flops)]
