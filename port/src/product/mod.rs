//! The CATProduct structure decode core (Phase 6, Ticket P3-V0 under Spec F #45).
//!
//! Authority: `docs/specs/phase6-assembly-viewer-spec.md` (§2 and §8).
//! Prior evidence: `scripts/triage/p2_pool_pairing.py` and
//! `scripts/triage/p26_instance_binding.py`.

#![allow(clippy::suboptimal_flops)]

pub mod binding;
pub mod framing;
pub mod pairing;
pub mod pool;
pub mod transforms;

pub use binding::{
    BindingMode, IDENTITY_TRANSFORM, PlacementBinding, PlacementStatus, bind_instances,
    compute_bindings,
};
pub use framing::{
    PoolCandidate, PoolForm, detect_pool_form, extract_r15_instance_names, find_structure_pool,
    scan_framing_candidates, verify_length_law,
};
pub use pairing::{
    InstanceRecord, PairingClassificationSummary, PairingRule, ProductInstanceRecord,
    classify_pairings, extract_instances, is_constraint_name, separate_instances_and_constraints,
};
pub use pool::{
    BINARY_SENTINEL, ItemKind, PoolItem, decode_pool_texts, is_colon_shape, is_dot_shape, is_token,
    is_uscore_shape, walk_chain,
};
pub use transforms::{
    TransformRecord, decode_129b_record, decode_r15_matrix_stream, is_81b_connector_record,
    is_129b_magic, parse_run_length_floats, scan_modern_transform_records, scan_r15_matrix_streams,
    scan_raw_56b_records,
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
            let mut instances = extract_instances(&texts, pool_has_position);

            // Scan for transform records:
            // 1. Modern 129b records (with 81b connector record filtering)
            let mut transform_records = scan_modern_transform_records(data);
            // 2. R15 inline matrix streams fallback
            if transform_records.is_empty() {
                transform_records = scan_r15_matrix_streams(data);
            }
            // 3. Raw 56b ctorproxy records fallback
            if transform_records.is_empty() {
                transform_records = scan_raw_56b_records(data);
            }

            // Bind instances to transforms
            let binding_mode =
                bind_instances(&mut instances, &transform_records, pool_has_position);

            let mut warnings = Vec::new();
            if binding_mode == BindingMode::Undecodable {
                warnings.push(ProductWarning {
                    class: "undecodable-placement".to_string(),
                    detail: format!(
                        "constraint mesh override or unresolvable transform records ({} records for {} instances)",
                        transform_records.len(),
                        instances.len()
                    ),
                });
            }

            let total_instances = instances.len();
            let placed_instances = instances
                .iter()
                .filter(|i| i.placement_status == PlacementStatus::Placed)
                .count();
            let identity_instances = instances
                .iter()
                .filter(|i| i.placement_status == PlacementStatus::Identity)
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
                warnings,
            })
        }
        PoolForm::R15Ref => {
            let inst_names = extract_r15_instance_names(data);
            let instances: Vec<ProductInstanceRecord> = inst_names
                .into_iter()
                .map(|name| {
                    let part_number = name
                        .rsplit_once('.')
                        .map_or(&name[..], |(stem, _)| stem)
                        .to_string();
                    ProductInstanceRecord {
                        instance_name: name,
                        part_number,
                        pairing_rule: crate::product::pairing::PairingRule::BarePair,
                        has_position_attr: true,
                        placement_status: PlacementStatus::Undecodable,
                        transform: None,
                        object_tag: None,
                        classification_detail: Some("r15-legacy-reference-form".to_string()),
                    }
                })
                .collect();
            let total_instances = instances.len();
            Ok(ProductStructureDocument {
                schema_version: 1,
                product_name: crate::identity::parse_document_name(data)
                    .unwrap_or_else(|| "Product".to_string()),
                detected_version,
                pool_form: pool_form.as_str().to_string(),
                total_instances,
                placed_instances: 0,
                identity_instances: 0,
                instances,
                warnings: vec![ProductWarning {
                    class: "r15-legacy-reference-form".to_string(),
                    detail: "R15 attribute-reference form detected; structure pool is unframed"
                        .to_string(),
                }],
            })
        }
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

    fn push_pool_item(payload: &mut Vec<u8>, text: &str) {
        payload.push((text.len() + 1) as u8);
        payload.extend_from_slice(text.as_bytes());
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
    fn parse_synthetic_placed_product_with_129b_transform() {
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

        let mut file_data = build_synthetic_product_data(&payload);

        // Append a valid 129-byte transform record
        let magic = transforms::RECORD_129B_MAGIC_R20;
        let tag_id: u32 = 42;
        let sep = transforms::SEPARATOR_BYTE;
        let t = [12.5f64, -34.0, 56.78];
        let q = [1.0f64, 0.0, 0.0, 0.0];
        let flags = [1.0f64, 0.0, 0.0, 0.0];
        let bbox = [10.0f64, 20.0, 30.0, 40.0];

        let mut rec = Vec::with_capacity(129);
        rec.extend_from_slice(&magic);
        rec.extend_from_slice(&tag_id.to_le_bytes());
        rec.push(sep);
        for v in t {
            rec.extend_from_slice(&v.to_le_bytes());
        }
        for v in q {
            rec.extend_from_slice(&v.to_le_bytes());
        }
        for v in flags {
            rec.extend_from_slice(&v.to_le_bytes());
        }
        for v in bbox {
            rec.extend_from_slice(&v.to_le_bytes());
        }

        file_data.extend_from_slice(&rec);

        let doc = parse_product(&file_data).unwrap();
        assert_eq!(doc.total_instances, 1);
        assert_eq!(doc.placed_instances, 1);
        assert_eq!(doc.identity_instances, 0);
        assert_eq!(doc.instances[0].placement_status, PlacementStatus::Placed);
        assert_eq!(
            doc.instances[0].transform,
            Some([12.5, -34.0, 56.78, 1.0, 0.0, 0.0, 0.0])
        );
        assert_eq!(doc.instances[0].object_tag, Some(42));
        assert!(doc.warnings.is_empty());
    }

    #[test]
    fn parse_synthetic_product_root_plus_sequential() {
        let mut payload = Vec::new();
        push_pool_item(&mut payload, "ASMPRODUCT");
        push_pool_item(&mut payload, "RootAssy");

        // Instance 1: PartA PartA.1 _Position
        push_pool_item(&mut payload, "_PartNumber");
        push_pool_item(&mut payload, "PartA");
        push_pool_item(&mut payload, "_InstanceName");
        push_pool_item(&mut payload, "PartA.1");
        push_pool_item(&mut payload, "_Position");
        push_pool_item(&mut payload, "PRDREP");

        // Instance 2: PartB PartB.1 _Position
        push_pool_item(&mut payload, "_PartNumber");
        push_pool_item(&mut payload, "PartB");
        push_pool_item(&mut payload, "_InstanceName");
        push_pool_item(&mut payload, "PartB.1");
        push_pool_item(&mut payload, "_Position");
        push_pool_item(&mut payload, "PRDREP");

        let mut file_data = build_synthetic_product_data(&payload);

        // Build 3 records (1 root group + 2 instance records)
        let magic = transforms::RECORD_129B_MAGIC_R20;
        let sep = transforms::SEPARATOR_BYTE;

        for (i, t_x) in [0.0f64, 100.0, 200.0].iter().enumerate() {
            let mut rec = Vec::with_capacity(129);
            rec.extend_from_slice(&magic);
            rec.extend_from_slice(&(100u32 + i as u32).to_le_bytes());
            rec.push(sep);
            for v in [*t_x, 0.0f64, 0.0f64] {
                rec.extend_from_slice(&v.to_le_bytes());
            }
            for v in [1.0f64, 0.0f64, 0.0f64, 0.0f64] {
                rec.extend_from_slice(&v.to_le_bytes());
            }
            for v in [0.0f64; 4] {
                rec.extend_from_slice(&v.to_le_bytes());
            }
            for v in [0.0f64; 4] {
                rec.extend_from_slice(&v.to_le_bytes());
            }
            file_data.extend_from_slice(&rec);
        }

        let doc = parse_product(&file_data).unwrap();
        assert_eq!(doc.total_instances, 2);
        assert_eq!(doc.placed_instances, 2);
        assert_eq!(doc.identity_instances, 0);

        // Instance 0 matches record 1 (skip root record 0)
        assert_eq!(doc.instances[0].instance_name, "PartA.1");
        assert_eq!(
            doc.instances[0].transform,
            Some([100.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0])
        );
        assert_eq!(doc.instances[0].object_tag, Some(101));

        // Instance 1 matches record 2
        assert_eq!(doc.instances[1].instance_name, "PartB.1");
        assert_eq!(
            doc.instances[1].transform,
            Some([200.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0])
        );
        assert_eq!(doc.instances[1].object_tag, Some(102));
        assert!(doc.warnings.is_empty());
    }

    #[test]
    fn parse_synthetic_product_undecodable_mesh_anti_masking() {
        let mut payload = Vec::new();
        push_pool_item(&mut payload, "ASMPRODUCT");
        push_pool_item(&mut payload, "MeshAssy");

        // 2 instances with _Position
        for name in &["PartA.1", "PartB.1"] {
            push_pool_item(&mut payload, "_PartNumber");
            push_pool_item(&mut payload, "PartX");
            push_pool_item(&mut payload, "_InstanceName");
            push_pool_item(&mut payload, name);
            push_pool_item(&mut payload, "_Position");
            push_pool_item(&mut payload, "PRDREP");
        }

        let mut file_data = build_synthetic_product_data(&payload);

        // Append 5 records (mismatch with 2 instances -> undecodable constraint mesh)
        let magic = transforms::RECORD_129B_MAGIC_R20;
        let sep = transforms::SEPARATOR_BYTE;
        for i in 0..5 {
            let mut rec = Vec::with_capacity(129);
            rec.extend_from_slice(&magic);
            rec.extend_from_slice(&(i as u32).to_le_bytes());
            rec.push(sep);
            for v in [i as f64, 0.0f64, 0.0f64] {
                rec.extend_from_slice(&v.to_le_bytes());
            }
            for v in [1.0f64, 0.0f64, 0.0f64, 0.0f64] {
                rec.extend_from_slice(&v.to_le_bytes());
            }
            for v in [0.0f64; 4] {
                rec.extend_from_slice(&v.to_le_bytes());
            }
            for v in [0.0f64; 4] {
                rec.extend_from_slice(&v.to_le_bytes());
            }
            file_data.extend_from_slice(&rec);
        }

        let doc = parse_product(&file_data).unwrap();
        assert_eq!(doc.total_instances, 2);
        assert_eq!(doc.placed_instances, 0);
        assert_eq!(doc.identity_instances, 0);

        // Strict Anti-Masking: transform must be None, never origin identity!
        for inst in &doc.instances {
            assert_eq!(inst.placement_status, PlacementStatus::Undecodable);
            assert!(inst.transform.is_none());
        }
        assert!(
            doc.warnings
                .iter()
                .any(|w| w.class == "undecodable-placement")
        );
    }

    #[test]
    fn parse_corpus_coso_root_plus_sequential_if_available() {
        let manifest_dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR"));
        let path = manifest_dir
            .join("../corpus/Apoloo13/ASE_III/diseño_3d/prueba_tensor_cable/coso.CATProduct");
        if !path.exists() {
            return;
        }
        let data = std::fs::read(&path).expect("read coso");
        let doc = parse_product(&data).unwrap();
        assert_eq!(doc.pool_form, "framed");
        assert_eq!(doc.total_instances, 7);
        assert_eq!(doc.placed_instances, 7);
        assert_eq!(doc.identity_instances, 0);
        for inst in &doc.instances {
            assert_eq!(inst.placement_status, PlacementStatus::Placed);
            assert!(inst.transform.is_some());
        }
        assert!(
            !doc.warnings
                .iter()
                .any(|w| w.class == "undecodable-placement")
        );
    }

    #[test]
    fn parse_corpus_servo_sts3215_if_available() {
        let manifest_dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR"));
        let path = manifest_dir.join(
            "../corpus/Apoloo13/ASE_III/diseño_3d/lengua/lengua_v2/servo_STS3215_03a v1.CATProduct",
        );
        if !path.exists() {
            return;
        }
        let data = std::fs::read(&path).expect("read servo");
        let doc = parse_product(&data).unwrap();
        assert_eq!(doc.pool_form, "framed");
        assert_eq!(doc.total_instances, 3);
        assert_eq!(doc.placed_instances, 2);
        // The first 2 instances are placed parts with valid transforms
        assert_eq!(doc.instances[0].placement_status, PlacementStatus::Placed);
        assert!(doc.instances[0].transform.is_some());
        assert_eq!(doc.instances[1].placement_status, PlacementStatus::Placed);
        assert!(doc.instances[1].transform.is_some());
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

        // Anti-masking invariant: complex constraint mesh instances must be Undecodable with transform: None
        assert!(
            doc.warnings
                .iter()
                .any(|w| w.class == "undecodable-placement")
        );
        for inst in &doc.instances {
            if inst.has_position_attr {
                assert_eq!(inst.placement_status, PlacementStatus::Undecodable);
                assert!(inst.transform.is_none());
            }
        }
    }
}
