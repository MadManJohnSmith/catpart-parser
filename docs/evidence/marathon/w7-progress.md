# W7 — speed oracle (ronda v3)

**Branch**: `marathon/w7-speed-oracle` (base d8554e0). **Host**: TARDIS.
**Anti-OOM**: `CARGO_BUILD_JOBS=2 RUSTFLAGS="-C debuginfo=0"`; `free -m`
before every heavy run. **Evidence note**:
[2026-11-22-w7-speed-oracle.md](../2026-11-22-w7-speed-oracle.md).

## Hypotheses

### H1 — fast-path de fitness vía `fidelity-cli` + caché `(file_sha256, code_digest)` — LANDED

- Discovery: L2 (export+gate) es el 99.6% del coste del sweep fitness
  (Python: 1.17 s L1 vs 292.6 s L2 en 757 archivos). El binario nativo
  hace la fase L2 16.6x (Submarino) / 10.4x (candidatos).
- Engines: `python` (default, histórico byte a byte) / `rust` / `fast`
  (L1 Python + L2 Rust — el mejor medido). Todos los gates corren igual
  sobre la salida de cualquier engine (vocabulario idéntico).
- `run_fitness(engine=...)`; caché incremental con digest que vincula
  speed.py+runner.py+invariants.py+binario (se auto-invalidó en vivo al
  tocar speed.py — funcionó como diseñado).
- Sweep streaming (1 archivo en vuelo, CSV prefijo-completo, RSS medida
  con getrusage).

**Antes/después** — `docs/evidence/data/w7-speed-claims.csv`:

| corpus | engine | wall | speedup | pico RSS |
| :--- | :--- | ---: | ---: | :--- |
| Submarino (757, 3.5 GB) | python | 294.7 s | 1.0x | 267.9 MiB |
| Submarino | fast | 19.8 s | **14.9x** | 55.0 + 55.0 MiB |
| Submarino | fast caché caliente | 1.03 s | **285x** | 33.4 MiB |
| Candidatos (762, 11 GB) | python | 765.1 s | 1.0x | **5323.0 MiB** |
| Candidatos | fast | 77.8 s | **9.8x** | 227.3 + 1194.0 MiB |

**Equivalencia**: 0 divergencias python↔fast y python↔rust en los 757
y en los 762 (gigantes incluidos: la tienda Aston de 198 MiB / 2.72M
vértices concuerda por archivo) — `w7-parity-claims-*.csv` + `compare`
exit 0. Hallazgo: la PROSA del warning `primary-loop-relist-skip`
difiere entre gemelos en corpus real — la regla §3.2 ya la declara
nunca-comparada; el comparador quedó a nivel de clases.

### H2 — fast-gate `scripts/check-fast.sh` — LANDED

4.15 s / 107 tests (lint + unitario fitness/CLI + paridad de engines
con el binario real + claims-CSV checker). `check.sh` intacto
(verificado byte a byte contra la base) y sigue siendo la autoridad
pre-push. Falla RUIDOSO sin binario port. Lo que NO cubre está en la
cabecera del script (matriz fidelity completa, cargo/wasm, node,
Playwright). `w7-gate-claims.csv`.

### H3 — harness de ground truth `scripts/benchmark_ground_truth.py` — LANDED

Chamfer (simétrico) + Hausdorff p95/máx (simétrico) + `area_ratio`,
distancia exacta por voxel grid con expansión por anillos (sin
aproximación en ninguna dirección), streaming par a par. STL
(binario/ASCII) + OBJ; STEP rechazado POR NOMBRE (B-rep ≠ teselada).
`--selftest` fija 5 aristas sintéticas; 11 tests pytest prueban el
cero END-TO-END (export del seam ↔ STL de la misma malla: Hausdorff 0,
area_ratio 1) y el punto ciego declarado (densidad → solo area_ratio).

## Negativos

- El caso OOM quedó MEDIDO, no teórico: el engine Python sobre
  candidatos pica 5323 MiB en el proceso padre (anfitrión con ~5-6 GB
  libres en ese momento — un job simultáneo lo mata). El engine fast
  baja el pico combinado a ~1.4 GiB (decode nativo transitorio por
  archivo) y el padre queda plano.
- El speedup decae en archivos gigantes (14.9x en submarino → 9.8x en
  candidatos): el decode nativo de una tienda de 198 MiB cuesta 41.6 s
  (vs 378.7 s Python) — el techo es el I/O + la serialización PLY, que
  ambos engines pagan.
- Ningún check eliminado ni relajado: `check.sh` idéntico a la base
  (diff vacío); el default `engine="python"` preserva el comportamiento
  histórico (suite completa en verde antes del push).

## Siguiente paso

Opcional para el Orquestador: exponer `--engine` en el console script
`catpart-fitness` (requiere tocar `cli.py`, fuera del scope W7); y
re-evaluar el corpus del manifest (1,824 filas) en la máquina que lo
alberga con `engine=fast` — la paridad y el harness ya están probados
aquí sobre 762 archivos reales.
