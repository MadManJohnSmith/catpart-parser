"""The fitness fast-path (marathon W7, speed oracle): native-engine
seams, an incremental cache and the streaming corpus sweep.

The fitness protocol's measured cost on a real corpus is dominated by
the L2 export (the G4 seam's decode + mesh invariants + PLY write), not
by the L1 inspect: measured 2026-11-22 on a 120-file deterministic
sample of a 757-file V5 corpus, the in-process Python pair costs
~367 ms/file of which ~365 ms is L2. The port's ``fidelity-cli``
binary — the same shipped seam the Fidelity harness drives (spec §2.4)
— decodes and exports natively at ~16 ms/file (a measured 22x on the
same sample), with the sweep's parent process staying flat.

Three engines, one classification contract:

- ``python`` (the default everywhere): the in-process reference seams
  (:func:`catpart.fitness.runner._classify_file`,
  :func:`catpart.fitness.runner._measure_l2`). Byte-for-byte the
  historical behavior; nothing else in this module runs unless asked.
- ``rust``: both phases through the ``fidelity-cli`` subprocesses —
  ``inspect`` for L1, ``export`` for L2 — with the runner's own
  post-processing (schema validation, invariants, the L2 sanity gate)
  applied to the port's outputs, so the classification vocabulary is
  the runner's, not the port's.
- ``fast``: Python L1 (in-process inspect is faster than a subprocess
  spawn at ~1.7 ms/file) + Rust L2 (the 22x phase). The measured best
  of both; the recommended sweep engine.

The incremental cache is keyed by ``(file_sha256, code_digest)``:
``file_sha256`` is the swept file's SHA-256, ``code_digest`` is the
SHA-256 over the fast-path's own sources (this module, the runner, the
invariants) plus the port binary's bytes — any change to the gate
semantics or the decoder invalidates every entry at once. Cache hits
still pay the digest hash (it is the lookup key) but skip both seams.
The cache file lives wherever the caller points ``--cache`` (the sweep
defaults it to a run-scoped temp path): it is a scratch artifact, never
a committed one.

The sweep streams file by file: one file in flight, its CSV row
written and flushed before the next file is touched, aggregates-only
in memory. Peak RSS is bounded by the largest single file (the export
seam reads whole stores) regardless of corpus size; the measured
757-file / 3.5 GB run holds the parent at a flat ~16 MiB.

The ``compare`` subcommand diffs two sweep CSVs on the
classification-and-L2 fields (the runner's decision surface), never on
error ``detail`` prose — the same never-compared-bite-wise rule the
Fidelity harness states (spec §3.2). A nonzero exit means the two
engines disagree on at least one row.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from resource import RUSAGE_CHILDREN, RUSAGE_SELF, getrusage

ENGINE_PYTHON = "python"
ENGINE_RUST = "rust"
ENGINE_FAST = "fast"
ENGINES: tuple[str, ...] = (ENGINE_PYTHON, ENGINE_RUST, ENGINE_FAST)

#: The port binary override (same resolution order as the Fidelity
#: harness's ``FIDELITY_PORT_BIN``: explicit override first).
PORT_BIN_ENV = "CATPART_PORT_BIN"

#: The fast-path's own sources the code digest pins (gate semantics
#: live in the runner and the invariants; this module is the seams).
_CODE_SOURCES = ("speed.py", "runner.py", "invariants.py")

#: Cache entry fields (the reduced per-file record the sweep needs;
#: the full inspect document is never retained — streaming contract).
_CACHE_VERSION = 1

SWEEP_COLUMNS = (
    "sha256",
    "path",
    "engine",
    "cache",
    "classification",
    "detected_version",
    "kind",
    "l2_status",
    "l2_error_class",
    "l2_failed_check",
    "l2_vertex_count",
    "l2_triangle_count",
    "l2_degenerate_triangle_count",
    "l2_warnings",
    "error",
    "hash_seconds",
    "l1_seconds",
    "l2_seconds",
)

# --- the port binary ------------------------------------------------------


def resolve_port_binary(build_if_missing: bool = False) -> Path:
    """Locate the release ``fidelity-cli`` (the Fidelity harness's
    resolution order: the ``CATPART_PORT_BIN`` override, the release
    target next to this checkout). ``build_if_missing`` runs the
    harness's own build step (``cargo build --release --locked`` in
    ``port/``) once — the same convention
    ``scripts/fidelity_run.py::build_port_bin`` pins, so a test that
    needs the real binary pays the build the fixture-mode gate test
    would pay anyway.
    """
    override = os.environ.get(PORT_BIN_ENV)
    if override:
        path = Path(override)
        if path.is_file():
            return path
        raise FileNotFoundError(f"{PORT_BIN_ENV}={override} is not a file")
    port_dir = Path(__file__).resolve().parents[3] / "port"
    for name in ("fidelity-cli", "fidelity_cli"):
        candidate = port_dir / "target" / "release" / name
        if candidate.is_file():
            return candidate
    if not build_if_missing:
        raise FileNotFoundError(
            "the release fidelity-cli binary is missing; build it with "
            "`cargo build --release --locked` in port/ (or set "
            f"{PORT_BIN_ENV})"
        )
    cargo = shutil.which("cargo")
    if cargo is None:
        raise FileNotFoundError(
            "the release fidelity-cli binary is missing and cargo is not "
            "on PATH — the Rust toolchain is a required dev dependency "
            "(spec §7)"
        )
    build = subprocess.run(
        [cargo, "build", "--release", "--locked"],
        cwd=port_dir,
        capture_output=True,
        text=True,
    )
    if build.returncode != 0:
        sys.stderr.write(build.stdout)
        sys.stderr.write(build.stderr)
        raise FileNotFoundError("cargo build --release failed (see stderr above)")
    return resolve_port_binary(build_if_missing=False)


# --- digests --------------------------------------------------------------


def file_sha256(path: Path) -> str:
    """The file's SHA-256, read in 1 MiB chunks (a 3.5 GB corpus stays
    flat in memory: only the chunk buffer is held)."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def code_digest(port_bin: Path) -> str:
    """The fast-path's code digest: SHA-256 over this module's, the
    runner's and the invariants' sources plus the port binary's bytes.

    Every entry in the cache is keyed with it, so a changed gate, a
    changed seam or a rebuilt decoder invalidates the whole cache at
    once — no stale-result window can outlive the change that would
    make one.
    """
    digest = hashlib.sha256()
    digest.update(f"cache-v{_CACHE_VERSION}".encode("utf-8"))
    package_dir = Path(__file__).resolve().parent
    for name in _CODE_SOURCES:
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update((package_dir / name).read_bytes())
        digest.update(b"\0")
    digest.update(b"port-bin\0")
    digest.update(port_bin.read_bytes())
    return digest.hexdigest()


