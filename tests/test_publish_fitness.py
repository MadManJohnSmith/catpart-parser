"""The gh-pages publication script (``scripts/publish_fitness.py``, ticket #16).

Tests treat the script as the unit under test — imported by file path,
because it is a standalone stdlib script, not package code — and assert
on its external contract: the two shields-endpoint JSON files it renders
from a synthetic fitness history, the gh-pages branch it builds with git
plumbing against a scratch bare origin (never the real remote), and the
README badge's consistency with the file the script emits.

The synthetic rows mirror the committed ``fitness/history.jsonl`` shape
(one accepted baseline plus rejected no-regret re-runs), so the fixtures
exercise the same code paths as the real publication.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "publish_fitness.py"


def load_script():
    spec = importlib.util.spec_from_file_location("publish_fitness", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


publish = load_script()


def history_row(
    run_id: str,
    timestamp: str,
    accepted: bool,
    dev: tuple[int, int] = (1745, 1751),
    held_out: tuple[int, int] = (73, 73),
    l2: tuple[int, int, int, int] | None = None,
) -> dict:
    """One synthetic row in the committed fitness-history-row-v0 shape.

    ``l2`` (dev pass/total, held-out pass/total) populates ``scalars.L2``
    in the G5 shape; ``None`` keeps the pre-G5 null.
    """
    if l2 is None:
        l2_scalars = None
    else:
        l2_dev, l2_ho = (l2[0], l2[1]), (l2[2], l2[3])
        l2_scalars = {
            "dev": {"rate": l2_dev[0] / l2_dev[1], "pass": l2_dev[0], "total": l2_dev[1]},
            "held-out": {
                "rate": l2_ho[0] / l2_ho[1],
                "pass": l2_ho[0],
                "total": l2_ho[1],
            },
        }
    return {
        "schema_version": 0,
        "run_id": run_id,
        "timestamp": timestamp,
        "tool_version": "0.1.0",
        "corpus_digest": "a" * 64,
        "accepted": accepted,
        "baseline_run_id": None,
        "no_regret": {
            "dev_rose": None,
            "held_out_fell": None,
            "reason": "baseline: no previous accepted row",
        },
        "scalars": {
            "L1": {
                "dev": {"rate": dev[0] / dev[1], "clean": dev[0], "total": dev[1]},
                "held-out": {
                    "rate": held_out[0] / held_out[1],
                    "clean": held_out[0],
                    "total": held_out[1],
                },
            },
            "L2": l2_scalars,
            "L3": None,
        },
        "report": f"reports/{run_id}.json",
    }


def synthetic_history() -> list[dict]:
    """The committed history's shape: one accepted baseline, two rejections."""
    return [
        history_row("20261107T205256Z-f4fbe7", "2026-11-07T20:52:56Z", True),
        history_row("20261107T205330Z-31eef6", "2026-11-07T20:53:30Z", False),
        history_row("20261108T190649Z-a5daec", "2026-11-08T19:06:49Z", False),
    ]


def write_history(root: Path, rows: list[dict]) -> Path:
    path = root / "fitness" / "history.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


# --- rendering: the two shields-endpoint JSON files -------------------------


def test_latest_endpoint_json_shows_the_last_accepted_run(tmp_path: Path) -> None:
    # Rejected runs never move the accepted baseline (ADR-0001), so the
    # badge reads the last ACCEPTED row, not the last row.
    history = write_history(tmp_path, synthetic_history())
    endpoint = json.loads(publish.render_files(history)[publish.LATEST_FILENAME])
    assert endpoint == {
        "schemaVersion": 1,
        "label": "L1 clean-parse (Dev)",
        "message": "99.66%",
        "color": "brightgreen",
    }


def test_history_json_lists_accepted_runs_oldest_to_newest(tmp_path: Path) -> None:
    history = write_history(
        tmp_path,
        [
            history_row("20261107T205256Z-f4fbe7", "2026-11-07T20:52:56Z", True),
            history_row("20261107T205330Z-31eef6", "2026-11-07T20:53:30Z", False),
            history_row("20261108T190649Z-a5daec", "2026-11-08T19:06:49Z", True, dev=(1749, 1751)),
        ],
    )
    document = json.loads(publish.render_files(history)[publish.HISTORY_FILENAME])
    assert document["schema_version"] == 1
    assert document["source"] == "fitness/history.jsonl"
    assert [run["run_id"] for run in document["runs"]] == [
        "20261107T205256Z-f4fbe7",
        "20261108T190649Z-a5daec",
    ]
    assert [run["timestamp"] for run in document["runs"]] == [
        "2026-11-07T20:52:56Z",
        "2026-11-08T19:06:49Z",
    ]
    assert document["runs"][0]["dev"] == {"clean": 1745, "total": 1751, "pct": 99.66}
    assert document["runs"][1]["dev"] == {"clean": 1749, "total": 1751, "pct": 99.89}


