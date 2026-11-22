# W18 — half-read-gated wider tie (wave 4, continuous 7/7)

**Branch**: `marathon/w18-halfread-wider`. **Host**: Gallyfrey.
**Anti-OOM**: sequential heavy files, `free -m` checked (5.1-7.1 GB
avail), pytest 1 process.

## Objective evolution

1. Original: recover the W7-B 003 fixes through a half-read-gated
   wider tie. Superseded mid-flight by the Orquestador: W3 (E5) was the
   regression source, 003 is restored on main (`88b1fa6`), so the gate
   became an optional robustness measure with a strict acceptance
   condition (preserve the 4 fixes + 0 pass→fail, else document the
   negative and stop without touching behavior).
2. Independent finding recorded before the update: the
   First_Back_Shell/backshell_M flip is **W3's merge 528a0a0**, bisected
   per-commit (da16f56 and d8554e0 PASS at canonical 2,220/3,320 tri;
   528a0a0 FAIL 8,278/26 and 9,142/34; restored-003 main `647f324` PASS
   again). Matches the Orquestador's verdict.

## Result: NEGATIVE, no runtime change

The W1-signature gate is inert on its activation class (the signature
requires a u16be-re-read OOB, and the OOB slot / #66 post-vote gate
already decide those votes) and loses the 4 fixes (366 measured full
ties across Guntle/M3x16/LedStrips_5V carry **zero** signed narrow
candidates, so the gate resolves them narrow = the measured pre-003
not-manifold failures). Full argument and tables:
[2026-11-22-w18-halfread-gate-negative.md](../2026-11-22-w18-halfread-gate-negative.md).

## Log

- 2026-11-22: branch created from `origin/marathon/w18-halfread-wider`
  (8851273), then rebased to main `647f324` after the W3-revert +
  003-restore landed (the two regression files only PASS on the
  post-revert lineage — the verification is meaningless below it).
- Micro-batch restored: `w7b-micro.tar` (sha256
  `7cd7e547…417724`, verified) from `/tmp/w5-serve/` to
  `~/.local/state/catpart-parser/w18/`; the 2 regression files
  downloaded from B31CAADoc (sha256s match the manifest).
- Baseline at `647f324` (Python engine, `w18_l2_gate.py`): 12/12 PASS —
  Guntle 3,093 tri/1,037 bnd; LedStrips_5V 16,130/4,260; M3x16
  1,702/1,402; First_Back_Shell 2,220/574; backshell_M 3,320/968;
  M4x10 2,426/582; NPart194321 51,826/18,546; head_ia 24 MB 480,662/8,784;
  frente 66,444/2,066; Motor 165,354/47,388; LedStrips_Smooth
  229,732/38,888; head_ia 231 MB 649,136/5,482 (Smooth, head_ia 231 MB
  and frente match the W7-B post-003 sweep figures exactly).
- Counterfactual on 8851273 (003 reverted): Guntle/M3x16/LedStrips_5V
  FAIL not-manifold (2,984/1,096, 1,702/1,403, 15,860/4,331) — the
  gate's narrow resolution for the 0-signed tie set.
- Tie-signature dumps: 80/24/262 full ties, 0 signed; FBS/backshell 0
  full ties (`w18_tie_signature_probe.py`, `--selftest` pinned both
  signature edges).
- Deliverables: 2 probes, 5 tie dumps, 1 claims CSV, this note + the
  negative note. No change to `vote.py`/`vote.rs`/`composite*`.
- Gate on the pushed tree: ruff / claims-CSV / pytest (1,003 passed,
  21 skipped) / cargo build native+wasm32 / cargo test (252+6) all
  green. TWO PRE-EXISTING main-level failures (verified identical on a
  pristine 373b234 checkout, files outside W18's territory — flagging
  for W16/W4 + the Orquestador): `cargo fmt --check` fails in
  face_gp.rs's test block and `cargo clippy -D warnings` fails with 9
  collapsible_if in display.rs. The wasm-pack gate section is skipped
  per the W18 no-wasm-pack rule; committed pkg copies checked in sync
  read-only.
