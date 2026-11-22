//! Deterministic binary-signature families for store-level failures
//! (W8, marathon wave 4) — the port of the Python reference module
//! ``catpart.geometry.unclassified``
//! (``src/catpart/geometry/unclassified.py``).
//!
//! The W6 Top-1 ROI row (366 ``fail-unclassified`` submarine parts) is
//! closed at base dae7dd1: the per-file harness names every failure
//! (``error_class`` / ``failed_check``) and the census at base counts 0
//! unclassified rows on both corpora (docs/evidence/
//! 2026-11-22-w8-unclassified.md). What remained unnamed is the VARIANT
//! level: ``undecoded-variant`` covers both real variant gaps (content
//! the pinned decode families do not cover) and stores that carry no
//! geometry payload at all. This module names the latter
//! deterministically.
//!
//! The ``empty-geometry-store`` family (W8 signature law; measured
//! 10/10 on the official corpus's ``undecoded-variant`` cluster — CAA
//! fixture parts whose located ``CATStdCont`` store bodies are
//! 648-2,575 B with no payload markers):
//!
//! - the store located and validated (G1 N2/N6 passed — this is NOT
//!   ``missing-geometry-store``);
//! - zero pool groups (the no-pool arm: the flattened pool is empty);
//! - zero ``10 24 04 ff ff 00 00 00`` wrapper markers (``kinds`` empty —
//!   no pool sub-kind, no composite index space, no trailer opener);
//! - zero facet-header candidates (the facet scan finds nothing).
//!
//! Such a body cannot export under ANY pinned decode family — there is
//! nothing to decode — so the honest classification is the store's own.
//! A body with ANY wrapper marker or ANY facet candidate keeps
//! ``undecoded-variant`` (a real variant gap). The check runs where the
//! no-pool error is constructed, before the stage-13 second-chance
//! route (:fn:`export::unrouted_element_space`): a token-bearing
//! list-node store still exports through that route and the constructed
//! error is discarded, so every exporting store is row-identical
//! (fail-closed wiring).
//!
//! Evidence: ``docs/evidence/2026-11-22-w8-unclassified.md``.
//!
//! Numeric contract (spec §2.2 point 3): classification module — the
//! only measurement is the facet scanner's candidate count (an integer)
//! and the wrapper scan (integer offsets); no float arithmetic runs
//! here, so no ``suboptimal_flops`` carve-out is needed.

use super::errors::{EMPTY_GEOMETRY_STORE, ExportError, UNDECODED_VARIANT};
use super::facets;
use super::pool;
use super::store;

/// The G2 P8 no-pool classification this module refines (kept verbatim:
/// bodies outside the signature law keep it).
///
/// Twin: ``unclassified._NO_POOL_DETAIL``.
const NO_POOL_DETAIL: &str = "no 01 06 vertex pool decoded from the store body \
     (G2 P8 family: strips without a pool, or an empty store)";

/// The W8 binary signature of one store body (twin:
/// ``unclassified.BodySignature``).
///
/// Every field is a direct measurement of the body bytes (no parse
/// beyond the pinned scanners): the wrapper sub-kinds found after the
/// full wrapper, the facet-header candidate count, the body length and
/// the pool-group count (the caller's pool scan result).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BodySignature {
    /// The body length in bytes.
    pub body_bytes: usize,
    /// The wrapper sub-kinds, in body order.
    pub kinds: Vec<Vec<u8>>,
    /// The facet-header candidate count (the clean-path scan).
    pub facet_candidates: usize,
    /// The decoded pool-group count.
    pub pool_groups: usize,
}

impl BodySignature {
    /// The ``empty-geometry-store`` signature law (W8).
    ///
    /// Zero pool groups, zero wrapper markers, zero facet candidates:
    /// no pinned payload marker of any kind. A body with any marker
    /// keeps ``undecoded-variant``.
    pub fn is_empty_payload(&self) -> bool {
        self.pool_groups == 0 && self.kinds.is_empty() && self.facet_candidates == 0
    }

    /// The stable cluster signature string for the census tool (twin:
    /// ``BodySignature.signature``).
    pub fn signature(&self) -> String {
        let kinds = if self.kinds.is_empty() {
            "-".to_string()
        } else {
            self.kinds
                .iter()
                .map(|k| {
                    k.iter()
                        .map(|b| format!("{b:02x}"))
                        .collect::<Vec<_>>()
                        .join("")
                })
                .collect::<Vec<_>>()
                .join(",")
        };
        format!(
            "body={} pools={} kinds={} facet-cands={}",
            self.body_bytes, self.pool_groups, kinds, self.facet_candidates
        )
    }
}

