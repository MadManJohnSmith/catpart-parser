//! The geometry half of the Port: nested-store navigation, vertex
//! pool, facet semantics, mesh invariants, PLY output, the classified
//! error seam, the export orchestration and the composite index
//! space — the 1:1 port of the Python package ``catpart/geometry/``
//! (spec §2.1 of ``docs/specs/phase5-viewer-spec.md``).
//!
//! V0 (ticket #51): module stubs only — bodies land with V2
//! (non-composite, ticket #41) and V3 (the composite whale,
//! ticket #42). Each sub-module's doc header cites the evidence notes
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
