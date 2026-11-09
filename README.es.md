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

## Progreso

Tracker de implementación — 23 tickets bajo las specs
[#8](https://github.com/MadManJohnSmith/catpart-parser/issues/8) (tooling),
[#9](https://github.com/MadManJohnSmith/catpart-parser/issues/9) (inferencia
de formato) y [#10](https://github.com/MadManJohnSmith/catpart-parser/issues/10)
(parser L1). Se actualiza a medida que se cierran los tickets; el estado
autoritativo vive en el issue tracker.

**Specs A/B/C completas (17/17, 2026-11-09). Fase 4 abierta: spec D (#28,
geometría L2) con 6 tickets — 2/6 (G1+G2 hechos 2026-11-09).**

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
| D | [#31](https://github.com/MadManJohnSmith/catpart-parser/issues/31) G3 primitive semantics (triangles) | planeado |
| D | [#32](https://github.com/MadManJohnSmith/catpart-parser/issues/32) G4 catpart-export CLI + geometry fixtures | planeado |
| D | [#33](https://github.com/MadManJohnSmith/catpart-parser/issues/33) G5 L2 fitness + publication | planeado |
| D | [#34](https://github.com/MadManJohnSmith/catpart-parser/issues/34) G6 grind L2 to the bar (Phase 4 close) | planeado |

## Hoja de ruta

| Nivel | Entregable | Estado |
|---|---|---|
| L0 | Corpus público + triage a nivel de bytes con evidencia reproducible | hecho (Fases 0/1) |
| L1 | Mapa de contenedores/secciones, metadatos, inventario de contenedores, nombres | hecho (Fase 3) |
| L2 | Geometría básica: mallas y curvas exportables a STEP o renderizables | planeado |
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
