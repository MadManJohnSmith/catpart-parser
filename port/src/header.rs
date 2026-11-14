//! The 32-byte outer header of CATIA V5 ``.CATPart``/``.CATProduct``
//! files — the port of the Python reference module ``catpart.header``
//! (``src/catpart/header.py``), per spec §2.1 of
//! ``docs/specs/phase5-viewer-spec.md`` (the module-mapping table;
//! 32-byte header, H1 law).
//!
//! V0 (ticket #51): stub — the decode body lands with the L1 slice
//! (V1, ticket #40). The Python twin's docstring carries the decoded
//! field model; this port cites, never restates.
//!
//! Evidence (the same citations the twin's docstring carries):
//!
//! - ``docs/evidence/2026-11-07-container-triage.md`` ("Outer
//!   container structure")
//! - ``docs/evidence/2026-11-07-container-table-and-trailer.md``
//!   ("B1" — the dword12 chain law and the dual-region variant)
//!
//! Numeric contract (spec §2.2 point 3): decode module — the
//! ``suboptimal_flops`` allow below is the pinned carve-out (mul_add
//! changes rounding and flips exact-equality decisions); see the
//! crate docs in ``lib.rs`` for the full policy.
#![allow(clippy::suboptimal_flops)]
