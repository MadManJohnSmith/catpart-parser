# Independent Verification Report: R15 Reference Form & Legacy Position Decode

- **Review Target**: Ticket P6-R15 (commit `f31baa7` on `main`)
- **Reviewer**: Independent Review Sub-Agent
- **Date**: 2026-11-16
- **Evidence Note Reviewed**: [`docs/evidence/2026-11-16-r15-position-probe.md`](file:///home/alan/Documents/Repos/catpart-parser/docs/evidence/2026-11-16-r15-position-probe.md)
- **Triage Script Reviewed**: [`scripts/triage/p6_r15_position_probe.py`](file:///home/alan/Documents/Repos/catpart-parser/scripts/triage/p6_r15_position_probe.py)
- **Claims CSVs Reviewed**:
  - [`docs/evidence/data/p6-r15-position-claims.csv`](file:///home/alan/Documents/Repos/catpart-parser/docs/evidence/data/p6-r15-position-claims.csv)
  - [`docs/evidence/data/p6-r15-position-files-claims.csv`](file:///home/alan/Documents/Repos/catpart-parser/docs/evidence/data/p6-r15-position-files-claims.csv)
- **Independent Verification Code**: `~/.local/state/catpart-parser/r15-review/independent_verifier.py`
- **Verification Summary Artifact**: `~/.local/state/catpart-parser/r15-review/independent_summary.json`

---

## 1. Formal Verdict

### **VERDICT: PASS WITH FINDINGS**

The core structural and algebraic decode of the legacy CATIA position encoding is **fully confirmed and verified**.
The legacy position representation is an inline 12-element run-length floating-point stream (`8d 81` marker followed by tags `0xe8 = 0.0`, `0xe7 = 1.0`, `0xe9 = -1.0`, and `0xe6 = f64le`) encoding a row-major $3 \times 3$ proper rotation matrix and a 3D translation vector in millimeters.

Across the entire 382-file manifest (380 byte-verified CATIA products):
1. **45 / 45 R15 placed files (100.0%)** decode to valid placements (42 inline matrix streams with proper orthogonal rotation matrices and 3 default identity references).
2. **220 / 220 placed files with zero ctorproxy records (100.0%)** decode to valid placements (219 inline matrix streams and 1 default identity reference).
3. **341 / 380 byte-verified CATIA products (89.74%)** carry $\ge 1$ valid inline matrix stream, yielding **3,382 proper orthogonal matrices** corpus-wide.
4. **All 3,382 matrices satisfy proper orthogonality**:
   - Maximum determinant error: $\max |\det(R) - 1.0| = \mathbf{2.19 \times 10^{-12}}$ (well within machine epsilon $\ll 10^{-6}$).
   - Maximum row norm error: $\max |\|R_i\| - 1.0| = \mathbf{9.90 \times 10^{-13}}$.
   - Maximum pairwise orthogonality error: $\max |R_i \cdot R_j| = \mathbf{9.26 \times 10^{-13}}$.
5. **The test gate is fully green**: `scripts/check.sh` passes (ruff clean, pytest 381 passed / 7 skipped, cargo native + wasm32 + clippy -D warnings + test 97 passed, wasm-pack node 6 passed, pkg sync clean).
6. **CSV hygiene is 100% compliant**: `check_claims_csv_quoting.py` verifies all claims tables; byte-deterministic output on re-generation.

One non-blocking finding (**F1**) is identified regarding the sequential instance-binding lookback heuristic in the triage probe and recorded below for downstream implementation guidance.

---

## 2. Independent Methodology & Protocol

Per `docs/agents/dispatch-recipes.md`, verification was conducted with an **independent walker**:
- **Zero imported functions**: The child script (`p6_r15_position_probe.py`) was **never imported**.
- **Independent byte readers**: A custom parser (`independent_decode_run_length_floats`) was implemented from scratch to decode tags `0xe8`, `0xe7`, `0xe9`, and `0xe6 <f64le>`.
- **Independent linear algebra engine**: Vector norms, dot products, and $3 \times 3$ determinants were implemented directly from first mathematical principles.
- **Independent corpus walk**: Iterated across all 382 manifest rows (`kind=product`), reading raw bytes, identifying `\x8d\x81` tokens, testing proper orthogonality, and verifying attribute stream contexts.
- **Verification script location**: `~/.local/state/catpart-parser/r15-review/independent_verifier.py`.

---

## 3. Detailed Verification of Claims

### 3.1 Mathematical Orthogonality and Scaling (Claims P6-R15-2 & P6-R15-5)

The 12-element stream represents:
$$M = \begin{bmatrix} R_{11} & R_{12} & R_{13} \\ R_{21} & R_{22} & R_{23} \\ R_{31} & R_{32} & R_{33} \end{bmatrix}, \quad T = \begin{bmatrix} T_x \\ T_y \\ T_z \end{bmatrix}$$

Every matrix discovered corpus-wide (3,382 matrices across 341 files) was evaluated against proper rotation in $SO(3)$:
1. $\det(R) = +1.000000$:
   - Across all 3,382 matrices, $\max |\det(R) - 1.0| = 2.19 \times 10^{-12}$.
   - 100.0% of matrices satisfy $|\det(R) - 1.0| \le 10^{-6}$.
2. Orthonormal basis rows $\|R_i\| = 1.000000$:
   - $\max |\|R_i\| - 1.0| = 9.90 \times 10^{-13}$.
3. Mutual orthogonality $R_i \cdot R_j = 0.0$:
   - $\max |R_i \cdot R_j| = 9.26 \times 10^{-13}$.
4. Physical translation scale:
   - Components span $[0.0, 417486.53]$ mm (0 to 417.5 meters). These correspond to realistic CAD millimeter coordinates (small mechanism parts to large multi-meter aerospace airframes and factory layouts).

**Verdict**: **VERIFIED FACT**.

---

### 3.2 The 45 R15 Placed Files (Claims P6-R15-1, P6-R15-2, P6-R15-3)

P25 scoped 45 files carrying `_Position` with R15 reference markers (`r15_position_entries > 0`).

Independent re-derivation confirms:
- **42 files** carry the inline 12-element matrix stream following `\x0a_Position` and `\x8d\x81`.
- **3 files** carry the interned identity reference `81 e9 34 07 04 01 fe` (or `81 e9 f4 07 04 01 fe`).
- **Placement resolution**: **45 / 45 = 100.00%**.

Kinematic breakdown:
- **Exact identity ($R=I, T=0$)**: 21 files.
- **Pure translation ($R=I, T \neq 0$)**: 13 files.
- **Rotated transforms ($R \neq I, \det=1.000000$)**: 8 files.
- **Identity constant reference**: 3 files.

All 8 rotated files independently verified:
1. `ff75709ea141b6bf` (`Geometrical_Bundle1`): $\det(R) = 1.000000$, $T = [981.0641, 0.0, -43.0157]$ mm
2. `21392fc55f7f9f8c` (`Electrical_Bundle1`): $\det(R) = 1.000000$, $T = [-308.61, 0.0, 0.0]$ mm
3. `34555cab0f61b75d` (`ProductForGenShapeUseCase`): $\det(R) = 1.000000$, $T = [21.31, 112.77, 30.71]$ mm
4. `bc01c5d3afb9778e` (`Geometrical_Bundle2_Ehf1`): $\det(R) = 1.000000$, $T = [28.25, -3.50, -19.78]$ mm
5. `3a40ea07220459e0` (`CAA_EHIMultiSegmentSample`): $\det(R) = 1.000000$, $T = [13.25, -3.50, -19.78]$ mm
6. `deb14002fc0dca7e` (`Ehi_ElecEquipment`): $\det(R) = 1.000000$, $T = [50.00, -10.10, 0.0]$ mm
7. `c0f11142aab05958` (`CAAPstBlockMovable_chain`): $\det(R) = 1.000000$, $T = [25.62, -45.51, -2.13]$ mm
8. `82617df657e59001` (`CAAPstPrdObjectPublisher`): $\det(R) = 1.000000$, $T = [-54.61, -37.63, 38.03]$ mm

**Verdict**: **VERIFIED FACT**.

---

### 3.3 The 220 Zero-CtorProxy Placed Files (Claim P6-R15-4)

P25 identified 260 placed files in the corpus (`placed_pool == 1`). Modern `CATCtorProxyCont` quaternion records were present in only 40 files, leaving 220 placed files with zero ctorproxy records.

Independent scan across all 220 files confirms:
- **219 files** carry $\ge 1$ valid `8d 81` 12-element matrix stream.
- **1 file** (`5f46062dffd19377`) carries the abbreviated identity reference (`81 e9 34 07 04 01 fe`).
- **0 files** remain unresolved.
- **Placement coverage: 220 / 220 = 100.00%**.

Bucket distribution of the 220 zero-record files:
- R15: 8 / 8
- R16: 6 / 6
- R17: 8 / 8
- R18: 7 / 7
- R19: 78 / 78
- R20: 10 / 10
- R21: 37 / 37
- R23: 3 / 3
- R24: 12 / 12
- R26: 1 / 1
- unknown: 50 / 50
- **Total: 220 / 220**

**Verdict**: **VERIFIED FACT**.

---

### 3.4 Corpus-Wide Prevalence Census (Claim P6-R15-5)

Independent walk across all 380 byte-verified CATIA products (`pool_form != 'non-catia'`):

| Bucket | Verified Matrix Files | Total Files | Coverage | Total Matrices |
|---|---|---|---|---|
| R15 | 13 | 14 | 92.86% | 24 |
| R16 | 18 | 18 | 100.00% | 82 |
| R17 | 13 | 16 | 81.25% | 48 |
| R18 | 16 | 25 | 64.00% | 62 |
| R19 | 102 | 105 | 97.14% | 1,435 |
| R20 | 26 | 26 | 100.00% | 292 |
| R21 | 52 | 53 | 98.11% | 922 |
| R23 | 3 | 3 | 100.00% | 33 |
| R24 | 16 | 17 | 94.12% | 104 |
| R26 | 1 | 1 | 100.00% | 3 |
| unknown | 81 | 102 | 79.41% | 377 |
| **Total** | **341** | **380** | **89.74%** | **3,382** |

Every bucket total and file count matches the child's claims table and files table **row-for-row on all 382 rows**.

**Verdict**: **VERIFIED FACT**.

---

### 3.5 R23 Framed Placement Files (Claim P6-R15-6)

All 3 R23 placed files carry zero ctorproxy records but carry valid `8d 81` matrix streams:
- `2a2c6df18eeda566` (`Fou.CATProduct`): 2 matrices ($T = [90.66, 40.76, 46.22]$ mm)
- `8c19aab3c2c7aa11` (`ScrewedPlates.CATProduct`): 8 matrices ($x = -120, -60$ mm; $z = -8.4, 5, 7, 18$ mm; camera at $[255.05, -475.29, 166.16]$ mm)
- `da7d6badc6f5b1ac` (`SetDeContraintes.CATProduct`): 23 matrices (circular assembly constraint layout)
- Total: 33 matrices, all with $\det(R) = 1.000000$.

**Verdict**: **VERIFIED FACT**.

---

## 4. Findings and Structural Observations

### Finding F1 (Non-Blocking): Scope of Sequential Instance Binding and Probe Lookback Ceiling

In Section 7 of [`docs/evidence/2026-11-16-r15-position-probe.md`](file:///home/alan/Documents/Repos/catpart-parser/docs/evidence/2026-11-16-r15-position-probe.md), the evidence note states:
> *"The object serialization is strictly sequential: 1. Object start marker (`ea <id>`), 2. `_InstanceName` attribute (`\x0d_InstanceName\x80 ... <name>`), 3. Followed immediately by `_Position` attribute (`\x0a_Position\x80 ... 8d 81 <12-stream>`). The position belongs to the instance that contains it."*

An exhaustive byte-level inspection of all 45 R15 placed files reveals that while the **conceptual finding is correct** (transforms are inline component attributes, not detached index tables), the structural layout exhibits four distinct patterns:

```mermaid
flowchart TD
    subgraph PatternA["Pattern A: Direct Sequential (25/45)"]
        A1["Object Header (ea)"] --> A2["_InstanceName (< 500 B)"] --> A3["_Position (8d 81)"]
    end
    subgraph PatternB["Pattern B: Intervening Electrical/Geo Defs (9/45)"]
        B1["Object Header (ea)"] --> B2["_InstanceName"] --> B3["Elec/Geo Metadata (500-2043 B)"] --> B4["_Position (8d 81)"]
    end
    subgraph PatternC["Pattern C: Inverted In-Block Order (4/45)"]
        C1["Object Header (ea)"] --> C2["_Position (8d 81)"] --> C3["Component Metadata"] --> C4["_InstanceName"]
    end
    subgraph PatternD["Pattern D: Raw Shape Objects (7/45)"]
        D1["MaterialDataCont / Raw Objects"] --> D2["Shape Name (e.g. Shape 1, cyl)"] --> D3["_Position (8d 81) (No _InstanceName tag)"]
    end
```

1. **Direct Sequential (25 files)**: `_InstanceName` directly precedes `_Position` within 500 bytes (min 91 B, max 472 B, mean 217.0 B).
2. **Intervening Metadata (9 files)**: `_InstanceName` precedes `_Position`, but is separated by 500 to 2,043 bytes of electrical or bundle definition attributes (e.g., `ElecBundleCnctPt`, `ElecLogicalTermination`, `ElecTermination` in `Geometrical_Bundle1.CATProduct`).
3. **Inverted In-Block Order (4 files)**: In files like `eba990baf2b98b88` (`ElectricalWorkBenchesIntegration_Ehf1`), `_Position` precedes `_InstanceName` by 158 bytes within the component representation definition (`Product8`).
4. **Non-Product / Raw Shape Objects (7 files)**: In files like `5d2cf490aa507fc5`, the container is `MaterialDataCont` and objects are raw shapes (e.g., `Shape 1`, `cyl`) where positions are serialized without the `_InstanceName` tag.

**Consequence for Census CSV**:
In [`scripts/triage/p6_r15_position_probe.py`](file:///home/alan/Documents/Repos/catpart-parser/scripts/triage/p6_r15_position_probe.py), the helper `decode_r15_position()` hardcodes a backward search slice:
```python
lookback = data[max(0, idx - 400) : idx]
```
Because of this 400-byte cap:
- Exactly **25 of the 45 files** have `r15_instance_name` populated in `p6-r15-position-files-claims.csv`.
- Exactly **20 of the 45 files** have an empty `r15_instance_name` field, even though `_InstanceName` is present earlier in 9 files (at distances 545 B to 2,398 B) or later in 4 files.

**Recommendation**:
This does not affect any claim in `p6-r15-position-claims.csv` (claims evaluate placement validity, proper rotation, and coverage, which are 100% true). Downstream assembly builders should implement block-scoped container parsing rather than a fixed 400-byte window when binding instances to transforms.

---

## 5. Selftest & CSV Hygiene Verification

### 5.1 Selftest Pins (13 Pins)
The probe script's `--selftest` mode was independently executed and analyzed:
1. `identity-det`, `identity-ortho`, `identity-quat`: Unit identity matrix evaluates to $\det=1.0$, proper rotation, unit quaternion $(1,0,0,0)$.
2. `rz90-det`, `rz90-ortho`, `rz90-quat-w`, `rz90-quat-z`: 90° rotation around Z axis evaluates to $\det=1.0$, proper rotation, $q = (\sqrt{2}/2, 0, 0, \sqrt{2}/2)$.
3. `reflection-rejected`: Mirror/improper rotation ($\det = -1.0$) is rejected by `is_proper_rotation`.
4. `non-ortho-rejected`: Skewed non-orthogonal vectors are rejected.
5. `parse-id-status`, `parse-id-len`, `parse-id-vals`, `parse-id-consumed`: Literal tags `e7 e8 e8 ...` parse to 12 floats consuming 12 bytes.
6. `parse-e9-ok`, `parse-e9-val`: Tag `0xe9` correctly decodes to $-1.0$.
7. `parse-e6-ok`, `parse-e6-val`, `parse-e6-consumed`: Tag `0xe6` consumes 9 bytes and unpacks IEEE-754 double `123.456`.
8. `parse-trunc-err`: Truncated `e6` buffer returns `e6_truncated` error without throwing exceptions.
9. `parse-bad-tag`: Unknown byte stops parsing cleanly.
10. `scan-matrices-count`, `scan-matrices-det`: Scans synthetic streams for `8d 81` markers.
11. `r15-dec-found`, `r15-dec-type`, `r15-dec-inst`, `r15-dec-identity`, `r15-dec-det`: Full R15 synthetic block parses instance name and inline matrix.
12. `r15-id-ref-found`, `r15-id-ref-type`, `r15-id-ref-is-id`: Abbreviated identity reference parses correctly.
13. `elec-not-detected`: False-positive rejection fixture: `\x10Elec_X_Position` is not mistaken for `_Position`.

All 13 pins pass cleanly.

### 5.2 CSV Hygiene
- Checked with [`scripts/triage/check_claims_csv_quoting.py`](file:///home/alan/Documents/Repos/catpart-parser/scripts/triage/check_claims_csv_quoting.py):
  - 47 CSV files checked across repo (12,646 rows).
  - Every row parses at exact header width without shifts or trailing comma issues.
- Direct row-width validation:
  - `docs/evidence/data/p6-r15-position-claims.csv`: exactly 7 columns, 6 claim rows.
  - `docs/evidence/data/p6-r15-position-files-claims.csv`: exactly 22 columns, 382 file rows.
- Deterministic reproduction:
  - Re-running `python3 -I scripts/triage/p6_r15_position_probe.py --all` produces **zero git diff** against committed artifacts.

---

## 6. Gate Status

The repository test gate was executed via `scripts/check.sh`:
- **Python**:
  - `ruff check .`: All checks passed!
  - `pytest -q`: **381 passed, 7 skipped** (25.33 s).
- **Cargo (Rust Port)**:
  - `cargo build (native)`: ok
  - `cargo build (wasm32-unknown-unknown)`: ok
  - `cargo fmt --check`: ok
  - `cargo clippy -D warnings`: ok
  - `cargo test (port)`: **97 passed; 0 failed**
- **Wasm**:
  - `wasm-pack build --target web --release`: ok
  - `wasm-pack test --node`: **6 passed; 0 failed**
  - `pkg sync`: ok

---

## 7. Review Conclusion

The P6-R15 deliverable successfully resolves the longstanding legacy position encoding open class.
The mathematical evidence is irrefutable: $100\%$ of candidate matrices achieve double-precision proper orthogonality ($\max |\det(R) - 1.0| = 2.19 \times 10^{-12}$), placement coverage is $100\%$ across both R15 placed files (45/45) and zero-ctorproxy placed files (220/220), and the format spans $89.7\%$ of the entire CATIA product corpus.

The deliverable is approved: **PASS WITH FINDINGS**.
The code and documentation are ready for integration into downstream Phase 6 assembly pipelines.
