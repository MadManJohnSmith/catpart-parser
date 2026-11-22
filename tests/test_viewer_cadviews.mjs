/* Test suite for the W22 CAD-view module (site/viewer/cadviews.js):
   the CATIA-space preset mapping per display mode, the pose-based
   orbit controller (preset transitions, cancellation, orbit.js-compat
   framing), and the client-side mesh components behind the Bodies
   section. Pure ES module over the pinned three.js — zero npm
   dependencies. Run via: node tests/test_viewer_cadviews.mjs
   (wired into the gate's `node --test tests/*.mjs`). */

import assert from "node:assert/strict";
import * as THREE from "../site/viewer/three.module.min.js";
import {
  CATIA_VIEW_PRESETS,
  VIEW_NAMES,
  catiaToWorld,
  computeComponents,
  createCadOrbit,
  easeInOut,
  modeUpAxis,
  poseFromDirUp,
  reorderByComponents,
  resolvePreset,
  slerpUnit,
} from "../site/viewer/cadviews.js";

const EPS = 1e-6;
function vecClose(actual, expected, eps = EPS, label = "") {
  assert.ok(
    Math.abs(actual.x - expected[0]) < eps &&
      Math.abs(actual.y - expected[1]) < eps &&
      Math.abs(actual.z - expected[2]) < eps,
    `${label}: got (${actual.x}, ${actual.y}, ${actual.z}), expected ${expected}`,
  );
}

/* A synchronous scheduler: every scheduleFrame call runs the frame
   immediately (recursively), so a transition completes inside the
   setPreset call. frameDelta is injectable per test. */
function syncScheduler(frameDelta = 16) {
  return {
    scheduleFrame(cb) {
      cb();
    },
    frameDelta,
  };
}

/* A manual scheduler: callbacks queue up; the test pumps them one by
   one (mid-flight cancellation tests). */
function manualScheduler(frameDelta = 16) {
  const queue = [];
  return {
    scheduleFrame(cb) {
      queue.push(cb);
    },
    get pending() {
      return queue.length;
    },
    pump(steps = 1) {
      for (let i = 0; i < steps; i++) {
        const cb = queue.shift();
        if (!cb) break;
        cb();
      }
    },
    frameDelta,
  };
};

function newCamera() {
  return new THREE.PerspectiveCamera(50, 1, 0.01, 1e7);
}

/* ---- 1. the CATIA -> world mapping per mode ---------------------- */

{
  vecClose(catiaToWorld([1, 2, 3], "part"), [1, 2, 3], EPS, "part mapping is the identity");
  vecClose(catiaToWorld([1, 2, 3], "assembly"), [1, 3, -2], EPS, "assembly mapping is B: (x,y,z)->(x,z,-y)");
  vecClose(modeUpAxis("part"), [0, 0, 1], EPS, "part up axis is CATIA Z");
  vecClose(modeUpAxis("assembly"), [0, 1, 0], EPS, "assembly up axis is world Y (B stands CATIA Z up)");
}

/* ---- 2. the standard views, resolved per mode -------------------- */

{
  for (const name of VIEW_NAMES) {
    assert.ok(CATIA_VIEW_PRESETS[name], `preset ${name} exists`);
  }
  // Part mode: raw coordinates ARE CATIA axes.
  let p = resolvePreset("front", "part");
  vecClose(p.dir, [0, 1, 0], EPS, "part front: camera on CATIA +Y");
  vecClose(p.up, [0, 0, 1], EPS, "part front: CATIA Z up on screen");
  p = resolvePreset("top", "part");
  vecClose(p.dir, [0, 0, 1], EPS, "part top: camera on CATIA +Z");
  vecClose(p.up, [0, 1, 0], EPS, "part top: CATIA Y up on screen");
  p = resolvePreset("right", "part");
  vecClose(p.dir, [1, 0, 0], EPS, "part right: camera on CATIA +X");
  vecClose(p.up, [0, 0, 1], EPS, "part right: CATIA Z up on screen");
  p = resolvePreset("iso", "part");
  const s = 1 / Math.sqrt(3);
  vecClose(p.dir, [s, s, s], EPS, "part iso: (1,1,1)/sqrt(3)");
  // Assembly mode: the root basis B = R_X(-pi/2) maps the presets.
  p = resolvePreset("front", "assembly");
  vecClose(p.dir, [0, 0, -1], EPS, "assembly front: CATIA +Y -> world -Z");
  vecClose(p.up, [0, 1, 0], EPS, "assembly front: world Y up on screen");
  p = resolvePreset("top", "assembly");
  vecClose(p.dir, [0, 1, 0], EPS, "assembly top: camera on CATIA +Z = world +Y");
  vecClose(p.up, [0, 0, -1], EPS, "assembly top: CATIA +Y up on screen = world -Z");
  p = resolvePreset("right", "assembly");
  vecClose(p.dir, [1, 0, 0], EPS, "assembly right: CATIA +X = world +X");
  p = resolvePreset("iso", "assembly");
  vecClose(p.dir, [s, s, -s], EPS, "assembly iso: (1,1,-1)/sqrt(3)");
  assert.throws(() => resolvePreset("nope", "part"), /unknown CAD view/, "unknown preset rejected");
}

