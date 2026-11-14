//! Container-name table record parsing (schema v1) — the port of the
//! Python reference module ``catpart.containers``
//! (``src/catpart/containers.py``), per spec §2.1 of
//! ``docs/specs/phase5-viewer-spec.md`` (B1 records, kind law).
//!
//! V0 (ticket #51): stub — the decode body lands with the L1 slice
//! (V1, ticket #40). The Python twin's docstring carries the record
//! layout and the anchor-scan procedure; this port cites, never
//! restates.
//!
//! Evidence (the same citations the twin's docstring carries):
//!
//! - ``docs/evidence/2026-11-07-container-table-and-trailer.md``
//!   ("B1" — the fixed-layout record, the anchor scan, laws T1-T3,
//!   D1-D3)
//! - ``docs/evidence/2026-11-07-container-kind-law.md`` (the kind law:
//!   ``CATPrtCont`` / ``CATProdCont`` / ``CATMechProdCont``)
//!
//! Numeric contract (spec §2.2 point 3): decode module — the
//! ``suboptimal_flops`` allow below is the pinned carve-out (mul_add
//! changes rounding and flips exact-equality decisions); see the
//! crate docs in ``lib.rs`` for the full policy.
#![allow(clippy::suboptimal_flops)]
