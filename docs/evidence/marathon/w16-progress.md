# W16 progress — Bloque A4: ley de coordenadas U4 (skip-slots)

Rama `marathon/w16-u4-curve-loops`, base `339525a`. 2026-11-22.

## Entregado

- **Ley U4 = U4-D dup-prev, total**: 0 unpinnable slots sobre 473,801
  skips (Motor 5,616 / Audi R8 22,466 / Vulcan 445,719); batería de
  coplanaridad 99.9955% sobre 401,956 loops skip-ref (18 no planares,
  todos Vulcan).  La aritmética reconcilia EXACTO con los contadores
  shipped en los 3 targets: skipref_loops == exported + dropped
  (4,073 = 3,992+81; 12,289 = 11,660+629; 267,594 = 255,470+12,124).
- **Hipótesis 1** (offset a registros/polilíneas de curva vecinos):
  refutada como FUENTE (registros 33 3X de 18-30 B per-curva, no
  per-slot; 24 registros vs 26 skips en el anchor; id ∈ {1,2} sin
  correspondencia con skips), confirmada como CORROBORACIÓN (los
  anillos escritos y las polilíneas de aristas comparten los dups).
- **Hipótesis 2** (coordenada inline comprimida): refutada — la región
  de puntos consume exactamente el write_count declarado; la región
  trailing del nodo es estructura (u16 cuantizados), no triples f32.
- **Hallazgo A4**: los loops descartados no son fallos de coordenadas:
  son (a) refusals del guard de malla (edge-overuse), (b) miembros de
  registros 0x47/0x4f declinados, (c) la clase degenerada — quads del
  escritor `(P, X, P, Y)` cuyo dup-pin es VERDADERO y cuya superficie
  real se recupera con el convenio skip-degenerate G3 F7 que la vía
  primaria ya aplica.  Bruto medido: Motor 121 tris / 5,534 mm²,
  Audi 761 tris / 13.59M mm², Vulcan 22,421 tris / 19.03M mm².
  El cambio de emisión vive en composite.py (W17): el módulo de ley
  queda validado y listo para integrar.
- **knurling_screw 117**: NO medible — el archivo no está en disco
  (confirmado por la sonda read-only 2026-11-21); cero cifras
  inventadas; criterio de reapertura en la nota.

## Archivos

- `src/catpart/geometry/curves.py` (ley U4: pin, batería, split
  degenerado, walker 33 3X, ring cross-check) + twin
  `port/src/geometry/curves.rs` (13 tests, clippy limpio).
- `tests/test_curves.py` (27 sintéticos, sin corpus).
- `scripts/triage/measure_u4_skip_law.py` (runner sobre el decode
  shipped, 1 proceso, streaming por rep).
- `docs/evidence/data/u4-skip-law-{files,claims}.csv` (3 filas target,
  reconciliación exacta documentada).
- `docs/evidence/2026-11-22-u4-skip-coordinate-law.md` (nota fechada,
  negativos y reapertura).

## Incidente OOM y presupuesto

El turno previo fue killed por OOM del Linux con dos jobs grandes
simultáneos (build_export de Audi+Vulcan en un proceso y
probe_declined de Vulcan en otro) junto al gate del Orquestador.  La
unidad 1 (módulo + twin + tests + runner) SÍ llegó a commitearse
(`59ae58c`) antes del kill.  Este turno: cero build_export de parts
>15 MB; las filas Audi/Vulcan se re-derivaron streaming desde los
captures ya en disco (mismo resultado; Motor valida la equivalencia
byte a nivel de fila contra el runner committed).

## SHAs

- `59ae58c` — módulo de ley + twin + tests + runner.
- (este) — CSVs + nota + progress.

## Siguiente paso sugerido

1. W17: adoptar `curves.split_loop_triangles` en el weld de
   composite.py (per-triangle degenerate split detrás del mismo mesh
   guard) y correr el A/B de corpus (0 regresiones es la condición).
2. knurling_screw: medir al llegar el archivo (sonda lista).
