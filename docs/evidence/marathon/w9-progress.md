# W9 progress — STEP oracle in assemblies / law R (round v4, 2026-11-22)

Branch `marathon/w9-step-assemblies`, base `d700b6d` (W5 law C). Data:
full Submarino snapshot at
`~/.local/state/catpart-parser/w9-sub/` (1.87 GB tarball sha
verified by extraction; binaries never committed — `/tmp` could not hold
the extraction, the session-state directory is used instead). All nine
snapshot `.stp` exports are used as oracle (W5 had four).

## Hypotheses and outcome

1. **4×4 matrices with mirror/scale** — RESOLVED NEGATIVE (1
   measurement): `p32 --rejected-census` finds 0 of the 111 raw `8d81`
   records rejected by the proper-rotation gate across all 199 documents
   (`w9-rejected-matrix-census-claims.csv`); no det < 0 and no scale ≠ 1
   bodies exist in the corpus, and all nine STEP exports carry proper
   rotations only (det = +1, unit columns). A synthetic mirror negative
   pins the gate's behavior (`p32 --selftest`).
2. **Instance registration variants** — NEGATIVE with reopening criteria:
   the remaining undecodable placing documents split into count-mismatch
   rotation-refuted / rotation-unattributable (`B4`, `Tuerc-pctrl`,
   `MB81-0001..0004`, `base-motor-Mtu`), count-mismatch multi-body (the
   swbd panels, cuerpo A3K/B3K/C3K — the STEP confirms their record
   rotation exactly but the per-row translation has no key), and
   identity-rotation count-matched shared bodies (0B2W-nut-bt,
   switchboard-control-01BW, battery banks, Door-Ade — no per-instance
   witness; the propagation reading dropped at attempt 1 against the
   switchboard counter-example). Reopen on the `ea`-oid object-stream
   decode (per-child key).
3. **The new STEP exports as ground truth** — DECISIVE: the three
   rotation-bearing exports (Control-power-room, Medio-Stern, MB81) keep
   per-instance ROTATIONS in their `ITEM_DEFINED_TRANSFORMATION`s
   (translations baked): 9 / 10 / 7 rotated instances, all pure 90°-
   multiple rotations. This gave the first per-instance rotation evidence
   for the binary placements and refuted law C's sharing rule as a
   universal law.

## Law R (landed): rotation-witnessed shared placements

The shared body `ba2a3c4e20f91f95` (`T = (−4682.6207, 0, 0)` mm, Rz(180°))
is count-matched in `MD-base-motor-01` (2 records == 2 own children) and
the MB81 export shows both children at Rz(180°) — rotation error 0.000000
deg per instance — while `MB81-0001/0003` carrying the same body have all
children at identity rotation. Law C's all-refused identity was an
**oracle-refuted identity** for those rows. Law R (in
`_name_table_placement` + byte-identical Rust mirror in
`port/src/product/binding.rs`): a document whose records are ALL one
shared body, count-matched, with a NON-identity rotation, binds the matrix
to every own child. Identity-rotation shared bodies keep the W5 refusal.

Walk-level movement (`w9-walk-delta-claims.csv`): MB81 placed 0 → **2**
(`MD-Base-R-01K`, `MD-Rubber-01K`), identity 163 → 161; every other root
byte-identical to W5. New roots walked: Compart-02A-mtu 0/13/0,
Control-power-room 10/168/17, Medio-Stern 10/242/22. Position checks: the
2 new placed rows carry bbox-containment error 0.000000 (raw units) and
rotation error 0.000000 deg; the W5 nut-bt placements are now ALSO
rotation-exact (0.000000 deg in two independent exports).

## Deliverables (committed on this branch)

* Law R in `src/catpart/fixtures_assembly.py` (`_name_table_placement`,
  `_ROTATION_WITNESS_IDENTITY`) + byte-identical Rust mirror
  `port/src/product/binding.rs` (`bind_name_table`, rotation-witness
  branch + docstring); walker census unchanged (law C classification).
* Probe `scripts/triage/p32_w9_step_oracle_join.py` (join / rejected
  census / body census / walk delta / parity / selftest) and p30 probe
  fixes (`PRODUCT_DEFINITION_FORMATION_WITH_SPECIFIED_SOURCE` subtype +
  post-pass `PRODUCT_DEFINITION → PRODUCT` resolution).
* Evidence CSVs: `docs/evidence/data/w9-step-oracle-join-claims.csv`,
  `w9-rejected-matrix-census-claims.csv`,
  `w9-shared-body-rotation-census-claims.csv`, `w9-walk-delta-claims.csv`.
* Tests: 4 new Python tests (3 synthetic law-R + MB81 real-file), 3 new
  Rust binding tests; 28 law/name-table pytest green; 234+ cargo tests
  green; full gate (check.sh) green — see the parity table in
  `docs/evidence/2026-11-22-w9-step-assemblies.md` (8 roots, Python = Rust
  canonical JSON; the four W5 SHAs unchanged).

## Next step

Decode the `ea <oid:u32>` object stream of `CATProdCont` to get a per-
child key: it resolves the count-mismatch class (which child owns the
rotated record in MB81-0002/base-motor-Mtu) and the multi-body panel rows
(which cuerpo owns which translation) — the two remaining classes of
undecodable rows, plus the 2 documented oracle-refuted identities.