# --- the native seams (the runner's classification contract) --------------


def _classified_error(stderr: bytes) -> tuple[str, str] | None:
    """The port's one-JSON-line classified failure, or ``None`` when
    stderr is not that shape (a harness-level failure, not a class)."""
    try:
        payload = json.loads(stderr.decode("utf-8", errors="replace"))
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("error_class"), str):
        return None
    return payload["error_class"], str(payload.get("detail", ""))


def classify_file_rust(file_path: Path, port_bin: Path) -> tuple[str, str | None, dict | None]:
    """L1 through the port's ``inspect`` seam, then the runner's own
    post-processing — schema validation and the minimal invariants —
    exactly as :func:`catpart.fitness.runner._classify_file` applies
    them to the in-process document. The port's exit-1 classified
    failure maps to the fitness class ``crash`` (the single-class L1
    vocabulary both sides share, ``bin/fidelity-cli.rs``); any other
    non-zero exit is a harness-level failure recorded as ``crash`` with
    a ``harness:`` detail — the run must not silently reclassify a
    broken seam as clean data, and one broken file must never abort a
    sweep (the runner's own rule).
    """
    # Lazy: the runner imports this module's engine seams; importing it
    # at module level would be a cycle.
    from catpart.fitness.runner import (
        CLASS_CLEAN,
        CLASS_CRASH,
        CLASS_MISSING_INVARIANT,
        CLASS_SCHEMA_INVALID,
        INSPECT_SCHEMA,
    )
    from catpart.fitness.invariants import check_invariants
    from catpart.schema.validate import SchemaError, ValidationError, validate

    try:
        proc = subprocess.run(
            [str(port_bin), "inspect", str(file_path)],
            capture_output=True,
            timeout=600,
        )
    except subprocess.TimeoutExpired as exc:
        return CLASS_CRASH, f"harness: inspect timeout after {exc.timeout}s", None
    except OSError as exc:
        return CLASS_CRASH, f"harness: cannot execute {port_bin}: {exc}", None
    if proc.returncode != 0:
        # The classified line IS the port's failure contract (exit 1);
        # anything else is a harness-level failure, never a match.
        classified = _classified_error(proc.stderr) if proc.returncode == 1 else None
        if classified is not None and classified[0] == "crash":
            return CLASS_CRASH, classified[1], None
        detail = proc.stderr.decode("utf-8", errors="replace").strip() or "(no stderr)"
        return CLASS_CRASH, f"harness: inspect exited {proc.returncode}: {detail}", None
    try:
        document = json.loads(proc.stdout.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return CLASS_CRASH, f"harness: unreadable inspect stdout: {exc}", None
    try:
        validate(document, INSPECT_SCHEMA)
    except ValidationError as exc:
        return CLASS_SCHEMA_INVALID, str(exc), document
    except SchemaError as exc:
        from catpart.fitness import FitnessError

        raise FitnessError(f"the committed inspect schema is invalid: {exc}") from exc
    failure = check_invariants(document)
    if failure is not None:
        return CLASS_MISSING_INVARIANT, failure, document
    return CLASS_CLEAN, None, document


def measure_l2_rust(file_path: Path, out_path: Path, port_bin: Path) -> dict:
    """L2 through the port's ``export`` seam, scored by the runner's
    own sanity gate (:func:`catpart.fitness.runner._score_export`) —
    the gate vocabulary (``failed_check`` classes and thresholds) is
    the runner's; only the decode + PLY write moved native. The port's
    exit-1 classified failures carry the geometry error-class
    vocabulary at the same raise sites as the Python ``ExportError``
    contract, so the record shape is identical to
    :func:`catpart.fitness.runner._measure_l2`'s; any other non-zero
    exit is the :data:`catpart.fitness.runner.L2_EXPORT_CRASH` class
    with a ``harness:`` detail (an exporter bug must stay visible, not
    vanish into a pass/fail headline)."""
    from catpart.fitness.runner import L2_EXPORT_CRASH, _l2_failure, _score_export

    try:
        proc = subprocess.run(
            [str(port_bin), "export", str(file_path), str(out_path)],
            capture_output=True,
            timeout=600,
        )
    except subprocess.TimeoutExpired as exc:
        return _l2_failure(L2_EXPORT_CRASH, f"harness: export timeout after {exc.timeout}s")
    except OSError as exc:
        return _l2_failure(L2_EXPORT_CRASH, f"harness: cannot execute {port_bin}: {exc}")
    if proc.returncode != 0:
        classified = _classified_error(proc.stderr) if proc.returncode == 1 else None
        if classified is not None:
            return _l2_failure(classified[0], classified[1])
        detail = proc.stderr.decode("utf-8", errors="replace").strip() or "(no stderr)"
        return _l2_failure(L2_EXPORT_CRASH, f"harness: export exited {proc.returncode}: {detail}")
    try:
        summary = json.loads(proc.stdout.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return _l2_failure(L2_EXPORT_CRASH, f"harness: unreadable export summary: {exc}")
    # The exporter self-checks its summary against the committed schema
    # before returning; a shape violation here is a port bug — surfaced
    # as the crash class, never scored as a gate failure.
    if not isinstance(summary, dict) or "mesh" not in summary or "bounding_box" not in summary:
        return _l2_failure(L2_EXPORT_CRASH, "harness: export summary is not a summary document")
    return _score_export(summary)


def engine_seams(engine: str, port_bin: Path | None = None):
    """The ``(classify_file, measure_l2)`` pair for ``engine``.

    ``python`` returns the runner's own seams unchanged (module
    attributes resolved through them at call time, so the existing
    monkeypatch-based tests keep faking the seam exactly where they
    always did). ``rust`` and ``fast`` return the native-backed pairs;
    ``fast`` keeps L1 in-process (measured faster than a subprocess
    spawn) and moves only the L2 export native.
    """
    if engine == ENGINE_PYTHON:
        from catpart.fitness.runner import _classify_file, _measure_l2

        return _classify_file, _measure_l2
    if port_bin is None:
        port_bin = resolve_port_binary()
    if engine == ENGINE_RUST:
        return (
            lambda file_path: classify_file_rust(file_path, port_bin),
            lambda file_path, out_path: measure_l2_rust(file_path, out_path, port_bin),
        )
    if engine == ENGINE_FAST:
        from catpart.fitness.runner import _classify_file

        return _classify_file, lambda file_path, out_path: measure_l2_rust(
            file_path, out_path, port_bin
        )
    raise ValueError(f"unknown engine: {engine!r} (expected one of {', '.join(ENGINES)})")


# --- the incremental cache -------------------------------------------------


class CodeCache:
    """Append-only JSONL cache keyed by ``(file_sha256, code_digest)``.

    Entries are the sweep's reduced per-file records (classification,
    detected_version, kind, the full L2 record). Appends are flushed
    per entry: a killed sweep leaves every completed row usable. The
    key's digest half pins the code — see :func:`code_digest`.
    """

    def __init__(self, path: Path | None, digest: str):
        self.path = path
        self.digest = digest
        self.hits = 0
        self.misses = 0
        self._entries: dict[tuple[str, str], dict] = {}
        if path is not None and path.is_file():
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue  # a torn last line from a killed run
                    key = (entry.get("sha256"), entry.get("code_digest"))
                    if key[0] and key[1] == digest:
                        self._entries[key] = entry

    def get(self, sha256: str) -> dict | None:
        entry = self._entries.get((sha256, self.digest))
        if entry is None:
            self.misses += 1
            return None
        self.hits += 1
        return entry["record"]

    def put(self, sha256: str, record: dict) -> None:
        entry = {"sha256": sha256, "code_digest": self.digest, "record": record}
        self._entries[(sha256, self.digest)] = entry
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, separators=(",", ":")) + "\n")


