# W4 progress — bag-rep carriers + honest BLANK feature tree (ronda v3)

**Worker**: W4 · **Rama**: `marathon/w4-bagrep-spectree` · **Base**: `d8554e0`
**Estado**: COMPLETE (2 hipótesis cerradas, 1 negativo documentado).
**Evidence**: [2026-11-22-face-gp-counter-table.md](../2026-11-22-face-gp-counter-table.md) ·
[2026-11-22-feature-tree.md](../2026-11-22-feature-tree.md) ·
`data/w4-face-gp-sweep.csv`, `data/w4-face-gp-counter-table-claims.csv`,
`data/w4-feature-tree-{files,claims}.csv`, `data/w4-open-rate-files.csv`.

## Hipótesis 1 — gramática `d2 d2 50` + los 34/44 carriers sin malla (#63) — **ACIERTO**

La pista era correcta: los `0x50` llevan el MISMO header `+57`
(`kind, N_tris, N_strips, N_fans` u32le) pero con **`kind=0`**, y la cola
es `u16be` (equivalente al `u16le`+1 de la pista) desde **`+74`**:
`3*N_tris` valores → **tabla de counts u16be** (uno por strip, luego uno
por fan) → valores concatenados; cierre byte-exacto en `rel_len - 1`.
**100/100 cierres** en la población de 44 carriers; los "pasos +3" son la
misma codificación mult-3 (`idx = 3*vertex`) y `A/B = 0/1` no aparece como
par constante — los strips zigzaguean entre filas.

- **Causa raíz de los carriers fuera**: (a) los `0x50` ignorados (89+11);
  (b) el framing `0x51`-only corría un span 0x51 POR ENCIMA de los `0x50`
  intercalados y no cerraba (CAKhw @236932); el extent ahora termina en el
  siguiente sub-record de cualquier tipo; (c) el gate rechazaba `kind != 3`.
- **Resultado del sweep corpus completo** (1,762 partes disponibles): **14
  fuegos** (13 del baseline + **`CAAPstPad1_2` nuevo**, 30 tris, fail →
  pass), **0 regresiones**, **0 held-out**. Ganancias: Pad1_1 56→112,
  Plate 64→100, Funnel 14→30, Screw 42→102, CAKhw 25→559 (×2),
  CAAMai 154→560/418. Mallas manifold, degenerados 0, ratios físicos OK.
- **Paridad Python=Rust: 49/49** PLY byte-idénticos + summary documento-igual
  (los no cambiados conservan sus hashes comprometidos).
- **Proyección L2 dev**: 1138/1381 = 0.8240 → **1139/1381 = 0.8248** (+1).
  Held-out flat.
- **Negativo documentado** (`FG2-07`): los 445 sub-records ANTES del primer
  class record (33 archivos) no tienen ley de emparejamiento — 32/33 sin
  arrays limpios en ventana; el restante gated 0. Un intento, sin segundo.

## Hipótesis 2 — feature tree determinista + panel viewer — **ACIERTO (honesto)**

Ley pinned: byte de longitud `L` (4..40) + exactamente `L-1` bytes ASCII
del charset `[A-Za-z0-9_.]` cuyo texto COMPLETO casa
`^(Type)(\.\d+|\d+)?$` (`len = strlen + 1`; anchors `07 Sketch`,
`05 Pad1`, `09 Sketch.1`, `0b EdgeFillet`). Vocabulario shipped: **17
tipos** medidos; la familia de parámetros (`Volume`/`Density`/`Area`/
`Mass`) excluida (cabeceras de propiedades, 51/51 archivos).

- Auditoría de los 56 BLANK: **38 feature-tree** · **13 `CATPrtCont`-only**
  (WELD-W1, grid, 550.000/511.000_NOTE A, BENDABLE-PIPE, …) · **4 sin
  nada** · 1 fuera de disco (drift upstream, cuarentena).
- 3 implementaciones, una ley: `display.scan_feature_tree` (Python) =
  `display::scan_feature_tree` (Rust, paridad 5/5 con bloque en summary) =
  scan client-side en `viewer.js` (**JS = Python 16/16** archivos reales).
- **Panel Feature / Spec Tree** en viewer (js/html/css): etiqueta
  `feature-tree-only` + badge `no-geometry` cuando 0 triángulos/puntos.