def test_render_is_deterministic(tmp_path: Path) -> None:
    # Idempotence precondition: same input history -> byte-identical files.
    history = write_history(tmp_path, synthetic_history())
    assert publish.render_files(history) == publish.render_files(history)


def test_history_json_carries_the_l2_series_next_to_l1(tmp_path: Path) -> None:
    # Ticket #33: the trend gains the L2 pass/total series per accepted
    # run; pre-G5 rows publish as a null entry. The badge stays L1.
    history = write_history(
        tmp_path,
        [
            history_row("20261107T205256Z-f4fbe7", "2026-11-07T20:52:56Z", True),
            history_row(
                "20261109T100000Z-abcdef",
                "2026-11-09T10:00:00Z",
                True,
                dev=(1749, 1751),
                l2=(1096, 1377, 60, 61),
            ),
        ],
    )
    document = json.loads(publish.render_files(history)[publish.HISTORY_FILENAME])
    assert document["runs"][0]["l2"] is None
    assert document["runs"][1]["l2"] == {
        "dev": {"pass": 1096, "total": 1377, "pct": 79.59},
        "held-out": {"pass": 60, "total": 61, "pct": 98.36},
    }

    endpoint = json.loads(publish.render_files(history)[publish.LATEST_FILENAME])
    assert endpoint["label"] == "L1 clean-parse (Dev)"  # one headline per level


def test_accepted_row_with_bad_l2_counts_fails_closed(tmp_path: Path) -> None:
    row = history_row(
        "20261109T100000Z-abcdef", "2026-11-09T10:00:00Z", True, l2=(2000, 1377, 60, 61)
    )
    history = write_history(tmp_path, [row])
    with pytest.raises(publish.PublishError, match="invalid L2 dev pass/total"):
        publish.render_files(history)


def test_accepted_row_with_malformed_l2_object_fails_closed(tmp_path: Path) -> None:
    row = history_row("20261109T100000Z-abcdef", "2026-11-09T10:00:00Z", True)
    row["scalars"]["L2"] = {"dev": {"clean": 1, "total": 2}}  # L1-shaped, not pass/total
    history = write_history(tmp_path, [row])
    with pytest.raises(publish.PublishError, match="invalid L2 dev pass/total"):
        publish.render_files(history)


def test_badge_color_bands(tmp_path: Path) -> None:
    assert publish._badge_color(99.0) == publish.COLOR_GOOD
    assert publish._badge_color(90.0) == publish.COLOR_MID
    assert publish._badge_color(89.9) == publish.COLOR_BAD


# --- fail-closed behavior ----------------------------------------------------


def test_history_without_accepted_run_fails_closed(tmp_path: Path) -> None:
    history = write_history(
        tmp_path, [history_row("20261107T205330Z-31eef6", "2026-11-07T20:53:30Z", False)]
    )
    with pytest.raises(publish.PublishError, match="no accepted run"):
        publish.render_files(history)


def test_corrupt_history_line_fails_closed(tmp_path: Path) -> None:
    history = write_history(tmp_path, synthetic_history())
    corrupted = history.read_text(encoding="utf-8") + "{not json\n"
    history.write_text(corrupted, encoding="utf-8")
    with pytest.raises(publish.PublishError, match="not valid JSON"):
        publish.render_files(history)


def test_accepted_row_without_dev_scalar_fails_closed(tmp_path: Path) -> None:
    row = history_row("20261107T205256Z-f4fbe7", "2026-11-07T20:52:56Z", True)
    row["scalars"]["L1"] = None  # a future row before L1 exists must not publish
    history = write_history(tmp_path, [row])
    with pytest.raises(publish.PublishError, match="no L1 dev scalar"):
        publish.render_files(history)


