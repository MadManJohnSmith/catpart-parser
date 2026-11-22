# W9: the STEP oracle in assemblies — rotation witness, law R (2026-11-22, Python + Rust)

Marathon round v4, worker W9 (assemblies). Base `d700b6d` (W5 law C), branch
`marathon/w9-step-assemblies`. Oracle: **all nine** snapshot `.stp` exports
(W5 used four; W9 adds `MD-Compart-02A-mtu`, `MD-Control-power-room`,
`MD-Medio-Stern`, `MD-MTU-16V-652-MB81` and the second sail export
`submarine-Tr-1700-S42-vela-Mast`), joined per instance against the binary
walk (`scripts/triage/p32_w9_step_oracle_join.py`, probe reproduction; data
subset `~/.local/state/catpart-parser/w9-sub/`, binaries never committed).

## The five new STEP exports (fact)

`p30 --instances` on the snapshot's five unused exports (probe fixed first,
see below): 13 NAUO (Compart-02A-mtu, all identity), 195 (Control-power-room,
186 identity + **9 rotated**), 277 (Medio-Stern, 267 + **10 rotated**), 214
(MTU-16V-652-MB81, 207 + **7 rotated**), 33 (submarine-vela, all identity).

Unlike W5's four exports (all 229 transforms identity), the three
rotation-bearing exports keep **per-instance rotations** in their
`ITEM_DEFINED_TRANSFORMATION`s while baking the translations into the
component geometry: every rotated instance carries `T = (0, 0, 0)` with a
pure rotation (det = +1.0, column norms 1.0, angles exact multiples of
90° — Rz(−90°) for the swbd nut/cuerpo families, Rz(180°) for the MB81
base-motor/escape families). No export shows a mirror (det < 0) or a scale
≠ 1. The per-file scale law (raw → mm) extends W5's: Control-power-room /
Medio-Stern / Compart-02A-mtu carry `SI_UNIT(.MILLI., .METRE.)` and
millimetre values; MB81 carries metre values with no MILLI clause; the
second sail export is metre-scaled in a foreign (full-ship) frame and gets
no absolute-frame check.

Probe fixes (`p30_step_oracle.py`, both affecting parent/child attribution
only): the formations are written as the `PRODUCT_DEFINITION_FORMATION_
WITH_SPECIFIED_SOURCE` subtype (previously unmatched → `parent = None` for
every MB81 instance), and `PRODUCT_DEFINITION → PRODUCT` resolves in a
post-pass (forward references lost the join at parse time).

## Hypothesis 1: mirror/scale matrices — negative (fact, 1 measurement)

The corpus carries **zero** records the proper-rotation gate rejects:
`p32 --rejected-census` over all 199 documents finds 111 raw `8d81`
records, 0 rejected (`docs/evidence/data/w9-rejected-matrix-census-claims.csv`,
one row per document). There are no det < 0 bodies and no scale ≠ 1 bodies
in the snapshot, so the "rejected mirror/scale matrices" of the dispatch
hypothesis do not exist in this corpus; the gate's behavior is pinned by a
synthetic negative in `p32 --selftest` (diag(1, 1, −1) → rejected,
classified `mirror-det-negative`). No code change: accepting mirror/scale
matrices would have no oracle support (all nine exports carry proper
rotations only) and no corpus case.

## The per-instance join (fact)

`p32 --join` keys every STEP `NEXT_ASSEMBLY_USAGE_OCCURRENCE` to the walk
row `(parent product, instance name)` across the nine exports
(`docs/evidence/data/w9-step-oracle-join-claims.csv`, one row per instance
with walk status, STEP transform class, rotation error, bbox containment).
Results (fact):

* **Every rotated STEP instance's rotation is matched by a binary record
  body — or by nothing.** The 5 `MD-nut-bt-23..27` rows placed by
  `MD-swbd-0C3W-nut-bt` (W5 S7, unique body `2d93e9c5ce346cf4`) match their
  STEP rotation **exactly** (rotation error 0.000000 deg, in both
  Control-power-room and Medio-Stern — two independent exports), and the
  translation `(1048.576, −741.877, 0)` mm is inside the Control-power-room
  export frame (bbox containment error 0.000000, raw units). The W5
  bbox-only confirmation of the nut-bt family is now rotation-exact.
* The `MD-swbd-cuerpo-C0K..C3K` instances (children of panel-0C3W) are
  STEP-rotated Rz(−90°) with `T = 0`; the panel document's 4 records carry
  exactly that rotation (3 distinct bodies, translations along the panel
  row). 4 records cannot be attributed to 5 own children with a distinct
  body per row — the rows stay **undecodable** (fail-closed), now with the
  documented per-instance rotation evidence. Binding the rotation alone is
  refused: the export's `T = 0` is the baked geometry, not the child's
  position, so a rotation-only placement would collapse the row to the
  parent origin (invented, not decoded).
