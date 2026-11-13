# catpart-parser

Un parser open source para archivos de pieza y producto de **CATIA V5** de
Dassault Systèmes (`.CATPart`, `.CATProduct`) — leyendo el formato binario
directamente, **sin necesidad de una instalación de CATIA**.

## Por qué

CATIA V5 guarda los modelos en un formato binario propietario y sin
documentar. Hoy las únicas formas de leer estos archivos son:

- Convertidores comerciales (de pago, código cerrado).
- Automatización COM de una instancia de CATIA en ejecución (requiere
  licencia de pago).

No existe ningún parser binario libre y open source. Este proyecto pretende
ser el primero completo, habilitando interoperabilidad, acceso a archivos y
tooling para quien recibe archivos CATIA sin tener un puesto de CATIA.

## Estado

[![L1 clean-parse (Dev)](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/MadManJohnSmith/catpart-parser/gh-pages/fitness-latest.json)](https://github.com/MadManJohnSmith/catpart-parser/blob/main/fitness/history.jsonl)

**Parser L1 disponible — Fase 3 cerrada (2026-11-08).** `catpart-inspect`
emite JSON schema-v1 (cabecera, inventario de contenedores con anotación de
clase base, `document_name`, trailer, versión detectada) y
`catpart-fitness` mide el parseo limpio sobre el corpus: **Dev 99.66%
(1745/1751), held-out 100% (73/73)**, no-regret según ADR-0001. Ver
[docs/ROADMAP.md](docs/ROADMAP.md) (bloque de estado de la Fase 3),
[docs/format/README.md](docs/format/README.md) (estructuras documentadas)
y `fitness/history.jsonl`. Publicado en vivo: el badge de arriba lee el
endpoint de `gh-pages`, refrescado localmente por
`scripts/publish_fitness.py` (ADR-0003, nunca en CI) — reconstruye y fuerza
el push del JSON de `gh-pages`.

**Geometría L2 (spec D, [#33](https://github.com/MadManJohnSmith/catpart-parser/issues/33)) —
disponible, baseline publicado.** `catpart-fitness` también mide el
escalar L2 por ADR-0001: la proporción de filas `kind=part` del manifest
cuya salida de `catpart-export` pasa la sanidad — exportación exitosa,
malla no vacía, manifold, bounding box finito y plausible, sin
triángulos degenerados por encima del umbral F7 de G3 (0 en cada soup de
store limpio). La población L2 es solo de piezas: los products se
excluyen (el negativo documentado — 0/37 products muestreados llevan
algún store de geometría,
[docs/evidence/2026-11-08-geometry-payloads.md](docs/evidence/2026-11-08-geometry-payloads.md)).
Las señales por componente (volumen cerrado donde se espera, shells
abiertos, conteos degenerados) se reportan por ejecución y nunca
colapsan en el titular; el badge de arriba sigue siendo L1 (un titular
por nivel, ADR-0001), y `fitness-history.json` lleva la serie L2 de
ejecuciones aceptadas junto a la L1. El baseline L2 aceptado (run
`20261110T172440Z-3ea53d`, 2026-11-10): **Dev 76/1,381 = 5.50%,
held-out 0/61**. La brecha está clasificada, no es anecdótica:
1,024 `undecoded-variant` (espacio de índices compuesto, lecturas
primitivas 0x4b/0x4e y 0x41/0x44 sin fijar — los abiertos que ponen la
barra), 313 `missing-geometry-store` (consistente con el rango
documentado 0.82–0.93 de presencia de stores), 29
`malformed-store-header`; de los 76 pases, 66 volúmenes cerrados +
10 shells abiertos (señales por componente).
[#34](https://github.com/MadManJohnSmith/catpart-parser/issues/34) (G6)
mueve las variantes no decodificadas hacia la barra de ≥ 80% bajo
no-regret.

**Estado del grind (2026-11-13, CIERRE):** la fila final aceptada (run
`20261113T231506Z-c2ab64`) pone L2 en **Dev 1,033/1,381 = 74.80%,
held-out 56/61**, L1 plano, 1,173 exportaciones — desde el baseline
de 76 pases por las 15 etapas #34 aterrizadas (absorción de pools
por-rep + leyes de anchos, recuperación de locators incluida la
extensión other-container, decode composite table-walk /
por-rep / raw-array, la ley E0 de curve-entries, la ley de espacio
de elementos de stage-13, y los levers dup-pin-ALL + dedup
unordered de stage-15, autorizados por el dueño). La barra del 80%
es inalcanzable: el techo medido del residual es exactamente lo
aterrizado (+32), y toda clase de fallo restante está cerrada por
bytes contra cualquier ley con evidencia commiteada (128 stores
no-pool llevan CERO registros de facetas; 125 cabeceras
missing-locator inalcanzables; las coordenadas de elementos UV no
están en el payload; los not-manifold son content-fins/libros
coplanares en los bytes). Bajo la regla pre-autorizada de revisión
de barra del ROADMAP, la barra L2 se re-ajusta al techo medido
**74.80% (margen 0)** con negativos documentados — la tabla por
clase y la compuerta de render sanity (PASS, subconjunto Dev de 6
stores) viven en
[docs/evidence/2026-11-13-phase4-close.md](docs/evidence/2026-11-13-phase4-close.md).
Historia: `fitness/history.jsonl` (append-only).

## Progreso

Tracker de implementación — 23 tickets bajo las specs
[#8](https://github.com/MadManJohnSmith/catpart-parser/issues/8) (tooling),
[#9](https://github.com/MadManJohnSmith/catpart-parser/issues/9) (inferencia
de formato) y [#10](https://github.com/MadManJohnSmith/catpart-parser/issues/10)
(parser L1). Se actualiza a medida que se cierran los tickets; el estado
autoritativo vive en el issue tracker.

**Specs A/B/C completas (17/17, 2026-11-09). Fase 4 abierta: spec D (#28,
geometría L2) con 6 tickets — 5/6 (G1-G5 hechos 2026-11-10).**

| Spec | Ticket | Estado |
|---|---|---|
| A | [#11](https://github.com/MadManJohnSmith/catpart-parser/issues/11) A1 package skeleton & CLI | hecho |
| A | [#13](https://github.com/MadManJohnSmith/catpart-parser/issues/13) A3 version detection + manifest backfill | hecho |
| A | [#14](https://github.com/MadManJohnSmith/catpart-parser/issues/14) A4 fitness runner | hecho |
| A | [#12](https://github.com/MadManJohnSmith/catpart-parser/issues/12) A2 fixture generator | hecho |
| A | [#15](https://github.com/MadManJohnSmith/catpart-parser/issues/15) A5 GitHub Actions CI (after A2) | hecho |
| A | [#16](https://github.com/MadManJohnSmith/catpart-parser/issues/16) A6 gh-pages publication | hecho |
| B | [#17](https://github.com/MadManJohnSmith/catpart-parser/issues/17) B1 container table & trailer | hecho |
| B | [#19](https://github.com/MadManJohnSmith/catpart-parser/issues/19) B3 container payload blocks | hecho |
| B | [#18](https://github.com/MadManJohnSmith/catpart-parser/issues/18) B2 header/tail semantics | hecho |
| B | [#20](https://github.com/MadManJohnSmith/catpart-parser/issues/20) B4 CGMGeom/CATCGRCont payloads | hecho |
| B | [#21](https://github.com/MadManJohnSmith/catpart-parser/issues/21) B5 R19 vs R21 differential | hecho |
| B | [#22](https://github.com/MadManJohnSmith/catpart-parser/issues/22) B6 format document v1 (Phase 2 close) | hecho |
| C | [#23](https://github.com/MadManJohnSmith/catpart-parser/issues/23) C1 schema v1 + L1 baseline | hecho |
| C | [#24](https://github.com/MadManJohnSmith/catpart-parser/issues/24) C2 feature tree (documented negative) | hecho |
| C | [#25](https://github.com/MadManJohnSmith/catpart-parser/issues/25) C3 units/names (document_name; units negative) | hecho |
| C | [#26](https://github.com/MadManJohnSmith/catpart-parser/issues/26) C4 Phase 3 acceptance | hecho |
| C | [#27](https://github.com/MadManJohnSmith/catpart-parser/issues/27) C5 fitness publication (after A6) | hecho |
| D | [#29](https://github.com/MadManJohnSmith/catpart-parser/issues/29) G1 nested store navigation decoded | hecho |
| D | [#30](https://github.com/MadManJohnSmith/catpart-parser/issues/30) G2 vertex pool decoded | hecho |
| D | [#31](https://github.com/MadManJohnSmith/catpart-parser/issues/31) G3 primitive semantics (triangles) | hecho |
| D | [#32](https://github.com/MadManJohnSmith/catpart-parser/issues/32) G4 catpart-export CLI + geometry fixtures | hecho |
| D | [#33](https://github.com/MadManJohnSmith/catpart-parser/issues/33) G5 L2 fitness + publication | hecho |
| D | [#34](https://github.com/MadManJohnSmith/catpart-parser/issues/34) G6 grind L2 to the bar (Phase 4 close) | en curso |

## Hoja de ruta

| Nivel | Entregable | Estado |
|---|---|---|
| L0 | Corpus público + triage a nivel de bytes con evidencia reproducible | hecho (Fases 0/1) |
| L1 | Mapa de contenedores/secciones, metadatos, inventario de contenedores, nombres | hecho (Fase 3) |
| L2 | Geometría básica: mallas y curvas exportables a STEP o renderizables | cerrada al 74.80% (barra re-ajustada por la regla pre-autorizada) |
| L3 | B-rep paramétrico completo (sólidos CAD precisos) | planeado, el más difícil |

## Método

- **Dirigido por corpus.** El fitness es la proporción del corpus que parsea
  limpio, más verificaciones de sanidad geométrica (renderizable sin NaNs,
  volúmenes cerrados).
- **Dirigido por evidencia.** Cada afirmación estructural está atada a rangos
  de bytes concretos y digests de archivo; los hallazgos negativos también se
  registran.
- **Ingeniería inversa solo para interoperabilidad.** Documentamos estructuras
  observadas; no se redistribuye código propietario. Ver *Legal* abajo.

## Legal

Ingeniería inversa de un formato de archivo para interoperabilidad. Este
proyecto no redistribuye código de Dassault ni usa especificaciones filtradas.
La documentación del formato producida aquí se deriva de observar archivos
reales y el comportamiento documentado de herramientas.

## Licencia

[Apache-2.0](LICENSE) — elegida por su concesión explícita de patentes.
