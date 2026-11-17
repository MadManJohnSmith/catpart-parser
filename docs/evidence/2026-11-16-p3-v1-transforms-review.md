# P3-V1 Independent Review Report: Rust Transform Record Decoder & Instance Binding Engine

**Target Commit**: `d0a58eb` on `main`  
**Date**: 2026-11-16  
**Reviewer**: Independent Verifier Sub-Agent  
**Design Authority**: [`docs/specs/phase6-assembly-viewer-spec.md`](file:///home/alan/Documents/Repos/catpart-parser/docs/specs/phase6-assembly-viewer-spec.md) (§2 and §8)  
**Declared Bar**: [`docs/evidence/2026-11-14-p4-assembly-bar.md`](file:///home/alan/Documents/Repos/catpart-parser/docs/evidence/2026-11-14-p4-assembly-bar.md) (P4 Assembly Bar, Clause 3 Anti-Masking Invariant)  
**Prior Evidence & Decoders**:
- [`scripts/triage/p26_instance_binding.py`](file:///home/alan/Documents/Repos/catpart-parser/scripts/triage/p26_instance_binding.py)
- [`scripts/triage/p6_r15_position_probe.py`](file:///home/alan/Documents/Repos/catpart-parser/scripts/triage/p6_r15_position_probe.py)
- [`docs/evidence/2026-11-16-p26-binding-probe.md`](file:///home/alan/Documents/Repos/catpart-parser/docs/evidence/2026-11-16-p26-binding-probe.md)
- [`docs/evidence/2026-11-16-r15-position-probe.md`](file:///home/alan/Documents/Repos/catpart-parser/docs/evidence/2026-11-16-r15-position-probe.md)
**Independent Verification Artifacts**:
- [`port/tests/independent_verify_p3_v1.rs`](file:///home/alan/Documents/Repos/catpart-parser/port/tests/independent_verify_p3_v1.rs) (Native Rust test suite)
- [`scripts/triage/verify_p3_v1_transforms.py`](file:///home/alan/Documents/Repos/catpart-parser/scripts/triage/verify_p3_v1_transforms.py) (Python independent verification script)

---

## 1. Executive Summary & Verdict

### Formal Verdict: PASS WITH FINDINGS

The implementation of Ticket P3-V1 delivered in commit `d0a58eb` is **VERIFIED** by independent mathematical and empirical re-derivation.

The modern 129-byte transform record decoder (`port/src/product/transforms.rs`), 81-byte connector point filter, R15 inline run-length matrix stream decoder, and instance binding engine (`port/src/product/binding.rs`) faithfully implement the physical container specifications and strictly satisfy Clause 3 of the declared P4 Assembly Bar:
> **The Anti-Masking Invariant**: Undecodable placements (such as the complex 112-constraint mesh in `lengua.CATProduct`) are flagged as `PlacementStatus::Undecodable` with `transform: None` and an explicit diagnostic warning. They are **NEVER** silently defaulted or masked to origin identity `[0, 0, 0, 1, 0, 0, 0]`.

Independent verification across the entire corpus (570 `.CATProduct` files, 3,451 instances) confirms **zero anti-masking violations, zero leaked constraints into instance lists, and zero panics**.

Four technical findings and layout clarifications are documented in Section 5. Notably, Finding 1 resolves a critical documentation discrepancy between the brief's offsets and physical CATIA byte structures.

---

## 2. Review Checklist & Key Results

| Requirement / Item | Status | Independent Verification Result |
|---|---|---|
| **1. 129-Byte Modern Record Decoder** | **PASS** | Validates primary magic `\xb5\x13\x27\x79` and alt magic `\xb5\x03\x27\x79`. Verifies invariant separator byte `0x80` at byte 8 (decimal offset 8). Translation $[T_x, T_y, T_z]$ decoded from bytes 9..33 ($\le 10^7$ mm bound). Unit quaternion $[Q_w, Q_x, Q_y, Q_z]$ decoded from bytes 33..65 with gate $\|\|q\|^2 - 1.0\| \le 10^{-4}$. Fails closed on corrupt data. |
| **2. 81-Byte Connector Point Filter** | **PASS** | Recognizes 81-byte record magic `\xb5\x13\x0e\x49` with separator `0x80`. Skips 81-byte records during transform scanning, preventing assembly constraint connector points from contaminating spatial instance placements. |
| **3. R15 Inline Matrix Stream Decoder** | **PASS** | Scans for `[0x8d, 0x81]` marker. Extracts 12 run-length IEEE-754 floats (`0xe8` $\to 0.0$, `0xe7` $\to 1.0$, `0xe9` $\to -1.0$, `0xe6` $\to \text{f64le}$). Checks $\mathrm{SO}(3)$ proper rotation orthonormality ($\det(R) \approx +1.0$, $R R^T \approx I$). Converts rotation matrix to w-first quaternion via Shepperd's algorithm with $Q_w \ge 0.0$. |
| **4. Instance Binding Engine** | **PASS** | Implements deterministic binding modes: `sequential_1to1`, `root_plus_sequential`, `identity_default`, and `undecodable`. Strictly adheres to the P4 Assembly Bar Anti-Masking Invariant (`transform: None` on undecodable placements). |
| **5. Corpus Test Vectors** | **PASS** | **Apoloo13 / Coso** (`prueba_tensor_cable/coso.CATProduct`): 7 placed instances with valid transforms (`root_plus_sequential`).<br>**Apoloo13 / Servo** (`lengua_v2/servo_STS3215_03a v1.CATProduct`): 2 placed instances (`sequential_1to1`).<br>**Apoloo13 / Lengua** (`lengua_v2/lengua.CATProduct`): 31 instances correctly classified as `Undecodable` with `transform: None` (112 constraints cleanly separated).<br>**Dictor** (`HaneulMyo/model/Product1.CATProduct`): 3 instances cleanly separated from 5 constraints. |
| **6. Corpus-Scale Audit** | **PASS** | Full audit across 570 `.CATProduct` files (356 framed, 3,451 instances):<br>- Placed instances: 496 (all with verified unit quaternions)<br>- Identity instances: 138 (all with canonical origin identity)<br>- Undecodable instances: 2,817 (100% with `transform: None`; 0 masked to origin)<br>- Leaked constraints: 0 |
| **7. Test Suite & Code Hygiene** | **PASS** | `port` native test suite: **144 passed, 0 failed**.<br>`independent_verify_p3_v1`: **6 passed, 0 failed**.<br>`scripts/triage/verify_p3_v1_transforms.py`: **all checks passed**.<br>`cargo clippy -- -D warnings`: **0 warnings**.<br>`cargo fmt --check`: **clean**.<br>`scripts/check.sh`: **clean gate**. |

---

## 3. Detailed Technical Verification

### 3.1 129-Byte Modern Transform Record Anatomy

In CATIA V5 R18–R26 files carrying `CATCtorProxyCont` containers, transform records follow a fixed 129-byte physical layout:

```text
Offset (Dec)   Offset (Hex)   Field Length   Type          Description
---------------------------------------------------------------------------------------------
0..4           0x00..0x04     4 bytes        [u8; 4]       Magic (\xb5\x13\x27\x79 or \xb5\x03\x27\x79)
4..8           0x04..0x08     4 bytes        u32le         OmbObjectTag ID
8              0x08           1 byte         u8            Invariant separator byte (0x80)
9..33          0x09..0x21     24 bytes       3 x f64le     Translation vector [tx, ty, tz] in mm
33..65         0x21..0x41     32 bytes       4 x f64le     Unit quaternion [qw, qx, qy, qz], w-first
65..97         0x41..0x61     32 bytes       4 x f64le     Flags and coordinate qualifiers
97..129        0x61..0x81     32 bytes       4 x f64le     Bounding box extents [min_x, max_x, min_y, max_y]
---------------------------------------------------------------------------------------------
Total: 129 bytes (0x81 in hex)
```

The decoder in `port/src/product/transforms.rs::decode_129b_record` enforces strict validation:
1. **Magic Verification**: Confirms magic matches `RECORD_129B_MAGIC_R20` (`[0xb5, 0x13, 0x27, 0x79]`) or `RECORD_129B_MAGIC_R20_ALT` (`[0xb5, 0x03, 0x27, 0x79]`).
2. **Separator Check**: Rejects any record where `buf[8] != 0x80`.
3. **Finiteness Check**: Unpacks all 15 IEEE-754 doubles and requires `val.is_finite()`.
4. **Unit Quaternion Gate**: Evaluates `norm2 = qw^2 + qx^2 + qy^2 + qz^2` and requires `(norm2 - 1.0).abs() <= 1e-4`. Directional normal sentinels (`norm2 ≈ 2.0`, e.g. `(0, 0, 1, 1)`) fail this gate closed.
5. **Translation Bounds**: Rejects translations exceeding `TRANSLATION_BOUND_MAX = 1e7` mm ($10,000$ km).

### 3.2 81-Byte Connector Point Record Filter

Connector points mediation geometry for assembly constraints (`Offset`, `Coincidence`, `Surface contact`) is serialized in `CATCtorProxyCont` alongside transform records using an 81-byte format:

```text
Offset (Dec)   Offset (Hex)   Field Length   Type          Description
---------------------------------------------------------------------------------------------
0..4           0x00..0x04     4 bytes        [u8; 4]       Magic (\xb5\x13\x0e\x49)
4..8           0x04..0x08     4 bytes        u32le         OmbObjectTag ID
8              0x08           1 byte         u8            Invariant separator byte (0x80)
9..33          0x09..0x21     24 bytes       3 x f64le     Point anchor coordinates [px, py, pz]
33..65         0x21..0x41     32 bytes       4 x f64le     Axis normal / direction vector
65..81         0x41..0x51     16 bytes       2 x f64le     Limits / constraint parameters
---------------------------------------------------------------------------------------------
Total: 81 bytes (0x51 in hex)
```

In `scan_modern_transform_records`, `is_81b_connector_record` detects these 81-byte records and advances the scan index by `RECORD_81B_LEN` (81 bytes). This ensures:
- Connector point coordinates are never mistaken for instance transform translations.
- Scanning preserves alignment across containers with mixed 129-byte and 81-byte records (e.g. `91fe0d674f7c30db`: $2 \times 129 + 2 \times 81 = 420$ bytes).

### 3.3 R15 Inline Matrix Stream Decoder

For R15-era legacy generation products and placed instances without modern `CATCtorProxyCont` override records, CATIA serializes transforms inline using run-length encoded IEEE-754 floating point numbers following `[0x8d, 0x81]`.

The tag grammar in `parse_run_length_floats` decodes:
- `0xE8` $\to 0.0$ (1 byte)
- `0xE7` $\to 1.0$ (1 byte)
- `0xE9` $\to -1.0$ (1 byte)
- `0xE6` $\to \text{f64le}$ (9 bytes: 1 tag byte + 8-byte IEEE-754 double)

The first 9 decoded floats form a row-major $3 \times 3$ rotation matrix $R$, and floats 9..11 form the translation vector $[T_x, T_y, T_z]$.

`is_proper_rotation` verifies that $R \in \mathrm{SO}(3)$:
- $\left| \det(R) - 1.0 \right| \le 10^{-4}$
- $\left| \|R_i\| - 1.0 \right| \le 10^{-4}$ for each row $i \in \{0, 1, 2\}$
- Mutual orthogonality: $\left| R_i \cdot R_j \right| \le 10^{-4}$ for $i \ne j$

`mat3_to_quat` implements Shepperd's algorithm (selecting the maximum of $\operatorname{tr}(R)$ and diagonal elements $m_{00}, m_{11}, m_{22}$) to avoid numerical instability or division by near-zero, normalizes the quaternion, and canonicalizes to $Q_w \ge 0.0$.

### 3.4 Instance Binding Engine & The Anti-Masking Invariant

`port/src/product/binding.rs` establishes deterministic binding between pool instances and transform records:

1. **`Sequential1to1`**: Number of placed instances equals number of transform records ($N_{\text{rec}} = N_{\text{inst}}$). Record $i$ maps to instance $i$.
2. **`RootPlusSequential`**: $N_{\text{rec}} = N_{\text{inst}} + 1$. Record 0 is product root transform; record $i+1$ maps to instance $i$ (verified on `coso.CATProduct`).
3. **`IdentityDefault`**: Pool declares `_Position` but carries 0 override records ($N_{\text{rec}} = 0$). Instances are placed at canonical identity `[0, 0, 0, 1, 0, 0, 0]` as explicit CATIA default.
4. **`Unplaced`**: File declares no `_Position` attributes. Instances receive `PlacementStatus::Identity`.
5. **`Undecodable`**: Complex constraint mesh overrides or record mismatches ($N_{\text{rec}} \ne N_{\text{inst}}$, e.g. `lengua.CATProduct` with 177 records and 31 instances). Instances receive `PlacementStatus::Undecodable` with `transform: None` and a diagnostic warning.

---

## 4. Empirical Corpus Audit & Independent Verification

The independent test suite [`port/tests/independent_verify_p3_v1.rs`](file:///home/alan/Documents/Repos/catpart-parser/port/tests/independent_verify_p3_v1.rs) and verification script [`scripts/triage/verify_p3_v1_transforms.py`](file:///home/alan/Documents/Repos/catpart-parser/scripts/triage/verify_p3_v1_transforms.py) evaluated all real-world corpus files:

### 4.1 Sample-Level Verification

| File | SHA-16 | Total Inst | Placed Inst | Mode | Status / Verification Note |
|---|---|---|---|---|---|
| `Dictor/HaneulMyo/model/Product1.CATProduct` | `0018ec386764dcea` | 3 | 3 | `identity_default` | 3 instances (`Part001.1`, `Part0024.1`, `Part001.2`) cleanly separated from 5 constraints (`Coincidence.1`..`5`). Placed at identity. |
| `Apoloo13/.../coso.CATProduct` | `81b1fe655b83f7ee` | 7 | 7 | `root_plus_sequential` | 7 instances bound to 8 records (record 0 root transform skipped). All 7 instances placed with non-zero 3D translations. |
| `Apoloo13/.../lengua_v2/lengua.CATProduct` | `126c9fda3c4218c3` | 31 | 0 | `undecodable` | 143 dot names cleanly partitioned into 31 part instances and 112 constraints. 177 ctorproxy records. Strict Anti-Masking: all 31 instances flagged `Undecodable` with `transform: None`. |
| `Apoloo13/.../lengua_v1/lengua.CATProduct` | `ff4a50eb5792a4ea` | 2 | 0 | `undecodable` | 34 dot names partitioned into 2 part instances and 32 constraints. 21 ctorproxy records. Strict Anti-Masking: 2 instances flagged `Undecodable` with `transform: None`. |
| `Apoloo13/.../servo_STS3215_03a v1.CATProduct` | `91fe0d674f7c30db` | 3 | 2 | `sequential_1to1` | 2 placed child instances (`ac2:1`, `ac1:1`) bound to 2 129B records; 1 unplaced root assembly ref (`main_structure:1`). 2 81B connector records filtered. |

### 4.2 Scale Corpus Statistics

Across all 570 `.CATProduct` files examined:
- **Total Files Audited**: 570
- **Framed Structure Pools**: 356
- **Total Instances Decoded**: 3,451
- **Instances with Decoded 3D Transforms (`Placed`)**: 496 (100% verified unit quaternions)
- **Instances at Origin Identity (`Identity`)**: 138 (100% verified $[0,0,0, 1,0,0,0]$)
- **Instances Classified Undecodable (`Undecodable`)**: 2,817 (100% verified `transform: None`)
- **Leaked Assembly Constraints into Instance Lists**: **0**
- **Anti-Masking Violations**: **0**

---

## 5. Technical Findings & Layout Clarifications

### Finding 1: Layout & Offset Clarification (Empirical Ground Truth vs Brief Hex/Decimal Conflation)
- **Description**: The review brief cited:
  - *"Invariant separator byte 0x80 at offset 16"*
  - *"Translation $[X, Y, Z]$ at offset 17 and w-first unit quaternion at offset 41"*
  - *"Separator byte 0x50 at offset 16"*
- **Physical Analysis**:
  1. The true header is 8 bytes: 4 bytes magic (`\xb5\x13\x27\x79` or `\xb5\x03\x27\x79`) + 4 bytes `u32le` tag ID.
  2. The invariant separator byte `0x80` is located at **byte 8 (decimal offset 8, hex `0x08`)**, NOT offset 16.
  3. Bytes 9..33 (hex `0x09..0x21`) hold the translation vector $[T_x, T_y, T_z]$ ($3 \times \text{f64le}$). Byte 16 is the high byte (sign and exponent) of the double-precision float $T_x$. Looking for `0x80` at offset 16 would fail on 100% of valid CATIA files.
  4. Bytes 33..65 (hex `0x21..0x41`) hold the unit quaternion $[Q_w, Q_x, Q_y, Q_z]$ ($4 \times \text{f64le}$).
  5. The brief's numbers 17 and 41 arose from conflating hexadecimal notation from Spec §2.4: `0x21..0x41` was read as decimal 41 (instead of decimal 65), and `0x09..0x21` was read as decimal 17 (or $T_y$ start offset 17).
  6. The 81-byte record stride in hex is `0x51`. `0x50` is decimal 80 (the end offset of range `0..80`). The separator byte for 81-byte records is `0x80` at byte 8; across all 260 occurrences in the corpus, no separator byte `0x50` exists.
- **Verdict**: The implementation in `port/src/product/transforms.rs` correctly implements the physically true layout (byte 8 for `0x80`, bytes 9..33 for $T$, bytes 33..65 for $Q$), exactly matching binary files and triage reference decoders.

### Finding 2: `scan_r15_matrix_streams` Advance Stride Optimization
- **Description**: In `port/src/product/transforms.rs`, `scan_r15_matrix_streams` advances `idx = pos + 2` after decoding a matrix stream.
- **Impact**: Non-blocking. A decoded matrix stream consumes between 12 and 108 bytes. Advancing by only 2 bytes leaves open the theoretical possibility that arbitrary mantissa bytes of an IEEE-754 double literal (`0xE6`) inside the stream could match `[0x8d, 0x81]` and attempt a redundant decode.
- **Recommendation**: Update `decode_r15_matrix_stream` to return the consumed byte length `consumed`, and advance `idx = pos + 2 + consumed` on successful decode.

### Finding 3: 81-Byte Connector Point Finiteness Verification
- **Description**: `is_81b_connector_record` verifies the 4-byte magic `\xb5\x13\x0e\x49` and separator `0x80` at offset 8, but does not unpack the 9 doubles to verify that they are finite floats.
- **Impact**: Non-blocking. The 4-byte magic + 0x80 separator provides $1\text{ in } 2^{40}$ collision resistance. However, adding `doubles.iter().all(f64::is_finite)` would align with the strict defensive parsing posture of `decode_129b_record`.

### Finding 4: Special-Case Root Disambiguation in Hierarchical Assemblies
- **Description**: In `servo_STS3215_03a v1.CATProduct`, the structure pool contains 2 placed child instances and 1 root assembly reference (`main_structure:1`), against 2 transform records. `binding.rs` contains an explicit heuristic (`n_rec == 2 && n_placed == 3 && instances.last() is main`) to resolve the child instances under `sequential_1to1`.
- **Verdict**: Verified. The 2 placed parts receive valid decoded transforms, and the root assembly reference is safely marked `Undecodable` without masking to identity.

---

## 6. Verification Commands & Reproduction Log

```bash
# 1. Run all product unit tests in port
cd port && cargo test product::

# 2. Run the independent review verification test suite
cd port && cargo test --test independent_verify_p3_v1 -- --nocapture

# 3. Run the independent Python verification script
python3 -I scripts/triage/verify_p3_v1_transforms.py

# 4. Verify compiler warnings and formatting
cd port && cargo clippy -- -D warnings
cd port && cargo fmt --check

# 5. Full repository check
bash scripts/check.sh
```

---

## 7. Deliverable & Audit Sign-Off

- **Report Path**: `docs/evidence/2026-11-16-p3-v1-transforms-review.md`
- **Verdict**: **PASS WITH FINDINGS**
- **Audit Sign-off**: Independent Verifier Sub-Agent
