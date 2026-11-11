"""Stage-3a corpus A/B gate (G6 #34): the locator recovery extension.

Replays the fitness L2 seam (``build_export`` + the runner's sanity
gate, the exact per-part record ``catpart-fitness`` scores) over the L2
population — manifest ``kind=part``, splits dev + held-out — and diffs
every part's outcome against the stage-1 census CSV's classification
(docs/evidence/data/l2-grind-classification.csv, ``replay_class``)
under the stage-3a gate STATED IN ADVANCE (dispatch-recipes hard rule:
any unexplained delta is a stop-and-re-root-cause gate):

- exactly the 135 missing-store parts become located: the census's
  36 clean -> pass (or a named sanity failure), the 70 composite /
  21 poolless / 8 refs-beyond -> undecoded-variant;
- the 29 malformed-store-header parts reclassify to undecoded-variant
  (post-fix composite 11 / poolless 18) — the class goes to 0;
- the 178 genuinely store-less parts REMAIN missing-geometry-store;
- every other part's class is unchanged (76 pass, 963 undecoded-
  variant, 61 held-out undecoded-variant).

Expected dev totals: pass 112, undecoded-variant 1,152,
missing-geometry-store 178, malformed-store-header 0.

It also verifies, on the moved parts: (a) the recovery provenance is
recorded (``store_recovery`` on passing summaries, the probe/law suffix
on failing details, exactly the census's probe/family); (b) L1
stability — with ``--inspect-baseline-python`` (a venv python whose
``catpart`` resolves to the pre-stage-3a code, e.g. the main checkout's
editable install), the live ``build_inspect_report`` fields
(detected_version, kind, container_names) must equal the baseline
interpreter's over the same parts: the locate law does not touch
container inventory. Without it the check is skipped (the committed
baseline report predates unrelated container-table parse refinements,
so comparing live inspect against it shows pre-existing drift, not
stage-3a deltas).

Run: .venv/bin/python -I scripts/triage/check_locator_recovery_ab.py
[--corpus-root PATH] [--census PATH] [--inspect-baseline-python PY]

Deterministic: sorted-manifest order; the verdict is printed with the
per-part delta table; exit 0 = gate pass, exit 1 = unexplained delta.
"""
import argparse
import csv
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
CENSUS = ROOT / "docs" / "evidence" / "data" / "l2-grind-classification.csv"
BASELINE_REPORT = ROOT / "fitness" / "reports" / "20261110T172440Z-3ea53d.json"

sys.path.insert(0, str(ROOT / "src"))

from catpart.fitness.runner import _score_export  # noqa: E402
from catpart.geometry import build_export  # noqa: E402
from catpart.geometry.errors import ExportError  # noqa: E402

RECOVERY_SUFFIX = "[store recovered via"
TAIL_LAWS = {"dword8-overshoot": "overshoot", "padded-tail": "padded"}


def expected_outcome(row):
    """The stage-3a gate's expected outcome for one census row.

    Returns ``(error_class_or_None, may_sanity_fail)``. ``may_sanity_fail``
    marks the census-clean recoveries: their export classification is
    pass or a named sanity failure (failed_check), never a classified
    error (the stage-1 table's near-term L2 value).
    """
    root = row["root_class"]
    if root == "pass":
        return None, False
    if root in ("composite-space", "refs-beyond-pool", "poolless-store",
                "undecoded-variant"):
        return "undecoded-variant", False
    if root == "malformed-store-header":
        # L4 riding the same change: both G1 tail families recover.
        return "undecoded-variant", False
    if root == "missing-store":
        if row["recovery_probe"].endswith("-located"):
            cls = row["recovery_store_class"]
        elif row["recovery_malform_family"]:
            cls = row["recovery_postfix_class"]
        else:
            return "missing-geometry-store", False
        if cls == "clean":
            return None, True
        return "undecoded-variant", False
    raise AssertionError(f"unexpected census root class {root!r}")


def expected_provenance(row):
    """The (container, tail_law) the recovery must record, or None."""
    root = row["root_class"]
    if root == "malformed-store-header":
        return "stdcont", TAIL_LAWS[row["malform_family"]]
    if root != "missing-store":
        return None
    probe = row["recovery_probe"]
    if probe.endswith("-malformed"):
        law = TAIL_LAWS[row["recovery_malform_family"]]
    else:
        law = "shipped"
    return probe.split("-")[0], law


def measure_part(file_path, out_path):
    """The fitness seam's per-part record + the raw summary provenance."""
    try:
        summary = build_export(file_path, out_path)
    except ExportError as exc:
        return {
            "status": "fail",
            "error_class": exc.error_class,
            "error": exc.detail,
            "failed_check": None,
            "recovery": None,
            "vertex_count": None,
            "triangle_count": None,
        }
    record = _score_export(summary)
    record["recovery"] = summary.get("store_recovery")
    record["error"] = None
    return record


