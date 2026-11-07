"""Console-script entry points for catpart-parser.

The two seams of Spec A (#8): ``catpart-inspect`` emits
schema-versioned JSON; ``catpart-fitness`` is a stub until the
fitness-runner ticket (#14).

catpart-inspect output is schema v0 (ticket #11): schema_version, magic,
header_dword, file_size, container_names; the detected CNEXTINFOS
version field (ticket #13) was added while the schema stayed v0.
File-level failures (missing file, unreadable, smaller than the 32-byte
header) print a ``catpart-inspect: error: ...`` line to stderr and exit
1; usage errors exit 2 via argparse convention. catpart-fitness exits 2
with a "not implemented yet" note while it is a stub.
"""

from __future__ import annotations

import argparse
import json
import mmap
import sys
from pathlib import Path

from catpart.containers import scan_container_names
from catpart.header import HEADER_SIZE, parse_header
from catpart.version import detect_version

SCHEMA_VERSION = 0


def build_inspect_report(path: Path) -> dict:
    """Build the schema-v0 report dict for ``path``.

    The file is memory-mapped so the whole-file container-name scan
    (corpus maximum: a 375 MB part) never loads the payload into RAM.
    Raises :class:`OSError` for unreadable paths and :class:`ValueError`
    for files smaller than the 32-byte header.
    """
    file_size = path.stat().st_size
    if file_size < HEADER_SIZE:
        raise ValueError(
            f"not a CATIA V5 container: header needs {HEADER_SIZE} bytes, got {file_size}"
        )
    with open(path, "rb") as fh, mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as data:
        info = parse_header(data[:HEADER_SIZE])
        version = detect_version(data)
        names = scan_container_names(data)
    return {
        "schema_version": SCHEMA_VERSION,
        "magic": info.magic,
        "header_dword": info.header_dword,
        "file_size": file_size,
        "detected_version": version,
        "container_names": names,
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
            "schema-versioned JSON report (schema v0: magic string, header "
            "dword, file size, detected CNEXTINFOS version, container-name "
            "strings)."
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
    """Entry point of the ``catpart-fitness`` console script.

    Stub until the fitness-runner ticket (#14): the fitness protocol
    itself is ADR-0001. Exits 2 with a note on stderr; the non-zero
    code marks "requested operation not available" as distinct from a
    runtime failure (1).
    """
    del argv  # accepted for console-script signature symmetry
    print("catpart-fitness: not implemented yet", file=sys.stderr)
    return 2
