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
  fitness and never reach gh-pages. The badge stays L1 — one headline
  per level (ADR-0001) — even after L2 exists (ticket #33).
- ``fitness-history.json`` — the compact accepted-run trend, oldest to
  newest (run_id, timestamp, L1 Dev scalar; the L2 pass/total scalars
  over the parts-only population ride alongside since ticket #33, null
  for runs emitted before the L2 baseline). An accepted run cannot have
  dropped the Held-out split (no-regret would reject it), so the Dev
  trend is the whole accepted trend.
- ``.nojekyll`` — keep the GitHub Pages URL serving the raw files without
  Jekyll processing; the badge itself reads ``raw.githubusercontent.com``,
  which serves ``.json`` as text/plain — accepted by the shields endpoint
  badge, which requires no particular content type.
- ``site/`` — the GitHub Pages landing page (``index.html`` and friends),
  copied into the tree verbatim — except that any file carrying the
  history token (``/*__FITNESS_HISTORY__*/null``) gets that token
  replaced with the freshly rendered history document, so the page's
  trend charts publish current without a client-side fetch. A missing or
  empty ``site/`` publishes the two JSON files alone (the historical
  shape).

Branch mechanics use git plumbing only (``hash-object`` / ``mktree`` /
``commit-tree`` / ``update-ref``): no worktree, no index checkout, the
current branch and working tree are never touched. The publication commit
is a pure function of the input history and the ``site/`` contents
(author, committer and dates are fixed; the date is the last accepted
run's timestamp), and its message names the run it was rendered from.

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
from datetime import datetime
from pathlib import Path

#: The generated file set of the gh-pages tree; anything else published
#: comes from the repository's ``site/`` landing directory (see the
#: module docstring).
NOJEKYLL_FILENAME = ".nojekyll"
LATEST_FILENAME = "fitness-latest.json"
HISTORY_FILENAME = "fitness-history.json"

#: The landing directory riding along to gh-pages, and the exact token
#: inside ``site/fitness.js`` that is replaced by the fresh history
#: document at publish time (byte-exact, never parsed — a JSON payload
#: may itself contain ``;`` or quotes).
SITE_DIRNAME = "site"
HISTORY_TOKEN = "/*__FITNESS_HISTORY__*/null"

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


def _parse_timestamp(timestamp: str) -> datetime:
    """Parse an ISO-8601 UTC history timestamp (``...Z`` or ``...+00:00``)."""
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PublishError(f"invalid history timestamp {timestamp!r}: {exc}") from exc


def _l2_scalars(row: dict) -> dict | None:
    """The accepted row's validated L2 scalars, or ``None`` before G5.

    The trend JSON carries L2 alongside L1 (ticket #33): pass/total
    counts over the split's kind=part rows, per split. Rows emitted
    before the L2 baseline exist carry ``scalars.L2: null`` and publish
    as a null entry; a malformed L2 object is a hard error, like L1's.
    """
    l2 = row["scalars"].get("L2")
    if l2 is None:
        return None
    if not isinstance(l2, dict):
        raise PublishError(f"accepted run {row['run_id']}: invalid L2 scalars object")
    out: dict[str, dict[str, int]] = {}
    for split in ("dev", "held-out"):
        counts = l2.get(split)
        passed = counts.get("pass") if isinstance(counts, dict) else None
        total = counts.get("total") if isinstance(counts, dict) else None
        if (
            not isinstance(passed, int)
            or isinstance(passed, bool)
            or not isinstance(total, int)
            or isinstance(total, bool)
            or total < 1
            or not 0 <= passed <= total
        ):
            raise PublishError(
                f"accepted run {row['run_id']}: invalid L2 {split} pass/total counts: "
                f"{passed!r}/{total!r}"
            )
        out[split] = {"pass": passed, "total": total}
    return out


def _accepted_runs(rows: list[dict]) -> list[tuple[dict, tuple[int, int], dict | None]]:
    """The accepted rows with their L1 Dev ``(clean, total)`` and validated
    L2 scalars (``None`` before the L2 baseline), in file order.

    File order must be append order (non-decreasing timestamps): the trend
    JSON promises oldest-to-newest, so an out-of-order history is a hard
    error, never a mislabeled publication.
    """
    runs: list[tuple[dict, tuple[int, int], dict | None]] = []
    previous_ts: datetime | None = None
    for row in rows:
        if not row["accepted"]:
            continue
        ts = _parse_timestamp(row["timestamp"])
        if previous_ts is not None and ts < previous_ts:
            raise PublishError(
                f"accepted run {row['run_id']}: timestamp {row['timestamp']!r} is older "
                "than a previous accepted run; the history is not append-ordered"
            )
        previous_ts = ts
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
        runs.append((row, (clean, total), _l2_scalars(row)))
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


def render_latest(runs: list[tuple[dict, tuple[int, int], dict | None]]) -> bytes:
    """The shields.io endpoint JSON: last accepted run's L1 Dev share.

    The badge stays L1 even after L2 exists — one headline per level
    (ADR-0001); the L2 series lives in the trend JSON only.
    """
    row, (clean, total), _l2 = runs[-1]
    pct = _dev_pct(clean, total)
    endpoint = {
        "schemaVersion": 1,
        "label": "L1 clean-parse (Dev)",
        "message": f"{pct:.2f}%",
        "color": _badge_color(pct),
    }
    return (json.dumps(endpoint, separators=(",", ":")) + "\n").encode("utf-8")


def _history_document(runs: list[tuple[dict, tuple[int, int], dict | None]]) -> dict:
    """The trend document (human-readable rendering input), oldest to newest.

    Each run carries the L1 Dev trend and, since ticket #33, its L2
    pass/total scalars over the parts-only population (``null`` for runs
    emitted before the L2 baseline).
    """
    return {
        "schema_version": 1,
        "source": "fitness/history.jsonl",
        "note": (
            "One entry per accepted fitness run (the ADR-0001 no-regret "
            "baseline), oldest to newest; dev is the L1 clean-parse share "
            "and l2 the geometry-sanity share over parts (null before the "
            "L2 baseline exists)."
        ),
        "runs": [
            {
                "run_id": row["run_id"],
                "timestamp": row["timestamp"],
                "dev": {"clean": clean, "total": total, "pct": _dev_pct(clean, total)},
                "l2": None
                if l2 is None
                else {
                    split: {
                        "pass": counts["pass"],
                        "total": counts["total"],
                        "pct": _dev_pct(counts["pass"], counts["total"]),
                    }
                    for split, counts in l2.items()
                },
            }
            for row, (clean, total), l2 in runs
        ],
    }


def render_history(runs: list[tuple[dict, tuple[int, int], dict | None]]) -> bytes:
    """The accepted-run trend JSON, oldest to newest (human-readable)."""
    return (json.dumps(_history_document(runs), indent=2) + "\n").encode("utf-8")


def _files_for(runs: list[tuple[dict, tuple[int, int], dict | None]]) -> dict[str, bytes]:
    return {
        NOJEKYLL_FILENAME: b"",
        LATEST_FILENAME: render_latest(runs),
        HISTORY_FILENAME: render_history(runs),
    }


def render_files(history_path: Path) -> dict[str, bytes]:
    """The exact gh-pages file contents for ``history_path`` (test seam)."""
    return _files_for(_accepted_runs(read_history(history_path)))


def _site_files(repo: Path, runs: list[tuple[dict, tuple[int, int], dict | None]]) -> dict[str, bytes]:
    """The landing-page files under ``repo/site``, with the history injected.

    Every file publishes verbatim except any carrying the exact
    ``HISTORY_TOKEN`` byte sequence: that sequence is replaced with the
    compact rendered history document, so the page's charts publish the
    current accepted-run series without a client-side fetch. The
    replacement is byte-exact — the payload is never parsed, so JSON
    punctuation inside it is inert. A missing or empty ``site/`` yields
    nothing (the historical tree).
    """
    site = repo / SITE_DIRNAME
    if not site.is_dir():
        return {}
    fresh = json.dumps(_history_document(runs), separators=(",", ":")).encode("utf-8")
    token = HISTORY_TOKEN.encode("utf-8")
    files: dict[str, bytes] = {}
    for path in sorted(p for p in site.rglob("*") if p.is_file()):
        rel = path.relative_to(site).as_posix()
        try:
            blob = path.read_bytes()
        except OSError as exc:
            raise PublishError(f"cannot read site file {path}: {exc}") from exc
        if token in blob:
            blob = blob.replace(token, fresh)
        files[rel] = blob
    return files


def build_tree(repo: Path, files: dict[str, bytes]) -> str:
    """Write blobs and build the gh-pages root tree (deterministic).

    Paths may be nested (``assets/x.svg``): the tree is assembled
    bottom-up with ``mktree``, so a subdirectory becomes a subtree.
    """
    blobs: dict[str, str] = {}
    for name in sorted(files):
        blobs[name] = _git(repo, ["hash-object", "-w", "--stdin"], input_bytes=files[name]).strip()

    def mktree(entries: dict) -> str:
        lines = []
        for name in sorted(entries):
            node = entries[name]
            if isinstance(node, dict):
                lines.append(f"040000 tree {mktree(node)}\t{name}")
            else:
                lines.append(f"100644 blob {node}\t{name}")
        return _git(repo, ["mktree"], input_bytes=("\n".join(lines) + "\n").encode("utf-8")).strip()

    root: dict = {}
    for name, blob in blobs.items():
        cursor = root
        for part in name.split("/")[:-1]:
            cursor = cursor.setdefault(part, {})
        cursor[name.split("/")[-1]] = blob
    return mktree(root)


def _commit_tree(repo: Path, tree: str, parent: str | None, last_accepted: dict) -> str:
    """Commit ``tree``; author, committer and date derive from the input."""
    timestamp = last_accepted["timestamp"].replace("Z", "+00:00")
    env = {**os.environ, **COMMIT_IDENT, "GIT_AUTHOR_DATE": timestamp, "GIT_COMMITTER_DATE": timestamp}
    args = ["commit-tree", tree]
    if parent is not None:
        args += ["-p", parent]
    args += ["-m", f"publish fitness artifacts (latest accepted run {last_accepted['run_id']})"]
    return _git(repo, args, env=env).strip()


def _tree_summary(files: dict[str, bytes]) -> str:
    """One console line describing what the tree carries."""
    generated = {NOJEKYLL_FILENAME, LATEST_FILENAME, HISTORY_FILENAME}
    site = sorted(set(files) - generated)
    out = f"{NOJEKYLL_FILENAME}, {LATEST_FILENAME}, {HISTORY_FILENAME}"
    if site:
        out += f", + {len(site)} site file(s)"
    return out


def publish(repo: Path, history_path: Path, remote: str, *, push: bool) -> str:
    """Render, commit and (optionally) force-push ``gh-pages``; returns the head."""
    runs = _accepted_runs(read_history(history_path))
    files = _files_for(runs)
    files.update(_site_files(repo, runs))
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
            # The local tree already matches: only the remote may still be
            # stale (a previous push failed mid-run, or the branch was built
            # with --no-push first). Republish when it differs, so a rerun
            # never leaves the badge reading an older-but-true remote.
            if push and _remote_head(repo, remote) != head:
                _git(repo, ["push", "--force", remote, PUBLISH_BRANCH])
                print(
                    f"republished {PUBLISH_BRANCH} {head} (tree {tree}) to {remote}: "
                    f"{_tree_summary(files)}"
                )
                return head
            print(f"gh-pages is already up to date (tree {tree}); nothing to publish")
            return head

    commit = _commit_tree(repo, tree, head, runs[-1][0])
    _git(repo, ["update-ref", f"refs/heads/{PUBLISH_BRANCH}", commit])
    if push:
        _git(repo, ["push", "--force", remote, PUBLISH_BRANCH])
        print(
            f"published {PUBLISH_BRANCH} {commit} (tree {tree}) to {remote}: "
            f"{_tree_summary(files)}"
        )
    else:
        print(
            f"built {PUBLISH_BRANCH} {commit} (tree {tree}); not pushed (--no-push): "
            f"{_tree_summary(files)}"
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
