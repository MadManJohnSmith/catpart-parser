# P3 — Position-Layer Segmentation and the 8d81 `_Position` Law (2026-11-18)

**Ticket**: recover the instances blocked by the count-equality binding gate.
**Scope**: `port/src/product/` (Rust) + `src/catpart/fixtures_assembly.py` (Python twin).
**Corpus**: 571 `.CATProduct` files (381 decoded by the product seam; one 11-byte
`AssemblyTemplate.CATProduct` is a documented `truncated-file` refusal).

**Premise correction (byte-verified here and by the independent investigation)**:
the 129-byte `CATCtorProxyCont` records are **constraint/connector frames**, not
instance placement. Placement is the `8d 81` matrix stream whose attribute header
is the `_Position` attribute. Binding instances to 129-byte records is what the
old gate did on the dual-layer files; it is withdrawn.

---

## 1. The Byte Law

The 4–5 bytes immediately before the `8d 81` marker classify the matrix:

| Attribute header | Class | Meaning |
|---|---|---|
| `e8 f4 07 37` | explicit | explicit instance `_Position` (12-element SO(3)+T stream) |
| `e9 f4 07 04 37` | identity | attribute frame shared by constraint/connector objects; **ordinal placeholder only, never a transform** |
| `e8 e0 07 37` | root | product-root position (excluded from instances) |
| anything else | other | not a `_Position` value (excluded) |

The independent review census found 312 identity-header records; 261 sit under
`CstIndex` / `_hasConnections` / `_AlternateShapeRep`, only 2 under `_Reps`,
with identity rotation 312/312 and zero translation 311/312. The header is an
attribute frame, not an instance position. The law therefore keeps every
identity record in the ordinal sequence (so the following records do not shift)
and writes it as `undecodable` with `transform: None`.

The matrix payload is the already-decoded R15 12-element run-length stream
(`e8`→0.0, `e7`→1.0, `e9`→-1.0, `e6`→f64le); the first 9 values are the row-major
rotation, the last 3 the translation. Every accepted matrix must pass
`det(R)=+1`, unit rows, mutual orthogonality (tolerance `1e-4`), and translation
bounds `|t| <= 1e7` (Python twin included).

**Binding law (accepted only when the counts close):**

| Condition | Binding |
|---|---|
| `explicit == positioned` | bind the explicit records in document order |
| `explicit + identity == positioned` | keep document order; explicit records bind, identity frames stay undecodable placeholders |
| trailing root reference (`main*`) | bind the first `positioned - 1` explicit records; the root reference's own explicit record is excluded by precedence |
| any other count | **undecodable** (never identity) |

The law is a named mode: `position_stream_8d81` (Rust) /
`position_stream_8d81` (Python). It is never silent: the Rust seam emits a
`position-stream-8d81` warning, the Python twin mirrors it, and a mismatch calls
`mark_position_layer_undecodable` (transform `None`). The object→instance join
itself remains unproven at `b3d283f`; this ticket uses the byte-level attribute
header and count law, not the unproven join.

---

## 2. Dual-Layer Files: The Safe A/B

Exactly 10 products carry both layers (129-byte records and `_Position` 8d81
matrices). Only two of them pass the legacy 129-byte gate: **coso**
(`81b1fe655b83f7ee`) and **servo** (`91fe0d674f7c30db`). The other eight are
`connector_proxy_mesh` and were already undecodable; they stay undecodable
because their `_Position` count does not close under the law (see §4).

| File | Inst | 129 B (unit) | explicit | identity | root | Legacy | New | Placed / undecodable |
|---|---:|---:|---:|---:|---:|---|---|---|
| coso `81b1fe65` | 7 | 8 | 6 | 1 | 1 | `root_plus_sequential` | `position_stream_8d81` (document order) | 6 / 1 |
| servo `91fe0d67` | 3 | 2 | 3 | 1 | 0 | `sequential_1to1_root_ref` | `position_stream_8d81` (root ref excluded) | 2 / 1 |

### 2.1 coso — 6 transforms corrected, identity frame stays undecodable

The 129-byte layer put all 7 origins inside a 9.0 mm box with duplicate pairs
(part-local constraint connector points). The explicit `_Position` layer spreads
them to a 65.8 mm assembly, minimum pairwise distance 10.9 mm, no duplicates.
The second 8d81 record is an identity frame: it keeps ordinal position 2 (so
`Part5.1.2` does **not** shift), but it is **never bound**; `Part5.1` is
`undecodable` with `transform: None` (Clause 3).

