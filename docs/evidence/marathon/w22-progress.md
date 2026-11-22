# W22 progress — CATIA-like viewer fidelity (Bloque E18, heredado de W14)

**Worker**: W22 · **Rama**: `marathon/w22-viewer-catia` · **Base**: `56ced34`
**Estado**: COMPLETE (3 entregables viewer + 1 probe read-only; 1 desviación declarada).
**Evidence**: [2026-11-22-w22-graphic-attributes.md](../2026-11-22-w22-graphic-attributes.md) ·
`data/w22-graphic-attributes-files.csv` (1,442 filas) ·
`data/w22-graphic-attributes-claims.csv` (W22-GA-01..08) ·
`data/w22-bodies-sample-files.csv` (120 filas) ·
`screenshots/w22-canonical-{front,iso}.png` ·
`screenshots/w22-real-{front-feature-selected,iso-body0-hidden,front-even-shading}.png` ·
`screenshots/w22-real-tree-selected-bodies-panel.png` (la fila Point resaltada + el
detalle 0x373A + el panel Bodies con Component 1 oculto).

## D1 — Vistas estándar CAD — **ACIERTO**

Nuevo módulo `site/viewer/cadviews.js` (puro, testeable en node):
presets en ejes **CATIA** (iso (1,1,1), frontal +Y, superior +Z, lateral
+X, screen-up Z — la superior con +Y en pantalla), mapeados por modo:
part = coordenadas crudas; assembly = base `R_X(-pi/2)`
(CATIA (x,y,z) -> mundo (x,z,−y), verificado contra
`tests/test_assembly_scene.mjs`). Encuadre automático a la esfera de la
bbox con el MISMO margen 2.2x de `orbit.js`; transición animada
(~280ms, easeInOutQuad): slerp de cuaternión + radio log-lerp + target
lerp — **solo cámara**, cero trabajo de geometría por frame (seguro a
escala Dodge 2.5M tris); cancelación a mitad de vuelo re-basa el estado
esférico desde la pose exacta (el drag nunca "salta").
`node tests/test_viewer_cadviews.mjs` (§1-§8): mapping por modo, poses
exactas de los 4 presets x 2 modos, round-trip pose<->esférica, cancel
sin snap, framing 2.2x.

**Desviación declarada (1 de 2 permitidas por hipótesis)**:
`site/viewer/orbit.js` guarda sus ángulos esféricos en una closure sin
setter y NO está en mi set exclusivo de edición; viewer.js adjunta el
controlador de `cadviews.js` (misma gramática drag/rueda/margen 2.2x) y
`orbit.js` queda intacto y sin consumidor. Alternativa descartada:
editar orbit.js fuera del set. `attachOrbit` sigue exportándose para
cualquier consumidor futuro.

## D2 — Normales consistentes (even shading) — **ACIERTO**

Toggle `Even shading` (default OFF, persiste entre cargas como
Edges/Wireframe): `flatShading` en el MATERIAL (part: `solidMaterial`;
assembly: los materiales de las instancias, patrón `setWireframe`).
three.js r170 deriva la normal por fragmento de las derivadas de
pantalla — SIEMPRE mirando a cámara — así el winding mixto deja de
producir caras oscuras. Cero cambios a la malla exportada (vértices,
índices y normales intactos), coste = 1 recompilación de shader, no un
pase de geometría. `window.viewer.shading` = "smooth"|"flat" para los
checks; verificado en la aceptación (off->on->off, aria-pressed).

## D3 — Feature tree interactivo + Bodies — **ACIERTO (con etiqueta honesta)**

- **Filas clicables**: cada fila del censo resalta (`selected`) y
  muestra el detalle del registro: `Point: 1 framed record(s) — first
  at byte 14138 (0x373A)` — el único dato por-operación que el censo
  lleva (offset + count). `window.viewer.featureSelection`.
