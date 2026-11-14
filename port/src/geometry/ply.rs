//! Binary little-endian PLY output — the port of the Python reference
//! module ``catpart.geometry.ply`` (``src/catpart/geometry/ply.py``),
//! per spec §2.1 of ``docs/specs/phase5-viewer-spec.md`` (binary-LE
//! PLY writer; Fidelity compares the PLY byte-identical, §3.2).
//!
//! V0 (ticket #51): stub — the body lands with the non-composite
//! geometry slice (V2, ticket #41). The Python twin's docstring
//! carries the writer contract (vertices = pool walk order, faces
//! as-is, f32/u32 little-endian); this port cites, never restates.
//!
//! Evidence: the twin's docstring cites no dedicated evidence note —
//! it is ticket #32's writer over the G2/G3 conventions; its claims
//! trace to ``docs/evidence/2026-11-09-vertex-pool.md`` (P3, the
//! f32le pool) and ``docs/evidence/2026-11-09-facet-semantics.md``
//! (F5, the winding law; G3's soup convention). Those are the
//! citations this port carries.
//!
//! Numeric contract (spec §2.2): decode module — the
//! ``clippy::suboptimal_flops`` allow below is the pinned carve-out
//! (mul_add changes rounding and flips exact-equality decisions); see
//! the crate docs in ``../lib.rs`` for the full policy.
#![allow(clippy::suboptimal_flops)]
