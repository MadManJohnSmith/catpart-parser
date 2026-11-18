# v1.0 readiness — terminal-state gap list (#49)

**Date** 2026-11-18 · **Repo** local `main` @ `e610bbc` (2 commits ahead of `origin/main` @ `4b6e770`)
· **Scope** read-only audit: every state below comes from a committed artifact (cited `file:line`) or the live
issue tracker (`gh issue view`); nothing in the tree was modified. **Verdict: not ready.** Three of the five
ROADMAP terminal conditions are met (Phases 4, 5, 6); Phase 7 is open, and none of the five closure artifacts
exists yet (`git tag -l` and `git ls-remote --tags origin` are both empty; `gh release list` is empty).

---

## 1. Terminal-state condition matrix

Sources: the ADR (`docs/adr/0004-terminal-state-web-viewer.md`), the ROADMAP closure block
(`docs/ROADMAP.md:249-274`) and the ticket body (`gh issue view 49`). Every row is one condition, not one
document.

| # | Condition | State | Evidence / what remains |
| :-- | :--- | :--- | :--- |
| **M1** | Port proves Fidelity to the Python reference over the corpus (ADR-0004:36-39) | **Met** | One run, both slices, full populations: 3,266/3,266 match, 0 mismatches (`docs/ROADMAP.md:164-171`; note `docs/evidence/2026-11-14-v6-fidelity-full-corpus.md`). CI covers the port on synthetic fixtures only (`ci.yml:83-147`), as ADR-0003 requires. |
| **M2** | Phase 4 (L2) closed — bar met or re-adjusted (ROADMAP:253-255) | **Met** | `docs/ROADMAP.md:96-124`: CLOSED 2026-11-13, accepted row `20261113T231506Z-c2ab64`, Dev 1,033/1,381 = 74.80%, held-out 56/61, bar re-adjusted under the pre-authorized rule (`docs/ROADMAP.md:267-274`). |
| **M3** | Phase 5 (viewer, parts) acceptance met (ROADMAP:256) | **Met** | `docs/ROADMAP.md:158-187`: CLOSED 2026-11-14; viewer live on gh-pages via publication commit `e8c0ebc`. |
| **M4** | Phase 6 (assemblies) acceptance met (ROADMAP:257) | **Met** | `docs/ROADMAP.md:209-225`: CLOSED 2026-11-16; census 382/382 (`:210`), Assembly Bar declared (`:212`), headless acceptance 8/8 (`README.md:47`, `docs/evidence/2026-11-16-p3-v6-acceptance-review.md:46`). |
| **M5** | Phase 7 (B-rep) acceptance met — 100% of the frozen vocabulary resolved, L3 headline under no-regret (ROADMAP:245-247, :258) | **Not met** | No Phase 7 status block exists (`grep 'Status (' docs/ROADMAP.md` → lines 51, 72, 96, 158, 209 only). #47 OPEN, #58 (BR6: graph + STEP + L3 scorer + close) OPEN. L3 is null in every history row (`fitness/history.jsonl:14`). See §2 and blockers B1-B4, B6. |
| **M6** | Tag `v1.0` + release notes (ROADMAP:259) | **Not started** | No tag local or remote; no release. Sequence in §3. |
| **M7** | Final fitness report published on gh-pages (ROADMAP:259-260) | **Stale / incomplete** | gh-pages head `8e69bb7` renders only accepted L1/L2 runs and stops at `20261113T231506Z-c2ab64`; the trend document has no L3 field (`scripts/publish_fitness.py:322-356`) and the site has no L3 series (`site/index.html:102-153`). See B3. |
| **M8** | ROADMAP: every phase closed or negatived, status blocks complete (ROADMAP:260-261) | **Partial** | Phases 2-6 carry `Status (...)` blocks; **Phase 0 and Phase 1 carry none** (`docs/ROADMAP.md:11-25`, `:27-39`) and Phase 7 has none (`:227-247`). Add three status blocks at close, plus a dated closure line inside `## Terminal state and closure`. |
| **M9** | Corpus frozen — the verified 2026-11-07 backup stands; manifest digest in the release notes (ROADMAP:261-262) | **Binding exists, not yet stated** | The manifest is the corpus registry and its SHA-256 is the run's `corpus_digest` (`src/catpart/fitness/runner.py:146-152`); all 14 history rows record the same `dc75f8fe9156dd69…` (`fitness/history.jsonl:1-14`), so the corpus definition has not moved since the first accepted run. Measured today at `e610bbc`: `sha256sum manifests/corpus-manifest.csv` → `dc75f8fe9156dd69b26f2a44ff642c396c7c484d4049a831b88cf6b91d11b164`. A fitness run validates manifest *fields*, never the binaries on disk (`src/catpart/fitness/runner.py:181-206`), so the freeze statement must name the verification method, not imply a fresh digest sweep. |
| **M10** | Remaining issues labelled `post-v1.0` (ROADMAP:262) | **Partial** | #50 already carries the label. Still open after the tag: #1 (`wayfinder:map`, 6/6 sub-issues done), and #47/#58/#49 must close rather than be labelled. Decide #1's disposition (§5, D3). |
| **M11** | README closure note — what shipped, final scalars, where the viewer lives (`gh issue view 49`) | **Not started** | `README.md:48` still reads "L3 — full parametric B-rep … in progress"; `README.md:126` says Spec G "in progress"; `README.es.md:49` and `:113` carry the same stale L3 rows; `site/index.html:89` publishes "L3 (Phase 7) planned · hardest" to gh-pages. |
| **M12** | `v1.0` is a verifiable state — the tag exists with every phase closed or negatived (ADR-0004:43-44) | **Not met** | Consequence of M5-M8. The tag must point at a commit that already contains the closure artifacts (§3 S9). |

