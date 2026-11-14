//! The WASM boundary (spec §2.3 of ``docs/specs/phase5-viewer-
//! spec.md``) — the two whole-buffer entries the viewer drives, no
//! streaming. This module is compiled **only** for
//! ``wasm32-unknown-unknown`` (the ``cdylib`` the viewer ships, §5);
//! the native ``rlib`` the Fidelity harness drives has no JS runtime
//! and never links it. The decode itself is the SAME code the harness
//! proved natively (§2.1: one crate, two targets) — this file is the
//! seam, assembly only: **it performs no decode arithmetic** (the V0
//! lint policy, ``lib.rs``; no ``suboptimal_flops`` allow here).
//!
//! # The two entries (§2.3)
//!
//! - ``decode_inspect(bytes) -> JsValue`` — the schema-v1 inspect
//!   document (what the metadata panel renders), via
//!   :fn:`crate::inspect::build_inspect_document` (the shared document
//!   builder; field order single-sourced with the native CLI seam,
//!   §2.4).
//! - ``decode_export(bytes) -> { summary, vertices: Float32Array,
//!   triangles: Uint32Array, curves: Array<Float32Array> }`` — the
//!   export-summary object, the pool in walk order, the decoded
//!   triangles, and the decoded polyline loops (the curve-entry point
//!   sequences) for the overlay. ``curves`` is **additive and NOT part
//!   of the Fidelity definition** (§2.3; V3 carried it on
//!   ``CompositeDecode`` for exactly this handoff) — the summary and
//!   the PLY never contain it.
//!
//! # Failure: the classified error object
//!
//! Both entries return ``Result<JsValue, JsValue>``; the ``Err`` value
//! is the classified error object ``{ error_class, detail }`` itself,
//! thrown to the caller by the generated glue (a JS exception whose
//! payload IS that object). The vocabulary is the exact Python
//! error-class vocabulary (§2.3): the geometry classes come from
//! :mod:`crate::geometry::errors` at the twin's raise sites; the
//! inspect seam's L1-reachable refusals classify as ``crash`` (the
//! Python side's own classification for every exception raised while
//! producing the inspect output — ``runner.py::_classify_file``; see
//! the ``inspect`` module header). One boundary-specific arm: an EMPTY
//! buffer on ``decode_export`` — the twin's ``mmap`` refuses an empty
//! file with an unclassified ``ValueError`` (the native CLI mirrors it
//! with a panic, exiting the 0/1 seam contract) — is classified
//! ``crash`` here instead, because the viewer must display a failure,
//! never a blank screen (§5) and a wasm trap is not a classified
//! error. The ``detail`` prose is never compared byte-wise (§3.2) and
//! cites the violated claim.
//!
//! # The typed arrays (§2.3) and the one narrowing
//!
//! ``vertices``/``triangles`` are real typed arrays (the viewer
//! consumes them directly — a JSON round-trip per mesh is waste; the
//! JSON contract lives where it is measured, the native CLI, §2.3).
//! The boundary's ONLY numeric operation is the exact narrowing
//! ``f64 -> f32`` of the pool coordinates: the decode widened every
//! coordinate once at load, f32 -> f64 (§2.2's widening point,
//! ``pool.rs``), so the f64 holds the f32 value exactly and ``as f32``
//! recovers it bit-exactly — no rounding decision is made here. The
//! summary crosses as a ``JsValue`` via ``serde_wasm_bindgen`` (the
//! §2.3-prescribed dependency; no string intermediate).
//!
//! # Dependencies added at V4 (§2.3; recorded on ticket #43)
//!
//! ``serde_wasm_bindgen`` — the §2.3-prescribed summary conversion;
//! ``js-sys`` — the typed-array constructors the §2.3 shapes require
//! (same wasm-bindgen family, same release cadence). No other crates.

use wasm_bindgen::prelude::*;

use js_sys::{Array, Float32Array, Object, Uint32Array};

use crate::geometry::errors::IO_ERROR;
use crate::geometry::export::export_data;
// The "crash" class: the Python side's own classification for every
// exception raised while producing an output (``runner.py::
// _classify_file``); the inspect module owns the constant with the
// citation. ``decode_export``'s one reachable arm is the twin's
// unclassified empty-file ValueError — same runner classification.
use crate::inspect::{INSPECT_CRASH, build_inspect_document};
use serde_wasm_bindgen::to_value;