# --- the streaming sweep ---------------------------------------------------


def collect_files(root: Path, pattern: str = "*.CATPart", limit: int | None = None) -> list[Path]:
    """The sweep population: every file matching ``pattern`` under
    ``root``, sorted by path (deterministic; a re-run sweeps the same
    files in the same order). ``limit`` takes the first N — the
    deterministic-sample prefix, not a random draw."""
    files = sorted(p for p in root.rglob(pattern) if p.is_file())
    return files[:limit] if limit is not None else files


def _warning_classes(l2: dict | None) -> list[str]:
    """The L2 warnings' class list — the decision surface. The
    warnings' ``detail`` prose is deliberately dropped: it is the one
    field the Fidelity contract declares never-compared (spec §3.2;
    measured 2026-11-22: the exporters' ``primary-loop-relist-skip``
    wording differs between the twins on real corpus stores, and the
    runner's aggregates read ``w["class"]`` only)."""
    if l2 is None:
        return []
    return [w["class"] for w in (l2.get("warnings") or [])]


def _l2_csv_fields(l2: dict | None) -> dict[str, str]:
    """The L2 record's CSV projection (warnings as the compact JSON
    class list so the column stays one CSV field)."""
    if l2 is None:
        return {
            "l2_status": "",
            "l2_error_class": "",
            "l2_failed_check": "",
            "l2_vertex_count": "",
            "l2_triangle_count": "",
            "l2_degenerate_triangle_count": "",
            "l2_warnings": "",
        }
    return {
        "l2_status": l2.get("status") or "",
        "l2_error_class": l2.get("error_class") or "",
        "l2_failed_check": l2.get("failed_check") or "",
        "l2_vertex_count": "" if l2.get("vertex_count") is None else str(l2["vertex_count"]),
        "l2_triangle_count": "" if l2.get("triangle_count") is None else str(l2["triangle_count"]),
        "l2_degenerate_triangle_count": (
            "" if l2.get("degenerate_triangle_count") is None else str(l2["degenerate_triangle_count"])
        ),
        "l2_warnings": json.dumps(_warning_classes(l2), separators=(",", ":")),
    }


