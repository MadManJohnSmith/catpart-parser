# v1.0 release notes — draft + tag/publish checklist

**Date** 2026-11-18 · **Repo** `main` (measured at `c4e06cc`; the tree is moving during the release window — re-run §0 at S0) · **Scope** design draft only: no existing file was modified.
**Deliverable of record** this file. **File that ships** `docs/releases/v1.0.md` (created by copying §1 after
the `[[L3_HEADLINE]]` slot is filled from the committed row).
**Inputs** [#49](https://github.com/MadManJohnSmith/catpart-parser/issues/49) (`gh issue view 49`),
[ADR-0004](../adr/0004-terminal-state-web-viewer.md), [`ROADMAP.md:249-274`](../ROADMAP.md),
[`v1-readiness.md`](v1-readiness.md), [`br6-close-checklist.md`](br6-close-checklist.md),
`pyproject.toml`, [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml),
[`scripts/publish_fitness.py`](../../scripts/publish_fitness.py), `fitness/history.jsonl`.

**This draft is deliberately not a "ready to tag" artifact.** Three committed facts block the sequence in
§2 as written: Phase 7 is short of its own acceptance text (2 `candidate` rows put the contract at 21/23;
§0 G2), the L3 counting rule is written one way in the contract and another in the scorer/tests (§0 G3),
and the BR6 graph/STEP deliverables targeted by #58 are absent from the tree (§0 G1). Section 2 therefore
starts with STOP gates. A release body that skips them would violate the "no invented numbers" rule
(`dispatch-recipes.md:126-140`) and ADR-0004's "verifiable state" requirement
(`0004-terminal-state-web-viewer.md:43-44`).

---

## 0. Gates that must be green before S1 (state at `c4e06cc`)

| # | Gate | State | Citation |
| :-- | :--- | :--- | :--- |
| **G1** | Phase 7 deliverables landed — B-rep graph + STEP export + close note | **Not met**: `git ls-files` has no `src/catpart/brep/graph.py`, no `step_export.py`, no `scripts/triage/decode_brep_graph.py`, no `tests/test_brep_graph.py`; `src/catpart/brep/__init__.py:1-10` still calls itself the scaffold the orchestrator populates "at the BR6 integration step" | `src/catpart/brep/__init__.py:1-10`; `v1-readiness.md` §2 P7-1; `br6-close-checklist.md:16-21` |
| **G2** | 100% of the frozen 23 constructs resolved | **Not met under the contract**: 14 decoded + 3 documented-negative + 4 documented-open = **21/23**; CRV-08 and SRF-07 remain `candidate`, and the contract says "`candidate` and `pending-merge` are not resolved". (The older 17/23 reading in the close audit predates the 2026-11-18 correction that added documented-open to the resolved set.) | `br6-graph-design.md:158`; `br6-close-checklist.md:96-114` |
| **G3** | One L3 counting rule across artifacts | **Contradiction**: the design note and the row schema both say a `candidate` is NOT resolved (`br6-graph-design.md:158`; `fitness-history-row-v0.json:196-201`), while the scorer's `RESOLVED_OUTCOMES` includes `candidate` (`l3.py:114`, `:519-520`), the tests pin 23/23 with `candidate: 2` (`tests/test_fitness_l3.py:116-137`), and the L3 claims call 23/23 "every frozen construct resolved" (`br6-l3-claims.csv:3`). The runner would therefore emit a scalar that contradicts the contract it is scored against. | the five citations in this row; also `2026-11-18-br6-l3-history.md:42-44` |
| **G4** | L3 row appended to the committed history | **Not met**: 14 rows, every one `"L3": null`, every one `tool_version: 0.1.0` | `fitness/history.jsonl:1-14` |
| **G5** | ROADMAP status blocks complete | **Not met**: `grep 'Status (' docs/ROADMAP.md` → lines 51, 72, 96, 158, 209 only; Phase 0 (`:11-25`), Phase 1 (`:27-39`) and Phase 7 (`:227-247`) have none | `ROADMAP.md:11-39`, `:227-247`; `v1-readiness.md` M8 |
| **G6** | Closure artifacts absent | no tag local or remote (`git tag -l` empty, `git ls-remote --tags origin` empty), no release (`gh release list` empty), no `docs/releases/` directory | measured at `c4e06cc` |
| **G7** | Local `main` is the remote's `main` | **Not met**: local `main` is 6 commits ahead of `origin/main` @ `6a2d042` at measurement (`c4e06cc` head) | `git log --oneline origin/main..HEAD` |

**Gate rule.** If any of G1-G3 is still open at S3, the sequence stops. Do **not** resolve G2/G3 by editing
the frozen vocabulary, relabelling a row, or hand-computing a percentage: a counting-rule change is a
STOP-and-report owner decision (`dispatch-recipes.md:240-262`), and the pre-authorized bar-revision rule does
not apply because nothing shows CRV-08/SRF-07 are unreachable (`ROADMAP.md:267-274`;
`br6-close-checklist.md:199-206`).

---

## 1. Release-notes draft (for `gh release create v1.0 --notes-file`)

Copy the block below verbatim to `docs/releases/v1.0.md` and replace the one placeholder,
`[[L3_HEADLINE]]`, with the value read from the committed row — never with a hand-computed ratio. The fill
must have this shape, with every angle-bracket value taken from the row:

> `<resolved>/<total>` resolved under the row's counting rule — decoded `<n>`, documented-negative `<n>`,
> documented-open `<n>`, candidate `<n>` — row `<run_id>`

For orientation only: the committed scorer's registry yields 23/23 with `candidate: 2`
(`tests/test_fitness_l3.py:116-137`), but the design contract says those two candidates are **not**
resolved, i.e. 21/23 (`br6-graph-design.md:158`). The appended row is the authority and the fill must match
it, not this note. Stop if `resolved != total`, **and also** stop if
`resolved != decoded + documented-negative + documented-open` — that inequality means the row counted
candidates as resolved, contradicting the contract even when `resolved == total`. Phase 7's acceptance
text is "100% of the frozen vocabulary resolved" (`ROADMAP.md:245-247`), so the body must not claim it
otherwise. The `candidate <n>` part of the fill is mandatory whenever it is non-zero: publishing 23/23 as
"100% decoded" would be false (`l3.py:24-30`).

````markdown
# catpart-parser v1.0

A free, open-source reader for CATIA V5 `.CATPart` / `.CATProduct` binaries — no CATIA
installation — with a viewer that decodes and renders parts and assemblies entirely in the
browser.

## What shipped

| Level | Result | Evidence |
|---|---|---|
| **L1 — metadata & containers** (`catpart-inspect`) | Dev **1,745/1,751 = 99.66%**; held-out **73/73** | `fitness/history.jsonl:14`, `docs/ROADMAP.md:72-85` |
| **L2 — mesh export** (`catpart-export`, binary PLY) | Dev **1,033/1,381 = 74.80%**; held-out **56/61**; **1,173** exports; closed at the measured ceiling with the bar re-adjusted to it at margin 0 | `fitness/history.jsonl:14`, `docs/ROADMAP.md:96-124` |
| **L3 — B-rep construct coverage** | [[L3_HEADLINE]] | `fitness/history.jsonl` (last row), `docs/evidence/2026-11-18-br6-l3-history.md` |
| **Part viewer** (Rust→WASM, client-side) | Fidelity **3,266/3,266**, **0** mismatches, **0** harness errors — one run, both slices, full populations, 255.9 s; in-browser scalar = the published L2 scalar ± 0 (declared margin 0) | `docs/ROADMAP.md:158-187`, `docs/evidence/2026-11-14-v6-fidelity-full-corpus.md` |
| **Assembly viewer** (`.CATProduct`, multi-file) | Product census **382/382** classified; instance-structure agreement on **253** framed records; 4-state classification tree; headless acceptance **8/8** | `docs/ROADMAP.md:209-225`, `README.md:47` |

The L3 figure is **construct coverage over the vocabulary frozen by the Phase 7 census** — one scalar, not a
corpus-wide exact-solid rate, and it has no Dev/held-out split because construct coverage is a property of the
decoder/evidence set, not of a corpus sample. It is reported alongside L1/L2 under no-regret; corpus
prevalence is reported alongside it and never gates (`docs/ROADMAP.md:245-247`).

Live viewer: https://madmanjohnsmith.github.io/catpart-parser/viewer/viewer.html
Docs site: https://madmanjohnsmith.github.io/catpart-parser/

## Corpus (frozen)

- **1,824 unique files** — 1,442 parts, 382 products; Dev **1,751** / held-out **73**
  (`docs/corpus-report.md:9-13`).
- The corpus definition is `manifests/corpus-manifest.csv`, SHA-256
  `dc75f8fe9156dd69b26f2a44ff642c396c7c484d4049a831b88cf6b91d11b164`. The same digest is the
  `corpus_digest` of every committed fitness row, so the corpus definition has not moved since the first
  accepted run (`fitness/history.jsonl:1-14`; `src/catpart/fitness/runner.py:160-166`).
- **Freeze statement — what was verified.** The verified 2026-11-07 backup stands. This release verifies
  the **manifest**, not the binaries on disk: a fitness run validates every manifest field (per-file
  SHA-256 format, kind, split, path, no duplicate digests) and never re-hashes `corpus/`
  (`src/catpart/fitness/runner.py:169-237`). Binaries are not redistributed; only the manifest is
  committed.

## What is not supported (documented negatives, not bugs)

- **Parametric recipe recovery** — features, sketches and editable parameters are out of scope by
  decision; the Phase 3 specification-tree negative stands (`docs/ROADMAP.md:81-85`, `:241-243`).
- **Products carry no geometry store** — 0/382 product rows in the Phase 6 census
  (`docs/ROADMAP.md:210`); the earlier sampled negative was 0/37 (`:191-192`).
- **The L2 ceiling is measured, not unfinished** — 74.80% is the reachable ceiling: 128 no-pool stores
  carry zero facet records (structurally incapable), 125 missing-locator headers are unreachable by
  construction, the UV family's element coordinates are not in the payload, and the remaining
  not-manifold failures are content fins present in the bytes; the measured residual ceiling (+32) landed
  in the final stage and the bar was re-adjusted to 74.80% at margin 0
  (`docs/ROADMAP.md:107-115`).
- **L3 denominator provenance (disclosure).** The per-construct corpus counts in the frozen vocabulary are
  quoted as frozen input, never as decode rates: **15 of 23** reproduce exactly from the committed census
  CSV, and **8** — `CRV-04`, `CRV-05`, `CRV-08`, `SRF-03`, `SRF-04`, `SRF-05`, `SRF-06`, `SRF-07` — have
  no committed generator and no claims row, so no committed artifact produces them
  (`docs/agents/br6-vocabulary-provenance.md:52-96`). Four further rows (`TOP-02`, `CRV-03`, `CRV-06`,
  `SRF-08`) carry counts produced by detectors that do not measure the named construct (`:110-114`).
  `CRV-03` = 357 equals `CRV-04` + `CRV-05` = 214 + 143, so those three rows double-count the conic
  carrier set and are not a partition (`:88-96`). The headline is row-level construct coverage and does
  not rest on those cells; the denominator is kept and disclosed rather than re-frozen, because
  re-freezing would shrink 23 → 18 rows and delete independently established outcomes
  (`:120-141`).
- **B-rep identity.** The L3 metric is construct coverage; it is not a claim that every part exports an
  exact solid.

## Status

Public and usable. **No maintenance is promised**; a later bugfix may ship as `v1.0.1` without reopening
the project (`docs/ROADMAP.md:264-265`). The final fitness report is published on gh-pages.

Every figure above traces to a committed artifact at the tag commit: the fitness rows
(`fitness/history.jsonl`), the phase close blocks (`docs/ROADMAP.md`), the dated evidence notes and claims
CSVs (`docs/evidence/`), and the corpus report (`docs/corpus-report.md`).
````

### 1.1 Fill instructions (kept out of the release body)

1. `[[L3_HEADLINE]]` ← the last row of `fitness/history.jsonl`: `scalars.L3.resolved`/`total`,
   `scalars.L3.rate`, `scalars.L3.by_outcome`, and its `run_id`. One sentence, all four numbers.
2. If the row's `by_outcome.candidate` is non-zero, the fill must say "candidate N" — the release must not
   present candidate rows as decoded coverage (`l3.py:24-30`; `2026-11-17-br6-l3-scorer.md:205-233`).
3. Re-check the two named outcome lists in §1 against the row before publishing; the registry is a module
   constant and can move between this draft and the run (`l3.py:216-223`).
4. L1/L2 cite `fitness/history.jsonl:14` — the accepted L2 row `20261113T231506Z-c2ab64`. The L3 append
   becomes line 15 and does not move that row, so the citation stays stable.
5. Do **not** add a per-construct corpus count/rate table to the release body. The Phase 7 note owns it,
   under the provenance disclosure (`br6-vocabulary-provenance.md:120-141`).
6. If `src/catpart/brep/graph.py` + `step_export.py` land before the tag, add one capability row citing
   their commits; if they do not, do not mention STEP export anywhere in the body (G1).

---

## 2. Exact ordered checklist to tag and publish v1.0

Every Python invocation is prefixed with `export LD_LIBRARY_PATH=/usr/lib:$LD_LIBRARY_PATH` on this host
(`.venv/bin/python` needs `libpython3.14.so.1.0` from `/usr/lib`; `v1-readiness.md:64-66`).
Run everything from `/home/alan/Documents/Repos/catpart-parser`.

### S0 — Preflight (read-only)

```bash
export LD_LIBRARY_PATH=/usr/lib:$LD_LIBRARY_PATH
git fetch origin
git status --short                  # expect only untracked user/agent files, no tracked modifications
git log --oneline origin/main..HEAD # non-empty now (G7); must be empty after S4/S6
git tag -l v1.0                     # must be empty
git ls-remote --tags origin v1.0    # must be empty
gh release list                     # must not contain v1.0
```

STOP unless G1-G3 in §0 are green. They are not green at `c4e06cc`.

### S1 — Version bump (`pyproject.toml` + the `tool_version` read path)

`tool_version` is read from the **installed package metadata**, not from a source constant:
`src/catpart/fitness/runner.py:572-577` (`importlib.metadata.version("catpart-parser")`, `0+unknown` when
not installed), recorded on the report at `:749` and on the history row at `:765`; the row schema documents
the same source (`src/catpart/schema/fitness-history-row-v0.json:26-30`). The only version string that feeds
it is `pyproject.toml:7` (currently `0.1.0`; every committed row records `0.1.0`,
`fitness/history.jsonl:1-14`).

```bash
# edit pyproject.toml:7 -> version = "1.0.0"
.venv/bin/pip install -e '.[test,lint]'   # refreshes the installed metadata; do not skip
.venv/bin/python -c "import importlib.metadata as m; print(m.version('catpart-parser'))"
# expected: 1.0.0
```

Do **not** run the fitness run before this step — the row would record `0.1.0` and the tagged state would
not be a verifiable v1.0 (`v1-readiness.md` B6).

Out of scope by decision: `port/Cargo.toml:11` and `port/pkg/package.json:5` also say `0.1.0`, but they do
not feed `tool_version`. Changing them forces a `wasm-pack` rebuild of both committed pkg copies
(`scripts/check.sh:87-94` enforces byte identity with `site/viewer/pkg`). Leave them unless the owner wants
the shipped WASM package versioned; record the decision either way.

### S2 — Full local gate

```bash
bash scripts/check.sh
```

This is the local copy of CI (`.github/workflows/ci.yml:37-147`): ruff (`check.sh:27-28`), `pytest -q`
(`:29-30`), claims-CSV quoting (`:37-38`), cargo build native + wasm32, fmt, clippy `-D warnings`, test
(`:52-62`), `wasm-pack build --target web --release --out-dir target/wasm-pack-check` and
`wasm-pack test --node` (`:79-82`), `port/pkg` vs `site/viewer/pkg` identity (`:87-94`), `node --test
tests/*.mjs` (`:96-99`), Playwright assembly acceptance (`:104-107`). Expected: every `check: …` line
passes, **no `SKIP`** for node/Playwright on this host, exit 0. CI remains the authority; the `pre-push`
hook re-runs this gate for `refs/heads/main` only (`.git/hooks/pre-push:11-17`).

### S3 — Local fitness run that writes the L3 row (machine holding `corpus/`)

Never in CI (`ADR-0003`; `ci.yml:1-5`). Corpus must be present (~3.4 GB) and `manifests/corpus-manifest.csv`
must be the committed one.

```bash
export LD_LIBRARY_PATH=/usr/lib:$LD_LIBRARY_PATH
.venv/bin/catpart-fitness \
  --manifest manifests/corpus-manifest.csv \
  --corpus-root . \
  --fitness-dir fitness
```

The three flags are the documented defaults (`src/catpart/cli.py:150-170`); they are written out to make the
binding explicit. Expected: the row JSON on stdout; **one** appended line in `fitness/history.jsonl`
(`wc -l` → 15); one `fitness/reports/<run_id>.json`; `tool_version: 1.0.0`; `corpus_digest`
`dc75f8fe…`; `scalars.L1`/`L2` identical to row 14 (1,745/1,751 and 1,033/1,381); `scalars.L3` populated;
`accepted: true` and `no_regret.reason` = `"L3 recorded with L1/L2 intact"`
(`src/catpart/fitness/history.py:74`, `:421-448`). Verify:

```bash
.venv/bin/python -c "import json; r=json.loads(open('fitness/history.jsonl').read().splitlines()[-1]); print(r['run_id'], r['tool_version'], r['accepted'], r['corpus_digest']); print(r['scalars']['L1']); print(r['scalars']['L2']); print(r['scalars']['L3']); print(r['no_regret'])"
wc -l fitness/history.jsonl
sha256sum manifests/corpus-manifest.csv
```

**STOP conditions:** `accepted` is false (`publish_fitness.py` takes accepted rows only,
`scripts/publish_fitness.py:545`); `scalars.L3` is null; `tool_version` is not `1.0.0`; the digest differs
from the manifest; or L1/L2 moved. Do not edit the row or the history by hand — the history is append-only
and a rejected row stays as the record.

### S4 — Closure docs, gate, commit, push

Edit, citing only figures that exist in committed artifacts:

- `docs/ROADMAP.md` — add the **Phase 7 status block** after `:247` (pattern: Phase 4 at `:96`, Phase 6 at
  `:209`), containing the committed L3 row id and the per-construct L3 table under the D1 disclosure; add
  the missing **Phase 0** block after `:25` and **Phase 1** block after `:39`; mark terminal-state item 4
  closed and add the dated closure line inside `## Terminal state and closure` (after `:265`).
- `README.md:48` (L3 capability row), `:111` (L3 table row), `:126` (Spec G state).
- `README.es.md:49`, `:113`.
- `site/index.html:89` (`planned · hardest` → the committed L3 result) and **`:36`** (`55 / 61 unseen
  parts` → the accepted row's **56/61**, `fitness/history.jsonl:14`; this is a live published-figure
  defect, `v1-readiness.md` B11-adjacent).
- the Phase 7 close note at its real date (pinned candidate `docs/evidence/2026-11-17-br6-graph-l3.md`,
  `docs/agents/br6-graph-design.md:156`; `v1-readiness.md` B7 requires the actual landing date).

```bash
bash scripts/check.sh
git add pyproject.toml fitness docs/ROADMAP.md docs/evidence README.md README.es.md site
git status --short
git commit -m "docs: Phase 7 close + v1.0 closure artifacts"
git push origin main
git log --oneline origin/main..HEAD   # must be empty
```

Use explicit pathspecs (as above), not `git add -A`: the tree also carries the user file
`RESPALDO-LEEME.md`, and this draft (`docs/agents/v1-release-notes-draft.md`) is not part of the release
payload unless the owner chooses to keep it as a design record. `git add fitness` stages both the appended
`fitness/history.jsonl` row and the new `fitness/reports/<run_id>.json`.

### S5 — gh-pages publish (exact command) + live verification

The publisher reads `fitness/history.jsonl`, renders `fitness-latest.json` + `fitness-history.json`, and
rebuilds `gh-pages` from those plus `site/` and `docs/format`; default remote `origin`, default history
`fitness/history.jsonl`; flags are `--history`, `--remote`, `--no-push`; exit codes 0/1/2
(`scripts/publish_fitness.py:55-63`, `:614-631`). It is idempotent and force-updates `gh-pages`, which is
safe because that branch holds only generated files (`:48-53`).

```bash
export LD_LIBRARY_PATH=/usr/lib:$LD_LIBRARY_PATH
.venv/bin/python scripts/publish_fitness.py --no-push   # optional dry run: builds refs/heads/gh-pages only
.venv/bin/python scripts/publish_fitness.py             # render, commit, force-push origin/gh-pages
git ls-remote origin gh-pages                           # must equal the printed commit
```

Expected console line (`:589-592`):

```text
published gh-pages <commit> (tree <tree>) to origin: .nojekyll, fitness-latest.json, fitness-history.json, + N site file(s), + M format doc(s)
```

The publication commit is dated with the last accepted run's timestamp (`:520-527`). Then verify the served
surface:

```bash
curl -s https://raw.githubusercontent.com/MadManJohnSmith/catpart-parser/gh-pages/fitness-latest.json
curl -s https://raw.githubusercontent.com/MadManJohnSmith/catpart-parser/gh-pages/fitness-history.json | tail -30
```

`fitness-history.json` must end with the new run **including `"l3"`**, and the landing page must no longer
say `planned · hardest` (`site/index.html:89`; `site/` is published verbatim,
`scripts/publish_fitness.py:442-470`).

### S6 — Release-notes file, final gate, commit, push

```bash
# copy §1 of this draft to docs/releases/v1.0.md, fill [[L3_HEADLINE]] from the row, re-check the disclosures
bash scripts/check.sh
git add docs/releases/v1.0.md docs/ROADMAP.md
git commit -m "docs: v1.0 release notes"
git push origin main
git log --oneline origin/main..HEAD   # must be empty
git status --short                    # must not show docs/releases/v1.0.md
```

The release body must exist in the repository before the tag: a GitHub release body is immutable in this
project's discipline, and immutable figures must cite committed artifacts (`dispatch-recipes.md:133-140`;
`v1-readiness.md` B10).