- **El contrato de export NO cambia**: una parte sin carriers sigue
  elevando su error clasificado (los 13 tests de contrato pasan intactos);
  el bloque `feature_tree` (aditivo, schema v1) viaja en los summaries de
  display; para los BLANK el árbol llega al viewer vía el scan client-side.
- **Open Rate honesto: +0 por el árbol** — por construcción no emite
  triángulo/punto/segmento y no se cuenta como geometría. La única subida
  del Open Rate viene de la hipótesis 1 (+1 MESH: CAAPstPad1_2).

## Open Rate honesto (re-medición, este host)

`data/w4-open-rate-files.csv` (el `open-rate-files.csv` comprometido
queda intacto — es la corrida del 2026-11-20, stale por 24 filas que la
reconciliación corrige y verifica con exports al código d8554e0).
Like-for-like vs d8554e0 (filas de drift restauradas a su clase base):

| | d8554e0 true | w4 | |
|---|---|---|---|
| MESH | 1,202 | **1,203** | +1 (`CAAPstPad1_2` DISPLAY→MESH, 30 tris) |
| DISPLAY | 211 | **210** | −1 (la misma fila) |
| BLANK | 29 | **29** | plano — el suelo sin carriers |
| **Open** | **1,413/1,442 = 97.99%** | **1,413/1,442 = 97.99%** | plano en filas: la fila movida ya estaba abierta como display y sube a malla real (+1 pass L2) |

**El Open Rate honesto NO baja y NO se infla**: el árbol de features no
cuenta como geometría (0 filas), y la palanca counter-table sube la
CALIDAD de una fila ya abierta (display→malla, +1 pass L2). Los 29
BLANK restantes son el suelo honesto: filas sin NINGÚN carrier
decodificable (19 missing-geometry-store + 10 undecoded-variant; 0 de
los 44 carriers bag-rep queda en BLANK).

**62 partes dev del repo `Apoloo13/ASE_III` están off-disk** (cambiaron
upstream tras el freeze 2026-11-07; el historial del repo NO contiene
los bytes congelados — mejor esfuerzo 7/69 shas verificados sobre 40
commits), de modo que el CSV crudo de este host no es 1:1 con el del
2026-11-20; la tabla de arriba es la reconciliación fila a fila.
Nota de proceso: la primera corrida del probe (`/tmp/w4-openrate.log`)
produjo datos por-fila inconsistentes (clases de reporte mezcladas) y
queda superseded; la corrida final es determinista (2 ejecuciones del
entorno actual coinciden con los exports directos, el sweep y la
paridad).

## Caveat del fitness run (importante para el Orquestador)

**No se commiteó un run de fitness**: con 62 partes dev off-disk (60 de
ellas eran passes del baseline d2c9ff), un run aquí registraría `unavailable`
(cuenta como no-pass, `runner.py`) y sería **rechazado falsamente**. La
evidencia no-regret es el sweep + paridad de arriba (cambio scan-local,
detrás de 3 rutas previas; el conjunto de fuegos solo crece; 0 held-out).
**Pendiente para el Orquestador**: restaurar el corpus ASE_III del freeze
(otra máquina/backup) y correr `catpart-fitness` con baseline d2c9ff.

## Tests

- `tests/test_face_gp.py`: 18 (ambos framings, interleave, gate axes,
  export route). `tests/test_no_surface_fallback.py`: 22 (+5 feature-tree).
- Rust: `face_gp` 14, `display` 12; fixture-mode fidelity (matriz
  sintética L1+L2) **verde**.
- Corpus: paridad 49/49; sweep determinista (`w4-face-gp-sweep.csv`).

## SHAs

- `a8bd1b7` — ley counter-table + extractor + panel + tests.
- `e353c76` — notas de evidencia.
- (final) — open-rate CSV + este note.

## Siguiente paso sugerido

1. Restaurar el corpus congelado y correr el fitness (accept esperado:
   L2 dev +1, resto flat).
2. El `0x51` con fans (`nfans > 0`) no existe en el corpus — la ley está
   implementada simétrica (tabla: strips luego fans) y fail-closed.
3. Los 4 archivos `none` y los 13 `prtcont-only` son el suelo honesto:
   no-geometry sin invención.