def inspect_fields(file_path):
    """The live code's inspect fields for one part.

    ``container_names`` mirrors the runner's derivation
    (``_per_file_record``): unique names, first-occurrence order."""
    from catpart.cli import build_inspect_report

    report = build_inspect_report(file_path)
    names: list[str] = []
    for record in report["containers"]:
        name = record["name"]
        if name not in names:
            names.append(name)
    return {
        "detected_version": report["detected_version"],
        "kind": report["kind"],
        "container_names": names,
    }


def observed_provenance(record):
    """(container, tail_law) the recorded provenance, or None."""
    if record["status"] == "pass":
        got = record["recovery"]
        return None if got is None else (got["container"], got["tail_law"])
    err = record["error"] or ""
    if RECOVERY_SUFFIX in err:
        import re

        m = re.search(
            r"recovered via the (\w+) probe, (\w+) tail law", err
        )
        if m:
            return m.group(1), m.group(2)
    return None


_INSPECT_PROBE = (
    "import csv, json, sys\n"
    "from pathlib import Path\n"
    "from catpart.cli import build_inspect_report\n"
    "manifest, corpus_root = sys.argv[1], Path(sys.argv[2])\n"
    "shas = set(sys.argv[3].split(','))\n"
    "out = {}\n"
    "for r in csv.DictReader(open(manifest)):\n"
    "    if r['kind'] != 'part' or r['sha256'][:16] not in shas:\n"
    "        continue\n"
    "    rep = build_inspect_report(corpus_root / r['local_path'])\n"
    "    out[r['sha256'][:16]] = {\n"
    "        'detected_version': rep['detected_version'],\n"
    "        'kind': rep['kind'],\n"
    "        'container_names': [c['name'] for c in rep['containers']],\n"
    "    }\n"
    "print(json.dumps(out))\n"
)


