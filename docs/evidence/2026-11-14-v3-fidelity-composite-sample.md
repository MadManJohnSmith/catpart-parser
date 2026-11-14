# Fidelity run — corpus-mode

- Run stamp: 2026-11-14T18:10:51Z (UTC)
- Slice: L2-export slice (§3.1: the kind=part rows), V3 composite-family-stratified sample (ticket #42: per-family seats from the stage-15 roster, every firing law and the fail-closed composite class included): summary parsed-document equality + PLY byte-identical + error_class equality on double refusals (§3.2); the composite path is ported — composite-path exports compare fully incl. the composite block (a port refusal against a twin export is a mismatch)
- CSV: `docs/evidence/data/v3-fidelity-l2-claims.csv` (452 rows)
- Wall-clock: 56.0 s (measured, both subprocess passes included)
- Outcomes: {'match': 452}
- Mismatches (output-mismatch + error-class-mismatch): 0
- Harness-level failures (never matches, §3.2): 0
- V3 composite-family sample (stage-15 roster, ticket #42): 100 seats per family, sampled 452; per family — composite-fail-closed: 144 in the roster, 100 drawn; identity-mixedwrite-reps: 88 in the roster, 88 drawn (ran in full — the family is smaller than the seat quota); identity-per-rep: 156 in the roster, 108 drawn; identity-raw-array: 28 in the roster, 28 drawn (ran in full — the family is smaller than the seat quota); identity-table-walk: 789 in the roster, 128 drawn
- Forced firing-law rows (59): stage14-dup-pin-ceiling.csv (26 dup-pin firing rows) + stage14-notmanifold-mechanism.csv (33 dedup-fire-surface rows)
- Sampled by export outcome class: {'fail': 61, 'pass': 291, 'undecoded-variant': 100}
- Population by split: {'dev': 430, 'held-out': 22}
- Population by kind: {'part': 452}
- Population by magic_ok: {'yes': 452}
- Subprocess time totals: python 46.6 s, port 9.3 s
- §4 budget (per-ticket sample runs ≤ 15 min at N=100): WITHIN at N=452
