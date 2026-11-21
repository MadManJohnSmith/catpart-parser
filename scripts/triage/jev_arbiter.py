"""jev-1.13-free residue arbiter (Phase 3 P3.5, approved design B).

Only residue records — what ``router.route`` could not map — reach this
module. It asks the System One typed decision API
(``POST https://opencode.ai/inference/systemone/v1/systemone``, shape
``{model, state, questions{choice|noul|score}}``) for the three triage
decisions, reusing the transport pattern S8 measured at ~166 ms p50
(subagents/s8-decision-models-eval/eval_decisions.py).

Route criteria are the CLARIFIED ones from S8's re-run of the 20
feature-only/healthy cases (rubric_clarified_rerun.json + informe.md §4):
``known_feature_only`` is spelled out as the documented no-surface-display
family — NOT a decoding failure — and ``needs_new_re_subagent`` as a real
extraction/decoding failure. The score legend is collision-free: each
level maps to one bucket family (the original "3 no real geometry"
collided with feature-only, which is also geometry-free by design).

Hard limits (machine-shared): concurrency 2, exponential backoff on
429/5xx/transport errors with at most 3 retries, 30 s per-call timeout,
and exactly 1 retry on an invalid/parse-failing answer body. ``decide``
never raises: a failed case comes back with ``error`` set and the caller
routes it to ``needs_review`` so a triage run can never crash on the
arbiter.

Key handling: ``OPENCODE_API_KEY`` in the environment, else ``--key-file``
pointing at an EXTERNAL file (e.g. /tmp/oc_key.txt, mode 600). Keys are
never hardcoded, never committed, never read from inside the repo.
Without a key ``resolve_key`` returns None and the caller falls back to
``needs_review`` (exit 0).

Only the compact JSON feature record travels to the API — never CATPart
contents.
"""

from __future__ import annotations

import json
import os
import random
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

SYSONE_URL = "https://opencode.ai/inference/systemone/v1/systemone"
MODEL = "jev-1.13-free"
UA = "opencode/2.3.2 (catpart-parser triage harness)"

CALL_TIMEOUT_S = 30
MAX_WORKERS = 2
TRANSPORT_RETRIES = 3          # 429 / 5xx / transport-level, with backoff
TRANSPORT_BACKOFF_S = (2.0, 5.0, 10.0)
PARSE_RETRIES = 1              # invalid or unparseable answer body

BUCKETS = (
    "known_seam_not_manifold",
    "known_feature_only",
    "known_not_a_catpart",
    "needs_new_re_subagent",
    "already_healthy",
)

STATE_HEADER = """You are a System-1 triage router for a CATIA V5 corpus pipeline. You see a compact JSON feature record for one .CATPart file (parsed metadata only, never the file contents). Judge it instantly: route it into exactly one bucket, decide whether deep System-2 analysis by a stronger agent is needed, and score the visual fidelity risk of a rendered 3D view.

Feature record for the file:
"""

STATE_FOOTER = "\n\nAnswer the three questions about this feature record."

# S8 clarified criteria (see module docstring): feature-only vs needs_new
# is a family distinction, not a severity guess, and the risk legend gives
# every level exactly one bucket family.
QUESTIONS = {
    "route_bucket": {
        "type": "choice",
        "instructions": "Route this file into exactly one bucket.",
        "criteria": {
            "known_seam_not_manifold": (
                "mesh topology defect that is a known, documented seam/open-shell "
                "artifact of this corpus; benign, no new investigation needed"),
            "known_feature_only": (
                "the documented no-surface-display family: the parser found only "
                "wireframe/display content (display points or curve segments) and no "
                "solid mesh is expected — this is NOT a decoding failure; healthy "
                "for this pipeline"),
            "known_not_a_catpart": (
                "not a genuine CATIA part container (mislabeled junk, text, placeholder)"),
            "needs_new_re_subagent": (
                "a real extraction or decoding failure: the parser could not extract or "
                "decode real geometry and no documented family explains it; needs a new "
                "reverse-engineering investigation"),
            "already_healthy": (
                "parsed clean, all checks passed, and a real mesh was emitted; any "
                "warnings are documented, handled processing notes"),
        },
    },
    "escalate_to_system2": {
        "type": "noul",
        "instructions": "True only if this file needs deep System-2 analysis by a stronger model/agent.",
    },
    "visual_fidelity_risk": {
        "type": "score",
        "instructions": "Expected risk that a rendered 3D view misrepresents the real part.",
        "criteria": [
            "1 renders faithfully (clean mesh, or display-only carrier as expected)",
            "2 benign documented artifact only (seam/open-shell handled, minor quality skips)",
            "3 junk container (nothing real to render)",
            "4 large visual loss (geometry missing or undecoded)",
            "5 severe visible holes (a defect leaves visible gaps)",
        ],
    },
}

