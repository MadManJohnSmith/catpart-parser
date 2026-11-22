# Phase 7 close-out — SUPERSEDED (retirement record, not a pre-close draft)

**Dated** 2026-11-18 (the dispatch's base) · **Re-verified** 2026-11-21 at main @ `e27069d`
· **Status** **VOID AS A PRE-CLOSE DRAFT** — the close it was written to prepare shipped on
2026-11-18, before this rewrite could be applied.

The dispatch asked for a rewrite of the 554-line draft that adopted 21/23, and named
`main @ 91c9e4b` as the base. Between that base and this rewrite the phase closed: the L3
row was appended, `v1.0` shipped, the graph/STEP branch merged, both tickets closed, and
this path was retired by `c9f7c64` — *"docs(agents): retire the pre-adjudication Phase 7
close draft … It encodes 21/23 and 'candidate 2'; the adjudicated close is 23/23 with zero
candidates, recorded in docs/evidence/2026-11-18-phase7-close.md. Keeping the stale draft
invites reusing a wrong figure."*

Re-emitting paste-ready "insert this block" text now would assert a tree state that no
longer exists: `ROADMAP.md` already carries the block, the READMEs already say closed,
`docs/evidence/2026-11-18-phase7-close.md` is committed, and `fitness/history.jsonl` holds
the L3 row. So this file records the supersession with the artifacts that fulfilled each
deliverable, instead of re-drafting them.

---

## 1. What the dispatch asked for, and where it actually landed

| § | Requested deliverable | Shipped artifact | Commit |
| :-- | :--- | :--- | :--- |
| 1 | ROADMAP Phase 7 status block, dated 2026-11-18, 23-row verdict, documented-opens with ceilings, 8-cell disclosure, `[[L3_RUN_ID]]`/`[[L3_RATE]]` filled | [`docs/ROADMAP.md:275-295`](../ROADMAP.md); terminal-state item 4 at `:306` | `444af18`, `8aff02d` |
| 2 | README / README.es L3 line replacement for "in progress" | `README.md:48,111,126`; `README.es.md:49,113,128` | `6a79fbd`, `f6e0dd5` |
| 3 | Dated closure evidence note with every number tied to a committed row | [`docs/evidence/2026-11-18-phase7-close.md`](../evidence/2026-11-18-phase7-close.md) (136 lines, §1–§8) | `8aff02d` |
| 4 | Honesty paragraph: candidate not resolved, documented-open closed with a ceiling, corpus rate never gates, 8 cells unprovenanced | close note §1, §3, §5; ROADMAP `:275-295` | `444af18`, `8aff02d` |
| 5 | Sequence: bump → gate → run → commit row+report → docs → push → close #58 then #47 | executed 2026-11-18: row `030b654`, release `a8048c1`, issues closed 17:34:59Z / 17:35:14Z | `030b654`, `a8048c1` |
| 6 | What the draft does not assert | close note §8 (exact solids 0/1,442; no NURBS payload; no product structure in STEP) | `8aff02d` |

## 2. Verified state at `e27069d` (not at `91c9e4b`)

| Fact | Evidence |
| :--- | :--- |
| Phase 7 is **CLOSED at 23/23**: 14 decoded, 3 documented negatives, 6 documented-opens with published ceilings, 0 candidates, 0 pending-merge | `BR6L3-03..07`; scorer summary re-run at `e27069d`: `23/23 resolved (1.0000)` |
| The L3 row is landed, not pending | `fitness/history.jsonl:15` — run `20261118T171127Z-0882ce`, `tool_version 1.0.0`, `accepted: true`, reason `L3 recorded with L1/L2 intact`; close note `:23-27` |
| `tool_version` was bumped before the run | `pyproject.toml:7` = `1.0.0`; row 15 records `1.0.0` |
| L1/L2 at the close row | L1 1,745/1,751 Dev + 73/73 held-out; L2 1,033/1,381 Dev + 56/61 held-out (close note `:24-25`) |
| The corpus rate is reported and never gates | 21,659/33,166 = 0.6530; `corpus_context.gating: false` (`BR6L3-16`/`BR6L3-17`) |
| Both tickets are CLOSED | #58 at `2026-11-18T17:34:59Z`, #47 at `2026-11-18T17:35:14Z` |
| Graph/STEP **is** on main and in the close | `src/catpart/brep/graph.py`, `step_export.py`; `docs/evidence/data/br6-graph-claims.csv`; close note §4 |
| History is 29 rows today, not 14 | `wc -l fitness/history.jsonl` = 29; post-`v1.0` L2 work continued (last row `20261121T071114Z-e4a04e`, L2 Dev 1,137/1,381 = 82.33%, held-out 57/61) |

## 3. Where the dispatch's premises diverged from how the close actually landed

1. **"Graph/STEP rows only after that branch merges."** It did merge, before the close:
   `1c8f16c` (2026-11-18 11:09), 6 minutes ahead of the L3 row (`030b654`, 11:11). The
   shipped close therefore carries graph/STEP results (close note §4: 0/76 closed shells
   satisfy the B-rep pairing law, `BR6G-05b`; facet mode 53/1,442 parts, `BR6G-07a`; exact
   mode 0/1,442). The one claim that survives unchanged is the **exact-solid** one: 0 of
   1,442 parts export an exact solid, and the STEP `FILE_DESCRIPTION` labels the subset.
2. **"14 rows → 15."** True on the close day; stale today. The history is at 29 rows
   because post-release L2 work kept appending. Any sentence of the form "L1/L2 unchanged"
   is true of row 15 only and must name that row.
3. **"[[L3_RUN_ID]] / [[L3_RATE]] are the run's own values."** They are now known and
   committed: `20261118T171127Z-0882ce` / `1.0`. There is no open placeholder left in the
   tree.
4. **"Close #58 then #47."** Done, in that order, 15 seconds apart.

## 4. If a pre-close draft is still wanted

It must be produced against the old base, not against `main`:

```bash
git worktree add /tmp/opencode/phase7-preclose 91c9e4b
```

Even there, the honest content is not a 500-line paste-ready block: at `91c9e4b` the
prose would have to adopt **23/23 with zero candidates** (the scorer and claims already
said so), while the L3 row, the READMEs, the ROADMAP block and the graph/STEP merge were
still pending. The 21/23 premise belongs to `c06664e` and earlier and is now history,
recorded as superseded in `br6-close-checklist.md:30`.

## 5. What this record does not assert

- It does not assert 21/23 or `candidate 2` as the current state, and it does not reopen
  #47 or #58.
- It does not assert that graph/STEP is absent or that exact solids ship: graph/STEP is on
  `main`; exact STEP export is 0/1,442 parts.
- It does not assert that the close is still to be written, and it does not re-derive any
  number: every figure above is quoted from the committed close note, the committed row or
  the committed claims CSV, or from a scorer run at `e27069d`.