### S7 — Tag and push

The tag must name a commit that is already on `origin/main` and already contains S4+S6
(`v1-readiness.md` M12; ADR-0004:43-44).

```bash
git rev-parse HEAD
git rev-parse origin/main                              # must be identical
git tag -a v1.0 -m "catpart-parser v1.0 — terminal state (ADR-0004)" "$(git rev-parse HEAD)"
git push origin v1.0
git ls-remote --tags origin v1.0                       # tag object + peeled commit
git rev-parse v1.0^{commit}                            # must equal origin/main
```

The `pre-push` hook gates only `refs/heads/main` (`.git/hooks/pre-push:11-17`), so the tag push is **not**
re-checked: S2 and S6 are the only gate on the tagged tree.

### S8 — Publish the release

```bash
gh release create v1.0 --verify-tag \
  --title "v1.0 — CATIA V5 reader with a client-side viewer" \
  --notes-file docs/releases/v1.0.md
gh release view v1.0 --json tagName,name,isDraft,isPrerelease,url
```

`--verify-tag` makes the command fail rather than create a missing tag. Verify the body matches the
committed file:

```bash
gh release view v1.0 --json body -q .body > /tmp/opencode/release-body.md
diff -u docs/releases/v1.0.md /tmp/opencode/release-body.md   # empty except a possible trailing newline
```

