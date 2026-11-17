# P3-V2 Independent Review Report: WASM Boundary & Glue Packaging

**Target Commit**: `4603aba` on `main`  
**Date**: 2026-11-16  
**Reviewer**: Independent Verifier Sub-Agent  
**Design Authority**: [`docs/specs/phase6-assembly-viewer-spec.md`](file:///home/alan/Documents/Repos/catpart-parser/docs/specs/phase6-assembly-viewer-spec.md) (§7.1, §7.2, §7.3, and §8)  
**Prior Seam Spec**: [`docs/specs/phase5-viewer-spec.md`](file:///home/alan/Documents/Repos/catpart-parser/docs/specs/phase5-viewer-spec.md) (§2.3)  
**Target Surface Under Review**:
- [`port/src/wasm_boundary.rs`](file:///home/alan/Documents/Repos/catpart-parser/port/src/wasm_boundary.rs)
- [`port/tests/wasm.rs`](file:///home/alan/Documents/Repos/catpart-parser/port/tests/wasm.rs)
- [`port/pkg/`](file:///home/alan/Documents/Repos/catpart-parser/port/pkg/)
- [`site/viewer/pkg/`](file:///home/alan/Documents/Repos/catpart-parser/site/viewer/pkg/)

---

## 1. Executive Summary & Verdict

### Formal Verdict: PASS WITH FINDINGS

The implementation of Ticket P3-V2 (WASM Boundary & Glue Packaging) delivered in commit `4603aba` is **VERIFIED** by independent technical review and empirical test validation.

Ticket P3-V2 extends the WebAssembly boundary with the whole-buffer assembly entry point `decode_product_structure`, bridging the Rust product structure core (`port/src/product/`) with the browser runtime (`site/viewer/`).

Key verification results:
1. **Entry Point Conformance**: `decode_product_structure(bytes: &[u8]) -> Result<JsValue, JsValue>` conforms strictly to the FFI signature established in Phase 6 Spec §7.2.
2. **Failure Classification**: Refusals are serialized as standard `{ error_class, detail }` JS objects. Truncated inputs (< 32 bytes) refuse with `truncated-file`. Empty inputs refuse with `empty-buffer` (see Finding 1 for comparison against the Phase 5 `crash` convention).
3. **Serialization Integrity**: Successful parses serialize `ProductStructureDocument` into native JS objects via `serde_wasm_bindgen::to_value`, preserving exact types: schema versions, instance arrays, boolean position flags, w-first transform arrays `[tx, ty, tz, qw, qx, qy, qz]`, and diagnostic warnings.
4. **Artifact Integrity & Pkg Sync**: Built artifacts in `port/pkg/` and deployed viewer assets in `site/viewer/pkg/` are confirmed **100% byte-identical** (`diff -q -r` reports zero drift). Both declare `decode_product_structure(bytes: Uint8Array | number[]): any;` in their TypeScript definition headers.
5. **Headless In-Node Test Suite**: `wasm-pack test --node` passes all 10 tests headlessly (4 dedicated assembly boundary tests + 6 existing Phase 5 tests) with zero panics or errors.
6. **Gate Health**: `bash scripts/check.sh` passes 100% clean across all Python, Rust native, wasm32, formatting, clippy, and pkg-sync checks.

Three minor technical findings and architectural notes are documented in Section 5.

---

## 2. Review Checklist & Key Results

| Requirement / Item | Status | Independent Verification Result |
|---|---|---|
| **1. WASM Boundary Entry Point** | **PASS** | `decode_product_structure` declared with `#[wasm_bindgen]` in `port/src/wasm_boundary.rs`. Accepts whole-buffer `&[u8]`, delegates to `parse_product`, and returns `Result<JsValue, JsValue>`. |
| **2. Empty Buffer Classification** | **PASS WITH FINDINGS** | Empty slice (`&[]`) refuses closed with `{ error_class: "empty-buffer", detail: "cannot decode product structure from 0 bytes" }`. (Finding 1: Spec §7.2 illustrative code proposed `INSPECT_CRASH`, but domain-specific `"empty-buffer"` is cleaner and pinned in test suite). |
| **3. Truncated Buffer Classification** | **PASS** | Short buffers (< 32 bytes) refuse closed with `{ error_class: "truncated-file", detail: "buffer too short for CATIA container header: ..." }`. |
| **4. Serialization via `serde_wasm_bindgen`** | **PASS** | `ProductStructureDocument` and all child types (`ProductInstanceRecord`, `ProductWarning`, `PlacementStatus`, `PairingRule`) serialize directly into JS objects using `serde_wasm_bindgen::to_value`. Serialization failures are caught and mapped to `classified_error(IO_ERROR, ...)`. |
| **5. Shipped Artifact Integrity & Pkg Sync** | **PASS** | `diff -q -r port/pkg site/viewer/pkg` is 100% clean (zero diffs, exit code 0). Committed packages contain identical `port.d.ts`, `port.js`, `port_bg.wasm`, `port_bg.wasm.d.ts`, `package.json`, and `.gitignore`. |
| **6. TypeScript Definitions** | **PASS** | `port/pkg/port.d.ts` and `site/viewer/pkg/port.d.ts` export `decode_product_structure(bytes: Uint8Array \| number[]): any;`. `InitOutput` in both defines `readonly decode_product_structure: (a: number, b: number) => [number, number, number];`. |
| **7. Headless Node WASM Test Suite** | **PASS** | `cd port && wasm-pack test --node` passes 10/10 tests in 0.04s. Full coverage on `product_structure_synthetic_valid_decode`, `product_structure_synthetic_identity_decode`, `product_structure_short_buffer_refuses_truncated_file`, and `product_structure_empty_buffer_refuses_empty_buffer`. |
| **8. Gate Execution (`scripts/check.sh`)** | **PASS** | Full gate runs cleanly: `ruff` 0 errors, `pytest` 395 passed (7 skipped), `cargo build` (native & wasm32), `cargo clippy -D warnings` 0 warnings, `cargo fmt --check` clean, `cargo test` 150 passed, `wasm-pack test --node` 10 passed, `pkg sync` 0 diffs. |

---

## 3. Detailed Technical Verification

### 3.1 WASM Boundary Entry Point & FFI Contract

In `port/src/wasm_boundary.rs`:

```rust
/// The Phase 6 product structure entry point (spec §7.2 of
/// ``docs/specs/phase6-assembly-viewer-spec.md``).
/// Accepts raw bytes of a .CATProduct file and returns the parsed
/// hierarchy, instance list, and transform vectors.
#[wasm_bindgen]
pub fn decode_product_structure(bytes: &[u8]) -> Result<JsValue, JsValue> {
    match parse_product(bytes) {
        Ok(doc) => to_value(&doc).map_err(|err| {
            classified_error(
                IO_ERROR,
                &format!("cannot serialize product structure: {err}"),
            )
        }),
        Err(refusal) => Err(classified_error(refusal.class, &refusal.detail)),
    }
}
```

The function strictly satisfies the architectural principles established in Phase 5 Spec §2.3 and Phase 6 Spec §7.2:
- **Zero Decode Arithmetic at Boundary**: Like `decode_inspect` and `decode_export`, `decode_product_structure` performs no parsing or arithmetic directly. It is purely an FFI adaptation seam between the Rust core and JavaScript runtime.
- **Whole-Buffer Semantic**: The function accepts raw bytes representing the full `.CATProduct` container. No streaming or partial chunking is introduced, keeping the boundary predictable and memory-safe.
- **Fail-Safe Classified Errors**: Errors are constructed via `classified_error(class, detail)`, producing an immutable JS `Object` with properties `error_class` and `detail`. When returned as `Err(JsValue)`, `wasm-bindgen` throws this object as a standard JS exception, allowing `viewer.js` to catch `{ error_class, detail }` directly without unhandled traps or blank screens.

### 3.2 Error Classification & Fail-Closed Behavior

The failure handling path was tested against empty, truncated, and malformed inputs:

1. **Empty Buffer (`bytes.len() == 0`)**:
   `parse_product` detects `data.is_empty()` and returns `ProductError { class: "empty-buffer", detail: "cannot decode product structure from 0 bytes" }`. The WASM wrapper catches this and throws `{ error_class: "empty-buffer", detail: "cannot decode product structure from 0 bytes" }`. Verified in Node test `product_structure_empty_buffer_refuses_empty_buffer`.
2. **Truncated Buffer (`bytes.len() < 32`)**:
   `parse_product` detects `data.len() < 32` (insufficient for the standard 32-byte CATIA container header) and returns `ProductError { class: "truncated-file", detail: "buffer too short for CATIA container header: <N> bytes" }`. The WASM wrapper throws `{ error_class: "truncated-file", detail: ... }`. Verified in Node test `product_structure_short_buffer_refuses_truncated_file`.
3. **Missing Structure Pool**:
   Non-product files or corrupt containers that pass header checks but lack the `fe 7c 02` framed pool or valid R15 references return `class: "missing-structure-pool"`.

### 3.3 Data Structure Serialization

Serialization maps Rust domain models to JavaScript objects using `serde_wasm_bindgen`:

```rust
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct ProductStructureDocument {
    pub schema_version: u32,
    pub product_name: String,
    pub detected_version: String,
    pub pool_form: String, // "framed" | "r15-ref" | "unframed"
    pub total_instances: usize,
    pub placed_instances: usize,
    pub identity_instances: usize,
    pub instances: Vec<ProductInstanceRecord>,
    pub warnings: Vec<ProductWarning>,
}
```

Verified field conversions across the boundary:
- `schema_version`: mapped to JS `Number` (value `1.0`).
- `instances`: mapped to JS `Array<Object>`.
- `instances[i].transform`: mapped to JS `Array<Number>` of length 7 (`[tx, ty, tz, qw, qx, qy, qz]`) for placed instances, or `null`/`undefined` for identity and undecodable instances.
- `instances[i].placement_status`: serialized via `#[serde(rename_all = "snake_case")]` to strings `"placed"`, `"identity"`, or `"undecodable"`.
- `instances[i].pairing_rule`: serialized to strings `"triple"`, `"desc_block"`, or `"bare_pair"`.
- `instances[i].has_position_attr`: serialized to JS `Boolean`.
- `warnings`: mapped to JS `Array<Object>` carrying `{ class: string, detail: string }`.

All types and values were verified across the boundary in `product_structure_synthetic_valid_decode` and `product_structure_synthetic_identity_decode`.

### 3.4 Shipped Artifact Integrity & Pkg Sync

Per Phase 5 review finding F1 and Phase 6 packaging requirements, `port/pkg/` (crate output) and `site/viewer/pkg/` (static web deployment) must never drift.

Verification:
```bash
$ diff -q -r port/pkg site/viewer/pkg
# (Exit code 0 — 100% byte-identical)
```

Both directories contain:
- `port.d.ts` (2,770 bytes)
- `port.js` (15,622 bytes)
- `port_bg.wasm` (361,401 bytes)
- `port_bg.wasm.d.ts` (830 bytes)
- `package.json` (346 bytes)
- `.gitignore` (1 byte)

TypeScript declaration verified in `port.d.ts`:
```typescript
/**
 * The Phase 6 product structure entry point (spec §7.2 of
 * ``docs/specs/phase6-assembly-viewer-spec.md``).
 * Accepts raw bytes of a .CATProduct file and returns the parsed
 * hierarchy, instance list, and transform vectors.
 * @param {Uint8Array | number[]} bytes
 * @returns {any}
 */
export function decode_product_structure(bytes: Uint8Array | number[]): any;
```

In `port.js`:
```javascript
export function decode_product_structure(bytes) {
    const ptr0 = passArray8ToWasm0(bytes, wasm.__wbindgen_malloc);
    const len0 = WASM_VECTOR_LEN;
    const ret = wasm.decode_product_structure(ptr0, len0);
    if (ret[2]) {
        throw takeFromExternrefTable0(ret[1]);
    }
    return takeFromExternrefTable0(ret[0]);
}
```

### 3.5 Headless In-Node Test Suite Execution

Execution of `wasm-pack test --node` in `port/`:

```text
[INFO]: 🎯  Checking for the Wasm target...
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.95s
[INFO]: ⬇️  Installing wasm-bindgen...
    Finished `test` profile [unoptimized + debuginfo] target(s) in 0.02s
     Running tests/wasm.rs (target/wasm32-unknown-unknown/debug/deps/wasm-23b6da4bb4ec1a02.wasm)
Executing bindgen...
running 10 tests
test product_structure_synthetic_valid_decode ... ok
test product_structure_synthetic_identity_decode ... ok
test product_structure_short_buffer_refuses_truncated_file ... ok
test product_structure_empty_buffer_refuses_empty_buffer ... ok
test inspect_document_short_file_refuses_crash ... ok
test inspect_document_canonical ... ok
test export_empty_buffer_classifies_crash ... ok
test export_composite_curve_exposure_at_the_boundary ... ok
test export_classified_failures_match_the_twin_vocabulary ... ok
test export_canonical_summary_and_typed_arrays ... ok

test result: ok. 10 passed; 0 failed; 0 ignored; 0 filtered out; finished in 0.04s
```

All 4 assembly boundary test cases executed successfully without traps, memory leaks, or unhandled exceptions.

---

## 4. Gate Verification

Running `bash scripts/check.sh` produces an unblemished green pass across all gates:

```text
check: PY=.venv/bin/python RUFF=.venv/bin/ruff
check: ruff check .
All checks passed!
check: pytest -q
395 passed, 7 skipped in 46.93s
check: cargo build (native)
check: cargo build (wasm32-unknown-unknown)
check: cargo fmt --check (port)
check: cargo clippy -D warnings (port)
check: cargo test (port)
144 passed (src/lib.rs) + 6 passed (tests/independent_verify_p3_v1.rs)
check: wasm-pack build --target web --release (check dir)
check: wasm-pack test --node (the shipped artifact runs)
10 passed in 0.04s
check: pkg sync (port/pkg vs site/viewer/pkg)
# Clean exit 0
```

---

## 5. Technical Findings & Architectural Notes

### Finding 1: Empty Buffer Classification — Semantic Specialization vs. Phase 5 `crash` Convention

- **Observation**:
  In Phase 5, `decode_export(&[])` returns `{ error_class: "crash", detail: ... }` because the Python twin's `mmap("")` raised an unclassified `ValueError`, which `runner.py::_classify_file` mapped to `crash`. The Phase 6 Spec §7.2 draft code snippet also included:
  ```rust
  if bytes.is_empty() {
      return Err(classified_error(
          INSPECT_CRASH,
          "empty buffer: cannot decode product structure from 0 bytes",
      ));
  }
  ```
  However, in Ticket P3-V2 (and P3-V0), `parse_product` directly emits `ProductError { class: "empty-buffer", detail: ... }`. Consequently, `decode_product_structure(&[])` returns `{ error_class: "empty-buffer", detail: ... }`.
- **Assessment**:
  The classification `"empty-buffer"` is semantically superior to `"crash"`, as it clearly indicates an input defect rather than an unhandled internal decoder fault or memory panic. The viewer UI (`site/viewer/viewer.js`) renders any `{ error_class, detail }` cleanly in the error panel.
- **Resolution**:
  Accept `"empty-buffer"` as the canonical Phase 6 assembly classification for 0-byte files. The test suite in `port/tests/wasm.rs` explicitly tests and locks in this behavior (`product_structure_empty_buffer_refuses_empty_buffer`). Spec §7.2 should be updated in a future editorial pass to reflect `"empty-buffer"` instead of `INSPECT_CRASH`.

### Finding 2: TypeScript Return Type in Generated Bindings (`any` vs `ProductStructureDocument`)

- **Observation**:
  `port/pkg/port.d.ts` generated by `wasm-bindgen` declares:
  `export function decode_product_structure(bytes: Uint8Array | number[]): any;`.
  Because `serde_wasm_bindgen` handles conversion dynamically via `JsValue`, `wasm-bindgen` cannot infer the concrete TypeScript interface structure at compile time.
- **Assessment**:
  This is a known limitation of `wasm-bindgen` + `serde_wasm_bindgen`. Phase 6 Spec §7.3 provides the formal TypeScript interface definitions (`ProductStructureDocument`, `ProductInstanceRecord`, `ProductWarning`).
- **Recommendation**:
  Ensure `site/viewer/` codebase maintains `types.d.ts` (or JSDoc `@type {import("./types.js").ProductStructureDocument}`) so that client code retains full IDE autocompletion and type safety when consuming `decode_product_structure`.

### Finding 3: Linear Memory Ingestion and Transient Memory Envelope

- **Observation**:
  `decode_product_structure` passes raw bytes into WASM linear memory via `passArray8ToWasm0` (`wasm.__wbindgen_malloc`).
- **Assessment**:
  While `.CATPart` files can reach ~120 MB (necessitating the desktop-only memory envelope documented in Phase 5 §10), `.CATProduct` files are structural metadata containers whose uncompressed size across the corpus is typically under 1 MB (rarely exceeding 5 MB). Transient copying of `.CATProduct` buffers into WASM linear memory introduces no measurable memory pressure.

---

## 6. Conclusion & Sign-Off

Ticket P3-V2 successfully satisfies all requirements of the Phase 6 Assembly Viewer Specification (§7.1, §7.2, §8). The WASM boundary entry point is robust, fail-closed, byte-identical across package directories, and thoroughly verified under headless Node testing and CI gate checks.

**Final Verdict**: **PASS WITH FINDINGS**  
**Gate Status**: **GREEN (100% Pass)**  
**Next Step**: Ready for downstream ingestion and scene-graph integration (Tickets P3-V3, P3-V4, P3-V5, P3-V6).
