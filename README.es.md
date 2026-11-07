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

**Fase de investigación — triage del formato.** Aún no hay salida parseable.
Ver [docs/ROADMAP.md](docs/ROADMAP.md) y
[docs/research/format-landscape.md](docs/research/format-landscape.md).

## Hoja de ruta

| Nivel | Entregable | Estado |
|---|---|---|
| L0 | Corpus público + triage a nivel de bytes con evidencia reproducible | planeado |
| L1 | Mapa de contenedores/secciones, metadatos, árbol de features, unidades, nombres | planeado |
| L2 | Geometría básica: mallas y curvas exportables a STEP o renderizables | planeado |
| L3 | B-rep paramétrico completo (sólidos CAD precisos) | planeado, el más difícil |

## Método

- **Dirigido por corpus.** El fitness es el porcentaje del corpus que parsea
  limpio, más verificaciones de sanidad geométrica (renderizable sin NaNs,
  sólidos que cierran).
- **Dirigido por evidencia.** Cada afirmación estructural está atada a rangos
  de bytes concretos y digests de archivo; los hallazgos negativos también se
  registran.
- **Ingeniería inversa solo para interoperabilidad.** Documentamos estructuras
  observadas; no se redistribuye código propietario. Ver *Legal* abajo.

## Legal

Ingeniería inversa de un formato de archivo para interoperabilidad. Este
proyecto no redistribuye código de Dassault ni usa especificaciones filtradas.
La documentación del formato que se produzca aquí se deriva de observar
archivos reales y el comportamiento documentado de herramientas.

## Licencia

[Apache-2.0](LICENSE) — elegida por su concesión explícita de patentes.
