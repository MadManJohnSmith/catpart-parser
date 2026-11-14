# Phase 5 V6 (ticket #44): the acceptance + publication close

**Status: implemented on the V6 worktree branch, 2026-11-14; coordinator
review pending.** Design authority: `docs/specs/phase5-viewer-spec.md`
— this note cites §3.1/§3.2 (the Fidelity-1 definition), §3.4 (the
in-browser margin), §4 (the harness and the ≤ 2 h budget), §5 (the
publication shape), §6 V6 (the ticket scope), §11 (the margin
declaration, 2026-11-14). The ticket is #44; the acceptance checklist
is spec E #39's, verbatim, and this note carries it item by item.
Nothing is merged or pushed to `main`: commits live on the worktree
branch only (the gh-pages publication below is the one designed
exception — a generated branch, ADR-0003).

## The acceptance checklist (spec E #39, verbatim criteria)

### 1. Fidelity-1 on the corpus (0 mismatches vs the Python reference) — spec §3.1/§3.2 populations and diff definition

**Met: 3,266/3,266 rows match — 0 mismatches, 0 harness-errors, exit
0 — in ONE run, ONE CSV, both slices, full populations (no
`--sample`).**

- Command (repo root, corpus machine):
  `.venv/bin/python scripts/fidelity_run.py --slice both --csv
  docs/evidence/data/v6-fidelity-full-corpus-claims.csv --note
  docs/evidence/2026-11-14-v6-fidelity-full-corpus.md`
  (the harness rebuilt the port binary first —
  `cargo build --release --locked`, §4).
- Mechanical note (committed AS PRODUCED):
  [docs/evidence/2026-11-14-v6-fidelity-full-corpus.md](2026-11-14-v6-fidelity-full-corpus.md);
  per-file CSV: `docs/evidence/data/v6-fidelity-full-corpus-claims.csv`
  (3,266 rows; column 0 = row key).
