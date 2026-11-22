/* W22 (2026-11-22, Bloque E18) — the standard CAD-view poses, the
   pose-based orbit controller that drives them, and the client-side
   mesh components behind the viewer's Bodies section.

   A node-testable pure module over the one pinned three.js module: no
   DOM at import time — createCadOrbit touches the canvas only through
   the pointer/wheel listeners it attaches, and the frame scheduler is
   injectable so tests pump transitions synchronously
   (tests/test_viewer_cadviews.mjs).

   Why a second controller next to orbit.js: the standard-view presets
   need camera POSE control — view direction, screen-up, radius and
   target, with an eased transition between poses. site/viewer/orbit.js
   keeps its spherical angles inside a closure behind frame()/update()
   (angles are not settable from outside), and that file sits outside
   W22's exclusive edit set, so it stays untouched; viewer.js attaches
   this controller instead. The interaction grammar is the same (drag
   to orbit, wheel dolly, the 2.2x framing margin, the phi clamp) — one
   additive API on top: setMode/setPreset.

   CAD view semantics: the presets are defined in CATIA's coordinate
   axes (Z up, Y depth) — isometric (1,1,1), front (+Y), top (+Z),
   right (+X) — and mapped per display mode: part mode shows the raw
   decoded coordinates (CATIA axes), assembly mode stands the root on
   the R_X(-pi/2) basis B (spec §5.2), CATIA (x, y, z) -> (x, z, -y).
   Screen-up per preset keeps CATIA's convention: iso/front/right carry
   Z up on screen; the top view carries CATIA +Y up on screen. */

import * as THREE from "./three.module.min.js";

export const VIEW_NAMES = ["iso", "front", "top", "right"];

/* The default transition duration (ms) — short enough to read as a
   camera jump, long enough to see the rotation (CATIA's animation). */
export const VIEW_TRANSITION_MS = 280;

/* The framing margin — the exact constant orbit.js.frame uses (2.2x),
   so scripted checks see the same fit whichever controller is attached. */
export const FRAME_MARGIN = 2.2;

/* The phi clamp (orbit.js's constant): the up vector never flips. */
const PHI_MIN = 0.01;
const PHI_MAX = Math.PI - 0.01;

/* The standard CATIA views, in CATIA's coordinate axes. */
export const CATIA_VIEW_PRESETS = {
  iso: { dir: [1, 1, 1], up: [0, 0, 1] },
  front: { dir: [0, 1, 0], up: [0, 0, 1] },
  top: { dir: [0, 0, 1], up: [0, 1, 0] },
  right: { dir: [1, 0, 0], up: [0, 0, 1] },
};

/* The per-mode world mapping. "part": the raw decoded coordinates ARE
   CATIA axes. "assembly": the root basis B = R_X(-pi/2) stands the
   model up, CATIA (x, y, z) -> world (x, z, -y). */
export function catiaToWorld(v, mode) {
  if (mode === "assembly") {
    return new THREE.Vector3(v[0], v[2], -v[1]);
  }
  return new THREE.Vector3(v[0], v[1], v[2]);
}

/* One preset, resolved for a display mode: { dir, up } in world space
   (unit direction from the model's center toward the camera). */
export function resolvePreset(name, mode) {
  const preset = CATIA_VIEW_PRESETS[name];
  if (!preset) throw new Error(`unknown CAD view: ${name}`);
  return {
    dir: catiaToWorld(preset.dir, mode).normalize(),
    up: catiaToWorld(preset.up, mode).normalize(),
  };
}

/* The per-mode default up axis (the drag-orbit's turntable axis). */
export function modeUpAxis(mode) {
  return mode === "assembly"
    ? new THREE.Vector3(0, 1, 0) // B stands CATIA Z onto world Y
    : new THREE.Vector3(0, 0, 1); // raw coordinates: CATIA Z up
}

/* Pose <-> spherical conversion. A pose is { dir, up }: the direction
   target->camera and the screen-up. The spherical form is { az, pol,
   upAxis } around the up axis: pol measured from upAxis, az around it,
   measured from the reference horizontal H built below. The conversion
   is exact for dir not parallel to up (the CAD views never are: the
   top view's dir is perpendicular to its own screen-up). At the poles
   (dir parallel to upAxis) the azimuth is undefined — the previous az
   is kept so a pole-to-pole resume never rolls randomly. */
