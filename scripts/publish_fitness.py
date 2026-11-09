#!/usr/bin/env python3
"""Publish the fitness artifacts to the ``gh-pages`` branch (ADR-0003, ticket #16).

Local-only by decision (ADR-0003): real fitness is measured on the machine
holding ``corpus/`` and GitHub Actions stays light (A5), so publication is
this script run by hand — it is never wired into CI. It reads the committed
append-only ``fitness/history.jsonl``, renders two shields.io-endpoint JSON
files, and rebuilds the ``gh-pages`` branch from exactly those files:

- ``fitness-latest.json`` — the endpoint the README Status badge reads:
  the last ACCEPTED run's L1 Dev clean-parse share. Rejected runs never
  move the accepted baseline (ADR-0001 no-regret rule), so they are not
  fitness and never reach gh-pages.
- ``fitness-history.json`` — the compact accepted-run trend, oldest to
  newest (run_id, timestamp, L1 Dev scalar). An accepted run cannot have
  dropped the Held-out split (no-regret would reject it), so the Dev
  trend is the whole accepted trend.
- ``.nojekyll`` — keep GitHub Pages serving raw paths without Jekyll
  processing; the badge itself reads ``raw.githubusercontent.com``,
  which serves ``.json`` as application/json either way.

Branch mechanics use git plumbing only (``hash-object`` / ``mktree`` /
``commit-tree`` / ``update-ref``): no worktree, no index checkout, the
current branch and working tree are never touched. The publication commit
is a pure function of the input history (author, committer and dates are
fixed; the date is the last accepted run's timestamp), and its message
names the run it was rendered from.

Idempotence: the branch tree is a pure function of the history file —
same input history, byte-identical tree. When the freshly rendered tree
already matches the current ``gh-pages`` head the script is a no-op (no
commit, no push), so rerunning never duplicates rows or files. Changed
content is published as a forced update, which is safe because the branch
holds only generated files.

Usage (from anywhere inside the repository):

    python scripts/publish_fitness.py                # render, commit, push origin
    python scripts/publish_fitness.py --remote URL   # any clone or target path
    python scripts/publish_fitness.py --no-push      # build the local ref only

Exit codes follow the console-script convention: 0 on success (including
the already-up-to-date no-op), 1 on runtime failures, 2 on usage errors.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

#: The exact file set of the gh-pages tree — nothing else is published.
NOJEKYLL_FILENAME = ".nojekyll"
LATEST_FILENAME = "fitness-latest.json"
HISTORY_FILENAME = "fitness-history.json"

#: The publication branch (ADR-0003: gh-pages is the fitness visibility surface).
PUBLISH_BRANCH = "gh-pages"

DEFAULT_REMOTE = "origin"

#: Badge color bands for the L1 Dev clean-parse percentage: accepted
#: increments keep the badge green; a visibly fallen rate reads as a
#: problem without anyone opening the history.
COLOR_GOOD = "brightgreen"
COLOR_MID = "yellow"
COLOR_BAD = "red"

#: Fixed identity of the publication commits (the .invalid domain marks
#: them non-replyable); the commit date comes from the rendered history.
COMMIT_IDENT = {
    "GIT_AUTHOR_NAME": "catpart-parser",
    "GIT_AUTHOR_EMAIL": "fitness@catpart-parser.invalid",
    "GIT_COMMITTER_NAME": "catpart-parser",
    "GIT_COMMITTER_EMAIL": "fitness@catpart-parser.invalid",
}


class PublishError(Exception):
    """Operator-facing failure; :func:`main` prints it and exits 1."""


def _run_git(
    repo: Path,
    args: list[str],
    *,
    input_bytes: bytes | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Run git inside ``repo``, never raising for a nonzero exit."""
    try:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            input=input_bytes,
            capture_output=True,
            env=env,
        )
    except FileNotFoundError as exc:
        raise PublishError("git is not installed; publication needs git") from exc


def _git(
    repo: Path,
    args: list[str],
    *,
    input_bytes: bytes | None = None,
    env: dict[str, str] | None = None,
) -> str:
    """Run git inside ``repo`` and return stdout; a nonzero exit fails closed."""
    proc = _run_git(repo, args, input_bytes=input_bytes, env=env)
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip()
        raise PublishError(f"git {' '.join(args)} failed: {detail}")
    return proc.stdout.decode("utf-8")


def _repo_root() -> Path:
    """The repository containing the working directory."""
    return Path(_git(Path.cwd(), ["rev-parse", "--show-toplevel"]).strip())


