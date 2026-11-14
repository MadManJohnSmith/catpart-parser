//! Export orchestration: nested store -> PLY + summary — the port of
//! the Python reference module ``catpart.geometry.export``
//! (``src/catpart/geometry/export.py``), per spec §2.1 of
//! ``docs/specs/phase5-viewer-spec.md`` (orchestration + recovery).
//!
//! V0 (ticket #51): stub — the body lands with the non-composite
//! geometry slice (V2, ticket #41). The Python twin's docstring
//! carries the export rule ("export what the evidence pins"), the
//! schema-versioned summary contract and the stage-3a/12 recovery
//! composition; this port cites, never restates.
//!
//! Evidence: the twin's docstring cites no dedicated evidence note —
//! it composes the sibling modules' models (each cites its own note;
//! see ``store.rs``/``pool.rs``/``facets.rs``/``mesh.rs``/``ply.rs``/
//! ``errors.rs``/``composite.rs`` here) and names the recovery
//! extensions, which trace to
//! ``docs/evidence/2026-11-10-l2-grind-classification.md`` (sections
//! 5-6, stage 3a #34) and the stage-12 ``other-container`` family.
//! The summary schema is the committed
//! ``src/catpart/schema/export-summary-v1.json``. Those are the
//! citations this port carries.
//!
//! Numeric contract (spec §2.2): decode module — coordinates are f32
//! widened to f64 once at load, all arithmetic f64 in verbatim
//! expression shape; the ``clippy::suboptimal_flops`` allow below is
//! the pinned carve-out (mul_add changes rounding and flips
//! exact-equality decisions); see the crate docs in ``../lib.rs`` for
//! the full policy.
#![allow(clippy::suboptimal_flops)]
