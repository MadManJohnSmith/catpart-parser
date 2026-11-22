#!/usr/bin/env python3
"""W6 laya domain calibrator: fit + calibrate on the labeled parts (official
corpus dev + Submarino eval), report per-class accuracy/F1 on the
``route == "auto"`` / ``probabilities`` gate — never raw ``confidence`` —
and compare against the deterministic router (``router.py``) on its residue.

Rewritten against laya 0.5.2's real API: ``VegaAgent.fit(rows, questions)``
takes rows ``{"state": <flat features>, "gold": {"<qid>": <label>}}`` and
returns per-question heads whose serving decision is ``report[qid]
["used_by_auto"]``. ``predict``/``predict_batch`` return per-question
answers with ``route`` ("auto" when the conformal band holds one option at
the target precision), ``probabilities`` and ``prediction_set`` — that
``route`` is the gate this script reports on.

Split: official dev = fit/calibrate, official held-out + Submarino = eval
(distribution shift is the interesting case: train official-only, test
Submarino too). The Submarino rows carry no mesh-* fields (None), which
the state renders as "na".

Jev: pass ``--jev-key-file`` (OpenCode System One route B, model
``jev-1.13-free``) to also score the router-residue records with Jev.
Without a key the script says so explicitly and skips — probabilities are
never invented. That code path ships untested (no key on this host yet).

Usage:
  USE_TF=0 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 python -B \\
      scripts/triage/w6_laya_fit.py --features <features.jsonl> \\
      [--out-dir ~/.local/state/catpart-parser/w6-laya]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/triage"))

import router  # noqa: E402

QUESTIONS_BASE = {
    "instructions": (
        "A CATPart binary was parsed by a reverse-engineered parser. "
        "Classify the outcome into exactly one failure family."
    ),
}
FAMILY_DESC = {
    "pass": (
        "parsed clean: real solid mesh (MESH), no failed check, no defect "
        "expected in a faithful render"
    ),
    "check:empty-mesh": (
        "no triangles decoded but display points/segments exist "
        "(wireframe-only display, no surface decoded)"
    ),
    "check:not-manifold": (
        "mesh decoded but fails the manifold check (open shell, boundary "
        "edges, duplicate triangles)"
    ),
    "error:undecoded-variant": (
        "real geometry exists but an undecoded container/record variant "
        "blocked extraction"
    ),
    "error:missing-geometry-store": (
        "file carries no geometry store at all (BLANK, junk or wrong kind)"
    ),
    "fail-unclassified": (
        "failed for a reason the other families do not cover (e.g. only "
        "degenerate triangles, no evaluable surface)"
    ),
}

JEV_URL = "https://opencode.ai/inference/systemone/v1/systemone"
JEV_MODEL = "jev-1.13-free"
JEV_QUESTIONS = {
    "fail_family": {
        "type": "choice",
        "instructions": QUESTIONS_BASE["instructions"],
        "criteria": FAMILY_DESC,
    },
}


def laya_state(rec: dict) -> dict:
    """Feature record -> compact flat state for the engine."""
    return {
        "source": rec["source"],
        "version_family": rec["version_family"],
        "classification": rec["classification"] or "unknown",
        "container_count": len(rec["containers"]),
        "has_CGMGeom": "CGMGeom" in rec["containers"],
        "has_CATPrtCont": "CATPrtCont" in rec["containers"],
        "error_class": rec["error_class"] or "none",
        "failed_check": rec["failed_check"] or "none",
        "open_kind": rec["open_class"] or "none",
        "vertex_count": rec["vertex_count"] or 0,
        "triangle_count": rec["triangle_count"] or 0,
        "degenerate_triangle_count": rec["degenerate_triangle_count"] or 0,
        "display_points": rec["display_points"] or 0,
        "display_segments": rec["display_segments"] or 0,
        "mesh_manifold": rec["mesh_manifold"] if rec["mesh_manifold"] is not None else "na",
        "mesh_closed": rec["mesh_closed"] if rec["mesh_closed"] is not None else "na",
        "boundary_edge_count": rec["boundary_edge_count"] or 0,
        "size_bytes": rec["size_bytes"] or 0,
        "warning_count": len(rec["warnings"]),
        "warnings": rec["warnings"],
        "seconds": rec["seconds"] or 0.0,
    }


def route_record(rec: dict) -> dict:
    """Feature record -> router.make_record input."""
    return router.make_record(
        path=rec["path"],
        source="submarine-m1" if rec["source"] == "submarine" else "open-rate",
        error_class=rec["error_class"] or "",
        failed_check=rec["failed_check"] or "",
        l2_status=rec["l2_status"] or "",
        open_kind=rec["open_class"] or "",
        warnings=rec["warnings"],
        triangle_count=rec["triangle_count"] or 0,
        point_count=rec["vertex_count"] or 0,
        display_points=rec["display_points"] or 0,
        display_segments=rec["display_segments"] or 0,
        size_bytes=rec["size_bytes"],
        report_kind=rec["report_kind"],
    )


def jev_answer(key: str, state_text: str, timeout: int = 60) -> dict | None:
    """One System One route-B call; returns the raw answers dict or None."""
    body = json.dumps(
        {"model": JEV_MODEL, "state": state_text, "questions": JEV_QUESTIONS}
    ).encode()
    request = urllib.request.Request(
        JEV_URL,
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode())
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(f"  jev call failed: {exc}", flush=True)
        return None
    answers = payload.get("answers") or {}
    q = answers.get("fail_family") or {}
    probs = q.get("probabilities") or {}
    return {"choice": q.get("choice"), "probabilities": probs, "usage": payload.get("usage")}


def prf(confusion: dict[str, Counter], cls: str) -> tuple[float, float, float]:
    # a predicted class with zero truth rows has no entry under its own
    # key — P=0/R=0 is the honest score for it
    tp = confusion.get(cls, Counter())[cls]
    fp = sum(c[cls] for k, c in confusion.items() if k != cls)
    fn = sum(confusion.get(cls, Counter()).values()) - tp
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f1


def evaluate(name: str, subset: list[dict], agent, questions: dict, out_dir: Path) -> dict:
    """Gated (route==auto + probabilities) and ungated accuracy on a subset."""
    confusion: dict[str, Counter] = {}
    ungated_ok = 0
    gated = 0
    verdicts_path = out_dir / f"w6-verdicts-{name}.jsonl"
    with open(verdicts_path, "w", encoding="utf-8") as vout:
        chunk = 16
        for start in range(0, len(subset), chunk):
            part = subset[start : start + chunk]
            preds = agent.predict_batch([laya_state(r) for r in part], questions)
            for r, pred in zip(part, preds):
                ans = (pred or {}).get("answers", {}).get("fail_family") or {}
                probs = ans.get("probabilities") or {}
                best = max(probs, key=probs.get) if probs else None
                truth = r["fail_family"]
                route = ans.get("route")
                if route == "auto" and probs:
                    confusion.setdefault(truth, Counter())[best or "?"] += 1
                else:
                    gated += 1
                ungated_ok += int(best == truth)
                vout.write(
                    json.dumps(
                        {
                            "path": r["path"],
                            "truth": truth,
                            "choice": ans.get("choice"),
                            "route": route,
                            "abstain": ans.get("abstain"),
                            "confidence": ans.get("confidence"),
                            "probs": probs,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
            print(
                f"  [{name}] {start + len(part)}/{len(subset)} "
                f"(last: {part[-1]['path']}, route={route})",
                flush=True,
            )
    correct = sum(c[k] for k, c in confusion.items())
    total = sum(sum(c.values()) for c in confusion.values())
    acc = correct / total if total else 0.0
    print(f"\n== {name}: gated acc={acc:.4f} on {total} auto-routed ({gated} gated out) ==", flush=True)
    print(f"   ungated argmax acc={ungated_ok / len(subset):.4f} on all {len(subset)}", flush=True)
    classes = sorted({k for c in confusion.values() for k in c} | set(confusion))
    per_class = {}
    for cls in classes:
        p, r_, f1 = prf(confusion, cls)
        per_class[cls] = {"P": p, "R": r_, "F1": f1, "support": sum(confusion.get(cls, Counter()).values())}
        print(f"  {cls:34s} P={p:.3f} R={r_:.3f} F1={f1:.3f} n={per_class[cls]['support']}", flush=True)
    return {
        "accuracy_gated": acc,
        "auto_routed": total,
        "gated_out": gated,
        "accuracy_ungated_argmax": ungated_ok / len(subset) if subset else 0.0,
        "n": len(subset),
        "per_class": per_class,
        "confusion": {t: dict(c) for t, c in confusion.items()},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--features", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path.home() / ".local/state/catpart-parser/w6-laya")
    ap.add_argument("--jev-key-file", type=Path, default=None)
    ap.add_argument("--jev-max", type=int, default=60)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    import laya  # USE_TF=0 is set by the caller

    records = [
        json.loads(line)
        for line in args.features.read_text().splitlines()
        if line.strip()
    ]
    labeled = [r for r in records if r["l2_status"] in ("pass", "fail")]
    print(f"labeled records: {len(labeled)}", flush=True)
    print("fail_family dist:", dict(Counter(r["fail_family"] for r in labeled)), flush=True)

    train = [r for r in labeled if r["split"] == "dev"]
    print(f"train(dev)={len(train)} eval(held-out)={sum(1 for r in labeled if r['split'] == 'held-out')} "
          f"eval(sub)={sum(1 for r in labeled if r['split'] == 'submarine')}", flush=True)

    classes = sorted({r["fail_family"] for r in labeled})
    questions = {
        "fail_family": {
            "type": "choice",
            "instructions": QUESTIONS_BASE["instructions"],
            "criteria": {c: FAMILY_DESC.get(c, f"failure family {c}") for c in classes},
        }
    }

    agent = laya.VegaAgent(device="cpu")
    rows = [{"state": laya_state(r), "gold": {"fail_family": r["fail_family"]}} for r in train]
    t0 = time.time()
    report = agent.fit(rows, questions)
    print(f"fit done in {time.time() - t0:.0f}s", flush=True)
    print(json.dumps(report, indent=1, default=str)[:2000], flush=True)
    try:
        agent.save_calibration(str(args.out_dir / "w6-calibration.json"))
    except Exception as exc:  # calibration save is best-effort provenance
        print(f"save_calibration failed: {exc}", flush=True)

    results = {}
    for name, subset in (
        ("held-out", [r for r in labeled if r["split"] == "held-out"]),
        ("submarine", [r for r in labeled if r["split"] == "submarine"]),
    ):
        if subset:
            results[name] = evaluate(name, subset, agent, questions, args.out_dir)

    # Deterministic-router residue on the same records: laya's arbitration target.
    residue, routed = [], 0
    for r in labeled:
        bucket = router.route(route_record(r))
        if bucket is None:
            residue.append(r)
        else:
            routed += 1
    print(f"\nrouter: {routed} routed deterministically, {len(residue)} residue (route=None)", flush=True)
    residue_truth = Counter(r["fail_family"] for r in residue)
    print("residue truth dist:", dict(residue_truth), flush=True)

    # Jev on the residue (route B, jev-1.13-free) — only with a key file.
    jev_metrics: dict = {"skipped": "no --jev-key-file: no key on this host, probabilities not invented"}
    if args.jev_key_file:
        key = args.jev_key_file.read_text(encoding="utf-8").strip()
        if not key:
            jev_metrics = {"skipped": "empty key file"}
        else:
            ok = tot = 0
            for r in residue[: args.jev_max]:
                ans = jev_answer(key, json.dumps(laya_state(r)))
                if ans and ans["choice"]:
                    tot += 1
                    ok += int(ans["choice"] == r["fail_family"])
            jev_metrics = {"scored": tot, "accuracy": ok / tot if tot else None}
            print(f"jev on residue: {jev_metrics}", flush=True)
    else:
        print("jev: no key file — skipped (probabilities not invented)", flush=True)

    out = {
        "schema": "w6-laya-fit-2",
        "laya_version": getattr(laya, "__version__", "?"),
        "n_train": len(train),
        "fit_report": report,
        "results": results,
        "router_residue": len(residue),
        "residue_truth": dict(residue_truth),
        "jev": jev_metrics,
    }
    (args.out_dir / "laya-fit-metrics.json").write_text(json.dumps(out, indent=1))
    print(f"metrics -> {args.out_dir / 'laya-fit-metrics.json'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
