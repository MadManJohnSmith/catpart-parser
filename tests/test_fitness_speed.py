"""The fitness fast-path's tests (marathon W7, speed oracle).

Two pinned contracts, both measured against the real seams:

1. **Engine parity** — the native engines (``rust``/``fast``) classify
   and gate-score every A2 fixture variant exactly as the ``python``
   engine does: same classification vocabulary, same detected_version,
   same kind, same full L2 record. Error ``detail`` prose is excluded
   (the never-compared-bite-wise rule, spec §3.2). The parity pins run
   through :func:`catpart.fitness.speed.compare_sweep_csvs` — the same
   comparator the sweep CLI ships — and through :func:`run_fitness`
   on the same mini manifest, both engines, scalar-for-scalar.

2. **The cache and the streaming sweep** — a cache hit skips both
   seams but not the digest (it is the key); a changed code digest
   invalidates every entry; the CSV on disk is a prefix-complete view
   of the run at any instant (rows flushed per file).

The port-binary pins need the release ``fidelity-cli`` (built on
demand, the ``scripts/fidelity_run.py::build_port_bin`` convention);
when cargo cannot provide it they skip LOUDLY with the build command
in the skip reason — never silently.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from catpart.fitness.runner import FitnessError, run_fitness
from catpart.fitness.speed import (
    CodeCache,
    ENGINE_PYTHON,
    collect_files,
    code_digest,
    compare_sweep_csvs,
    engine_seams,
    file_sha256,
    resolve_port_binary,
    run_sweep,
)
from fixtures_gen import CORRUPTED_VARIANTS, VALID_VARIANTS, build_catpart, build_fixture
from test_fitness_runner import write_mini_corpus


def _port_bin_or_skip() -> Path:
    """The release port binary, built on demand — or a LOUD skip."""
    try:
        return resolve_port_binary(build_if_missing=True)
    except FileNotFoundError as exc:
        pytest.skip(
            "port release binary unavailable (build it with "
            "`cargo build --release --locked` in port/): " + str(exc)
        )


def _write_variant_dir(tmp_path: Path) -> Path:
    """Every A2 variant on disk, one file per variant (canonical named
    for the ``None`` variant), for the engine-parity sweeps."""
    root = tmp_path / "variants"
    root.mkdir()
    for variant in (*VALID_VARIANTS, *CORRUPTED_VARIANTS):
        name = "canonical" if variant is None else variant
        (root / f"{name}.CATPart").write_bytes(build_fixture(variant=variant))
    return root


def _run_sweep_to(root: Path, engine: str, tmp_path: Path, cache_path: Path | None = None):
    """A full sweep (L2 on) over ``root`` with ``engine``, rows in CSV."""
    out_csv = tmp_path / f"sweep-{engine}.csv"
    port_bin = None if engine == ENGINE_PYTHON else resolve_port_binary()
    summary = run_sweep(
        collect_files(root),
        engine=engine,
        port_bin=port_bin,
        out_csv=out_csv,
        cache_path=cache_path,
    )
    return summary, out_csv


# --- resolution and digests -------------------------------------------------


def test_port_binary_override_wins(tmp_path: Path, monkeypatch) -> None:
    binary = tmp_path / "fidelity-cli"
    binary.write_bytes(b"fake binary")
    monkeypatch.setenv("CATPART_PORT_BIN", str(binary))
    assert resolve_port_binary() == binary
    monkeypatch.setenv("CATPART_PORT_BIN", str(tmp_path / "missing"))
    with pytest.raises(FileNotFoundError, match="CATPART_PORT_BIN"):
        resolve_port_binary()


def test_engine_seams_python_pair_is_the_runner_seams() -> None:
    from catpart.fitness.runner import _classify_file, _measure_l2

    classify, measure = engine_seams(ENGINE_PYTHON)
    assert classify is _classify_file
    assert measure is _measure_l2


def test_code_digest_binds_sources_and_binary(tmp_path: Path) -> None:
    binary = tmp_path / "fidelity-cli"
    binary.write_bytes(b"one build")
    first = code_digest(binary)
    assert first == code_digest(binary), "same inputs -> same digest"
    binary.write_bytes(b"a different build")
    assert code_digest(binary) != first, "a rebuilt decoder must invalidate the cache"


def test_file_sha256_matches_hashlib(tmp_path: Path) -> None:
    import hashlib

    data = tmp_path / "blob"
    data.write_bytes(b"x" * (1 << 20) + b"tail")  # spans the chunk boundary
    assert file_sha256(data) == hashlib.sha256(data.read_bytes()).hexdigest()


# --- the streaming sweep (engine python: no port binary needed) --------------


def test_sweep_rows_and_summary_python_engine(tmp_path: Path) -> None:
    root = _write_variant_dir(tmp_path)
    # A deterministic three-file population: two parseable variants and
    # the short-file crash.
    files = [
        root / "canonical.CATPart",
        root / "dual-region.CATPart",
        root / "short-file.CATPart",
    ]
    out_csv = tmp_path / "sweep-python.csv"
    summary = run_sweep(files, engine=ENGINE_PYTHON, out_csv=out_csv)
    with out_csv.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 3
    assert [row["sha256"] for row in rows] == [file_sha256(f) for f in files]
    classifications = {row["path"].split("/")[-1]: row["classification"] for row in rows}
    assert classifications["short-file.CATPart"] == "crash"
    assert classifications["canonical.CATPart"] == "clean"
    assert summary["classifications"]["clean"] == 2
    assert summary["classifications"]["crash"] == 1
    # The python engine IS the equivalence reference: no cache, no
    # digest (nothing native to bind), every file runs the real seams.
    assert summary["cache_hits"] == 0 and summary["cache_misses"] == 0
    assert summary["peak_rss_parent_mib"] > 0
    assert summary["code_digest"] is None


def test_streaming_csv_is_prefix_complete(tmp_path: Path, monkeypatch) -> None:
    """Kill the sweep mid-run: the CSV on disk holds exactly the rows
    already processed (one file in flight, rows flushed per file)."""
    root = _write_variant_dir(tmp_path)
    files = [
        root / "canonical.CATPart",
        root / "dual-region.CATPart",
        root / "short-file.CATPart",
    ]
    out_csv = tmp_path / "sweep-killed.csv"
    real_seams = engine_seams(ENGINE_PYTHON)
    classify = real_seams[0]

    def measure_that_dies(file_path, out_path):
        if file_path.name == "dual-region.CATPart":
            raise RuntimeError("simulated harness death")
        from catpart.fitness.runner import _measure_l2

        return _measure_l2(file_path, out_path)

    def fake_seams(engine, port_bin=None):
        assert engine == ENGINE_PYTHON
        return classify, measure_that_dies

    monkeypatch.setattr("catpart.fitness.speed.engine_seams", fake_seams)
    with pytest.raises(RuntimeError, match="simulated harness death"):
        run_sweep(files, engine=ENGINE_PYTHON, out_csv=out_csv)
    with out_csv.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert [row["path"].split("/")[-1] for row in rows] == ["canonical.CATPart"]


def test_collect_files_is_a_sorted_prefix(tmp_path: Path) -> None:
    root = _write_variant_dir(tmp_path)
    every = collect_files(root)
    assert every == sorted(every)
    assert collect_files(root, limit=5) == every[:5]


# --- the incremental cache ---------------------------------------------------


def test_cache_hit_skips_seams_not_the_digest(tmp_path: Path, monkeypatch) -> None:
    """A warm cache answers from records; a changed code digest (a
    rebuilt binary, a changed gate) starts every entry over."""
    root = _write_variant_dir(tmp_path)
    files = [root / "canonical.CATPart", root / "short-file.CATPart"]
    port_bin = _port_bin_or_skip()
    cache_path = tmp_path / "cache.jsonl"

    calls = {"l2": 0}
    real_seams = engine_seams("fast", port_bin)

    def counting_measure(file_path, out_path):
        calls["l2"] += 1
        return real_seams[1](file_path, out_path)

    monkeypatch.setattr(
        "catpart.fitness.speed.engine_seams",
        lambda engine, port_bin=None: (real_seams[0], counting_measure),
    )
    first = run_sweep(files, engine="fast", port_bin=port_bin, cache_path=cache_path)
    assert calls["l2"] == 2
    assert first["cache_misses"] == 2 and first["cache_hits"] == 0
    second = run_sweep(files, engine="fast", port_bin=port_bin, cache_path=cache_path)
    assert calls["l2"] == 2, "a cache hit must not run the seams again"
    assert second["cache_hits"] == 2 and second["cache_misses"] == 0
    assert second["classifications"] == first["classifications"]

    monkeypatch.setattr("catpart.fitness.speed.code_digest", lambda binary: "stale" * 16)
    third = run_sweep(files, engine="fast", port_bin=port_bin, cache_path=cache_path)
    assert calls["l2"] == 4, "a changed code digest must invalidate every entry"
    assert third["cache_misses"] == 2 and third["cache_hits"] == 0


def test_code_cache_ignores_torn_lines_and_foreign_digests(tmp_path: Path) -> None:
    cache_path = tmp_path / "cache.jsonl"
    digest = "a" * 64
    cache_path.write_text(
        json.dumps({"sha256": "f" * 64, "code_digest": digest, "record": {"classification": "clean", "l2": None}})
        + "\n"
        + "{torn line without newline ending"  # a killed run's last line
        + "\n"
        + json.dumps({"sha256": "e" * 64, "code_digest": "b" * 64, "record": {"classification": "clean"}})
        + "\n",
        encoding="utf-8",
    )
    cache = CodeCache(cache_path, digest)
    assert cache.get("f" * 64)["classification"] == "clean"
    assert cache.get("e" * 64) is None, "a foreign code digest is a miss"
    assert cache.get("0" * 64) is None


# --- engine parity (needs the release port binary) ----------------------------


def test_engine_parity_over_every_fixture_variant(tmp_path: Path) -> None:
    """``rust`` and ``fast`` vs ``python`` over every A2 variant: zero
    divergences on the classification-and-L2 decision surface."""
    root = _write_variant_dir(tmp_path)
    _port_bin_or_skip()
    base_summary, base_csv = _run_sweep_to(root, ENGINE_PYTHON, tmp_path)
    rust_summary, rust_csv = _run_sweep_to(root, "rust", tmp_path)
    fast_summary, fast_csv = _run_sweep_to(root, "fast", tmp_path)

    assert base_summary["files"] == rust_summary["files"] == fast_summary["files"]
    assert rust_summary["classifications"] == base_summary["classifications"]
    assert rust_summary["l2_statuses"] == base_summary["l2_statuses"]
    for engine_csv in (rust_csv, fast_csv):
        count, divergences = compare_sweep_csvs(base_csv, engine_csv)
        assert count == 0, "engine divergences: " + "; ".join(divergences)


def test_engine_parity_exercises_crash_and_export_failures(tmp_path: Path) -> None:
    """The parity population is not a clean-only walk: the corrupted
    variants land in ``crash``/``schema-invalid`` and the store-less
    exports fail ``missing-geometry-store`` on BOTH engines."""
    root = _write_variant_dir(tmp_path)
    _port_bin_or_skip()
    base_summary, base_csv = _run_sweep_to(root, ENGINE_PYTHON, tmp_path)
    assert "crash" in base_summary["classifications"], "the crash variants must be exercised"
    rust_summary, rust_csv = _run_sweep_to(root, "rust", tmp_path)
    count, _ = compare_sweep_csvs(base_csv, rust_csv)
    assert count == 0
    with base_csv.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    export_classes = {row["l2_error_class"] for row in rows if row["l2_error_class"]}
    assert "missing-geometry-store" in export_classes


def test_run_fitness_engine_parity_same_manifest(tmp_path: Path) -> None:
    """The full protocol, both engines, one mini manifest: identical
    scalars, identical per-file decision surface, identical acceptance.

    The L2 records compare on the runner's decision surface: the
    warnings' ``detail`` prose is projected to the class list before
    the equality (the twins' wordings differ on real stores — measured
    2026-11-22 — and prose is never compared, spec §3.2)."""
    manifest_path = write_mini_corpus(tmp_path, build_catpart)[0]
    _port_bin_or_skip()

    def decision_surface(record: dict) -> dict:
        l2 = record["l2"]
        if l2 is not None:
            l2 = dict(l2)
            l2["warnings"] = [w["class"] for w in (l2.get("warnings") or [])]
        return (record["classification"], record["detected_version"], l2)

    py_row = run_fitness(
        manifest_path, fitness_dir=tmp_path / "fitness-py", engine=ENGINE_PYTHON
    )
    fast_row = run_fitness(manifest_path, fitness_dir=tmp_path / "fitness-fast", engine="fast")

    assert py_row["accepted"] == fast_row["accepted"]
    assert py_row["scalars"] == fast_row["scalars"]
    py_report = json.loads(
        (tmp_path / "fitness-py" / py_row["report"]).read_text(encoding="utf-8")
    )
    fast_report = json.loads(
        (tmp_path / "fitness-fast" / fast_row["report"]).read_text(encoding="utf-8")
    )
    assert py_report["totals"] == fast_report["totals"]
    py_files = {record["sha256"]: record for record in py_report["files"]}
    fast_files = {record["sha256"]: record for record in fast_report["files"]}
    assert set(py_files) == set(fast_files)
    for sha, py_record in py_files.items():
        assert decision_surface(py_record) == decision_surface(fast_files[sha]), sha


def test_run_fitness_unknown_engine_fails_closed(tmp_path: Path) -> None:
    manifest_path = write_mini_corpus(tmp_path, build_catpart)[0]
    with pytest.raises(FitnessError, match="unknown engine"):
        run_fitness(manifest_path, engine="laya")
