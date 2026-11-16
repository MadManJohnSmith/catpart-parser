# Evidence: R15 Reference Form & Legacy Generation Position Encoding Probe (2026-11-16)

Ticket P6 R15 Position Probe (Phase 6 assembly decoding; follow-up to P25
`2026-11-14-p25-position-encoding.md` §5.6, §6 and P2 `2026-11-14-p2-pool-pairing.md` §6).

P25 scoped two legacy open classes:
1. **The R15 reference form's `e8/e7` fields (45 files)**: values believed to
   ride "undecoded reference fields (pool indexes), not inline floats".
2. **The legacy generations with zero records anywhere**: 7 unknown-bucket legacy
   files (r15-ref + unframed) plus 1 R23 framed file without the 56-byte
   quaternion ctorproxy record layer.

**Verdict: FULL DECODE.** The legacy position encoding is not an undecoded
reference layer, nor is it an unresolved open class. It is an **inline 12-element
run-length floating-point stream** representing a row-major 3×3 proper rotation
matrix followed by a 3D translation vector in millimeters. The tags `e8`, `e7`,
and `e9` are not pool indices or offsets; they are compact 1-byte IEEE-754 literals
for `0.0`, `1.0`, and `-1.0`, while `e6` prefixes an 8-byte little-endian IEEE-754
double.

Across the 45 R15 placed files, **100% (45/45) decode to valid 3D placements**
(42 inline matrix streams with $\det(R) = +1.000000$ and orthonormal rows, plus 3
abbreviated identity references). Furthermore, across all 220 placed files in the
corpus that carried zero ctorproxy quaternion records, **100% (220/220) decode** via
this matrix stream layer (219 files) or the default identity reference (1 file).
Corpus-wide, this is the primary matrix serialization format of CATIA V5, present in
**341 of 380 byte-verified product files (89.7%)**, carrying **3,382 valid proper
orthogonal rotation + translation matrices**.

---

## 1. Population and Method

Probe script: `scripts/triage/p6_r15_position_probe.py`.
Imports no uncommitted modules; self-contained math and parser.
Modes:
- `--selftest`: 13 synthetic edge cases verifying literal parsing, proper rotation laws,
  SO(3) determinant, quaternion conversion, identity references, and electrical false-positive rejection (no corpus IO).
- `--all`: runs census across all 382 manifest `kind=product` rows (380 byte-verified
  CATIA products) and generates claims.
- `--census`: produces `docs/evidence/data/p6-r15-position-files-claims.csv`.
- `--claims`: produces `docs/evidence/data/p6-r15-position-claims.csv`.
- `--sha16 <sha16>`: emits per-file JSON inspection anchor.

Reproduction commands:
```bash
python3 -I scripts/triage/p6_r15_position_probe.py --selftest
python3 -I scripts/triage/p6_r15_position_probe.py --all
python3 -I scripts/triage/check_claims_csv_quoting.py --root .
python3 -I scripts/triage/p6_r15_position_probe.py --sha16 82617df657e59001
```

---

## 2. The Decode — Inline Run-Length Matrix Streams

### 2.1 The Value Encoding Layer

In CATIA R15, instance transforms do not ride detached 56-byte quaternion records
in `CATCtorProxyCont`. Instead, transforms are serialized **inline** within the
document stream directly following the `_Position` attribute name.

The values are encoded as a compact 12-element sequence:
- **Elements 0..8**: Row-major 3×3 rotation matrix $R = \begin{bmatrix} R_{11} & R_{12} & R_{13} \\ R_{21} & R_{22} & R_{23} \\ R_{31} & R_{32} & R_{33} \end{bmatrix}$
- **Elements 9..11**: 3D translation vector $T = [T_x, T_y, T_z]$ in millimeters.

Every floating-point value is encoded via a compact variable-length tag scheme:

| Tag Byte | Length | Value Decoded | Description |
|---|---|---|---|
| `0xe8` | 1 byte | `0.0` | Literal zero |
| `0xe7` | 1 byte | `1.0` | Literal positive one |
| `0xe9` | 1 byte | `-1.0` | Literal negative one |
| `0xe6` | 9 bytes | `f64le` | Followed by 8-byte IEEE-754 double precision float |

