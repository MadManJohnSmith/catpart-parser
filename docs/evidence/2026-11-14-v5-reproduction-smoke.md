# Reproduction harness — fixture machinery smoke (ticket #52, phase A)

**MACHINERY VALIDATION ONLY — NOT A RATE.** The rows below are
A2 synthetic fixtures driven to prove the harness machinery
(page load, feed, per-check read, comparison, CSV write).
They are not a population measurement and must not inform the
§3.4 margin, whose inputs are native Fidelity evidence only.

- Run stamp: 2026-11-14T19:58:34Z (UTC)
- Serving: python3 -m http.server 8933 --bind 127.0.0.1 --directory /home/alan/.t3/worktrees/catpart-parser/t3-00bc2093-6ea3b6053084fd39/site (read-only static)
- Page requests: 10 total; external: 0
- Reference records: the shipped fitness seam over a generated mini-manifest (in-run temp report, not committed): 11 l2 records
- CSV: `docs/evidence/data/v5-reproduction-smoke-claims.csv` (10 rows)
- Wall-clock: 0.8 s (measured)
- Per-file viewer seconds: n=10, mean 0.031, max 0.108
- Per-file timeout: 300 s (a hit records a harness-error row)
- Outcomes: {'match': 10}
- Comparison branches exercised: {'degenerate-triangles': 2, 'malformed-pool-vertex': 1, 'malformed-store-header': 1, 'missing-geometry-store': 1, 'not-manifold': 1, 'pass': 3, 'undecoded-variant': 1}
