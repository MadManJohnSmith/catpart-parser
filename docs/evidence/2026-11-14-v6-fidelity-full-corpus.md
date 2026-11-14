# Fidelity run — corpus-mode

- Run stamp: 2026-11-14T21:34:43Z (UTC)
- Slice: L1-JSON slice (§3.1: ALL manifest rows — parts, products and the magic_ok=no junk); --slice both: the L2 export comparison runs on the part rows of the same sample (summary + PLY bytes + error classes; composite-path exports compare fully (ported at V3 #42))
- CSV: `docs/evidence/data/v6-fidelity-full-corpus-claims.csv` (3266 rows)
- Wall-clock: 235.5 s (measured, both subprocess passes included)
- Outcomes: {'match': 3266}
- Mismatches (output-mismatch + error-class-mismatch): 0
- Harness-level failures (never matches, §3.2): 0
- Population by split: {'dev': 3132, 'held-out': 134}
- Population by kind: {'part': 2884, 'product': 382}
- Population by magic_ok: {'no': 10, 'yes': 3256}
- Subprocess time totals: python 214.0 s, port 20.7 s
- §4 budget (per-ticket sample runs ≤ 15 min at N=100): WITHIN at N=3266
