//! The trailer terminating a CATIA V5 ``.CATPart``/``.CATProduct``
//! file — the port of the Python reference module ``catpart.trailer``
//! (``src/catpart/trailer.py``), per spec §2.1 of
//! ``docs/specs/phase5-viewer-spec.md`` (A..G dwords, CB__END).
//!
//! V0 (ticket #51): stub — the decode body lands with the L1 slice
//! (V1, ticket #40). The Python twin's docstring carries the A..G
//! dword rates and the writer-registration block; this port cites,
//! never restates.
//!
//! Evidence (the same citations the twin's docstring carries):
//!
//! - ``docs/evidence/2026-11-07-container-table-and-trailer.md``
//!   ("Trailer" — the seven big-endian dwords, the writer
//!   registration block)
//!
//! Numeric contract (spec §2.2 point 3): decode module — the
//! ``suboptimal_flops`` allow below is the pinned carve-out (mul_add
//! changes rounding and flips exact-equality decisions); see the
//! crate docs in ``lib.rs`` for the full policy.
#![allow(clippy::suboptimal_flops)]
