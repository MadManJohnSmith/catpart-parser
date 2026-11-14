//! Classified export failures — the port of the Python reference
//! module ``catpart.geometry.errors``
//! (``src/catpart/geometry/errors.py``), per spec §2.1 of
//! ``docs/specs/phase5-viewer-spec.md`` (the classified error seam;
//! §2.3 pins the exact error-class vocabulary the viewer displays).
//!
//! V0 (ticket #51): stub — the body lands with the non-composite
//! geometry slice (V2, ticket #41). The Python twin's docstring
//! carries the class list and each class's violated-claim provenance;
//! this port cites, never restates. The machine contract is the
//! ``error_class`` string; the detail must be non-empty and cite the
//! violated claim (house convention, carried into the port — spec
//! §3.2).
//!
//! Evidence (the same citations the twin's docstring carries):
//!
//! - ``docs/evidence/2026-11-09-nested-store.md`` (section 6 — the
//!   G1 miss taxonomy behind ``missing-geometry-store``)
//! - ticket #32 (the classified-failure seam; the kebab-case class +
//!   evidence-citing detail convention, consistent with the fitness
//!   classification)
//!
//! Numeric contract (spec §2.2 point 3): decode module — the
//! ``suboptimal_flops`` allow below is the pinned carve-out (mul_add
//! changes rounding and flips exact-equality decisions); see the
//! crate docs in ``../lib.rs`` for the full policy.
#![allow(clippy::suboptimal_flops)]
