# W26 progress — empty-mesh structural clustering + top non-U3 carrier attack (B6)

**Worker**: W26 · **Rama**: `marathon/w26-empty-mesh-clusters` · **Base**: `676537e`
**Estado**: COMPLETE — clustering + taxonomía con tasas entregados; ataque
al cluster top no-U3 en **negativo medido** (0 flips, 0 regresiones, 0
cambios en `src/` ni `port/`).
**Evidence**: [2026-11-22-w26-empty-mesh-clusters.md](../2026-11-22-w26-empty-mesh-clusters.md) ·
`data/w26-empty-mesh-clusters.csv` (211 filas) · `data/w26-cluster-ranks.csv` (102) ·
`data/w26-residual-carriers.csv` (55) · `data/w26-empty-mesh-claims.csv` (W26-01..14) ·
`scripts/triage/w26_empty_mesh_clusters.py` + `w26_residual_carriers_probe.py`
(`--selftest` 6/6 y 9/9).

## Clustering (W26-01..06)

211 archivos → **102 clusters** de firma exacta (versión join; tabla de
contenedores ordenada; tags de spans; forma del store: pool/compuesto/
buckets de candidatos; presencia de opcodes con buckets de magnitud —
la magnitud nunca parte una clase; W13 `d2 d2`/`30 04` incluidos).
El censo reproduce la baseline W2 exacta en las 211 filas (95,819
pool points; 178,240 candidatos; 6,206 aceptados; 124 spans).

| clase | archivos | bytes | % |
|---|---:|---:|---:|
| pool+facet (**U3-variant**) | 10 | 247.2 MB | 89.0% |
| zero-carrier | 107 | 14.7 MB | 5.3% |
| curves-only | 73 | 9.7 MB | 3.5% |
| outside-only | 10 | 3.6 MB | 1.3% |
| pool-only (7 no-U3 + 2 U3) | 9 | 1.8 MB | 0.7% |
| facet-only | 2 | 0.7 MB | 0.2% |

## SKIP documentado (W26-02): el cluster top es el U3-variant refutado

C01 = `PalmDown5motors2` (237.9 MB, el 85.7% de los bytes de la
población). Los 12 archivos U3 (oráculo W2b) llevan el 89.1% de los
bytes y 95,783/95,819 pool points. Presupuesto de la familia agotado
(W2: 2 intentos de mapeo; W2b: oráculo de normales almacenadas) →
**salto al siguiente y por qué queda registrado**; es además el único
carrier de triángulos decodificable de toda la población (W26-14).

## Ataque al top no-U3: C06 (outside-only) y todo el residuo (W26-07..12)

La población residual no-U3 completa: **55 candidatos** sin resolver
(49 outside-span en 11 clusters; 6 in-span en C55+C62; marcadores
0x41–0x4e).

- **Intento 1 (familia C06): ley de emparejamiento estricta** — conteo
  declarado mult-3 N respaldado por una corrida u16le contigua de
  exactamente N palabras (< N, no nula; la forma W2b F5). La lectura
  laxa ("corrida larga in-bounds") es vacua sobre bytes de stream y NO
  se usa. **0/55 disparan** el criterio de reapertura W13-#2.
- **Intento 2 (familia inline): censo de geometría** — la clase
  0x41/0x45 de C06: constantes de apertura por archivo (2562/10) y **0**
  zonas f32 (tablas de IDs, no geometría). La familia `0xea`-ty
  (0x46/0x48/0x4e): 18/55 (32.7%), cuerpos de objeto con campos f64 e
  IDs, sin arrays declarados. C55: sus 5 hits 0x4c in-span anteceden una
  **tabla de posiciones f32 inline de 127,771 B** (grillas stride-12 con
  y=20.0 constante) **sin cola de conectividad** → contenido
  vértices-only: `triangle_count` seguiría en 0 → **estructuralmente
  no flippable**; la ley cometida rechaza el header correctamente.

**Resultado**: negativo medido, ambas familias cerradas en presupuesto.
**Flips: 0** (nada que cablear — no existe carrier de triángulos
honesto fuera de U3). **Regresiones: 0** por construcción (probes
read-only; sin `src/` ni `port/`; precedente W13).

## Criterio de reapertura

1. **Ley de element-region U3** (criterios W2/W2b sin cambios): los
   únicos carriers de triángulos — el assembly 0x49 counts-less de W2
   sigue esperando en `brep_mesh.py`.
2. Una muestra futura con candidato outside-span que dispare la ley
   estricta de corrida exacta (quedó cometida en el probe).
3. Cola de conectividad tras una tabla de posiciones inline (la forma
   C55 + refs): re-medir la familia 0x4c-inline contra la gramática de
   strips (lane W17).

## Tests

- `tests/test_w26_probes.py`: ambos selftests por `main(["--selftest"])`
  (6/6 y 9/9) — cubiertos por el gate.
- Gate `scripts/check.sh` (CARGO_BUILD_JOBS=1, RUSTFLAGS=-C debuginfo=0,
  pytest 1 proceso): ruff limpio · **pytest 1006 passed / 21 skipped** ·
  claims-CSV quoting ok · cargo build native + wasm32 ok · fmt + clippy
  -D warnings limpios · **cargo test 252 passed** + integración verde.
- Único paso rojo: `wasm-pack` no está en agentvm2 y el brief de esta
  unidad lo prohíbe (anti-OOM) — la sección de artefactos shipped del
  gate no corre aquí. La unidad no toca `port/` ni `site/` (0 archivos
  de runtime), así que el artefacto shipped está intacto por
  construcción; CI es la autoridad.
- Sin cambios de runtime → paridad Py=Rust intacta por construcción.