* `MD-hatch_down_31` (child of `MD-Hatch-middle-diesel`, Medio-Stern) is
  STEP-rotated Rz(180°); its document's 4 records carry Rz(180°) **about Y**
  (`539e0f6ebc6c8b97`, 180° rotation error against the STEP) plus two copies
  of the 13-document connector body. The true placement rotation is absent
  from the binary — the mixed-refusal fail-closed state stands, and no
  record is bindable.
* `Tuerc-pctrl` (1 record, 2.55° tilt about X) and `MD-MTU-16V-652-B4`
  (1 record, 0.56° tilt about X): their own children are **all STEP-identity**
  in every covering export — the tilted records are rotation-refuted as
  child placements (they cannot bind any child). The count-mismatch
  undecodable state stands with the negative documented.
* `MD-MTU-16V-652-MB81-0004` (3 identical records, `T = (−80.44, 0, 0)`,
  identity rotation, 4 own children): children all STEP-identity;
  rotation-compatible, translations baked, `3 ≠ 4` unattributable —
  undecodable stands.

## Law R: rotation-witnessed shared placements (landed, walker-only)

The corpus census with per-document count-match state
(`docs/evidence/data/w9-shared-body-rotation-census-claims.csv`: 6 shared
bodies, 27 (body, document) rows, 11 count-matched) refutes law C's
sharing rule as a universal law and bounds it (fact):

* The shared body `ba2a3c4e20f91f95` (`T = (−4682.6207, 0, 0)` mm,
  **Rz(180°)**) is carried by 5 documents. In `MD-base-motor-01` it is
  count-matched (2 records == 2 own children) and the MB81 export shows
  **both** children (`MD-Base-R-01K`, `MD-Rubber-01K` — each instantiated
  twice in the export; the name-level law covers every instance) at
  Rz(180°), `T = 0`: rotation error 0.000000 deg per instance, the baked
  translation inside the MB81 export frame. Under W5 law C those 2 walk
  rows (4 exported instances) decoded identity — an **oracle-refuted
  identity** (the export proves they are not identity). W5 could not see
  this: its four exports did not cover MB81.
* In `MB81-0001`/`MB81-0003` the SAME body is carried by 1 record against
  4 own children, and the MB81 export shows **all** their children at
  identity rotation — the record is refuted as a placement for every
  candidate child there. In `MB81-0002`/`MD-base-motor-Mtu` exactly one
  child is STEP-rotated Rz(180°) (the record matches that child's rotation
  byte-exactly), but 1 record against 4 own children has no per-child key.
  Binary structure is identical across the four documents and the per-
  instance truth differs — no structural law can separate them (negative,
  see below).
* The identity-rotation count-matched shared bodies (`9178dabde3636d53` in
  6 documents, `09d5c78f312dfeac` in the two battery banks, `ecde1383cc94a778`
  in `BW-Door-Ade`, `55036aec9129c58e` in `MD-swbd-0B2W-nut-bt`) keep the
  W5 refusal: an identity rotation cannot distinguish a placement from a
  connector frame, and W5's vela/flooding/bow extent refutations cover the
  `9178dabd`/`ecde1383` class.

**Law R (landed, walker-only, `bind_name_table` / `_name_table_placement`)**:
a document whose records are ALL one shared body, count-matched to its own
children (`#R == #own(D)`), with a NON-identity rotation, binds the matrix
to every own child. Identity-rotation shared bodies keep the W5 refusal;
Clause 3 identity frames never place; mixed sets stay fail-closed. The
binding stays name-level: every instance of a bound name takes the matrix
(the export confirms this for the twice-instantiated `MD-Base-R-01K` /
`MD-Rubber-01K`).

Walk-level movement (`docs/evidence/data/w9-walk-delta-claims.csv`; the
committed W5 counts are the `*_w5` columns):

| root | placed | identity | undecodable |
|---|---|---|---|
| VM-vela-Mast | 0 (W5: 0) | 45 | 0 |
| MD-swbd-panel-0A1w | 5 (W5: 5) | 33 | 5 |
| BW-Flooding-compartment-sup | 0 (W5: 0) | 43 | 11 |
| BW-section-bow | 0 (W5: 0) | 85 | 0 |
| MD-MTU-16V-652-MB81 | **2** (W5: 0) | 161 (W5: 163) | 38 |
| MD-Compart-02A-mtu (new) | 0 | 13 | 0 |
| MD-Control-power-room (new) | 10 | 168 | 17 |
| MD-Medio-Stern (new) | 10 | 242 | 22 |

The 2 MB81 rows carry rotation error 0.000000 deg and bbox containment
error 0.000000 (raw units) per instance. All other walked roots are
byte-identical to W5 (the four W5 parity SHAs are unchanged).

## Hypothesis 2: instance registration variants — negative with reopening criteria

The remaining undecodable placing documents are, per instance-name
registration, one of:

