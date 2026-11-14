//! The geometry half of the Port: nested-store navigation, vertex
//! pool, facet semantics, mesh invariants, PLY output, the classified
//! error seam, the export orchestration and the composite index
//! space — the 1:1 port of the Python package ``catpart/geometry/``
//! (spec §2.1 of ``docs/specs/phase5-viewer-spec.md``).
//!
//! V2 (ticket #41): every sub-module except ``composite`` carries the
//! real 1:1 port (the Python twins' behavior mirrored, fail-closed
//! arms included); ``composite.rs`` remains the V0 stub until V3
//! (ticket #42) — the export orchestration's composite route fails
//! closed with the twin's ``undecoded-variant`` class until then (the
//! Fidelity harness excludes composite-path exports; ticket #41's
//! hard stop). Each sub-module's doc header cites the evidence notes
//! its Python twin cites; the numeric-contract lint policy (spec
//! §2.2) lives in the crate docs (``../lib.rs``) and as the pinned
//! ``clippy::suboptimal_flops`` carve-out in each decode module.

pub mod composite;
pub mod errors;
pub mod export;
pub mod facets;
pub mod mesh;
pub mod ply;
pub mod pool;
pub mod store;
