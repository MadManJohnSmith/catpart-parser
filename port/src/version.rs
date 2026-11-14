//! Per-file version detection via the embedded CNEXTINFOS release
//! marker — the port of the Python reference module
//! ``catpart.version`` (``src/catpart/version.py``), per spec §2.1 of
//! ``docs/specs/phase5-viewer-spec.md`` (CNEXTINFOS detection).
//!
//! V0 (ticket #51): stub — the decode body lands with the L1 slice
//! (V1, ticket #40). The Python twin's docstring carries the anchored
//! token rule and the windowing (8 KB primary, 64 KB fallback); this
//! port cites, never restates.
//!
//! Evidence (the same citations the twin's docstring carries):
//!
//! - ``docs/evidence/2026-11-07-container-triage.md`` ("Per-file
//!   version marker" — the CNEXTINFOS-anchored release token, the
//!   windowing counts, the naive-pattern negative)
//!
//! Numeric contract (spec §2.2 point 3): decode module — the
//! ``suboptimal_flops`` allow below is the pinned carve-out (mul_add
//! changes rounding and flips exact-equality decisions); see the
//! crate docs in ``lib.rs`` for the full policy.
#![allow(clippy::suboptimal_flops)]
