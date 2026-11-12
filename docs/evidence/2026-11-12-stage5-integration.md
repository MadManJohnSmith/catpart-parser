# Evidence: stage-5 integration of the stage-4b laws into the exporter (2026-11-12)

Ticket #34 (G6 stage 5): the two stage-4b decode laws land in
`src/catpart/geometry/composite.py` (branch
`t3/integrate-decode-laws-exporter`, base `e8a6f02`), ported from the
committed reference implementations (`scripts/triage/unabsorbed_pool_law.py`,
`scripts/triage/not_manifold_audit.py` — not re-derived):

- **The width-law extension** (R10/R11): `parse_strip_records` gains
  the u24be candidate (element counts above 65,535 cannot index in two
  bytes) and the loop-plane tiebreak (a candidate whose
  normal-carrying loops are non-coplanar against the record's stored
  normal loses to a coplanar one) — rank (tiling, repeats, oob,
  nonplanar, width, k).  The plane law is a tiebreak inside the width
  rank, NOT an export gate (the stage-3d decision stands).
- **The per-rep decomposition** (R1-R5): on the single-rep reading's
  absorption-gate failure, the store body reads as a sequence of reps
  — rep k = (the k-th `01 06` pool wrapper, the k-th walk-exact
  token-bearing list node, the strip records in that node's territory)
  — with per-rep absorption (verbatim f32, else within `NOISE_REL`
  1e-5 relative; measured noise <= 1.25e-8), per-rep M2b identity refs
  gate against the REP's element count, and per-rep triangulation
  merged into one mesh.  Fail-closed per rep: a rep that does not
  absorb or whose references leave its own element space stays
  unexported with the reason named — no guessing.
- **The curve-entry non-export rule is UNCHANGED** (stage-4a verdict,
  `2026-11-12-curve-entry-analysis.md` section 5).  **E0 is NOT
  implemented**: the 4a note's own order of operations gates E0 on a
  recomputation AFTER this integration ("the 4b laws ... will move
  fail-closed stores into the exported set and change which stores are
  empty-mesh; recompute E0 after the stage-5 integration ... then
  decide"), and the membership call on unverified geometry is the
  coordinator's — implementing the criterion now would bake in the
  pre-integration empty-mesh list.
- **Not in this dispatch**: the 4a-residue raw-array law (walk-mismatch
  family) and the U3-variant second layout family — no delta is
  expected from either.

Labels: **fact** = measured/cited from a committed artifact;
**inference** = derived, reasoning shown; **unknown** = open.

## Declared expected A/B delta (2026-11-12, written BEFORE the corpus run)

External-changeset gate rule (dispatch-recipes.md): the expected delta
is stated first; any unexplained delta is a stop-and-re-root-cause
gate.  Baseline: `identity-export-files.csv` @ `6e97ebd` (the 2026-11-12
post-3a regeneration) — 1,442 rows; exports 859 = 112 clean + 747
composite; L2 gate pass 782 (dev 734 = the accepted fitness row's
figure, held-out 48); error classes: missing-geometry-store 178,
malformed-store-header 0, undecoded-variant 405 (fact).

| # | family | expected delta | source |
|---|---|---|---|
| D1 | per-rep family (the 148 stage-3d-unabsorbed stores: 92 big + 56 small at the decode level, 92 + 55 at the seam) | **+147..+148 composite exports** (all 148 become composite rows: 111/148 absorb per-rep with no OOB reps (`per_rep_tol=1`, `refs_oob_reps=0`, unabsorbed-pool-files.csv); the 37 residue stores each carry >= 1 diagonal-absorbing in-bounds rep (unabsorbed-pool-reps.csv: good-reps-per-store 1..28), exported partially under per-rep fail-closed). The 1-store spread is the decode-vs-seam scope mismatch the 4b note names (92+56 decode vs 92+55 seam). | fact (census) + inference (partial-export semantics) |
| D2 | width law, `13bb5c0c` (element_count 236,385) | its records flip to u24be: triangles **5,855 -> 30,292** (byte-verified re-parse, 4b note); L2 **stays FAIL not-manifold** (15 residual non-manifold edges, `v2_manifold=0` in not-manifold-files.csv) — changed row, named | fact |
| D3 | width law, the not-manifold 29 | **21 re-measure manifold** (`v2_manifold=1`) and their other L2 components already pass (the 29 fail ONLY not-manifold, 4b note) -> **+21 L2 passes**; their PLY bytes change (the misread triangles are replaced) — 21 changed rows, named | fact |
| D4 | width law, the residual 8 (13bb5c0c + 7 normal-less non-tiling 0x42 stores) | unchanged rows: no stored normal -> the plane law is silent; nothing tiles -> no u24be candidate | fact |
| D5 | width law on every OTHER exported store (747 + the D1 gains) | **0 expected flips**: a width flip requires a (tiling, repeats, oob) tie or a u24be exact-tiling win; on exact-tiling records no different-width candidate can tie (the byte-length arithmetic pins (width, k) given the counts-sum law — count bytes are stream bytes, so a wider candidate needs all-zero ref bytes). Any flip that appears is named per-store with its record evidence. | inference |
| D6 | clean (112) + non-composite exports | **0 changed rows** (the composite path is not involved) | fact (code path) |
| D7 | L2 pass set | **superset of the baseline's 782; zero lost passes** (hard gate): expected 782 + 21 (D3) + (the passing share of D1's new exports — unknown split pass / empty-mesh / not-manifold, measured not projected) | declaration |
| D8 | error classes | undecoded-variant 405 -> 405 - (D1's count); missing/malformed unchanged | inference |
| D9 | replay digests (replay_export_seam.py, run at BOTH ends) | ply_sha256 + l2_fields_sha256 identical on every row EXCEPT the named changed rows (D2, D3) and the new exports (D1) | declaration |
| D10 | performance | no explosion: the identity decode is bounded (slowest export 1.37 s at baseline); u24be adds one width candidate per record | inference |

Interactions named in advance: the D1 reps' records parse under the NEW
width law — a rep lost to a width-induced OOB would be named (none
expected: the 111 carry no OOB reps under the old law, and the census's
4 OOB rep rows sit in the 37); `d748c70c`'s u16be-ceiling refs
(rep 13 max ref 65,359) may re-parse under u24be inside its partial
export.  A passing row regressing to L2 fail = STOP (D7).

## Observed A/B (filled AFTER the run)

Pending — this section is completed by the stage-5 corpus run; the
committed CSVs land with it (stage5-identity-export-files.csv + the
replay digests at both ends).

## Reproduction

```
ln -s /home/alan/Documents/Repos/catpart-parser/corpus corpus   # gitignored, read-only
.venv/bin/python -I scripts/triage/ab_identity_export.py --out-name stage5-identity-export-files.csv
git worktree add /tmp/catpart-stage5-base e8a6f02   # baseline replay end
cd /tmp/catpart-stage5-base && ln -s <main>/corpus corpus && .venv/bin/python -I scripts/triage/replay_export_seam.py --out-dir /tmp/stage5-ab
.venv/bin/python -I scripts/triage/replay_export_seam.py --out-dir /tmp/stage5-ab
```
