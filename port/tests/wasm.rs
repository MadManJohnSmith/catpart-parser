//! The wasm-bindgen Node tests (spec §7 step 6 of
//! ``docs/specs/phase5-viewer-spec.md``): CI *runs* the shipped WASM
//! artifact headlessly — not merely builds it — catching
//! wasm-linkage-only bugs the native runs cannot see. The subset is the
//! §7 shape: the canonical store + corrupted variants (one per
//! classified class) + the composite curve-entry shape (the §2.3 curve
//! exposure at the boundary) + the short-file inspect refusal.
//!
//! The fixture bytes are the GENERATED source arrays in
//! ``tests/fixtures/mod.rs`` (``scripts/gen_wasm_fixture_data.py``; the
//! binary guard forbids committed fixture binaries and the Node
//! harness has no fs) — the same generator the fixture-mode Fidelity
//! harness drives, so the subset is the real A2 bytes, and
//! ``tests/test_wasm_fixture_data.py`` (the Python gate) pins the
//! committed arrays byte-identical to a fresh generation.
//!
//! The expected classes below are the twin's raise-site classes (the
//! same rows the fixture-mode harness compares against Python —
//! captured 2026-11-14 from ``catpart-export`` on the identical bytes).
//! Whole-file ``#![cfg(target_arch = "wasm32")]``: the native test
//! binary compiles empty (no wasm runtime natively); ``wasm-pack test
//! --node`` compiles and runs these under Node.

#![cfg(target_arch = "wasm32")]

mod fixtures;

use wasm_bindgen::prelude::*;
use wasm_bindgen_test::wasm_bindgen_test;

use js_sys::{Array, Float32Array, Object, Reflect, Uint32Array};
use port::wasm_boundary::{decode_export, decode_inspect};
use wasm_bindgen::JsCast;

/// The classified error's ``error_class`` field off a thrown value.
fn error_class(err: &JsValue) -> String {
    Reflect::get(err, &JsValue::from_str("error_class"))
        .expect("the classified error object carries error_class")
        .as_string()
        .expect("error_class is a string")
}

/// The classified error's ``detail`` field (non-empty house convention).
fn error_detail(err: &JsValue) -> String {
    Reflect::get(err, &JsValue::from_str("detail"))
        .expect("the classified error object carries detail")
        .as_string()
        .expect("detail is a string")
}

/// A summary field by name as f64 (counts are numbers across the
/// boundary).
fn summary_f64(summary: &JsValue, field: &str) -> f64 {
    Reflect::get(summary, &JsValue::from_str(field))
        .expect("the summary carries the field")
        .as_f64()
        .expect("the field is a number")
}

#[wasm_bindgen_test]
fn inspect_document_canonical() {
    let doc = decode_inspect(fixtures::GEOMETRY).expect("the canonical fixture inspects");
    assert_eq!(
        Reflect::get(&doc, &JsValue::from_str("schema_version"))
            .unwrap()
            .as_f64(),
        Some(1.0)
    );
    assert_eq!(
        Reflect::get(&doc, &JsValue::from_str("kind"))
            .unwrap()
            .as_string(),
        Some("part".into())
    );
    assert_eq!(
        Reflect::get(&doc, &JsValue::from_str("detected_version"))
            .unwrap()
            .as_string(),
        Some("V5R21SP0HF0".into())
    );
    let containers = Reflect::get(&doc, &JsValue::from_str("containers"))
        .unwrap()
        .dyn_into::<Array>()
        .unwrap();
    assert_eq!(containers.length(), 3);
    let trailer = Reflect::get(&doc, &JsValue::from_str("trailer")).unwrap();
    assert!(!trailer.is_null() && !trailer.is_undefined());
}

#[wasm_bindgen_test]
fn inspect_document_short_file_refuses_crash() {
    // The A2 table pins short-file -> the crash class on both sides
    // (the Python side's own classification for its ValueError).
    let err = decode_inspect(fixtures::SHORT_FILE).unwrap_err();
    assert_eq!(error_class(&err), "crash");
    assert!(
        error_detail(&err).contains("header needs 32 bytes, got 16"),
        "the detail cites the violated claim"
    );
}

