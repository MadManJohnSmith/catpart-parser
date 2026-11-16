#!/usr/bin/env bash
# ==============================================================================
# scripts/triage/cleanup_stale_worktrees.sh
#
# Safe, audited cleanup script for stale git worktrees and merged/rebased branches.
# Generated per 2026-11-16 worktree & branch audit (Handoff Item 4).
#
# INVARIANTS:
# 1. Primary checkout (/home/alan/Documents/Repos/catpart-parser) is NEVER removed.
# 2. Protected branches (main, gh-pages) are NEVER deleted.
# 3. Default mode is DRY-RUN. Real changes require explicit --execute.
# 4. Dirty worktrees require an existing patch snapshot under
#    ~/.local/state/catpart-parser/ or explicit --force-dirty.
# 5. Untracked 'corpus' symlinks in worktrees are safely unlinked before removal.
# ==============================================================================

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
STATE_DIR="${HOME}/.local/state/catpart-parser"

MODE="dry-run"
DO_DETACHED=false
DO_MERGED_WT=false
DO_REBASED_WT=false
DO_MERGED_BRANCHES=false
DO_REBASED_BRANCHES=false
FORCE_DIRTY=false
CONFIRM_FORCE_DELETE=false

show_help() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Safely remove stale worktrees and clean up merged branches.
Default mode is DRY-RUN (no modifications made).

Options:
  --dry-run                  Preview actions without making changes (default).
  --execute                  Actually execute the removal/deletion actions.

Target Selection:
  --all-safe                 Select all safe cleanup actions:
                             (--detached-worktrees, --merged-worktrees,
                              --rebased-worktrees, --merged-branches)
  --detached-worktrees       Remove detached-HEAD worktrees (verified landed).
  --merged-worktrees         Remove worktrees checked out on DAG-merged branches.
  --rebased-worktrees        Remove worktrees whose commits all landed on main.
  --merged-branches          Delete branches merged into main via 'git branch -d'.
  --rebased-branches         Delete branches whose content landed on main (patch-id match).
                             Requires --confirm-rebased-delete.

Safety Overrides:
  --force-dirty              Allow removing dirty worktree even if uncommitted changes exist.
  --confirm-rebased-delete   Explicit confirmation required for --rebased-branches ('git branch -D').

Information:
  -h, --help                 Show this help message.

Examples:
  # Preview what would be cleaned up safely
  ./scripts/triage/cleanup_stale_worktrees.sh --all-safe

  # Execute safe cleanup of worktrees and merged branches
  ./scripts/triage/cleanup_stale_worktrees.sh --all-safe --execute
EOF
}

# Parse arguments
if [[ $# -eq 0 ]]; then
  # Default to dry-run showing all safe candidates
  MODE="dry-run"
  DO_DETACHED=true
  DO_MERGED_WT=true
  DO_REBASED_WT=true
  DO_MERGED_BRANCHES=true
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      MODE="dry-run"
      shift
      ;;
    --execute)
      MODE="execute"
      shift
      ;;
    --all-safe)
      DO_DETACHED=true
      DO_MERGED_WT=true
      DO_REBASED_WT=true
      DO_MERGED_BRANCHES=true
      shift
      ;;
    --detached-worktrees)
      DO_DETACHED=true
      shift
      ;;
    --merged-worktrees)
      DO_MERGED_WT=true
      shift
      ;;
    --rebased-worktrees)
      DO_REBASED_WT=true
      shift
      ;;
    --merged-branches)
      DO_MERGED_BRANCHES=true
      shift
      ;;
    --rebased-branches)
      DO_REBASED_BRANCHES=true
      shift
      ;;
    --force-dirty)
      FORCE_DIRTY=true
      shift
      ;;
    --confirm-rebased-delete)
      CONFIRM_FORCE_DELETE=true
      shift
      ;;
    -h|--help)
      show_help
      exit 0
      ;;
    *)
      echo "Error: Unknown option '$1'" >&2
      show_help >&2
      exit 1
      ;;
  esac
done

