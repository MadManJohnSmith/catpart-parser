//! Mesh invariants over the decoded triangle soup (G3 F6/F8 measures)
//! — the port of the Python reference module
//! ``catpart.geometry.mesh`` (``src/catpart/geometry/mesh.py``), per
//! spec §2.1 of ``docs/specs/phase5-viewer-spec.md`` (invariants).
//!
//! V0 (ticket #51): stub — the body lands with the non-composite
//! geometry slice (V2, ticket #41). The Python twin's docstring
//! carries the invariant set (undirected edge usage, manifold,
//! closure, orientation consistency, boundary count) and the
//! ``open-shell`` warning class; this port cites, never restates.
//!
//! Evidence: the twin's docstring cites no dedicated evidence note —
//! it is adapted from ``scripts/triage/decode_facet_semantics.py``'s
//! ``soup_stats`` with the semantics unchanged (ticket #32), its
//! numbers are the G3 acceptance-seed soup measures (140 triangles,
//! 210 edges, closed manifold, oriented) and its claim home is the
//! G3 note's F6/F8: ``docs/evidence/2026-11-09-facet-semantics.md``.
//! Those are the citations this port carries.
//!
//! Numeric contract (spec §2.2): decode module — the
//! ``clippy::suboptimal_flops`` allow below is the pinned carve-out
//! (mul_add changes rounding and flips exact-equality decisions); see
//! the crate docs in ``../lib.rs`` for the full policy.
#![allow(clippy::suboptimal_flops)]