def run_sweep(
    files: list[Path],
    *,
    engine: str = ENGINE_FAST,
    port_bin: Path | None = None,
    out_csv: Path | None = None,
    cache_path: Path | None = None,
    with_l2: bool = True,
    corpus_root: Path | None = None,
) -> dict:
    """The streaming sweep: classify (and, when ``with_l2``, export +
    gate-score) every file in ``files``, one at a time, writing each
    row before touching the next file. Returns the run summary (the
    JSON the ``sweep`` subcommand prints).

    The cache is consulted by ``(file_sha256, code_digest)``; a hit
    skips both seams but still pays the digest (it is the key). Peak
    RSS (parent + children via ``getrusage``) is measured, not
    estimated. ``out_csv`` rows land incrementally — the file on disk
    is a prefix-complete view of the run at any instant.
    """
    if engine not in ENGINES:
        raise ValueError(f"unknown engine: {engine!r} (expected one of {', '.join(ENGINES)})")
    classify, measure = engine_seams(engine, port_bin)
    digest = code_digest(port_bin) if engine != ENGINE_PYTHON else None
    cache = CodeCache(cache_path, digest) if digest is not None else None
    scratch_dir: Path | None = None
    cleanup = None
    if with_l2:
        holder = tempfile.TemporaryDirectory(prefix="catpart-fitness-sweep-")
        cleanup = holder
        scratch_dir = Path(holder.name)
    out_file = None
    writer = None
    if out_csv is not None:
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        out_file = out_csv.open("w", encoding="utf-8", newline="")
        writer = csv.DictWriter(out_file, fieldnames=SWEEP_COLUMNS)
        writer.writeheader()

    classifications: Counter[str] = Counter()
    l2_statuses: Counter[str] = Counter()
    hash_s = l1_s = l2_s = 0.0
    try:
        for file_path in files:
            row: dict[str, str] = {
                "path": str(file_path.relative_to(corpus_root)) if corpus_root else str(file_path),
                "engine": engine,
            }
            started = time.monotonic()
            sha256 = file_sha256(file_path)
            row["sha256"] = sha256
            hash_seconds = time.monotonic() - started
            row["hash_seconds"] = f"{hash_seconds:.6f}"
            hash_s += hash_seconds

            cached = cache.get(sha256) if cache is not None else None
            record: dict
            file_l1_s = file_l2_s = 0.0
            if cached is not None:
                record = cached
                row["cache"] = "hit"
                classification = record["classification"]
                output = record.get("output")
                l2 = record.get("l2")
            else:
                row["cache"] = "miss"
                a = time.monotonic()
                classification, error, output = classify(file_path)
                b = time.monotonic()
                l2 = measure(file_path, scratch_dir / f"{sha256[:16]}.ply") if with_l2 else None
                c = time.monotonic()
                file_l1_s, file_l2_s = b - a, c - b
                l1_s += file_l1_s
                l2_s += file_l2_s
                record = {
                    "classification": classification,
                    "error": error,
                    "output": None
                    if output is None
                    else {
                        "detected_version": output.get("detected_version"),
                        "kind": output.get("kind"),
                    },
                    "l2": l2,
                }
                if cache is not None:
                    cache.put(sha256, record)
            row["classification"] = classification
            row["detected_version"] = "" if output is None else str(output.get("detected_version"))
            row["kind"] = "" if output is None else str(output.get("kind"))
            row["error"] = "" if record.get("error") is None else str(record["error"])
            row.update(_l2_csv_fields(l2))
            # Per-phase seconds are recorded on miss rows only (a hit's
            # cost is the hash; the phases did not run). The accumulated
            # totals land in the summary.
            row["l1_seconds"] = f"{file_l1_s:.6f}" if cached is None else ""
            row["l2_seconds"] = f"{file_l2_s:.6f}" if cached is None else ""
            classifications[classification] += 1
            if with_l2 and l2 is not None:
                l2_statuses[str(l2.get("status"))] += 1
            if writer is not None:
                writer.writerow(row)
                out_file.flush()
    finally:
        if out_file is not None:
            out_file.close()
        if cleanup is not None:
            cleanup.cleanup()

    summary = {
        "engine": engine,
        "files": len(files),
        "wall_seconds": None,  # filled by the caller (the subcommand)
        "hash_seconds": round(hash_s, 3),
        "l1_seconds": round(l1_s, 3),
        "l2_seconds": round(l2_s, 3),
        "cache_hits": cache.hits if cache is not None else 0,
        "cache_misses": cache.misses if cache is not None else 0,
        "classifications": dict(classifications),
        "l2_statuses": dict(l2_statuses),
        "code_digest": digest,
        "peak_rss_parent_mib": round(getrusage(RUSAGE_SELF).ru_maxrss / 1024, 1),
        "peak_rss_children_mib": round(getrusage(RUSAGE_CHILDREN).ru_maxrss / 1024, 1),
    }
    return summary


