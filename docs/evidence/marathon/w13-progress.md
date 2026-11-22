# W13 progress — `d2 d2 XX` / `30 04 XX` sibling sweep (Bloque B7, continuación)

**Worker**: W13 · **Rama**: `marathon/w13-d2d2-sweep` · **Base**: `339525a`
**Estado**: COMPLETE — 2 hipótesis en **negativo medido** (0 cierres, 0 flips,
0 regresiones). Sin cambios en `src/`, `port/` ni `site/`.
**Evidence**: [2026-11-22-w13-d2d2-variants.md](../2026-11-22-w13-d2d2-variants.md) ·
`data/w13-d2d2-variants-claims.csv` (W13-01..14) ·
`data/w13-empty-mesh-sweep.csv` (211 filas) ·
`scripts/triage/w13_d2d2_variants_probe.py` (`--selftest` 5/5).

## Hipótesis 1 — variantes hermanas `d2 d2 XX` (51/52/otros) — **NEGATIVO medido**

- **`0x52` no existe**: 0 hits en 1,442 .CATPart (W13-01). Nada que cablear.
- `0x50`/`0x51` ya cableados por W4; los hits 0x50/0x51 FUERA de spans
  (1055 records en 72 archivos) cierran **0/1055** bajo ambas leyes y
  **0/1055** tienen header sane en +57 (W13-06/07): son records de
  aristas/puntos (ID + `02 00` + `"32"` + triples f32 inline + cola de
  enteros + tag ASCII) cuya geometría **ya se muestra** por la ruta
  display (8/8 muestreados, p.ej. CAACafSearch 116 pts/6 segs) — W13-08/09.
- El record grande (>20 KB) por archivo (72): 0 arrays f32 declarados,
  cola u16be 62.7% mult-3 = ruido, sin stream (W13-08).
- `0x30` = relleno encadenado (copias de 8 bytes consecutivas; el "flag"
  es el primer byte de la siguiente copia); `0x01` = terminadores de
  cadena / otra clase pequeña (0 in-span, 0/710 sane@57); `0x00` =
  boundary artifact conocido (W13-04/13).
- In-span corpus-wide: 0x50 97/100 cierran; 0x51 39/88. Los 52 sin
  cierre se reparten por delta: +0 ×17, −4 ×8, −10 ×5, −2 ×4, +1 ×2,
  ≤−1403 ×16 (W13-10). **Los no-cierres cercanos NO dan flips**: los
  únicos 2 in-span de los 211 son de CAAPstPad1_2 (delta −4), que ya
  flippea con la ley W4 (W13-11). Variante "cola ≤4 bytes" documentada
  como open question, NO cableada (crecería mallas de archivos que ya
  pasan: churn de hashes + paridad por 0 flips).

## Hipótesis 2 — familia `30 04 XX` — **NEGATIVO medido**

- `XX=04` en **378,501/378,501** hits corpus-wide (W13-02); todo core de
  7 bytes precedido por `30` (W13-03). No existe la familia hermana.
- La discrepancia de censo (378,501 vs 190,278) es el doble conteo del
  relleno encadenado (stride 8), no una variante (W13-03/04).

## Sweep de los 211 y flips (W13-05/12)

| zona | archivos | carriers | resultado |
|---|---|---|---|
| no-hits | 138 | 0 | sin carriers de la familia — suelo estructural |
| between-spans-only | 72 | 1055 records | aristas/puntos, ya mostrados por display; 0/1055 cierres |
| in-span | 1 | 3 records | CAAPstPad1_2 — ya produce malla (30 tris, el flip de W4; fila stale del CSV base) |

**Flips reales medidos: 0** (dev y held-out; 0 held-out en cualquier
clase de variante). **Regresiones: 0** por construcción (ningún archivo
de runtime tocado; los negativos quedan pineados por tests sintéticos).

## Criterio de reapertura

1. Censo (`census`) marque un flag nuevo con hits in-span en una
   muestra futura → decodificar contra la gramática W4 antes de cablear.
2. Un record between-spans que indexe un array EXTERNO (mult-3
   in-bounds) → nueva ley de emparejamiento (el negativo FG2-07 de W4
   cubre el subconjunto before-first-record).
3. Población empty-mesh cuyos únicos records in-span caigan en los
   deltas −4/−2/+0/−10 → variante de cola acotada (≤5 u16be, mult-3) con
   gate estricto, medida SOLO sobre esa población.

## Tests

- `tests/test_face_gp.py`: **25 verdes** (7 nuevos sintéticos fail-closed:
  flag-52, prefijo `30 04 05`, relleno encadenado, record de aristas,
  strip que desborda (+0), cola de 4 bytes (−4), terminador 0x01).
- `test_no_surface_fallback.py` intacto: 47 passed / 1 skipped junto al
  anterior (1 proceso).
- Paridad Python=Rust: sin cambios de runtime → intacta por construcción.

## SHAs

- Un único commit sobre la base `339525a` con la unidad completa:
  probe + CSVs + esta nota + tests + progreso (ver `git log -1` en la
  rama; el SHA no se auto-referencia).