export function poseFromDirUp(dir, up, prevAz = 0) {
  const u = up.clone().normalize();
  // The reference horizontal H: the least-parallel world axis of u,
  // orthogonalized against u — deterministic for any u, degenerate
  // only when u is exactly halfway between two axes (impossible for
  // the axis-aligned CATIA ups).
  const axes = [
    new THREE.Vector3(1, 0, 0),
    new THREE.Vector3(0, 1, 0),
    new THREE.Vector3(0, 0, 1),
  ];
  let best = axes[0];
  for (const axis of axes) {
    if (Math.abs(axis.dot(u)) < Math.abs(best.dot(u))) best = axis;
  }
  const h = best.clone().addScaledVector(u, -best.dot(u)).normalize();
  const b = new THREE.Vector3().crossVectors(u, h);
  const pol = Math.acos(Math.min(1, Math.max(-1, dir.clone().normalize().dot(u))));
  const az = Math.sin(pol) < 1e-6 ? prevAz : Math.atan2(dir.dot(b), dir.dot(h));
  return { az, pol, upAxis: u };
}

/* Vector slerp (rotation between two unit vectors, shortest arc):
   used for the screen-up interpolation during a transition. The
   degenerate cases — parallel and antipodal inputs — fall back to a
   nlerp (an antipodal pair's rotation axis is undefined, so the
   fallback picks the least-parallel world axis as the swing plane;
   no preset pair among the shipped views hits it). */
export function slerpUnit(a, b, t) {
  const out = new THREE.Vector3();
  const dot = Math.min(1, Math.max(-1, a.dot(b)));
  const angle = Math.acos(dot);
  const sinAngle = Math.sin(angle);
  if (sinAngle < 1e-6) {
    out.copy(a).lerp(b, t);
    if (out.lengthSq() < 1e-12) {
      // Antipodal at the midpoint: swing through the least-parallel axis.
      const axes = [
        new THREE.Vector3(1, 0, 0),
        new THREE.Vector3(0, 1, 0),
        new THREE.Vector3(0, 0, 1),
      ];
      let best = axes[0];
      for (const axis of axes) {
        if (Math.abs(axis.dot(a)) < Math.abs(best.dot(a))) best = axis;
      }
      out.copy(best).addScaledVector(a, -best.dot(a));
    }
    return out.normalize();
  }
  const sa = Math.sin((1 - t) * angle) / sinAngle;
  const sb = Math.sin(t * angle) / sinAngle;
  out.copy(a).multiplyScalar(sa).addScaledVector(b, sb).normalize();
  return out;
}

/* The eased fraction (easeInOutQuad) the transitions run on. */
export function easeInOut(t) {
  return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
}

/* The default frame scheduler: rAF in the browser, setTimeout in node. */
function defaultScheduleFrame(cb) {
  if (typeof requestAnimationFrame === "function") {
    requestAnimationFrame(cb);
  } else {
    setTimeout(cb, 0);
  }
}

/* The client-side mesh components: connected triangle groups over the
   SHARED VERTEX indices of the decoded mesh (two triangles belong to
   the same component when they share a vertex index). This is a
   VISUAL grouping computed in the viewer — never a decoded CATIA body
   boundary: the export contract carries one merged pool and the
   parser is untouched. Labeled honestly in the UI.

   Union-find with path halving + union by size, chunked: the caller
   yields between chunks (requestAnimationFrame in the browser) so a
   Dodge-scale mesh (2.5M triangles) never blocks the main thread in
   one go. Returns { count, labels, counts }: the per-triangle
   component label (compact ids in first-seen order) and the per-
   component triangle count. */
export async function computeComponents(vertexCount, triangles, opts = {}) {
  const chunk = opts.chunk || 250000;
  const yieldFrame = opts.yieldFrame || defaultScheduleFrame;
  const triCount = Math.floor(triangles.length / 3);
  const parent = new Int32Array(vertexCount);
  for (let i = 0; i < vertexCount; i++) parent[i] = i;
  const size = new Uint32Array(vertexCount).fill(1);

  const find = (x) => {
    while (parent[x] !== x) {
      parent[x] = parent[parent[x]]; // path halving
      x = parent[x];
    }
    return x;
  };
  const union = (a, b) => {
    let ra = find(a);
    let rb = find(b);
    if (ra === rb) return;
    if (size[ra] < size[rb]) {
      const swap = ra;
      ra = rb;
      rb = swap;
    }
    parent[rb] = ra;
    size[ra] += size[rb];
  };

  let done = 0;
  while (done < triCount) {
    const end = Math.min(done + chunk, triCount);
    for (let t = done; t < end; t++) {
      const a = triangles[t * 3];
      const b = triangles[t * 3 + 1];
      const c = triangles[t * 3 + 2];
      union(a, b);
      union(b, c);
    }
    done = end;
    if (done < triCount) {
      await new Promise(yieldFrame);
    }
  }

  // Compact the roots into first-seen component ids.
  const labels = new Int32Array(triCount);
  const rootIds = new Map();
  const countsList = [];
  for (let t = 0; t < triCount; t++) {
    const root = find(triangles[t * 3]);
    let id = rootIds.get(root);
    if (id === undefined) {
      id = countsList.length;
      rootIds.set(root, id);
      countsList.push(0);
    }
    labels[t] = id;
    countsList[id] += 1;
  }
  return {
    count: countsList.length,
    labels,
    counts: new Uint32Array(countsList),
  };
}

