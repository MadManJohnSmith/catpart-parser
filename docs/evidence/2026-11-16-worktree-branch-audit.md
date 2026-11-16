# Worktree & Branch Audit — 2026-11-16

**Auditor:** WORKTREE & BRANCH CLEANUP AUDITOR  
**Date:** 2026-11-16  
**Context:** Handoff item 4 ("the residual-worktree sweep: third deferral, ~24 branches + 5 unmerged-judgment branches + 1 dirty t3/dup-pin-all-unordered-dedup").  
**Authority:** Repo root at `/home/alan/Documents/Repos/catpart-parser`, main @ `f3531a9` (ahead of `origin/main` @ `8af7ccd` by 1 commit: P2.5 merge).

---

## 1. Executive Summary

This audit performs the comprehensive residual-worktree and branch sweep deferred across Phase 4 and Phase 5. Every active worktree, local branch, and remote tracking branch was inspected for path, checked-out commit, cleanliness, merge status, and patch equivalence against `main`.

### Key Findings

1. **Active Worktrees (33 total):**
   - **1 Primary Repository Checkout:** `/home/alan/Documents/Repos/catpart-parser` on `main` (**KEEP**, untouchable).
   - **3 Review Worktrees in State Directory (`~/.local/state/catpart-parser/`):** All detached HEAD, clean, and 100% verified landed on `main`.
   - **29 Worktrees in T3 State Directory (`~/.t3/worktrees/catpart-parser/`):**
     - 8 detached HEAD worktrees (clean, all verified landed on `main`).
     - 5 worktrees on branches merged in DAG into `main` (4 clean, 1 dirty).
     - 16 worktrees on grind-era branches whose commits were rebased/squashed into `main` (clean, 15 verified identical patch-ids on `main`, 1 explicitly reconciled and discarded).
   - **Net Worktree Disposition:** **32 stale worktrees eligible for safe removal**; 0 active delegate worktrees in flight.

2. **The Dirty Worktree (`t3/dup-pin-all-unordered-dedup`):**
   - Worktree path: `/home/alan/.t3/worktrees/catpart-parser/t3-784f911f-2e28ab51352ce0b4` checked out on `t3/dup-pin-all-unordered-dedup` @ `6fc5935`.
   - Status: Modified `src/catpart/geometry/composite.py`.
   - **Action Taken:** Per the residual-worktree playbook (`docs/agents/dispatch-recipes.md`), a safe diff snapshot was created before anything was touched:
     `~/.local/state/catpart-parser/t3-dup-pin-all-unordered-dedup-residual.patch` (15,916 bytes).
   - **Root Cause & Content Parity:** This uncommitted work was the early Stage-15 implementation draft of the relaxed dup-pin law before unordered-triangle dedup was added to all four composite exits. The complete implementation was subsequently committed on `t3/dup-pin-all-unordered-tri-dedup` at commit `8241006` and landed on `main` at commit `3e0a4f5`. No uncommitted content is lost.

3. **Status of P2.5 Worktree:**
   - Worktree path: `/home/alan/.t3/worktrees/catpart-parser/t3-e4707571-bce6f1f1255b5ce5` on `t3/p2-5-probe-position-encoding`.
   - Status: **Clean**, and fast-forward merged to local `main` at commit `f3531a9`. Safe to remove with `git worktree remove`.

4. **Resolution of the 5 "Unmerged-Judgment" Branches:**
   - The five branches named in commit `78e2e8b` as requiring unmerged judgment (`stage-4a-residue-family`, `t3/stage-3d-reconciliation`, `t3/integrate-raw-array-decode`, `t3/integrate-stage8-locator-artifacts`, `t3/integrate-decode-laws-exporter`) are **confirmed 100% merged into `origin/main`** (local rebased branches merged; remote branches carry identical patch-ids).

5. **Local Branches (52 total):**
   - **2 Protected Branches:** `main` (active trunk) and `gh-pages` (orphan branch hosting the live GitHub Pages viewer). **KEEP**.
   - **30 Merged Branches without Worktrees:** Fully merged into `main` in git DAG. Safe to delete immediately via `git branch -d`.
   - **5 Merged Branches with Worktrees:** Merged into `main`, but currently checked out in stale worktrees. Safe to delete with `git branch -d` immediately following worktree removal.
   - **14 Rebased/Landed Branches:** Unmerged in DAG solely due to the linear-history rebase protocol, but verified to have 100% of their commits landed on `main` with identical patch-ids. Safe to delete with `git branch -D`.
   - **1 Reconciled/Discarded Branch:** `stage-3d-exporter-integration` @ `d832b86` (alternative stage-3d implementation; explicitly analyzed, reconciled, and discarded per commit `53ea4df` and `docs/agents/stage-3d-reconciliation.md`). Safe to delete or archive.