### S9 — Issue closures (#58, then #47, then #49; #1 per D3)

`#58` is the BR6 implementation ticket; it closes before `#47` (Spec G), which closes before `#49` (the
release ticket). All three close with **committed** pointers only (`dispatch-recipes.md:133-140`).

```bash
gh issue close 58 --comment "<BR6 close: graph/STEP commits, L3 row id, ROADMAP Phase 7 block>"
gh issue close 47 --comment "<Spec G close: use the §4 draft in docs/agents/br6-close-checklist.md:167-197 with every <...> replaced by a committed row>"
gh issue close 49 --comment "<closure: tag v1.0, release URL, gh-pages publication, ROADMAP closure line, L3 row id>"
gh issue close 1  --comment "<D3: all six decision sub-issues complete; closed as achieved>"
gh issue list --state open     # expect only the post-v1.0 issue #50
```

`#50` already carries the `post-v1.0` label; verify rather than re-label. Do not close `#47` from the draft
text if G2 is still open — the draft itself is preconditioned on A2/A3/A4 being green
(`br6-close-checklist.md:167-170`). `#1`'s disposition is decision D3 (`v1-readiness.md:258`): the
recommendation is to close it as achieved (all six decision sub-issues are complete); the recorded
alternative is to label it `post-v1.0` instead.