# --- the comparator --------------------------------------------------------


#: The compared fields (the decision surface): classification plus every
#: L2 record field the runner's gate or aggregate reads. ``error`` and
#: ``detected_version`` prose is never compared, and ``l2_warnings``
#: carries the warning CLASSES only (spec §3.2's rule: prose — the
#: twins' ``detail`` wordings — is never compared).
COMPARE_FIELDS = (
    "classification",
    "detected_version",
    "kind",
    "l2_status",
    "l2_error_class",
    "l2_failed_check",
    "l2_vertex_count",
    "l2_triangle_count",
    "l2_degenerate_triangle_count",
    "l2_warnings",
)


def compare_sweep_csvs(base_csv: Path, other_csv: Path) -> tuple[int, list[str]]:
    """Diff two sweep CSVs on :data:`COMPARE_FIELDS`, keyed by sha256.

    Returns ``(mismatch_count, first_divergences)`` — at most the first
    20 divergences, one line each, ``path: field: base vs other``. Rows
    present on one side only are mismatches (a population difference is
    itself a comparison result).
    """
    def load(path: Path) -> dict[str, dict[str, str]]:
        with path.open(newline="", encoding="utf-8") as fh:
            return {row["sha256"]: row for row in csv.DictReader(fh)}

    base, other = load(base_csv), load(other_csv)
    mismatches: list[str] = []
    for sha in sorted(set(base) | set(other)):
        b, o = base.get(sha), other.get(sha)
        where = (b or o)["path"]
        if b is None:
            mismatches.append(f"{where}: row missing from {base_csv.name}")
            continue
        if o is None:
            mismatches.append(f"{where}: row missing from {other_csv.name}")
            continue
        for field in COMPARE_FIELDS:
            if b[field] != o[field]:
                mismatches.append(f"{where}: {field}: {b[field]!r} vs {o[field]!r}")
    return len(mismatches), mismatches[:20]