_RECORD_FIELDS = (
    "path", "size_bytes", "error_class", "failed_check", "l2_status",
    "open_kind", "warnings", "triangle_count", "point_count",
    "display_points", "display_segments",
)


@dataclass(frozen=True)
class Decision:
    """One arbiter verdict, or an ``error`` if every attempt failed."""

    bucket: str
    escalate: bool
    risk: int
    confidence: float
    latency_ms: int
    list_cost_usd: float
    attempts: int
    error: str


def resolve_key(key_file: str | None = None) -> str | None:
    """Env var first, then an external key file. None = no key available."""
    key = os.environ.get("OPENCODE_API_KEY", "").strip()
    if key:
        return key
    if key_file:
        path = Path(key_file).expanduser()
        try:
            key = path.read_text().strip()
        except OSError:
            return None
        return key or None
    return None


def build_state(rec: dict) -> str:
    """The informational state: header + compact feature-record JSON."""
    payload = {field: rec.get(field) for field in _RECORD_FIELDS}
    return STATE_HEADER + json.dumps(payload, ensure_ascii=False) + STATE_FOOTER


def normalize_answers(answers: dict) -> dict:
    """Typed answers -> {bucket, escalate, risk, confidence}; ValueError on
    any shape drift (drives the single parse retry)."""
    a_route = answers.get("route_bucket") or {}
    bucket = str(a_route.get("choice", "")).strip()
    if bucket not in BUCKETS:
        raise ValueError(f"bad route_bucket: {bucket!r}")
    probs = a_route.get("probabilities") or {}
    conf = a_route.get("confidence")
    if conf is None:
        conf = probs.get(bucket, 0.0)
    esc_prob = float((answers.get("escalate_to_system2") or {}).get("noul", 0.0))
    risk = int(round(float((answers.get("visual_fidelity_risk") or {}).get("score", 0.0)))) + 1
    risk = max(1, min(5, risk))
    return {"bucket": bucket, "escalate": esc_prob >= 0.5,
            "risk": risk, "confidence": float(conf)}


def _post(url: str, key: str, body: dict, timeout_s: int) -> tuple[bool, int, str, int]:
    """One HTTP POST; (ok, status, body_text, latency_ms). Status -1 =
    transport-level failure (DNS, refused, timeout)."""
    t0 = time.perf_counter()
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "User-Agent": UA, "x-opencode-session": "ses_" + uuid.uuid4().hex[:24]})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            return True, r.status, r.read().decode(), int((time.perf_counter() - t0) * 1000)
    except urllib.error.HTTPError as e:
        return False, e.code, e.read().decode(errors="replace"), int((time.perf_counter() - t0) * 1000)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return False, -1, str(e), int((time.perf_counter() - t0) * 1000)


def decide(key: str, rec: dict) -> Decision:
    """Arbitrate one record. Retries: 3 with backoff on 429/5xx/transport,
    1 on an unparseable body; never raises."""
    body = {"model": MODEL, "state": build_state(rec), "questions": QUESTIONS}
    transport_retries = 0
    parse_retries = 0
    attempts = 0
    latency_ms = 0
    list_cost = 0.0
    while True:
        attempts += 1
        ok, status, payload, latency_ms = _post(SYSONE_URL, key, body, CALL_TIMEOUT_S)
        if not ok:
            if status in (429, 500, 502, 503, 504, -1) and transport_retries < TRANSPORT_RETRIES:
                time.sleep(TRANSPORT_BACKOFF_S[transport_retries] + random.uniform(0, 1))
                transport_retries += 1
                continue
            return Decision("", False, 0, 0.0, latency_ms, 0.0, attempts,
                            f"HTTP {status}: {payload[:200]}")
        try:
            data = json.loads(payload)
            parsed = normalize_answers(data["answers"])
        except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
            if parse_retries < PARSE_RETRIES:
                parse_retries += 1
                continue
            return Decision("", False, 0, 0.0, latency_ms, 0.0, attempts,
                            f"answer parse: {exc}")
        usage = data.get("usage") or {}
        list_cost = float(usage.get("cost", 0.0) or 0.0)
        return Decision(parsed["bucket"], parsed["escalate"], parsed["risk"],
                        parsed["confidence"], latency_ms, list_cost, attempts, "")


def decide_all(key: str, records: list[dict],
               progress=None) -> list[Decision]:
    """Arbitrate records at concurrency 2 (shared-machine limit), keeping
    input order. ``progress(done, total)`` is optional."""
    decisions: list[Decision | None] = [None] * len(records)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(decide, key, rec): i for i, rec in enumerate(records)}
        done = 0
        for fut, i in futures.items():
            decisions[i] = fut.result()
            done += 1
            if progress:
                progress(done, len(records))
    return decisions  # type: ignore[return-value]