def _head_commit(repo: Path, ref: str) -> str | None:
    """Current commit of ``ref``, or ``None`` when the ref does not exist."""
    proc = _run_git(repo, ["rev-parse", "--verify", "--quiet", ref])
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("utf-8").strip()


def _remote_head(repo: Path, remote: str) -> str | None:
    """``gh-pages`` head on ``remote``, or ``None`` when it has none."""
    out = _git(repo, ["ls-remote", remote, f"refs/heads/{PUBLISH_BRANCH}"])
    lines = [line for line in out.splitlines() if line.strip()]
    return lines[0].split()[0] if lines else None


def read_history(history_path: Path) -> list[dict]:
    """Parse the history JSONL, failing closed on any malformed line.

    Structural validation only — the runner owns the committed
    ``fitness-history-row-v0`` schema — but every non-empty line must
    parse and carry what rendering consumes (``run_id``/``timestamp``
    strings, an ``accepted`` boolean, the ``scalars`` object). A corrupt
    line is a hard error, never a skipped row, mirroring
    :func:`catpart.fitness.history.load_last_accepted_row`.
    """
    try:
        text = history_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PublishError(f"cannot read fitness history {history_path}: {exc}") from exc
    rows: list[dict] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        where = f"{history_path}:{lineno}"
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PublishError(f"{where}: history line is not valid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise PublishError(f"{where}: history row is not a JSON object")
        for key, kind in (
            ("run_id", str),
            ("timestamp", str),
            ("accepted", bool),
            ("scalars", dict),
        ):
            if not isinstance(row.get(key), kind):
                raise PublishError(f"{where}: history row has no valid {key!r} field")
        rows.append(row)
    if not rows:
        raise PublishError(f"{history_path}: no history rows")
    return rows


def _accepted_dev(rows: list[dict]) -> list[tuple[dict, tuple[int, int]]]:
    """The accepted rows with their L1 Dev ``(clean, total)``, in file order."""
    runs: list[tuple[dict, tuple[int, int]]] = []
    for row in rows:
        if not row["accepted"]:
            continue
        l1 = row["scalars"].get("L1")
        dev = l1.get("dev") if isinstance(l1, dict) else None
        if not isinstance(dev, dict):
            raise PublishError(f"accepted run {row['run_id']}: no L1 dev scalar to publish")
        clean, total = dev.get("clean"), dev.get("total")
        if (
            not isinstance(clean, int)
            or isinstance(clean, bool)
            or not isinstance(total, int)
            or isinstance(total, bool)
            or total < 1
            or not 0 <= clean <= total
        ):
            raise PublishError(
                f"accepted run {row['run_id']}: invalid L1 dev clean/total counts: "
                f"{clean!r}/{total!r}"
            )
        runs.append((row, (clean, total)))
    if not runs:
        raise PublishError("history has no accepted run; there is no fitness to publish")
    return runs


def _dev_pct(clean: int, total: int) -> float:
    return round(100.0 * clean / total, 2)


def _badge_color(pct: float) -> str:
    if pct >= 99.0:
        return COLOR_GOOD
    if pct >= 90.0:
        return COLOR_MID
    return COLOR_BAD


def render_latest(runs: list[tuple[dict, tuple[int, int]]]) -> bytes:
    """The shields.io endpoint JSON: last accepted run's L1 Dev share."""
    row, (clean, total) = runs[-1]
    pct = _dev_pct(clean, total)
    endpoint = {
        "schemaVersion": 1,
        "label": "L1 clean-parse (Dev)",
        "message": f"{pct:.2f}%",
        "color": _badge_color(pct),
    }
    return (json.dumps(endpoint, separators=(",", ":")) + "\n").encode("utf-8")


def render_history(runs: list[tuple[dict, tuple[int, int]]]) -> bytes:
    """The accepted-run trend JSON, oldest to newest (human-readable)."""
    document = {
        "schema_version": 1,
        "source": "fitness/history.jsonl",
        "note": (
            "One entry per accepted fitness run (the ADR-0001 no-regret "
            "baseline), oldest to newest; pct is the L1 Dev clean-parse share."
        ),
        "runs": [
            {
                "run_id": row["run_id"],
                "timestamp": row["timestamp"],
                "dev": {"clean": clean, "total": total, "pct": _dev_pct(clean, total)},
            }
            for row, (clean, total) in runs
        ],
    }
    return (json.dumps(document, indent=2) + "\n").encode("utf-8")


def _files_for(runs: list[tuple[dict, tuple[int, int]]]) -> dict[str, bytes]:
    return {
        NOJEKYLL_FILENAME: b"",
        LATEST_FILENAME: render_latest(runs),
        HISTORY_FILENAME: render_history(runs),
    }


def render_files(history_path: Path) -> dict[str, bytes]:
    """The exact gh-pages file contents for ``history_path`` (test seam)."""
    return _files_for(_accepted_dev(read_history(history_path)))


def build_tree(repo: Path, files: dict[str, bytes]) -> str:
    """Write blobs and build the gh-pages root tree (deterministic)."""
    entries = []
    for name in sorted(files):
        blob = _git(repo, ["hash-object", "-w", "--stdin"], input_bytes=files[name]).strip()
        entries.append(f"100644 blob {blob}\t{name}")
    return _git(repo, ["mktree"], input_bytes=("\n".join(entries) + "\n").encode("utf-8")).strip()


def _commit_tree(repo: Path, tree: str, parent: str | None, last_accepted: dict) -> str:
    """Commit ``tree``; author, committer and date derive from the input."""
    timestamp = last_accepted["timestamp"].replace("Z", "+00:00")
    env = {**os.environ, **COMMIT_IDENT, "GIT_AUTHOR_DATE": timestamp, "GIT_COMMITTER_DATE": timestamp}
    args = ["commit-tree", tree]
    if parent is not None:
        args += ["-p", parent]
    args += ["-m", f"publish fitness artifacts (latest accepted run {last_accepted['run_id']})"]
    return _git(repo, args, env=env).strip()


def publish(repo: Path, history_path: Path, remote: str, *, push: bool) -> str:
    """Render, commit and (optionally) force-push ``gh-pages``; returns the head."""
    runs = _accepted_dev(read_history(history_path))
    files = _files_for(runs)
    tree = build_tree(repo, files)

    head = _head_commit(repo, f"refs/heads/{PUBLISH_BRANCH}")
    if head is None:
        # First publication from this clone: adopt the remote branch if it
        # has one, so repeat runs keep one publication history instead of
        # force-resetting it from every fresh clone.
        remote_head = _remote_head(repo, remote)
        if remote_head is not None:
            _git(
                repo,
                [
                    "fetch",
                    "--force",
                    remote,
                    f"+refs/heads/{PUBLISH_BRANCH}:refs/heads/{PUBLISH_BRANCH}",
                ],
            )
            head = remote_head
    if head is not None:
        head_tree = _git(repo, ["rev-parse", f"{head}^{{tree}}"]).strip()
        if head_tree == tree:
            print(f"gh-pages is already up to date (tree {tree}); nothing to publish")
            return head

    commit = _commit_tree(repo, tree, head, runs[-1][0])
    _git(repo, ["update-ref", f"refs/heads/{PUBLISH_BRANCH}", commit])
    if push:
        _git(repo, ["push", "--force", remote, PUBLISH_BRANCH])
        print(
            f"published {PUBLISH_BRANCH} {commit} (tree {tree}) to {remote}: "
            f"{NOJEKYLL_FILENAME}, {HISTORY_FILENAME}, {LATEST_FILENAME}"
        )
    else:
        print(
            f"built {PUBLISH_BRANCH} {commit} (tree {tree}); not pushed (--no-push): "
            f"{NOJEKYLL_FILENAME}, {HISTORY_FILENAME}, {LATEST_FILENAME}"
        )
    return commit


def main(argv: list[str] | None = None) -> int:
    """Entry point; returns the process exit code (0 success, 1 failure)."""
    parser = argparse.ArgumentParser(
        prog="publish_fitness.py",
        description=(
            "Publish the fitness artifacts (ADR-0003, ticket #16): read "
            "fitness/history.jsonl, render the shields.io endpoint JSONs "
            "(fitness-latest.json for the README badge, fitness-history.json "
            "for the accepted-run trend) and rebuild + force-push the gh-pages "
            "branch from exactly those files. Local-only by decision: never "
            "run from CI. Idempotent: unchanged history is a no-op."
        ),
    )
    parser.add_argument(
        "--history",
        type=Path,
        default=None,
        help="fitness history JSONL (default: <repository root>/fitness/"
        "history.jsonl; a relative path resolves against the working directory)",
    )
    parser.add_argument(
        "--remote",
        default=DEFAULT_REMOTE,
        help="git remote (name or URL/path) to force-push gh-pages to "
        "(default: origin)",
    )
    parser.add_argument(
        "--no-push",
        action="store_true",
        help="update the local gh-pages ref but skip the push",
    )
    args = parser.parse_args(argv)
    try:
        repo = _repo_root()
        history_path = (
            args.history if args.history is not None else repo / "fitness" / "history.jsonl"
        )
        publish(repo, history_path, args.remote, push=not args.no_push)
    except PublishError as exc:
        print(f"publish_fitness.py: error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