### S10 — ROADMAP final state (verification against the **tagged tree**)

```bash
git show v1.0:docs/ROADMAP.md | grep -n 'Status ('          # expect 8 blocks: Phases 0-7
git show v1.0:docs/ROADMAP.md | sed -n '/## Terminal state and closure/,$p'
git show v1.0:README.md | grep -n -iE 'in progress|planned'
git show v1.0:README.es.md | grep -n -iE 'en curso|planeado'
git show v1.0:site/index.html | grep -n -iE 'planned|55 / 61'
git show v1.0:docs/releases/v1.0.md | head -40
git rev-parse v1.0^{tree} origin/main^{tree}                # must be identical
```

Expected: every phase carries a status block; the terminal-state block marks Phases 4-7 closed (or
negatived) with dates; no `in progress` / `en curso` L3 row remains; the tagged tree contains the release
notes and the L3 row; the tag tree equals `origin/main`'s tree.

---

## 3. Do-not-publish list

These are the specific ways the evidence does **not** support a number. All are forbidden in the release
body, the tag annotation, the gh-pages site, the README(s) and the close comments.

1. **The 8 unprovenanced denominator cells, as counts or rates.** `CRV-04` 214 / 0.182, `CRV-05` 143 /
   0.115, `CRV-08` 1,280 / 0.975, `SRF-03` 542 / 0.465, `SRF-04` 412 / 0.354, `SRF-05` 320 / 0.275,
   `SRF-06` 680 / 0.582, `SRF-07` 890 / 0.795. No committed generator, no claims row, and the rates are
   not `round(k/1089, 4)` for any integer `k` (`br6-vocabulary-provenance.md:52-54`, `:68-96`).
