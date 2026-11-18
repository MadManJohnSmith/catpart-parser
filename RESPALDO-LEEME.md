# Respaldo catpart-parser — 2026-11-07 (pre-formateo)

Contenido y verificaciones reales hechas:

- `catpart-parser-all.bundle` — bundle `--all` del repo (rama `main` @ `840606d` y `research/corpus-routes` @ `f114f46`, 6 refs, historial completo). `git bundle verify` OK en esta ubicación. Restaurar: `git clone catpart-parser-all.bundle catpart-parser` (o clonar de GitHub, que ya tiene todo: push verificado `88f3fd5..840606d`).
- `corpus/` — copia completa de los 1824 archivos .CATPart/.CATProduct (3.4 GB). **Verificado: 1824/1824 archivos con sha256 idéntico al `manifests/corpus-manifest.csv` del repo; 0 faltantes, 0 mismatches.**
- `redownload_corpus.py` — script de redescarga desde las source_url del manifiesto (por si el corpus de respaldo se pierde; los repos de origen son de terceros y pueden haber desaparecido).

Decisión del dueño (2026-11-07, por ask): respaldar el corpus completo — evidencia primaria, no regenerable con garantías (repos de terceros).

Muere deliberadamente (regla regenerable):
- `.venv/` y `__pycache__/` — regenerables (`pip install -e .[test]`).
- `/tmp/b3a/` y `/tmp/b3a-payload-strings.csv` (paso a del ticket #19) — superados por los datos commiteados más amplios (`docs/evidence/data/container-payloads-scan.csv`, 114 archivos ⊇ los 10 del paso a) y por `scripts/triage/decode_container_payloads.py`.

No hay cambios sin commit ni ficheros sin trackear en el repo (inventario Fase 1: árbol limpio; único blob colgante de 3088 bytes sin valor).