def test_accepted_row_with_bad_counts_fails_closed(tmp_path: Path) -> None:
    row = history_row("20261107T205256Z-f4fbe7", "2026-11-07T20:52:56Z", True, dev=(1751, 1750))
    history = write_history(tmp_path, [row])
    with pytest.raises(publish.PublishError, match="invalid L1 dev clean/total"):
        publish.render_files(history)


def test_out_of_order_accepted_timestamps_fail_closed(tmp_path: Path) -> None:
    # The trend JSON promises oldest-to-newest: an append-order violation is
    # a hard error, never a mislabeled publication (A6 review F3).
    history = write_history(
        tmp_path,
        [
            history_row("20261108T190649Z-a5daec", "2026-11-08T19:06:49Z", True, dev=(1748, 1751)),
            history_row("20261107T205256Z-f4fbe7", "2026-11-07T20:52:56Z", True),
        ],
    )
    with pytest.raises(publish.PublishError, match="not append-ordered"):
        publish.render_files(history)


def test_malformed_accepted_timestamp_fails_closed(tmp_path: Path) -> None:
    row = history_row("20261107T205256Z-f4fbe7", "not-a-date", True)
    history = write_history(tmp_path, [row])
    with pytest.raises(publish.PublishError, match="invalid history timestamp"):
        publish.render_files(history)


# --- the badge and the README agree -----------------------------------------


def test_readme_badge_reads_the_emitted_endpoint_file() -> None:
    readme = (SCRIPT_PATH.parents[1] / "README.md").read_text(encoding="utf-8")
    badge_url = (
        "https://raw.githubusercontent.com/MadManJohnSmith/catpart-parser/"
        f"gh-pages/{publish.LATEST_FILENAME}"
    )
    assert f"https://img.shields.io/endpoint?url={badge_url}" in readme
    # The badge lives in the Status section, before the next heading.
    status = readme.split("## Status", 1)[1].split("\n## ", 1)[0]
    assert "img.shields.io/endpoint?url=" in status
    # The one-line local-only doc names the script and the convention.
    assert "scripts/publish_fitness.py" in status
    assert "ADR-0003" in status


# --- the site/ landing page rides along --------------------------------------


def test_site_payload_token_replacement_is_byte_exact(tmp_path: Path) -> None:
    """The token swap touches only the token — no parsing, no spill.

    The committed payload placeholder is null behind a marker comment;
    the rewrite replaces the exact byte sequence, so a rendered history
    whose own strings contain ';' or quotes stays inert, and statements
    around the assignment survive untouched.
    """
    runs = publish._accepted_runs(
        publish.read_history(SCRIPT_PATH.parents[1] / "fitness" / "history.jsonl")
    )
    fresh = json.dumps(publish._history_document(runs), separators=(",", ":"))
    site = tmp_path / publish.SITE_DIRNAME
    site.mkdir()
    (site / "fitness.js").write_text(
        f"x = 1; window.FITNESS_HISTORY = {publish.HISTORY_TOKEN}; y = 2;\n",
        encoding="utf-8",
    )
    text = publish._site_files(tmp_path, runs)["fitness.js"].decode("utf-8")
    assert text == f"x = 1; window.FITNESS_HISTORY = {fresh}; y = 2;\n"
    assert publish.HISTORY_TOKEN not in text


def test_site_file_without_the_token_publishes_verbatim(tmp_path: Path) -> None:
    runs = publish._accepted_runs(
        publish.read_history(SCRIPT_PATH.parents[1] / "fitness" / "history.jsonl")
    )
    site = tmp_path / publish.SITE_DIRNAME
    site.mkdir()
    (site / "about.html").write_text('<p>fresh; quoted "; "</p>\n', encoding="utf-8")
    files = publish._site_files(tmp_path, runs)
    assert files["about.html"] == b'<p>fresh; quoted "; "</p>\n'


# --- the branch: plumbing against a scratch bare origin ----------------------

requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="git is not available")


def run_git(*args: str) -> str:
    proc = subprocess.run(["git", *args], check=True, capture_output=True)
    return proc.stdout.decode("utf-8").strip()


