//! Independent verification test suite for Ticket P3-V1:
//! Rust Transform Record Decoder & Instance Binding Engine.
//!
//! Verifies:
//! 1. 129-byte modern transform record decoder (primary/alt magic, separator byte 0x80, bounds, gates).
//! 2. 81-byte connector point filter (filtering as constraint geometry).
//! 3. R15 inline matrix stream decoder (8d 81 marker, run-length floats, SO(3) orthonormality, quat w-first).
//! 4. Instance binding engine & Anti-masking invariant (Clause 3 of P4 Assembly Bar).
//! 5. Verification on actual corpus files (coso, lengua, servo, Dictor Product1).

use port::product::binding::{BindingMode, IDENTITY_TRANSFORM, PlacementStatus, compute_bindings};
use port::product::pairing::{PairingRule, ProductInstanceRecord, is_constraint_name};
use port::product::parse_product;
use port::product::transforms::{
    RECORD_81B_LEN, RECORD_81B_MAGIC_R20, RECORD_129B_MAGIC_R20, RECORD_129B_MAGIC_R20_ALT,
    SEPARATOR_BYTE, TransformRecord, decode_129b_record, is_81b_connector_record,
    is_proper_rotation, mat3_to_quat, parse_run_length_floats, scan_modern_transform_records,
};
use std::path::Path;

#[test]
fn verify_requirement_1_129b_modern_record_decoder() {
    // 1a. Primary and Alt magic
    assert!(port::product::transforms::is_129b_magic(
        &RECORD_129B_MAGIC_R20
    ));
    assert!(port::product::transforms::is_129b_magic(
        &RECORD_129B_MAGIC_R20_ALT
    ));
    assert!(!port::product::transforms::is_129b_magic(&[0, 0, 0, 0]));

    // 1b. Correct layout:
    // Offset 0..4: magic
    // Offset 4..8: tag ID
    // Offset 8: separator byte 0x80
    // Offset 9..33: translation [tx, ty, tz] (3 * 8 bytes)
    // Offset 33..65: unit quat [qw, qx, qy, qz] (4 * 8 bytes)
    // Offset 65..97: flags (4 * 8 bytes)
    // Offset 97..129: bounding box (4 * 8 bytes)
    let mut buf = vec![0u8; 129];
    buf[0..4].copy_from_slice(&RECORD_129B_MAGIC_R20);
    buf[4..8].copy_from_slice(&1234u32.to_le_bytes());
    buf[8] = SEPARATOR_BYTE; // 0x80

    let t: [f64; 3] = [150.0, -250.0, 350.0];
    let q: [f64; 4] = [1.0, 0.0, 0.0, 0.0]; // identity w-first
    let flags: [f64; 4] = [1.0, 0.0, 0.0, 0.0];
    let bbox: [f64; 4] = [-100.0, 100.0, -100.0, 100.0];

    for (i, &v) in t.iter().enumerate() {
        buf[9 + i * 8..9 + (i + 1) * 8].copy_from_slice(&v.to_le_bytes());
    }
    for (i, &v) in q.iter().enumerate() {
        buf[33 + i * 8..33 + (i + 1) * 8].copy_from_slice(&v.to_le_bytes());
    }
    for (i, &v) in flags.iter().enumerate() {
        buf[65 + i * 8..65 + (i + 1) * 8].copy_from_slice(&v.to_le_bytes());
    }
    for (i, &v) in bbox.iter().enumerate() {
        buf[97 + i * 8..97 + (i + 1) * 8].copy_from_slice(&v.to_le_bytes());
    }

    let rec = decode_129b_record(&buf).expect("valid 129b record must decode");
    assert_eq!(rec.tag_id, 1234);
    assert_eq!(rec.translation, [150.0, -250.0, 350.0]);
    assert_eq!(rec.quaternion, [1.0, 0.0, 0.0, 0.0]);
    assert!(rec.is_unit_quaternion(1e-4));

    // 1c. Separator violation: if byte at offset 8 is not 0x80, must fail closed
    let mut bad_sep = buf.clone();
    bad_sep[8] = 0x50; // wrong separator
    assert!(decode_129b_record(&bad_sep).is_none());

    // 1d. Quaternion gate violation: norm2 = 2.0 (directional sentinel)
    let mut bad_quat = buf.clone();
    let q_sentinel = [0.0f64, 0.0, 1.0, 1.0]; // norm2 = 2.0
    for (i, v) in q_sentinel.iter().enumerate() {
        bad_quat[33 + i * 8..33 + (i + 1) * 8].copy_from_slice(&v.to_le_bytes());
    }
    assert!(decode_129b_record(&bad_quat).is_none());

    // 1e. Translation bounds violation (> 1e7 mm)
    let mut bad_trans = buf.clone();
    let t_huge = [1e8f64, 0.0, 0.0];
    for (i, v) in t_huge.iter().enumerate() {
        bad_trans[9 + i * 8..9 + (i + 1) * 8].copy_from_slice(&v.to_le_bytes());
    }
    assert!(decode_129b_record(&bad_trans).is_none());
}

