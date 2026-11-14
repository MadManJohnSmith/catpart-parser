//! Nested V5_CFV2 stream-store navigation (G1 model) — the port of
//! the Python reference module ``catpart.geometry.store``
//! (``src/catpart/geometry/store.py``), per spec §2.1 of
//! ``docs/specs/phase5-viewer-spec.md`` (G1 + the stage-3a/12 probes).
//!
//! V0 (ticket #51): stub — the body lands with the non-composite
//! geometry slice (V2, ticket #41). The Python twin's docstring
//! carries the header/header-less variants, the trailer-law catalog
//! validation and the recovery extension; this port cites, never
//! restates.
//!
//! Evidence (the same citations the twin's docstring carries):
//!
//! - ``docs/evidence/2026-11-09-nested-store.md`` (the G1 model: N1,
//!   N1h/N1l, N2, N3, N4w, N6; corrections C1/C3; section 6 the miss
//!   taxonomy)
//! - ``docs/evidence/2026-11-10-l2-grind-classification.md``
//!   (sections 5-6 — the stage-3a recovery extension, #34: the
//!   relaxed tail law and the non-stdcont probes)
//!
//! Numeric contract (spec §2.2 point 3): decode module — the
//! ``suboptimal_flops`` allow below is the pinned carve-out (mul_add
//! changes rounding and flips exact-equality decisions); see the
//! crate docs in ``../lib.rs`` for the full policy.
#![allow(clippy::suboptimal_flops)]