6. **Cleanup Automation Script:**
   - Created `scripts/triage/cleanup_stale_worktrees.sh` (executable, tested, and guarded by safety unit tests in `tests/test_cleanup_stale_worktrees.py`). Default mode is non-destructive dry-run.

---

## 2. Complete Worktree Inventory (33 Worktrees)

| # | Worktree Path | HEAD SHA | Checked-out Ref | Status | Landed on `main` | Recommended Action |
|---|---|---|---|---|---|---|
| 01 | `/home/alan/Documents/Repos/catpart-parser` | `f3531a9` | `refs/heads/main` | Clean (1 intentional untracked) | Primary Trunk | **KEEP** (Protected Root) |
| 02 | `~/.local/state/catpart-parser/stage13-review/baseline-eed27a9` | `eed27a9` | `(detached)` | Clean | Yes (ancestor) | `git worktree remove` |
| 03 | `~/.local/state/catpart-parser/stage13-review/phasea-93f3a85` | `93f3a85` | `(detached)` | Clean | Yes (patch `1517b46b` @ `9d16885`) | `git worktree remove` |
| 04 | `~/.local/state/catpart-parser/stage6-review/checkout` | `c7986bc` | `(detached)` | Clean | Yes (patch `4d61aee9` @ `8cf8192`) | `git worktree remove` |
| 05 | `~/.t3/worktrees/catpart-parser/retro-37-38` | `a17042a` | `retro/37-38-drift-check-gate` | Clean | Yes (patches @ `2d0b88d`, `75efae7`) | `git worktree remove` |
| 06 | `~/.t3/worktrees/catpart-parser/stage11-phaseA` | `b91492a` | `t3/stage11-subnode-phase-a` | Clean | Yes (superseded by `745c07d`) | `git worktree remove` |
| 07 | `~/.t3/worktrees/catpart-parser/t3-122827d8-8357006a1951ecb1` | `2ba08b3` | `t3/stage10-pre-merge-review` | Clean | Yes (patches @ `56877d7`..`8d50469`) | `git worktree remove` |
| 08 | `~/.t3/worktrees/catpart-parser/t3-13e3296c-571fc19b18fab260` | `91e5260` | `(detached)` | Clean | Yes (patch `2eeb1dd1` @ `c2ceba1`) | `git worktree remove` |
| 09 | `~/.t3/worktrees/catpart-parser/t3-1b2c692e-c2a0f0c027cf2167` | `8c87605` | `t3/csv-quoting-debt-repair` | Clean | Yes (patch `d6fced2f` @ `c872ed6`) | `git worktree remove` |
| 10 | `~/.t3/worktrees/catpart-parser/t3-1b341cbe-74b48c00a63685e2` | `03adec3` | `t3/dup-pin-all-unordered-tri-dedup` | Clean | Yes (patches @ `7cfd14f`..`3e0a4f5`) | `git worktree remove` |
| 11 | `~/.t3/worktrees/catpart-parser/t3-21cd2398-85787736433f692a` | `5daa0af` | `(detached)` | Clean | Yes (patch `3c0bf6b2` @ `0fbc5cd`) | `git worktree remove` |
| 12 | `~/.t3/worktrees/catpart-parser/t3-23d9ccc7-bc013191722eecdb` | `7850d67` | `(detached)` | Clean | Yes (rebased/merged @ `0cb0797`) | `git worktree remove` |
| 13 | `~/.t3/worktrees/catpart-parser/t3-2a139776-03e9da6171654fda` | `9c5bad8` | `t3/element-space-beyond-pool` | Clean | Yes (patches @ `c44d8d0`..`3d43f5f`) | `git worktree remove` |
| 14 | `~/.t3/worktrees/catpart-parser/t3-30fdd56e-147b2dd606f40824` | `a96393e` | `(detached)` | Clean | Yes (ancestor) | `git worktree remove` |
| 15 | `~/.t3/worktrees/catpart-parser/t3-377997d0-d2d17cda3f2d026b` | `3ea96a4` | `t3/subnode-index-absorption` | Clean | Yes (patch `411d39d2` @ `745c07d`) | `git worktree remove` |
| 16 | `~/.t3/worktrees/catpart-parser/t3-3a2b4b76-8efd3f410738d489` | `fd7a604` | `t3/retro-phase5-report` | Clean | Yes (DAG merged) | `git worktree remove` |
| 17 | `~/.t3/worktrees/catpart-parser/t3-4a56a786-3cba441b3703e1b2` | `18e5fb1` | `t3/stage15-pre-merge-review` | Clean | Yes (patches @ `1b5bf51`..`3e0a4f5`) | `git worktree remove` |
| 18 | `~/.t3/worktrees/catpart-parser/t3-506d06b2-8aee8a55c39f41b1` | `014005d` | `t3/e0-curve-entry-impl` | Clean | Yes (patches @ `992e2f0`..`8d50469`) | `git worktree remove` |
| 19 | `~/.t3/worktrees/catpart-parser/t3-784f911f-2e28ab51352ce0b4` | `6fc5935` | `t3/dup-pin-all-unordered-dedup` | **DIRTY** (`composite.py`) | Yes (snapshot saved; landed @ `3e0a4f5`) | `git worktree remove --force` |
| 20 | `~/.t3/worktrees/catpart-parser/t3-81e88679-7547f47f440be572` | `a96393e` | `t3/exporter-composite-law-integration` | Clean | Yes (DAG merged) | `git worktree remove` |
| 21 | `~/.t3/worktrees/catpart-parser/t3-99ebfacc-4ea569a1b59e2926` | `2c834c5` | `t3/stage14-pre-merge-review` | Clean | Yes (patches @ `cffbbd4`, `a4fc435`) | `git worktree remove` |
| 22 | `~/.t3/worktrees/catpart-parser/t3-9a46fcbe-1e6486dc3b1d16b8` | `4f982c7` | `t3/stage11-pre-merge-review` | Clean | Yes (patches @ `1e5ef8a`, `745c07d`) | `git worktree remove` |
| 23 | `~/.t3/worktrees/catpart-parser/t3-a0e8d223-9030f98d92655a01` | `d832b86` | `stage-3d-exporter-integration` | Clean | Reconciled & discarded (`53ea4df`) | `git worktree remove` |
| 24 | `~/.t3/worktrees/catpart-parser/t3-a715703f-79294e2f4512396f` | `b330bee` | `(detached)` | Clean | Yes (ancestor) | `git worktree remove` |
| 25 | `~/.t3/worktrees/catpart-parser/t3-a768df7e-aea72b0dfe8f9401` | `934fa6d` | `t3/stage12-pre-merge-review` | Clean | Yes (patches @ `48f45a0`..`ba727e0`) | `git worktree remove` |
| 26 | `~/.t3/worktrees/catpart-parser/t3-a87b7e74-8e5b36faee562080` | `308f587` | `(detached)` | Clean | Yes (patch `c39abd98` @ `93a70c4`) | `git worktree remove` |
| 27 | `~/.t3/worktrees/catpart-parser/t3-b17436de-39720e206564bfea` | `91e5260` | `(detached)` | Clean | Yes (patch `2eeb1dd1` @ `c2ceba1`) | `git worktree remove` |
| 28 | `~/.t3/worktrees/catpart-parser/t3-bee7521f-deebc5b0c8f4d24c` | `15ba3a8` | `t3/empty-mesh-not-manifold` | Clean | Yes (patch `b376f88a` @ `a4fc435`) | `git worktree remove` |
| 29 | `~/.t3/worktrees/catpart-parser/t3-c65d70fe-61b91d84e8f9cb1d` | `48e6b15` | `(detached)` | Clean | Yes (patch `d597df8e` @ `ccd7145`) | `git worktree remove` |
| 30 | `~/.t3/worktrees/catpart-parser/t3-d1311493-6d8c8a5ad5ef1a18` | `dd77a58` | `t3/stage12-noncomposite-failclosed-census` | Clean | Yes (patches @ `ef871b0`..`ba727e0`) | `git worktree remove` |
| 31 | `~/.t3/worktrees/catpart-parser/t3-d67bfa13-eed710a66c5b7c52` | `b255cb9` | `t3/stage-3b-corrections` | Clean | Yes (DAG merged) | `git worktree remove` |
| 32 | `~/.t3/worktrees/catpart-parser/t3-e4707571-bce6f1f1255b5ce5` | `f3531a9` | `t3/p2-5-probe-position-encoding` | Clean | Yes (merged @ `f3531a9`) | `git worktree remove` |
| 33 | `~/.t3/worktrees/catpart-parser/t3-f61986df-765b5b8283a22b5b` | `8cac7e8` | `t3/stage13-pre-merge-review` | Clean | Yes (patches @ `bc1e221`..`3d43f5f`) | `git worktree remove` |