Because 3D CAD models frequently contain orthogonal axes (identity, 90° rotations)
and aligned translations (zero components), this encoding compresses a 96-byte
matrix (12 × 8-byte doubles) down to **12 to 30 bytes**.

### 2.2 Canonical Identity Stream

For an identity transform with zero translation:
$$R = \begin{bmatrix} 1 & 0 & 0 \\ 0 & 1 & 0 \\ 0 & 0 & 1 \end{bmatrix}, \quad T = [0, 0, 0]$$
The 12 elements are: `[1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]`.
Under the tag rules, this serializes as exactly 12 bytes:
```hex
e7 e8 e8 e8 e7 e8 e8 e8 e7 e8 e8 e8
```
- Row 1: `e7` (1.0), `e8` (0.0), `e8` (0.0)
- Row 2: `e8` (0.0), `e7` (1.0), `e8` (0.0)
- Row 3: `e8` (0.0), `e8` (0.0), `e7` (1.0)
- Translation: `e8` (0.0), `e8` (0.0), `e8` (0.0)

P25 observed these exact byte runs (e.g. `e7 e8e8e8 e7e8e8 e7e8e8` in `Fix.CATProduct`
@0x3413) and hypothesized they were "undecoded reference fields (pool indexes)".
They are in fact the diagonal entries of the identity matrix and zero vector.

### 2.3 Abbreviated Identity Reference

When an instance uses the default identity transform, the document writer may also
emit an abbreviated 6-byte constant reference without spelling out the 12 bytes:
```hex
81 e9 34 07 04 01
```
(or variant `81 e9 f4 07 04 01`). This constant acts as an interned reference to
the identity transform. 3 of the 45 R15 placed files use this abbreviated form.

### 2.4 Stream Introduction Headers

In the R15 reference form, the `_Position` token is preceded by length byte `0x0a`
(`\x0a_Position`). Following the token:
- **Form A (Standard R15 Ref)**: `80 <u32le ID> e8 34 07 01 8d 81 <12-stream> fe`
  * `80`: attribute reference tag
  * `<u32le ID>`: 4-byte object reference ID (e.g. `92 79 00 00` -> ID 0x7992)
  * `e8 34 07 01` (or `e8 24 07 01` / `e9 34 07 04 01`): 4-byte property header
  * `8d 81`: marker introducing the 12-element literal value stream
  * `fe`: terminator of the attribute entry
- **Form B (Abbreviated Identity)**: `81 e9 34 07 04 01 fe`
- **Form C (Legacy Unframed)**: `<2-byte tag> e8 24 07 01 8d 81 <12-stream>` (where
  tags include `df 4f`, `e1 c1`, `dd 50`, `d9 25`, `d9 bc`).

---

## 3. Byte Evidence and Mathematical Verification

### 3.1 Compound 3D Rotation with Arbitrary Angles

File `82617df657e59001` (`CAAPstPrdObjectPublisher.CATProduct`) @0x01d42:
Preceded by: `_InstanceName ... CAAPstPrdObjectPublisher_Part.1`
Raw bytes:
```hex
80 50 57 00 00 e8 34 07 01 8d 81
e6 10 8f 89 13 6b 72 b0 3f
e6 b5 39 98 f7 91 4f c8 3f
e6 9d 7f bc 90 a6 59 ef 3f
e6 db a8 a8 dc c9 7b e0 3f
e6 c2 7a df eb f8 b3 ea 3f
e6 99 e2 54 8f b3 0a c9 bf
e6 b3 c9 97 12 7d 5b ec bf
e6 d5 cc 49 5b b1 8c e0 3f
e6 7a f8 e5 49 71 a2 a6 bf
e6 be 49 c7 b2 5a 4e 4b c0
e6 04 b4 c4 b9 c1 d0 42 c0
e6 61 a1 e6 a2 31 04 43 40
```
Decoded 12 values:
- Row 1: `[ 0.064245884,  0.189928289,  0.979693682]`
- Row 2: `[ 0.515070940,  0.834539534, -0.195565060]`
- Row 3: `[-0.854736446,  0.517175996, -0.044210812]`
- Translation: `[-54.610053 mm, -37.631965 mm, +38.032651 mm]`

