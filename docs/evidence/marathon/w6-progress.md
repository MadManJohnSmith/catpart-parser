# W6 progress — laya oracle + visual QA + ROI mining (ronda v3)

Baseline d8554e0 · rama `marathon/w6-laya-oracle` · 2026-11-22 · Gallyfrey.
Entregables commiteados: `scripts/triage/w6_*.py` + `scripts/triage/top-targets.md`.
Artefactos de trabajo (no committeables): `~/.local/state/catpart-parser/w6-laya/`
(features.jsonl, verdicts JSONL, metrics, renders, manifest, logs).

## H1 — Laya calibrado de dominio (VegaAgent, CPU, USE_TF=0, 2 hilos)

- Features JSONL: 2,199 archivos etiquetados (1,442 corpus del informe fitness
  commiteado `20261121T103944Z-d2c9ff` + open-rate + manifest; 757 Submarino de
  `m1_files.csv`). Labels `fail_family` del censo (pass / check:* / error:* /
  fail-unclassified). Builder streaming: `w6_build_features.py`.
- Fit: `VegaAgent.fit()` sobre dev oficial (1,381) con calibrate por defecto
  (banda conformal objetivo 0.95). 8,438 s en CPU. **La API real de laya 0.5.2
  no tiene `Agent.fit()`**: el intento previo `w6_laya_fit.py` asumía una
  API inexistente (y leía `route` en la raíz del predict, cuando vive en
  `answers[qid]`). Reescrito contra `VegaAgent` (`gold` como `{qid: answer}`).
- Head vs engine: **cv_accuracy 1.000 vs engine 0.743 (chance 0.125) →
  `used_by_auto=true`**: el head (logístico sobre features congeladas) bate al
  reader y se sirve en auto. Banda conformal alcanzó el objetivo (0 gated-out
  en 818 filas de eval).
- Eval gated (`route=="auto"` + `probabilities`; nunca `confidence` cruda):
  held-out 61/61 acc **1.0000**; Submarino 757 acc **0.9987** (único fallo:
  la fila `error:no-evaluable-surface`, clase sin ejemplos de train).
- **Advertencia de circularidad (importante)**: el estado lleva
  `error_class`/`failed_check`/`open_kind`, de los que se deriva la etiqueta;
  la accuracy sobre clases de tabla es un chequeo de contrato (laya reproduce
  la tabla del router determinista), NO una prueba de generalización. El test
  de generalización es H3 (features puramente geométricas).
- Bug corregido a mitad de camino: `fail_family` leía `status` en filas
  Submarino del CSV (que trae `l2_status`) → los 366 pass quedaban como
  `fail-unclassified` (falsos 0.5152). Fix + re-score offline desde los
  veredictos crudos guardados (sin re-entrenar; train nunca estuvo
  contaminado). El crash `KeyError: 'pass'` del primer run también queda
  blindado (`prf` tolera clases predichas sin filas de verdad).
- Router determinista: 760 ruteados, **1,439 residuo** (1,417 pass-con-avisos +
  21 degenerate + 1 no-evaluable). Laya sobre el residuo: held-out-residue
  57/57 **1.0000**, submarine-residue 374/375 **0.9973**. En pass-con-avisos
  laya reproduce `pass` (misma asunción no medida que el router documenta).
- Jev: **NO disponible** — sin `OPENCODE_API_KEY`/`OPENROUTER_API_KEY`/
  `TYPESAFE_API_KEY` en el host; el único candidato local
  (`~/.config/opencode/service.json`) responde **401 Invalid credential** en
  System One. No se inventan probabilidades; el gancho `--jev-key-file` queda
  listo (ruta B, `jev-1.13-free`) y no testeado por falta de clave.

## H2 — Oráculo de QA visual (2 intentos → NEGATIVO documentado)

- Infra: `w6_render_meshes.py` exporta PLY (`build_export`, seam catpart-export,
  venv con `catpart` en d8554e0) y renderiza raster ortográfico stdlib
  (seam `render_sanity_close.py` de G3; sin wasm-pack, sin Chromium). 100
  mallas estratificadas (sospechosos espagueti incl. `acc-Cont-Lft`, degenerate,
  avisos, controles limpios, tiny-pass, display, big-pass) + manifest JSONL.