---

## 3. The Residual Patch Snapshot: `t3-784f911f`

### Inspection Details
- **Worktree:** `/home/alan/.t3/worktrees/catpart-parser/t3-784f911f-2e28ab51352ce0b4`
- **Branch:** `t3/dup-pin-all-unordered-dedup`
- **Checked-out Commit:** `6fc5935103` (*"Handoff amendment (cont. 23): OWNER DECISION - land the two measured levers..."*)
- **Dirty State:** `M src/catpart/geometry/composite.py`

### What Was Dirty?
Inspection of the working tree diff in `src/catpart/geometry/composite.py` reveals an early implementation of Stage 15's Lever 1:
- Removed the Stage-10 E0-b coplanarity battery check from `_e0b_dup_pin` so that normal-less and nonplanar dropped curve-entry loops export under the U4-D duplicate-previous weld.
- Updated docstrings for the owner-authorized overturn.
- Crucially, it did **not yet** contain Lever 2 (`_apply_unordered_dedup`) integrated across the four composite exit functions (`decode_composite_store`, `_decode_per_rep`, `_decode_raw_array`, `_decode_mixedwrite`).

The developer then switched to branch `t3/dup-pin-all-unordered-tri-dedup`, completed both levers in commit `8241006` (*"#34 stage-15 implementation: the two owner-authorized measured levers..."*), measured the declared/observed A/B deltas (`270464d`, `03adec3`), completed review (`18e5fb1`), and merged the completed work into `main` at `3e0a4f5`.

