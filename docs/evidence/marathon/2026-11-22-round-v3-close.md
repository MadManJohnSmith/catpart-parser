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

- **W3** E5 B-spline exacta: `marathon/w3-e5-algebra` (`d4a1fbc`). +15 L2 dev esperados, pero su ruta introdujo 2 `pass→fail` por degenerados (`First_Back_Shell`, `backshell_M`); revertido initially. **W15** dejó el fix en `marathon/w15-e5-tail` (`408f568`). **Later update 2026-11-23**: W3+W15 re-merged as `04de331`; both parts pass (8,278 / 9,142 tris, 0 degenerates) and the route is in the 2026-11-24 / 2026-11-25 accepted rows. No longer pending.
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
2. W3+W15 ya re-mergeados (`04de331`); no queda re-merge — el gate quedó cubierto por las filas aceptadas 2026-11-24/25.
3. Merge de la evidencia W6/W12/W20 (W11/W19 ya son ancestros de main) y las ramas foundation de los escáneres unwired.
4. Reintentar W21/W24/W25/W14 cuando el proveedor reponga cuota.
5. Mantener el criterio: 0 regresiones, 0 fuerá bruta, gates intactos.

## Known gap (2026-11-25)
`acc-Cont-Lft.CATPart` flips `not-manifold → pass` in W1 and stays in
the 92.87% — but the passing emission is **563 triangles** from node
0's territory, not the body's surface. The store carries 13 token nodes
(12 walk-exact + 1 container); the single-rep reading parses all 142
records against node 0's 220 elements, 96 seam declines + 19 relist
skips force the mix to `manifold = True`, and the W1-B multi-region
route therefore never fires. The per-rep reading is 13 reps / **6,602 triangles** / manifold
/ 0 degenerate / 12 boundary edges. Root cause, reopening criterion and
reproduction: [2026-11-25-acc-cont-lft-single-rep.md](../2026-11-25-acc-cont-lft-single-rep.md).

**Index of unsynthesized findings**: [2026-11-25-unsynthesized-findings.md](../2026-11-25-unsynthesized-findings.md).

**Later update (2026-11-25)**: the open-rate census was re-run over the
current tree: **1,413/1,442 = 97.99%** (1,304 MESH + 109 DISPLAY + 29
BLANK = 19 `missing-geometry-store` + 10 `empty-geometry-store`). The
97.92 % figure shown on the W26 site card was the stale committed CSV;
the fresh probe supersedes it. Against the 2026-11-20 census: 45
DISPLAY→MESH + 1 BLANK→MESH.