/// The classified error object ``{ error_class, detail }`` (§2.3's
/// exact shape) as a ``JsValue``. Built by property assignment — a
/// two-string-field object cannot fail to construct, so the failure
/// path has no failure path of its own.
fn classified_error(error_class: &str, detail: &str) -> JsValue {
    let error = Object::new();
    js_sys::Reflect::set(
        &error,
        &JsValue::from_str("error_class"),
        &JsValue::from_str(error_class),
    )
    .expect("a fresh Object accepts a string-keyed property");
    js_sys::Reflect::set(
        &error,
        &JsValue::from_str("detail"),
        &JsValue::from_str(detail),
    )
    .expect("a fresh Object accepts a string-keyed property");
    error.into()
}

/// The §2.3 inspect entry: the schema-v1 document for the whole buffer,
/// or the classified error thrown (see the module header). Whole-buffer
/// only — the decode is one pass over the in-memory buffer, the shape
/// the Fidelity harness compares (§2.3's rationale).
#[wasm_bindgen]
pub fn decode_inspect(bytes: &[u8]) -> Result<JsValue, JsValue> {
    match build_inspect_document(bytes) {
        Ok(document) => to_value(&document).map_err(|err| {
            classified_error(
                INSPECT_CRASH,
                &format!("cannot serialize the inspect document: {err}"),
            )
        }),
        Err(refusal) => Err(classified_error(refusal.error_class, &refusal.detail)),
    }
}

/// The §2.3 export entry: the summary plus the typed-array mesh and the
/// additive curve loops, or the classified error thrown. The PLY has no
/// meaning at this boundary — the viewer consumes the arrays directly.
#[wasm_bindgen]
pub fn decode_export(bytes: &[u8]) -> Result<JsValue, JsValue> {
    if bytes.is_empty() {
        // The twin's mmap refuses an empty file with an unclassified
        // ValueError (the native CLI mirrors it with a panic); here it
        // classifies as the crash class so the viewer displays it
        // (module header).
        return Err(classified_error(
            INSPECT_CRASH,
            "empty buffer: the twin's mmap refuses an empty file \
             (unclassified ValueError; the crash class)",
        ));
    }
    let outcome =
        export_data(bytes).map_err(|exc| classified_error(exc.error_class, &exc.detail))?;
    let summary = to_value(&outcome.summary).map_err(|err| {
        classified_error(IO_ERROR, &format!("cannot serialize the summary: {err}"))
    })?;

    // The exact f64 -> f32 narrowing (module header): the decode's f64s
    // hold widened f32s, so `as f32` is bit-exact recovery, not a
    // rounding decision (§2.2).
    let mut xyz = Vec::with_capacity(outcome.vertices.len() * 3);
    for (x, y, z) in &outcome.vertices {
        xyz.push(*x as f32);
        xyz.push(*y as f32);
        xyz.push(*z as f32);
    }
    let vertices = Float32Array::from(xyz.as_slice());

    let mut abc = Vec::with_capacity(outcome.triangles.len() * 3);
    for (a, b, c) in &outcome.triangles {
        abc.push(*a);
        abc.push(*b);
        abc.push(*c);
    }
    let triangles = Uint32Array::from(abc.as_slice());

    // The additive curve exposure (§2.3): every dropped curve-entry
    // loop's pre-weld point sequence, in encounter order. Empty on the
    // non-composite path (the clean path has no curve-entry loops).
    let curves = Array::new();
    for curve in &outcome.curves {
        let mut pts = Vec::with_capacity(curve.len() * 3);
        for (x, y, z) in curve {
            pts.push(*x as f32);
            pts.push(*y as f32);
            pts.push(*z as f32);
        }
        curves.push(&Float32Array::from(pts.as_slice()).into());
    }

    let result = Object::new();
    js_sys::Reflect::set(&result, &JsValue::from_str("summary"), &summary)
        .expect("a fresh Object accepts a string-keyed property");
    js_sys::Reflect::set(&result, &JsValue::from_str("vertices"), &vertices.into())
        .expect("a fresh Object accepts a string-keyed property");
    js_sys::Reflect::set(&result, &JsValue::from_str("triangles"), &triangles.into())
        .expect("a fresh Object accepts a string-keyed property");
    js_sys::Reflect::set(&result, &JsValue::from_str("curves"), &curves.into())
        .expect("a fresh Object accepts a string-keyed property");
    Ok(result.into())
}