#[wasm_bindgen_test]
fn export_canonical_summary_and_typed_arrays() {
    // Captured from catpart-export on the identical bytes (2026-11-14):
    // v 8 / t 12, closed manifold, bbox [0,0,0]-[20,100,60].
    let result = decode_export(fixtures::GEOMETRY).expect("the canonical fixture exports");
    let summary = Reflect::get(&result, &JsValue::from_str("summary")).unwrap();
    assert_eq!(summary_f64(&summary, "vertex_count"), 8.0);
    assert_eq!(summary_f64(&summary, "triangle_count"), 12.0);
    assert_eq!(summary_f64(&summary, "degenerate_triangle_count"), 0.0);
    let mesh = Reflect::get(&summary, &JsValue::from_str("mesh")).unwrap();
    assert_eq!(
        Reflect::get(&mesh, &JsValue::from_str("manifold"))
            .unwrap()
            .as_bool(),
        Some(true)
    );
    assert_eq!(
        Reflect::get(&mesh, &JsValue::from_str("closed"))
            .unwrap()
            .as_bool(),
        Some(true)
    );
    let bbox_max = Reflect::get(&summary, &JsValue::from_str("bounding_box"))
        .unwrap()
        .dyn_into::<Object>()
        .unwrap();
    let max = Reflect::get(&bbox_max, &JsValue::from_str("max"))
        .unwrap()
        .dyn_into::<Array>()
        .unwrap();
    assert_eq!(max.get(0).as_f64(), Some(20.0));
    assert_eq!(max.get(1).as_f64(), Some(100.0));
    assert_eq!(max.get(2).as_f64(), Some(60.0));

    // The typed arrays (§2.3): Float32Array xyz in walk order, Uint32Array
    // triangle soup — real typed arrays, not boxed JS arrays.
    let vertices = Reflect::get(&result, &JsValue::from_str("vertices"))
        .unwrap()
        .dyn_into::<Float32Array>()
        .expect("vertices is a Float32Array");
    assert_eq!(vertices.length(), 24); // 8 vertices x 3
    let triangles = Reflect::get(&result, &JsValue::from_str("triangles"))
        .unwrap()
        .dyn_into::<Uint32Array>()
        .expect("triangles is a Uint32Array");
    assert_eq!(triangles.length(), 36); // 12 triangles x 3
    // The canonical store has no curve-entry loops: the additive
    // §2.3 curves ride empty.
    let curves = Reflect::get(&result, &JsValue::from_str("curves"))
        .unwrap()
        .dyn_into::<Array>()
        .unwrap();
    assert_eq!(curves.length(), 0);
}

#[wasm_bindgen_test]
fn export_composite_curve_exposure_at_the_boundary() {
    // The composite decode's dropped curve-entry loop crosses as one
    // pre-weld polyline loop (§2.3, additive — never in the summary).
    let result = decode_export(fixtures::COMPOSITE_CURVE_ENTRIES)
        .expect("the curve-entry composite fixture exports");
    let summary = Reflect::get(&result, &JsValue::from_str("summary")).unwrap();
    assert_eq!(summary_f64(&summary, "triangle_count"), 12.0);
    let composite = Reflect::get(&summary, &JsValue::from_str("composite")).unwrap();
    assert_eq!(
        Reflect::get(&composite, &JsValue::from_str("loops_curve_entry"))
            .unwrap()
            .as_f64(),
        Some(1.0),
        "one loop still dropped (the summary block the Fidelity harness compares)"
    );
    let curves = Reflect::get(&result, &JsValue::from_str("curves"))
        .unwrap()
        .dyn_into::<Array>()
        .unwrap();
    assert_eq!(curves.length(), 1, "one dropped loop -> one polyline");
    let curve = curves
        .get(0)
        .dyn_into::<Float32Array>()
        .expect("each curve is a Float32Array");
    assert_eq!(curve.length() % 3, 0, "xyz triples");
    assert!(curve.length() >= 6, "a polyline has at least two points");
}

#[wasm_bindgen_test]
fn export_classified_failures_match_the_twin_vocabulary() {
    // One corrupted variant per classified class — the exact kebab
    // strings the twin raises on these bytes (fixture-mode harness
    // rows, §3.2).
    let cases: [(&[u8], &str); 4] = [
        (fixtures::BAD_NESTED_MAGIC, "missing-geometry-store"),
        (fixtures::TRUNCATED_POOL, "malformed-pool-group"),
        (fixtures::NAN_COORDS, "malformed-pool-vertex"),
        (fixtures::OUT_OF_RANGE_REFS, "undecoded-variant"),
    ];
    for (bytes, expected) in cases {
        let err = decode_export(bytes).unwrap_err();
        assert_eq!(error_class(&err), expected, "class matches the twin");
        assert!(!error_detail(&err).is_empty(), "detail is non-empty");
    }
    // The store-less short file: the twin's export seam raises
    // missing-geometry-store on it (no CATStdCont block, nothing to
    // probe) — NOT an invented crash class.
    let err = decode_export(fixtures::SHORT_FILE).unwrap_err();
    assert_eq!(error_class(&err), "missing-geometry-store");
}

#[wasm_bindgen_test]
fn export_empty_buffer_classifies_crash() {
    // The twin's mmap refuses an empty file with an unclassified
    // ValueError; the boundary classifies it (the runner's crash
    // class) so the viewer displays it — never a blank screen, never a
    // wasm trap (the module header).
    let err = decode_export(&[]).unwrap_err();
    assert_eq!(error_class(&err), "crash");
    assert!(!error_detail(&err).is_empty());
}