/* Reorder the mesh's triangle index buffer by component (stable within
   each component: the original triangle order is kept), so each
   component renders as its own draw range over the same geometry.
   Returns { index, ranges } — the ranges are { start, count } in
   INDICES (3 per triangle), ready for BufferGeometry.setDrawRange. */
export function reorderByComponents(triangles, labels, compCount) {
  const triCount = labels.length;
  const starts = new Uint32Array(compCount);
  for (let t = 0; t < triCount; t++) starts[labels[t]] += 1;
  let total = 0;
  for (let k = 0; k < compCount; k++) {
    const n = starts[k];
    starts[k] = total;
    total += n;
  }
  const index = new Uint32Array(triangles.length);
  const cursor = new Uint32Array(compCount);
  for (let t = 0; t < triCount; t++) {
    const k = labels[t];
    const pos = starts[k] + cursor[k];
    cursor[k] += 1;
    index[pos * 3] = triangles[t * 3];
    index[pos * 3 + 1] = triangles[t * 3 + 1];
    index[pos * 3 + 2] = triangles[t * 3 + 2];
  }
  const ranges = [];
  for (let k = 0; k < compCount; k++) {
    const count = cursor[k];
    ranges.push({ start: starts[k] * 3, count: count * 3, triangles: count });
  }
  return { index, ranges };
}

/* The pose-based orbit controller. Same user grammar as orbit.js
   (drag orbit, wheel dolly, pointer capture) plus the CAD-view
   presets with eased camera transitions. */