2. **The four mis-scoped denominators as decode rates.** `TOP-02` 1,435 (= body/CGM presence), `CRV-03`
   357 (= every conic carrier, no ellipse discriminator), `CRV-06` and `SRF-08` 1,435 (= `cgm_present`;
   BR5 measures content at 0/1,089) (`br6-vocabulary-provenance.md:110-114`).
3. **The conic split as a partition.** `CRV-03` = 357 = `CRV-04` 214 + `CRV-05` 143 is double-counting the
   same 357-file carrier set (`:88-96`).
4. **Any corpus rate as the headline.** In particular `BR6L3-16` 21,659 / 33,166 = 0.6530: it is a sum over
   the frozen `corpus_occurrences` column, so it inherits the 8 unprovenanced cells, and the close audit
   explicitly says no aggregate L3 corpus rate should be built from those cells
   (`br6-close-checklist.md:142-145`; the row itself is `br6-l3-claims.csv:17`). Say "corpus prevalence is
   reported alongside and never gates" without a number.
5. **"100% resolved" / "23/23" / "0 candidates"** unless the committed row's `resolved == total`
   **and** `resolved == decoded + documented-negative + documented-open`. The contract reading is **21/23**
   (`br6-graph-design.md:158`: candidate and pending-merge are not resolved; the schema description agrees,
   `fitness-history-row-v0.json:196-201`). The committed code emits 23/23 only because `RESOLVED_OUTCOMES`
   also counts `candidate` (`l3.py:114`); that is the defect to fix before publishing, not a number to
   quote. The older 17/23 reading (`br6-close-checklist.md:107`) predates the 2026-11-18 correction. Never
   publish 23/23 as "all decoded": 14 are decoded (`br6-l3-claims.csv:4`).
