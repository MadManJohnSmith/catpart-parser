# W5 progress — assemblies / `CATProdCont` placement (round v3, 2026-11-22)

Branch `marathon/w5-assemblies`, base `d8554e0`. Oracle subset sha256
`d42ae23ee4a4d2acfb011b6ea98f7b8776300015e6d0ed51015e37ef6b9dc212` (tar),
`583afa59…ec60` (m2), `3e4bbfa5…4bcc` (m1) — all verified before use;
binaries stay in `/tmp/w5`, never committed.

## Hypotheses and outcome

1. **STEP oracle for `_Position` (8d81) join key** — RESOLVED NEGATIVE with
   a corpus law. The four STEP exports carry every
   `ITEM_DEFINED_TRANSFORMATION` as identity (positions baked into
   component geometry), so no instance↔matrix key exists in the exports;
   per-instance ground truth comes from the baked geometry frames instead.
   The decisive finding: the non-root `8d81` records are **shared connector
   frames** — one byte-identical body (`T = (-0.0, -2.241, 2179.457)` mm)
   appears in 13 unrelated documents; 6 shared bodies total (25 distinct
   bodies, 111 records, 199 documents). Binding them as instance placements
   puts children 18.1× outside the product's exported Z extent — the oracle
   refutes all 19 such rows the pre-W5 walk had "placed".
2. **Raise real `placed`** — done by *removing* false placements and
   oracle-confirming identity. Walk level over the 5 roots (428 rows):
   placed 24 → 5 (the 5 swbd nut-bt rows, body unique to their document,
   inside the export frame, per-instance error 0.000), undecodable 104 → 54
   (oracle-consistent identity for 50 refused-only rows), identity 300 →
   369. No identity-masking: every identity upgrade is either the
   zero-record law or the shared-body refusal, oracle-confirmed on the four
   STEP-backed products (`w5-oracle-placement-claims.csv`, 51 changed rows).
3. **Correlation table + negative with reopening criteria** —
   `docs/evidence/2026-11-22-w5-catprodcont-placement.md` §Negatives:
   no per-document structural discriminator (55 distinct 24 B headers /
   74 shared records — 2 attempts spent); unique-hash unbindable docs
   (B4 34-own-1-record, MB81-0004, swbd panel root, 3 mixed docs) stay
   fail-closed undecodable.

## Metric movement (before → after, walk level)

| root | placed | identity | undecodable |
|---|---|---|---|
| VM-vela-Mast | 5 → 0 | 22 → 45 | 18 → 0 |
| MD-swbd-panel-0A1w | 5 → 5 | 29 → 33 | 9 → 5 |
| BW-Flooding-compartment-sup | 2 → 0 | 41 → 43 | 11 → 11 |
| BW-section-bow | 10 → 0 | 63 → 85 | 12 → 0 |
| MD-MTU-16V-652-MB81 | 2 → 0 | 145 → 163 | 54 → 38 |

Position error per instance: the 19 removed false placements carried
2179.457 mm (Z) error against the oracle; they now decode identity with
0. The 5 surviving placements carry 0.000 mm against the swbd export frame.

## Deliverables (committed on this branch)

* Law C in `src/catpart/fixtures_assembly.py` (`_name_table_placement`
  + walker census) and the byte-identical Rust mirror
  `port/src/product/{binding,ownership}.rs`; parity seam
  `fidelity-cli tree` added to `port/src/bin/fidelity-cli.rs`.
* Probes: `scripts/triage/p30_step_oracle.py` (STEP oracle; selftest),
  `scripts/triage/p31_lawc_census.py` (census/walk/oracle/parity; selftest).
* Evidence CSVs: `docs/evidence/data/w5-matrix-census-claims.csv`,
  `w5-matrix-census-files-claims.csv`, `w5-walk-delta-claims.csv`,
  `w5-oracle-placement-claims.csv` (per-instance error).
* Tests: 5 synthetic law-C tests + 2 updated real-file tests (Python),
  4 walker + 3 binding tests (Rust). 232 cargo tests green; 71 targeted
  pytest green; fixture suites green (26); claims-CSV hygiene green (88
  files).

## Parity (Python = Rust, canonical JSON sha256)

| root | sha256 |
|---|---|
| VM-vela-Mast | `9183874af43b8134cf78a0c2d5de2dae8364354196ce82b0e3f2a3bfa22749f8` |
| MD-swbd-panel-0A1w | `e543521da47c8a99f4529d02b46528c5765bef5bedca92d008f44696797080a1` |
| BW-Flooding-compartment-sup | `6e6463b0064053d9e368b3755feb8956184924c49463913cceca0f791bc0e9b1` |
| BW-section-bow | `9941bd3b9234d546ecc4e92a2b4c741da629190e8b00bd8496a3463f01155b4d` |
| MD-MTU-16V-652-MB81 | `5208f15dcacfc8a7e59bda8c703fd305edd20c438d9d890cdc517c97c2cad509` |

Method: both sides canonicalized (`json.dumps(sort_keys=True)`) before
hashing; `fidelity-cli tree` drives the same 199-document set.

## Next step

Decode the `ea <oid:u32>` object stream of `CATProdCont` (vela: 77 oids,
dense 1–78) to separate connector objects from instance objects per
document — that would turn the set-relative law C into a per-document law
and let the remaining 54 undecodable rows (unique-hash unbindable docs)
resolve. Second: a connector-bearing STEP export would confirm the frames'
geometric meaning.
