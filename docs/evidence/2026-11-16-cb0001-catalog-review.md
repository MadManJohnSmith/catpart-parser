# CB0001 Catalog Census: Independent Verification Report (2026-11-16)

**Target Ticket**: Phase 6 Follow-on Decode Lead: CB0001 Catalog Census (#46 / Spec F #45).  
**Committed Target**: [`6e39608`](file:///home/alan/Documents/Repos/catpart-parser/docs/evidence/2026-11-16-cb0001-catalog-census.md)  
**Deliverable Verified**: [docs/evidence/2026-11-16-cb0001-catalog-census.md](file:///home/alan/Documents/Repos/catpart-parser/docs/evidence/2026-11-16-cb0001-catalog-census.md), [scripts/triage/p6_cb0001_catalog_census.py](file:///home/alan/Documents/Repos/catpart-parser/scripts/triage/p6_cb0001_catalog_census.py), [docs/evidence/data/p6-cb0001-catalog-claims.csv](file:///home/alan/Documents/Repos/catpart-parser/docs/evidence/data/p6-cb0001-catalog-claims.csv), and [docs/evidence/data/p6-cb0001-catalog-files-claims.csv](file:///home/alan/Documents/Repos/catpart-parser/docs/evidence/data/p6-cb0001-catalog-files-claims.csv).  
**Review Method**: Independent verification walker (`scripts/triage/test_cb0001_review_independent.py`) written without importing the child decoder.

---

## 1. Executive Summary & Verdict

### Verdict: **PASS**

All 12 claims (P6-CB-1 through P6-CB-12) and the mathematical laws governing the `CB0001` body catalog are verified with 100% agreement across the corpus:
1. **Population (Claim P6-CB-1)**: Exactly **44 of 382 product files** carry an embedded body `CB0001` catalog in `[0, dword8)`. All 44 belong to legacy generations (`unknown`: 39, `R16`: 4, `R15`: 1).
2. **Dual-Region Class (Claim P6-CB-3)**: 100% (44/44) of body catalog files have `has_ff8 == False` (the legacy dual-region header structure).
3. **Header Offset Law H2 (Claim P6-CB-2)**: `catalog_offset == header.dword16` on **44/44 (100.0%)**.
4. **Header Span Law (Claim P6-CB-6)**: `val2 == dword16 + dword20` on **44/44 (100.0%)**, confirming that `dword20` is the exact byte allocation for the catalog region.
5. **Counter Law (Claim P6-CB-5)**: `cntB == cntA + 1` on **44/44 (100.0%)**.
6. **Physical Region Tiling (Claim P6-CB-8)**: `min(X) == 64` and `max(X + Y) == dword16` on **44/44 (100.0%)**, proving the body catalog functions as a physical storage directory for all blocks written prior to the catalog itself.
7. **Negative Assembly Semantics (Claim P6-CB-11)**: Mechanically swept across all 44 catalogs: **0/44** contain instance tokens (`_InstanceName`, `_Position`, `_Component`, `_PartNumber`).
8. **Carrier Overlap (Claim P6-CB-12)**: Only 1 of 40 placed ctorproxy transform files (`fad540f761d4eebd`, 2 records) overlaps with the `CB0001` class.

---

## 2. Independent Verification Results

| Claim | Topic | Expected | Independent Walker | Agreement |
|---|---|---|---|---|
| **P6-CB-1** | Population with body CB0001 | 44 | 44 | 100.0% |
| **P6-CB-2** | Catalog offset == dword16 | 44/44 | 44/44 | 100.0% |
| **P6-CB-3** | `has_ff8 == False` | 44/44 | 44/44 | 100.0% |
| **P6-CB-5** | `cntB == cntA + 1` | 44/44 | 44/44 | 100.0% |
| **P6-CB-6** | `val2 == d16 + d20` | 44/44 | 44/44 | 100.0% |
| **P6-CB-8** | `min(X)==64, max(X+Y)==d16` | 44/44 | 44/44 | 100.0% |
| **P6-CB-11**| Assembly semantic negative | 0/44 | 0/44 | 100.0% |

- `p6_cb0001_catalog_census.py --selftest`: **PASS** (8 synthetic tests).
- `check_claims_csv_quoting.py`: **47 claims CSVs checked, 12,646 rows, 0 shifted**.
- `pytest`: **381 passed, 7 skipped**.
- `ruff`: clean.