/* ---- 3. the controller: presets land the exact pose -------------- */

{
  const camera = newCamera();
  const sched = syncScheduler(16);
  const orbit = createCadOrbit(camera, null, {
    scheduleFrame: sched.scheduleFrame,
    frameDelta: sched.frameDelta,
  });
  const fit = { center: new THREE.Vector3(10, -4, 2), radius: 5 };
  orbit.setMode("part");
  for (const name of VIEW_NAMES) {
    camera.position.set(100, 100, 100);
    camera.up.set(0, 1, 0);
    orbit.setPreset(name, fit);
    const ro = orbit.readout();
    assert.equal(ro.currentView, name, `${name}: currentView set`);
    assert.equal(ro.transitioning, false, `${name}: transition completed synchronously`);
    assert.equal(ro.mode, "part", `${name}: mode carried`);
    const preset = resolvePreset(name, "part");
    vecClose(new THREE.Vector3(...ro.dir), [preset.dir.x, preset.dir.y, preset.dir.z], 1e-6, `${name}: direction`);
    vecClose(new THREE.Vector3(...ro.up), [preset.up.x, preset.up.y, preset.up.z], 1e-6, `${name}: screen-up`);
    assert.ok(Math.abs(ro.radius - fit.radius * 2.2) < 1e-9, `${name}: framing radius is the 2.2x margin`);
    vecClose(new THREE.Vector3(...ro.target), [fit.center.x, fit.center.y, fit.center.z], 1e-9, `${name}: target`);
    // The camera really sits where the pose says: eye = target + dir*radius.
    const eye = camera.position.clone().sub(new THREE.Vector3(...ro.target));
    vecClose(eye.normalize(), [preset.dir.x, preset.dir.y, preset.dir.z], 1e-6, `${name}: eye on the pose ray`);
  }
}

/* ---- 4. the assembly-mode presets through the controller --------- */

{
  const camera = newCamera();
  const sched = syncScheduler(16);
  const orbit = createCadOrbit(camera, null, {
    scheduleFrame: sched.scheduleFrame,
    frameDelta: sched.frameDelta,
  });
  orbit.setMode("assembly");
  orbit.setPreset("top", { center: new THREE.Vector3(), radius: 4 });
  let ro = orbit.readout();
  vecClose(new THREE.Vector3(...ro.dir), [0, 1, 0], EPS, "assembly top: looks down the world Y axis");
  vecClose(new THREE.Vector3(...ro.up), [0, 0, -1], EPS, "assembly top: screen-up = world -Z");
  orbit.setPreset("front", { center: new THREE.Vector3(), radius: 4 });
  ro = orbit.readout();
  vecClose(new THREE.Vector3(...ro.dir), [0, 0, -1], EPS, "assembly front: camera on world -Z");
  vecClose(new THREE.Vector3(...ro.up), [0, 1, 0], EPS, "assembly front: screen-up = world Y");
}

/* ---- 5. orbit.js-compatible frame() ------------------------------ */

