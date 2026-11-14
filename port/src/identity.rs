//! The CATIA identity block: the save-time document name (schema v1) —
//! the port of the Python reference module ``catpart.identity``
//! (``src/catpart/identity.py``), per spec §2.1 of
//! ``docs/specs/phase5-viewer-spec.md`` (document_name, C3).
//!
//! V0 (ticket #51): stub — the decode body lands with the L1 slice
//! (V1, ticket #40). The Python twin's docstring carries the walk
//! model (claim D2) and the presence rates; this port cites, never
//! restates.
//!
//! Evidence (the same citations the twin's docstring carries):
//!
//! - ``docs/evidence/2026-11-08-units-names-probe.md`` (C3 phase A,
//!   ticket #25 — claims D1/D2/D4, the save-time-name exceptions)
//! - ``docs/evidence/2026-11-07-container-payload-layout.md`` ("The
//!   CATIA identity block")
//! - ``docs/format/payload-blocks.md`` section 5.3 (the documented
//!   negative: no unit-system structure — the module parses names
//!   only, deliberately no units field)
//!
//! Numeric contract (spec §2.2 point 3): decode module — the
//! ``suboptimal_flops`` allow below is the pinned carve-out (mul_add
//! changes rounding and flips exact-equality decisions); see the
//! crate docs in ``lib.rs`` for the full policy.
#![allow(clippy::suboptimal_flops)]
