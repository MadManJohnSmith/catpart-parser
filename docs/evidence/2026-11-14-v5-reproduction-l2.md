# Reproduction run — the full L2 population (ticket #52, phase B)

- Margin: 0.0 (the owner's declared value, passed via --margin; declared-before-run per §3.4 — the dated declaration record lives in the spec §11 and the run note's prose)
- No --limit exists: this run is the FULL population (§3.1)

- Run stamp: 2026-11-14T20:29:51Z (UTC)
- Serving: python3 -m http.server 8933 --bind 127.0.0.1 --directory /home/alan/.t3/worktrees/catpart-parser/t3-7813376b-2d8698db85fed5fd/site (read-only static)
- Page requests: 60 total; external: 0
- Reference records: fitness/reports/20261113T231506Z-c2ab64.json (run_id 20261113T231506Z-c2ab64, corpus_digest dc75f8fe9156dd69…, manifest manifests/corpus-manifest.csv sha256-verified against it)
- CSV: `docs/evidence/data/v5-reproduction-l2-claims.csv` (1442 rows)
- Wall-clock: 76.0 s (measured)
- Per-file viewer seconds: n=1442, mean 0.052, max 0.837
- Per-file timeout: 300 s (a hit records a harness-error row)
- Outcomes: {'match': 1442}
- Split dev: population 1381, compared 1381, matched 1381, mismatched 0, harness-errors 0 (excluded per §3.4, named below), reference-unavailable 0 (named below)
  - rate 1.000000 vs published scalar 0.748009, |delta| 0.251991 vs margin 0.0 → EXCEEDED
- Split held-out: population 61, compared 61, matched 61, mismatched 0, harness-errors 0 (excluded per §3.4, named below), reference-unavailable 0 (named below)
  - rate 1.000000 vs published scalar 0.918033, |delta| 0.081967 vs margin 0.0 → EXCEEDED
