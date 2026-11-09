"""Seam 2 (Spec A #8, ticket #14): the ``catpart-fitness`` report/history JSON.

Tests assert only on the runner's external contract, mirroring how the
real corpus run is consumed: the history row JSON, the report JSON it
references, and the append-only ``fitness/history.jsonl`` file. The
schema files ``fitness-report-v0.json`` and ``fitness-history-row-v0.json``
are the authority for "valid", exactly as ``v0.json`` is for
``catpart-inspect`` output.

Every test builds a tiny fixture manifest plus a synthetic mini-corpus
under ``tmp_path`` (the real corpus is gitignored and absent in CI, and
the A2 fixture generator is a later ticket). Files use the
``conftest.build_catpart`` shapes; the manifest mirrors the real
``manifests/corpus-manifest.csv`` column layout with the fixture files'
real SHA-256 digests.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

import pytest

from catpart.fitness import LevelScore, SplitScore, evaluate_no_regret
from catpart.schema import load_schema
from catpart.schema.validate import ValidationError, validate

MANIFEST_COLUMNS = (
    "sha256",
    "kind",
    "size_bytes",
    "split",
    "reported_version",
    "detected_version",
    "repo",
    "path",
    "local_path",
    "source_url",
    "copies",
    "magic_ok",
)


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def manifest_row(name: str, split: str, data: bytes) -> dict[str, str]:
    """One manifest row in the real corpus-manifest.csv column layout."""
    return {
        "sha256": sha256_of(data),
        "kind": "part",
        "size_bytes": str(len(data)),
        "split": split,
        "reported_version": "",
        "detected_version": "unknown",
        "repo": "fixture/repo",
        "path": f"parts/{name}.CATPart",
        "local_path": f"corpus/fixture/parts/{name}.CATPart",
        "source_url": f"https://example.invalid/fixture/{name}",
        "copies": "1",
        "magic_ok": "yes",
    }


def write_manifest(root: Path, rows: list[dict[str, str]]) -> Path:
    """Write ``rows`` as the repo-layout manifest ``<root>/manifests/corpus-manifest.csv``.

    The two-level layout matters: the runner derives the repository root
    (and with it the default fitness directory and corpus root) from the
    manifest's ``manifests/`` parent, exactly as it does for the real
    manifest.
    """
    manifest_dir = root / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "corpus-manifest.csv"
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(MANIFEST_COLUMNS))
    writer.writeheader()
    writer.writerows(rows)
    manifest_path.write_text(buffer.getvalue(), encoding="utf-8")
    return manifest_path


def digest_of_manifest(manifest_path: Path) -> str:
    return hashlib.sha256(manifest_path.read_bytes()).hexdigest()


def history_lines(root: Path) -> list[dict]:
    """Parsed rows of ``<root>/fitness/history.jsonl``."""
    text = (root / "fitness" / "history.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def run_fitness_cli(tmp_path: Path, capsys, argv: list[str] | None = None) -> tuple[int, str, str]:
    """Invoke the ``catpart-fitness`` entry point in-process against the fixture repo."""
    from catpart.cli import main_fitness

    args = argv if argv is not None else ["--manifest", str(tmp_path / "manifests" / "corpus-manifest.csv")]
    code = main_fitness(list(args))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def main_fitness_quiet(capsys) -> tuple[int, str, str]:
    """Invoke ``catpart-fitness`` with no arguments (default paths)."""
    from catpart.cli import main_fitness

    code = main_fitness([])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def clean_bytes(build_catpart, **kwargs) -> bytes:
    """Bytes of a fixture file that parses clean under the v1 invariants.

    The v1 invariants (``catpart.fitness.invariants``) need the header
    dword below the file size, the V5_CFV2 magic, and - when the file
    ends with CB__END\\0, as the fixture does - the law-H1 chain and the
    trailer constants; the conftest fixture builds all of that
    structurally genuine. The conftest default dword (0x10000) exceeds
    these ~2 KB fixtures, so clean fixtures use a corpus-plausible 1024.
    """
    kwargs.setdefault("header_dword", 1024)
    return build_catpart(**kwargs)


# --- slice 1: first run writes the report and exactly one baseline row -----


def test_first_run_writes_report_and_single_baseline_row(
    tmp_path: Path, build_catpart, capsys
) -> None:
    manifest_path, _ = write_mini_corpus(tmp_path, build_catpart)

    code, out, err = run_fitness_cli(tmp_path, capsys)
    assert code == 0, err

    row = json.loads(out)
    validate(row, load_schema("fitness-history-row-v0"))

    lines = (tmp_path / "fitness" / "history.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == row

    report_path = tmp_path / "fitness" / row["report"]
    assert report_path.is_file()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    validate(report, load_schema("fitness-report-v0"))

    assert row["corpus_digest"] == digest_of_manifest(manifest_path)
    assert row["accepted"] is True
    assert row["baseline_run_id"] is None
    assert row["no_regret"] == {
        "dev_rose": None,
        "held_out_fell": None,
        "reason": "baseline: no previous accepted row",
    }
    assert row["scalars"]["L1"]["dev"] == {"rate": 2 / 3, "clean": 2, "total": 3}
    assert row["scalars"]["L1"]["held-out"] == {"rate": 1.0, "clean": 2, "total": 2}
    assert row["scalars"]["L2"] is None
    assert row["scalars"]["L3"] is None


# --- slices 2-3: classification vocabulary and per-split aggregation ------


def write_mini_corpus(tmp_path: Path, build_catpart) -> tuple[Path, dict[str, bytes]]:
    """The standard fixture corpus: 2 clean dev, 1 crash dev, 2 clean held-out.

    Returns the manifest path and the file contents by name, so tests can
    rewrite fixture files between runs to simulate a parser change while
    the manifest (and with it the corpus digest) stays fixed.
    """
    files = {
        "dev-a": ("dev", clean_bytes(build_catpart)),
        "dev-b": (
            "dev",
            clean_bytes(
                build_catpart,
                records=(("CATPrtCont", "CATProdCont"),),
                payload=b"\x01\x02\x03\x04" * 8,
            ),
        ),
        "dev-crash": ("dev", b"V5_CFV2\x00"),  # shorter than the 32-byte header
        "ho-a": ("held-out", clean_bytes(build_catpart, payload=b"\xab\xcd\xef\x01" * 8)),
        "ho-b": (
            "held-out",
            # A product-like table: every with-table corpus file names
            # CATPrtCont (part) or CATProdCont/CATMechProdCont (product)
            # - kind law K1 - so a table with neither would not be clean.
            clean_bytes(build_catpart, records=(("CATProdCont", "CATFeatCont"),)),
        ),
    }
    rows = [manifest_row(name, split, data) for name, (split, data) in files.items()]
    for name, (_, data) in files.items():
        target = tmp_path / "corpus" / "fixture" / "parts" / f"{name}.CATPart"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return write_manifest(tmp_path, rows), dict(files)


def test_report_classifies_clean_and_crash_files(
    tmp_path: Path, build_catpart, capsys
) -> None:
    manifest_path, _ = write_mini_corpus(tmp_path, build_catpart)
    code, out, err = run_fitness_cli(tmp_path, capsys)
    assert code == 0, err

    report = json.loads(
        (tmp_path / "fitness" / json.loads(out)["report"]).read_text(encoding="utf-8")
    )
    by_sha = {record["sha256"]: record for record in report["files"]}
    assert len(by_sha) == 5

    clean = by_sha[sha256_of(clean_bytes(build_catpart))]
    assert clean["classification"] == "clean"
    assert clean["error"] is None
    assert clean["detected_version"] == "V5R21SP0HF0"
    assert clean["container_names"][0] == "CATPrtCont"
    assert clean["kind"] == "part"
    assert clean["path"] == "parts/dev-a.CATPart"
    assert clean["split"] == "dev"

    crash = by_sha[sha256_of(b"V5_CFV2\x00")]
    assert crash["classification"] == "crash"
    assert crash["error"] == (
        "ValueError: not a CATIA V5 container: header needs 32 bytes, got 8"
    )
    assert crash["detected_version"] is None
    assert crash["container_names"] is None


def test_row_and_report_carry_the_inspect_schema_version(
    tmp_path: Path, build_catpart, capsys
) -> None:
    # Spec C: "the schema version is part of every output document and
    # every history row". The row's own schema_version names the row
    # format (fitness-history-row-v0); inspect_schema_version names the
    # catpart-inspect contract the run validated against (v1 as of C1).
    write_mini_corpus(tmp_path, build_catpart)
    code, out, err = run_fitness_cli(tmp_path, capsys)
    assert code == 0, err
    row = json.loads(out)
    assert row["inspect_schema_version"] == 1
    report = json.loads(
        (tmp_path / "fitness" / row["report"]).read_text(encoding="utf-8")
    )
    assert report["inspect_schema_version"] == 1


def test_missing_invariant_classification(tmp_path: Path, build_catpart, capsys) -> None:
    # The conftest default header dword (0x10000 = 65536) exceeds the ~2 KB
    # fixture size, violating the one evidenced v0 invariant
    # (header-dword-below-file-size): schema-valid output, but not clean.
    data = build_catpart()
    held_out = clean_bytes(build_catpart, payload=b"\x09\x0a\x0b\x0c" * 8)
    rows = [manifest_row("bad-dword", "dev", data), manifest_row("ho-ok", "held-out", held_out)]
    parts = tmp_path / "corpus" / "fixture" / "parts"
    parts.mkdir(parents=True, exist_ok=True)
    (parts / "bad-dword.CATPart").write_bytes(data)
    (parts / "ho-ok.CATPart").write_bytes(held_out)
    write_manifest(tmp_path, rows)

    code, out, err = run_fitness_cli(tmp_path, capsys)
    assert code == 0, err
    report = json.loads(
        (tmp_path / "fitness" / json.loads(out)["report"]).read_text(encoding="utf-8")
    )
    record = report["files"][0]
    assert record["classification"] == "missing-invariant"
    assert record["error"] == (
        "header-dword-below-file-size: header_dword 65536 is not below file_size "
        f"{len(data)}"
    )
    assert record["container_names"] is not None  # the parse itself succeeded
    assert report["splits"]["dev"]["missing-invariant"] == 1
    assert report["splits"]["dev"]["rate"] == 0.0


def test_schema_invalid_classification(tmp_path: Path, build_catpart, capsys, monkeypatch) -> None:
    # A parser regression that emits a schema-violating report (here:
    # the kind field missing from a v1 report). The committed validator
    # is the authority for this classification, so the fake output is
    # validated exactly like real output.
    write_mini_corpus(tmp_path, build_catpart)

    def broken_inspect(path):
        return {
            "schema_version": 1,
            "magic": "V5_CFV2",
            "header_dword": 1024,
            "header_dword12": 1024,
            "ff8_at_16_24": True,
            "header_dword16": None,
            "header_dword20": None,
            "file_size": 2048,
            "detected_version": "unknown",
            "containers": [],
            "trailer": None,
            # kind missing -> violates schema v1
        }

    monkeypatch.setattr("catpart.fitness.runner.build_inspect_report", broken_inspect)
    code, out, err = run_fitness_cli(tmp_path, capsys)
    assert code == 0, err
    report = json.loads(
        (tmp_path / "fitness" / json.loads(out)["report"]).read_text(encoding="utf-8")
    )
    classifications = {record["classification"] for record in report["files"]}
    assert classifications == {"schema-invalid"}
    assert all("kind" in record["error"] for record in report["files"])
    assert report["splits"]["dev"]["schema-invalid"] == 3
    assert report["totals"]["schema-invalid"] == 5


def test_unavailable_file_counts_against_rate(tmp_path: Path, build_catpart, capsys) -> None:
    manifest_path, files = write_mini_corpus(tmp_path, build_catpart)
    # Remove one clean dev file from disk without touching the manifest:
    # the row stays in the corpus denominator as not clean.
    missing = tmp_path / "corpus" / "fixture" / "parts" / "dev-a.CATPart"
    missing.unlink()

    code, out, err = run_fitness_cli(tmp_path, capsys)
    assert code == 0, err
    report = json.loads(
        (tmp_path / "fitness" / json.loads(out)["report"]).read_text(encoding="utf-8")
    )
    unavailable = [
        record for record in report["files"] if record["classification"] == "unavailable"
    ]
    assert len(unavailable) == 1
    assert unavailable[0]["path"] == "parts/dev-a.CATPart"
    assert "missing on disk" in unavailable[0]["error"]
    assert report["splits"]["dev"] == {
        "files": 3,
        "available": 2,
        "unavailable": 1,
        "clean": 1,
        "schema-invalid": 0,
        "crash": 1,
        "missing-invariant": 0,
        "rate": 1 / 3,
    }
    assert report["totals"]["files"] == 5
    assert report["totals"]["available"] == 4
    assert report["totals"]["clean"] == 3


# --- slice 4: append-only history, one row per run -------------------------


def test_second_run_appends_exactly_one_row_and_never_rewrites(
    tmp_path: Path, build_catpart, capsys
) -> None:
    manifest_path, _ = write_mini_corpus(tmp_path, build_catpart)
    code1, out1, err1 = run_fitness_cli(tmp_path, capsys)
    assert code1 == 0, err1
    first_row = json.loads(out1)
    assert first_row["accepted"] is True

    history_path = tmp_path / "fitness" / "history.jsonl"
    history_after_first = history_path.read_text(encoding="utf-8")

    # Same corpus, same parser: the Dev rate does not rise, so the run is
    # rejected — but it is still recorded, exactly one more row.
    code2, out2, err2 = run_fitness_cli(tmp_path, capsys)
    assert code2 == 0, err2
    second_row = json.loads(out2)

    lines = history_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert lines[0] == history_after_first.splitlines()[0]  # byte-identical
    assert second_row["run_id"] != first_row["run_id"]
    assert second_row["accepted"] is False
    assert second_row["baseline_run_id"] == first_row["run_id"]
    assert second_row["no_regret"] == {
        "dev_rose": False,
        "held_out_fell": False,
        "reason": "dev did not rise",
    }
    assert history_path.read_text(encoding="utf-8") == "\n".join(lines) + "\n"


def test_no_regret_flags_dev_rise_with_held_out_fall_as_rejected(
    tmp_path: Path, build_catpart, capsys
) -> None:
    manifest_path, _ = write_mini_corpus(tmp_path, build_catpart)
    code1, out1, err1 = run_fitness_cli(tmp_path, capsys)
    assert code1 == 0, err1
    first_row = json.loads(out1)
    assert first_row["scalars"]["L1"]["dev"] == {"rate": 2 / 3, "clean": 2, "total": 3}
    assert first_row["scalars"]["L1"]["held-out"] == {"rate": 1.0, "clean": 2, "total": 2}

    parts = tmp_path / "corpus" / "fixture" / "parts"
    # Simulate a parser change (the manifest, and with it the corpus
    # digest, stays fixed): every dev file now parses clean, while one
    # held-out file no longer parses at all.
    (parts / "dev-crash.CATPart").write_bytes(
        clean_bytes(build_catpart, payload=b"\x11\x22\x33\x44" * 8)
    )
    (parts / "ho-a.CATPart").write_bytes(b"V5_CFV2\x00")

    code2, out2, err2 = run_fitness_cli(tmp_path, capsys)
    assert code2 == 0, err2
    second_row = json.loads(out2)
    assert second_row["scalars"]["L1"]["dev"] == {"rate": 1.0, "clean": 3, "total": 3}
    assert second_row["scalars"]["L1"]["held-out"] == {"rate": 0.5, "clean": 1, "total": 2}
    assert second_row["accepted"] is False
    assert second_row["no_regret"] == {
        "dev_rose": True,
        "held_out_fell": True,
        "reason": "held-out fell",
    }


def test_accepted_when_dev_rises_and_held_out_stable(
    tmp_path: Path, build_catpart, capsys
) -> None:
    manifest_path, _ = write_mini_corpus(tmp_path, build_catpart)
    code1, out1, err1 = run_fitness_cli(tmp_path, capsys)
    assert code1 == 0, err1

    (tmp_path / "corpus" / "fixture" / "parts" / "dev-crash.CATPart").write_bytes(
        clean_bytes(build_catpart, payload=b"\x11\x22\x33\x44" * 8)
    )
    code2, out2, err2 = run_fitness_cli(tmp_path, capsys)
    assert code2 == 0, err2
    second_row = json.loads(out2)
    assert second_row["accepted"] is True
    assert second_row["no_regret"] == {
        "dev_rose": True,
        "held_out_fell": False,
        "reason": "dev rose and held-out did not fall",
    }
    assert second_row["baseline_run_id"] == json.loads(out1)["run_id"]


def test_dev_fall_is_rejected(tmp_path: Path, build_catpart, capsys) -> None:
    manifest_path, _ = write_mini_corpus(tmp_path, build_catpart)
    code1, out1, err1 = run_fitness_cli(tmp_path, capsys)
    assert code1 == 0, err1

    (tmp_path / "corpus" / "fixture" / "parts" / "dev-a.CATPart").write_bytes(
        b"V5_CFV2\x00"
    )
    code2, out2, err2 = run_fitness_cli(tmp_path, capsys)
    assert code2 == 0, err2
    second_row = json.loads(out2)
    assert second_row["accepted"] is False
    assert second_row["no_regret"]["dev_rose"] is False
    assert second_row["no_regret"]["held_out_fell"] is False


# --- slice 5: the baseline is the last ACCEPTED row ------------------------


def test_comparison_targets_the_last_accepted_row(
    tmp_path: Path, build_catpart, capsys
) -> None:
    manifest_path, _ = write_mini_corpus(tmp_path, build_catpart)
    _, out1, _ = run_fitness_cli(tmp_path, capsys)
    baseline_row = json.loads(out1)

    # Run 2 (rejected): one dev file stops parsing.
    (tmp_path / "corpus" / "fixture" / "parts" / "dev-a.CATPart").write_bytes(b"V5_CFV2\x00")
    _, out2, _ = run_fitness_cli(tmp_path, capsys)
    assert json.loads(out2)["accepted"] is False

    # Run 3: the dev file is back to its run-1 state. Compared against the
    # last ACCEPTED row (run 1: dev 2/3), not against rejected run 2
    # (dev 1/3): equal dev does not rise, so run 3 is rejected too.
    (tmp_path / "corpus" / "fixture" / "parts" / "dev-a.CATPart").write_bytes(
        build_catpart(header_dword=1024)
    )
    _, out3, _ = run_fitness_cli(tmp_path, capsys)
    third_row = json.loads(out3)
    assert third_row["accepted"] is False
    assert third_row["baseline_run_id"] == baseline_row["run_id"]
    assert third_row["no_regret"]["dev_rose"] is False


# --- slice 6: a corpus change voids the comparison -------------------------


def test_corpus_digest_change_voids_comparison(
    tmp_path: Path, build_catpart, capsys
) -> None:
    manifest_path, _ = write_mini_corpus(tmp_path, build_catpart)
    _, out1, _ = run_fitness_cli(tmp_path, capsys)
    first_row = json.loads(out1)
    assert first_row["accepted"] is True

    # Add a dev file and its manifest row: the manifest bytes change, so
    # the corpus digest changes and no comparison against run 1 is valid.
    added = clean_bytes(build_catpart, payload=b"\x55\x66\x77\x88" * 8)
    target = tmp_path / "corpus" / "fixture" / "parts" / "dev-added.CATPart"
    target.write_bytes(added)

    text = manifest_path.read_text(encoding="utf-8")
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(MANIFEST_COLUMNS))
    writer.writeheader()
    for row in csv.DictReader(io.StringIO(text)):
        writer.writerow(row)
    writer.writerow(manifest_row("dev-added", "dev", added))
    manifest_path.write_text(buffer.getvalue(), encoding="utf-8")

    _, out2, _ = run_fitness_cli(tmp_path, capsys)
    second_row = json.loads(out2)
    assert second_row["accepted"] is True
    assert second_row["baseline_run_id"] == first_row["run_id"]
    assert second_row["no_regret"] == {
        "dev_rose": None,
        "held_out_fell": None,
        "reason": "baseline: previous accepted row has a different corpus digest",
    }


# --- the no-regret helper itself (ticket #14 names it directly) ------------


def level_scores(dev: tuple[int, int], held_out: tuple[int, int]) -> dict:
    return {
        "L1": LevelScore(
            dev=SplitScore(*dev),
            held_out=SplitScore(*held_out),
        ),
        "L2": None,
        "L3": None,
    }


def test_helper_flags_dev_rise_with_held_out_fall_as_rejected() -> None:
    verdict = evaluate_no_regret(
        level_scores((2, 3), (2, 2)),
        level_scores((3, 3), (1, 2)),
    )
    assert verdict.accepted is False
    assert verdict.dev_rose is True
    assert verdict.held_out_fell is True


def test_helper_accepts_dev_rise_with_held_out_stable() -> None:
    verdict = evaluate_no_regret(
        level_scores((2, 3), (2, 2)),
        level_scores((3, 3), (2, 2)),
    )
    assert verdict.accepted is True
    assert verdict.reason == "dev rose and held-out did not fall"


def test_helper_rejects_dev_equal_even_when_held_out_rises() -> None:
    # ADR-0001: accepted only if Dev rises. Equal Dev is not an increment.
    verdict = evaluate_no_regret(
        level_scores((2, 3), (1, 2)),
        level_scores((2, 3), (2, 2)),
    )
    assert verdict.accepted is False
    assert verdict.dev_rose is False
    assert verdict.held_out_fell is False


def test_helper_rejects_dev_fall_with_held_out_fall() -> None:
    verdict = evaluate_no_regret(
        level_scores((2, 3), (2, 2)),
        level_scores((1, 3), (1, 2)),
    )
    assert verdict.accepted is False
    assert verdict.reason == "dev did not rise and held-out fell"


def test_helper_compares_exact_fractions_not_floats() -> None:
    # 10^17 / (3 x 10^17) and (10^17 + 1) / (3 x 10^17) tie as floats but
    # differ as exact fractions; the verdict must see the rise.
    baseline_dev = SplitScore(10**17, 3 * 10**17)
    current_dev = SplitScore(10**17 + 1, 3 * 10**17)
    assert baseline_dev.rate == current_dev.rate  # float rates tie
    verdict = evaluate_no_regret(
        level_scores((10**17, 3 * 10**17), (1, 1)),
        level_scores((10**17 + 1, 3 * 10**17), (1, 1)),
    )
    assert verdict.accepted is True
    assert verdict.dev_rose is True


def test_helper_requires_a_comparable_level() -> None:
    with pytest.raises(ValueError):
        evaluate_no_regret(
            {"L1": None, "L2": None, "L3": None},
            level_scores((1, 1), (1, 1)),
        )


# --- slice 7: fail-closed behavior ------------------------------------------


def test_corrupt_history_fails_closed_and_is_never_rewritten(
    tmp_path: Path, build_catpart, capsys
) -> None:
    manifest_path, _ = write_mini_corpus(tmp_path, build_catpart)
    _, out1, _ = run_fitness_cli(tmp_path, capsys)
    history_path = tmp_path / "fitness" / "history.jsonl"
    corrupted = history_path.read_text(encoding="utf-8") + "{not json\n"
    history_path.write_text(corrupted, encoding="utf-8")

    code, out, err = run_fitness_cli(tmp_path, capsys)
    assert code == 1
    assert out == ""
    assert "history" in err
    assert "catpart-fitness: error:" in err
    # Fail closed: the corrupt file is left untouched, no row appended.
    assert history_path.read_text(encoding="utf-8") == corrupted


def test_history_row_violating_schema_fails_closed(
    tmp_path: Path, build_catpart, capsys
) -> None:
    manifest_path, _ = write_mini_corpus(tmp_path, build_catpart)
    _, out1, _ = run_fitness_cli(tmp_path, capsys)
    history_path = tmp_path / "fitness" / "history.jsonl"
    rows = history_path.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(rows[0])
    tampered["accepted"] = "yes"  # not a boolean
    history_path.write_text(json.dumps(tampered) + "\n", encoding="utf-8")

    code, out, err = run_fitness_cli(tmp_path, capsys)
    assert code == 1
    assert "fitness-history-row-v0" in err


def test_unknown_split_value_fails_closed(tmp_path: Path, build_catpart, capsys) -> None:
    data = clean_bytes(build_catpart)
    rows = [manifest_row("only", "training", data)]  # not dev / held-out
    write_manifest(tmp_path, rows)
    target = tmp_path / "corpus" / "fixture" / "parts" / "only.CATPart"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)

    code, out, err = run_fitness_cli(tmp_path, capsys)
    assert code == 1
    assert out == ""
    assert "unknown split 'training'" in err


def test_duplicate_sha256_fails_closed(tmp_path: Path, build_catpart, capsys) -> None:
    data = clean_bytes(build_catpart)
    same = manifest_row("a", "dev", data)
    twin = manifest_row("b", "held-out", data)  # identical bytes, different path
    write_manifest(tmp_path, [same, twin])
    parts = tmp_path / "corpus" / "fixture" / "parts"
    parts.mkdir(parents=True, exist_ok=True)
    (parts / "a.CATPart").write_bytes(data)
    (parts / "b.CATPart").write_bytes(data)

    code, out, err = run_fitness_cli(tmp_path, capsys)
    assert code == 1
    assert "duplicate sha256" in err


def test_empty_split_fails_closed(tmp_path: Path, build_catpart, capsys) -> None:
    data = clean_bytes(build_catpart)
    write_manifest(tmp_path, [manifest_row("only-dev", "dev", data)])
    parts = tmp_path / "corpus" / "fixture" / "parts"
    parts.mkdir(parents=True, exist_ok=True)
    (parts / "only-dev.CATPart").write_bytes(data)

    code, out, err = run_fitness_cli(tmp_path, capsys)
    assert code == 1
    assert "held-out" in err


def test_missing_manifest_fails_closed(tmp_path: Path, capsys) -> None:
    code, out, err = run_fitness_cli(tmp_path, capsys)
    assert code == 1
    assert out == ""
    assert "cannot read corpus manifest" in err


def test_default_paths_resolve_from_the_working_directory(
    tmp_path: Path, build_catpart, capsys, monkeypatch
) -> None:
    write_mini_corpus(tmp_path, build_catpart)
    monkeypatch.chdir(tmp_path)
    code, out, err = main_fitness_quiet(capsys)
    assert code == 0, err
    assert (tmp_path / "fitness" / "history.jsonl").is_file()
    assert json.loads(out)["accepted"] is True


# --- schema pins: the committed contracts reject malformed artifacts -------


VALID_ROW = {
    "schema_version": 0,
    "run_id": "20261107T120000Z-abc123",
    "timestamp": "2026-11-07T12:00:00Z",
    "tool_version": "0.1.0",
    "corpus_digest": "a" * 64,
    "accepted": True,
    "baseline_run_id": None,
    "no_regret": {"dev_rose": None, "held_out_fell": None, "reason": "baseline: no previous accepted row"},
    "scalars": {
        "L1": {
            "dev": {"rate": 0.5, "clean": 1, "total": 2},
            "held-out": {"rate": 1.0, "clean": 1, "total": 1},
        },
        "L2": None,
        "L3": None,
    },
    "report": "reports/20261107T120000Z-abc123.json",
}


def test_valid_history_row_schema_shape() -> None:
    validate(VALID_ROW, load_schema("fitness-history-row-v0"))


@pytest.mark.parametrize(
    "mutation",
    [
        lambda r: {**r, "accepted": "yes"},
        lambda r: {**r, "corpus_digest": "A" * 64},  # uppercase not allowed
        lambda r: {**r, "run_id": "20261107T120000Z"},  # missing hex suffix
        lambda r: {**r, "timestamp": "2026-11-07 12:00:00"},
        lambda r: {**r, "scalars": {**r["scalars"], "L1": {**r["scalars"]["L1"], "dev": {"rate": 1.5, "clean": 3, "total": 2}}}},
        lambda r: {**r, "scalars": {**r["scalars"], "L2": {"dev": {}}}},  # not null
        lambda r: {k: v for k, v in r.items() if k != "corpus_digest"},
        lambda r: {**r, "no_regret": {"dev_rose": None, "reason": "..."}},  # missing held_out_fell
        lambda r: {**r, "baseline_run_id": 12},
    ],
)
def test_history_row_schema_rejects_malformed_rows(mutation) -> None:
    with pytest.raises(ValidationError):
        validate(mutation(VALID_ROW), load_schema("fitness-history-row-v0"))


def test_future_fields_accepted_additively() -> None:
    # Evolution rule (schema/__init__.py): additive changes keep the version.
    validate({**VALID_ROW, "notes": "accepted by session 42"}, load_schema("fitness-history-row-v0"))


def test_inspect_schema_version_field_on_row_schema() -> None:
    # C1 adds inspect_schema_version additively to the v0 row shape.
    validate({**VALID_ROW, "inspect_schema_version": 1}, load_schema("fitness-history-row-v0"))


def test_report_schema_rejects_unknown_classification() -> None:
    with pytest.raises(ValidationError):
        validate(
            {
                "schema_version": 0,
                "run_id": "20261107T120000Z-abc123",
                "timestamp": "2026-11-07T12:00:00Z",
                "tool_version": "0.1.0",
                "manifest_path": "manifests/corpus-manifest.csv",
                "corpus_digest": "a" * 64,
                "splits": {},
                "totals": {},
                "scalars": {},
                "accepted": True,
                "baseline_run_id": None,
                "no_regret": {"dev_rose": None, "held_out_fell": None, "reason": "x"},
                "files": [
                    {
                        "sha256": "b" * 64,
                        "path": "x.CATPart",
                        "split": "dev",
                        "classification": "bogus",
                        "detected_version": None,
                        "container_names": None,
                        "error": None,
                    }
                ],
            },
            load_schema("fitness-report-v0"),
        )