#[test]
fn verify_requirement_2_81b_connector_point_filter() {
    let mut rec81 = vec![0u8; 81];
    rec81[0..4].copy_from_slice(&RECORD_81B_MAGIC_R20);
    rec81[4..8].copy_from_slice(&55u32.to_le_bytes());
    rec81[8] = SEPARATOR_BYTE; // 0x80
    for i in 0..9 {
        let v = (i as f64) * 10.0;
        rec81[9 + i * 8..9 + (i + 1) * 8].copy_from_slice(&v.to_le_bytes());
    }

    assert!(is_81b_connector_record(&rec81));
    assert_eq!(rec81.len(), RECORD_81B_LEN);

    // Filter verification: 81-byte records in stream are skipped and never treated as instance transforms
    let mut stream = Vec::new();
    stream.extend_from_slice(&rec81);
    let scanned = scan_modern_transform_records(&stream);
    assert!(
        scanned.is_empty(),
        "81-byte connector point must not be treated as a transform record"
    );
}

#[test]
fn verify_requirement_3_r15_inline_matrix_stream_decoder() {
    // 3a. Marker pattern 8d 81
    assert_eq!(port::product::transforms::R15_MATRIX_MARKER, [0x8d, 0x81]);

    // 3b. Run-length float extraction
    // e7 -> 1.0, e8 -> 0.0, e9 -> -1.0, e6 + 8 bytes -> arbitrary double
    let mut stream = vec![0xE7, 0xE8, 0xE9];
    stream.push(0xE6);
    stream.extend_from_slice(&123.456f64.to_le_bytes());
    let (floats, consumed) = parse_run_length_floats(&stream, 4).expect("parse 4 floats");
    assert_eq!(floats, vec![1.0, 0.0, -1.0, 123.456]);
    assert_eq!(consumed, 1 + 1 + 1 + 9);

    // 3c. Orthonormality check for 3x3 rotation matrix (det(R) == +1, R R^T == I)
    let rot_90_x: [[f64; 3]; 3] = [[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]];
    assert!(is_proper_rotation(&rot_90_x, 1e-4));

    let not_proper: [[f64; 3]; 3] = [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, -1.0], // det = -1.0 (reflection)
    ];
    assert!(!is_proper_rotation(&not_proper, 1e-4));

    // 3d. Matrix-to-quaternion conversion (w-first)
    // 90 deg around X: qw = cos(45 deg) = sqrt(2)/2, qx = sin(45 deg) = sqrt(2)/2, qy = 0, qz = 0
    let q_90_x = mat3_to_quat(&rot_90_x);
    let half_sqrt2 = std::f64::consts::FRAC_1_SQRT_2;
    assert!((q_90_x[0] - half_sqrt2).abs() < 1e-6);
    assert!((q_90_x[1] - half_sqrt2).abs() < 1e-6);
    assert!(q_90_x[2].abs() < 1e-6);
    assert!(q_90_x[3].abs() < 1e-6);
}