| Instance | Before (129 B) | After (explicit 8d81) | Δ (mm) |
|---|---|---|---|
| Part4.1 | (0.000, 7.817, -2.500) | (-10.137, 11.301, 2.082) | 11.657 |
| Part5.1 | (0.000, 6.617, -2.500) | **undecodable** (identity frame placeholder) | — |
| Part5.1.2 | (0.000, 3.300, 2.500) | (9.863, 11.301, 6.582) | 13.341 |
| Part7.1 | (0.000, 7.817, -2.500) | (-9.087, 46.186, 11.082) | 41.704 |
| Part7.2 | (0.000, 0.000, 0.000) | (-16.242, -18.609, 2.082) | 24.788 |
| Part5.1.1 | (0.000, 0.000, 2.000) | (-5.721, -6.555, 6.582) | 9.833 |
| Part5.1.1.1 | (0.000, 0.000, 0.000) | (-1.450, 32.127, 6.582) | 32.826 |

Median Δ over the **6 real transforms** = **19.06 mm**. Three of them gain a
non-identity rotation (`Part7.1` and `Part5.1.1.1` at 180° (w=0), `Part7.2` at
41.4°); before, all seven were identity rotations.

### 2.2 servo — 2 transforms corrected; root reference excluded by precedence

| Instance | Before (129 B) | After (8d81) | Δ (mm) |
|---|---|---|---|
| ac2:1 | (12.500, 0.000, 14.400) | (0.000, 0.000, -22.923) | 39.360 |
| ac1:1 | (12.500, 0.000, 16.200) | (43.211, 51.280, 0.000) | 61.929 |

`main:1` **does have an explicit position record**: row 3,
`T=(43.211, 51.280, -1.700)` (`ref[0]+1`). The binding precedence is positional:
rows 1–2 bind the two child instances, row 3 belongs to the root assembly
reference and is left `undecodable` with `transform: None`. The
`classification_detail` states this precedence and the record's translation;
it no longer claims the record is absent.

### 2.3 Corpus A/B (Rust seam, 381 decoded products / 2,475 instances)

| Metric | Before | After |
|---|---:|---:|
| Placed instances | 379 | **378** |
| Identity instances | 91 | **91** |
| Undecodable instances | 2,005 | **2,006** |
| Files with ≥1 placed | 60 | **60** |
| Placement transforms changed | — | **8 real** (coso 6, servo 2) |
| Regressions on the 379 placed | — | **0** |

The only status change is coso `Part5.1` (placed → undecodable identity-frame
placeholder). The other 378 placed instances keep their status; only the 8 real
transform tuples change. No identity class changed, and no previously placed
instance is masked to identity.

**No placement transform is sourced from a 129-byte record after this ticket.**
The two legacy-placed dual-layer files now bind from explicit `_Position`; the
other 58 placed files carry no 129-byte records and already bind from their
`8d 81` matrices (the R15 fallback). The 129-byte scan survives only as the
strict fallback for a hypothetical no-`_Position` file, and no corpus file uses
it for a placement.

**Disclosure — Python ledger.** The Python twin previously bound up to
`min(instances, 129 B records)` without the count gate and ignored
colon-shaped names. Aligning it with Rust changes its ledger independently of
the Rust A/B above: 16 files gain 298 colon-shaped instances; 112 naive
129-byte placements are withdrawn in this tree (the review's independent count
is 108; the delta is the description-block/colon collapse). Before:
2,176 total / 2,084 placed / 91 identity / 1 undecodable. After: 2,474 total /
2,268 placed / 91 identity / 115 undecodable. Python still lacks the R15
matrix fallback, so its corpus-wide ledger is not the Rust ledger; the §2.3 A/B
and §3 counts are **Rust-only**, with Python/Rust parity asserted on the
coso/servo anchors.

---

## 3. The 29 `connector_proxy_mesh` Files

The P2.6 census lists **443 dot names**; the pairing pipeline extracts **440
instances** (3 description-block pairs collapse: `90cac…`, `a1c…`, `2107…`).
The position-layer census covers all 29:

| Rule | Instances |
|---|---:|
| Already placed via the 8d81 R15 fallback (`423778ea`) | 9 |
| Remain **undecodable** after this ticket | 431 |
| New placements from a bare matrix count | **0** |

`423778ea942078e3` (9 instances) keeps its 9 placements: it is bound by the
existing R15 fallback, not by the new law, and its position layer also contains
8 explicit + 1 identity frame. The new identity-placeholder rule is not applied
to modern=0 R15 files in this ticket; re-binding 423 would make its identity
frame undecodable (8 placed), which is a separate change. It is not a regression
here.