### Snapshot Preservation
Per the residual-worktree playbook (`docs/agents/dispatch-recipes.md`), the entire working diff was snapshotted to disk:
```bash
git -C /home/alan/.t3/worktrees/catpart-parser/t3-784f911f-2e28ab51352ce0b4 diff \
  > ~/.local/state/catpart-parser/t3-dup-pin-all-unordered-dedup-residual.patch
```
- **File:** `/home/alan/.local/state/catpart-parser/t3-dup-pin-all-unordered-dedup-residual.patch`
- **Size:** 15,916 bytes (379 lines diff)
- **Status:** Safely preserved. The worktree is now cleared for removal via `git worktree remove --force`.

---

## 4. Complete Local Branch Inventory (52 Branches)

| Branch Name | HEAD SHA | Merged DAG (`origin/main`) | Merged DAG (`main`) | Content Parity with `main` | Attached Worktree | Classification | Disposition |
|---|---|---|---|---|---|---|---|
| `gh-pages` | `e8c0ebc` | No | No | N/A (Orphan deployment branch) | None | **KEEP** | Active deployment branch |
| `main` | `f3531a9` | Ahead 1 | Current | Identical | `/home/alan/Documents/Repos/catpart-parser` | **KEEP** | Active development trunk |
| `retro-reconcile` | `2d0b88d` | Yes | Yes | Identical | None | **DELETE** | `git branch -d` |
| `retro/37-38-drift-check-gate` | `a17042a` | No | No | 100% (patches @ `2d0b88d`, `75efae7`) | `retro-37-38` | **DELETE** | `git branch -D` (after wt) |
| `s2b-91e5260` | `c2ceba1` | Yes | Yes | Identical | None | **DELETE** | `git branch -d` |
| `s3a-7850d67` | `0cb0797` | Yes | Yes | Identical | None | **DELETE** | `git branch -d` |
| `s3b-c1687e4` | `249135b` | Yes | Yes | Identical | None | **DELETE** | `git branch -d` |
| `s3d-ccc7c14` | `1a5c4b4` | Yes | Yes | Identical | None | **DELETE** | `git branch -d` |
| `stage-3d-exporter-integration` | `d832b86` | No | No | Reconciled & discarded (`53ea4df`) | `t3-a0e8d223` | **DELETE/ARCHIVE** | `git branch -D` (after wt) |
| `stage-4a-residue-family` | `ba10b5c` | Yes | Yes | Identical | None | **DELETE** | `git branch -d` |
| `t3/61451b5c` | `94359b0` | Yes | Yes | Identical | None | **DELETE** | `git branch -d` |
| `t3/a87b7e74` | `320f05b` | Yes | Yes | Identical | None | **DELETE** | `git branch -d` |
| `t3/composite-v3-review` | `05e3cab` | Yes | Yes | Identical | None | **DELETE** | `git branch -d` |
| `t3/csv-quoting-debt-repair` | `8c87605` | No | No | 100% (patch @ `c872ed6`) | `t3-1b2c692e` | **DELETE** | `git branch -D` (after wt) |
| `t3/dup-pin-all-unordered-dedup` | `6fc5935` | Yes | Yes | Identical (landed @ `3e0a4f5`) | `t3-784f911f` | **DELETE** | `git branch -d` (after wt) |
| `t3/dup-pin-all-unordered-tri-dedup` | `03adec3` | No | No | 100% (patches @ `7cfd14f`..`3e0a4f5`) | `t3-1b341cbe` | **DELETE** | `git branch -D` (after wt) |
| `t3/e0-curve-entry-impl` | `014005d` | No | No | 100% (patches @ `992e2f0`..`8d50469`) | `t3-506d06b2` | **DELETE** | `git branch -D` (after wt) |
| `t3/element-space-beyond-pool` | `9c5bad8` | No | No | 100% (patches @ `c44d8d0`..`3d43f5f`) | `t3-2a139776` | **DELETE** | `git branch -D` (after wt) |
| `t3/empty-mesh-not-manifold` | `15ba3a8` | No | No | 100% (patch @ `a4fc435`) | `t3-bee7521f` | **DELETE** | `git branch -D` (after wt) |
| `t3/exporter-composite-law-integration` | `a96393e` | Yes | Yes | Identical | `t3-81e88679` | **DELETE** | `git branch -d` (after wt) |
| `t3/exporter-composite-law-integration-1` | `14486db` | Yes | Yes | Identical | None | **DELETE** | `git branch -d` |
| `t3/g6-stage2b-node-streams` | `2d0b88d` | Yes | Yes | Identical | None | **DELETE** | `git branch -d` |
| `t3/integrate-decode-laws-exporter` | `7166b01` | Yes | Yes | Identical | None | **DELETE** | `git branch -d` |
| `t3/integrate-raw-array-decode` | `02e783d` | Yes | Yes | Identical | None | **DELETE** | `git branch -d` |
| `t3/integrate-stage8-locator-artifacts` | `028c5e4` | Yes | Yes | Identical | None | **DELETE** | `git branch -d` |
| `t3/locator-recovery-extension-1` | `14486db` | Yes | Yes | Identical | None | **DELETE** | `git branch -d` |
| `t3/p1-product-census-review` | `b9732be` | Yes | Yes | Identical | None | **DELETE** | `git branch -d` |
| `t3/p2-5-probe-position-encoding` | `f3531a9` | No (in local) | Yes | Identical | `t3-e4707571` | **DELETE** | `git branch -d` (after wt) |
| `t3/p2-pool-pairing-review` | `d1b7016` | Yes | Yes | Identical | None | **DELETE** | `git branch -d` |
| `t3/phase5-viewer-spec-draft` | `6c6b3e8` | Yes | Yes | Identical | None | **DELETE** | `git branch -d` |
| `t3/pin-curve-entry-coordinates` | `c1eb3b1` | Yes | Yes | Identical | None | **DELETE** | `git branch -d` |
| `t3/retro-phase5-report` | `fd7a604` | Yes | Yes | Identical | `t3-3a2b4b76` | **DELETE** | `git branch -d` (after wt) |
| `t3/review-phase-a-52-repro` | `684e0ba` | Yes | Yes | Identical | None | **DELETE** | `git branch -d` |
| `t3/review-stage-2b` | `9903db2` | Yes | Yes | Identical | None | **DELETE** | `git branch -d` |
| `t3/review-ticket-41-v2-geometry-port` | `78e2e8b` | Yes | Yes | Identical | None | **DELETE** | `git branch -d` |
| `t3/review-v1-port-fidelity` | `5ddf194` | Yes | Yes | Identical | None | **DELETE** | `git branch -d` |
| `t3/review-verdict` | `0cb0797` | Yes | Yes | Identical | None | **DELETE** | `git branch -d` |
| `t3/stage-3b-corrections` | `b255cb9` | Yes | Yes | Identical | `t3-d67bfa13` | **DELETE** | `git branch -d` (after wt) |
| `t3/stage-3d-exporter-integration` | `249135b` | Yes | Yes | Identical | None | **DELETE** | `git branch -d` |
| `t3/stage-3d-reconciliation` | `1e754ad` | Yes | Yes | Identical | None | **DELETE** | `git branch -d` |
| `t3/stage-4a-residue-family` | `8fccb45` | Yes | Yes | Identical | None | **DELETE** | `git branch -d` |
| `t3/stage10-land` | `b15e592` | Yes | Yes | Identical | None | **DELETE** | `git branch -d` |
| `t3/stage10-pre-merge-review` | `2ba08b3` | No | No | 100% (patches @ `56877d7`..`8d50469`) | `t3-122827d8` | **DELETE** | `git branch -D` (after wt) |
| `t3/stage11-pre-merge-review` | `4f982c7` | No | No | 100% (patches @ `1e5ef8a`, `745c07d`) | `t3-9a46fcbe` | **DELETE** | `git branch -D` (after wt) |
| `t3/stage11-subnode-phase-a` | `b91492a` | No | No | 100% (superseded by `745c07d`) | `stage11-phaseA` | **DELETE** | `git branch -D` (after wt) |
| `t3/stage12-noncomposite-failclosed-census` | `dd77a58` | No | No | 100% (patches @ `ef871b0`..`ba727e0`) | `t3-d1311493` | **DELETE** | `git branch -D` (after wt) |
| `t3/stage12-pre-merge-review` | `934fa6d` | No | No | 100% (patches @ `48f45a0`..`ba727e0`) | `t3-a768df7e` | **DELETE** | `git branch -D` (after wt) |
| `t3/stage13-pre-merge-review` | `8cac7e8` | No | No | 100% (patches @ `bc1e221`..`3d43f5f`) | `t3-f61986df` | **DELETE** | `git branch -D` (after wt) |
| `t3/stage14-pre-merge-review` | `2c834c5` | No | No | 100% (patches @ `cffbbd4`, `a4fc435`) | `t3-99ebfacc` | **DELETE** | `git branch -D` (after wt) |
| `t3/stage15-pre-merge-review` | `18e5fb1` | No | No | 100% (patches @ `1b5bf51`..`3e0a4f5`) | `t3-4a56a786` | **DELETE** | `git branch -D` (after wt) |
| `t3/subnode-index-absorption` | `3ea96a4` | No | No | 100% (patch @ `745c07d`) | `t3-377997d0` | **DELETE** | `git branch -D` (after wt) |
| `t3/ticket-51-review` | `c1043fb` | Yes | Yes | Identical | None | **DELETE** | `git branch -d` |

