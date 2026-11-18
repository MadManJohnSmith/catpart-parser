/* Hand-written orbit + zoom (spec §5: the viewer keeps the site's
   zero-dependency property — no vendored example code beyond the one
   pinned three.module.min.js). Spherical orbit around a target with
   wheel dolly; desktop pointer events only (§1: desktop is the target
   surface). */

import * as THREE from "./three.module.min.js";

const TWO_PI = Math.PI * 2;

export function attachOrbit(canvas, camera) {
  const state = {
    target: new THREE.Vector3(0, 0, 0),
    radius: 10,
    // Spherical angles around the target: azimuth theta, polar phi.
    theta: Math.PI * 0.25,
    phi: Math.PI * 0.35,
    dragging: false,
    lastX: 0,
    lastY: 0,
  };

  function apply() {
    // Clamp phi inside (0, PI) so the up vector never flips.
    const phi = Math.min(Math.max(state.phi, 0.01), Math.PI - 0.01);
    const sinPhi = Math.sin(phi);
    camera.position.set(
      state.target.x + state.radius * sinPhi * Math.sin(state.theta),
      state.target.y + state.radius * Math.cos(phi),
      state.target.z + state.radius * sinPhi * Math.cos(state.theta),
    );
    camera.lookAt(state.target);
  }

  canvas.addEventListener("pointerdown", (ev) => {
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
    state.theta = (state.theta - dx * 0.008) % TWO_PI;
    state.phi = Math.min(Math.max(state.phi - dy * 0.008, 0.01), Math.PI - 0.01);
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
      // Multiplicative dolly: zoom feels identical at any radius.
      const factor = Math.exp(ev.deltaY * 0.0012);
      state.radius = Math.min(Math.max(state.radius * factor, 0.01), 1e7);
      apply();
    },
    { passive: false },
  );

  return {
    /** Frame a bounding sphere: center the orbit and fit the radius. */
    frame(center, radius) {
      state.target.copy(center);
      // A 2.2x margin keeps the whole mesh visible with the fov.
      state.radius = Math.max(radius * 2.2, 0.01);
      apply();
    },
    update: apply,
  };
}