- **Badge `no-geometry`**: verificado en aceptación sobre el fixture
  corrupted (decode clasificado falla; el scan client-side sobre los
  bytes crudos mantiene el árbol) — la ley de W4 intacta.
- **Bodies (componentes visuales)**: ley client-side
  `computeComponents` (union-find sobre índices de vértice
  COMPARTIDOS, chunked 250k tris/frame — nunca bloquea el hilo) +
  `reorderByComponents` (reorden estable del índice; cada componente
  = un draw range sobre LOS MISMOS atributos position/normal — datos
  exportados intactos). Panel con toggles por componente, "Show all",
  edges overlay oculto mientras hay un componente oculto.
  **Etiqueta honesta**: agrupación VISUAL por conectividad de
  vértices, NO frontera de cuerpos CATIA decodificada (el contrato de
  export lleva un pool único; el parser está fuera de alcance).
- **Paridad JS=Python**: casos dorados IDÉNTICOS en
  `tests/test_viewer_cadviews.mjs` §9/§10 y
  `tests/test_w22_bodies_parity.py` (un divergencia JS/Python rompe
  una de las dos suites); la ley se valida contra un ORACLE
  independiente (BFS sobre adyacencia) en 64 mallas aleatorias +
  golden. Paridad real: Support-plate (sha16 `58294667cca84de1`,
  fila comprometida en `data/w22-bodies-sample-files.csv`): Python 7
  componentes = JS 7 en el browser (sesión real, screenshot).
- **Tasa real** (muestra 120 partes, seed 20261122): 117 con malla,
  50 multi-componente (42.7%), mediana 1, máx 75.

## D4 — CATGraphicAttributeSet (probe read-only) — **NEGATIVO medido + LEAD**

`CATGraphicAttributeSet` = **0/1,442** partes (familia vis-token
completa también 0, ASCII/case/UTF-16LE). El portador real de
RGB/opacidad en este corpus es la familia **fe-framed material-property
blocks** (33/1,442 = 2.3%, la ley `len=strlen+1` de los feature names):
`Color`/`TransparentColor` con triple de 3 bytes tras `84 81`
(candidato RGB), `Reflectivity`/`Transparency` con `e6` + f64 LE de
valores físicos limpios (0.7, 0.495, 0.05, 0.7333=11/15), `e8` vacío
domina Transparency (26 vs 1). **Nada cableado en runtime** — handoff
completo (próximos pasos, anclas, límites declarados) en la nota.
`--selftest` 6/6; claims CSV pasa el checker del gate (106 CSVs).

## Gates

- `node --test tests/*.mjs` — 6/6 suites verdes (incluida la nueva
  `test_viewer_cadviews.mjs`).
- `pytest -q` — 1008 passed / 21 skipped (incluye los 5 nuevos de
  `test_w22_bodies_parity.py`); ruff clean; claims CSV checker ok.
- Aceptaciones Playwright LOCALES (una pestaña, batches pequeños,
  `browser.close()` al final; precondiciones pgrep/free verificadas):
  `viewer_acceptance.py` PASS (7 checks), `assembly_viewer_acceptance.py`
  PASS (6 fixtures), NUEVA `scripts/w22_viewer_acceptance.py` PASS
  (vistas, shading, árbol interactivo, badge, bodies, cero requests
  externos, cero errores de página).
- Contrato de export: 0 cambios (ni `src/` ni `port/` ni `pkg/`
  tocados; los 13 tests de contrato y la paridad port pasan intactos).

## Reapertura

1. Un export futuro que lleve fronteras de cuerpo por-parte reemplaza
   la fuente de verdad del panel Bodies (el client-side queda como
   fallback etiquetado).
2. El lead de material-properties se decodifica corpus-wide en su
   propio ticket (ver handoff W22-GA; el e8-variant y la forma larga
   de Color quedan ABIERTOS medidos).
3. Si un preset CATIA necesita el norte guardado en el archivo
   (views por documento), el mapping por modo de cadviews.js es el
   punto de extensión.