**State summary:** M1-M4 satisfied; M5 is the gate; M6-M12 are the closure work that #49 ships.

---

## 2. What Phase 7 still owes (the gate, in order)

| # | Item | Concrete action | Source |
| :-- | :--- | :--- | :--- |
| **P7-1** | B-rep graph + STEP export | Land `src/catpart/brep/graph.py`, `src/catpart/brep/step_export.py`, wire `src/catpart/brep/__init__.py` (today a scaffold that says exactly this), `scripts/triage/decode_brep_graph.py`, `tests/test_brep_graph.py` + `tests/test_brep_step_export.py` | `src/catpart/brep/__init__.py:1-10`; interfaces pinned in `docs/agents/br6-graph-design.md:1-160` |
| **P7-2** | L3 scalar must be *representable* | The committed row schema pins `scalars.L3` to `"type": "null"`; the runner aggregates only L1/L2. Changing both is work inside #58, not a side effect (B2) | `src/catpart/schema/fitness-history-row-v0.json:186-191`; `src/catpart/fitness/runner.py:475-484` |
| **P7-3** | L3 row under no-regret | `catpart-fitness` appends exactly one row; with L1/L2 flat and L3 non-gating the current rule **rejects** the run, so an L3-only increment never becomes the published baseline (B2) | `src/catpart/fitness/history.py:290-304`; `scripts/publish_fitness.py:250-290,311` |
| **P7-4** | Per-construct resolution table | Report per row the construct-level decode count or a documented negative — never the frozen count, which is unprovenanced for 8 rows (B4) | `docs/agents/br6-vocabulary-provenance.md:52,:112-118` |
| **P7-5** | Status blocks | ROADMAP Phase 7 block, README (both languages) L3 rows, `site/index.html:89`, then close #58 and #47 with an evidence pointer | `docs/ROADMAP.md:227-247`; `README.md:48` |

**Measured resolution status of the frozen 23** (verdicts quoted from the committed notes; not re-derived):

| Family | Resolved (decoded or documented negative) | Unresolved |
| :--- | :--- | :--- |
| Topology (7) | 7 — TOP-01 decoded (`docs/evidence/2026-11-17-br5-cgm-nurbs.md:17`), TOP-02 negative (`:18`), TOP-03 decoded (`docs/evidence/2026-11-17-br6-shell.md:15`), TOP-04/TOP-05 (`docs/evidence/2026-11-17-br2-planar-loops.md:14-15`), TOP-06/TOP-07 (`docs/evidence/2026-11-17-br3-curves.md:15-16`) | 0 |
| Curves (8) | 5 — CRV-01/02/03/07 decoded (`br3:17-19,:22`), CRV-06 negative (`br5:19`) | CRV-04, CRV-05 "documented-open" (`br3:20-21,:76-80`); CRV-08 "candidate" (`br3:23`) |
| Surfaces (8) | 5 — SRF-01 (`br2:16`), SRF-02/03/04 decoded (`br4:15-17`), SRF-08 negative (`br5:20`) | SRF-05, SRF-06 "documented-open" (`br4:18-19,:85-98`); SRF-07 "candidate" (`br4:20,:102`) |

