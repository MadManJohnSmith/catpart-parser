#!/usr/bin/env python3
"""Smoke test for the OpenCode System One route used by Jev.

Reads the key from OPENCODE_API_KEY or --key-file (never prints it), sends a
tiny typed request to the System One endpoint and prints the parsed answers,
latency and list cost. With --model jev-1.13 it also exercises the paid
route (a 402 is the expected result when the account has no credits).

Usage:
  python3 jev_opencode_smoke.py --key-file /tmp/oc_key.txt
  python3 jev_opencode_smoke.py --key-file /tmp/oc_key.txt --model jev-1.13
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

URL = "https://opencode.ai/inference/systemone/v1/systemone"
DEFAULT_MODEL = "jev-1.13-free"

STATE = (
    "Smoke test only. A CATPart file named demo.CATPart parsed cleanly: "
    "8 vertices, 12 triangles, manifold mesh, no warnings. It is a real "
    "part and the render is expected to be faithful."
)

QUESTIONS = {
    "route_bucket": {
        "type": "choice",
        "instructions": "Route this file into exactly one bucket.",
        "criteria": {
            "already_healthy": "parsed clean, real mesh, no unexplained warnings",
            "known_feature_only": "display/wireframe only by design, no solid expected",
            "needs_new_re_subagent": "real extraction or decoding failure",
        },
    },
    "escalate_to_system2": {
        "type": "noul",
        "instructions": "True only if this file needs deeper System-2 analysis.",
    },
    "visual_fidelity_risk": {
        "type": "score",
        "instructions": "Expected risk that a rendered view misrepresents the part.",
        "criteria": [
            "1 renders faithfully",
            "2 benign documented artifact",
            "3 nothing real to render",
            "4 large visual loss",
            "5 severe visible holes",
        ],
    },
}


def resolve_key(args) -> str | None:
    key = os.environ.get("OPENCODE_API_KEY", "").strip()
    if key:
        return key
    if args.key_file:
        try:
            with open(args.key_file, encoding="utf-8") as fh:
                return fh.read().strip() or None
        except OSError as exc:
            print(f"key file error: {exc}", file=sys.stderr)
    return None


def post(key: str, model: str, timeout: int) -> tuple[int, str, int]:
    body = json.dumps(
        {"model": model, "state": STATE, "questions": QUESTIONS}
    ).encode()
    request = urllib.request.Request(
        URL,
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "opencode/2.3.2 (jev-opencode smoke test)",
            "x-opencode-session": "ses_" + uuid.uuid4().hex[:24],
        },
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode(), int(
                (time.perf_counter() - started) * 1000
            )
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(errors="replace"), int(
            (time.perf_counter() - started) * 1000
        )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return -1, str(exc), int((time.perf_counter() - started) * 1000)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--key-file", default=None)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    key = resolve_key(args)
    if not key:
        print(
            "no OpenCode key: set OPENCODE_API_KEY or pass --key-file",
            file=sys.stderr,
        )
        return 1

    status, payload, latency_ms = post(key, args.model, args.timeout)
    print(f"model={args.model} status={status} latency_ms={latency_ms}")
    if status != 200:
        print(payload[:400].replace("\n", " "))
        return 1
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        print("invalid JSON body")
        return 1
    answers = data.get("answers") or {}
    route = answers.get("route_bucket") or {}
    noul = answers.get("escalate_to_system2") or {}
    score = answers.get("visual_fidelity_risk") or {}
    usage = data.get("usage") or {}
    print(
        json.dumps(
            {
                "choice": route.get("choice"),
                "confidence": route.get("confidence"),
                "escalate": noul.get("noul"),
                "score_0based": score.get("score"),
                "risk_1based": (
                    None
                    if score.get("score") is None
                    else int(round(float(score["score"]))) + 1
                ),
                "usage_cost_usd": usage.get("cost", 0.0),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
