#!/usr/bin/env python3
"""Score the L3 construct-coverage headline from committed artifacts (BR6, #58).

Reads only committed files — the frozen 23-construct vocabulary
(``docs/evidence/data/brep-construct-vocabulary.csv``), the declarative
``RESOLUTION_REGISTRY`` in ``catpart.fitness.l3`` and the per-BR claims CSVs
it cites — so the run is corpus-free, network-free and deterministic. It
never appends to ``fitness/history.jsonl``: the last accepted row is read
for the no-regret context (L1/L2 frozen scalars) and left untouched.

Outputs, by default:

* the JSON document on **stdout** (machine-readable artifact);
* the human-readable summary on **stderr**.

``--json-out`` / ``--summary-out`` redirect either stream to a file.

  export LD_LIBRARY_PATH=/usr/lib:${LD_LIBRARY_PATH:-}
  .venv/bin/python -I scripts/triage/score_l3_constructs.py
  .venv/bin/python -I scripts/triage/score_l3_constructs.py \\
      --json-out /tmp/l3.json --summary-out /tmp/l3.txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(ROOT / "src"))

from catpart.fitness import FitnessError  # noqa: E402
from catpart.fitness.l3 import dumps, render_summary, score_l3  # noqa: E402


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Score the L3 construct-coverage headline from committed artifacts."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="repo root holding docs/evidence/data and fitness/ (default: this checkout)",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="write the JSON document here (default: stdout)",
    )
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=None,
        help="write the human summary here (default: stderr)",
    )
    args = parser.parse_args(argv)

    try:
        score = score_l3(args.root)
    except FitnessError as exc:
        print(f"score-l3: error: {exc}", file=sys.stderr)
        return 1

    document = dumps(score)
    summary = render_summary(score)
    if args.json_out is None:
        sys.stdout.write(document)
        sys.stdout.flush()
    else:
        _write(args.json_out, document)
    if args.summary_out is None:
        sys.stderr.write(summary)
        sys.stderr.flush()
    else:
        _write(args.summary_out, summary)
        print(
            f"score-l3: {score.resolved}/{score.total} resolved "
            f"(summary: {args.summary_out})",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
