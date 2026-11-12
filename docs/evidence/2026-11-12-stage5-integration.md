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

## Observed A/B (2026-11-12, post-declaration run; correction of D4/D5 dated here)

Corpus: 1,442 parts, dev + held-out.  Runs: `ab_identity_export.py`
(→ `stage5-identity-export-files.csv`, committed) and
`replay_export_seam.py` at BOTH ends (→ `stage5-replay-baseline.csv` /
`stage5-replay-stage5.csv`, committed; the baseline end replays the
`e8a6f02` src — the main checkout at this base).

**First run FAILED the preservation gate, root-caused and fixed before
acceptance (dated correction):** with the u24be candidate offered
unconditionally, 4 exported stores (4436caff, 4ff7b61b, 6b05e15d,
d4eace9b — element counts 657..26,127, all <= 65,535) flipped to
3-byte junk parses: on interleaved (non-tiling) records a u24be
candidate can land exactly on the next header and wins on TILING
before the oob rank fires, and the refs gate then fails the whole
store — 4 lost L2 passes (hard gate: zero).  Fix: the u24be candidate
is offered only when `element_count > 65,535` (the brief's own
wording, and R10's scope: a 2-byte ref cannot index such an element
space; below it a 3-byte candidate only reads junk past it).  Re-run:
gate green.  The 4b reference (`parse_width_test`) has the same
exposure — its analysis covered the 29 not-manifold stores only; the
integration A/B is where it surfaces (the handoff's verification-scope
note, confirmed).

**Declared vs observed:**

| # | declared | observed | verdict |
|---|---|---|---|
| D1 | +147..+148 composite exports from the 148-family | **+148: all 148 export** (L2 split: 117 pass, 19 not-manifold, 12 empty-mesh) | met |
| D2 | 13bb5c0c triangles 5,855 -> 30,292, stays not-manifold | exact (30,292; fail not-manifold — the 4b re-test's 15 residual edges) | met |
| D3 | +21 L2 passes from the width-fixed not-manifold set | **+21, exactly the `v2_manifold=1` set** (16 with identical v/t, 5 with width-flip v/t changes) | met |
| D4 | residual 8 unchanged | **corrected**: 26504a08 (residual 8) flipped a normal-carrying record u8 -> u16be (270 -> 268 triangles) and stays not-manifold; the other 7 unchanged | corrected, named |
| D5 | 0 width flips on other exported stores | **corrected**: the plane tiebreak re-parses **155 records on 59 exported stores, ALL u8 -> u16be** on non-tiling (interleaved) records — the tie vector the declaration missed: on non-tiling records u8/u16be tie on (tiling, repeats, oob), and the demoted u8 loops are TESTED-nonplanar while the promoted u16be loops are UNTESTED (refs hit skip slots — the check bypasses them, the 4b reference's own semantics).  Net measured effect: +21 not-manifold -> pass, +2 degenerate-triangles -> pass (5f8f00de, 78685667 — near-duplicates, +4 triangles each, under the cap; NOT in the declared +21, named), 9 pass -> pass with small triangle decrements (-2..-8), 24 pass -> pass with identical v/t, 2 fail -> fail (13bb5c0c, 26504a08).  **0 lost passes.** | corrected, named |
| D6 | clean + non-composite unchanged | 0 changed rows (112/112; the 36 recovery-clean preserved) | met |
| D7 | pass set superset, zero lost passes | **782 -> 926 (+144; dev 734 -> 871, held-out 48 -> 55); 0 lost exports, 0 lost passes** | met |
| D8 | undecoded-variant 405 - D1 | 405 -> 253: -148 family - **4 census-blind unabsorbed stores** (1f03e69c, 72e19c62, abbd842d, bdf09b28 — baseline detail "unabsorbed variant", outside the 4b census because the seam's stage-3a recovery reaches stores the census's strict locator does not; per-rep applies at the seam's span).  missing 178, malformed 0 unchanged | met + named extra |
| D9 | digests identical outside named rows | exported-both 859: **799 byte-identical** (PLY + L2 fields), 60 PLY-diff — all composite, all mapped above (59 plane-tiebreak + 13bb5c0c u24be); 6 of the 60 change PLY bytes with identical L2 fields (triangle content changed, counts/bbox/stats coincided) | met |
| D10 | no explosion | replay wall time comparable both ends; no timeouts | met |

**Accounting (every changed row mapped):**

- exports 859 -> **1,011** (+152: 148 family + 4 census-blind; 0 lost);
  composite 747 -> 899 (the 747 single-rep exports all still export
  through `identity-table-walk`; +152 through `identity-per-rep`).
- L2 pass 782 -> **926** = 782 preserved + 117 (family) + 4
  (census-blind) + 21 (the 4b width set) + 2 (5f8f00de/78685667).
- PLY/L2-digest change set: 152 new exports + 60 width-law rows; every
  other row byte-identical.
- The brief's other reference figures are NOT part of this delta: the
  raw-array law (~29-31) and U3-variant are not integrated here; E0
  (+24 max) not implemented (above).

**Residual / open (named):** (1) the plane tiebreak promotes
untested-on-skip-slots parses over tested-nonplanar ones — the 4b
reference's semantics, net L2-positive here (+23 fixes, 0 losses), but
a stricter rule (prefer tested-coplanar, fall back to the committed
rank otherwise) would revert the 7 fail->pass flips; left as the 4b
law, named for review.  (2) 19 family exports fail not-manifold and 12
empty-mesh — per-store rows in the committed CSV.  (3) The seam-scope
mismatch the 4b note named (92+55 vs 92+56) resolved: the 148th store
was census-invisible like the 4 (locator reach), not seam-path
different.

## Reproduction

```
ln -s /home/alan/Documents/Repos/catpart-parser/corpus corpus   # gitignored, read-only
.venv/bin/python -I scripts/triage/ab_identity_export.py --out-name stage5-identity-export-files.csv
# replay at both ends (baseline end = the main checkout's src @ e8a6f02):
mkdir -p /tmp/stage5-base/scripts/triage && cd /tmp/stage5-base
ln -s <main>/src src; ln -s <main>/manifests manifests; ln -s <main>/corpus corpus
cp <worktree>/scripts/triage/replay_export_seam.py scripts/triage/
python3 -I scripts/triage/replay_export_seam.py --out-dir /tmp/stage5-ab --out-name replay-baseline.csv
cd <worktree>
.venv/bin/python -I scripts/triage/replay_export_seam.py --out-dir /tmp/stage5-ab --out-name replay-stage5.csv
# per-row join + digest comparison: the committed stage5-claims.csv rows
```

Committed artifacts: `stage5-identity-export-files.csv` (the seam A/B,
1,442 rows), `stage5-replay-baseline.csv` / `stage5-replay-stage5.csv`
(PLY + L2-fields digests at both ends, 1,442 rows each),
`stage5-claims.csv`.
