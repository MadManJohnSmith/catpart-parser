"""Deterministic triage router (Phase 3 P3.5, approved design B).

The S8 decision-models eval (subagents/s8-decision-models-eval/informe.md)
showed the corpus triage GT is derivable from ``error_class`` /
``failed_check`` alone, so known classes are routed by this table with no
model, and only the ambiguous residue goes to the jev arbiter
(``jev_arbiter.py``). That also removes jev's measured failure mode by
construction: its feature-only -> needs_new confusion can no longer fire
because that class never reaches the model.

The table mirrors S8's GT_RULES exactly (its rubric, informe.md §2):
severity 1 = no known risk, 2 = benign documented artifact, 3 = no real
geometry, 4 = high visual loss. ``escalate`` mirrors the rubric too: every
known defect bucket escalates except the two healthy families.

Residue contract: ``route`` returns ``None`` exactly when the record's
evidence cannot be mapped to a table row with internal consistency. The
reasons, each pinned by a test:

- ``class_outside_table`` — resolved class is not in the table
  (``degenerate-triangles``, ``no-evaluable-surface``, ``unknown``, any
  future class). The table only claims what S8 validated.
- ``pass_with_warnings`` — a passed file carrying warnings. S8's GT for
  ``pass`` required the warning-free subset; warned passes were never
  GT-validated, and ``open-shell``-style warnings carry the corpus seam
  signal, so claiming ``already_healthy`` for them would be an unmeasured
  rule.
- ``pass_without_mesh`` / ``pass_without_l2`` — a pass whose evidence
  contradicts a rendered mesh (open-rate: not ``MESH`` or zero triangles;
  submarine: ``l2_status`` not ``pass``).
- ``feature_only_without_display_evidence`` — ``empty-mesh`` with neither
  display points nor segments, which contradicts the no-surface-display
  family definition (all 245 current empty-mesh rows carry points, so
  this guards future drift only).

``report kind`` is checked BEFORE the resolved class because the four
``not-a-catpart`` rows carry report class ``missing-geometry-store``
(probe_open_rate.py records the open outcome, and a non-container opens
BLANK): class-first routing would send junk to ``needs_new``.

The ``kind=unknown`` DISPLAY rows route as ``known_feature_only`` — the
display family does not depend on container kind — even though S8 excluded
them from its model-eval dataset for GT ambiguity; that exclusion was about
sampling cases for models, not about the display evidence itself.
"""

from __future__ import annotations

from dataclasses import dataclass

BUCKETS = (
    "known_seam_not_manifold",
    "known_feature_only",
    "known_not_a_catpart",
    "needs_new_re_subagent",
    "already_healthy",
)

# (bucket, escalate, risk) — S8 GT_RULES verbatim (eval_decisions.py:125).
ROUTE_TABLE = {
    "not-manifold": ("known_seam_not_manifold", True, 2),
    "undecoded-variant": ("needs_new_re_subagent", True, 4),
    "missing-geometry-store": ("needs_new_re_subagent", True, 4),
    "empty-mesh": ("known_feature_only", False, 1),
    "not-a-catpart": ("known_not_a_catpart", True, 3),
    "pass": ("already_healthy", False, 1),
}

RESIDUE_REASONS = (
    "class_outside_table",
    "pass_with_warnings",
    "pass_without_mesh",
    "pass_without_l2",
    "feature_only_without_display_evidence",
)


@dataclass(frozen=True)
class Route:
    """A deterministic table hit; ``reason`` names the table row."""

    bucket: str
    escalate: bool
    risk: int
    reason: str


def make_record(
    path: str,
    source: str,
    error_class: str = "",
    failed_check: str = "",
    l2_status: str = "",
    report_kind: str = "",
    open_kind: str = "",
    warnings: list[str] | None = None,
    triangle_count: int = 0,
    point_count: int = 0,
    display_points: int = 0,
    display_segments: int = 0,
    size_bytes: int | None = None,
) -> dict:
    """Normalized feature record the router and arbiter both consume.

    Only parsed metadata travels to the arbiter — never CATPart contents.
    For open-rate rows ``point_count``/``display_points`` are the same
    ``points`` column (a DISPLAY row has no mesh vertices), mirroring the
    S8 dataset build.
    """
    return {
        "path": path,
        "source": source,
        "error_class": error_class,
        "failed_check": failed_check,
        "l2_status": l2_status,
        "report_kind": report_kind,
        "open_kind": open_kind,
        "warnings": list(warnings or []),
        "triangle_count": triangle_count,
        "point_count": point_count,
        "display_points": display_points,
        "display_segments": display_segments,
        "size_bytes": size_bytes,
    }


def resolve_class(rec: dict) -> str:
    """The S8 class resolution: named error, else failed check, else the
    l2 verdict; a failed l2 with no named reason resolves to ``unknown``."""
    return (
        rec["error_class"]
        or rec["failed_check"]
        or ("pass" if rec["l2_status"] == "pass" else "unknown")
    )


def route(rec: dict) -> Route | None:
    """Route one normalized record, or ``None`` when it is residue."""
    # kind first: not-a-catpart rows carry class missing-geometry-store.
    if rec["report_kind"] == "not-a-catpart":
        bucket, esc, risk = ROUTE_TABLE["not-a-catpart"]
        return Route(bucket, esc, risk, "table:not-a-catpart")

    cls = resolve_class(rec)
    if cls not in ROUTE_TABLE:
        return None
    if cls == "pass":
        if rec["warnings"]:
            return None
        if rec["source"] == "open-rate":
            if rec["open_kind"] != "MESH" or rec["triangle_count"] <= 0:
                return None
        elif rec["l2_status"] != "pass":
            return None
    if cls == "empty-mesh" and rec["display_points"] <= 0 and rec["display_segments"] <= 0:
        return None
    bucket, esc, risk = ROUTE_TABLE[cls]
    return Route(bucket, esc, risk, f"table:{cls}")


def residue_reason(rec: dict) -> str:
    """Why ``route`` returned None; only meaningful for residue records."""
    if rec["report_kind"] == "not-a-catpart":
        return ""
    cls = resolve_class(rec)
    if cls not in ROUTE_TABLE:
        return "class_outside_table"
    if cls == "pass":
        if rec["warnings"]:
            return "pass_with_warnings"
        if rec["source"] == "open-rate":
            if rec["open_kind"] != "MESH" or rec["triangle_count"] <= 0:
                return "pass_without_mesh"
        elif rec["l2_status"] != "pass":
            return "pass_without_l2"
    if cls == "empty-mesh" and rec["display_points"] <= 0 and rec["display_segments"] <= 0:
        return "feature_only_without_display_evidence"
    return ""
