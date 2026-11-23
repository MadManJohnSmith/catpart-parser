# Maratón catpart-parser — cierre de la ronda v3 (2026-11-22)

**Estado**: sesión detenida por el usuario. Los workers se paran por **cuota del proveedor Z.AI Start Plan** (`1005 exceed quota limit`) en Gallyfrey, TARDIS y agentvm2. No se cambió de proveedor por directiva explícita.

## Punto de partida y resultado

| Métrica | Baseline `d8554e0` | Cierre |
|---|---:|---:|
| L2 Dev | 82.40% (1,138) | **83.35% (1,146/1,375)** |
| L2 Held-out | 93.44% (57/61) | **93.44% (57/61)** |
| L2 Submarino | 58.92% (446/757) | **92.87% (703/757)** medido por W10; W1-B verificado 683 en `main` |
| `not-manifold` Submarino | 277 | **20** (W10) |
| Open Rate honesto | 97.99% | **97.99%** (el feature tree no cuenta como geometría) |
| Audi R8 (chamfer) | 0.0002 mm | **0.0002 mm** (sin cambio; área 0.8736→0.8775) |
| Dodge | 2.50M tris | **2.50M tris**, pero el par de benchmark es incomparable (×100 unidades, ×10 teselación) |

## Leyes y fixes integrados en `origin/main`

- **W1** anti-half-read u8/u16be (fail-closed).
- **W1-B** segunda lectura multi-región: un token node por período; Submarino 448→683, `not-manifold` 275→40, 0 cambios de clase.
- **W10** extent recovery + seam por rep: 683→703, `not-manifold` 40→20.
- **W4** framing `0x50` (counts u16be, 100/100 cierres) + feature/spec tree honesto (17 tipos) + panel viewer; +1 L2 dev.
- **W9** Ley R: rotación no-identidad count-matched como testigo de placement; MB81 0→2, error 0.000000°.
- **W7-B** parches 001/002/003/004: header fantasma Rust (`head_ia` 1,413/1,413), exact-tiling corto (Motor 23→0, NPart 3→0), tiebreak de ancho (4 fallos oficiales), contadores relaxed.
- **W8** familia `empty-geometry-store` (10/10, fail-closed).
- **W17** contenedor `00 00 00 01` = continuación de raw-array (259 nodos/127 archivos, 100% decode) + split U4 con stat propia.
- **W22** viewer CATIA: vistas estándar, even shading, árbol interactivo, Bodies por union-find.
- **W7** fast engine (0 flips vs Python en 1,824 archivos), `check-fast.sh`, harness de ground truth.

## Evidencia y ramas no integradas

- **W3** E5 B-spline exacta: `marathon/w3-e5-algebra` (`d4a1fbc`). +15 L2 dev esperados, pero su ruta introdujo 2 `pass→fail` por degenerados (`First_Back_Shell`, `backshell_M`); **revertido de main**. **W15** dejó el fix en `marathon/w15-e5-tail` (`408f568`): filtro de degenerados en la ruta de superficie. Pendiente: re-merge y gate.
- **W6** Laya calibrado + top-targets: `marathon/w6-laya-oracle` (`d5975ae`), pendiente de merge (scripts/nota).
- **W11** negativo B8 + scanner: `marathon/w11-analytic-surfaces` (`534c6c2`); mover escáner a `foundation/w11-analytic`, nota/CSV a main.
- **W12** oráculo inverso: `marathon/w12-inverse-oracle` (`f481106`); evidencia + checker CSV + 1 línea en `check.sh`, pendiente.
- **W13** variantes d2d2/3004: integrado (negativo).
- **W18** compuerta half-read: negativo; el parche 003 es la regla correcta.
- **W19** stream-version: `78f01af` (negativo + 2 leyes); escáner a foundation.
- **W20** Dodge: negativo (artefacto del par, no routing); `334b76d`.
- **W16** ley U4: `276aac8`, módulo adoptado por W17.
- **W21/W24/W25** y **W14**: fallaron por cuota; contexto en sus hilos.
- **W23/W26/W27**: W26 entregó taxonomía (211→102 clusters, 0 flips); W23/W27 fallaron por cuota.

## Verificación del cierre

- `origin/main` `8970794` (gate: 1,016 passed + pin test verde; cargo/wasm/node/Playwright verdes).
- Merge local de W17+W22 sobre `8970794`: fast fitness **1,146/1,375 (83.35%)**, held-out 57/61, **0 pass→fail**; cargo 267+6, fmt/clippy limpios, node 6/6, 49 tests dirigidos verdes.
- El pytest completo sobre el árbol W17+W22 no llegó a correr por la detención de la sesión; W17 (977 tests) y W22 (`check.sh` exit 0) tenían gates propios verdes en sus ramas.

## Siguiente sesión

1. Reintentar el pytest completo sobre el árbol final y el probe del Submarino con W17 (W27 quedó sin cuota).
2. Re-merge de W3 + fix de W15 y verificación de los +15 dev (0 regresiones).
3. Merge de la evidencia W6/W11/W12/W19/W20 y las ramas foundation de los escáneres unwired.
4. Reintentar W21/W24/W25/W14 cuando el proveedor reponga cuota.
5. Mantener el criterio: 0 regresiones, 0 fuerá bruta, gates intactos.
