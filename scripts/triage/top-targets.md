# W6 top targets — residual ROI ranking (ronda v3)

Source: 2199 labeled parts (official corpus + Submarino), baseline d8554e0. Rank = archivos x triangulos of the cluster; zero-mesh clusters use bytes as the proxy. Hypotheses are starting points, not verdicts.

| # | familia | version | archivos | triángulos | bytes | ROI | hipótesis sugerida |
|---|---------|---------|----------|-----------:|------:|----:|--------------------|
| 1 | check:not-manifold | unknown | 357 | 712941 | 249895089 | 254519937 | manifold/sewing law on kept-degenerate + duplicate-triangle stores; verify the L1.1 crease/edge vote on the top files |
| 2 | check:empty-mesh | V5R24 | 1 | 0 | 237851950 | 237851950 | surface decode for display-only stores: bag-rep count-framed f32 arrays + 3X record centers already carry points; find the triangle law |
| 3 | check:empty-mesh | unknown | 160 | 0 | 30809525 | 30809525 | surface decode for display-only stores: bag-rep count-framed f32 arrays + 3X record centers already carry points; find the triangle law |
| 4 | check:empty-mesh | V5R20 | 6 | 0 | 7077967 | 7077967 | surface decode for display-only stores: bag-rep count-framed f32 arrays + 3X record centers already carry points; find the triangle law |
| 5 | check:empty-mesh | V5R21 | 8 | 0 | 4526242 | 4526242 | surface decode for display-only stores: bag-rep count-framed f32 arrays + 3X record centers already carry points; find the triangle law |
| 6 | check:empty-mesh | V5R19 | 15 | 0 | 2429982 | 2429982 | surface decode for display-only stores: bag-rep count-framed f32 arrays + 3X record centers already carry points; find the triangle law |
| 7 | error:missing-geometry-store | unknown | 19 | 0 | 1548458 | 1548458 | container walk misses a geometry store: verify the store-kind law on the file's container table |
| 8 | error:no-evaluable-surface | unknown | 1 | 0 | 1411684 | 1411684 | surface decoded but outside evaluable tolerance: check PLANE_TOL law on the failing store |
| 9 | check:empty-mesh | V5R18 | 15 | 0 | 973214 | 973214 | surface decode for display-only stores: bag-rep count-framed f32 arrays + 3X record centers already carry points; find the triangle law |
| 10 | check:empty-mesh | V5R16 | 8 | 0 | 889343 | 889343 | surface decode for display-only stores: bag-rep count-framed f32 arrays + 3X record centers already carry points; find the triangle law |
| 11 | check:degenerate-triangles | unknown | 19 | 43317 | 33701012 | 823023 | degenerate-triangle emission guard: vertex-pool pairing on the failing stores |
| 12 | check:empty-mesh | V5R17 | 6 | 0 | 492409 | 492409 | surface decode for display-only stores: bag-rep count-framed f32 arrays + 3X record centers already carry points; find the triangle law |
| 13 | error:undecoded-variant | unknown | 6 | 0 | 474833 | 474833 | undecoded container/record variant: byte-diff one file against a passing sibling of the same version family |
| 14 | error:undecoded-variant | V5R21 | 5 | 0 | 304464 | 304464 | undecoded container/record variant: byte-diff one file against a passing sibling of the same version family |
| 15 | check:degenerate-triangles | V5R21 | 1 | 224435 | 190164863 | 224435 | degenerate-triangle emission guard: vertex-pool pairing on the failing stores |
| 16 | check:empty-mesh | V5R15 | 4 | 0 | 169788 | 169788 | surface decode for display-only stores: bag-rep count-framed f32 arrays + 3X record centers already carry points; find the triangle law |
| 17 | check:empty-mesh | V5R23 | 1 | 0 | 60949 | 60949 | surface decode for display-only stores: bag-rep count-framed f32 arrays + 3X record centers already carry points; find the triangle law |
| 18 | check:not-manifold | V5R21 | 3 | 19789 | 51973557 | 59367 | manifold/sewing law on kept-degenerate + duplicate-triangle stores; verify the L1.1 crease/edge vote on the top files |
| 19 | check:not-manifold | V5R20 | 1 | 59188 | 113221986 | 59188 | manifold/sewing law on kept-degenerate + duplicate-triangle stores; verify the L1.1 crease/edge vote on the top files |
| 20 | check:degenerate-triangles | V5R19 | 1 | 51369 | 2235204 | 51369 | degenerate-triangle emission guard: vertex-pool pairing on the failing stores |
| 21 | check:not-manifold | V5R24 | 1 | 2975 | 3925829 | 2975 | manifold/sewing law on kept-degenerate + duplicate-triangle stores; verify the L1.1 crease/edge vote on the top files |

## Top archivos dentro de los 3 clusters de mayor ROI

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

### check:empty-mesh (unknown)

| archivo | bytes | triángulos | warnings |
|---------|------:|-----------:|----------|
| sample/CAACATIAV4Interfaces.edu/CNext/resources/graphic/MigrationReportExtraction/attribut.CATPart | 40801 | 0 | no-surface-display |
| sample/CAACATIAApplicationFrm.edu/InputData/CAACafSearch.CATPart | 120733 | 0 | no-surface-display |
| online/CAAScdPriUseCases/samples/CAAPriChangeHole.CATPart | 358504 | 0 | no-surface-display |
| sample/CAAMechanicalModeler.edu/InputData/CAAAxisSystemCreation.CATPart | 69962 | 0 | no-surface-display |
| online/CAAScdMatUseCases/samples/Part1.CATPart | 77989 | 0 | no-surface-display |
| online/CAAScdDmuUseCases/samples/rod_3d.CATPart | 137092 | 0 | no-surface-display |
| sample/CAAMechanicalModeler.edu/InputData/CAACombinedCurveWithBackup.CATPart | 65292 | 0 | no-surface-display |
| sample/CAAProductStructure.edu/CNext/resources/graphic/CAAPstBrowseImpSample.CATPart | 60781 | 0 | no-surface-display |
| online/CAAScdDmuUseCases/samples/skeleton.CATPart | 81012 | 0 | no-surface-display |
| sample/CAAElecHarnessItf.edu/CNext/resources/graphic/CAA_EHIMultiSegmentSample/Battery6Volts.CATPart | 133074 | 0 | no-surface-display |