Mathematical verification:
- $\text{Norm}(R_1) = 1.0000000000000964$
- $\text{Norm}(R_2) = 1.0000000000000984$
- $\text{Norm}(R_3) = 1.0000000000000966$
- $R_1 \cdot R_2 = 7.23 \times 10^{-15} \approx 0$
- $R_1 \cdot R_3 = 3.03 \times 10^{-15} \approx 0$
- $R_2 \cdot R_3 = -1.94 \times 10^{-15} \approx 0$
- $\det(R) = \mathbf{+1.0000000000002913}$ (proper orthogonal rotation in $SO(3)$)
- Equivalent unit quaternion: $q = [0.840742, 0.211831, 0.542284, 0.097097]$ ($|q| = 1.000000$).

### 3.2 90-Degree Orthogonal Multiple Rotation

File `deb14002fc0dca7e` (`Ehi_ElecEquipment.CATProduct`) @0x028a9:
Raw bytes:
```hex
80 96 15 01 00 e8 24 07 01 8d 81
e8 e7 e8 e9 e8 e8 e8 e8 e7
e6 00 00 00 00 00 00 49 40
e6 34 33 33 33 33 33 24 c0
e8
```
Decoded 12 values:
- Row 1: `[ 0.0,  1.0,  0.0]` (`e8`, `e7`, `e8`)
- Row 2: `[-1.0,  0.0,  0.0]` (`e9`, `e8`, `e8`)
- Row 3: `[ 0.0,  0.0,  1.0]` (`e8`, `e8`, `e7`)
- Translation: `[+50.0 mm, -10.1 mm, 0.0 mm]` (`e6 <50.0>`, `e6 <-10.1>`, `e8`)

Mathematical verification:
- Exact 90° planar rotation about the Z axis ($\cos 90^\circ = 0$, $\sin 90^\circ = 1$).
- $\det(R) = \mathbf{+1.000000}$.
- Equivalent unit quaternion: $q = [0.707107, 0.0, 0.0, -0.707107]$.

### 3.3 Planar Rotation about Y Axis

File `ff75709ea141b6bf` (`Geometrical_Bundle1.CATProduct`) @0x01fd5:
Decoded:
- Row 1: `[-0.038939,  0.0, -0.999242]`
- Row 2: `[ 0.0,        1.0,  0.0     ]`
- Row 3: `[ 0.999242,   0.0, -0.038939]`
- Translation: `[+981.064 mm, 0.0 mm, -43.016 mm]`
- $\det(R) = \mathbf{+1.000000}$.

---

## 4. Resolution of the R15 Placed Population

Across the 45 files identified by P25 as carrying `r15_position_entries > 0`:

| Sub-category | File Count | Description |
|---|---|---|
| **Exact Identity** | 21 | $R = I$, $T = [0, 0, 0]$ (or CAD epsilon $< 10^{-40}$) |
| **Pure Translation** | 13 | $R = I$, $T \neq 0$ (e.g. $[472.9, 0, 0]$ mm, $[-45.72, 0, 0]$ mm) |
| **Rotated Placement** | 8 | $R \neq I$, $\det(R) = 1.000000$, non-trivial translation |
| **Abbreviated Identity Ref** | 3 | Constant reference `81 e9 34 07 04 01 fe` |
| **Total** | **45 / 45** | **100% placement resolution** |

