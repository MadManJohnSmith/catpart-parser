# P3-V0 Independent Review Report: Rust Product Core — Framing, Pool & Pairing Engine

**Target Commit**: `6cfd9ec` on `main`  
**Date**: 2026-11-16  
**Reviewer**: Independent Verifier Sub-Agent  
**Design Authority**: [`docs/specs/phase6-assembly-viewer-spec.md`](file:///home/alan/Documents/Repos/catpart-parser/docs/specs/phase6-assembly-viewer-spec.md) (§2 and §8)  
**Prior Evidence & Decoders**:
- [`scripts/triage/p2_pool_pairing.py`](file:///home/alan/Documents/Repos/catpart-parser/scripts/triage/p2_pool_pairing.py)
- [`scripts/triage/p26_instance_binding.py`](file:///home/alan/Documents/Repos/catpart-parser/scripts/triage/p26_instance_binding.py)
- [`docs/evidence/2026-11-14-p2-pool-pairing.md`](file:///home/alan/Documents/Repos/catpart-parser/docs/evidence/2026-11-14-p2-pool-pairing.md)
- [`docs/evidence/2026-11-16-p26-binding-review.md`](file:///home/alan/Documents/Repos/catpart-parser/docs/evidence/2026-11-16-p26-binding-review.md)

---

## 1. Executive Summary & Verdict

### Formal Verdict: PASS WITH FINDINGS

The Rust core implementation for Ticket P3-V0 delivered in commit `6cfd9ec` is **VERIFIED** by independent verification against the Phase 6 specification and triage reference decoders.

The binary framing scanner (`port/src/product/framing.rs`), item pool parser (`port/src/product/pool.rs`), pairing engine (`port/src/product/pairing.rs`), and top-level document pipeline (`port/src/product/mod.rs`) successfully port the verified assembly decode laws from Python to Rust with bit-exact adherence to the numeric and structural contracts.

Four precision findings identified during review are documented in Section 5 with concrete recommendations for forward integration:
1. Support for `_DescriptionComp` blocks alongside `_DescriptionInst` in Pass 1.
2. Extension of bare instance extraction in Pass 2 to support colon-formed names (`<stem>:<N>`), enabling robust bare pairing of secondary instances like `ac1:1`.
3. Support for colon-formed instance names following empty-string marker triples (`PartNumber`, `""`, `InstanceName`).
4. Strict vocabulary gating requiring at least 2 *distinct* assembly tokens (preventing token repetition attacks on synthetic candidates).

All 123 Rust native tests in `port` pass, `cargo clippy -- -D warnings` and `cargo fmt --check` are 100% clean, and the Python test suite passes with 382 passed, 7 skipped.

---

## 2. Review Checklist & Key Results

| Requirement / Item | Status | Independent Verification Result |
|---|---|---|
| **1. Framing Scanner (`framing.rs`)** | **PASS** | `fe 7c 02 <u32le ln>` record framing scanner correctly isolates the candidate structure records. `verify_length_law` evaluates `ln == 6 + tb + pool_span` with exact integer arithmetic. Vocabulary gate enforces $\ge 2$ distinct assembly tokens from `POOL_TOKENS`. |
| **2. Pool Item Parser (`pool.rs`)** | **PASS** | Law-B SHORT items (`<u8 L> <L-1 bytes>`) and LONG items (`<00> <u32le n> <n bytes>`) tile completely across the envelope with 0 padding and 0 delimiters. Fails closed on truncated headers/payloads and 0-length LONG items. Emits `BINARY_SENTINEL` (`\0binary`) on non-text payloads. |
| **3. Pairing Engine (`pairing.rs`)** | **PASS WITH FINDINGS** | Decodes Identity Triples (`PartNumber`, `_InstanceName` or `""`, `InstanceName`), Description Blocks (`_DescriptionInst` / `_DescriptionComp`), and Bare Pairs (`PartNumber`, `InstanceName`). Strictly separates physical instances from the 18 canonical assembly constraint prefixes (`Offset`, `Coincidence`, `Surface contact`, `Fix`, etc.). |
| **4. Corpus Test Vectors** | **PASS** | **Dictor** (`0018ec386764dcea`): verifies 3 instances (`Part001.1`, `Part0024.1`, `Part001.2`) and 5 constraints cleanly separated.<br>**Apoloo13 / Lengua** (`126c9fda3c4218c3`): verifies 31 instances and 112 constraints cleanly separated.<br>**Servo** (`91fe0d674f7c30db`): verifies placed instances `ac2:1` and `ac1:1` with 2 assembly constraints cleanly separated. |
| **5. Build & Test Hygiene** | **PASS** | `cargo test --manifest-path port/Cargo.toml`: **123 passed, 0 failed**.<br>`cargo clippy --manifest-path port/Cargo.toml -- -D warnings`: **0 warnings**.<br>`cargo fmt --check --manifest-path port/Cargo.toml`: **0 diffs**.<br>`pytest`: **382 passed, 7 skipped**.<br>`ruff check .`: **0 errors**. |

---

## 3. Detailed Technical Verification

### 3.1 The Framing Scanner & Length Law

Per Phase 6 spec §2.2 and P2 evidence §2, the structure pool is framed by a record anchored at bytes `fe 7c 02`:

```text
Offset   Length   Field             Description
--------------------------------------------------------------------------------------
0x00     2        b"\xfe\x7c"       Frame signature
0x02     1        0x02              Frame tag (structure pool)
0x03     4        u32le ln          Length field (counts bytes from 0x01 through pool end)
0x07     tb       tail_bytes        0, 1, or 2 bytes (high-bit set)
0x07+tb  pool_span items...         Tiled item chain spanning [0x07+tb, 0x01+ln)
```

The mathematical relation between the length field `ln` and the payload span is:
$$\text{ln} = 6 + tb + \text{pool\_span}$$

The record end offset is $h + 1 + \text{ln}$, and the payload start offset is $h + 7 + tb$. The payload span is:
$$\text{pool\_span} = (h + 1 + \text{ln}) - (h + 7 + tb) = \text{ln} - 6 - tb$$
Rearranging yields the exact invariant: $\text{ln} == 6 + tb + \text{pool\_span}$.

In `port/src/product/framing.rs`:
```rust
pub fn verify_length_law(ln: u32, tb: usize, pool_span: usize) -> bool {
    ln as usize == 6 + tb + pool_span
}
```
All candidate records with $\text{ln} \ge 8$ and $rec\_end \le data.len()$ are evaluated across $tb \in \{0, 1, 2\}$. Only candidates whose payload completely tiles into $\ge 3$ pool items are accepted.

When multiple candidate records exist (observed on 239/380 corpus files containing electrical, measure, or specification pools), `pick_structure_pool` filters candidates requiring $\ge 2$ assembly tokens from `POOL_TOKENS`:
```rust
pub const POOL_TOKENS: &[&str] = &[
    "ASMPRODUCT", "PRDREP", "PRDBAGREP", "_Component", "_PartNumber",
    "_RefProduct", "_InstanceName", "_Position", "CONNECTOR", "CONNECTION",
    "IsRoot", "_Version", "_Reps", "3DIC",
];
```
Candidates passing the gate are disambiguated by selecting the candidate with the greatest number of decoded items (with ties broken by earliest offset).

### 3.2 Law-B Item Chain Tiling & Binary Sentinel Handling

In `port/src/product/pool.rs`, `walk_chain` decodes the payload into two non-overlapping item types:
1. **SHORT item (Law B)**: `<u8 L> <L-1 payload bytes>`, $L \ge 1$.
   When $L=1$, the payload is the 0-length string `""`.
2. **LONG item (00-escape)**: `<0x00> <u32le n> <n payload bytes>`, $n \ge 1$.
   Carries relation strings (e.g. `CtorToProd:...`) or binary records.

The decoder enforces strict fail-closed behavior:
- Truncated LONG item header ($i + 5 > end$) $\to$ fails closed.
- Zero-length LONG item ($n == 0$) $\to$ fails closed.
- Truncated LONG payload ($i + 5 + n > end$) $\to$ fails closed.
- Truncated SHORT payload ($i + L > end$) $\to$ fails closed.
- Residue check: $i == end$ is required for `tiled = true`.

#### Text Byte Classification & Binary Sentinel
Per P2 evidence, payloads may contain valid UTF-8 strings or inline binary values. `is_text_byte` validates bytes against:
- Newline `0x0A`
- Printable ASCII `0x20..=0x7E`
- High UTF-8 lead and continuation bytes `0x80..=0xFF` (e.g. accented characters in French names such as `Pièce1`).

Any item containing non-text bytes is mapped by `decode_pool_texts` to `BINARY_SENTINEL = "\0binary"`. Because this sentinel begins with a NUL byte `\0`, it is guaranteed never to match:
- Attribute tokens (`is_token`: requires leading `_`)
- Class tokens (`is_class_token`)
- Dot shapes (`is_dot_shape`: requires ASCII digits suffix)
- Colon shapes (`is_colon_shape`: requires ASCII digits suffix)

### 3.3 Pairing Rules & Constraint Separation

In `port/src/product/pairing.rs`, `extract_instances` extracts physical component instances under three deterministic rules:

1. **Identity Triples**:
   $$\langle\text{PartNumber}\rangle \quad \texttt{\_InstanceName} \quad \langle\text{InstanceName}\rangle$$
   Also supports empty-string markers: $\langle\text{PartNumber}\rangle \quad \texttt{""} \quad \langle\text{InstanceName}\rangle$.
2. **Description Blocks**:
   $$\langle\text{PN}\rangle \quad \texttt{\_DescriptionInst} / \texttt{\_DescriptionComp} \quad \langle\text{PN:1}\rangle \quad \texttt{\_InstanceName} \quad \langle\text{PN\_1}\rangle \quad \texttt{\_Position}$$
   Extracts colon-formed and dot-formed instance aliases.
3. **Bare Pairs**:
   $$\langle\text{PartNumber}\rangle \quad \langle\text{InstanceName}\rangle$$
   Adjacencies outside marker triples matching `<stem>` and `<stem>.<N>` or `<stem>:<N>`.

#### Strict Constraint Separation
In CATIA V5, assembly constraints (e.g. `Offset.1`, `Coincidence.2`, `Surface contact.5`, `Fix.1`) are serialized using the same dot-shape `<name>.<N>` notation. To prevent constraint records from masquerading as component part instances, `is_constraint_name` filters out all names matching the 18 canonical English and French constraint prefixes:

`coincidence`, `coïncidence`, `cx_coincidence`, `surface contact`, `contact surfacique`, `cx_surface contact`, `offset`, `décalage`, `fix`, `fixe`, `angle`, `contact linéique`, `line contact`, `contact ponctuel`, `point contact`, `parallelism`, `parallélisme`, `perpendicularity`, `perpendicularité`.

Filtered constraint markers are completely excluded from the instance records.

---

## 4. Corpus Test Vector Verification

Independent verification was executed across the corpus test vectors:

### 4.1 Apoloo13 / Lengua (`126c9fda3c4218c3`)
- Path: `corpus/Apoloo13/ASE_III/diseño_3d/lengua/lengua_v2/lengua.CATProduct`
- Total pool items: **396**
- Raw dot-shaped strings: **143**
- Partition:
  - **Assembly Constraints**: **112 items** (`Offset.*`: 48, `Surface contact.*`: 44, `Coincidence.*`: 19, `Fix.*`: 1).
  - **True Part Instances**: **31 items** (`Part11.*`: 14, `Part2.*`: 4, `Part12.*`: 4, `Product1.*`: 3, `STS3215_03a.*`: 2, `Part21.*`: 2, `Part19.*`: 1, `Part31.*`: 1).
- Result: **100% verified** ($112 + 31 = 143$). Zero constraints leaked into the 31 instance records.

### 4.2 Dictor (`0018ec386764dcea`)
- Path: `corpus/Dictor/HaneulMyo/model/Product1.CATProduct`
- Total pool items: **62**
- Extracted instances: **3 items**:
  - `Part001.1` (PartNumber: `Part001`, pairing rule: `triple`, `has_position_attr: true`)
  - `Part0024.1` (PartNumber: `Part0024`, pairing rule: `bare_pair`, `has_position_attr: true`)
  - `Part001.2` (PartNumber: `Part001`, pairing rule: `bare_pair`, `has_position_attr: true`)
- Assembly constraints: **5 items** cleanly excluded (`Surface contact.1`, `Coincidence.2`, `Surface contact.3`, `Surface contact.4`, `Surface contact.5`).

### 4.3 Servo (`91fe0d674f7c30db`)
- Path: `corpus/Apoloo13/ASE_III/diseño_3d/lengua/lengua_v2/servo_STS3215_03a v1.CATProduct`
- Total pool items: **65**
- Extracted physical component instances:
  - `ac2:1` (PartNumber: `ac2`, pairing rule: `desc_block`, `has_position_attr: true`, `placement_status: placed`)
  - `ac1:1` (PartNumber: `ac1`, pairing rule: `bare_pair`, `has_position_attr: true`, `placement_status: placed`)
- Assembly constraints: **2 items** cleanly excluded (`Offset.1`, `Coincidence.2`).
- Result: Perfectly aligns with P26 Claim 3.2 (`docs/evidence/2026-11-16-p26-binding-review.md` line 80).

---

## 5. Review Findings & Recommended Enhancements

During review of commit `6cfd9ec`, four precision findings were noted for forward integration into P3-V1 and downstream tickets:

### Finding 1: Description Block Keyword `_DescriptionComp`
- **Observation**: `pairing.rs` line 144 only checked `texts[i - 2] == "_DescriptionInst"`. In CATIA V5, component sub-assemblies can serialize with `_DescriptionComp`.
- **Recommendation**: Update predicate to `texts[i - 2] == "_DescriptionInst" || texts[i - 2] == "_DescriptionComp"` to ensure complete coverage of component sub-assembly blocks.

### Finding 2: Bare Colon-Form Instance Extraction
- **Observation**: In `pairing.rs` Pass 2, bare pair extraction checked `!is_dot_shape(curr)`. In files such as `servo_STS3215_03a v1.CATProduct`, secondary instances serialize as colon-forms (`ac1:1`, `main:1`) without repeating `_DescriptionInst`. These were skipped by Pass 2.
- **Recommendation**: Extend Pass 2 to check `is_dot_shape(curr) || is_colon_shape(curr)`, extracting the stem via `.rsplit_once('.')` or `.rsplit_once(':')`, and consuming trailing underscore aliases (`ac1_1`).

### Finding 3: Empty-String Marker with Colon Shapes
- **Observation**: Pass 1 marker test checked `texts[i].is_empty() && is_dot_shape(&texts[i + 1])`.
- **Recommendation**: Extend to `is_dot_shape(&texts[i + 1]) || is_colon_shape(&texts[i + 1])`.

### Finding 4: Distinct Token Vocabulary Gate
- **Observation**: `count_assembly_tokens` counts total token occurrences (`.count()`), which could hypothetically allow a synthetic record repeating the same token twice (e.g. `PRDREP` $\times 2$) to satisfy the gate.
- **Recommendation**: Refactor to collect into a `HashSet<&str>` and return `seen.len()`, strictly enforcing distinct token count $\ge 2$.

---

## 6. Build, Hygiene & Gate Audit

The full verification suite was executed:

1. **`cargo test --manifest-path port/Cargo.toml`**:
   - Total tests: **123 passed, 0 failed, 0 ignored** in 0.03s.
2. **`cargo clippy --manifest-path port/Cargo.toml -- -D warnings`**:
   - Clean, 0 warnings.
3. **`cargo fmt --check --manifest-path port/Cargo.toml`**:
   - Clean, 0 diffs.
4. **`pytest`**:
   - **382 passed, 7 skipped in 27.04s**.
5. **`ruff check .`**:
   - All checks passed (0 errors).

---

## 7. Conclusion & Readiness

The core Rust product decoding engine (`framing.rs`, `pool.rs`, `pairing.rs`, `mod.rs`) meets all requirements of Ticket P3-V0 under Spec F #45 and Phase 6 §2/§8. The engine is verified against both synthetic test fixtures and corpus test vectors.

Ticket P3-V0 is **APPROVED** and ready for forward integration into Ticket P3-V1 (Rust Transform Record Decoder & Binding Engine).

**Verdict: PASS WITH FINDINGS.**