6. **The withdrawn SRF-05 ceiling.** The 4,289-loop figure was FALSE and is withdrawn; 67,919 is a bound on
   the whole classified population, explicitly "not a corpus ceiling", and SRF-06 inherits it
   (`2026-11-17-br4-quadrics.md:92`, `:132`; `br6-close-checklist.md:135-137`).
7. **"The corpus was re-hashed for the release."** Only the manifest digest is measured; a run validates
   manifest fields and never re-hashes `corpus/` (`src/catpart/fitness/runner.py:169-237`;
   `v1-readiness.md:27`, B9). The freeze statement must name that method.
8. **The 0/37 product figure as the census result.** The Phase 6 census is 0/382 (`ROADMAP.md:210`);
   0/37 is an earlier sample (`:191-192`). Never present the sample as the census.
9. **L2 as a whole-corpus rate.** The denominator is the parts-only population: 1,381 Dev parts and 61
   held-out parts (`fitness/history.jsonl:14`); products are excluded, and 1,173 files exported.
10. **The stale 55/61 held-out figure** on `site/index.html:36`. The accepted row is 56/61
    (`fitness/history.jsonl:14`). Fix before publishing; the site ships verbatim.
11. **STEP export / exact solids**, while `src/catpart/brep/graph.py` and `step_export.py` are absent
    (`src/catpart/brep/__init__.py:1-10`, G1). The L3 metric is construct coverage, not an export promise.