- Lección de selección: "menor used_written" literal llena el barrido de
  filas vacías (52 errores de export, 65 sin mallas en el intento v1) —
  re-estratificado por superficie de riesgo.
- Intento 1 (3 vistas por malla, `predict(image=...)`): el gate nunca llega a
  auto; **los 3 controles limpios salen `debris_spaghetti` (0.59-0.62)** con
  confianza mayor que el sospechoso real (0.417); `debris_score=1` ("nada")
  contradice cada `render_class`. Especificidad ~0, confianza invertida.
- Intento 2 (montaje 3-vistas en una imagen, prompt neutro): salida degenerada
  — **todo** `debris_spaghetti` uniforme (0.47-0.53, todo review).
- **Veredicto: laya-vision 0.5.2 sobre rasters ortográficos flat-shaded NO
  discrimina espagueti de sólido limpio.** Criterio de reapertura: renders
  sombreados/AA/>480 px con overlay de aristas, o el viewer WASM real con
  cámara; o un vision-model validado sobre rasters CAD. Los PNGs/manifest
  quedan en state para ese intento.

## H3 — Head logístico destilable (pivote a etiquetas deterministas)

Labels (no laya-vision): positivo = not-manifold con
`duplicate-triangles-dedup-declined` (la firma acc-Cont-Lft, n=315), negativo =
pass sin warnings (n=144). Muestra balanceada 120/120 determinista.

- Variante A (todos los features): LOO 1.000, banda elem_decl≤255 (n=26)
  1.000 — **circular por construcción** (la etiqueta se define de los mismos
  warnings en features); vale solo como chequeo de consistencia del censo.
- **Variante B (sin fuga, solo geometría: log tris, log verts, degen_ratio,
  boundary)**: **LOO 0.775**; banda ambigua elem≤255: **0.923** (n=26).
  Pesas (intercept −4.386): `log1p_tris +1.368`, `log1p_verts −0.704`,
  `degen_ratio +0.393`. Lectura: los parses espagueti producen muchos
  triángulos con pocos vértices reales (ratio tris/verts alto) + degenerados.
- Para W1: la señal geométrica pura alcanza 0.775 (débil como gate único);
  0.923 en la banda elem≤255 la hace accionable como flag de revisión, no
  como gate. La regla compacta con warnings ya existe en el parser
  (warn_count + dedup-declined) — H3 confirma que no hay sustituto
  geométrico fuerte.

## H4 — Minería de targets (`w6_top_targets.py` → `top-targets.md`)

Ranking ROI por (familia × versión), `archivos × triángulos` (bytes como
proxy en clusters sin mallas). Top 3: `fail-unclassified` (366 arch,
1.09M tris, 529 MB — Submarino), `check:not-manifold` (357 arch, 713k tris,
250 MB), `check:empty-mesh` V5R24 (1 arch de 237 MB). Cada cluster lleva
hipótesis sugerida; top-10 archivos por cluster en la nota commiteada.

## Notas de entorno

- Corpus binario no está en el worktree (nunca se commitea): barrido de corpus
  vía `--corpus-root /home/alan/Documents/Repos/catpart-parser` (checkout en
  d8554e0). Snapshot Submarino ya extraído en `bench-submarine/snapshot/`.
- Visión requirió venv aparte (`w6-laya/venv-vision`, torch 2.15.0+cpu +
  torchvision 0.29.2+cpu + laya 0.5.2): el torch cu132 del venv laya es un
  build custom y ninguna torchvision publicada carga contra él (nms ABI).
  El venv laya quedó intacto (solo se añadió pillow, sin borrar nada).
- Latencias: texto ~2.5-5 s/fila CPU; imagen ~40-43 s/fila (2 hilos u 1).

## Siguiente paso

1. Clave de Jev → correr el gancho del residuo (comparación pendiente).
2. Reapertura del oráculo visual con renders del viewer real.
3. W1: destilar la regla tris/verts + degen_ratio como flag de revisión en
   la banda elem≤255 (0.923), empezando por los clusters del top-targets.