---

## 5. Remote Tracking Branch Inventory (17 Remote Branches)

| Remote Ref | HEAD SHA | Merged into `origin/main` | Content Parity with `main` | Historical Role / Purpose | Classification |
|---|---|---|---|---|---|
| `origin/gh-pages` | `e8c0ebc` | No | N/A (independent history) | GitHub Pages live static viewer host | **KEEP** |
| `origin/main` | `8af7ccd` | Yes | 1 behind local `main` | Primary remote trunk | **KEEP** |
| `origin/research/corpus-routes` | `f114f46` | No | Independent (`docs/research/corpus-sources.md`) | Early Wayfinder ticket #2 research (2026-11-06) | **ARCHIVE** (Remote only) |
| `origin/retro/37-38-drift-check-gate` | `a17042a` | No | 100% (landed @ `2d0b88d`, `75efae7`) | Pre-rebase push of ticket #37/#38 gate commits | **DELETE / PRUNE** |
| `origin/stage-3d-exporter-integration` | `d832b86` | No | Reconciled & discarded (`53ea4df`) | Alternate stage-3d walk + plane gate implementation | **DELETE / PRUNE** |
| `origin/stage-4a-residue-family` | `5e5cb0b` | No | 100% (patch identical to local `ba10b5c`) | Pre-rebase push of stage 4a walk-mismatch split | **DELETE / PRUNE** |
| `origin/t3/curve-entry-analysis` | `c1eb3b1` | Yes | Merged | Analysis of curve entry loops (Phase 4) | **DELETE / PRUNE** |
| `origin/t3/e0-curve-entry-impl` | `014005d` | No | 100% (landed @ `992e2f0`..`8d50469`) | Pre-rebase push of stage 10 E0-b implementation | **DELETE / PRUNE** |
| `origin/t3/g6-stage8-mixed-float-68-stores`| `c1eb3b1` | Yes | Merged | Stage 8 mixed float stores analysis | **DELETE / PRUNE** |
| `origin/t3/integrate-decode-laws-exporter` | `ca9e838` | No | 100% (patch identical to local `7166b01`) | Pre-rebase push of stage 5 review fixes | **DELETE / PRUNE** |
| `origin/t3/integrate-raw-array-decode` | `a41844e` | No | 100% (patch identical to local `02e783d`) | Pre-rebase push of stage 6 review N2 pins | **DELETE / PRUNE** |
| `origin/t3/integrate-stage8-locator-artifacts`| `4c0443d` | No | 100% (patch identical to local `028c5e4`) | Pre-rebase push of stage 9 review corrections | **DELETE / PRUNE** |
| `origin/t3/research-multi-part-container-decode`| `c1eb3b1` | Yes | Merged | Multi-part container research | **DELETE / PRUNE** |
| `origin/t3/review-stage-6-integration` | `c1eb3b1` | Yes | Merged | Stage 6 review verdict | **DELETE / PRUNE** |
| `origin/t3/stage-3d-reconciliation` | `959d54c` | No | 100% (patch identical to local `1e754ad`) | Pre-rebase push of stage-3d reconciliation note | **DELETE / PRUNE** |
| `origin/t3/stage5-decode-laws-review` | `c1eb3b1` | Yes | Merged | Stage 5 decode laws review | **DELETE / PRUNE** |
| `origin/t3/stage9-pre-merge-review` | `c1eb3b1` | Yes | Merged | Stage 9 pre-merge review | **DELETE / PRUNE** |

