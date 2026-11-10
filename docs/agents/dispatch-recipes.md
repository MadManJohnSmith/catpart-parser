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
- Decisions are final (ADRs + issue map #1). If evidence contradicts a
  documented assumption, record the correction (precedent: B1's
  +12 -> +18) instead of massaging.
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
- Adopting an external changeset (precedent: ticket #35, 2026-11-10):
  state the expected per-store/per-part delta BEFORE running the corpus
  A/B, and treat any unexplained delta as a stop-and-re-root-cause gate.
  A plausible root-cause story (the external report's C11 mechanism)
  was falsified by the A/B: 1/15 expected recoveries plus 1,517
  u16be->u8 demotions at corpus scale. External patches are never
  executed — they are diffed and read only; corpus runs use committed
  code. Verdicts, expected deltas and re-scopes live in the ticket
  (#35 comment 2026-11-10).