Strictly under BR6's own counting rule — "resolved iff a committed decoder *or* a documented negative covers it;
`candidate` is not resolved" (`docs/agents/br6-graph-design.md:158`) — that is **17/23 resolved, 4
documented-open (CRV-04, CRV-05, SRF-05, SRF-06), 2 candidate (CRV-08, SRF-07)**. Counting documented-open as the
ROADMAP's negative path gives **21/23 with the same 2 candidates**. Which mapping holds is decision D4 (§6); the
rate itself must come from the committed row, not from this table.

---

## 3. Exact sequence to tag v1.0 and publish

Every Python invocation carries the host's shared-library prefix (`.venv/bin/python` needs
`libpython3.14.so.1.0` from `/usr/lib`); every step ends with a gate, because the tag must land on a commit whose
checks are green and which is already on `origin/main`.

**S0 — Preflight.** Expect only the untracked user file `RESPALDO-LEEME.md`; two commits (`ee720e5`, `e610bbc`)
are unpushed (B5).

```bash
cd /home/alan/Documents/Repos/catpart-parser
export LD_LIBRARY_PATH=/usr/lib:$LD_LIBRARY_PATH
git fetch origin && git status --short && git log --oneline origin/main..HEAD
```

**S1 — Phase 7 landed and closed** (§2, ticket #58 then #47). Expect #47 CLOSED; `docs/ROADMAP.md` Phase 7 block
present; `src/catpart/brep/graph.py` + `step_export.py` committed.

**S2 — Owner decisions recorded** (D1-D4, §5) in the owning note, dated, with declined alternatives
(`docs/agents/dispatch-recipes.md:240-262`).

**S3 — Version bump before the measured run.** The row records the installed package version
(`src/catpart/schema/fitness-history-row-v0.json:26-30`); every existing row says `0.1.0`.

```bash
# pyproject.toml: version = "0.1.0" -> "1.0.0"
.venv/bin/pip install -e '.[test,lint]'
.venv/bin/python -c "import importlib.metadata as m; print(m.version('catpart-parser'))"   # expected: 1.0.0
```

**S4 — Local gate (must be green before anything is pushed).** `scripts/check.sh` is the local copy of `ci.yml`:
ruff (`:27`), `pytest -q` (`:29-30`), claims-CSV quoting (`:37`), cargo build native + wasm32, fmt, clippy
`-D warnings`, test (`:53-62`), `wasm-pack build --target web --release --out-dir target/wasm-pack-check` and
`wasm-pack test --node` (`:79-82`), `port/pkg` vs `site/viewer/pkg` byte-identity diff (`:87`), `node --test
tests/*.mjs` (`:98-99`), Playwright assembly acceptance when installed (`:106-107`).

```bash
bash scripts/check.sh
```

Expected: every line `check: …` passes, no `SKIP` for node/playwright on this host, exit 0. CI
(`.github/workflows/ci.yml:37-147`) remains the authority; pushing `main` re-runs it via the `pre-push` hook.

**S5 — Fitness run, L1/L2/L3, on the machine holding `corpus/`** (ADR-0003: never in CI).

```bash
.venv/bin/catpart-fitness \
  --manifest manifests/corpus-manifest.csv \
  --corpus-root . \
  --fitness-dir fitness
```

Defaults are exactly those paths (`src/catpart/cli.py:150-170`); the flags are listed only to make the binding
explicit. Expected effect: the row JSON on stdout, one appended line in `fitness/history.jsonl` (today 14 lines,
`wc -l`), one full report `fitness/reports/<run_id>.json`, `scalars.L1`/`L2` identical to
`fitness/history.jsonl:14` (1,745/1,751 and 1,033/1,381), `scalars.L3` populated, `corpus_digest` still
`dc75f8fe…`, and `"accepted": true`. **If `accepted` is false the sequence stops** — `publish_fitness.py` reads
accepted rows only (B2).

**S6 — Closure docs, then commit and re-gate.** Write the D1/D2-disclosed L3 table into the Phase 7 status block
(`docs/ROADMAP.md:227`), add Phase 0/Phase 1 status blocks, add the dated closure line to `## Terminal state and
closure`, update `README.md:48`/`:113-126`, `README.es.md:49`/`:113`, and `site/index.html:35,:89` (the site row
ships to gh-pages). Every figure must be a committed row (dispatch rule,
`docs/agents/dispatch-recipes.md:126-140`).

```bash
bash scripts/check.sh && git add -A docs README.md README.es.md site pyproject.toml fitness
git commit -m "docs: Phase 7 close + v1.0 closure artifacts" && git push origin main
```

**S7 — Publish the fitness artifacts** (`scripts/publish_fitness.py:51-58`; flags `--history`, `--remote`,
`--no-push` at `:547-565`; exit 0/1/2; idempotent no-op when the tree already matches, `:44-49`).

```bash
.venv/bin/python scripts/publish_fitness.py --no-push     # optional dry run: builds refs/heads/gh-pages only
.venv/bin/python scripts/publish_fitness.py               # renders, commits, force-pushes origin/gh-pages
git ls-remote origin gh-pages                             # must equal the printed commit
```

Expected console line: `published gh-pages <commit> (tree <tree>) to origin: .nojekyll, fitness-latest.json,
fitness-history.json, + N site file(s), + M format doc(s)` (`:522-525`). The publisher dates the commit with the
last accepted run's timestamp (`:452-460`), so a successful run and a successful publish carry the same stamp.

**S8 — Verify the live surface.** `fitness-latest.json` must read the L1 share and
`fitness-history.json` must end with the new run including its L3 field; the landing page must show the new L3 row
(`.nojekyll` + `site/` are published verbatim, `scripts/publish_fitness.py:82,:377-403`).

```bash
curl -s https://raw.githubusercontent.com/MadManJohnSmith/catpart-parser/gh-pages/fitness-latest.json
curl -s https://raw.githubusercontent.com/MadManJohnSmith/catpart-parser/gh-pages/fitness-history.json | tail -30
```

**S9 — Release notes committed, then tag.** The release body must trace to a committed file, because a GitHub
release body is immutable and the project's rule is that immutable figures cite committed artifacts
(`docs/agents/dispatch-recipes.md:133-140`). Create `docs/releases/v1.0.md` from the skeleton in §4.

```bash
bash scripts/check.sh
git add docs/releases/v1.0.md && git commit -m "docs: v1.0 release notes" && git push origin main
git tag -a v1.0 -m "catpart-parser v1.0 — terminal state (ADR-0004)" "$(git rev-parse HEAD)"
git push origin v1.0
```

The `pre-push` hook gates only `refs/heads/main` (`.git/hooks/pre-push:11-17`), so the tag push is **not**
re-checked — S4/S6/S9 are the only gate on the tagged tree.

**S10 — Publish the release.**

```bash
gh release create v1.0 --verify-tag \
  --title "v1.0 — CATIA V5 reader with a client-side viewer" \
  --notes-file docs/releases/v1.0.md
```

**S11 — Close out.** Close #49 with pointers to the tag, the release, the published report and the ROADMAP closure
line; confirm every remaining open issue carries `post-v1.0` (today: #50) and settle #1 (D3). A later fix ships as
`v1.0.1` without reopening the project (`docs/ROADMAP.md:264-265`).

---

## 4. Release-notes draft skeleton (committed numbers only)

Every figure below is already committed; the bracketed slots must be filled from the new committed row/note.
Nothing here is estimated.

```markdown
# catpart-parser v1.0

A free, open-source reader for CATIA V5 `.CATPart` / `.CATProduct` binaries — no CATIA
installation — with a viewer that decodes and renders files entirely in the browser.

## What shipped

| Level | Result | Evidence |
|---|---|---|
| L1 — metadata & containers (`catpart-inspect`) | 1,745/1,751 = 99.66% Dev; 73/73 held-out | `fitness/history.jsonl:14`, `README.md:44` |
| L2 — mesh export (`catpart-export`, binary PLY) | 1,033/1,381 = 74.80% Dev; 56/61 held-out; 1,173 exports; bar re-adjusted to the measured ceiling with documented negatives | `docs/ROADMAP.md:105-124`, `:168-170` |
| L3 — B-rep construct coverage | <resolved>/23 of the frozen vocabulary; <n> documented negatives; <n> candidates | <committed L3 row id> + Phase 7 note |
| Viewer — parts (WASM, client-side) | Fidelity 3,266/3,266 (0 mismatches, full dual-slice run, 255.9 s); in-browser scalar = published L2 ± 0 | `docs/ROADMAP.md:164-177` |
| Viewer — assemblies (`.CATProduct`) | Product census 382/382 classified; instance structure agreement on 253 framed records; 4-state classification tree; headless acceptance 8/8 | `docs/ROADMAP.md:210-225`, `README.md:47` |

Live viewer: https://madmanjohnsmith.github.io/catpart-parser/viewer/viewer.html
Docs site: https://madmanjohnsmith.github.io/catpart-parser/ (format portal, evidence, export gallery)

## Corpus (frozen)

- 1,824 unique files (1,442 parts, 382 products), dev 1,751 / held-out 73
  (`docs/corpus-report.md:9-13`).
- Corpus definition = `manifests/corpus-manifest.csv`, SHA-256
  `dc75f8fe9156dd69b26f2a44ff642c396c7c484d4049a831b88cf6b91d11b164` (<re-measured at the tag commit>).
  Binaries are not redistributed; only the manifest is committed.

## What is not supported (documented negatives, not bugs)

- Parametric recipe recovery (features, sketches, editable parameters) — out of scope by decision
  (`docs/ROADMAP.md:241-243`).
- Constructs resolved as documented negatives in Phase 7: <list from the committed L3 table>.
- Products carry no geometry store (documented negative, `docs/ROADMAP.md:191-192`).

## Status

Public and usable; no maintenance is promised. A later bugfix may ship as v1.0.1 without reopening the project
(`docs/ROADMAP.md:264-265`).
```

**Do not put in the release notes:** the frozen per-class `corpus_occurrences` of CRV-04, CRV-05, CRV-08, SRF-03,
SRF-04, SRF-05, SRF-06, SRF-07 (`docs/agents/br6-vocabulary-provenance.md:52-54`); the withdrawn 4,289-loop
SRF-05 "ceiling" (`docs/evidence/2026-11-17-br4-quadrics.md:132`); any L3 rate that is not the committed row.

---

## 5. Blockers that must land before the tag

| # | Blocker | Why it blocks the tag | Owner action |
| :-- | :--- | :--- | :--- |
| **B1** | **Phase 7 is not closed** — #58 OPEN, #47 OPEN, no Phase 7 status block | ROADMAP:258 requires Phase 7 acceptance before the closure artifacts | Finish §2, close #58 → #47 |
| **B2** | **An L3 row cannot land as designed**: schema pins `scalars.L3` to `null`; runner aggregates L1/L2 only; the no-regret rule rejects a flat-L1/L2 run ("dev did not rise"); the publisher takes accepted rows only | #47 acceptance criterion 3 ("L3 headline in `fitness/history.jsonl` under no-regret") is unsatisfiable until the model, schema, rule and tests change together | Decide the model (D2) and implement it inside #58 |
| **B3** | **The publishing surface has no L3**: `fitness-history.json` renders `dev` + `l2` only; `site/index.html` has no L3 series and still prints "planned · hardest" | "Final fitness report published (gh-pages)" would publish L1/L2 only — M7 unmet even with a green L3 row | Extend `scripts/publish_fitness.py` (+ its tests) and the site charts inside #58 |
| **B4** | **Frozen denominator has 8 unprovenanced rows** — no committed generator reproduces CRV-04, CRV-05, CRV-08, SRF-03, SRF-04, SRF-05, SRF-06, SRF-07; the test pins schema only | Publishing an L3 table in BR1's shape would publish numbers no artifact produces — a direct violation of the "no invented numbers" rule | D1: disclosure column + mechanical guard (own ticket), or re-freeze (23 → 18 rows) — a STOP-and-report decision (`docs/agents/dispatch-recipes.md:240-262`) |
| **B5** | **Two commits unpushed** — local `main` @ `e610bbc`, `origin/main` @ `4b6e770` | The tag must name a commit that exists on the remote | Push after the gate |
| **B6** | **Version metadata says 0.1.0** (`pyproject.toml:7`, unchanged since ticket #11) and every history row records `tool_version: 0.1.0` | A v1.0 tag whose package metadata and measured row say 0.1.0 is not a verifiable v1.0 state (ADR-0004:43-44) | Bump, reinstall, run — in that order (S3 before S5) |
| **B7** | **Date provenance on the Phase 7 notes**: `docs/evidence/2026-11-17-br6-shell.md:3` is dated 2026-11-17 but its first commit is 2026-11-18 08:40 (`b8efbf2`, and the note itself says "committed 2026-11-18"); BR2's audit corrections (`…br2-planar-loops.md:4`) and BR5's review corrections (`…br5-cgm-nurbs.md:3,:114`) also landed 2026-11-18; the planned L3 note path is already pinned as `docs/evidence/2026-11-17-br6-graph-l3.md` (`docs/agents/br6-graph-design.md:156`) | A closure note dated before the work it records, or a release note citing "2026-11-17" for 2026-11-18 evidence, breaks the dated-evidence convention and the immutable-figures rule | Decide: land the L3 note under its real date (2026-11-18+) or keep the pinned path with an explicit dated section; release notes cite commits, not filenames |
| **B8** | **Phase 0 and Phase 1 have no status blocks** (`docs/ROADMAP.md:11-25`, `:27-39`) | ROADMAP:260-261 requires *every* phase closed or negatived | Add dated status blocks citing `docs/corpus-report.md` and the triage notes |
| **B9** | **Corpus-freeze evidence is a manifest digest, not a binary sweep** — a run never re-hashes `corpus/` | M9's "verified 2026-11-07 backup stands" must state what was actually verified | Record the manifest digest + the verification method in the release notes; re-verify with `scripts/triage/redownload_corpus.py` (verifies per-file SHA-256, `:39-40`) if a fresh sweep is wanted |
| **B10** | **No release-notes artifact exists in the repo** (no CHANGELOG, no `docs/releases/`) | The release body would be the only copy of the closure figures — uncommitted and un-citable | Commit `docs/releases/v1.0.md` before tagging (S9) |
| **B11** | **Stale published L3 copy**: `site/index.html:89` renders "planned · hardest" | gh-pages serves it verbatim (`scripts/publish_fitness.py:377-403`) | Update before S7, or republish after (publish is idempotent) |
| **B12** | **#1 (`wayfinder:map`) is open** with 6/6 sub-issues completed | Terminal state says remaining issues are labelled `post-v1.0` | D3: close as achieved, or label `post-v1.0` |

---

## 6. Owner decisions (each needs a dated record)

| # | Decision | Options | Recommendation |
| :-- | :--- | :--- | :--- |
| **D1** | Frozen L3 denominator: disclose or re-freeze? | (a) keep 23 rows, add a `provenance` column + guard, never publish the 8 unprovenanced counts as decode rates; (b) re-freeze to the generator's 18 rows | **(a)** — the audit's own recommendation: re-freezing deletes two independently established outcomes (SRF-03, SRF-04) and CRV-08's only evidence (`docs/agents/br6-vocabulary-provenance.md:120-140`) |
| **D2** | L3 in the fitness ladder | (a) L3 as a split-less, reported-not-gating scalar carried by an additive schema change + an explicit "first L3 row is a baseline transition" rule (precedent: the first L2 row, `src/catpart/fitness/runner.py:642-676`); (b) L3 with dev/held-out splits so it can legitimately "rise" | **(a)** — matches `docs/agents/br6-graph-design.md:158`; (b) invents two numbers where the census has one |
| **D3** | #1 disposition | close as achieved, or `post-v1.0` | Close: all six decision sub-issues are complete (`gh issue view 1`) |
| **D4** | "documented-open" counts as resolved? | (a) yes — CRV-04/CRV-05/SRF-05/SRF-06 are the ROADMAP's "documented negative plus published ceiling arithmetic"; (b) no — they stay unresolved and Phase 7 stays open | **(a) with disclosure**: SRF-05/SRF-06 carry an upper bound on the classified population, not a class-shaped ceiling (`docs/evidence/2026-11-17-br4-quadrics.md:85-98`), so the L3 table must say so per row. Either answer leaves CRV-08 and SRF-07 as `candidate`, which under BR6's rule is not resolved |

---

## 7. What this audit did not verify

- `scripts/check.sh` was **not** run (it builds the Rust crate and runs Playwright; the handoff budgets
  ~1.5-2 min on this host, `docs/agents/handoff-2026-11-17.md:97`). Its green state is an S4 obligation, not a
  claim of this note.
- The corpus binaries were not re-hashed; only the manifest digest was measured.
- BR2-BR6 prose figures were not re-derived — they are cited as committed verdicts. The one arithmetic this note
  performs is the resolved/unresolved count in §2, which is a count of cited rows, not a rate.
- gh-pages was read via `git show origin/gh-pages:…` (head `8e69bb7`), not over HTTP.