12. **Any figure that is not in a committed artifact at the tag commit** — including uncommitted first-run
    timings (the #52 precedent: the close comment cited 76.0 s while the committed record says 122.6 s,
    `dispatch-recipes.md:133-140`), and any hand-computed percentage from the L3 outcome counts.
13. **"The L3 scorer decodes bytes."** It cites one committed claim row per construct and validates the
    citation, path, label and attribution; it never measures geometry
    (`2026-11-17-br6-l3-scorer.md:205-233`; `l3.py:9-13`).

---

## 4. Rollback and post-publication immutability

### 4.1 If the tag or release is wrong — before it is announced/consumed

Delete in this order (release first, so no release is left pointing at a missing tag):

```bash
gh release delete v1.0 --yes          # removes the GitHub release; keeps the tag
git push origin :refs/tags/v1.0       # delete the remote tag (or: git push --delete origin v1.0)
git tag -d v1.0                       # delete the local annotated tag object
```

Then fix the underlying commit on `main` with a **new** commit (never rewrite published `main`), re-run
`bash scripts/check.sh`, push, recreate the tag on the corrected commit, and recreate the release with
`--notes-file docs/releases/v1.0.md`.

- Wrong **body only**, tag/tree correct: commit the corrected notes file, then
  `gh release edit v1.0 --notes-file docs/releases/v1.0.md`. Never edit the body in the web UI: the
  corrected prose must be a committed artifact first (`dispatch-recipes.md:133-140`).