export function createCadOrbit(camera, canvas, opts = {}) {
  const scheduleFrame = opts.scheduleFrame || defaultScheduleFrame;
  const transitionMs = opts.transitionMs === undefined ? VIEW_TRANSITION_MS : opts.transitionMs;

  const state = {
    mode: "part",
    target: new THREE.Vector3(0, 0, 0),
    radius: 10,
    az: Math.PI * 0.25,
    pol: 0.9553166, // atan(sqrt(2)) off the up axis: the CATIA iso elevation
    upAxis: modeUpAxis("part"),
    dragging: false,
    lastX: 0,
    lastY: 0,
    // The scripted-check surface for the current view preset.
    currentView: null,
    transitioning: false,
  };

  // The transition record (null when idle). The tween drives the
  // camera's quaternion + position directly; lookAt is not called
  // mid-flight. Cancelling re-bases the spherical state from the
  // exact mid-flight camera pose, so a user drag never snaps.
  let transition = null;

  function basis() {
    const u = state.upAxis;
    const axes = [
      new THREE.Vector3(1, 0, 0),
      new THREE.Vector3(0, 1, 0),
      new THREE.Vector3(0, 0, 1),
    ];
    let best = axes[0];
    for (const axis of axes) {
      if (Math.abs(axis.dot(u)) < Math.abs(best.dot(u))) best = axis;
    }
    const h = best.clone().addScaledVector(u, -best.dot(u)).normalize();
    const b = new THREE.Vector3().crossVectors(u, h);
    return { u, h, b };
  }

  function apply() {
    state.pol = Math.min(Math.max(state.pol, PHI_MIN), PHI_MAX);
    const { u, h, b } = basis();
    const sinPol = Math.sin(state.pol);
    camera.position
      .set(0, 0, 0)
      .addScaledVector(u, state.radius * Math.cos(state.pol))
      .addScaledVector(h, state.radius * sinPol * Math.cos(state.az))
      .addScaledVector(b, state.radius * sinPol * Math.sin(state.az))
      .add(state.target);
    camera.up.copy(u);
    camera.lookAt(state.target);
  }

  /* Re-base the spherical state from an exact camera pose (used when a
     transition is cancelled mid-flight and on preset completion). */
  function rebaseFromPose(dir, up, target, radius) {
    const pose = poseFromDirUp(dir, up, state.az);
    state.az = pose.az;
    state.pol = pose.pol;
    state.upAxis.copy(pose.upAxis);
    state.target.copy(target);
    state.radius = Math.max(radius, 0.01);
  }

  function cancelTransition() {
    if (!transition) return;
    const tr = transition;
    transition = null;
    state.transitioning = false;
    // The exact mid-flight pose: the tween's lerped target/radius and
    // the camera's current orientation.
    const dir = camera.position.clone().sub(tr.target).normalize();
    rebaseFromPose(dir, camera.up, tr.target, tr.radius);
    apply();
  }

  function step() {
    if (!transition) return;
    const tr = transition;
    tr.elapsed += tr.frameDelta();
    const t = Math.min(tr.elapsed / transitionMs, 1);
    const e = easeInOut(t);
    tr.q.copy(tr.q0).slerp(tr.q1, e);
    tr.target.lerpVectors(tr.target0, tr.target1, e);
    const r = Math.exp((1 - e) * Math.log(tr.r0) + e * Math.log(tr.r1));
    camera.up.copy(slerpUnit(tr.u0, tr.u1, e));
    const w = new THREE.Vector3(0, 0, -1).applyQuaternion(tr.q);
    camera.quaternion.copy(tr.q);
    camera.position.copy(tr.target).addScaledVector(w, -r);
    tr.radius = r;
    if (t >= 1) {
      transition = null;
      state.transitioning = false;
      state.currentView = tr.name;
      rebaseFromPose(tr.dir1, tr.u1, tr.target1, tr.r1);
      apply();
      if (tr.onDone) tr.onDone();
      return;
    }
    scheduleFrame(step);
  }

  /* The standard-view entry: frame the given bounds (center + fitting
     radius, the same 2.2x margin as frame()) and ease the camera into
     the named CATIA view for the current display mode. Camera-only
     work per frame — never a geometry pass, whatever the mesh size. */
  function setPreset(name, fit, onDone = null) {
    const { dir: dir1, up: up1 } = resolvePreset(name, state.mode);
    const r1 = Math.max(fit.radius * FRAME_MARGIN, 0.01);
    const target1 = new THREE.Vector3(fit.center.x, fit.center.y, fit.center.z);
    const eye1 = target1.clone().addScaledVector(dir1, r1);
    const q1 = new THREE.Quaternion().setFromRotationMatrix(
      new THREE.Matrix4().lookAt(eye1, target1, up1),
    );
    cancelTransition();
    const q0 = camera.quaternion.clone();
    const u0 = camera.up.clone().normalize();
    transition = {
      name,
      q0,
      q1,
      u0,
      u1: up1.clone(),
      target0: state.target.clone(),
      target1,
      r0: Math.max(state.radius, 0.01),
      r1,
      dir1,
      q: new THREE.Quaternion(),
      target: state.target.clone(),
      radius: state.radius,
      elapsed: 0,
      frameDelta: () => (opts.frameDelta === undefined ? 16.7 : opts.frameDelta),
      onDone,
    };
    state.transitioning = true;
    state.currentView = name;
    step();
  }

  /* orbit.js-compatible surface (AssemblyScene's autoFrame and
     frameInstance call these). frame() keeps the current angles and
     refits target + radius, exactly like orbit.js. */
  function frame(center, radius) {
    cancelTransition();
    state.target.copy(center);
    state.radius = Math.max(radius * FRAME_MARGIN, 0.01);
    apply();
  }

  function setMode(mode) {
    state.mode = mode === "assembly" ? "assembly" : "part";
  }

  /* --- the user interaction (the orbit.js grammar) ---------------- */

  if (canvas) {
    canvas.addEventListener("pointerdown", (ev) => {
      cancelTransition();
      state.dragging = true;
      state.lastX = ev.clientX;
      state.lastY = ev.clientY;
      canvas.setPointerCapture(ev.pointerId);
    });
    canvas.addEventListener("pointermove", (ev) => {
      if (!state.dragging) return;
      const dx = ev.clientX - state.lastX;
      const dy = ev.clientY - state.lastY;
      state.lastX = ev.clientX;
      state.lastY = ev.clientY;
      const TWO_PI = Math.PI * 2;
      state.az = (state.az - dx * 0.008) % TWO_PI;
      state.pol = Math.min(Math.max(state.pol - dy * 0.008, PHI_MIN), PHI_MAX);
      apply();
    });
    const endDrag = (ev) => {
      state.dragging = false;
      if (ev.pointerId !== undefined) {
        try {
          canvas.releasePointerCapture(ev.pointerId);
        } catch {
          /* already released */
        }
      }
    };
    canvas.addEventListener("pointerup", endDrag);
    canvas.addEventListener("pointercancel", endDrag);
    canvas.addEventListener(
      "wheel",
      (ev) => {
        ev.preventDefault();
        cancelTransition();
        const factor = Math.exp(ev.deltaY * 0.0012);
        state.radius = Math.min(Math.max(state.radius * factor, 0.01), 1e7);
        apply();
      },
      { passive: false },
    );
  }

  return {
    frame,
    update: apply,
    setMode,
    setPreset,
    /* The pose readout for the scripted checks (window.viewer.view). */
    readout() {
      const dir = camera.position.clone().sub(state.target).normalize();
      return {
        mode: state.mode,
        currentView: state.currentView,
        transitioning: state.transitioning,
        dir: [dir.x, dir.y, dir.z],
        up: [camera.up.x, camera.up.y, camera.up.z],
        radius: state.radius,
        target: [state.target.x, state.target.y, state.target.z],
      };
    },
  };
}
