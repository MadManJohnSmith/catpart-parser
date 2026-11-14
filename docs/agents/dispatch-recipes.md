# Subagent dispatch recipes (analysis tickets)

Conventions for dispatching implementation and analysis tickets to
subagents (chief-of-staff sessions). Adopted 2026-11-08, partly from the
[REAP prompt pack](https://github.com/JoasASantos/REA-Prompts)
(skills reap-03/15/16 + prompt-writing tips).

## Bounded dispatch discipline

Every dispatch states: one concrete deliverable, an explicit STOP
condition, and "partial factual results with the ambiguity named are an
acceptable outcome". Open-ended "decode X" prompts caused a reasoning
loop (ticket #19, step a); the fix was splitting B3 into (a) extract
facts, (b) validate claims + harness, (c) write docs — each with its own
commit boundary. Analysis tickets follow that split by default.

## Template: file-format structure decode (reap-03, adapted)

For tickets that decode a structure (B-branch style):

    Decode <STRUCTURE> from observed corpus files only. Describe it field
    by field with byte ranges and endianness, validate the model
    corpus-wide (or on a version-scoped sample, >= 3 files per marked
    line), and land a committed decoder script under scripts/triage/ +
    a dated evidence note + per-claim rates in docs/evidence/data/.
    Every claim: fact / inference / unknown, with the rate and version
    scope. Below-bar claims are labeled candidate. Nothing parses code;
    static reads only.

## Template: version differential (reap-15, adapted)

For cross-version tickets (B5-style):

    Compare <V_A> and <V_B> corpus samples (>= N files each, distinct
    digests, multiple repos). For every structural difference, classify
    it: writer-version change vs content variation, with byte evidence
    and per-version rates. Map each difference to a docs/format/ claim
    or an open question. Deliverable: differential note + claims CSV.

## Template: resume / next-step selection (reap-16, adapted)

For grind and assembly tickets (C4/B6-style):

    Review docs/evidence/ notes and their open questions. List what is
    NOT demonstrated yet, prioritize the next analyses by how much they
    reduce uncertainty per unit of work, and execute the top item to a
    committed deliverable. Update the evidence register afterwards.

## REA MCP availability

REA (rea.tools) MCP tools are registered in ZCode sessions on this host
(the earlier handoff predated that). Measured 2026-11-08 on corpus
files:

- **Works**: offline artifact inspections — e.g. `inspect_byte_entropy`
  (Shannon entropy, high/low runs, per-block) — producing canonical
  evidence records (evidence_id + artifact sha256) that can be cited
  like any other measurement.
- **Does not work**: binary-analysis sessions (`open_binary` and its
  dependents: byte-signature search, decompilation, call graphs).
  REA's providers target ELF/PE/Mach-O code images and reject CATIA
  containers as an unsupported format.
- **Consequence**: byte-level format analysis stays in the committed
  Python scripts (deterministic, reproducible, corpus-wide). Use REA
  inspections as supplementary evidence when a tool matches the need;
  record the evidence_id in the note.

## Hard rules carried into every dispatch

- RE only from observed files; no proprietary code, no leaked specs, no
  CATIA installers. Every claim traces to byte evidence with a
  reproduction command.
- Corpus binaries never committed; evidence notes + CSVs are.
- Before every push, run `scripts/check.sh` (ruff + pytest -q plus the
  port's cargo steps — build native + wasm32, fmt, clippy -D warnings,
  test — the local copy of ci.yml; ticket #38, retro 2026-11-11; the
  cargo steps added at V0/#51, 2026-11-13, with the Rust toolchain a
  required dev dependency from then on). CI remains the
  authority; the gate keeps a red run from reaching main post-hoc.
- Decisions are final (ADRs + issue map #1). If evidence contradicts a
  documented assumption, record the correction (precedent: B1's
  +12 -> +18) instead of massaging.
- A new evidence-data CSV family lands in the same stage as its
  mechanical hygiene check (2026-11-13 retro, candidate 1: the
  unquoted-comma debt spanned stage-5-era CSVs — ~52 rows, 8 files —
  while `scripts/triage/check_format_claims.py` already carried the
  identical check pattern for `docs/format/`; the 30-row semantic
  repair + delegate cycle was the interest on it). `*claims*.csv` is
  auto-covered by `scripts/triage/check_claims_csv_quoting.py` via the
  gate; a data directory outside that glob gets its own width/format
  checker at introduction, not at phase close.
- Every figure in a note's prose is derivable from a committed
  artifact (a CSV row or a committed `*-anchor.csv`) at dispatch time,
  before the review dispatch (2026-11-13 retro, candidate 3: ~10 of
  the stage 10-14 review corrections were prose-vs-data drift rooted
  in ad-hoc session-dir anchors — stage-13 F1's five byte-position
  errors, stage-14 F4-F6). This sharpens the #37 CSV-composability
  convention from a merge-time hand-check into a dispatch-time
  obligation; the probes' `--sha16`/`--include-sha16` anchor modes
  produce the committed anchor CSVs.
- A classifier or census mechanism whose labels feed a ceiling table
  or an owner decision states, per class, one explicit line — what
  this detector does NOT discriminate (ordering, sign, scope) — and
  carries a committed synthetic negative fixture for its discriminating
  edge, as a `--selftest` mode or pinned rows (2026-11-13 retro,
  candidate 4: stage-14 F1's ordered-triples-only detector measured
  family 1 instead of 8 and reopened a Phase-B gate; stage-12 F1's
  ceiling sum omitted its own cap-raisers, 144 vs 181 — owner-facing
  arithmetic. Declared-before-observed is self-referential and
  structurally cannot catch an unstated detector assumption; the
  independent-method review catches it, at review cost).
- A stage's own deliverable lands as
  `docs/evidence/<date>-stage<N>-<topic>.md`; dated corrections to
  other stages' notes stay as dated sections inside the owning note
  (2026-11-13 retro, candidate 7: stage 11's deliverable is an
  addendum inside the stage-8-era mixedwrite-reps note, resolvable
  only by grep). Extended 2026-11-14 (Phase 5 retro): a V-ticket's
  decision record gets the same treatment — ticket comments carry
  evidence pointers, but the curated decisions live in the owning
  note file (V3's record was ticket-resident and cost a grep to
  reconstruct).
- A generated artifact (a harness-written note/CSV) carrying a
  defect is fixed by fixing the GENERATOR and regenerating the
  artifact — a hand-edit or dated section inside a generated file is
  overwritten by the next run (Phase 5 retro, candidate 1: the V6
  close note kept its stale sentence after the generator-only fixup
  `b7ec659`; the record was regenerated by re-running the
  deterministic harness). When re-running, pass the record's exact
  output paths explicitly — the harness's default paths follow the
  SLICE/kind naming, not the ticket's record names (the coordinator
  clobbered the v1-named CSV with both-slice output on 2026-11-14
  before restoring it from git).
- A note-derived verdict/figure that a child flags as wrong is
  committed unedited under the stop and fixed at the coordinator
  layer (V5-B precedent) — and close comments cite COMMITTED
  figures: the #52 close comment's 76.0 s cites the uncommitted
  first run; the committed corrected record says 122.6 s. The rule
  (Phase 5 retro): figures in immutable comments must trace to
  committed artifacts; when they cannot, the handoff records the
  correction of record.
- A spec's NEGATIVE claims ("no X in the decode path") get a
  mechanical sweep at review: grep the operation, not just the word
  — the `**0.5` at composite.py:532 survived a `sqrt`-literal grep
  and a line-by-line coordinator review (V3, corrected in the spec's
  §11). Enumerate the claim's terms, sweep each mechanically, and
  record the sweep's file:line resolution in the register.
- At most 2 concurrent subagents on this host (owner update 2026-11-09;
  supersedes the earlier 1-at-a-time limit). Background dispatches
  preferred so the coordinator loop stays responsive. The second slot
  goes to review-vs-next-implementation overlap (next implementer bases
  on the reviewed ticket's branch, accepting a possible rebase) and to
  non-critical-path work; ticket-graph dependencies still gate what can
  run in parallel. Observed 2026-11-09: the provider's user-turn
  concurrency limit (error 3008) can fail a child's turn when child
  turns overlap a long coordinator turn — keep coordinator turns short
  while children run, and re-dispatch a failed child as a new delegate.
  Observed 2026-11-10: two overlapping CHILD turns trip 3008 even with
  short coordinator turns (the G5 review died twice this way), and the
  provider can also fail a turn with error 1005 (quota limit, distinct
  from 3008). Until the owner updates the concurrency policy, child
  turns run SERIALIZED: at most one child in flight; the second slot
  hosts only coordinator-executed work. A failed child's worktree is
  usually clean — check before re-dispatching, and re-dispatch as a NEW
  delegate_task (both 3008 and 1005 recovered on retry).
  Observed 2026-11-11: the owner re-authorized 2-parallel (session
  retro), and 3008 recurred the SAME day with two overlapping child
  turns (stage 4b died while stage 4a ran) — the provider's effective
  limit is one child turn in flight regardless of policy. Operating
  rule: dispatch two only when their turns will not overlap (e.g. a
  short gate pass against a long analysis); on 3008, serialize until
  the in-flight child completes, then re-dispatch fresh. The provider
  also handed the session off between backends mid-day (one fallback
  died on an out-of-balance account) — recover thread state via
  `t3_thread_read`, not memory.
- Adopting an external changeset (precedent: ticket #35, 2026-11-10):
  state the expected per-store/per-part delta BEFORE running the corpus
  A/B, and treat any unexplained delta as a stop-and-re-root-cause gate.
  A plausible root-cause story (the external report's C11 mechanism)
  was falsified by the A/B: 1/15 expected recoveries plus 1,517
  u16be->u8 demotions at corpus scale. External patches are never
  executed — they are diffed and read only; corpus runs use committed
  code. Verdicts, expected deltas and re-scopes live in the ticket
  (#35 comment 2026-11-10).

## Provider-failure playbook (2026-11-13 retro, candidate 2)

Practiced through the three 3008 failures of 2026-11-13 (stage-15
impl, stage-15 review, CSV repair — all recovered on re-dispatch);
written here because it lived only in a handoff marked SUPERSEDED and
was re-derived by hand each time:

1. On a failed child, verify terminal state FIRST (`task_status` or
   the child thread's activity): a "failed" turn may have committed
   its deliverable before dying.
2. Clean the residual before re-dispatching. The failure signature:
   an empty worktree plus a zero-unique-commit branch named for the
   dispatch (stage-15 review and the CSV repair left exactly this;
   stage-15 impl left none). Remove the worktree, delete the branch.
   SUBSTANTIAL UNCOMMITTED RESIDUAL branch (V3 whale, 2026-11-14):
   if the dead child left uncommitted work (~2.5k lines), snapshot
   the diff to ~/.local/state/<project>/<ticket>-residual.patch,
   clean as usual, and re-dispatch fresh with the patch attached as
   REFERENCE material — epistemically labeled: trust nothing, never
   apply blindly, every stage still passes its own harness re-run.
   What makes this safe is the regime (per-stage harness re-runs +
   the independent verifier), not the label: under seam-level
   Fidelity the partial's provenance cannot affect acceptance. The
   re-dispatch summary must state how much of the patch was reused;
   the verifier measures sequence alignment as an honesty check (V3:
   35.9% — re-derivation, not application).
3. A fresh review worktree's branch arrives parked at main's head
   (harness behavior, rediscovered by hand in all five stage-11-15
   review dispatches): reset it to the child's head before reviewing.
4. Never dispatch delegates or arm scheduled tasks from a
   notification-woken run (`parent_not_active` — it cost 4 wasted
   orchestrator calls to learn, handoff-2026-11-11 cont. 10-12):
   dispatch from a user-woken turn.
5. Re-dispatch as a NEW `delegate_task` with the same brief verbatim;
   3008 and 1005 recovered this way every observed time. Never resume
   or continue the failed delegate.

## Owner-decision protocol (2026-11-13 retro, candidate 5)

The pattern that worked five times across the grind (2026-11-12 →
2026-11-13), now written down — it governs the V5 margin declaration
and every later owner-facing decision:

1. Present decisions only on post-review, verified arithmetic — no
   unverified figure reaches the owner (the cont. 16 and cont. 20
   asks both followed review corrections).
2. Enumerate the options with one honest recommendation, including
   what it costs, and state the not-recommended option honestly —
   the owner may rationally pick it (cont. 17 did, recorded as
   rational on the stage-7→9 precedent).
3. Anchor risky continuations on measured precedent, not hope.
4. Record the decision dated, with declined alternatives, rationale,
   and sub-decisions to the digit (cont. 23's shape).
5. Pre-authorize recurring decision classes as standing rules so only
   parameters remain to decide (the ROADMAP bar-revision rule:
   written 2026-11-10, applied 2026-11-13 at margin 0 with zero new
   negotiation).
6. Overturning a standing conservative decision is a STOP-and-report,
   never a unilateral call (stage-14 §6 → cont. 23's dated
   authorization is what unblocked stage 15).

## Pre-commitment gating (Phase 5 retro, candidate 5)

When a run's data could contaminate a pre-commitment (a declared
margin, a projection, a bar), gate the run STRUCTURALLY, not by
instruction: the V5 harness requires an explicit `--margin`, offers
no subset/sample flag (no subset rate is even expressible), and the
two-phase split (build the harness → owner declares → run) kept any
in-browser measurement from existing at declaration time. The
declaration records dated, citing native evidence only. APPLICABILITY:
use the pattern only when contamination is possible — it adds a phase
boundary and a stop; do not make it default overhead for runs whose
results nothing pre-commits to.