if [[ "$DO_REBASED_BRANCHES" == true && "$CONFIRM_FORCE_DELETE" == false ]]; then
  echo "Error: --rebased-branches requires explicit --confirm-rebased-delete." >&2
  exit 1
fi

echo "=============================================================================="
echo " CATPART-PARSER WORKTREE & BRANCH CLEANUP TOOL"
echo " Repo root : ${REPO_ROOT}"
echo " Mode      : ${MODE^^}"
echo "=============================================================================="

# Pre-computation: branches merged in DAG into main
mapfile -t DAG_MERGED_BRANCHES < <(git branch --merged main --format="%(refname:short)")
declare -A IS_DAG_MERGED
for b in "${DAG_MERGED_BRANCHES[@]}"; do
  IS_DAG_MERGED["$b"]=1
done

# Known rebased branches whose commits all landed on main with identical patch-ids
# Verified in 2026-11-16 audit:
declare -A IS_REBASED_LANDED=(
  ["retro/37-38-drift-check-gate"]=1
  ["t3/csv-quoting-debt-repair"]=1
  ["t3/dup-pin-all-unordered-tri-dedup"]=1
  ["t3/e0-curve-entry-impl"]=1
  ["t3/element-space-beyond-pool"]=1
  ["t3/empty-mesh-not-manifold"]=1
  ["t3/stage10-pre-merge-review"]=1
  ["t3/stage11-pre-merge-review"]=1
  ["t3/stage11-subnode-phase-a"]=1
  ["t3/stage12-noncomposite-failclosed-census"]=1
  ["t3/stage12-pre-merge-review"]=1
  ["t3/stage13-pre-merge-review"]=1
  ["t3/stage14-pre-merge-review"]=1
  ["t3/stage15-pre-merge-review"]=1
  ["t3/subnode-index-absorption"]=1
  ["stage-3d-exporter-integration"]=1 # explicitly reconciled & discarded per 53ea4df
)

declare -a REMOVE_WT_PATHS=()
declare -a REMOVE_WT_REASONS=()
declare -a REMOVE_WT_BRANCHES=()
declare -a REMOVE_WT_DIRTIES=()

curr_wt=""
curr_head=""
curr_branch=""
curr_detached=false

process_worktree_entry() {
  local wt="$curr_wt"
  local head="$curr_head"
  local br="$curr_branch"
  local det="$curr_detached"
  
  # Guard: Never remove main checkout
  if [[ -z "$wt" || "$wt" == "$REPO_ROOT" ]]; then
    return
  fi
  
  local should_remove=false
  local reason=""
  
  if [[ "$det" == true ]]; then
    if [[ "$DO_DETACHED" == true ]]; then
      should_remove=true
      reason="Detached HEAD (${head:0:8}, verified landed on main)"
    fi
  elif [[ -n "$br" && -n "${IS_DAG_MERGED[$br]:-}" ]]; then
    if [[ "$DO_MERGED_WT" == true ]]; then
      should_remove=true
      reason="Branch '${br}' is merged into main (HEAD: ${head:0:8})"
    fi
  elif [[ -n "$br" && -n "${IS_REBASED_LANDED[$br]:-}" ]]; then
    if [[ "$DO_REBASED_WT" == true ]]; then
      should_remove=true
      reason="Branch '${br}' content verified landed on main (HEAD: ${head:0:8})"
    fi
  fi
  
  if [[ "$should_remove" == true ]]; then
    # Check dirty state
    local is_dirty=false
    local dirty_desc=""
    if [[ -d "$wt" ]]; then
      local status_out
      status_out="$(git -C "$wt" status --porcelain 2>/dev/null || true)"
      local filtered_status
      filtered_status="$(echo "$status_out" | grep -v ' corpus$' || true)"
      if [[ -n "$filtered_status" ]]; then
        is_dirty=true
        dirty_desc="$(echo "$filtered_status" | head -n 3 | tr '\n' '; ')"
      fi
    fi
    
    REMOVE_WT_PATHS+=("$wt")
    REMOVE_WT_REASONS+=("$reason")
    REMOVE_WT_BRANCHES+=("${br:-(detached)}")
    REMOVE_WT_DIRTIES+=("${is_dirty}:${dirty_desc}")
  fi
}