/// Measure one store body's binary signature (W8 census law; twin:
/// ``unclassified.body_signature``).
///
/// Reads the wrapper sub-kinds in ``[body_lo, body_hi)`` (the same
/// ``10 24 04 ff ff 00 00 00`` scan the pool decoder uses) and the
/// facet-header candidate count (the same
/// :fn:`facets::scan_facets` call the exporter's clean path makes).
/// No other parse.
pub fn body_signature(
    data: &[u8],
    body_lo: usize,
    body_hi: usize,
    pool_groups: usize,
) -> BodySignature {
    let kinds = store::find_all(data, pool::FULL_WRAP, body_lo, body_hi)
        .into_iter()
        .map(|offset| data[offset + 8..offset + 10].to_vec())
        .collect();
    let scan = facets::scan_facets(data, body_lo, body_hi, true);
    BodySignature {
        body_bytes: body_hi - body_lo,
        kinds,
        facet_candidates: scan.candidates,
        pool_groups,
    }
}

/// The no-pool arm's classification (W8 wiring for ``export.rs``;
/// twin: ``unclassified.no_pool_error``).
///
/// Called where ``export_store`` is about to raise the G2 P8 no-pool
/// error (flattened pool empty). A body matching the
/// ``empty-geometry-store`` signature law raises the named class; any
/// other body keeps the original ``undecoded-variant`` error verbatim
/// (fail-closed: the stage-13 second-chance route and the composite
/// path are untouched).
pub fn no_pool_error(data: &[u8], span: &store::StoreSpan, kinds: &[Vec<u8>]) -> ExportError {
    // ``kinds`` is the caller's pool-scan sub-kind list (the
    // authoritative body-order measurement, already in hand); the facet
    // candidate count comes from the same ``scan_facets`` call the
    // clean path makes (twin: ``unclassified.no_pool_error``).
    let scan = facets::scan_facets(data, span.body_lo, span.body_hi, true);
    let signature = BodySignature {
        body_bytes: span.body_hi - span.body_lo,
        kinds: kinds.to_vec(),
        facet_candidates: scan.candidates,
        pool_groups: 0,
    };
    if signature.is_empty_payload() {
        return ExportError {
            error_class: EMPTY_GEOMETRY_STORE,
            detail: format!(
                "the located store body carries no geometry payload of any \
                 pinned kind ({}; W8 signature law, \
                 docs/evidence/2026-11-22-w8-unclassified.md — the part's \
                 geometry, if any, lives outside the nested stream store)",
                signature.signature()
            ),
        };
    }
    ExportError::new(UNDECODED_VARIANT, NO_POOL_DETAIL)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// An empty body (0 pools, 0 kinds, 0 facet candidates) matches the
    /// signature law.
    #[test]
    fn empty_body_signature_matches() {
        let data = vec![0u8; 64];
        let sig = body_signature(&data, 8, 32, 0);
        assert_eq!(sig.body_bytes, 24);
        assert!(sig.is_empty_payload());
        assert_eq!(sig.signature(), "body=24 pools=0 kinds=- facet-cands=0");
    }

    /// A body carrying a wrapper marker keeps ``undecoded-variant``
    /// (the fail-closed rule: any pinned marker is a variant gap, not
    /// an empty payload).
    #[test]
    fn wrapper_marker_keeps_undecoded_variant() {
        let mut data = vec![0u8; 64];
        data[8..16].copy_from_slice(pool::FULL_WRAP);
        data[16..18].copy_from_slice(b"\x01\x03"); // non-pool sub-kind
        let sig = body_signature(&data, 0, 64, 0);
        assert!(!sig.is_empty_payload());
        assert_eq!(sig.kinds, vec![b"\x01\x03".to_vec()]);
    }

    /// A zero-body signature string is stable for the census CSV.
    #[test]
    fn signature_is_stable() {
        let sig = BodySignature {
            body_bytes: 2575,
            kinds: vec![],
            facet_candidates: 0,
            pool_groups: 0,
        };
        assert_eq!(sig.signature(), "body=2575 pools=0 kinds=- facet-cands=0");
    }
}