- **L1-JSON slice (§3.1: ALL manifest rows — parts, products, junk):
  1,824/1,824 match** (CSV rows keyed by sha256; splits: dev 1,751 +
  held-out 73). 1,823 clean pairs (exit 0 both sides, parsed-document
  equality) + **1 junk pair failing identically on both sides** (exit 1
  both sides, class `crash` — the L1 single-class vocabulary — the
  port reproduces the reference's fail-closed behavior on garbage).
- **L2-export slice (§3.1: ALL kind=part rows): 1,442/1,442 match**
  (CSV rows keyed `sha256|export`; splits: dev 1,381 + held-out 61):
  **1,173 exports with summary parsed-document equality AND
  byte-identical PLYs** (`ply_equal=true` on every compared export) +
  **269 double refusals with `error_class` string equality, pairwise**:
  `undecoded-variant` 144 + `missing-geometry-store` 125 = 269 —
  exactly the Phase 4 close's classified failure table (the port
  reproduces the classified error seam, §3.2's fourth surface).
- Every figure CSV-composable (#37): outcomes `{'match': 3266}`;
  population by split `{'dev': 3132, 'held-out': 134}`; by kind
  `{'part': 2884, 'product': 382}`; by magic_ok `{'no': 10, 'yes':
  3256}` (6 L1 junk rows + their 4 kind=part twins in the L2 slice);
  `first_divergence` empty on all 3,266 rows; zero
  excluded-composite-path rows (the composite path is ported, stage 3
  — composite-path exports compare fully).
- **Wall-clock: 255.9 s (measured, both subprocess passes included)**
  against §4's ≤ 2 h full-run budget (stated as a design target):
  WITHIN, 4.3 min. Subprocess totals: python 232.7 s, port 22.3 s
  (10.4× — §4's basis "the Python pass dominates; Rust native is
  expected 10-100× faster" holds). The mechanical note's own budget
  line is the per-ticket ≤ 15 min sample budget (labeled as such in
  the harness); the V6-measured budget is the full-run one recorded
  here.
- Reference basis (recorded): the Python seam driven is the corpus
  machine's editable install — the main checkout's `src/catpart` —
  **tree-identical to this branch's `src/catpart`** (base `7b95cd1`;
  `main`'s head `2a9fde0` differs only in
  `docs/agents/handoff-2026-11-13.md`); the port binary is built from
  this worktree's `port/` by the harness itself. Both seams are the
  accepted V1–V5 code; no seam was rebuilt for V6 (the hard stop).

### 2. In-browser sanity = published L2 scalar ± the declared margin — spec §3.4 (declared at V5's opening, before the run)

**Met — V5's run (#52), closed 2026-11-14; cited, NOT re-run (the V6
hard stop: V6 adds no browser work).**

- Margin **0**, owner-declared PRE-RUN (spec §11 register,
  2026-11-14; declared-before-observed discipline, §3.4).
- The full L2 population run (`scripts/reproduction_run.py --margin
  0`, all 1,442 kind=part rows, manifest order): **1,442/1,442
  per-file match; dev 1,033/1,381 = 0.7480086893555394 and held-out
  56/61 = 0.9180327868852459 — EQUAL to the published scalars
  digit-for-digit, |delta| = 0 ≤ margin 0 → WITHIN both splits; 0
  harness-errors, 0 exclusions to name; 0 external requests**.
  Evidence:
  [docs/evidence/2026-11-14-v5-reproduction-l2.md](2026-11-14-v5-reproduction-l2.md)
  + `docs/evidence/data/v5-reproduction-l2-claims.csv` (1,442 rows,
  all match), ticket #52 (closed), the published scalars from the
  accepted row `20261113T231506Z-c2ab64` in `fitness/history.jsonl`.

### 3. Mesh, metadata panel and curve overlay operational (in the browser)

**Met — V4's scripted Playwright acceptance (#43), 2026-11-14; cited,
not re-run.** Verbatim from
[docs/evidence/2026-11-14-v4-wasm-boundary-viewer.md](2026-11-14-v4-wasm-boundary-viewer.md)
(`scripts/viewer_acceptance.py`, headless Chromium, read-only static
serve of `site/`):

    viewer acceptance — PASS
      - canonical fixture: loaded, gate pass, 8 vertices / 12 triangles, finite bbox [0, 0, 0]..[20, 100, 60]
      - metadata panel: schema v1 fields present (version, kind, 3 containers)
      - curve overlay: 1 decoded loop(s), toggle off->on->off (aria-pressed tracked)
      - corrupted fixture: classified error shown (malformed-pool-vertex, 99-char detail), page alive
      - no server component: 10 requests, all on the serving origin; zero uncaught page errors

Mesh render + orbit/zoom + wireframe/solid, the schema-v1 metadata
panel, the curve overlay toggle, and the in-browser §3.4 gate all
exercised in a real browser; the shipped artifact is the committed
`port/pkg/` wasm (the same crate the Fidelity harness proves).

### 4. Every failure classified, never hidden

**Met — at the seam and in the viewer.**

- **At the seam (this run)**: every failure row carries its class on
  BOTH sides and they agree pairwise — the L1 junk pair (`crash`
  both), the 269 L2 double refusals (`undecoded-variant` 144,
  `missing-geometry-store` 125, pairwise equal), 0 unclassified rows,
  0 harness-error rows. §3.2's rule held mechanically: harness-level
  failures would have been recorded as their own outcome and never
  counted as matches — there were none to record.
- **In the viewer (V4, cited)**: a failing decode shows
  `{ error_class, detail }` in a dedicated panel, the blank canvas is
  hidden, the gate panel reads "no export — the decode failed", and
  the drop zone stays usable — never a blank screen (the V4 Playwright
  block's "classified error shown … page alive").
- **In the reproduction (V5, cited)**: the run's harness-error class
  is reported per-file and excluded-but-reported per §3.4 — zero hit
  (1,442/1,442 compared).

### 5. Close artifacts landed (note + CSVs + status blocks)

**Met — this commit.** The mechanical run note +
`v6-fidelity-full-corpus-claims.csv` (this note's §1), this close note
(the full checklist), and the status blocks: `docs/ROADMAP.md` Phase 5
(CLOSED), `README.md` + `README.es.md` (the Phase 5 completion lines
and the V6 tracker row).

### 6. No-regret untouched (the phase changes no fitness row — the Python reference is not modified)

**Met — verified.** `git diff 7b95cd1` on this branch touches ONLY:
`docs/evidence/2026-11-14-v6-fidelity-full-corpus.md`,
`docs/evidence/data/v6-fidelity-full-corpus-claims.csv`,
`docs/evidence/2026-11-14-v6-phase5-close.md` (this note),
`docs/ROADMAP.md`, `README.md`, `README.es.md`. Zero changes under
`src/catpart/`, `port/`, `fitness/`, `tests/`, `scripts/` — the
Python reference is byte-untouched, `fitness/history.jsonl` is
append-only-unchanged (the last accepted row remains
`20261113T231506Z-c2ab64`), and the published scalars stand. The V6
run consumed the reference; it did not move it.

## Publication (§5: the unchanged flow, §6 V6)

`python3 -I scripts/publish_fitness.py` run from this worktree root on
the corpus machine (stdlib-only, idempotent — never CI, ADR-0003):

- **gh-pages commit: `e8c0ebc87baaa8459b4c64fcb4b81bccd765b63d`**
  (tree `07ae42333b6b0265ebeb9ddf1e7987194b2851d5`), pushed to
  `origin` (exit 0). Message: "publish fitness artifacts (latest
  accepted run 20261113T231506Z-c2ab64)"; author/committer/date are
  the script's fixed identity (date = the last accepted run's
  timestamp).
- **The published tree carries the viewer** (repo path `site/viewer/`
  → gh-pages path `viewer/`): 11 files — `viewer.html`, `viewer.js`,
  `gate.js`, `orbit.js`, `viewer.css`, **`pkg/port.js` +
  `pkg/port_bg.wasm` (305,474 B)**, `pkg/*.d.ts`, `pkg/package.json`,
  **`three.module.min.js` (691,648 B, the vendored pinned r0.170)** —
  verified **byte-identical** to the committed `site/viewer/` blobs
  (git object ids equal, checked per file). The site nav carries the
  Viewer entry. `fitness-latest.json` / `fitness-history.json` /
  `.nojekyll` / `format/` (8 docs) ride along as before — 23 site
  files total, up from 12: the viewer is what the delta IS.
- The publish flow itself is untouched (the V6 hard stop; §5's
  "publication mechanism needs zero changes" verified by using it
  unchanged). Idempotence: the tree is a pure function of committed
  content — after the coordinator merges, re-running the script from
  `main` renders the same tree and no-ops ("already up to date").
- The prior gh-pages head was `7a8cb9d0` (2026-11-13, pre-viewer);
  the publication commit force-updates the generated branch, the
  designed behavior for a tree that "holds only generated files".

## The gate, end-to-end (scripts/check.sh — the local copy of ci.yml)

Result (2026-11-14, this branch, from the worktree's own `.venv` — no
shadow environment): ruff "All checks passed!"; pytest **374 passed,
8 skipped** in 23.3 s (the fixture-mode Fidelity harness re-ran green
inside it — 334/334 fixture rows — and the new
`v6-fidelity-full-corpus-claims.csv` passed the `*claims*.csv`
mechanical hygiene check it is auto-covered by); cargo build native +
wasm32 ✓; cargo fmt/clippy/test ✓; wasm-pack build + wasm-bindgen
Node tests **6 passed, 0 failed**; pkg sync check ✓.

## Flag for the coordinator (one, named; nothing edited post-run)

The harness's `--slice both` slice_note prose is stale at stage 3:
the committed mechanical note's Slice line says "composite-path
exports excluded, ticket #41 hard stop" — written in the V2 era and
no longer true of the comparison, which at `COMPOSITE_EXPORT_STAGE =
3` compares composite-path exports fully (a port refusal against a
twin export is a mismatch). The comparison itself is correct — zero
rows were excluded (outcomes: all `match`) — only the note's prose
sentence is stale. Per the V5 phase-B precedent the mechanical note is
committed AS PRODUCED (never edited post-run); the stale sentence
lives in `run_corpus_mode`'s `--slice both` branch
(`scripts/fidelity_run.py`) and is a one-line harness fixup for the
coordinator to land under review — the V6 hard stop ("no harness
changes") kept it out of this branch.

## Known gaps / partial results

- None blocking. The flag above is the single named item, plus one
  clarification recorded in §1: the mechanical note's budget line is
  the per-ticket sample budget (the harness has one budget line); the
  full-run ≤ 2 h budget is met at 255.9 s and recorded here.
- The live GitHub Pages serving is verified, not just pushed: after
  the force-push the Pages build served
  `https://madmanjohnsmith.github.io/catpart-parser/viewer/viewer.html`
  (HTTP 200) and `viewer/pkg/port.js` (the wasm-bindgen glue, served
  byte-real — probed 2026-11-14). The coordinator's verification is
  the natural double-check.
