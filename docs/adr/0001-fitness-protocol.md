# ADR-0001: Fitness protocol — scalar per level, author-grouped split, no-regret

The project's core loop is AI-agent sessions hill-climbing on an executable
fitness signal. We decided: one headline scalar per capability level
(L1 clean-parse rate, L2 geometry-sanity rate, L3 construct coverage);
a corpus split into Dev (~81%) and Held-out (~19%) grouped by
repo/author — never by file, because near-duplicate parts and repeated
standard components would leak across a per-file split; increments
accepted only under the no-regret rule (Dev rises AND Held-out does not
fall); and the full history, including rejected attempts, committed to the
repo (`fitness/history.jsonl` plus a report per run), since corpus binaries
cannot be committed. L0 carries no fitness metric — it is governed by the
Phase 0 acceptance criteria only.

## Considered Options

- Scorecard with weighted components: rejected — weights are extra
  arbitrary decisions that bias what sessions optimize.
- No split: rejected — an agent could overfit to individual corpus files
  with nothing to expose it.
- Manual acceptance of increments: rejected — a human bottleneck defeats
  the point of unattended grinding.

## Consequences

- Phase 3 acceptance (≥80% clean-parse) is measured on Dev and must also
  hold under no-regret on Held-out.
- Changing the corpus invalidates history comparison; every history row
  records a corpus digest so this is detectable.
- The fitness runner is fixed Python, consuming the parser's JSON output
  through a documented interface — parser language decisions cannot break
  the fitness system.
