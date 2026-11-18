/* The in-browser sanity gate — the §3.4 mirror of `_score_export`
   (src/catpart/fitness/runner.py:309-329, the law): same check order
   (empty → manifold → finite plausible bbox → degenerate ≤ 0), same
   constants, same failed-check vocabulary, bbox recorded null when the
   plausibility check fails (non-finite floats must not reach the
   displayed record). Spec: docs/specs/phase5-viewer-spec.md §3.4 —
   "The page's in-browser gate reimplements `_score_export` exactly".
   No margin is declared or hard-coded here: the V5 margin declaration
   is a separate, owner-approved artifact (§3.4) and this display is
   rate-agnostic. Drift detector for V5: the per-file per-check outcome
   this function returns is what the reproduction run compares against
   the Python fitness records. */

/* The gate's failed-check vocabulary and constants, verbatim from
   runner.py (MAX_DEGENERATE_TRIANGLES pins the G3 F7 rate: 0 on every
   clean-store soup). */
export const MAX_DEGENERATE_TRIANGLES = 0;
export const CHECK_EMPTY_MESH = "empty-mesh";
export const CHECK_NOT_MANIFOLD = "not-manifold";
export const CHECK_NONFINITE_BBOX = "nonfinite-bbox";
export const CHECK_DEGENERATE = "degenerate-triangles";

export const L2_PASS = "pass";
export const L2_FAIL = "fail";

/* runner.py::_bbox_plausible — finite bounds with min <= max on every
   axis (the "plausible" part of the L2 bounding-box check). */
export function bboxPlausible(bbox) {
  const lo = bbox.min;
  const hi = bbox.max;
  const all = [lo[0], lo[1], lo[2], hi[0], hi[1], hi[2]];
  for (let i = 0; i < 6; i++) {
    if (!Number.isFinite(all[i])) return false;
  }
  for (let axis = 0; axis < 3; axis++) {
    if (lo[axis] > hi[axis]) return false;
  }
  return true;
}

/* runner.py::_score_export — the gate, check order and field shape
   verbatim. `summary` is the WASM decode_export summary object (the
   export-summary-v1 fields: vertex_count, triangle_count,
   degenerate_triangle_count, mesh.manifold, bounding_box). Returns the
   runner's l2 record shape: status, failed_check, the three counts,
   bounding_box (null when implausible). */
export function scoreExport(summary) {
  const mesh = summary.mesh;
  const bbox = summary.bounding_box;
  let failedCheck;
  if (summary.vertex_count < 1 || summary.triangle_count < 1) {
    failedCheck = CHECK_EMPTY_MESH;
  } else if (!mesh.manifold) {
    failedCheck = CHECK_NOT_MANIFOLD;
  } else if (!bboxPlausible(bbox)) {
    failedCheck = CHECK_NONFINITE_BBOX;
  } else if (summary.degenerate_triangle_count > MAX_DEGENERATE_TRIANGLES) {
    failedCheck = CHECK_DEGENERATE;
  } else {
    failedCheck = null;
  }
  return {
    status: failedCheck === null ? L2_PASS : L2_FAIL,
    error_class: null,
    error: null,
    failed_check: failedCheck,
    vertex_count: summary.vertex_count,
    triangle_count: summary.triangle_count,
    degenerate_triangle_count: summary.degenerate_triangle_count,
    bounding_box: bboxPlausible(bbox) ? bbox : null,
  };
}