---

## 6. Deep Dive on Unmerged Local Branches (17 Branches)

In Git's DAG, 17 branches appear under `git branch --no-merged main`. The detailed audit below proves that 15 of these are **content-identical** to commits landed on `main`, 1 is **active and intentionally unmerged** (`gh-pages`), and 1 was **explicitly reconciled and discarded** (`stage-3d-exporter-integration`).

### 1. `gh-pages` (`e8c0ebc`)
- **Status:** Unmerged (Orphan root).
- **Purpose:** Published viewer and fitness report deployed static via GitHub Pages (HTTP 200).
- **Classification:** **KEEP** (Protected).

### 2. `retro/37-38-drift-check-gate` (`a17042a`)
- **Commits ahead:** 2 (`ad8c3e2` #37 generic note-figure arithmetic, `a17042a` #38 local merge gate).
- **Parity Proof:** Both commits were cherry-picked/rebased onto `main` as `75efae7` (patch `a48618ca`) and `2d0b88d` (patch `4dee17df`).
- **Classification:** **DELETE** (`git branch -D`).

### 3. `stage-3d-exporter-integration` (`d832b86`)
- **Commits ahead:** 1 (`d832b86` #34 stage-3d walk + identity laws).
- **Parity Proof:** This branch implemented an alternative stage-3d decoder with a strict plane gate. It was independently evaluated against `1a5c4b4` in `docs/agents/stage-3d-reconciliation.md` and commit `53ea4df` explicitly recorded: *"stage-3d reconciliation landed (discard d832b86; fold-ins + A/B regeneration pre-step)"*.
- **Classification:** **DELETE** (`git branch -D`).

### 4. `t3/csv-quoting-debt-repair` (`8c87605`)
- **Commits ahead:** 1 (`8c87605` #34 close sequence CSV-quoting repair).
- **Parity Proof:** Landed on `main` as commit `c872ed6` with identical patch-id `d6fced2f`.
- **Classification:** **DELETE** (`git branch -D`).

### 5. `t3/dup-pin-all-unordered-tri-dedup` (`03adec3`)
- **Commits ahead:** 3 (`8241006` stage-15 implementation, `270464d` declared A/B delta, `03adec3` observed A/B delta).
- **Parity Proof:** All 3 commits landed on `main` as `3e0a4f5`, `f4ffc0c`, and `7cfd14f` with identical patch-ids `50772826`, `264e2011`, and `78680d25`.
- **Classification:** **DELETE** (`git branch -D`).

### 6. `t3/e0-curve-entry-impl` (`014005d`)
- **Commits ahead:** 4 (`49d76ad` E0 recompute, `a34da46` E0-b dup-pin exporter, `97b8cf4` declared delta, `014005d` observed delta).
- **Parity Proof:** All 4 commits landed on `main` as `8d50469`, `95f969f`, `939e1cc`, and `992e2f0` with identical patch-ids.
- **Classification:** **DELETE** (`git branch -D`).

### 7. `t3/element-space-beyond-pool` (`9c5bad8`)
- **Commits ahead:** 5 (`e7546ab` Phase A 1/3, `93f3a85` Phase A 2/3, `c1b5194` Phase B 1/3, `5eaf762` Phase B 2/3, `9c5bad8` wrap-up observed).
- **Parity Proof:** All 5 commits landed on `main` as `3d43f5f`, `9d16885`, `40630ee`, `8eed567`, and `c44d8d0` with identical patch-ids.
- **Classification:** **DELETE** (`git branch -D`).

### 8. `t3/empty-mesh-not-manifold` (`15ba3a8`)
- **Commits ahead:** 1 (`15ba3a8` stage-14 Phase A).
- **Parity Proof:** Landed on `main` as commit `a4fc435` with identical patch-id `b376f88a`.
- **Classification:** **DELETE** (`git branch -D`).

### 9. `t3/stage10-pre-merge-review` (`2ba08b3`)
- **Commits ahead:** 5 (the 4 stage-10 implementation commits + review commit `2ba08b3`).
- **Parity Proof:** All 5 commits landed on `main` (`8d50469`..`56877d7`) with identical patch-ids.
- **Classification:** **DELETE** (`git branch -D`).

### 10. `t3/stage11-pre-merge-review` (`4f982c7`)
- **Commits ahead:** 2 (`3ea96a4` stage-11 Phase A probe, `4f982c7` review verdict MERGE).
- **Parity Proof:** Landed on `main` as `745c07d` and `1e5ef8a` with identical patch-ids.
- **Classification:** **DELETE** (`git branch -D`).

### 11. `t3/stage11-subnode-phase-a` (`b91492a`)
- **Commits ahead:** 1 (`b91492a` early orphan Phase A probe).
- **Parity Proof:** Documented in commit `5e03e74` (*"stage-11 dispatched via delegate_task from the user-woken run... orphan Phase A probe preserved to state, stale shell worktree removed"*). The re-dispatch `3ea96a4` was completed and landed as `745c07d`.
- **Classification:** **DELETE** (`git branch -D`).

### 12. `t3/stage12-noncomposite-failclosed-census` (`dd77a58`)
- **Commits ahead:** 6 (`42132fc` Phase A census, `8b167c6` Phase B locator probe, `5b3faf5` declared delta, `77e8629` provenance fix, `2ed4965` observed A/B, `dd77a58` probe anchor runs).
- **Parity Proof:** All 6 commits landed on `main` as `ba727e0`, `1492458`, `e47dad1`, `0c0689e`, `089809c`, and `ef871b0` with identical patch-ids.
- **Classification:** **DELETE** (`git branch -D`).

### 13. `t3/stage12-pre-merge-review` (`934fa6d`)
- **Commits ahead:** 7 (the 6 stage-12 commits + review commit `934fa6d`).
- **Parity Proof:** All 7 commits landed on `main` (`ba727e0`..`48f45a0`) with identical patch-ids.
- **Classification:** **DELETE** (`git branch -D`).

### 14. `t3/stage13-pre-merge-review` (`8cac7e8`)
- **Commits ahead:** 6 (the 5 stage-13 commits + review commit `8cac7e8`).
- **Parity Proof:** All 6 commits landed on `main` (`3d43f5f`..`bc1e221`) with identical patch-ids.
- **Classification:** **DELETE** (`git branch -D`).

### 15. `t3/stage14-pre-merge-review` (`2c834c5`)
- **Commits ahead:** 2 (`15ba3a8` Phase A, `2c834c5` review verdict MERGE).
- **Parity Proof:** Both commits landed on `main` as `a4fc435` and `cffbbd4` with identical patch-ids.
- **Classification:** **DELETE** (`git branch -D`).

### 16. `t3/stage15-pre-merge-review` (`18e5fb1`)
- **Commits ahead:** 4 (`8241006` implementation, `270464d` declared delta, `03adec3` observed delta, `18e5fb1` review verdict MERGE).
- **Parity Proof:** All 4 commits landed on `main` as `3e0a4f5`, `f4ffc0c`, `7cfd14f`, and `1b5bf51` with identical patch-ids.
- **Classification:** **DELETE** (`git branch -D`).

### 17. `t3/subnode-index-absorption` (`3ea96a4`)
- **Commits ahead:** 1 (`3ea96a4` stage-11 Phase A probe).
- **Parity Proof:** Landed on `main` as commit `745c07d` with identical patch-id `411d39d2`.
- **Classification:** **DELETE** (`git branch -D`).

---

## 7. Cleanup Automation Script Design & Test Results

### Script Specification
- **Path:** [`scripts/triage/cleanup_stale_worktrees.sh`](file:///home/alan/Documents/Repos/catpart-parser/scripts/triage/cleanup_stale_worktrees.sh)
- **Features:**
  - Strict POSIX / bash safety: `set -euo pipefail`.
  - Default execution mode: **DRY-RUN**. Modifying git state requires explicit `--execute`.
  - Primary checkout protection: Invariant check prevents `/home/alan/Documents/Repos/catpart-parser` from ever being targeted.
  - Branch protection: Invariant check prevents `main` and `gh-pages` from ever being deleted.
  - Residual worktree protection: Verifies cleanliness. If tracked modifications exist, verifies that a matching `.patch` file exists in `~/.local/state/catpart-parser/` before permitting removal.
  - Safe symlink handling: Automatically unlinks untracked `corpus` symlinks before calling `git worktree remove`, ensuring standard removal succeeds without needing `--force`.
  - Safe branch deletion: Uses `git branch -d` for DAG-merged branches. Forces `git branch -D` only when `--rebased-branches` AND `--confirm-rebased-delete` are explicitly given.

### Test Execution & Results
1. **Script Dry-Run Verification:**
   ```bash
   ./scripts/triage/cleanup_stale_worktrees.sh --all-safe
   ```
   *Result:* Identified 32 worktrees to remove, 34 merged branches to delete, 0 unintended removals, 0 errors.

2. **Automated Test Suite:**
   - **Path:** [`tests/test_cleanup_stale_worktrees.py`](file:///home/alan/Documents/Repos/catpart-parser/tests/test_cleanup_stale_worktrees.py)
   - Covers: CLI `--help`, default dry-run mode, root-checkout immunity invariant, protected branch immunity invariant, and confirmation-gate enforcement.
   - Run: `pytest tests/test_cleanup_stale_worktrees.py` -> **4 passed in 0.47s**.
   - Ruff lint: `.venv/bin/ruff check tests/test_cleanup_stale_worktrees.py` -> **All checks passed**.

---

## 8. Verification & Execution Instructions

To execute the cleanup safely:

### Step 1: Preview the cleanup
```bash
./scripts/triage/cleanup_stale_worktrees.sh --all-safe
```

### Step 2: Execute safe cleanup (worktrees + DAG-merged branches)
```bash
./scripts/triage/cleanup_stale_worktrees.sh --all-safe --execute
```
*Outcome:* Removes 32 stale worktrees and deletes 34 merged branches via safe `git branch -d`.

### Step 3 (Optional): Delete rebased/landed branches
```bash
./scripts/triage/cleanup_stale_worktrees.sh --rebased-branches --confirm-rebased-delete --execute
```
*Outcome:* Deletes the 16 grind-era branches whose commits were rebased/squashed onto `main`.