#[test]
fn verify_requirement_4_instance_binding_and_anti_masking() {
    let instances = vec![
        ProductInstanceRecord {
            instance_name: "Inst1.1".to_string(),
            part_number: "Part1".to_string(),
            pairing_rule: PairingRule::Triple,
            has_position_attr: true,
            placement_status: PlacementStatus::Placed,
            transform: None,
            object_tag: None,
            classification_detail: None,
        },
        ProductInstanceRecord {
            instance_name: "Inst2.1".to_string(),
            part_number: "Part2".to_string(),
            pairing_rule: PairingRule::Triple,
            has_position_attr: true,
            placement_status: PlacementStatus::Placed,
            transform: None,
            object_tag: None,
            classification_detail: None,
        },
    ];

    // Case 1: Sequential 1:1 (2 instances, 2 records)
    let recs_2 = vec![
        TransformRecord::from_placement([1.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0], 10),
        TransformRecord::from_placement([2.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0], 20),
    ];
    let (bindings, mode) = compute_bindings(&instances, &recs_2, true);
    assert_eq!(mode, BindingMode::Sequential1to1);
    assert_eq!(bindings[0].placement_status, PlacementStatus::Placed);
    assert_eq!(
        bindings[0].transform,
        Some([1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0])
    );

    // Case 2: Root plus sequential (2 instances, 3 records)
    let recs_3 = vec![
        TransformRecord::from_placement([0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0], 0),
        TransformRecord::from_placement([10.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0], 10),
        TransformRecord::from_placement([20.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0], 20),
    ];
    let (bindings, mode) = compute_bindings(&instances, &recs_3, true);
    assert_eq!(mode, BindingMode::RootPlusSequential);
    assert_eq!(bindings[0].placement_status, PlacementStatus::Placed);
    assert_eq!(
        bindings[0].transform,
        Some([10.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0])
    );

    // Case 3: Default Identity (2 instances, 0 records, pool has _Position)
    let (bindings, mode) = compute_bindings(&instances, &[], true);
    assert_eq!(mode, BindingMode::IdentityDefault);
    assert_eq!(bindings[0].placement_status, PlacementStatus::Placed);
    assert_eq!(bindings[0].transform, Some(IDENTITY_TRANSFORM));

    // Case 4: ANTI-MASKING INVARIANT TEST
    // 2 instances, but 5 records (mismatch -> undecodable constraint mesh)
    let recs_5 = vec![
        TransformRecord::from_placement([1.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0], 1),
        TransformRecord::from_placement([2.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0], 2),
        TransformRecord::from_placement([3.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0], 3),
        TransformRecord::from_placement([4.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0], 4),
        TransformRecord::from_placement([5.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0], 5),
    ];
    let (bindings, mode) = compute_bindings(&instances, &recs_5, true);
    assert_eq!(mode, BindingMode::Undecodable);
    for b in &bindings {
        assert_eq!(b.placement_status, PlacementStatus::Undecodable);
        // CRITICAL ANTI-MASKING CHECK: transform MUST BE NONE!
        assert!(
            b.transform.is_none(),
            "ANTI-MASKING VIOLATION: undecodable transform was masked to Some!"
        );
        assert!(b.classification_detail.is_some());
    }
}

#[test]
fn verify_requirement_5_corpus_samples() {
    let manifest_dir = Path::new(env!("CARGO_MANIFEST_DIR"));

    // 5a. Dictor Product1
    let dictor_p = manifest_dir.join("../corpus/Dictor/HaneulMyo/model/Product1.CATProduct");
    if dictor_p.exists() {
        let bytes = std::fs::read(&dictor_p).expect("read dictor");
        let doc = parse_product(&bytes).expect("parse dictor");
        assert_eq!(doc.pool_form, "framed");
        assert_eq!(doc.total_instances, 3);
        // Ensure constraint names never leak into instances
        for inst in &doc.instances {
            assert!(!is_constraint_name(&inst.instance_name));
        }
    }

    // 5b. Apoloo13 coso.CATProduct
    let coso_p = manifest_dir
        .join("../corpus/Apoloo13/ASE_III/diseño_3d/prueba_tensor_cable/coso.CATProduct");
    if coso_p.exists() {
        let bytes = std::fs::read(&coso_p).expect("read coso");
        let doc = parse_product(&bytes).expect("parse coso");
        assert_eq!(doc.pool_form, "framed");
        assert_eq!(doc.total_instances, 7);
        assert_eq!(doc.placed_instances, 7);
        for inst in &doc.instances {
            assert_eq!(inst.placement_status, PlacementStatus::Placed);
            assert!(inst.transform.is_some());
        }
    }

    // 5c. Apoloo13 lengua.CATProduct (lengua_v2)
    let lengua_p = manifest_dir
        .join("../corpus/Apoloo13/ASE_III/diseño_3d/lengua/lengua_v2/lengua.CATProduct");
    if lengua_p.exists() {
        let bytes = std::fs::read(&lengua_p).expect("read lengua");
        let doc = parse_product(&bytes).expect("parse lengua");
        assert_eq!(doc.pool_form, "framed");
        assert!(doc.total_instances >= 30);
        // Strict Anti-Masking: 112 unresolvable constraints in mesh -> Undecodable with transform: None
        assert!(
            doc.warnings
                .iter()
                .any(|w| w.class == "undecodable-placement")
        );
        for inst in &doc.instances {
            assert!(!is_constraint_name(&inst.instance_name));
            if inst.has_position_attr {
                assert_eq!(inst.placement_status, PlacementStatus::Undecodable);
                assert!(
                    inst.transform.is_none(),
                    "Anti-masking violation on lengua!"
                );
            }
        }
    }

    // 5d. Apoloo13 lengua.CATProduct (lengua_v1)
    let lengua_v1_p = manifest_dir
        .join("../corpus/Apoloo13/ASE_III/diseño_3d/lengua/lengua_v1/lengua.CATProduct");
    if lengua_v1_p.exists() {
        let bytes = std::fs::read(&lengua_v1_p).expect("read lengua v1");
        let doc = parse_product(&bytes).expect("parse lengua v1");
        assert_eq!(doc.pool_form, "framed");
        assert_eq!(doc.total_instances, 2);
        for inst in &doc.instances {
            assert!(!is_constraint_name(&inst.instance_name));
            if inst.has_position_attr {
                assert_eq!(inst.placement_status, PlacementStatus::Undecodable);
                assert!(inst.transform.is_none());
            }
        }
    }

    // 5e. Apoloo13 servo_STS3215_03a v1.CATProduct
    let servo_p = manifest_dir.join(
        "../corpus/Apoloo13/ASE_III/diseño_3d/lengua/lengua_v2/servo_STS3215_03a v1.CATProduct",
    );
    if servo_p.exists() {
        let bytes = std::fs::read(&servo_p).expect("read servo");
        let doc = parse_product(&bytes).expect("parse servo");
        assert_eq!(doc.pool_form, "framed");
        assert_eq!(doc.total_instances, 3);
        assert_eq!(doc.placed_instances, 2);
        assert_eq!(doc.instances[0].placement_status, PlacementStatus::Placed);
        assert!(doc.instances[0].transform.is_some());
        assert_eq!(doc.instances[1].placement_status, PlacementStatus::Placed);
        assert!(doc.instances[1].transform.is_some());
    }
}