# --- the CLI ---------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """``python -B -m catpart.fitness.speed <sweep|compare> ...``.

    ``sweep --root DIR [--engine fast|rust|python] [--limit N]
            [--no-l2] [--csv PATH] [--cache PATH] [--pattern GLOB]``
    sweeps the corpus directory streaming and prints the summary JSON
    (the evidence row: engine, wall, phases, cache, peak RSS).

    ``compare BASE.csv OTHER.csv`` diffs the two sweeps on the
    classification-and-L2 fields; exit 1 on any mismatch.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        sys.stderr.write(main.__doc__ or "")
        return 2
    if argv[0] == "compare":
        if len(argv) != 3:
            sys.stderr.write("usage: speed compare BASE.csv OTHER.csv\n")
            return 2
        count, first = compare_sweep_csvs(Path(argv[1]), Path(argv[2]))
        for line in first:
            print(line)
        print(f"compare: {count} mismatch(es)")
        return 1 if count else 0
    if argv[0] != "sweep":
        sys.stderr.write(f"unknown subcommand: {argv[0]}\n")
        return 2
    args = argv[1:]
    def value(flag: str, default: str | None = None) -> str | None:
        if flag in args:
            return args[args.index(flag) + 1]
        return default
    root = value("--root")
    if root is None:
        sys.stderr.write("usage: speed sweep --root DIR [--engine E] [--limit N] ...\n")
        return 2
    engine = value("--engine", ENGINE_FAST)
    pattern = value("--pattern", "*.CATPart")
    limit_raw = value("--limit")
    out_csv = value("--csv")
    cache_raw = value("--cache")
    with_l2 = "--no-l2" not in args
    files = collect_files(Path(root), pattern, int(limit_raw) if limit_raw else None)
    if not files:
        print("sweep: no files matched", file=sys.stderr)
        return 1
    port_bin = None if engine == ENGINE_PYTHON else resolve_port_binary()
    cache_path = Path(cache_raw) if cache_raw else (
        Path(tempfile.gettempdir()) / "catpart-fitness-cache" / f"{port_bin.name if port_bin else 'python'}.jsonl"
    )
    started = time.monotonic()
    summary = run_sweep(
        files,
        engine=engine,
        port_bin=port_bin,
        out_csv=Path(out_csv) if out_csv else None,
        cache_path=cache_path,
        with_l2=with_l2,
        corpus_root=Path(root),
    )
    summary["wall_seconds"] = round(time.monotonic() - started, 3)
    summary["ms_per_file"] = round(summary["wall_seconds"] / len(files) * 1000, 2)
    summary["cache_path"] = str(cache_path)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover - the console entry
    raise SystemExit(main())
