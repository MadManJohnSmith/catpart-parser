# W18 — the half-read-gated wider tie: NEGATIVE (inert on its activation class, loses the 4 fixes)

**Branch**: `marathon/w18-halfread-wider` (rebased onto main `647f324` —
W3 reverted, W7-B patch 003 restored). **Date**: 2026-11-22. **Host**:
Gallyfrey. **Runtime change shipped: none.** Two triage probes and this
note are the deliverable.

## The proposed law and why it was re-opened

The W7-B 003 wider tie (`255 - width` on full rank ties) was reverted
on 8851273 under the belief that it flipped First_Back_Shell and
backshell_M; the revert message proposed re-landing it gated on W1's
anti-half-read signature. This session first established the premise
was wrong: a per-commit bisect on First_Back_Shell
(`scripts/triage/w18_l2_gate.py`, per-commit `src` on each of
da16f56 → d8554e0 → the wave merges → 8851273) attributes the flip to
**W3's merge 528a0a0** (E5 exact B-spline surfaces), not to the tie
law; the Orquestador independently reached the same verdict and restored
003 (88b1fa6) after reverting W3 (373b234). With 003 restored the two
files are PASS again at the canonical figures (2,220 / 3,320 triangles,
0 degenerates) and carry **zero** full ties (`w18-tie-dumps/`), so they
never exercised the width slot at all.

The gate remained open as an optional robustness measure, with a strict
acceptance condition: preserve the 4 fixes and 0 pass→fail. Measured
result: **it fails the condition, and it is structurally inert where it
does fire.**

## Measurement 1 — the fix class carries no W1 signature (fact)

`scripts/triage/w18_tie_signature_probe.py` logs every vote the
restored-003 base resolves through the width slot over a tied u8
candidate (keys equal on every slot except width 6) and measures W1's
signature on the narrow block (even bytes 0x00 over the 2n span,
n >= 8, u16be re-read outside the element space). Dumps committed at
`docs/evidence/data/w18-tie-dumps/`, counts in
`docs/evidence/data/marathon-w18-halfread-gate-claims.csv`:

| file | full ties (w6-decided) | W1-signed narrow | L2 @ 647f324 |
| :--- | ---: | ---: | :--- |
| Guntle.ver5 | 16 | 0 | pass (3,093 tri) |
| M3x16_CHC | 2 | 0 | pass (1,702 tri) |
| LedStrips_5V_final | 36 | 0 | pass (16,130 tri) |
| First_Back_Shell | 0 | — | pass (2,220 tri) |
| backshell_M | 0 | — | pass (3,320 tri) |

Every logged tie is the Class C shape (e.g. Guntle `3815992`: u8
`[8, 113, 9, 58]` vs u16be `[2161, 2362, 2270, 2407]` — the u8 refs are
the byte interleave of the wider stream), and **not one** carries the
signature: the wider re-read is in-bounds on all of them. Under the
gated law these ties resolve narrow — the pre-003 resolution — whose
outcome is measured, not projected: re-running the gate harness on the
003-reverted state 8851273 gives Guntle **fail not-manifold** (2,984
tri / boundary 1,096), M3x16 **fail not-manifold** (1,702 / 1,403),
LedStrips_5V **fail not-manifold** (15,860 / 4,331). Smooth is the same
class per the W7-B committed note (pre-003: FAIL degenerate-triangles,
33) — inference, not re-measured here.

## Measurement 2 — the signature's class is decided before the width slot (rank structure)

The signature **requires** the u16be re-read to be OOB. In the rank
tuple the OOB slot (position 1) precedes the width slot (position 6),
so a vote where the gate's condition fires resolves identically under
the plain narrow law:

* u8 refs in-bounds + wider re-read OOB → the wider candidate loses on
  the OOB slot; narrow wins with or without the gate.
* u8 refs also OOB (the acc-Cont-Lft permuted-garbage case) → the
  winner is declined by the #66 post-vote gate (and the record was
  already covered by W1's committed decline, 031e508); the width slot
  only picks which decline path, not the outcome.

The only theoretical exception would be a signed u8 tied against a
clean u24be candidate (extended/P1g families, element_count > 65,535):
unmeasured on the corpus, and preferring u24be junk over the u8 there
is not evidence the gate's author intended. The probe's `--selftest`
pins the discriminating edge both ways: a synthetic signed block
(even bytes 0x00, re-read OOB) is detected; Guntle `3815992`'s real
block is NOT — the documented non-discrimination.

## Why there is no byte-level gate for Class C

At vote time both candidates of a Class C tie are viable, in-bounds,
repeat-free, plane-clean and non-exact; the u8 refs being the byte
interleave of the wider stream is trivially true for every u8/u16be
pair on the same bytes. The discriminating evidence — kept over-use
loops, degenerate emission windows — is post-decode, not in the record
bytes. Any byte heuristic that catches Guntle's interleave (e.g.
small-even-byte periodicity) is a NEW unmeasured classifier, out of
scope under the no-behavior-change mandate and unvalidatable without
the Orquestador's 1,413-file re-run.

## Verdict

NEGATIVE per the acceptance condition. The half-read-gated wider tie
(a) loses Guntle/M3x16/LedStrips_5V (measured counterfactuals) and
(b) changes nothing on the votes its signature marks (OOB slot / #66
gate decide first). The restored 003 stays as committed behavior; this
branch ships probes + evidence only. Reopening is warranted only by NEW
evidence — e.g. a corpus file whose clean non-exact tie resolves to a
wrong-geometry wider reading (none exists in the micro-batch: all 12
files PASS at `647f324`, figures matching the W7-B sweep).

## Provenance

- Probe scripts: `scripts/triage/w18_l2_gate.py` (L2 gate mirror of
  `_measure_l2`), `scripts/triage/w18_tie_signature_probe.py`
  (`--selftest` pinned).
- Tie dumps: `docs/evidence/data/w18-tie-dumps/*.jsonl` (5 files,
  54 tie records + 5 status lines; the dumps were regenerated once —
  the probe's first cut keyed the repeats slot as a constant, inflating
  the pair count to 366; the generator fix is committed and the
  committed dumps are its output).
- Counts: `docs/evidence/data/marathon-w18-halfread-gate-claims.csv`.
- Counterfactuals (003-reverted state): measured this session on
  8851273 with `w18_l2_gate.py`; Smooth from
  `2026-11-22-w7b-degenerate-manifold-fixes.md` (committed).
- Base figures: micro-batch 12/12 PASS at 647f324 (the four big files:
  frente 66,444 tri/2,066 bnd; Motor 165,354/47,388; LedStrips_Smooth
  229,732/38,888; head_ia 231 MB 649,136/5,482 — the last two matching
  the W7-B post-003 sweep exactly), table in
  [marathon/w18-progress.md](marathon/w18-progress.md).
- Gate on the pushed tree: ruff clean, claims-CSV checker clean,
  pytest 1,003 passed / 21 skipped, `cargo build` native + wasm32 OK,
  `cargo test` 252 lib + 6 integration OK. Two PRE-EXISTING main-level
  failures, verified identical on the pristine 373b234 checkout and
  outside W18's territory (face_gp.rs, display.rs — W16/W4):
  `cargo fmt --check` (face_gp.rs test block) and
  `cargo clippy -D warnings` (9 collapsible_if in display.rs). The
  wasm-pack gate section was skipped per the W18 brief's no-wasm-pack
  rule; the committed pkg copies were checked read-only (in sync).
