//! The CATProduct structure decode core (Phase 6, Ticket P3-V0 under Spec F #45).
//!
//! Authority: `docs/specs/phase6-assembly-viewer-spec.md` (§2 and §8).
//! Prior evidence: `scripts/triage/p2_pool_pairing.py` and
//! `scripts/triage/p26_instance_binding.py`.

#![allow(clippy::suboptimal_flops)]

pub mod framing;
pub mod pairing;
pub mod pool;

pub use framing::{
    PoolCandidate, PoolForm, detect_pool_form, find_structure_pool, scan_framing_candidates,
    verify_length_law,
};
pub use pairing::{
    InstanceRecord, PairingClassificationSummary, PairingRule, ProductInstanceRecord,
    classify_pairings, extract_instances, is_constraint_name, separate_instances_and_constraints,
};
pub use pool::{
    BINARY_SENTINEL, ItemKind, PoolItem, decode_pool_texts, is_colon_shape, is_dot_shape, is_token,
    is_uscore_shape, walk_chain,
};

use serde::{Deserialize, Serialize};

/// Document representation of a decoded CATProduct structure (spec §7.1).
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ProductStructureDocument {
    pub schema_version: u32,
    pub product_name: String,
    pub detected_version: String,
    pub pool_form: String,
    pub total_instances: usize,
    pub placed_instances: usize,
    pub identity_instances: usize,
    pub instances: Vec<ProductInstanceRecord>,
    pub warnings: Vec<ProductWarning>,
}

/// Type alias for the top-level product structure document.
pub type ProductStructure = ProductStructureDocument;

/// Non-fatal diagnostic warning emitted during product structure decode.
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
pub struct ProductWarning {
    pub class: String,
    pub detail: String,
}

/// Refusal or decode error during product structure parsing.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProductError {
    pub class: &'static str,
    pub detail: String,
}

impl core::fmt::Display for ProductError {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        write!(f, "{}: {}", self.class, self.detail)
    }
}

impl std::error::Error for ProductError {}