- Wrong **tag target** (tag on the wrong commit): the delete/re-tag sequence above; verify
  `git rev-parse v1.0^{commit}` equals `origin/main` before re-creating the release.
- Wrong **gh-pages content**: simply republish — the publisher is idempotent and force-updates the
  generated branch (`scripts/publish_fitness.py:48-53`, `:568-583`).

### 4.2 If v1.0 was already announced

Do not delete the tag or the release. Ship `v1.0.1` instead (`ROADMAP.md:264-265`): a deleted/re-pointed
public tag breaks clones, forks and caches and falsifies ADR-0004's "the tag exists with every phase closed
or negatived" state (`0004-terminal-state-web-viewer.md:43-44`). A correction to a published figure is
recorded as a dated correction in the owning evidence note, not by rewriting history
(`dispatch-recipes.md:112-121`).

### 4.3 What must stay immutable after publication

| Artifact | Rule | Citation |
| :--- | :--- | :--- |
| The `v1.0` tag object and its target commit | Never moved, never re-pointed, never force-updated. Fixes go to `v1.0.1`. | ADR-0004:43-44; `ROADMAP.md:264-265` |
| `fitness/history.jsonl` | Append-only. Never delete, reorder or rewrite a row; a rejected row stays. New runs append one line. | ADR-0001 no-regret; `2026-11-18-br6-l3-history.md:131-135` |
| `manifests/corpus-manifest.csv` and its digest | The corpus definition is frozen; a different digest voids comparison against earlier rows. | `fitness-history-row-v0.json:31-35`; `src/catpart/fitness/runner.py:160-166` |
| The release body's figures | Trace to committed artifacts at the tag commit; corrections come from a committed file, dated. | `dispatch-recipes.md:126-140` |
| `docs/releases/v1.0.md` | Is the release body's source of record; edit only via a commit + `gh release edit`. | `v1-readiness.md` B10 |
| Dated evidence notes and claims CSVs cited by the release | Corrections land as dated sections inside the owning note; no retroactive rewriting. | `dispatch-recipes.md:112-121` |
| The tagged tree's ROADMAP/README/site | The tag must contain the closure state it claims; verify with `git show v1.0:…` (S10). | ADR-0004:43-44 |

`gh-pages` is the one generated surface that is safe to force-update: it holds only generated files
(`fitness-latest.json`, `fitness-history.json`, `.nojekyll`, `site/`, `format/`), so a later republish is a
normal operation, not a rewrite of the project record (`scripts/publish_fitness.py:41-53`). Because the
branch is force-pushed, the release body should cite the **committed** row and the live JSON URLs rather
than a gh-pages commit hash that a later publish can orphan.