1. **Count-mismatch with a rotation-refuted or unattributable record**
   (`MD-MTU-16V-652-B4` 1/34, `MB81-0004` 3/4, `Tuerc-pctrl` 1/2,
   `MB81-0001/0002/0003` 1/4, `base-motor-Mtu` 1/4): the count law fails
   and — where the covering export is rotation-bearing — the record is
   either refuted for every candidate child (B4, Tuerc) or matches exactly
   one child (0002, base-motor-Mtu) with no per-child key in the bytes.
2. **Count-mismatch with multi-body records** (the swbd panels 4/5, the
   cuerpo A3K/B3K/C3K documents 2/4): the STEP confirms the records'
   rotation exactly, but the per-row translation has no key; a rotation-
   only binding is refused (the export's `T = 0` is baked geometry).
3. **Identity-rotation count-matched shared bodies** (`MD-swbd-0B2W-nut-bt`
   5/5 — the B-panel sibling of the placed A/C nut families — plus
   `MD-switchboard-control-01BW` 6/6, the battery banks 3/3, `BW-Door-Ade`
   2/2): no per-instance witness exists (rotation identity everywhere,
   translations baked), so the W5 refusal stands. The propagation reading
   (the panel's copy of `55036aec` is the nut sub-product's frame) was
   **dropped at attempt 1**: `MD-switchboard-control-01BW` is a child of
   `MD-Control-power-room`, which carries `9178dabd` 7 times — the same
   ancestor-carries-descendant's-body shape whose binding W5's oracle
   refutes in vela/bow, so the shape cannot discriminate.

*Reopen when*: the `ea <oid:u32>` object stream of `CATProdCont` yields a
per-child key (W5's standing next-step — it would resolve class 1's
"which child" and class 2's row order), or a connector-bearing export /
per-product oracle for the battery/switchboard subtrees lands (class 3).

Known fail-closed cost (documented, not maskable further): 2 walk rows
(3 exported instances) remain oracle-refuted identities in the MB81 walk
(`MD-escape-mtu-B2YR` bound identity by MB81-0002's all-refused law,
`MD-base-motor-01` bound identity by base-motor-Mtu's, instantiated twice
in the export) — both carry STEP rotations their documents' record counts
cannot attribute.

## Parity and tests

* Python `resolve_owned_assembly` vs Rust `fidelity-cli tree`: canonical
  JSON sha256 byte-identical on all **eight** walked roots (`p32 --parity`;
  the four W5 SHAs are unchanged; MB81's moves `5208f15d…` → `c6461e7d…`
  with the 2 law-R rows):

| root | sha256 (Python = Rust) |
|---|---|
| VM-vela-Mast | `9183874af43b8134cf78a0c2d5de2dae8364354196ce82b0e3f2a3bfa22749f8` |
| MD-swbd-panel-0A1w | `e543521da47c8a99f4529d02b46528c5765bef5bedca92d008f44696797080a1` |
| BW-Flooding-compartment-sup | `6e6463b0064053d9e368b3755feb8956184924c49463913cceca0f791bc0e9b1` |
| BW-section-bow | `9941bd3b9234d546ecc4e92a2b4c741da629190e8b00bd8496a3463f01155b4d` |
| MD-MTU-16V-652-MB81 | `c6461e7d925d512af3c7758876cb6fe6672c5a0a289f5bb8957646a4a2e54136` |
| MD-Compart-02A-mtu | `71e4c0813c790d8197074a0fe07f6a8417b276fa0c9f4f9a62b146889fb74960` |
| MD-Control-power-room | `55dc463f7874375b801e34d192cd15c8da940f36ecbf2bfb15b8b31c6f028a38` |
| MD-Medio-Stern | `96d3edc9a3a4c76ae3d55fd9c625bc35bfb4ef262833da1114bd58fbb1bae363` |

* Rust `port/src/product/binding.rs` mirrors law R byte-identically
  (detail strings); 3 new binding tests (rotation witness places, identity
  rotation refused, count-mismatch negative). Python: 4 new tests in
  `tests/test_product_placed_law.py` (3 synthetic + the MB81 real-file
  test); the 28 law/name-table tests are green.
* Probe: `scripts/triage/p32_w9_step_oracle_join.py` (join / rejected
  census / body census / walk delta / parity / selftest).

## Negatives and reopening criteria

1. **No mirror/scale matrices in the corpus** (fact, 1 measurement): 0/111
   records rejected; the hypothesis's premise is empty for this snapshot.
   *Reopen when*: a new corpus revision carries det < 0 or scale ≠ 1
   `_Position` bodies (the per-document CSV then classifies them).
2. **No per-child key for count-mismatched documents** (2 attempts' worth
   of structure probed via the count/rotation table): `MB81-0001` vs
   `MB81-0002` are binary-identical in structure with opposite per-instance
   truth — no document-local law separates them. *Reopen when*: the
   `ea`-oid object stream decode separates instance objects per document.
3. **Identity-rotation shared bodies have no per-instance witness** (1
   attempt: the propagation law, dropped against the
   switchboard-control-01BW counter-example). *Reopen when*: a
   connector-bearing STEP export or the `ea`-oid decode lands.