#[test]
fn verify_scale_corpus_anti_masking_and_soundness() {
    let manifest_dir = Path::new(env!("CARGO_MANIFEST_DIR"));
    let corpus_root = manifest_dir.join("../corpus");
    if !corpus_root.exists() {
        return;
    }

    // Find all CATProduct files
    let mut files = Vec::new();
    fn visit_dirs(dir: &Path, files: &mut Vec<std::path::PathBuf>) {
        if let Ok(entries) = std::fs::read_dir(dir) {
            for entry in entries.flatten() {
                let path = entry.path();
                if path.is_dir() {
                    visit_dirs(&path, files);
                } else if path.extension().and_then(|s| s.to_str()) == Some("CATProduct") {
                    files.push(path);
                }
            }
        }
    }
    visit_dirs(&corpus_root, &mut files);

    assert!(!files.is_empty(), "corpus should contain CATProduct files");

    let mut total_files = 0;
    let mut framed_files = 0;
    let mut total_instances = 0;
    let mut total_placed = 0;
    let mut total_identity = 0;
    let mut total_undecodable = 0;

    for file in &files {
        let Ok(data) = std::fs::read(file) else {
            continue;
        };
        let Ok(doc) = parse_product(&data) else {
            continue;
        };

        total_files += 1;
        if doc.pool_form == "framed" {
            framed_files += 1;
        }
        total_instances += doc.total_instances;
        total_placed += doc.placed_instances;
        total_identity += doc.identity_instances;

        for inst in &doc.instances {
            // Invariant 1: No constraint names in instances
            assert!(
                !is_constraint_name(&inst.instance_name),
                "Constraint '{}' leaked into instances in {:?}",
                inst.instance_name,
                file
            );

            match inst.placement_status {
                PlacementStatus::Placed => {
                    // Invariant 2: Placed instances MUST have Some(transform) with unit quat
                    let t = inst.transform.expect("placed instance must have transform");
                    let q_norm2 = t[3] * t[3] + t[4] * t[4] + t[5] * t[5] + t[6] * t[6];
                    assert!(
                        (q_norm2 - 1.0).abs() <= 1e-3,
                        "Quaternion must be unit norm: got {} in {:?}",
                        q_norm2,
                        file
                    );
                }
                PlacementStatus::Identity => {
                    // Invariant 3: Identity instances MUST have origin identity
                    assert_eq!(
                        inst.transform,
                        Some(IDENTITY_TRANSFORM),
                        "Identity instance must have IDENTITY_TRANSFORM in {:?}",
                        file
                    );
                }
                PlacementStatus::Undecodable => {
                    total_undecodable += 1;
                    // Invariant 4: STRICT ANTI-MASKING: transform MUST BE NONE! NEVER ORIGIN IDENTITY!
                    assert!(
                        inst.transform.is_none(),
                        "ANTI-MASKING VIOLATION: undecodable instance had transform {:?} in {:?}",
                        inst.transform,
                        file
                    );
                }
            }
        }
    }

    assert!(total_files > 0);
    assert!(framed_files > 0);
    assert!(total_instances > 0);
    // Print statistics for verifier audit
    println!(
        "Audited {} CATProduct files ({} framed): {} instances ({} placed, {} identity, {} undecodable)",
        total_files, framed_files, total_instances, total_placed, total_identity, total_undecodable
    );
}