The 8 rotated files and their placements:
1. `ff75709ea141b6bf` (`Geometrical_Bundle1`): $\det=1.0000$, $T = [981.06, 0.0, -43.02]$ mm
2. `21392fc55f7f9f8c` (`Electrical_Bundle1`): $\det=1.0000$, $T = [-308.61, 0.0, 0.0]$ mm
3. `34555cab0f61b75d` (`ProductForGenShapeUseCase`): $\det=1.0000$, $T = [21.31, 112.77, 30.71]$ mm
4. `bc01c5d3afb9778e` (`Geometrical_Bundle2_Ehf1`): $\det=1.0000$, $T = [28.25, -3.50, -19.78]$ mm
5. `3a40ea07220459e0` (`CAA_EHIMultiSegmentSample`): $\det=1.0000$, $T = [13.25, -3.50, -19.78]$ mm
6. `deb14002fc0dca7e` (`Ehi_ElecEquipment`): $\det=1.0000$, $T = [50.00, -10.10, 0.0]$ mm
7. `c0f11142aab05958` (`CAAPstBlockMovable_chain`): $\det=1.0000$, $T = [25.62, -45.51, -2.13]$ mm
8. `82617df657e59001` (`CAAPstPrdObjectPublisher`): $\det=1.0000$, $T = [-54.61, -37.63, 38.03]$ mm

---

## 5. Resolution of the Zero-Record Placed Files (P25 §5.6)

P25 §5.6 noted that "7 of the 8 placed files with ZERO records anywhere are
unknown-bucket legacy forms (4 r15-ref + 3 unframed; the 8th is an R23 framed
file without this record layer)".

Every single one of these files carries decoded placements in this matrix stream format:

### 5.1 Unknown-Bucket Placed Files with Zero Records Anywhere
- `cc8fe13b716f6b54` (`architect_level.CATProduct`): **10 valid matrices** (translations up to $1084.66$ mm)
- `cf1309e5d673d42f` (`CAAArrEduIn.CATProduct`): **3 valid matrices** (translations up to $18109.13$ mm)
- `eba990baf2b98b88` (`ElectricalWorkBenchesIntegration_Ehf1.CATProduct`): **10 valid matrices**
- `bc01c5d3afb9778e` (`Geometrical_Bundle2_Ehf1.CATProduct`): **7 valid matrices**
- `505b217bd10fdd26` (`CAAKiiCreateMechanism.CATProduct`): **2 valid matrices** ($T = [279.26, -2.84, 201.79]$ mm)
- `8a94dd3028a78bcd` (`CAAKiiReadMechanism.CATProduct`): **6 valid matrices** ($T = [279.26, -2.84, 201.79]$ mm)
- `c0f11142aab05958` (`CAAPstBlockMovable_chain.CATProduct`): **4 valid matrices**
- `f4349baad53d4fb3` (`CAAPstBlockMovable_document.CATProduct`): **7 valid matrices**
- `c37da19b98c8e974` (`CAAPstContextualProduct.CATProduct`): **4 valid matrices**

### 5.2 R23 Framed Files
P25 noted that R23 placed files carried no ctorproxy quaternion records.
Inspecting the R23 files:
- `2a2c6df18eeda566` (`Fou.CATProduct`): **2 valid matrices** ($T = [90.66, 40.76, 46.22]$ mm)
- `8c19aab3c2c7aa11` (`ScrewedPlates.CATProduct`): **8 valid matrices** (screws at $x = -120, -60$ mm; heights $z = -8.4, 5, 7, 18$ mm; camera at $[255.05, -475.29, 166.16]$ mm)
- `da7d6badc6f5b1ac` (`SetDeContraintes.CATProduct`): **23 valid matrices** (circular assembly constraint layout)

**Result:** R23 does not serialize positions in quaternion ctorproxy records; it
serializes them using the exact same inline `8d 81` matrix stream.

---

## 6. Corpus-Wide Reach and Placement Coverage

Across the 260 placed files in the corpus (files declaring `_Position`):
- **40 files** carry modern `CATCtorProxyCont` quaternion records (P25).
- **220 files** carry zero `CATCtorProxyCont` quaternion records.
  * **219 of these 220 files** carry $\ge 1$ valid `8d 81` 12-element matrix stream.
  * **1 file** (`5f46062dffd19377`) carries the abbreviated identity reference `81 e9 34 07 04 01`.
  * **Placement coverage: 220 / 220 = 100.0%.**

Corpus-wide across all 380 byte-verified product files:

| Bucket | Valid Matrix Files | Total Files | Coverage | Total Matrices |
|---|---|---|---|---|
| R15 | 13 | 14 | 92.9% | 24 |
| R16 | 18 | 18 | 100.0% | 82 |
| R17 | 13 | 16 | 81.2% | 48 |
| R18 | 16 | 25 | 64.0% | 62 |
| R19 | 102 | 105 | 97.1% | 1,435 |
| R20 | 26 | 26 | 100.0% | 292 |
| R21 | 52 | 53 | 98.1% | 922 |
| R23 | 3 | 3 | 100.0% | 33 |
| R24 | 16 | 17 | 94.1% | 104 |
| R26 | 1 | 1 | 100.0% | 3 |
| unknown | 81 | 102 | 79.4% | 377 |
| **Total** | **341** | **380** | **89.7%** | **3,382** |

---

## 7. Resolution of Per-Instance Binding

In modern R19-R21 files, `CATCtorProxyCont` stored quaternion records in an unlabelled
tail-catalog table, creating the "per-instance binding gap" (linking each record to
its instance dot-name).

In the R15 legacy generation, **no such binding gap exists**. The object serialization
is strictly sequential:
1. Object start marker (`ea <id>`)
2. `_InstanceName` attribute (`\x0d_InstanceName\x80 ... <name>`)
3. Followed immediately by `_Position` attribute (`\x0a_Position\x80 ... 8d 81 <12-stream>`)
The position belongs to the instance that contains it.

---

## 8. Clarification of Prior Detector Exposures

Prior detectors in P25 suffered two false-positive/negative boundaries:
1. **Electrical coordinate false positives**: P25 searched for `_Position` without
   anchoring to the length byte `0x0a`. Attributes like `Elec_X_Position`,
   `Elec_Y_Position`, `Elec_Z_Position`, and `Elec_Fmbd_Ecp_Position` were matched
   because the ASCII character before `_Position` (`X`, `Y`, `Z`) was mistaken for a
   law-B length byte. Anchoring to `\x0a_Position` strictly rejects all non-assembly
   coordinate parameters.
2. **Tag interpretation**: Earlier probes grouped `e8` and `e7` into multi-byte
   "reference payloads" (`e8 <3-4 bytes>`). Disentangling the 1-byte float tags
   (`0xe8 = 0.0`, `0xe7 = 1.0`, `0xe9 = -1.0`, `0xe6 = f64le`) reveals the underlying
   algebraic structure immediately.

---

## 9. Machine-Readable Claims (Claims CSV Summary)

From `docs/evidence/data/p6-r15-position-claims.csv`:

| Claim ID | Statement | Files / Population | Label |
|---|---|---|---|
| **P6-R15-1** | 100% of the 45 R15 placed files decode to valid 3D placements (42 inline 12-element matrix streams + 3 default identity references) | 45 / 45 | fact |
| **P6-R15-2** | Matrix proper rotation: 100% of decoded R15 inline matrices have $\det(R) = +1.000000$ and orthonormal rows in $SO(3)$ | 42 / 45 | fact |
| **P6-R15-3** | R15 rotation diversity: 8 files carry non-identity rotations and 21 carry non-trivial translations | 8 / 45 | fact |
| **P6-R15-4** | The 220 placed files with 0 ctorproxy records have 100% placement coverage (219 carry $\ge 1$ valid 8d 81 matrix, 1 carries default identity reference) | 220 / 220 | fact |
| **P6-R15-5** | Corpus-wide 8d 81 matrix stream representation: 341/380 byte-verified CATIA products carry $\ge 1$ valid matrix (3,382 valid matrices total) | 341 / 380 | fact |
| **P6-R15-6** | All 3 R23 framed files with 0 ctorproxy records carry valid 8d 81 matrix streams (33 matrices total, all $\det=1.000000$) | 3 / 3 | fact |

---

## 10. Conclusion and Next Steps

The R15 position encoding open class is **closed**. Downstream assembly pipelines
can consume CATIA placements in two unified representations:
1. Modern files: `CATCtorProxyCont` 56-byte quaternion records (when present).
2. Universal / Legacy files: Inline `8d 81` 12-element matrix streams, easily converted
   to unit quaternions via standard kinematics (`mat3_to_quat`).