**Why the other 431 are not promoted.** A bare count is not attribution. After
removing identity-frame closures, **10 of the 29** files have an
explicit-only count-consistent layer (`explicit == positioned`), covering **95
instances**:

`0d60a2bc` 5, `1b8c4500` 5, `2107dc0a` 9, `2b6c0970` 10, `322c8e13` 10,
`590430c6` 14, `974ef60f` 4, `a5d51be5` 28, `b96ef5f9` 5, `bad5257b` 5.

The previous 15-file/137-instance count included five files that only closed
through identity frames: `2cc002da` (6+1), `9a9d8a85` (12+7), `a1c2956c` (3+1),
and `423778ea` (8+1); `688fa042` is excluded by the review's object→instance
census, which places its 3 explicit-header matrices under representation
attributes (`_Reps`), not `_Position`. Those five no longer count. Promoting the
10 would place **95 instances**, not 128. The record-to-instance **order** is
still unproven (the object→instance join is open at `b3d283f`), so this ticket
does not enable it. The remaining 14 files do not close under the explicit-only
count (`90cac 35/37`, `ff4a 16/2`, `126c 38/31`, `de3c 82/96`, `c79c 12/11`,
`9662 26/15`, `5bb2 11/13`, `d323 20/26`, `eaa7 3/11`, `afe3 7/10`,
`b82b 16/18`, `6c3d 4/19`, `1a25 4/7`, `d852 5/7`).

The 129-byte layer is never used to fill a position for these files. Clause 3
of the P4 bar is preserved: no `_Position` instance is ever written as identity
because its transform was undecoded.

---

## 4. Committed Rows

- `docs/evidence/data/p3-position-layer-files-claims.csv` — 31 rows (29 mesh +
  coso + servo): per-file instance/129 B/explicit/identity/root counts, legacy
  gate, new law, placed/undecodable.
- `docs/evidence/data/p3-position-layer-claims.csv` — 5 claims:
  - **P3PL-1** header law (31/31 files carry classified matrices; 643 valid
    matrices in scope, 415 explicit, 108 identity frames (never bound), 104
    root positions (excluded), 16 outside all headers).
  - **P3PL-2** 129 B and identity frames are constraint/connector layers, not
    placement (10 dual-layer files; the two legacy-placed are `81b1fe65` and
    `91fe0d67`).
  - **P3PL-3** coso 6 + servo 2 real transforms from explicit 8d81 (8/8);
    `Part5.1` identity frame and `main:1` root reference stay undecodable.
  - **P3PL-4** mesh scope: 9 placed / 431 undecodable (440 pipeline instances;
    443 p26 dot names).
  - **P3PL-5** 10/29 explicit-only count-consistent layers (95 instances)
    documented but not enabled; 688 excluded by the review census.

---

## 5. Reproduction

```bash
export LD_LIBRARY_PATH=/usr/lib:$LD_LIBRARY_PATH

# Rust A/B (temporary example; not part of the gate)
cd port
cargo run --quiet --example product_census -- \
  ../manifests/corpus-manifest.csv /path/to/catpart-parser
cargo run --quiet --example product_census -- \
  ../manifests/corpus-manifest.csv /path/to/catpart-parser dump 81b1fe655b83f7ee

# Position-layer census + claims CSVs
python3 -I scripts/triage/p3_position_layer_census.py --selftest
python3 -I scripts/triage/p3_position_layer_census.py --all \
  --corpus /path/to/catpart-parser

# Twin tests
cargo test product::
python3 -m pytest -q tests/test_position_layer.py tests/test_assembly_fixtures.py
```

---

## 6. Gate

`scripts/check.sh` is green: ruff, pytest, claims-CSV quoting, native + wasm32
builds, `cargo fmt --check`, `cargo clippy -D warnings`, `cargo test`,
`wasm-pack build/test`, and `port/pkg` vs `site/viewer/pkg` sync.

---

## 7. Open (documented, not applied)

- The 95-instance promotion on the 10 explicit-only count-consistent mesh files
  stays disabled until each file's `_Position` record order is attributable to
  a named instance by bytes (object→instance join; open at `b3d283f`), not by
  count alone.
- The modern=0 R15 fallback files (including `423778ea`) still use their total
  matrix order, so an identity frame in that layer can bind an instance at
  identity. Applying the placeholder rule to the R15 path is a separate ticket.
- The 129-byte scan remains a strict fallback only when no `_Position` layer
  exists; no current corpus placement comes from it after this ticket.
