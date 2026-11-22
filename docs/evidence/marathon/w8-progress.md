# W8 — unclassified (ola 4, modo continuo)

**Branch**: `marathon/w8-unclassified` (base dae7dd1). **Host**: agentvm2.
**Anti-OOM**: `CARGO_BUILD_JOBS=1 RUSTFLAGS="-C debuginfo=0"`; sweep con
guard de tamaño (>50 MB → veredicto del reporte comprometido, nunca 2
.CATPart >15 MB en RAM); `free -m` antes de cada job pesado.
**Evidence note**: [2026-11-22-w8-unclassified.md](../2026-11-22-w8-unclassified.md).

## Objetivo del brief y lo que la evidencia dijo

El Top-1 de W6 (366 `fail-unclassified`, 1.09M triángulos, 529 MB) venía
del bench W1-era del Submarino (`m1_files.csv`), cuyas filas no llevaban
columnas de naming. En base dae7dd1 el harness nombra TODA falla
(`error_class`/`failed_check`) y la etiqueta da **0 filas** en ambos
corpora — verificado por 4 vías independientes (nota §1). El Top-1 ya
estaba cosechado: su masa vive hoy en familias nombradas
(not-manifold → W1-B, empty-mesh → W3, degenerate → facets,
missing-geometry-store → negativo cerrado CATCGRCont).

## H1 — censo + taxonomía por firma binaria — LANDED

- `scripts/triage/w8_unclassified_census.py` (stdlib, streaming, mmap
  plano anti-OOM): modo `census` (ley fail_family sobre CSVs/reports
  comprometidos → `data/w8-unclassified-census.csv`, 3,713 filas,
  0 unclassified) y modo `taxonomy` (firma binaria del brief: versión +
  forma de tabla de contenedores + firma de cada store localizado con
  caminata fiel a `_export_store_data` →
  `data/w8-unclassified-clusters.csv`).
- Taxonomía corpus-wide: **1,435 archivos → 725 clusters** (1,380 del
  corpus oficial descargado + 55 del subset W5 Submarino; el snapshot
  3.5 GB NO está en este host — Open question). Top fracasos = singles
  W1-B (degenerate 224K tris, not-manifold ×4). Descarga: 1,755
  verificados / 69 hash-mismatch (repos terceros cambiados; no
  escritos) / 1 fallo.

## H2 — familia `empty-geometry-store` (cluster top en territorio W8) — LANDED

- Firma: store localizado+validado (N2/N6) cuyo cuerpo no lleva
  NINGÚN marcador de payload pinneado (0 pool groups, 0 wrappers,
  0 facet candidates). Cuerpos medidos: 648–2,575 B, 10/10 archivos
  oficiales `error:undecoded-variant` (fixtures CAA sin sólido
  teselado en el store).
- Ley fail-closed en `src/catpart/geometry/unclassified.py` + gemelo
  `port/src/geometry/unclassified.rs`, wiring mínimo en el brazo
  no-pool de `export.{py,rs}`: cualquier marcador mantiene
  `undecoded-variant` verbatim; la ruta stage-13 no se toca (los
  exports quedan row-identical).
- **Flip: 10/10** `error:undecoded-variant` → `error:empty-geometry-store`
  (rerun first-hand de los diez). `LS-seg-22` (el único del Submarino)
  no está en disco: fail-closed mantiene su clase de base; reopen con
  la misma herramienta cuando haya snapshot.
- Paridad: fixture `geometry-empty-body` en el pin fidelity — la fila
  Python ≡ Rust (misma clase de rechazo), vocabulario fijado en
  `test_port_fidelity.py` + `errors.rs`. Tasa por claim: 10/10 oficial,
  1/1 pendiente de bytes.

## Gates (0 regresiones)

- ruff check . verde; pytest -q: 972 passed, 22 skipped (1 proceso).
- cargo: fmt --check, clippy -D warnings, test (230 lib + integración),
  build wasm32 limpio. Sin wasm-pack (prohibido en el brief; los pasos
  de artefacto embebido quedan para CI).
- Sweep corpus-wide en HEAD contra el reporte d2c9ff por sha256
  (`data/w8-corpus-sweep-w8.csv`): 1,380 unidos, 1,369 idénticos,
  10 moves = exactamente los flips, 1 artefacto del umbral del script
  de medición (gate `MAX_DEGENERATE_TRIANGLES = 0`, counts idénticos)
  — **0 regresiones de clasificación**. Resultado en la nota §4.

## Negativos

- El Top-1 literal ya no existe en base — hipótesis "quedan 366 sin
  nombre" cerrada como NEGATIVA con 4 vías de evidencia y criterio de
  reapertura (cualquier fila futura status≠pass sin error_class ni
  failed_check).
- CATCGRCont / quadrics / círculos 33 37 / 0x49 >65,535 / escape P1g /
  jev zero-shot: no tocados (negativos cerrados del coordinador).
- Taxonomía Submarino-wide y el flip de LS-seg-22: PENDIENTES por falta
  del snapshot en este host (gap de host, no de análisis).