{
  const camera = newCamera();
  const orbit = createCadOrbit(camera, null);
  orbit.setMode("part");
  orbit.frame(new THREE.Vector3(1, 2, 3), 10);
  const ro = orbit.readout();
  assert.ok(Math.abs(ro.radius - 22) < 1e-9, "frame: the 2.2x margin radius");
  vecClose(new THREE.Vector3(...ro.target), [1, 2, 3], 1e-9, "frame: target copied");
  // The frame() angles are kept: a second frame() with a different fit
  // moves only target + radius.
  const dirBefore = orbit.readout().dir;
  orbit.frame(new THREE.Vector3(5, 5, 5), 2);
  const ro2 = orbit.readout();
  assert.deepEqual(ro2.dir.map((v) => +v.toFixed(9)), dirBefore.map((v) => +v.toFixed(9)), "frame: angles kept");
}

/* ---- 6. mid-flight cancellation re-bases without a snap ---------- */

{
  const camera = newCamera();
  const sched = manualScheduler(28); // 280ms / 28 = 10 steps
  const orbit = createCadOrbit(camera, null, {
    scheduleFrame: sched.scheduleFrame,
    frameDelta: sched.frameDelta,
  });
  orbit.setMode("part");
  orbit.frame(new THREE.Vector3(), 10);
  orbit.setPreset("front", { center: new THREE.Vector3(), radius: 10 });
  assert.equal(orbit.readout().transitioning, true, "transition in flight");
  sched.pump(4);
  const midPos = camera.position.clone();
  const midUp = camera.up.clone();
  assert.equal(orbit.readout().transitioning, true, "still in flight at step 4");
  // A drag (pointerdown) cancels the transition; without a canvas we
  // exercise the same path through frame() (the rebase-and-apply).
  orbit.frame(new THREE.Vector3(0, 0, 0), 10);
  const ro = orbit.readout();
  assert.equal(ro.transitioning, false, "cancelled");
  const posAfter = camera.position.clone();
  const dist = midPos.distanceTo(posAfter);
  assert.ok(dist < 1e-6, `cancel must not snap (jumped ${dist})`);
  assert.ok(midUp.angleTo(camera.up) < 1e-6, "cancel keeps the mid-flight up");
}

/* ---- 7. poseFromDirUp round-trip --------------------------------- */

{
  for (const mode of ["part", "assembly"]) {
    for (const name of VIEW_NAMES) {
      const preset = resolvePreset(name, mode);
      const pose = poseFromDirUp(preset.dir, preset.up);
      // Reconstruct the direction from the spherical form around the
      // pose's own up axis.
      const axes = [
        new THREE.Vector3(1, 0, 0),
        new THREE.Vector3(0, 1, 0),
        new THREE.Vector3(0, 0, 1),
      ];
      let best = axes[0];
      for (const axis of axes) {
        if (Math.abs(axis.dot(pose.upAxis)) < Math.abs(best.dot(pose.upAxis))) best = axis;
      }
      const h = best.clone().addScaledVector(pose.upAxis, -best.dot(pose.upAxis)).normalize();
      const b = new THREE.Vector3().crossVectors(pose.upAxis, h);
      const dir = pose.upAxis
        .clone()
        .multiplyScalar(Math.cos(pose.pol))
        .addScaledVector(h, Math.sin(pose.pol) * Math.cos(pose.az))
        .addScaledVector(b, Math.sin(pose.pol) * Math.sin(pose.az));
      assert.ok(dir.angleTo(preset.dir) < 1e-6, `${mode}/${name}: pose round-trip`);
    }
  }
  // Pole: dir parallel to upAxis keeps the previous azimuth.
  const pose = poseFromDirUp(new THREE.Vector3(0, 0, 1), new THREE.Vector3(0, 0, 1), 0.7);
  assert.ok(Math.abs(pose.az - 0.7) < 1e-12, "pole keeps the previous azimuth");
}

/* ---- 8. the interpolation helpers -------------------------------- */

