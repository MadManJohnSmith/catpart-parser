# W-C: V5R26 product name tables and `own(D)` attribution (2026-11-21, Python + Rust)

Ticket #68 (parent #50). Diagnosis: `subagents/s3-product-assemblies/informe.md`
(`main` @ `1f752f0`). Probe: `scripts/triage/p29_name_table_walk.py`
(read-only; the snapshot lives outside the repo).

## The blind spot

In the snapshot generation (V5R26, 2018) the structure pool has **one**
`_InstanceName` item in **199/199** `.CATProduct` files and no per-instance
markers. The body is an interned **name table**: the value items are the
names of the components the document lists. All three existing pairing laws
look for per-instance shapes (triples, `_DescriptionInst` blocks, `X.N` /
`X:N`), so 48/199 documents returned `total_instances = 0` and the other 151
returned one spurious triple — the failure is enumeration, not transforms.

## The law landed

Gate (additive; a file the existing laws decode is never re-decided):

```
pool_form == "framed"
∧ "CATMechProdCont" ∉ texts[:24]
∧ "PRDBAGREP" immediately followed by "3DIC" in texts[:22]
∧ len(instances from the marker passes) == 0
```

Enumeration: the value items after the schema head (last schema token in
`texts[:22]`), skipping attribute tokens, class tokens, the V5R26 schema
vocabulary (`ASMProduct`, `_Reps`, `PRDREP`, `TEMP`, `IsRoot`, …), the
document's own `_PartNumber` value, and empty items. Table order is
preserved verbatim: it is **not** an instance order (A1/A3 arrive
alphabetized, B4/B2 in logical order), so no ordinal binding is allowed.

Placement (fail-closed):

| non-root `8d81` records | placement |
|---|---|
| 0 | `identity` at origin, `has_position_attr = false` (`_Position` absent ⟺ 0 records, 199/199) |
| > 0 | `undecodable`, `transform = None`, warning `position-binding-open-v5r26` |

Ownership lives in the walker, which holds the document set:

```
own(D) = [n for n in names(D) if n ∉ ⋃ names(P)]
P over names(D) that resolve to a <name>.CATProduct in the set
```

Measured (snapshot, `--report` + `--tree`):

| | parser instances | tree `own(D)` | identity | undecodable |
|---|---|---|---|---|
| `VM-vela-Mast` | 44 names | 45 | 22 | 23 |
| `MD-MTU-16V-652-MB81` | 185 names | 201 | 145 | 56 |
| all 199 products | 48 documents, 1,568 names | – | – | 694 |

`own(D)` counts against the reference STEP trees: MB81 5/5 distinct children
(the 6th NAUO is a repeated instance the interned table collapses), vela
18/18 (one renamed node: `VM-Mast-Bass-Punta` ↔ `VM-wings-hydraulic`),
MB81-0004 4/4, B4 34/34. The parser-level counts are the table entries, not
the tree; the walker is what restores the 45/201 rows.

## Transforms

The `_Position` layer keeps its existing precedence when instances come from
the marker passes. In the new branch the document-level record set is only
usable as a zero/non-zero signal: vela carries 5 explicit matrices
(`T = (−0.0, −2.241, 2179.457) mm`, its 5 non-identity children), MB81 none
(root `e8 e0 07 37` only). The non-trivial placements of the MB81 tree live
in child documents (`0002`: `−4682.6207 mm` + 180° Z; `0004`: `−80.4429 mm`;
`B4`: `[0, 0.054, −5.5015]`, `0.0098 rad X`), composed when the tree is
nested. Record count is not a gate: 0001/0003 carry one record with no
non-identity node in the STEP.

## Parity and tests

* Python: `fixtures_assembly.read_product_name_table`,
  `own_instance_names`, `resolve_owned_assembly`, branch in
  `read_product_structure`.
* Rust: `port/src/product/{pairing,binding,ownership}.rs`
  (`read_name_table`, `extract_name_table_instances`, `bind_name_table`,
  `own_children`, `resolve_owned_assembly`); parity measured on the same two
  roots (44/185 parser, 45/201 tree, 22/23 and 145/56).
* Tests: `tests/test_product_name_table.py` (synthetic V5R26 fixtures:
  enumeration order, identity vs undecodable, gate negatives, additivity,
  ownership walk) plus native Rust unit tests. The fixture and `_Position`
  suites stay green (`COSO` 7 and `SERVO` 3 instances keep the gate
  unreachable for the 4 canonical fixtures).

## Open

* The interned table loses multiplicity: MB81's 214 NAUO collapse to 201
  distinct names; no pool signal says how many instances a name holds.
* Renamed instances are invisible to the pairing: a name resolves to a file
  by construction, but the document it references cannot be validated
  without the binary reference layer.
* `#records > 0` at document level remains unbound (the table order is not
  an instance order); only the zero case is demonstrably identity.
