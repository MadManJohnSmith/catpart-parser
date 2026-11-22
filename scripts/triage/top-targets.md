# W6 top targets — residual ROI ranking (ronda v3)

Source: 2199 labeled parts (official corpus + Submarino), baseline d8554e0. Rank = archivos x triangulos of the cluster; zero-mesh clusters use bytes as the proxy. Hypotheses are starting points, not verdicts.

| # | familia | version | archivos | triángulos | bytes | ROI | hipótesis sugerida |
|---|---------|---------|----------|-----------:|------:|----:|--------------------|
| 1 | fail-unclassified | unknown | 366 | 1093262 | 529654636 | 400133892 | failures with no named reason: run the per-file check harness and name the family before routing |
| 2 | check:not-manifold | unknown | 357 | 712941 | 249895089 | 254519937 | manifold/sewing law on kept-degenerate + duplicate-triangle stores; verify the L1.1 crease/edge vote on the top files |
| 3 | check:empty-mesh | V5R24 | 1 | 0 | 237851950 | 237851950 | surface decode for display-only stores: bag-rep count-framed f32 arrays + 3X record centers already carry points; find the triangle law |
| 4 | check:empty-mesh | unknown | 160 | 0 | 30809525 | 30809525 | surface decode for display-only stores: bag-rep count-framed f32 arrays + 3X record centers already carry points; find the triangle law |
| 5 | check:empty-mesh | V5R20 | 6 | 0 | 7077967 | 7077967 | surface decode for display-only stores: bag-rep count-framed f32 arrays + 3X record centers already carry points; find the triangle law |
| 6 | check:empty-mesh | V5R21 | 8 | 0 | 4526242 | 4526242 | surface decode for display-only stores: bag-rep count-framed f32 arrays + 3X record centers already carry points; find the triangle law |
| 7 | check:empty-mesh | V5R19 | 15 | 0 | 2429982 | 2429982 | surface decode for display-only stores: bag-rep count-framed f32 arrays + 3X record centers already carry points; find the triangle law |
| 8 | error:missing-geometry-store | unknown | 19 | 0 | 1548458 | 1548458 | container walk misses a geometry store: verify the store-kind law on the file's container table |
| 9 | error:no-evaluable-surface | unknown | 1 | 0 | 1411684 | 1411684 | surface decoded but outside evaluable tolerance: check PLANE_TOL law on the failing store |
| 10 | check:empty-mesh | V5R18 | 15 | 0 | 973214 | 973214 | surface decode for display-only stores: bag-rep count-framed f32 arrays + 3X record centers already carry points; find the triangle law |
| 11 | check:empty-mesh | V5R16 | 8 | 0 | 889343 | 889343 | surface decode for display-only stores: bag-rep count-framed f32 arrays + 3X record centers already carry points; find the triangle law |
| 12 | check:degenerate-triangles | unknown | 19 | 43317 | 33701012 | 823023 | degenerate-triangle emission guard: vertex-pool pairing on the failing stores |
| 13 | check:empty-mesh | V5R17 | 6 | 0 | 492409 | 492409 | surface decode for display-only stores: bag-rep count-framed f32 arrays + 3X record centers already carry points; find the triangle law |
| 14 | error:undecoded-variant | unknown | 6 | 0 | 474833 | 474833 | undecoded container/record variant: byte-diff one file against a passing sibling of the same version family |
| 15 | error:undecoded-variant | V5R21 | 5 | 0 | 304464 | 304464 | undecoded container/record variant: byte-diff one file against a passing sibling of the same version family |
| 16 | check:degenerate-triangles | V5R21 | 1 | 224435 | 190164863 | 224435 | degenerate-triangle emission guard: vertex-pool pairing on the failing stores |
| 17 | check:empty-mesh | V5R15 | 4 | 0 | 169788 | 169788 | surface decode for display-only stores: bag-rep count-framed f32 arrays + 3X record centers already carry points; find the triangle law |
| 18 | check:empty-mesh | V5R23 | 1 | 0 | 60949 | 60949 | surface decode for display-only stores: bag-rep count-framed f32 arrays + 3X record centers already carry points; find the triangle law |
| 19 | check:not-manifold | V5R21 | 3 | 19789 | 51973557 | 59367 | manifold/sewing law on kept-degenerate + duplicate-triangle stores; verify the L1.1 crease/edge vote on the top files |
| 20 | check:not-manifold | V5R20 | 1 | 59188 | 113221986 | 59188 | manifold/sewing law on kept-degenerate + duplicate-triangle stores; verify the L1.1 crease/edge vote on the top files |
| 21 | check:degenerate-triangles | V5R19 | 1 | 51369 | 2235204 | 51369 | degenerate-triangle emission guard: vertex-pool pairing on the failing stores |
| 22 | check:not-manifold | V5R24 | 1 | 2975 | 3925829 | 2975 | manifold/sewing law on kept-degenerate + duplicate-triangle stores; verify the L1.1 crease/edge vote on the top files |

