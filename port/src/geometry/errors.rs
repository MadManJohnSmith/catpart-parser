//! Classified export failures — the port of the Python reference
//! module ``catpart.geometry.errors``
//! (``src/catpart/geometry/errors.py``), per spec §2.1 of
//! ``docs/specs/phase5-viewer-spec.md`` (the classified error seam;
//! §2.3 pins the exact error-class vocabulary the viewer displays).
//!
//! Every ``fidelity-cli export`` failure is machine-readable: an
//! :struct:`ExportError` carries a kebab-case ``error_class`` and a
//! human ``detail`` naming the violated evidence claim, printed as one
//! JSON line on stderr with exit code 1 (usage errors exit 2, mirroring
//! ``catpart-export``'s argparse convention). The machine contract is
//! the ``error_class`` string (§3.2 compares exactly that); the detail
//! must be non-empty and cite the violated claim (house convention,
//! carried into the port). The class constants below are the twin's
//! raise-site strings, single-sourced here so the vocabulary cannot
//! drift between modules; the raise sites stay 1:1 with the twins'.
//!
//! Error classes (the twin's docstring; consistent with the fitness
//! classification convention of kebab-case classes plus
//! evidence-citing detail):
//!
//! - ``missing-geometry-store``: no ``CATStdCont`` block, or no
//!   validated nested stream store in any ``CATStdCont``/
//!   ``CATXDocLinkCont``/``CATSeeBodyCont`` region (G1's miss taxonomy,
//!   docs/evidence/2026-11-09-nested-store.md section 6; the non-stdcont
//!   probes are the stage-3a recovery extension, #34).
//! - ``undecoded-variant``: a store is present but its geometry is not
//!   exportable under the pinned decode model — composite index space
//!   (G3 claim F8, open question 1), facet references beyond the pool
//!   (G3 open question 2), or no exportable facet content at all
//!   (0x41/0x44/0x4b/0x4e-only stores, G3 open questions 3-5).
//! - ``malformed-store-header``: a ``V5_CFV2`` header is present but
//!   fails the G1 N2 validation (ff x 8, zeros x 8, sane dwords,
//!   catalog magic), or its catalog tail matches neither the N6 trailer
//!   laws nor the two stage-3a relaxed-tail recovery families
//!   (dword8-overshoot, padded).
//! - ``malformed-pool-group``: a ``01 06`` pool group's walked
//!   vertex-record count does not equal its count field (G2 claim P2g
//!   violation; 2,090/2,090 corpus groups walk exactly, so a mismatch
//!   is broken structure).
//! - ``malformed-pool-vertex``: non-finite (NaN/inf) coordinates in the
//!   pool (G2 claim P3 violation; 100% finite corpus-wide).
//! - ``unreadable-file`` / ``io-error``: input path cannot be read,
//!   output cannot be written (OSError).
//!
//! Evidence (the same citations the twin's docstring carries):
//!
//! - ``docs/evidence/2026-11-09-nested-store.md`` (section 6 — the
//!   G1 miss taxonomy behind ``missing-geometry-store``)
//! - ticket #32 (the classified-failure seam; the kebab-case class +
//!   evidence-citing detail convention, consistent with the fitness
//!   classification)
//!
//! Numeric contract (spec §2.2 point 3): decode module — the
//! ``suboptimal_flops`` allow below is the pinned carve-out (mul_add
//! changes rounding and flips exact-equality decisions); see the
//! crate docs in ``../lib.rs`` for the full policy.
#![allow(clippy::suboptimal_flops)]

use std::fmt;

/// The §2.3 error-class vocabulary, verbatim from the twin's raise
/// sites (single-sourced so the strings cannot drift between modules).
pub const MISSING_GEOMETRY_STORE: &str = "missing-geometry-store";
pub const UNDECODED_VARIANT: &str = "undecoded-variant";
pub const MALFORMED_STORE_HEADER: &str = "malformed-store-header";
pub const MALFORMED_POOL_GROUP: &str = "malformed-pool-group";
pub const MALFORMED_POOL_VERTEX: &str = "malformed-pool-vertex";
pub const UNREADABLE_FILE: &str = "unreadable-file";
pub const IO_ERROR: &str = "io-error";

/// A classified export failure — the twin's
/// :class:`catpart.geometry.errors.ExportError`. ``error_class`` is the
/// machine-readable class (kebab-case), ``detail`` the human
/// explanation citing the evidence claim that was violated.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ExportError {
    /// The machine-readable class (one of the constants above).
    pub error_class: &'static str,
    /// The human explanation; non-empty, cites the violated claim.
    pub detail: String,
}

impl ExportError {
    /// The twin's ``ExportError(error_class, detail)`` constructor.
    pub fn new(error_class: &'static str, detail: impl Into<String>) -> Self {
        ExportError {
            error_class,
            detail: detail.into(),
        }
    }
}

/// The twin's ``str(exc)`` shape: ``"{error_class}: {detail}"``.
impl fmt::Display for ExportError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}: {}", self.error_class, self.detail)
    }
}

impl std::error::Error for ExportError {}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn display_carries_class_and_detail() {
        let error = ExportError::new(MISSING_GEOMETRY_STORE, "no CATStdCont storage block");
        assert_eq!(
            error.to_string(),
            "missing-geometry-store: no CATStdCont storage block"
        );
        assert_eq!(error.error_class, "missing-geometry-store");
        assert!(!error.detail.is_empty());
    }

    #[test]
    fn vocabulary_is_the_twin_kebab_classes() {
        // §2.3's exact vocabulary — the classes the harness compares.
        assert_eq!(UNDECODED_VARIANT, "undecoded-variant");
        assert_eq!(MALFORMED_STORE_HEADER, "malformed-store-header");
        assert_eq!(MALFORMED_POOL_GROUP, "malformed-pool-group");
        assert_eq!(MALFORMED_POOL_VERTEX, "malformed-pool-vertex");
        assert_eq!(UNREADABLE_FILE, "unreadable-file");
        assert_eq!(IO_ERROR, "io-error");
    }
}