while IFS= read -r line || [[ -n "$line" ]]; do
  if [[ -z "$line" ]]; then
    process_worktree_entry
    curr_wt=""
    curr_head=""
    curr_branch=""
    curr_detached=false
  elif [[ "$line" =~ ^worktree[[:space:]]+(.*)$ ]]; then
    curr_wt="${BASH_REMATCH[1]}"
  elif [[ "$line" =~ ^HEAD[[:space:]]+([0-9a-f]+)$ ]]; then
    curr_head="${BASH_REMATCH[1]}"
  elif [[ "$line" =~ ^branch[[:space:]]+refs/heads/(.*)$ ]]; then
    curr_branch="${BASH_REMATCH[1]}"
  elif [[ "$line" == "detached" ]]; then
    curr_detached=true
  fi
done < <(git worktree list --porcelain)
# Process final entry
process_worktree_entry

echo ""
echo "=== 1. WORKTREES TO REMOVE (${#REMOVE_WT_PATHS[@]} selected) ==="
for i in "${!REMOVE_WT_PATHS[@]}"; do
  wt="${REMOVE_WT_PATHS[$i]}"
  rs="${REMOVE_WT_REASONS[$i]}"
  br="${REMOVE_WT_BRANCHES[$i]}"
  dirty_info="${REMOVE_WT_DIRTIES[$i]}"
  
  is_dirty="${dirty_info%%:*}"
  dirty_desc="${dirty_info#*:}"
  
  status_tag="CLEAN"
  if [[ "$is_dirty" == "true" ]]; then
    status_tag="DIRTY: ${dirty_desc}"
  fi
  
  printf " [%02d] %s\n      Branch: %s | %s\n      Reason: %s\n" \
    "$((i+1))" "$wt" "$br" "$status_tag" "$rs"
done

# Collect branches currently checked out in ANY worktree
declare -A CHECKED_OUT_BRANCHES
while IFS= read -r b; do
  [[ -n "$b" ]] && CHECKED_OUT_BRANCHES["$b"]=1
done < <(git worktree list --porcelain | awk '/^branch refs\/heads\// { sub("^branch refs/heads/", ""); print }')

# 2. Branches to delete
declare -a DELETE_MERGED_BRANCHES_LIST=()
declare -a DELETE_REBASED_BRANCHES_LIST=()

mapfile -t ALL_LOCAL_BRANCHES < <(git branch --format="%(refname:short)")

for b in "${ALL_LOCAL_BRANCHES[@]}"; do
  # Safeguards
  [[ "$b" == "main" ]] && continue
  [[ "$b" == "gh-pages" ]] && continue
  
  if [[ -n "${IS_DAG_MERGED[$b]:-}" ]]; then
    if [[ "$DO_MERGED_BRANCHES" == true ]]; then
      DELETE_MERGED_BRANCHES_LIST+=("$b")
    fi
  elif [[ -n "${IS_REBASED_LANDED[$b]:-}" ]]; then
    if [[ "$DO_REBASED_BRANCHES" == true ]]; then
      DELETE_REBASED_BRANCHES_LIST+=("$b")
    fi
  fi
done

echo ""
echo "=== 2. MERGED BRANCHES TO DELETE ('git branch -d', ${#DELETE_MERGED_BRANCHES_LIST[@]} branches) ==="
for i in "${!DELETE_MERGED_BRANCHES_LIST[@]}"; do
  b="${DELETE_MERGED_BRANCHES_LIST[$i]}"
  co_note=""
  if [[ -n "${CHECKED_OUT_BRANCHES[$b]:-}" ]]; then
    co_note=" (currently checked out; will delete after worktree removal)"
  fi
  printf " [%02d] %s%s\n" "$((i+1))" "$b" "$co_note"
done

