# Fidelity run — fixture-mode (A2 fixtures, generated in-process via tests/fixtures_gen.py)

- Run stamp: 2026-11-14T18:09:55Z (UTC)
- Slice: L1 slice (inspect document equality) + L2 export slice on fixtures (summary + PLY bytes + error classes, §3.2); composite-family variants covered through port stage 3 of 3 (ticket #42's internal order: walk + per-rep -> raw-array + mixedwrite -> dup-pin + dedup + curve exposure)
- CSV: `docs/evidence/data/v3-fidelity-fixture-claims.csv` (334 rows)
- Wall-clock: 19.7 s (measured, both subprocess passes included)
- Outcomes: {'match': 334}
- Mismatches (output-mismatch + error-class-mismatch): 0
- Harness-level failures (never matches, §3.2): 0
- Population by split: {'fixture': 334}
- Population by kind: {'part': 313, 'product': 21}
- Population by magic_ok: {'n/a': 334}
- Subprocess time totals: python 18.5 s, port 0.8 s
- §4 budget (per-ticket sample runs ≤ 15 min at N=100): WITHIN at N=334