def inspect_fields_batch(baseline_python, manifest, corpus_root, shas):
    """Run build_inspect_report under the baseline interpreter (one
    subprocess for the whole batch) and return {sha16: fields}. The
    interpreter's own editable install resolves ``catpart`` — never
    this worktree's src."""
    import subprocess

    proc = subprocess.run(
        [str(baseline_python), "-I", "-c", _INSPECT_PROBE, str(manifest),
         str(corpus_root), ",".join(sorted(shas))],
        capture_output=True, text=True, timeout=600, check=True,
    )
    return json.loads(proc.stdout)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--corpus-root", default=str(ROOT))
    ap.add_argument("--census", default=str(CENSUS))
    ap.add_argument("--manifest", default=str(MANIFEST))
    ap.add_argument(
        "--inspect-baseline-python",
        default=None,
        help="venv python whose catpart resolves to the pre-stage-3a "
        "code; enables the L1 inspect A/B over the moved parts",
    )
    args = ap.parse_args()
    corpus_root = Path(args.corpus_root)
    census = {r["sha256"]: r for r in csv.DictReader(open(args.census))}

    with open(args.manifest) as fh:
        rows = [r for r in csv.DictReader(fh) if r["kind"] == "part"]
    rows.sort(key=lambda r: r["sha256"])

    transitions = Counter()
    deltas = []
    moved = []  # (census_row, seam record) for the 135 + 29
    with tempfile.TemporaryDirectory(prefix="catpart-ab-l2-") as scratch:
        scratch = Path(scratch)
        for row in rows:
            census_row = census.get(row["sha256"])
            if census_row is None:
                deltas.append((row["sha256"][:16], "NOT-IN-CENSUS"))
                continue
            record = measure_part(
                corpus_root / row["local_path"],
                scratch / f"{row['sha256'][:16]}.ply",
            )
            exp_class, may_sanity = expected_outcome(census_row)
            if exp_class is None:
                if may_sanity:
                    ok = record["status"] == "pass" or (
                        record["status"] == "fail"
                        and record["failed_check"] is not None
                    )
                else:
                    ok = record["status"] == "pass"
            else:
                ok = (
                    record["status"] == "fail"
                    and record["error_class"] == exp_class
                    and record["failed_check"] is None
                )
            base_class = census_row["replay_class"]
            key = (
                record["error_class"] or record["failed_check"]
                if record["status"] == "fail"
                else None
            )
            transitions[(base_class, record["status"], key)] += 1
            if not ok:
                deltas.append((
                    row["sha256"][:16], base_class, record["status"],
                    record["error_class"], record["failed_check"],
                    (record["error"] or "")[:160],
                ))
            if census_row["root_class"] in ("missing-store", "malformed-store-header") and (
                census_row["root_class"] != "missing-store"
                or census_row["recovery_probe"] != "none"
            ):
                moved.append((census_row, record))

    print("== stage-3a corpus A/B (L2 population, kind=part)")
    print(f"  parts: {len(rows)}")
    print("  transitions (census replay_class -> seam outcome):")
    for key, n in sorted(transitions.items(), key=lambda kv: str(kv[0])):
        print(f"    {key[0]:24s} -> {key[1]:4s} {str(key[2]):24s} {n}")
    print(f"  moved parts measured: {len(moved)} (expected 164)")

    # the clean recoveries' export classifications (the near-term L2 value)
    sanity_outcomes = Counter()
    clean_records = []
    for census_row, record in moved:
        cls = census_row["recovery_store_class"] or census_row["recovery_postfix_class"]
        if cls == "clean":
            clean_records.append((census_row, record))
            if record["status"] == "pass":
                sanity_outcomes["pass"] += 1
            else:
                sanity_outcomes[f"sanity:{record['failed_check']}"] += 1
    print(f"  clean recoveries: {len(clean_records)} (expected 36); "
          f"outcomes: {dict(sanity_outcomes)}")
    for census_row, record in clean_records:
        print(f"    {census_row['sha256'][:16]} {record['status']:4s} "
              f"v={record['vertex_count']} t={record['triangle_count']} "
              f"{record['failed_check'] or ''}")

    # provenance recording on the moved parts
    prov = Counter()
    prov_bad = []
    for census_row, record in moved:
        exp = expected_provenance(census_row)
        got = observed_provenance(record)
        if exp is None:
            prov["unrecovered"] += 1
        elif got == exp:
            prov[f"{got[0]}/{got[1]}"] += 1
        else:
            prov_bad.append((census_row["sha256"][:16], f"expected {exp}, got {got}"))
    print(f"  provenance: {dict(prov)}")
    for item in prov_bad[:20]:
        print("    provenance mismatch:", item)

    # L1 stability: live inspect vs (a) the baseline interpreter's
    # inspect when given, else (b) the committed baseline report's
    # per-file inspect fields (pre-stage-3a artifact).
    manifest_paths = {r["sha256"]: r["local_path"] for r in rows}
    if args.inspect_baseline_python:
        base_fields = inspect_fields_batch(
            Path(args.inspect_baseline_python), args.manifest, corpus_root,
            {census_row["sha256"][:16] for census_row, _ in moved},
        )
        base_label = "vs baseline interpreter"
    else:
        baseline = json.load(open(BASELINE_REPORT))
        base_fields = {r["sha256"][:16]: {
            "detected_version": r.get("detected_version"),
            "kind": r.get("kind"),
            "container_names": r.get("container_names"),
        } for r in baseline["files"]}
        base_label = "vs the committed baseline report"
    insp_bad = []
    for census_row, _record in moved:
        sha16 = census_row["sha256"][:16]
        base = base_fields.get(sha16)
        if base is None:
            insp_bad.append((sha16, "no baseline inspect fields"))
            continue
        live = inspect_fields(corpus_root / manifest_paths[census_row["sha256"]])
        for field in ("detected_version", "kind", "container_names"):
            if live[field] != base.get(field):
                insp_bad.append((sha16, field, base.get(field), live[field]))
    print(f"  L1 inspect stability over the {len(moved)} moved parts "
          f"({base_label}): "
          f"{'OK' if not insp_bad else f'{len(insp_bad)} MISMATCH(ES)'}")
    for item in insp_bad[:20]:
        print("   ", item)

    exp_totals = {"pass": 112, "undecoded-variant": 1152,
                  "missing-geometry-store": 178, "malformed-store-header": 0}
    obs_totals = Counter()
    for (_base, status, key), n in transitions.items():
        if status == "pass":
            obs_totals["pass"] += n
        elif key:
            obs_totals[key] += n
    print(f"  totals: observed {dict(obs_totals)}")
    print(f"  totals: expected {exp_totals}")

    failed = bool(deltas or prov_bad or insp_bad)
    for key, n in exp_totals.items():
        if obs_totals.get(key, 0) != n:
            print(f"  GATE FAIL: total {key} observed {obs_totals.get(key, 0)} "
                  f"!= {n}")
            failed = True
    if failed:
        print(f"\n  GATE FAIL: {len(deltas)} unexplained classification "
              f"delta(s)")
        for d in deltas[:40]:
            print("   ", d)
        sys.exit(1)
    print("\n  GATE PASS: every part matches the stage-3a stated delta")


main()
