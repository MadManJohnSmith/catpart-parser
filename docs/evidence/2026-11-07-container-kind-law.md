# Evidence: container-kind law — the name table decides part vs product (2026-11-07)

Scope: all 1818 unique `magic_ok` corpus files, as decoded by
`scripts/triage/decode_container_table.py`
(`docs/evidence/data/container-table.csv`). Method: read-only
cross-tabulation of two independently produced committed artifacts —
the Phase 0 manifest's `kind` column (part/product, recorded from each
file's source path and `.CATPart`/`.CATProduct` extension before any
byte parsing) and the container-name table records decoded in
`docs/evidence/2026-11-07-container-table-and-trailer.md` (the records'
`name1` values, its `names` column). Reproduce with
`python3 -I scripts/triage/verify_kind_law.py`. All numbers below are
that script's output.

## Law K1 (kind from table names)

Among the 1810 files whose container-name table was found, with zero
disagreements:

- `CATPrtCont` among the records' `name1` values <=> manifest kind
  `part` — 1436/1436 parts.
- `CATProdCont` among the `name1` values, with no `CATPrtCont`,
  <=> manifest kind `product` — 374/374 products (`CATMechProdCont`
  also appears in the table of some products and of 2 parts that carry
  `CATPrtCont`; it never appears without one of the two above).

Both directions hold: no part lacks `CATPrtCont`, no product carries
it, and every with-table file carries at least one of the two. The
manifest's `kind` labeling is independent of the byte parse (it comes
from the download path), so the agreement is a genuine correlation, not
a restatement.

*Interpretation (inference, consistent with the CAA concepts the Phase 1
note references): `CATPrtCont` is a part document's root container and
`CATProdCont` a product document's; a file whose table names the part
container is a part.* The law as stated is a byte-level fact for this
corpus; a counterexample file would be new evidence.

## Files without a table

The 8 files with no parsed table (see the "No table at all" exception
family in the container-table evidence note) are excluded from K1: 6
manifest-`product` and 2 manifest-`part`, all `unknown` version. The
table gives no kind evidence for them; K1 yields `unknown`.

## Reproduction

```
python3 -I scripts/triage/verify_kind_law.py
```