{
  const a = new THREE.Vector3(1, 0, 0);
  const b = new THREE.Vector3(0, 1, 0);
  vecClose(slerpUnit(a, b, 0), [1, 0, 0], EPS, "slerp t=0 is a");
  vecClose(slerpUnit(a, b, 1), [0, 1, 0], EPS, "slerp t=1 is b");
  const mid = slerpUnit(a, b, 0.5);
  assert.ok(Math.abs(mid.x - Math.SQRT1_2) < EPS && Math.abs(mid.y - Math.SQRT1_2) < EPS, "slerp midpoint");
  // Antipodal pair: defined (fallback), unit, never NaN.
  const anti = slerpUnit(new THREE.Vector3(0, 0, 1), new THREE.Vector3(0, 0, -1), 0.5);
  assert.ok(Number.isFinite(anti.x) && Math.abs(anti.length() - 1) < EPS, "antipodal slerp stays finite+unit");
  assert.ok(Math.abs(easeInOut(0)) < EPS && Math.abs(easeInOut(1) - 1) < EPS, "easeInOut endpoints");
  assert.ok(Math.abs(easeInOut(0.5) - 0.5) < EPS, "easeInOut midpoint");
}

/* ---- 9. computeComponents (the Bodies grouping law) -------------- */

{
  // Two disjoint triangles -> 2 components.
  let r = await computeComponents(
    6,
    new Uint32Array([0, 1, 2, 3, 4, 5]),
  );
  assert.equal(r.count, 2, "disjoint triangles: 2 components");
  assert.deepEqual(Array.from(r.counts), [1, 1], "disjoint: one triangle each");

  // Two triangles sharing one vertex -> 1 component.
  r = await computeComponents(5, new Uint32Array([0, 1, 2, 2, 3, 4]));
  assert.equal(r.count, 1, "vertex-shared triangles: 1 component");

  // The canonical fixture's shape (a box: 8 verts, 12 tris) -> 1.
  const boxTris = [
    0, 2, 1, 2, 3, 1, 4, 6, 5, 6, 7, 5, 0, 4, 1, 4, 5, 1, 2, 6, 3, 6, 7, 3,
    0, 1, 5, 0, 5, 4, 2, 3, 7, 2, 7, 6,
  ];
  r = await computeComponents(8, new Uint32Array(boxTris));
  assert.equal(r.count, 1, "the box fixture: 1 component");

  // Empty mesh -> 0 components.
  r = await computeComponents(0, new Uint32Array([]));
  assert.equal(r.count, 0, "empty mesh: 0 components");

  // Three disjoint pairs -> labels in first-seen order.
  r = await computeComponents(
    12,
    new Uint32Array([3, 4, 5, 0, 1, 2, 9, 10, 11, 6, 7, 8]),
  );
  assert.equal(r.count, 4, "four disjoint triangles");
  assert.deepEqual(Array.from(r.labels), [0, 1, 2, 3], "labels in first-seen order");
  assert.deepEqual(Array.from(r.counts), [1, 1, 1, 1], "counts match labels");

  // Chunking must not change the result (yield between chunks).
  const threeBodies = new Uint32Array([0, 1, 2, 3, 4, 5, 0, 1, 2, 6, 7, 8]);
  const whole = await computeComponents(9, threeBodies, { chunk: 1000 });
  const chunked = await computeComponents(9, threeBodies, { chunk: 1, yieldFrame: (cb) => cb() });
  assert.equal(whole.count, 3, "three vertex groups -> 3 components");
  assert.deepEqual(Array.from(whole.counts), Array.from(chunked.counts), "chunked == whole");
}

/* ---- 10. reorderByComponents (stable, ranges aligned) ------------ */

{
  // 4 triangles, labels [1, 0, 1, 0]: comp0 keeps t1, t3; comp1 keeps
  // t0, t2 — the original order inside each component.
  const tris = new Uint32Array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]);
  const labels = new Int32Array([1, 0, 1, 0]);
  const r = reorderByComponents(tris, labels, 2);
  assert.deepEqual(
    Array.from(r.index),
    [3, 4, 5, 9, 10, 11, 0, 1, 2, 6, 7, 8],
    "stable reorder by component",
  );
  assert.deepEqual(
    r.ranges.map((x) => x.start),
    [0, 6],
    "component 0 first, component 1 second",
  );
  assert.deepEqual(
    r.ranges.map((x) => x.count),
    [6, 6],
    "ranges count indices (3 per triangle)",
  );
  // The multiset is preserved.
  const sortedA = Array.from(tris).sort((x, y) => x - y);
  const sortedB = Array.from(r.index).sort((x, y) => x - y);
  assert.deepEqual(sortedA, sortedB, "reorder preserves the index multiset");
}

console.log("test_viewer_cadviews: all checks passed");