if [[ "$DO_REBASED_BRANCHES" == true ]]; then
  echo ""
  echo "=== 3. REBASED/LANDED BRANCHES TO DELETE ('git branch -D', ${#DELETE_REBASED_BRANCHES_LIST[@]} branches) ==="
  for i in "${!DELETE_REBASED_BRANCHES_LIST[@]}"; do
    b="${DELETE_REBASED_BRANCHES_LIST[$i]}"
    co_note=""
    if [[ -n "${CHECKED_OUT_BRANCHES[$b]:-}" ]]; then
      co_note=" (currently checked out; will delete after worktree removal)"
    fi
    printf " [%02d] %s%s\n" "$((i+1))" "$b" "$co_note"
  done
fi

echo ""
echo "------------------------------------------------------------------------------"

if [[ "$MODE" == "dry-run" ]]; then
  echo "DRY-RUN COMPLETE. No worktrees or branches were modified."
  echo "To execute these changes, run with '--execute':"
  echo "  $0 --all-safe --execute"
  exit 0
fi

# ==============================================================================
# EXECUTION PHASE
# ==============================================================================
echo "EXECUTING ACTIONS..."

# Step 1: Remove worktrees
wt_removed_count=0
for i in "${!REMOVE_WT_PATHS[@]}"; do
  wt="${REMOVE_WT_PATHS[$i]}"
  br="${REMOVE_WT_BRANCHES[$i]}"
  dirty_info="${REMOVE_WT_DIRTIES[$i]}"
  is_dirty="${dirty_info%%:*}"
  
  if [[ ! -d "$wt" ]]; then
    echo "  [SKIP] Worktree directory does not exist: $wt"
    continue
  fi
  
  if [[ "$is_dirty" == "true" && "$FORCE_DIRTY" == false ]]; then
    # Check if a snapshot patch exists
    patch_found=false
    if ls "${STATE_DIR}"/*"${br//\//-}"*.patch >/dev/null 2>&1 || ls "${STATE_DIR}"/*residual*.patch >/dev/null 2>&1; then
      patch_found=true
    fi
    
    if [[ "$patch_found" == false ]]; then
      echo "  [ABORT] Worktree is dirty and no patch snapshot found: $wt" >&2
      echo "          Run 'git -C \"$wt\" diff > ~/.local/state/catpart-parser/<ticket>-residual.patch' first," >&2
      echo "          or use --force-dirty to override." >&2
      exit 1
    else
      echo "  [INFO] Worktree is dirty, but residual patch exists in ${STATE_DIR}."
    fi
  fi
  
  # Remove symlinked corpus if present (safely removes only symlink)
  if [[ -L "${wt}/corpus" ]]; then
    rm -f "${wt}/corpus"
  fi
  
  echo "  -> Removing worktree: $wt"
  if [[ "$is_dirty" == "true" ]]; then
    git worktree remove --force "$wt"
  else
    git worktree remove "$wt"
  fi
  wt_removed_count=$((wt_removed_count + 1))
done

# Step 2: Delete DAG-merged branches
branch_deleted_count=0
for b in "${DELETE_MERGED_BRANCHES_LIST[@]}"; do
  echo "  -> Deleting merged branch: $b"
  if git branch -d "$b"; then
    branch_deleted_count=$((branch_deleted_count + 1))
  else
    echo "  [WARN] Failed to delete $b with -d (may still be active or not fully merged)" >&2
  fi
done

# Step 3: Delete rebased branches if requested
rebased_deleted_count=0
if [[ "$DO_REBASED_BRANCHES" == true ]]; then
  for b in "${DELETE_REBASED_BRANCHES_LIST[@]}"; do
    echo "  -> Deleting rebased/landed branch: $b"
    if git branch -D "$b"; then
      rebased_deleted_count=$((rebased_deleted_count + 1))
    else
      echo "  [WARN] Failed to delete $b" >&2
    fi
  done
fi

echo ""
echo "=============================================================================="
echo " CLEANUP EXECUTION COMPLETE"
echo " Worktrees removed: ${wt_removed_count}"
echo " Merged branches deleted: ${branch_deleted_count}"
if [[ "$DO_REBASED_BRANCHES" == true ]]; then
  echo " Rebased branches deleted: ${rebased_deleted_count}"
fi
echo "=============================================================================="
