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
| `e9 f4 07 04 37` | identity | abbreviated identity instance `_Position` |
| `e8 e0 07 37` | root | product-root position (excluded from instances) |
| anything else | other | not a `_Position` value (excluded) |

The matrix payload is the already-decoded R15 12-element run-length stream
(`e8`→0.0, `e7`→1.0, `e9`→-1.0, `e6`→f64le); the first 9 values are the row-major
rotation, the last 3 the translation. Every accepted matrix must pass
`det(R)=+1`, unit rows, and mutual orthogonality (tolerance `1e-4`).

**Binding law (accepted only when the counts close):**

| Condition | Binding |
|---|---|
| `explicit == positioned` | bind the explicit records in document order |
| `explicit + identity == positioned` | bind all `_Position` records in document order |
| trailing root reference (`main*`) | bind the first `positioned - 1` explicit records; the root reference stays undecodable |
| any other count | **undecodable** (never identity) |

The law is a named mode: `position_stream_8d81` (Rust) /
`position_stream_8d81` (Python). It is never silent: the Rust seam emits a
`position-stream-8d81` warning, the Python twin mirrors it, and a mismatch calls
`mark_position_layer_undecodable` (transform `None`).

---

## 2. Dual-Layer Files: The Safe A/B

Exactly 10 products carry both layers (129-byte records and `_Position` 8d81
matrices). Only two of them pass the legacy 129-byte gate: **coso**
(`81b1fe655b83f7ee`) and **servo** (`91fe0d674f7c30db`). The other eight are
`connector_proxy_mesh` and were already undecodable; they stay undecodable
because their `_Position` count does not close under the law (see §4).

| File | Inst | 129 B (unit) | explicit | identity | root | Legacy | New | Placed |
|---|---:|---:|---:|---:|---:|---|---|---:|
| coso `81b1fe65` | 7 | 8 | 6 | 1 | 1 | `root_plus_sequential` | `position_stream_8d81` (document order) | 7 |
| servo `91fe0d67` | 3 | 2 | 3 | 1 | 0 | `sequential_1to1_root_ref` | `position_stream_8d81` (root ref excluded) | 2 |

### 2.1 coso — 7 transforms corrected

The 129-byte layer put all 7 origins inside a 9.0 mm box with duplicate pairs
(part-local constraint connector points). The `_Position` layer spreads them to
a 65.8 mm assembly, minimum pairwise distance 10.9 mm, no duplicates.

| Instance | Before (129 B) | After (8d81) | Δ (mm) |
|---|---|---|---|
| Part4.1 | (0.000, 7.817, -2.500) | (-10.137, 11.301, 2.082) | 11.657 |
| Part5.1 | (0.000, 6.617, -2.500) | (0.000, 0.000, 0.000) | 7.074 |
| Part5.1.2 | (0.000, 3.300, 2.500) | (9.863, 11.301, 6.582) | 13.341 |
| Part7.1 | (0.000, 7.817, -2.500) | (-9.087, 46.186, 11.082) | 41.704 |
| Part7.2 | (0.000, 0.000, 0.000) | (-16.242, -18.609, 2.082) | 24.788 |
| Part5.1.1 | (0.000, 0.000, 2.000) | (-5.721, -6.555, 6.582) | 9.833 |
| Part5.1.1.1 | (0.000, 0.000, 0.000) | (-1.450, 32.127, 6.582) | 32.826 |

Median Δ = **13.34 mm**. Three instances gain a non-identity rotation
(`Part7.1` and `Part5.1.1.1` at 180° (w=0), `Part7.2` at 41.4°); before, all
seven were identity rotations. The identity record is the **second**
`_Position` record, so it fills `Part5.1` in document order — not an appended
default.

### 2.2 servo — 2 transforms corrected, root reference stays undecodable

| Instance | Before (129 B) | After (8d81) | Δ (mm) |
|---|---|---|---|
| ac2:1 | (12.500, 0.000, 14.400) | (0.000, 0.000, -22.923) | 39.360 |
| ac1:1 | (12.500, 0.000, 16.200) | (43.211, 51.280, 0.000) | 61.929 |

`main:1` is a root assembly reference; it remains `undecodable` with
`transform: None` (no identity masking).

### 2.3 Corpus A/B (Rust seam, 381 decoded products / 2,475 instances)

| Metric | Before | After |
|---|---:|---:|
| Placed instances | 379 | **379** |
| Identity instances | 91 | **91** |
| Undecodable instances | 2,005 | **2,005** |
| Files with ≥1 placed | 60 | **60** |
| Placement transforms changed | — | **9** (coso 7, servo 2) |
| Regressions on the 379 placed | — | **0** |

The per-file placed/identity/undecodable rows are byte-identical before and
after; only the 9 transform tuples change. No identity class changed.

**No placement transform is sourced from a 129-byte record after this ticket.**
The two legacy-placed dual-layer files now bind from `_Position`; the other 58
placed files carry no 129-byte records and already bind from their `8d 81`
matrices (the R15 fallback). The 129-byte scan survives only as the strict
fallback for a hypothetical no-`_Position` file, and no corpus file uses it for
a placement.

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

`423778ea942078e3` (9 instances) keeps its 9 placements: its position layer has
8 explicit + 1 identity = 9, and the existing R15 path already bound the same
9 records in the same order. It is not a new placement and it does not regress.

**Why the other 431 are not promoted.** A bare count is not attribution. 15 of
the 29 files have a count-consistent position layer under `explicit ==
positioned` or `explicit+identity == positioned` (CSV `note` column):
`0d60a2bc`, `1b8c4500`, `2107dc0a`, `2b6c0970`, `2cc002da`, `322c8e13`,
`423778ea`, `590430c6`, `688fa042`, `974ef60f`, `9a9d8a85`, `a1c2956c`,
`a5d51be5`, `b96ef5f9`, `bad5257b`. Enabling the law on those rows would place
**128 additional instances** (9a9d 19, a1c 4, 2107 9, 2cc 7, 688 3, a5d 28,
2b6 10, 590 14, 1b8 5, bad 5, 0d6 5, 974 4, 322 10, b96 5). The record-to-instance **order** is not independently proven there (only coso/servo were
validated against the 129-byte layer and geometry), so this ticket does not
enable it. The 14 remaining files do not close under either count law
(`90cac 36/37`, `ff4a 17/2`, `126c 42/31`, `de3c 106/96`, `c79c 13/11`,
`9662 27/15`, `5bb2 17/13`, `d323 21/26`, `eaa7 12/11`, `afe3 9/10`,
`b82b 17/18`, `6c3d 14/19`, `1a25 8/7`, `d852 10/7`).

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
    matrices in scope = 631 across the 29 mesh files + 12 in coso/servo; 523
    are position records, 104 are root positions (excluded), 16 are outside
    both headers).
  - **P3PL-2** 129 B is constraint/connector, not placement (10 dual-layer
    files, 2 legacy-placed).
  - **P3PL-3** coso 7 + servo 2 bound from 8d81 (9/9).
  - **P3PL-4** mesh scope: 9 placed / 431 undecodable (440 pipeline instances;
    443 p26 dot names).
  - **P3PL-5** 15/29 count-consistent layers documented but not enabled.

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

- The 128-instance promotion on the 15 count-consistent mesh files stays
  disabled until each file's `_Position` record order is attributable to a
  named instance by bytes (object-block/name reference), not by count alone.
- The 129-byte scan remains a strict fallback only when no `_Position` layer
  exists; no current corpus placement comes from it after this ticket.
