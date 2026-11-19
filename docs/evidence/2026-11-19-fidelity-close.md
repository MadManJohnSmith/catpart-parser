# Viewer fidelity close-out — what was fixed and what is a documented negative

**Date**: 2026-11-19
**Status**: CLOSED for the reachable scope. Every remaining family is a documented negative with published evidence and a reopen criterion; the exact-B-rep payload is an open-ended RE problem, not a missing fix.
**Ticket**: #50 (post-v1.0 fidelity)
**Starting point**: the owner reported that files could not be viewed faithfully. The audit measured L2-pass parts decoding **3%** and **41%** of their surface, a 0-triangle file shown as a successful load, and 321/1,436 parts with no triangles.

---

## 1. What changed

| Law | Effect | Evidence |
| :--- | :--- | :--- |
| **Per-loop weld with a manifold guard** | `labios/main` 2,299 → **5,410 mm² (96.6%)**; 702/703 gains kept, 0 manifold regressions | `2026-11-18-composite-loop-weld.md` |
| **Extended-header facet family** (`ty` soup + `b3` strips + `b4` fans, escaped counts), gated on manifold assembly | `Gabarit_trou_alu_alpha` 402 → **27,082 mm² (94.5%)**, closed, 0 boundary, 0 unused; 559 pass on the 581 carriers | `2026-11-18-extended-header-family.md` |
| **`0x49` short-form family** (`n == 3*ty`, no count table) | `gopro3` and `Tornillo 996r` recovered; 270,270/270,270 loops coplanar | `2026-11-18-composite-0x49.md` |
| **Primary-emit seam guard** (tiny loops only, 1% threshold) | 15 parts flip to manifold; +0.94 pp dev; no surface loss beyond 0.76% | `2026-11-18-primary-emit-seam.md` |
| **Coordinate-duplicate dedup** | `Test_trappe` manifold with unique-facet area unchanged (6e-12) | `2026-11-18-coordinate-duplicate-dedup.md` |
| **B3 rep-node pairing** | `TolerantSweepDev0/1` and `CAAGsiStartVolumeForBoolean` recovered (24 / 32 / 554 triangles); 2 further stores become manifold | `2026-11-18-b2-b3-variant-parts.md` |
| **`_Position` placement layer** | placement is the `8d81` stream with the explicit header; 8 real transforms corrected (coso 6, servo 2), the identity header is a constraint frame and never places | `2026-11-18-p3-position-layer-segmentation.md` |
| **Viewer honesty** | a 0-triangle decode fails with a named reason instead of a blank "loaded" canvas | `viewer.js`, `test_viewer_empty_mesh.py` |
| **Fidelity harness** | area, pool use, boundary edges and screenshots per file; the proxy is explicitly not ground truth | `2026-11-18-viewer-fidelity-audit.md` |

**Fitness**: L2 Dev **74.80% → 78.64%** (1,086/1,381), held-out **56/61 → 57/61**, L1 flat, L3 23/23. Accepted rows `20261118T232016Z-64b2a1`, `20261119T022504Z-a9bda9` and `20261119T035609Z-7dc3ea`; published to gh-pages.

## 2. What remains — documented negatives

Measured on the 1,436 parts (the 6 `magic_ok=no` misfits excluded):

| Family | Parts | Why it cannot be fixed here | Reopen criterion |
| :--- | ---: | :--- | :--- |
| `undecoded-variant`, no vertex pool | 128 | no tessellation is stored; `CGMGeom` is an identity/object dictionary with **0** knot/weight signatures and the record grid does not tile (0/128 exact); exact geometry would have to come from the pre-CGM bulk (11.17 MB here, 337 MB deep) | a committed grammar for the bulk stream (the CGM grid probe's smallest next step) |
| `undecoded-variant`, packing family | 13 | the mixed-write float-stream packing law is unsolved; the committed family ceiling is ≈0 payoff (0 of 13 recoverable today) | a new packing hypothesis that survives the all-nice + exact-walk gates |
| `missing-geometry-store` | 119 | no `V5_CFV2` header is reachable by any probe; these are catalogs/products without the part store | a locator for the CB0001 catalog family |
| `empty-mesh`, no facet record | 27 | the store genuinely carries no surface carrier (55-file family verified candidate-by-candidate); the geometry is edges/curves only | a decoded exact surface payload (the bulk RE above) |
| `not-manifold`, large over-uses | 6 | the over-use is in the bytes (content fins / rep re-listing); dropping the loops costs 1.1–53.9% of the part's area | a law that resolves the over-use without deleting surface (edge split per sheet is fail-closed against) |
| `degenerate-triangles` | 2 | 3 zero-cross slivers trip the strict `MAX_DEGENERATE_TRIANGLES = 0` gate (0.0096% of the mesh) | a relative degenerate cap, a gate-policy decision, not a decode fix |
| Connector-file instances | 431 | the `_Position`→instance join is not in the bytes (2,226/3,016 have no reference; H1 is serialization adjacency, H2/H3 have none); a guessed order would be identity masking | an object-level join key, or a geometric acceptance that pins the pairing |
| Identity/undecodable instances | 1,517 | no count-consistent `_Position` binding; Clause 3 forbids identity fallback | the same join, or a per-file evidence map |
| Exact solids (STEP) | 1,442 | exact mode requires the loop-segment B-rep pairing law (0/76 corpus shells) and the exact payload is not decoded | bulk/exact-model decode |

The eight frozen-denominator cells without a generator remain disclosed in
`docs/agents/br6-vocabulary-provenance.md`; the L3 headline does not rest on them.

## 3. What is no longer claimed

- The viewer is **not** a faithful CAD reproduction; it renders the decoded tessellation, now with a measured coverage harness and explicit failure states.
- Exact STEP is **0/1,442**; the shipped STEP is the faceted subset.
- The corpus rate (21,659/33,166) is reported and never gates.

## 4. Reproduce

```bash
export LD_LIBRARY_PATH=/usr/lib:${LD_LIBRARY_PATH:-}
.venv/bin/python scripts/triage/measure_viewer_fidelity.py --help   # per-file coverage
.venv/bin/catpart-fitness                                          # acceptance row
bash scripts/check.sh
```
