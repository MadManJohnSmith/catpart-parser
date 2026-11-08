# Evidence: container-tree assembly claim tested — parent_name is a class label, not a hierarchy pointer (2026-11-08)

Scope: all 1818 unique `magic_ok` corpus files, 1810 with-table files,
19300 records — the same validated record parse as
`docs/evidence/2026-11-07-container-table-and-trailer.md` (laws T1-T3;
this scan reproduces its per-file record counts and name order exactly,
1818/1818 files). Method: read-only byte scan with
`scripts/triage/verify_container_tree.py` (run with `python3 -I`),
which re-uses the B1 record model and adds the tree-assembly checks;
per-file results in `docs/evidence/data/container-tree-scan.csv`.

Context: ticket #24's owner decision makes the L1 "feature tree" the
container tree assembled from the container-name table records — each
record a node {name, parent_name, table_id, index, guid, weight}, the
hierarchy formed via the parent relation (parent_name) and ordered by
table_id/index. The claim under test was the simple parent_name law:
every file's records form a connected hierarchy rooted at
`AppliCont`/`CATContainer`-style roots via parent_name, i.e. each
record's parent_name resolves to the name1 of another record of the
same file (except roots). parent_name → name1 is the only parent
relation expressible through the name2 field.

## Result: the law fails corpus-wide

- 1699/19300 records (8.8%) have a parent_name matching a same-file
  name1; 17601 (91.2%) do not. No file has all records resolved
  (0/1810); 202/1810 files have zero resolving records; most files
  (1351/1810) carry 9-13 unresolved-parent records (the strict-model
  roots).
- The parent_name vocabulary is exactly **5 values corpus-wide**
  (19300/19300): `CATContainer` 12315 (63.8%), `CATFeatCont` 5026
  (26.0%), `CATProdCont` 1600 (8.3%), `CATSiMuGenCont` 312 (1.6%),
  `CATDrwCont` 47 (0.2%).
- `CATContainer` and `CATFeatCont` — 89.9% of all parent references —
  appear **0 times as name1** corpus-wide (for `CATFeatCont` this is
  the C7 negative of the payload note). They are class labels, not
  records: nearly every record points at a parent that is never a node.
- Where a parent_name does resolve, it always has exactly one candidate
  record (0 ambiguous resolutions corpus-wide) — but 158 of the 1699
  resolving records have their unique candidate strictly *after* them
  in file order, so even the resolving edges are not a consistent
  before-child ordering.
- `name1` is not unique within a file anyway: 138/1810 files repeat a
  name1 value, so name-based node identity is not unique in general
  (it only happens to be, for the names that serve as parents).
- `AppliCont` is not a hierarchy root under this relation: all 1433
  `AppliCont` rows carry parent_name `CATContainer` (unresolved);
  377/1810 files have no `AppliCont` row at all; its position varies
  (first record in 452 files, record 9-16+ in the others).

## What the data actually shows

`name2` behaves as a **base-class/secondary-name annotation** — a small
fixed vocabulary of container class names (`CATContainer`,
`CATFeatCont`, `CATProdCont`, `CATSiMuGenCont`, `CATDrwCont`), mostly
referring to classes that are never instantiated as records — not as a
within-file parent pointer. The container-name table carries no
validated parent-child hierarchy through parent_name; the only
corpus-wide structure laws on the records remain B1's T1-T3 (layout)
plus the kind law K1.

## Corrections to the B1 phrasing (no layout change)

- Table `0x00040001` holds 1441 rows, of which **1198 are the
  `AppliCont` row** and 243 are other containers (`CATProdCont` 99,
  `CATCompoundCont` 62, `CATFeatLocalRef` 21, `CGMGeom` 21, `CATMFBRP`
  18, `CATDrwMirrorCont` 14, ...); "the AppliCont row" described only
  the 1198. Every `AppliCont` row has idx 1.
- `AppliCont` sits in table `0x00040001` in 1198 files (weight 21) and
  in table `0x00030001` in 235 files (weight 11); B1's "weight 21, the
  AppliCont row" covers only the first family. Table `0x00040001`
  carries 2 rows on 20 of the 108 B1 sample files.

## Consequence for ticket #24

The tree-assembly model has no validated basis: per the ticket's stop
rule, no `feature_tree` output, schema change, or invariant was
implemented, and no fitness run was made (no parser change — a run
would only duplicate the standing baseline). Choosing the L1 container
tree's shape (e.g. flat ordered node list with parent_name as an
annotation, or a class-root grouping) is a new model decision that
needs its own documented claim; this note records the measurement it
must start from.

## Reproduction

```
python3 -I scripts/triage/verify_container_tree.py   # tree-law scan CSV + rates
```

The scan is stdlib-only and read-only with respect to the corpus;
runtime is seconds (first 2 MB window per file, as in B1). Its per-file
record counts and name order match `container-table.csv` exactly on all
1818 files (parity checked against the committed B1 CSV).