## Top archivos dentro de los 3 clusters de mayor ROI

### fail-unclassified (unknown)

| archivo | bytes | triángulos | warnings |
|---------|------:|-----------:|----------|
| Submarine-Tr-1700-S42-Catia/ST-eskel-sup-T224.CATPart | 3004500 | 297048 | bspline-surface-tessellated, open-shell |
| Submarine-Tr-1700-S42-Catia/MD-Checker-plate-mtu-03.CATPart | 8638718 | 33084 | open-shell |
| Submarine-Tr-1700-S42-Catia/MD-Checker-plate-mtu-04.CATPart | 8626087 | 24682 | extended-header-geometry-declined, open-shell |
| Submarine-Tr-1700-S42-Catia/MD-Checker-plate-mtu-02.CATPart | 7199395 | 29404 | open-shell |
| Submarine-Tr-1700-S42-Catia/MD-Checker-plate-mtu-01.CATPart | 7244375 | 26842 | open-shell |
| Submarine-Tr-1700-S42-Catia/MD-Charge-air line-A1.CATPart | 1628503 | 40960 | bspline-surface-tessellated, open-shell |
| Submarine-Tr-1700-S42-Catia/MD-Charge-air line-A3.CATPart | 1596933 | 40960 | bspline-surface-tessellated, open-shell |
| Submarine-Tr-1700-S42-Catia/MD-Charge-air line-B2.CATPart | 1524978 | 40960 | bspline-surface-tessellated, open-shell |
| Submarine-Tr-1700-S42-Catia/MD-Charge-air line-B4.CATPart | 1493247 | 40960 | bspline-surface-tessellated, open-shell |
| Submarine-Tr-1700-S42-Catia/VM-exhaust-gas-YL.CATPart | 776602 | 74432 | bspline-surface-tessellated, open-shell |

### check:not-manifold (unknown)

| archivo | bytes | triángulos | warnings |
|---------|------:|-----------:|----------|
| Submarine-Tr-1700-S42-Catia/BW-tank-ballast-bow-YL.CATPart | 4002351 | 16316 | curve-entry-loops-exported-dup-pin, curve-entry-loops-unexported, degenerate-triangles-skipped |
| Submarine-Tr-1700-S42-Catia/MB-Frames-middle-centr-YR.CATPart | 1330160 | 40725 | duplicate-triangles-dedup-declined, extended-header-geometry-declined, open-shell |
| Submarine-Tr-1700-S42-Catia/MD-Frames-middl-diesl-YL.CATPart | 1329520 | 40742 | duplicate-triangles-dedup-declined, extended-header-geometry-declined, open-shell |
| Submarine-Tr-1700-S42-Catia/MB-Frames-middle-centr-YL.CATPart | 1323822 | 40893 | degenerate-triangles-skipped, duplicate-triangles-dedup-declined, extended-header-geometry-declined |
| Submarine-Tr-1700-S42-Catia/MD-Frames-middl-diesl-YR.CATPart | 1326686 | 40742 | duplicate-triangles-dedup-declined, extended-header-geometry-declined, open-shell |
| Submarine-Tr-1700-S42-Catia/MD-cobre-co-C2K.CATPart | 4400513 | 9736 | degenerate-triangles-skipped, duplicate-triangles-dedup-declined, extended-header-geometry-declined |
| Submarine-Tr-1700-S42-Catia/MD-cobre-co-B2.CATPart | 4400509 | 9736 | degenerate-triangles-skipped, duplicate-triangles-dedup-declined, extended-header-geometry-declined |
| Submarine-Tr-1700-S42-Catia/MD-cobre-co-A2.CATPart | 4401153 | 9732 | degenerate-triangles-skipped, duplicate-triangles-dedup-declined, extended-header-geometry-declined |
| Submarine-Tr-1700-S42-Catia/BW-tank-ballast-bow-YR.CATPart | 4335861 | 9867 | degenerate-triangles-skipped, duplicate-triangles-dedup-declined, extended-header-geometry-declined |
| Submarine-Tr-1700-S42-Catia/MB-Torpedo-rail-Bow-YR Geometry.CATPart | 3107023 | 10055 | curve-entry-loops-exported-dup-pin, curve-entry-loops-unexported, degenerate-triangles-skipped |

### check:empty-mesh (V5R24)

| archivo | bytes | triángulos | warnings |
|---------|------:|-----------:|----------|
| model/PalmDown5motors2.CATPart | 237851950 | 0 | no-surface-display |

