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
- One subagent at a time on this host (concurrency limit); background
  dispatches preferred so the coordinator loop stays responsive.
