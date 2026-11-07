"""Console-script entry points for catpart-parser.

The two seams of Spec A (#8): ``catpart-inspect`` emits
schema-versioned JSON; ``catpart-fitness`` (ticket #14) runs the
fitness protocol of ADR-0001 over the corpus manifest — classify every
file through :func:`build_inspect_report`, write the full report, and
append exactly one row (accepted or rejected) to the committed
append-only ``fitness/history.jsonl``.

catpart-inspect output is schema v1 (ticket #23): the v0 metadata
(magic, header dword8, file size, detected CNEXTINFOS version — tickets
#11/#13) plus the remaining header dwords, the part/product kind, the
parsed container-name table records (docs/evidence/2026-11-07-
container-table-and-trailer.md) and the trailer. v0 replaced its
whole-file container-name string scan with the record parse and dropped
the ``container_names`` field; that breaking change is why the schema
version moved to v1. File-level failures (missing file, unreadable,
smaller than the 32-byte header) print a ``catpart-inspect: error: ...``
line to stderr and exit 1; usage errors exit 2 via argparse convention.
catpart-fitness follows the same convention: exit 0 for a completed run
(the acceptance verdict is data on the history row, not a process
status), 1 on runtime failures, 2 on usage errors.
"""

from __future__ import annotations

import argparse
import json
import mmap
import sys
from pathlib import Path

from catpart.containers import detect_kind, parse_container_table
from catpart.header import HEADER_SIZE, parse_header
from catpart.trailer import parse_trailer
from catpart.version import detect_version

SCHEMA_VERSION = 1


def build_inspect_report(path: Path) -> dict:
    """Build the schema-v1 report dict for ``path``.

    The file is memory-mapped so the whole-file scans (the container-name
    table over the evidence-validated first 2 MB window; corpus maximum:
    a 375 MB part) never load the payload into RAM. Raises
    :class:`OSError` for unreadable paths and :class:`ValueError` for
    files smaller than the 32-byte header.
    """
    file_size = path.stat().st_size
    if file_size < HEADER_SIZE:
        raise ValueError(
            f"not a CATIA V5 container: header needs {HEADER_SIZE} bytes, got {file_size}"
        )
    with open(path, "rb") as fh, mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as data:
        info = parse_header(data[:HEADER_SIZE])
        version = detect_version(data)
        records = parse_container_table(data)
        trailer = parse_trailer(data)
    return {
        "schema_version": SCHEMA_VERSION,
        "magic": info.magic,
        "header_dword": info.header_dword,
        "header_dword12": info.header_dword12,
        "ff8_at_16_24": info.ff8_at_16_24,
        "header_dword16": info.header_dword16,
        "header_dword20": info.header_dword20,
        "file_size": file_size,
        "detected_version": version,
        "kind": detect_kind(records),
        "containers": [record.to_json() for record in records],
        "trailer": None if trailer is None else trailer.to_json(),
    }


def main_inspect(argv: list[str] | None = None) -> int:
    """Entry point of the ``catpart-inspect`` console script.

    Returns the process exit code: 0 on success, 1 on file-level
    errors, 2 on usage errors (raised as :class:`SystemExit` by
    argparse).
    """
    parser = argparse.ArgumentParser(
        prog="catpart-inspect",
        description=(
            "Inspect a CATIA V5 .CATPart/.CATProduct file and emit a "
            "schema-versioned JSON report (schema v1: magic, header dwords, "
            "file size, detected CNEXTINFOS version, part/product kind, the "
            "parsed container-name table records and the trailer)."
        ),
    )
    parser.add_argument("file", type=Path, help="path to a .CATPart/.CATProduct file")
    args = parser.parse_args(argv)
    try:
        report = build_inspect_report(args.file)
    except (OSError, ValueError) as exc:
        print(f"catpart-inspect: error: {exc}", file=sys.stderr)
        return 1
    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def main_fitness(argv: list[str] | None = None) -> int:
    """Entry point of the ``catpart-fitness`` console script (ticket #14).

    Measures fitness per ADR-0001 over the corpus manifest, writes the
    full report to ``fitness/reports/<run_id>.json`` and appends exactly
    one history row — accepted or rejected — to the committed
    ``fitness/history.jsonl``; the row JSON is printed to stdout. Exit
    codes: 0 for a completed run (acceptance is data, not process
    status), 1 on runtime failures (unreadable or malformed manifest,
    corrupt committed history, unwritable artifacts), 2 on usage errors
    (argparse).

    The runner import is deferred because the runner consumes
    :func:`build_inspect_report` from this module; a module-level import
    would form an import cycle.
    """
    parser = argparse.ArgumentParser(
        prog="catpart-fitness",
        description=(
            "Run the fitness protocol (ADR-0001) over the corpus manifest: "
            "classify every file through catpart-inspect, write the full "
            "report JSON, and append one row - accepted or rejected - to "
            "the committed fitness/history.jsonl. Defaults assume the "
            "repository layout; run from the repository root."
        ),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("manifests/corpus-manifest.csv"),
        help="corpus manifest CSV (default: manifests/corpus-manifest.csv "
        "relative to the working directory)",
    )
    parser.add_argument(
        "--corpus-root",
        type=Path,
        default=None,
        help="root the manifest's local_path entries resolve against "
        "(default: the repository root derived from the manifest location)",
    )
    parser.add_argument(
        "--fitness-dir",
        type=Path,
        default=None,
        help="directory holding history.jsonl and reports/ "
        "(default: <repository root>/fitness)",
    )
    args = parser.parse_args(argv)
    try:
        from catpart.fitness.runner import FitnessError, run_fitness

        row = run_fitness(
            args.manifest, corpus_root=args.corpus_root, fitness_dir=args.fitness_dir
        )
    except FitnessError as exc:
        print(f"catpart-fitness: error: {exc}", file=sys.stderr)
        return 1
    json.dump(row, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0