/// Parse a CATProduct binary buffer into a structured [`ProductStructureDocument`].
pub fn parse_product(data: &[u8]) -> Result<ProductStructureDocument, ProductError> {
    if data.is_empty() {
        return Err(ProductError {
            class: "empty-buffer",
            detail: "cannot decode product structure from 0 bytes".to_string(),
        });
    }
    if data.len() < 32 {
        return Err(ProductError {
            class: "truncated-file",
            detail: format!(
                "buffer too short for CATIA container header: {} bytes",
                data.len()
            ),
        });
    }

    let detected_version = crate::version::detect_version(data).to_string();
    let pool_form = detect_pool_form(data);

    match pool_form {
        PoolForm::Framed => {
            let pool = find_structure_pool(data).ok_or_else(|| ProductError {
                class: "missing-structure-pool",
                detail: "failed to locate valid framed structure pool".to_string(),
            })?;

            let texts = decode_pool_texts(&pool.items);

            // Determine product name from ASMPRODUCT successor, identity block, or fallback
            let mut product_name = String::new();
            for (i, t) in texts.iter().enumerate() {
                if t == "ASMPRODUCT" && i + 1 < texts.len() {
                    let next = &texts[i + 1];
                    if !is_token(next) && !pool::is_class_token(next) && next != BINARY_SENTINEL {
                        product_name.clone_from(next);
                        break;
                    }
                }
            }
            if product_name.is_empty() {
                if let Some(doc_name) = crate::identity::parse_document_name(data) {
                    product_name = doc_name;
                } else {
                    product_name = "Product".to_string();
                }
            }

            let pool_has_position = texts.iter().any(|t| t == "_Position");
            let instances = extract_instances(&texts, pool_has_position);

            let total_instances = instances.len();
            let placed_instances = instances
                .iter()
                .filter(|i| i.placement_status == "placed")
                .count();
            let identity_instances = instances
                .iter()
                .filter(|i| i.placement_status == "identity")
                .count();

            Ok(ProductStructureDocument {
                schema_version: 1,
                product_name,
                detected_version,
                pool_form: pool_form.as_str().to_string(),
                total_instances,
                placed_instances,
                identity_instances,
                instances,
                warnings: Vec::new(),
            })
        }
        PoolForm::R15Ref => Ok(ProductStructureDocument {
            schema_version: 1,
            product_name: crate::identity::parse_document_name(data)
                .unwrap_or_else(|| "Product".to_string()),
            detected_version,
            pool_form: pool_form.as_str().to_string(),
            total_instances: 0,
            placed_instances: 0,
            identity_instances: 0,
            instances: Vec::new(),
            warnings: vec![ProductWarning {
                class: "r15-legacy-reference-form".to_string(),
                detail: "R15 attribute-reference form detected; structure pool is unframed"
                    .to_string(),
            }],
        }),
        PoolForm::Unframed => Ok(ProductStructureDocument {
            schema_version: 1,
            product_name: crate::identity::parse_document_name(data)
                .unwrap_or_else(|| "Product".to_string()),
            detected_version,
            pool_form: pool_form.as_str().to_string(),
            total_instances: 0,
            placed_instances: 0,
            identity_instances: 0,
            instances: Vec::new(),
            warnings: vec![ProductWarning {
                class: "unframed-pool".to_string(),
                detail: "no framed structure pool or R15 reference entries found".to_string(),
            }],
        }),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn build_synthetic_product_data(instances_payload: &[u8]) -> Vec<u8> {
        let mut data = vec![0u8; 32];
        data[..8].copy_from_slice(b"V5_CFV2\x00");
        // Embed CNEXTINFOS version token
        data.extend_from_slice(b"\x00\x00CNEXTINFOS\x00\x00B24\x00\x00");

        let tb = 1;
        let pool_span = instances_payload.len();
        let ln = (6 + tb + pool_span) as u32;

        let mut rec = Vec::new();
        rec.extend_from_slice(&framing::FRAME_MARK);
        rec.push(framing::FRAME_TAG_POOL);
        rec.extend_from_slice(&ln.to_le_bytes());
        rec.push(0xbf); // tb=1
        rec.extend_from_slice(instances_payload);

        data.extend_from_slice(&rec);
        data
    }

    #[test]
    fn parse_product_empty_buffer_fails_closed() {
        let err = parse_product(&[]).unwrap_err();
        assert_eq!(err.class, "empty-buffer");
    }

    #[test]
    fn parse_product_short_buffer_fails_closed() {
        let err = parse_product(&[0u8; 10]).unwrap_err();
        assert_eq!(err.class, "truncated-file");
    }

    #[test]
    fn parse_synthetic_placed_product() {
        let mut payload = Vec::new();
        payload.push(11);
        payload.extend_from_slice(b"ASMPRODUCT");
        payload.push(9);
        payload.extend_from_slice(b"Product1");
        payload.push(12);
        payload.extend_from_slice(b"_PartNumber");
        payload.push(8);
        payload.extend_from_slice(b"Part001");
        payload.push(14);
        payload.extend_from_slice(b"_InstanceName");
        payload.push(10);
        payload.extend_from_slice(b"Part001.1");
        payload.push(10);
        payload.extend_from_slice(b"_Position");
        payload.push(7);
        payload.extend_from_slice(b"PRDREP");

        let file_data = build_synthetic_product_data(&payload);
        let doc = parse_product(&file_data).unwrap();

        assert_eq!(doc.schema_version, 1);
        assert_eq!(doc.product_name, "Product1");
        assert_eq!(doc.pool_form, "framed");
        assert_eq!(doc.total_instances, 1);
        assert_eq!(doc.placed_instances, 1);
        assert_eq!(doc.identity_instances, 0);
        assert_eq!(doc.instances[0].part_number, "Part001");
        assert_eq!(doc.instances[0].instance_name, "Part001.1");
        assert_eq!(doc.instances[0].pairing_rule, PairingRule::Triple);
        assert!(doc.instances[0].has_position_attr);
        assert_eq!(doc.instances[0].placement_status, "placed");
    }

    #[test]
    fn parse_synthetic_identity_product() {
        // Without _Position
        let mut payload = Vec::new();
        payload.push(11);
        payload.extend_from_slice(b"ASMPRODUCT");
        payload.push(9);
        payload.extend_from_slice(b"Product1");
        payload.push(12);
        payload.extend_from_slice(b"_PartNumber");
        payload.push(8);
        payload.extend_from_slice(b"Part001");
        payload.push(14);
        payload.extend_from_slice(b"_InstanceName");
        payload.push(10);
        payload.extend_from_slice(b"Part001.1");
        payload.push(7);
        payload.extend_from_slice(b"PRDREP");

        let file_data = build_synthetic_product_data(&payload);
        let doc = parse_product(&file_data).unwrap();

        assert_eq!(doc.total_instances, 1);
        assert_eq!(doc.placed_instances, 0);
        assert_eq!(doc.identity_instances, 1);
        assert!(!doc.instances[0].has_position_attr);
        assert_eq!(doc.instances[0].placement_status, "identity");
    }

    #[test]
    fn parse_corpus_dictor_product1_if_available() {
        let manifest_dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR"));
        let path = manifest_dir.join("../corpus/Dictor/HaneulMyo/model/Product1.CATProduct");
        if !path.exists() {
            return;
        }
        let data = std::fs::read(&path).expect("read Dictor Product1");
        let doc = parse_product(&data).unwrap();
        assert_eq!(doc.pool_form, "framed");
        assert_eq!(doc.product_name, "Product1");
        // Dictor Product1 declares 3 instances (Part001.1, Part0024.1, Part001.2) and 5 constraints
        assert_eq!(doc.total_instances, 3);
        assert_eq!(doc.instances[0].part_number, "Part001");
        assert_eq!(doc.instances[0].instance_name, "Part001.1");
        assert_eq!(doc.instances[0].pairing_rule, PairingRule::Triple);
        assert!(doc.instances[0].has_position_attr);

        assert_eq!(doc.instances[1].part_number, "Part0024");
        assert_eq!(doc.instances[1].instance_name, "Part0024.1");
        assert_eq!(doc.instances[1].pairing_rule, PairingRule::BarePair);

        assert_eq!(doc.instances[2].part_number, "Part001");
        assert_eq!(doc.instances[2].instance_name, "Part001.2");
        assert_eq!(doc.instances[2].pairing_rule, PairingRule::BarePair);
    }

    #[test]
    fn parse_corpus_lengua_v2_if_available() {
        let manifest_dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR"));
        let path = manifest_dir
            .join("../corpus/Apoloo13/ASE_III/diseño_3d/lengua/lengua_v2/lengua.CATProduct");
        if !path.exists() {
            return;
        }
        let data = std::fs::read(&path).expect("read lengua_v2");
        let doc = parse_product(&data).unwrap();
        assert_eq!(doc.pool_form, "framed");
        assert!(doc.total_instances >= 30);
        // Ensure no constraints leaked into instances
        for inst in &doc.instances {
            assert!(
                !is_constraint_name(&inst.instance_name),
                "constraint {} leaked into instances!",
                inst.instance_name
            );
        }
    }
}