@requires_git
def test_publish_to_scratch_origin_is_idempotent(tmp_path: Path, monkeypatch, capsys) -> None:
    """Two runs over the same history leave a byte-identical branch tree (AC 3).

    The scratch origin is a bare repo under tmp_path and the repo under
    test is a git init under tmp_path — the real remote is never touched.
    """
    origin = tmp_path / "origin.git"
    run_git("init", "--bare", str(origin))
    repo = tmp_path / "repo"
    history = write_history(repo, synthetic_history())
    run_git("init", str(repo))
    monkeypatch.chdir(repo)

    assert publish.main(["--remote", str(origin)]) == 0
    capsys.readouterr()
    head1 = run_git("-C", str(origin), "rev-parse", "refs/heads/gh-pages")
    tree1 = run_git("-C", str(origin), "rev-parse", "refs/heads/gh-pages^{tree}")
    names = run_git("-C", str(origin), "ls-tree", "--name-only", "refs/heads/gh-pages")
    assert sorted(names.splitlines()) == [
        ".nojekyll",
        "fitness-history.json",
        "fitness-latest.json",
    ]
    endpoint = json.loads(
        run_git("-C", str(origin), "show", f"refs/heads/gh-pages:{publish.LATEST_FILENAME}")
    )
    assert endpoint["message"] == "99.66%"

    # Second run over the same history: a no-op — same head, same tree.
    assert publish.main(["--remote", str(origin)]) == 0
    assert "already up to date" in capsys.readouterr().out
    assert run_git("-C", str(origin), "rev-parse", "refs/heads/gh-pages") == head1
    assert run_git("-C", str(origin), "rev-parse", "refs/heads/gh-pages^{tree}") == tree1

    # A newly accepted row changes the tree exactly once — appended to the
    # trend, never duplicated.
    newer = history_row("20261109T100000Z-abcdef", "2026-11-09T10:00:00Z", True, dev=(1748, 1751))
    with history.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(newer, separators=(",", ":")) + "\n")
    assert publish.main(["--remote", str(origin)]) == 0
    capsys.readouterr()
    tree3 = run_git("-C", str(origin), "rev-parse", "refs/heads/gh-pages^{tree}")
    assert tree3 != tree1
    trend = json.loads(
        run_git("-C", str(origin), "show", f"refs/heads/gh-pages:{publish.HISTORY_FILENAME}")
    )
    assert [run["run_id"] for run in trend["runs"]] == [
        "20261107T205256Z-f4fbe7",
        "20261109T100000Z-abcdef",
    ]


@requires_git
def test_fresh_clone_adopts_the_remote_branch(tmp_path: Path, monkeypatch) -> None:
    # A clone without a local gh-pages ref fetches the remote branch as the
    # parent, so repeat runs from fresh clones keep one publication history.
    origin = tmp_path / "origin.git"
    run_git("init", "--bare", str(origin))
    first = tmp_path / "first"
    write_history(first, synthetic_history())
    run_git("init", str(first))
    monkeypatch.chdir(first)
    assert publish.main(["--remote", str(origin)]) == 0
    head1 = run_git("-C", str(origin), "rev-parse", "refs/heads/gh-pages")

    second = tmp_path / "second"
    write_history(second, synthetic_history())
    run_git("init", str(second))
    monkeypatch.chdir(second)
    assert publish.main(["--remote", str(origin)]) == 0
    assert run_git("-C", str(origin), "rev-parse", "refs/heads/gh-pages") == head1


@requires_git
def test_no_push_builds_the_local_ref_only(tmp_path: Path, monkeypatch, capsys) -> None:
    origin = tmp_path / "origin.git"
    run_git("init", "--bare", str(origin))
    repo = tmp_path / "repo"
    write_history(repo, synthetic_history())
    run_git("init", str(repo))
    monkeypatch.chdir(repo)

    assert publish.main(["--remote", str(origin), "--no-push"]) == 0
    assert "not pushed" in capsys.readouterr().out
    # The local ref exists with the rendered tree; the origin stays empty.
    assert len(run_git("ls-remote", str(origin))) == 0
    names = run_git("ls-tree", "--name-only", "refs/heads/gh-pages")
    assert sorted(names.splitlines()) == [
        ".nojekyll",
        "fitness-history.json",
        "fitness-latest.json",
    ]


@requires_git
def test_stale_remote_is_republished_on_a_no_op_run(tmp_path: Path, monkeypatch, capsys) -> None:
    """A local no-op run still syncs a stale remote (A6 review F1).

    A --no-push build followed by a real run must republish the local head
    to the empty/outdated origin instead of reporting up-to-date against
    it — otherwise a failed push could leave the badge stale indefinitely.
    """
    origin = tmp_path / "origin.git"
    run_git("init", "--bare", str(origin))
    repo = tmp_path / "repo"
    write_history(repo, synthetic_history())
    run_git("init", str(repo))
    monkeypatch.chdir(repo)

    # Build locally only: the origin stays empty.
    assert publish.main(["--remote", str(origin), "--no-push"]) == 0
    capsys.readouterr()
    assert len(run_git("ls-remote", str(origin))) == 0

    # The next real run's tree matches the local branch but the remote is
    # stale: the local head is republished, not reported up to date.
    assert publish.main(["--remote", str(origin)]) == 0
    assert "republished" in capsys.readouterr().out
    head = run_git("-C", str(origin), "rev-parse", "refs/heads/gh-pages")
    assert head == run_git("rev-parse", "refs/heads/gh-pages")

    # Once the remote agrees, the same run is a true no-op again.
    assert publish.main(["--remote", str(origin)]) == 0
    assert "already up to date" in capsys.readouterr().out
    assert run_git("-C", str(origin), "rev-parse", "refs/heads/gh-pages") == head


# --- the site/ landing on the branch (needs git plumbing) ---------------------


def write_site(root: Path, fitness_js: str | None = None) -> Path:
    """A minimal landing tree: one root page, one nested asset, the payload."""
    site = root / publish.SITE_DIRNAME
    (site / "assets").mkdir(parents=True, exist_ok=True)
    (site / "fitness.js").write_text(
        fitness_js or f"window.FITNESS_HISTORY = {publish.HISTORY_TOKEN};\n",
        encoding="utf-8",
    )
    (site / "index.html").write_text(
        '<!DOCTYPE html><html><head><script src="fitness.js"></script></head>'
        "<body>landing</body></html>\n",
        encoding="utf-8",
    )
    (site / "assets" / "note.txt").write_text("verbatim asset\n", encoding="utf-8")
    return site


@requires_git
def test_site_landing_publishes_with_fresh_history_payload(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """site/ joins the tree; the history token is replaced with fresh data.

    The null token must not survive publication: it is swapped for the
    freshly rendered history document, while every other site file
    (including nested assets) publishes verbatim.
    """
    origin = tmp_path / "origin.git"
    run_git("init", "--bare", str(origin))
    repo = tmp_path / "repo"
    write_history(repo, synthetic_history())
    write_site(repo)
    run_git("init", str(repo))
    monkeypatch.chdir(repo)

    assert publish.main(["--remote", str(origin)]) == 0
    names = run_git("-C", str(origin), "ls-tree", "-r", "--name-only", "refs/heads/gh-pages")
    assert sorted(names.splitlines()) == [
        ".nojekyll",
        "assets/note.txt",
        "fitness-history.json",
        "fitness-latest.json",
        "fitness.js",
        "index.html",
    ]
    js = run_git("-C", str(origin), "show", "refs/heads/gh-pages:fitness.js")
    assert publish.HISTORY_TOKEN not in js
    payload = json.loads(
        js.split("window.FITNESS_HISTORY = ", 1)[1].strip().rstrip(";")
    )
    # synthetic_history carries one accepted row and two rejections.
    assert [run["run_id"] for run in payload["runs"]] == ["20261107T205256Z-f4fbe7"]
    asset = run_git("-C", str(origin), "show", "refs/heads/gh-pages:assets/note.txt")
    assert asset == "verbatim asset"
    assert "+ 3 site file(s)" in capsys.readouterr().out

    # Same history + same site: a no-op — the injected tree is deterministic.
    assert publish.main(["--remote", str(origin)]) == 0
    assert "already up to date" in capsys.readouterr().out


@requires_git
def test_empty_site_dir_publishes_the_historical_tree(tmp_path: Path, monkeypatch) -> None:
    """An empty site/ is no signal to fail: the three generated files alone."""
    origin = tmp_path / "origin.git"
    run_git("init", "--bare", str(origin))
    repo = tmp_path / "repo"
    write_history(repo, synthetic_history())
    (repo / publish.SITE_DIRNAME).mkdir()
    run_git("init", str(repo))
    monkeypatch.chdir(repo)

    assert publish.main(["--remote", str(origin)]) == 0
    names = run_git("-C", str(origin), "ls-tree", "--name-only", "refs/heads/gh-pages")
    assert sorted(names.splitlines()) == [
        ".nojekyll",
        "fitness-history.json",
        "fitness-latest.json",
    ]
