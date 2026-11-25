/* The Phase 5 & Phase 6 viewer: a hand-written ES module over the WASM entries
   and the pinned three.js module. No bundler, no framework, no node_modules.

   Supports:
   - Part Mode (Phase 5): Single .CATPart drag-drop/upload, geometry mesh,
     curve overlay, sanity gate, schema-v1 metadata panel.
   - Assembly Mode (Phase 6): Multi-file, .CATProduct, or .zip upload,
     Virtual File Catalog, 3D spatial scene graph with R_X(-pi/2) basis,
     geometry instancing pool, hierarchical instance tree with the 4
     canonical badges (Placed, Identity, Unresolved, Undecodable),
     interactive instance inspector, and exploded view slider.
*/

import * as THREE from "./three.module.min.js";
import init, { decode_export, decode_inspect, decode_product_structure } from "./pkg/port.js";
import { CHECK_EMPTY_MESH, MAX_DEGENERATE_TRIANGLES, scoreExport } from "./gate.js";
import {
  VIEW_NAMES,
  computeComponents,
  createCadOrbit,
  reorderByComponents,
} from "./cadviews.js";
import { VirtualFileCatalog } from "./catalog.js";
import { ingestFiles, isZipFile } from "./ingest.js";
import {
  AssemblyScene,
  STATUS_PLACED,
  STATUS_IDENTITY,
  STATUS_UNRESOLVED,
  STATUS_UNDECODABLE,
} from "./assembly_scene.js";
import { AssemblyUI } from "./assembly_ui.js";

const els = {
  drop: document.getElementById("drop"),
  input: document.getElementById("file-input"),
  status: document.getElementById("status"),
  canvas: document.getElementById("scene"),
  errorPanel: document.getElementById("error-panel"),
  errorClass: document.getElementById("error-class"),
  errorDetail: document.getElementById("error-detail"),
  gate: document.getElementById("gate"),
  gatePanel: document.getElementById("gate-panel"),
  featurePanel: document.getElementById("feature-panel"),
  featureTree: document.getElementById("feature-tree"),
  featureDetail: document.getElementById("feature-detail"),
  bodiesPanel: document.getElementById("bodies-panel"),
  bodiesList: document.getElementById("bodies-list"),
  meta: document.getElementById("meta"),
  metaPanel: document.getElementById("meta-panel"),
  displayLabel: document.getElementById("display-label"),
  displayLabelText: document.getElementById("display-label-text"),
  curvesBtn: document.getElementById("curve-toggle"),
  wireBtn: document.getElementById("wire-toggle"),
  edgesBtn: document.getElementById("edges-toggle"),
  shadingBtn: document.getElementById("shading-toggle"),
  materialBtn: document.getElementById("material-toggle"),
  viewButtons: {
    iso: document.getElementById("view-iso"),
    front: document.getElementById("view-front"),
    top: document.getElementById("view-top"),
    right: document.getElementById("view-right"),
  },
  curveState: document.getElementById("curve-state"),
  assemblyPanel: document.getElementById("assembly-panel"),
  inspectorPanel: document.getElementById("inspector-panel"),
  assemblyTreeContainer: document.getElementById("assembly-tree-container"),
  assemblySummaryBar: document.getElementById("assembly-summary-bar"),
  assemblySwitcherContainer: document.getElementById("assembly-switcher-container"),
  instanceInspector: document.getElementById("instance-inspector"),
  explodedToolbar: document.getElementById("exploded-view-toolbar"),
  explodeSlider: document.getElementById("explode-slider"),
  explodeValue: document.getElementById("explode-value"),
};

/* ---- three.js scaffolding (created once) ---- */

const renderer = new THREE.WebGLRenderer({ canvas: els.canvas, antialias: true });
renderer.setClearColor(0x0e1526);
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(50, 1, 0.01, 1e7);
scene.add(new THREE.HemisphereLight(0xcfe6ff, 0x202a3c, 1.5));
// The key light rides the camera (CATIA's view-relative lamp): the
// visible side stays lit and orbiting never turns a face black. The
// camera joins the scene so the light's target updates its matrices.
scene.add(camera);
const key = new THREE.DirectionalLight(0xffffff, 1.8);
key.position.set(1, 2, 1.5);
camera.add(key);
camera.add(key.target);
// The W22 pose-based controller (site/viewer/cadviews.js): same drag/
// wheel grammar as orbit.js plus the standard CAD-view presets.
const orbit = createCadOrbit(camera, els.canvas);

let meshObject = null;
let curveGroup = null;
let displayGroup = null;
let solidMaterial = null;
let showCurves = false;
let showWireframe = false;
let showEdges = true; // CATIA-style crease edges: on by default
let showEvenShading = false;
const CREASE_ANGLE_DEG = 28;
const MATERIAL_PRESETS = {
  native: { color: 0xd2d2ff, metalness: 0.1, roughness: 0.65 },
  "cad-gray": { color: 0xb4b4b4, metalness: 0.0, roughness: 0.8 },
};
let materialPreset = "native";
let hasNativeTriColors = false; // the last build carried per-triangle CATIA colors
let edgesObject = null;
let bodiesComponents = null; // null while not measured / < 2 components
let bodiesEpoch = 0; // guards the async body labeling across reloads
let sceneBounds = null; // { center, radius } — the loaded model's fit bounds

/* ---- Assembly Subsystems (Phase 6) ---- */

const assemblyScene = new AssemblyScene(scene, {
  defaultMaterial: null,
  applyRootBasis: true,
});

let activeCatalog = null;

const assemblyUI = new AssemblyUI({
  document: window.document,
  treeContainer: els.assemblyTreeContainer,
  summaryContainer: els.assemblySummaryBar,
  inspectorContainer: els.instanceInspector,
  switcherContainer: els.assemblySwitcherContainer,
  toolbarContainer: els.explodedToolbar,
  scene: assemblyScene,
  onExplodeChange: (scale) => {
    assemblyScene.setExplodedScale(scale);
  },
  onSelectInstance: (rec) => {
    if (rec && rec.instance_name) {
      assemblyScene.frameInstance(rec.instance_name, orbit);
    }
  },
  onToggleVisibility: (id, vis) => {
    assemblyScene.setInstanceVisibility(id, vis);
  },
  onIsolateInstance: (id, iso) => {
    assemblyScene.isolateInstance(id, iso);
  },
  onSwitchProduct: async (cand) => {
    if (activeCatalog && cand) {
      await loadAssemblyFromCatalog(activeCatalog, cand.name);
    }
  },
});

function resize() {
  const rect = els.canvas.getBoundingClientRect();
  const w = Math.max(rect.width, 1);
  const h = Math.max(rect.height, 1);
  renderer.setSize(w, h, false);
  renderer.setPixelRatio(window.devicePixelRatio);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  orbit.update();
}
window.addEventListener("resize", resize);

/* The render loop (orbit + toggles re-render on the next frame). */
function tick() {
  renderer.render(scene, camera);
  requestAnimationFrame(tick);
}
requestAnimationFrame(tick);

function setUIMode(mode) {
  orbit.setMode(mode);
  if (mode === "assembly") {
    if (els.assemblyPanel) els.assemblyPanel.hidden = false;
    if (els.inspectorPanel) els.inspectorPanel.hidden = false;
    if (els.explodedToolbar) els.explodedToolbar.hidden = false;
    if (els.gatePanel) els.gatePanel.hidden = true;
    if (els.featurePanel) els.featurePanel.hidden = true;
    if (els.metaPanel) els.metaPanel.hidden = true;
    viewerState.mode = "assembly";
  } else {
    if (els.assemblyPanel) els.assemblyPanel.hidden = true;
    if (els.inspectorPanel) els.inspectorPanel.hidden = true;
    if (els.explodedToolbar) els.explodedToolbar.hidden = true;
    if (els.gatePanel) els.gatePanel.hidden = false;
    if (els.featurePanel) els.featurePanel.hidden = false;
    if (els.metaPanel) els.metaPanel.hidden = false;
    viewerState.mode = "part";
  }
}

function clearScene() {
  for (const obj of [meshObject, edgesObject, curveGroup, displayGroup]) {
    if (!obj) continue;
    scene.remove(obj);
    obj.traverse((child) => {
      if (child.geometry) child.geometry.dispose();
      if (child.material) child.material.dispose();
    });
  }
  meshObject = null;
  edgesObject = null;
  curveGroup = null;
  displayGroup = null;
  bodiesComponents = null;
  sceneBounds = null;
  bodiesEpoch += 1;
  assemblyScene.clear();
  if (assemblyUI) assemblyUI.clear();
  if (els.bodiesPanel) {
    els.bodiesPanel.hidden = true;
    els.bodiesList.innerHTML = "";
  }
  if (els.featureDetail) {
    els.featureDetail.hidden = true;
    els.featureDetail.textContent = "";
  }
}

function disposeMesh() {
  clearScene();
}

/* ---- rendering the decoded result (Part Mode) ---- */

/**
 * Split vertex normals at sharp creases (> creaseDeg) while keeping smooth
 * shading across curved CAD surfaces (cylinders, fillets, bodywork).
 * Optionally attaches per-triangle native CATIA RGB colors (Uint8Array, 3 B/tri).
 */
function buildCreaseGeometry(vertices, triangles, creaseDeg = CREASE_ANGLE_DEG, triColors = null) {
  const triCount = (triangles.length / 3) | 0;
  if (triCount === 0) {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(vertices, 3));
    g.setIndex(new THREE.BufferAttribute(triangles, 1));
    return g;
  }
  const useColors = !!(triColors && triColors.length >= triCount * 3);
  const cosLimit = Math.cos((creaseDeg * Math.PI) / 180);
  const faceNx = new Float32Array(triCount);
  const faceNy = new Float32Array(triCount);
  const faceNz = new Float32Array(triCount);
  const faceArea = new Float32Array(triCount);

  const edgeMap = new Map();
  const vCount = (vertices.length / 3) | 0;
  for (let t = 0; t < triCount; t++) {
    const a = triangles[3 * t], b = triangles[3 * t + 1], c = triangles[3 * t + 2];
    const ax = vertices[3 * a], ay = vertices[3 * a + 1], az = vertices[3 * a + 2];
    const ux = vertices[3 * b] - ax, uy = vertices[3 * b + 1] - ay, uz = vertices[3 * b + 2] - az;
    const vx = vertices[3 * c] - ax, vy = vertices[3 * c + 1] - ay, vz = vertices[3 * c + 2] - az;
    const nx = uy * vz - uz * vy;
    const ny = uz * vx - ux * vz;
    const nz = ux * vy - uy * vx;
    const len = Math.hypot(nx, ny, nz);
    if (len > 1e-12) {
      faceNx[t] = nx / len;
      faceNy[t] = ny / len;
      faceNz[t] = nz / len;
      faceArea[t] = 0.5 * len;
    }
    const pairs = [[a, b], [b, c], [c, a]];
    for (let p = 0; p < 3; p++) {
      const u = pairs[p][0] < pairs[p][1] ? pairs[p][0] : pairs[p][1];
      const v = pairs[p][0] < pairs[p][1] ? pairs[p][1] : pairs[p][0];
      const key = u * vCount + v;
      const prev = edgeMap.get(key);
      if (prev === undefined) {
        edgeMap.set(key, t);
      } else if (prev >= 0) {
        edgeMap.set(key, -(prev * triCount + t + 1));
      } else {
        edgeMap.set(key, -Number.MAX_SAFE_INTEGER);
      }
    }
  }

  const parent = new Int32Array(triCount);
  for (let t = 0; t < triCount; t++) parent[t] = t;
  const find = (x) => {
    while (parent[x] !== x) {
      parent[x] = parent[parent[x]];
      x = parent[x];
    }
    return x;
  };
  for (const val of edgeMap.values()) {
    if (val < 0 && val > -Number.MAX_SAFE_INTEGER) {
      const code = -val - 1;
      const t0 = Math.floor(code / triCount);
      const t1 = code - t0 * triCount;
      const dot = faceNx[t0] * faceNx[t1] + faceNy[t0] * faceNy[t1] + faceNz[t0] * faceNz[t1];
      if (dot >= cosLimit) {
        const r0 = find(t0), r1 = find(t1);
        if (r0 !== r1) parent[r1] = r0;
      }
    }
  }

  const slotMap = new Map();
  const outPos = [];
  const outNx = [];
  const outNy = [];
  const outNz = [];
  const outCol = useColors ? [] : null;
  const outIdx = new Uint32Array(triangles.length);
  for (let t = 0; t < triCount; t++) {
    const grp = find(t);
    const w = faceArea[t] || 1e-6;
    const wx = faceNx[t] * w, wy = faceNy[t] * w, wz = faceNz[t] * w;
    const cTag = useColors
      ? `${triColors[3 * t]},${triColors[3 * t + 1]},${triColors[3 * t + 2]}`
      : "";
    for (let k = 0; k < 3; k++) {
      const vi = triangles[3 * t + k];
      const skey = useColors ? `${vi}:${grp}:${cTag}` : `${vi}:${grp}`;
      let slot = slotMap.get(skey);
      if (slot === undefined) {
        slot = outNx.length;
        slotMap.set(skey, slot);
        outPos.push(vertices[3 * vi], vertices[3 * vi + 1], vertices[3 * vi + 2]);
        outNx.push(wx);
        outNy.push(wy);
        outNz.push(wz);
        if (useColors) {
          outCol.push(
            triColors[3 * t] / 255,
            triColors[3 * t + 1] / 255,
            triColors[3 * t + 2] / 255,
          );
        }
      } else {
        outNx[slot] += wx;
        outNy[slot] += wy;
        outNz[slot] += wz;
      }
      outIdx[3 * t + k] = slot;
    }
  }
  const outNorm = new Float32Array(outNx.length * 3);
  for (let i = 0; i < outNx.length; i++) {
    const len = Math.hypot(outNx[i], outNy[i], outNz[i]) || 1;
    outNorm[3 * i] = outNx[i] / len;
    outNorm[3 * i + 1] = outNy[i] / len;
    outNorm[3 * i + 2] = outNz[i] / len;
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(outPos), 3));
  g.setAttribute("normal", new THREE.BufferAttribute(outNorm, 3));
  if (useColors) {
    g.setAttribute("color", new THREE.BufferAttribute(new Float32Array(outCol), 3));
  }
  g.setIndex(new THREE.BufferAttribute(outIdx, 1));
  return g;
}

function buildMesh(vertices, triangles, triColors = null) {
  const geometry = buildCreaseGeometry(vertices, triangles, CREASE_ANGLE_DEG, triColors);
  hasNativeTriColors = !!geometry.getAttribute("color");
  const preset = MATERIAL_PRESETS[materialPreset] || MATERIAL_PRESETS.native;
  const useVertColors = hasNativeTriColors && materialPreset === "native";
  solidMaterial = new THREE.MeshStandardMaterial({
    color: useVertColors ? 0xffffff : preset.color,
    vertexColors: useVertColors,
    metalness: preset.metalness,
    roughness: preset.roughness,
    wireframe: showWireframe,
    flatShading: showEvenShading,
    side: THREE.DoubleSide, // open shells are legitimate (G3 F6)
  });
  // A Group holding the surface mesh(es): one mesh when the Bodies
  // labeling is pending or finds a single visual component, one mesh
  // per component once a multi-component labeling lands (each with its
  // own draw range over the shared attributes — no duplicated data).
  meshObject = new THREE.Group();
  const surface = new THREE.Mesh(geometry, solidMaterial);
  surface.name = "surface";
  meshObject.add(surface);
  scene.add(meshObject);

  // The CATIA-style crease-edge overlay (2026-11-21): dark subtle lines
  // along face pairs meeting past 25 degrees (EdgesGeometry's threshold
  // angle), on by default next to the Wireframe toggle. A sibling
  // object, not a child: the mesh's DoubleSide shading is untouched and
  // the overlay disposes with the file's scene (clearScene). Hidden
  // while a Bodies component is toggled off (the overlay has no
  // per-component ranges; it comes back at full visibility).
  const edgesGeometry = new THREE.EdgesGeometry(geometry, CREASE_ANGLE_DEG);
  edgesObject = new THREE.LineSegments(
    edgesGeometry,
    new THREE.LineBasicMaterial({
      color: 0x16202e,
      transparent: true,
      opacity: 0.85,
    }),
  );
  edgesObject.visible = showEdges;
  scene.add(edgesObject);

  // Frame the bounding sphere the summary reports (already the pool's
  // extents; the Float32Array coordinates are the same values) — and
  // settle into the CATIA isometric view, the CAD default.
  geometry.computeBoundingSphere();
  const sphere = geometry.boundingSphere;
  sceneBounds = {
    center: sphere.center.clone(),
    radius: Math.max(sphere.radius, 1e-6),
  };
  orbit.setPreset("iso", {
    center: sceneBounds.center,
    radius: sceneBounds.radius,
  });
  labelBodies(geometry, (vertices.length / 3) | 0, triangles);
}

/* ---- Bodies (w22, 2026-11-22) ----
   The visual components of the decoded mesh, computed client-side
   (site/viewer/cadviews.js computeComponents: union-find over the
   shared VERTEX indices, chunked so a Dodge-scale mesh never blocks
   the main thread). One visual component renders as the ordinary
   single mesh — nothing changes; N >= 2 components re-render as one
   mesh per component (per-geometry draw ranges over the SAME position
   and normal attributes — the exported mesh data is untouched, this
   is a viewer-side grouping). The panel says what this is and is not:
   a visual grouping by shared vertices, never a decoded CATIA body
   boundary — the export contract carries one merged pool and the
   parser is out of reach for the viewer. */

async function labelBodies(geometry, weldedVertCount, weldedIndices) {
  const epoch = ++bodiesEpoch;
  const indexAttr = geometry.getIndex();
  const position = geometry.getAttribute("position");
  viewerState.bodies = { count: 1, components: [], allVisible: true, measuring: true };
  renderBodiesPanel();
  const result = await computeComponents(weldedVertCount || position.count, weldedIndices || indexAttr.array);
  if (epoch !== bodiesEpoch || !meshObject) return; // a newer load took over
  if (result.count >= 2) {
    const surface = meshObject.children.find((child) => child.name === "surface");
    const { index, ranges } = reorderByComponents(indexAttr.array, result.labels, result.count);
    const positionAttr = surface.geometry.getAttribute("position");
    const normalAttr = surface.geometry.getAttribute("normal");
    const colorAttr = surface.geometry.getAttribute("color");
    meshObject.remove(surface);
    surface.geometry.dispose(); // the shared attributes re-upload once, then reuse
    bodiesComponents = ranges.map((range, k) => {
      const compGeometry = new THREE.BufferGeometry();
      compGeometry.setAttribute("position", positionAttr);
      compGeometry.setAttribute("normal", normalAttr);
      if (colorAttr) compGeometry.setAttribute("color", colorAttr);
      compGeometry.setIndex(
        new THREE.BufferAttribute(index.subarray(range.start, range.start + range.count), 1),
      );
      compGeometry.setDrawRange(0, range.count);
      const mesh = new THREE.Mesh(compGeometry, solidMaterial);
      mesh.name = `body-${k}`;
      mesh.visible = true;
      meshObject.add(mesh);
      return { mesh, triangles: range.triangles, visible: true };
    });
    refreshEdgesVisibility();
  }
  viewerState.bodies = {
    count: result.count,
    components: (bodiesComponents || []).map((comp) => ({
      triangles: comp.triangles,
      visible: comp.visible,
    })),
    allVisible: true,
    measuring: false,
  };
  renderBodiesPanel();
  publishState();
}

function refreshEdgesVisibility() {
  if (!edgesObject) return;
  const allVisible = !bodiesComponents || bodiesComponents.every((comp) => comp.visible);
  edgesObject.visible = showEdges && allVisible;
}

function renderBodiesPanel() {
  if (!els.bodiesPanel || !els.bodiesList) return;
  const state = viewerState.bodies;
  if (!state || (!state.measuring && (!state.components || state.count < 2))) {
    els.bodiesPanel.hidden = true;
    els.bodiesList.innerHTML = "";
    return;
  }
  els.bodiesPanel.hidden = false;
  if (state.measuring) {
    // Only reachable while the chunked labeling is still yielding
    // across frames (a Dodge-scale mesh): tiny meshes finish inside
    // the same task, before the next paint.
    els.bodiesList.innerHTML = `<p class="dim">measuring visual components…</p>`;
    return;
  }
  const rows = bodiesComponents
    .map(
      (comp, k) =>
        `<div class="body-row${comp.visible ? "" : " body-hidden"}">` +
        `<button type="button" class="body-toggle" data-body="${k}" aria-pressed="${comp.visible ? "true" : "false"}">${comp.visible ? "visible" : "hidden"}</button>` +
        `<span class="body-name">Component ${k + 1}</span>` +
        `<span class="dim">${comp.triangles.toLocaleString("en")} tri</span>` +
        `</div>`,
    )
    .join("");
  els.bodiesList.innerHTML =
    `${rows}` +
    (state.allVisible
      ? ""
      : `<button type="button" id="bodies-show-all" class="bodies-show-all">Show all</button>`);
}

/* The no-surface display fallback (2026-11-19): a part with zero
   triangles but decoded carriers is drawn as it was decoded — a point
   cloud and the law-pinned curve segments — never as a surface. The
   label element says so; the gate panel still records empty-mesh. */
function buildDisplayCarriers(points, curveSegments) {
  displayGroup = new THREE.Group();
  const positions = new THREE.BufferAttribute(points, 3);
  if (points.length > 0) {
    const cloudGeometry = new THREE.BufferGeometry();
    cloudGeometry.setAttribute("position", positions);
    const cloud = new THREE.Points(
      cloudGeometry,
      new THREE.PointsMaterial({
        color: 0xffc857,
        size: 4,
        sizeAttenuation: false, // pixel size: visible at any model scale
      }),
    );
    displayGroup.add(cloud);
  }
  if (curveSegments.length > 0 && points.length > 0) {
    const segmentGeometry = new THREE.BufferGeometry();
    segmentGeometry.setAttribute(
      "position",
      new THREE.BufferAttribute(points, 3),
    );
    segmentGeometry.setIndex(new THREE.BufferAttribute(curveSegments, 1));
    displayGroup.add(
      new THREE.LineSegments(
        segmentGeometry,
        new THREE.LineBasicMaterial({ color: 0x38e1ff }),
      ),
    );
  }
  scene.add(displayGroup);

  const box = new THREE.Box3().setFromBufferAttribute(positions);
  const sphere = box.getBoundingSphere(new THREE.Sphere());
  sceneBounds = {
    center: sphere.center.clone(),
    radius: Math.max(sphere.radius, 1e-6),
  };
  orbit.setPreset("iso", {
    center: sceneBounds.center,
    radius: sceneBounds.radius,
  });
}

function setDisplayLabel(label) {
  if (!els.displayLabel) return;
  els.displayLabel.hidden = !label;
  if (els.displayLabelText) els.displayLabelText.textContent = label || "";
}

function buildCurves(curves) {
  curveGroup = new THREE.Group();
  const material = new THREE.LineBasicMaterial({ color: 0x38e1ff });
  for (const loop of curves) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(loop, 3));
    curveGroup.add(new THREE.Line(geometry, material.clone()));
  }
  curveGroup.visible = showCurves;
  scene.add(curveGroup);
}

/* ---- panels ---- */

function setStatus(text) {
  els.status.textContent = text;
}

function fmtBbox(bbox) {
  if (!bbox) return "null";
  const f = (v) => {
    // Shortest round-trip-ish rendering; finite by the gate's law.
    return String(Number(v.toPrecision(8)));
  };
  return (
    "min [" +
    bbox.min.map(f).join(", ") +
    "]  max [" +
    bbox.max.map(f).join(", ") +
    "]"
  );
}

function renderGate(summary) {
  const record = scoreExport(summary);
  const badge = record.status === "pass" ? "pill good" : "pill bad";
  const failed = record.failed_check
    ? `<div class="kv"><span>failed check</span><code>${record.failed_check}</code></div>`
    : "";
  const warnings = (summary.warnings || [])
    .map((w) => `<li><code>${esc(w.class)}</code> — ${esc(w.detail)}</li>`)
    .join("");
  els.gate.innerHTML = `
    <div class="gate-head"><span class="${badge}">${record.status}</span>
      <span class="dim">the §3.4 gate — the _score_export mirror</span></div>
    ${failed}
    <div class="kv"><span>vertices</span><code>${record.vertex_count}</code></div>
    <div class="kv"><span>triangles</span><code>${record.triangle_count}</code></div>
    <div class="kv"><span>degenerate</span><code>${record.degenerate_triangle_count}</code> <span class="dim">(max ${MAX_DEGENERATE_TRIANGLES})</span></div>
    <div class="kv"><span>bounding box</span><code>${fmtBbox(record.bounding_box)}</code></div>
    ${warnings ? `<div class="kv"><span>warnings</span></div><ul class="warns">${warnings}</ul>` : ""}
  `;
  return record;
}

function clearGate() {
  if (els.gate) {
    els.gate.innerHTML = `<p class="dim">no export — the decode failed (see the classified error)</p>`;
  }
}

/* ---- Feature / Spec Tree (w4, 2026-11-22) ----
   The part's parametric records, named from the writer's length-framed
   feature-type names: a length byte L (4..40) followed by exactly L-1
   ASCII bytes whose FULL text matches a pinned PartDesign/GSD type with
   an optional instance suffix (.N / N) — the measured framing
   00 07 "Sketch", 05 "Pad1", 09 "Sketch.1", 0b "EdgeFillet"
   (docs/evidence/2026-11-22-feature-tree.md).  The same vocabulary and
   framing the Python reference scans (catpart.geometry.display
   .scan_feature_tree) and the summary's additive feature_tree block
   carries; the client-side scan here covers the parts whose export
   classified-failed (no summary is emitted for them), so the tree is
   still on screen — labeled feature-tree-only, never geometry. */

const FEATURE_TYPES = [
  "Axis", "Boundary", "Chamfer", "Circle", "Curve", "EdgeFillet", "Hole",
  "Line", "Mirror", "Offset", "Pad", "Pattern", "Plane", "Point", "Pocket",
  "Rib", "Sketch",
];

function featureTypeOf(name) {
  for (const typ of FEATURE_TYPES) {
    if (!name.startsWith(typ)) continue;
    const rest = name.slice(typ.length);
    const digits = rest.startsWith(".")
      ? rest.slice(1)
      : rest;
    const ok = rest.startsWith(".")
      ? digits.length > 0 && /^\d+$/.test(digits)
      : rest.length === 0 || /^\d+$/.test(rest);
    if (ok) return typ;
  }
  return null;
}

function scanFeatureTree(bytes) {
  const containers = countToken(bytes, "CATPrtCont");
  const order = [];
  const counts = new Map();
  const offsets = new Map();
  let total = 0;
  for (let i = 0; i + 4 <= bytes.length; i++) {
    const length = bytes[i];
    if (length < 4 || length > 40 || i + length > bytes.length) continue;
    // the maximal [A-Za-z0-9_.] run (the twin's candidate regex), capped
    // at 39 characters, validated against the length byte's promise
    let run = 0;
    const cap = Math.min(bytes.length - (i + 1), 39);
    while (
      run < cap &&
      isNameByte(bytes[i + 1 + run])
    ) run++;
    if (run < 3 || run !== length - 1) continue;
    let text = "";
    for (let k = 0; k < run; k++) text += String.fromCharCode(bytes[i + 1 + k]);
    const typ = featureTypeOf(text);
    if (!typ) continue;
    total++;
    counts.set(typ, (counts.get(typ) || 0) + 1);
    if (!offsets.has(typ)) {
      offsets.set(typ, i + 1);
      order.push(typ);
    }
  }
  return {
    containers,
    features: order.map((typ) => ({
      type: typ,
      count: counts.get(typ),
      first_offset: offsets.get(typ),
    })),
    feature_names: total,
  };
}

function isNameByte(b) {
  return (
    (b >= 0x41 && b <= 0x5a) ||
    (b >= 0x61 && b <= 0x7a) ||
    (b >= 0x30 && b <= 0x39) ||
    b === 0x5f ||
    b === 0x2e
  );
}

function countToken(bytes, token) {
  let count = 0;
  for (let i = 0; i + token.length <= bytes.length; i++) {
    let hit = true;
    for (let k = 0; k < token.length; k++) {
      if (bytes[i + k] !== token.charCodeAt(k)) {
        hit = false;
        break;
      }
    }
    if (hit) count++;
  }
  return count;
}

function renderFeatureTree(tree, hasGeometry) {
  if (!els.featurePanel || !els.featureTree) return;
  if (!tree || (!tree.containers && tree.features.length === 0)) {
    els.featurePanel.hidden = true;
    return;
  }
  els.featurePanel.hidden = false;
  // The feature rows are buttons: clicking one highlights it and shows
  // where its framed records live in the file (the only per-feature
  // data the census carries — the offset, the count). A selection is
  // a highlight of the OPERATION's name census, never a geometry claim.
  const rows = tree.features
    .map(
      (feature) =>
        `<li><button type="button" class="feature-row" data-type="${esc(feature.type)}" ` +
        `data-count="${feature.count}" data-offset="${feature.first_offset}" aria-pressed="false">` +
        `<span class="feature-type">${esc(feature.type)}</span>` +
        `<span class="feature-count">${feature.count}</span></button></li>`,
    )
    .join("");
  const badge = hasGeometry
    ? ""
    : `<span class="feature-badge">no-geometry</span>`;
  els.featureTree.innerHTML = `
    <div class="feature-head">
      <span class="feature-kind">feature-tree-only</span>${badge}
    </div>
    <ul class="feature-list">
      <li class="feature-row feature-container">
        <span class="feature-type">CATPrtCont</span>
        <span class="feature-count">${tree.containers}</span>
      </li>
      ${rows || `<li class="feature-row dim"><span class="feature-type">no framed feature name</span></li>`}
    </ul>
    <p class="feature-note dim">${tree.feature_names} framed feature-name record(s), byte order —
    a name census of the parametric records, never a surface and never
    counted as geometry.</p>
  `;
}

/* The feature-row click: toggle the highlight, render the record's
   location detail (byte offset in hex + decimal). */
function onFeatureRowClick(button) {
  const wasSelected = button.classList.contains("selected");
  for (const row of els.featureTree.querySelectorAll("button.feature-row.selected")) {
    row.classList.remove("selected");
    row.setAttribute("aria-pressed", "false");
  }
  if (wasSelected) {
    viewerState.featureSelection = null;
    if (els.featureDetail) {
      els.featureDetail.hidden = true;
      els.featureDetail.textContent = "";
    }
    return;
  }
  button.classList.add("selected");
  button.setAttribute("aria-pressed", "true");
  const type = button.dataset.type;
  const count = Number(button.dataset.count);
  const offset = Number(button.dataset.offset);
  viewerState.featureSelection = { type, count, firstOffset: offset };
  if (els.featureDetail) {
    els.featureDetail.hidden = false;
    els.featureDetail.textContent =
      `${type}: ${count} framed record(s) — first at byte ${offset} ` +
      `(0x${offset.toString(16).toUpperCase()}). A name census location, never geometry.`;
  }
}

function clearFeatureTree() {
  if (!els.featurePanel || !els.featureTree) return;
  els.featurePanel.hidden = true;
  els.featureTree.innerHTML = "";
  viewerState.featureSelection = null;
  if (els.featureDetail) {
    els.featureDetail.hidden = true;
    els.featureDetail.textContent = "";
  }
}

function esc(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function renderMeta(doc) {
  if (!els.meta) return;
  const containers = (doc.containers || [])
    .map(
      (c) =>
        `<tr><td>${esc(c.name)}</td><td>${esc(c.parent_name)}</td><td>${c.index}</td></tr>`,
    )
    .join("");
  const trailer = doc.trailer
    ? `A=${doc.trailer.a} G=${doc.trailer.tail_region_length}`
    : "null";
  els.meta.innerHTML = `
    <div class="kv"><span>schema</span><code>v${doc.schema_version}</code></div>
    <div class="kv"><span>document name</span><code>${doc.document_name ? esc(doc.document_name) : "—"}</code></div>
    <div class="kv"><span>detected version</span><code>${esc(doc.detected_version)}</code></div>
    <div class="kv"><span>kind</span><code>${esc(doc.kind)}</code></div>
    <div class="kv"><span>file size</span><code>${doc.file_size.toLocaleString("en")} B</code></div>
    <div class="kv"><span>magic</span><code>${esc(doc.magic)}</code></div>
    <div class="kv"><span>trailer</span><code>${esc(trailer)}</code></div>
    <div class="kv"><span>containers (${(doc.containers || []).length})</span></div>
    ${containers ? `<table class="ctable"><tr><th>name</th><th>parent</th><th>idx</th></tr>${containers}</table>` : "—"}
  `;
}

function showError(cls, detail) {
  els.errorPanel.hidden = false;
  els.errorClass.textContent = cls;
  els.errorDetail.textContent = detail;
}

function clearError() {
  els.errorPanel.hidden = true;
  els.errorClass.textContent = "";
  els.errorDetail.textContent = "";
}

function refreshToggles(curveCount) {
  els.curveState.textContent = `${curveCount} loop${curveCount === 1 ? "" : "s"}`;
  els.curvesBtn.disabled = curveCount === 0;
  els.curvesBtn.setAttribute("aria-pressed", showCurves ? "true" : "false");
  els.wireBtn.setAttribute("aria-pressed", showWireframe ? "true" : "false");
  els.edgesBtn.setAttribute("aria-pressed", showEdges ? "true" : "false");
  els.shadingBtn.setAttribute("aria-pressed", showEvenShading ? "true" : "false");
  els.materialBtn.setAttribute("aria-pressed", materialPreset === "native" ? "true" : "false");
}

/* The scripted-check surface (window.viewer): the same state the
   panels render, machine-readable for Playwright acceptance
   (scripts/viewer_acceptance.py and scripts/assembly_viewer_acceptance.py)
   — read-only, never required to use the page. */
const viewerState = {
  status: "idle",
  mode: "part", // "part" | "assembly"
  fileName: null,
  gate: null,
  error: null,
  summary: null,
  inspect: null,
  curveCount: 0,
  curvesVisible: false,
  wireframe: false,
  edgesVisible: true,
  evenShading: false, // flat shading: every fragment shades front-facing
  shading: "smooth", // "smooth" | "flat" (the material state)
  materialPreset: "native", // "native" | "cad-gray"
  creaseAngleDeg: CREASE_ANGLE_DEG,
  view: null, // the CAD-view pose readout (cadviews.js)
  bodies: null, // the visual components (never decoded body boundaries)
  featureSelection: null, // the highlighted feature-census row
  display: null,
  assembly: null,
};

function publishState() {
  viewerState.curvesVisible = showCurves;
  viewerState.wireframe = showWireframe;
  viewerState.edgesVisible = showEdges;
  viewerState.evenShading = showEvenShading;
  viewerState.shading = showEvenShading ? "flat" : "smooth";
  viewerState.materialPreset = materialPreset;
  viewerState.creaseAngleDeg = CREASE_ANGLE_DEG;
  viewerState.view = orbit.readout();
  window.viewer = viewerState;
}

/* The current fit bounds for the standard-view buttons: the mesh's
   bounding sphere in part mode (already computed at build time), the
   scene's world bounding sphere in assembly mode. Camera-only work. */
function currentFit() {
  if (viewerState.mode === "assembly") {
    return assemblyScene.computeBoundingSphere("world");
  }
  return sceneBounds || { center: new THREE.Vector3(), radius: 10 };
}

/* The even-shading option (w22): flat shading on the material only —
   three.js derives per-fragment normals from screen-space derivatives
   (always front-facing), so mixed winding in the exported mesh stops
   producing dark faces. The mesh data (vertices, triangles, normals)
   is never touched, and the toggle costs one shader recompile, not a
   geometry pass — safe at Dodge scale. */
function applyMaterialPreset(name) {
  materialPreset = name in MATERIAL_PRESETS ? name : "native";
  const p = MATERIAL_PRESETS[materialPreset];
  const useVertColors = hasNativeTriColors && materialPreset === "native";
  if (solidMaterial) {
    solidMaterial.color.setHex(useVertColors ? 0xffffff : p.color);
    solidMaterial.vertexColors = useVertColors;
    solidMaterial.metalness = p.metalness;
    solidMaterial.roughness = p.roughness;
    solidMaterial.needsUpdate = true;
  }
  for (const inst of assemblyScene.instances.values()) {
    inst.traverse((child) => {
      if (child.isMesh && child.material) {
        const instHasCols = !!(child.geometry && child.geometry.getAttribute("color"));
        const useInstCols = instHasCols && materialPreset === "native";
        child.material.color.setHex(useInstCols ? 0xffffff : p.color);
        child.material.vertexColors = useInstCols;
        child.material.metalness = p.metalness;
        child.material.roughness = p.roughness;
        child.material.needsUpdate = true;
      }
    });
  }
  publishState();
}

function applyEvenShading(on) {
  showEvenShading = !!on;
  if (solidMaterial) {
    solidMaterial.flatShading = showEvenShading;
    solidMaterial.needsUpdate = true;
  }
  for (const inst of assemblyScene.instances.values()) {
    inst.traverse((child) => {
      if (child.isMesh && child.material && child.material.flatShading !== showEvenShading) {
        child.material.flatShading = showEvenShading;
        child.material.needsUpdate = true;
      }
    });
  }
}

/* ---- loading (Part Mode) ---- */

async function loadFile(file) {
  setUIMode("part");
  els.drop.classList.add("compact");
  clearGate();
  clearError();
  clearScene();
  showCurves = false;
  refreshToggles(0);
  viewerState.status = "decoding";
  viewerState.fileName = file.name;
  viewerState.error = null;
  viewerState.gate = null;
  viewerState.summary = null;
  viewerState.inspect = null;
  viewerState.curveCount = 0;
  viewerState.display = null;
  viewerState.assembly = null;
  viewerState.bodies = null;
  viewerState.featureSelection = null;
  publishState();
  setStatus(`decoding ${file.name} (${file.size.toLocaleString("en")} B)…`);
  const bytes = new Uint8Array(await file.arrayBuffer());
  let summary = null;
  let decoded = null;
  let doc = null;
  let exportError = null;
  let inspectError = null;
  try {
    decoded = decode_export(bytes);
    summary = decoded.summary;
    viewerState.curveCount = decoded.curves.length;
  } catch (err) {
    exportError = err;
  }
  const displayBlock = summary ? summary.no_surface_display : null;
  const displayPoints = decoded && decoded.points ? decoded.points : null;
  const displaySegments =
    decoded && decoded.curveSegments ? decoded.curveSegments : null;
  const hasDisplay =
    displayBlock !== null &&
    displayBlock !== undefined &&
    displayPoints !== null &&
    displayPoints.length > 0; // segments are always indexed into points
  if (decoded) {
    if (decoded.triangles.length > 0) {
      buildMesh(decoded.vertices, decoded.triangles, decoded.triColors || null);
    }
    buildCurves(decoded.curves);
  }
  setDisplayLabel(hasDisplay ? displayBlock.label : null);
  if (hasDisplay) {
    buildDisplayCarriers(displayPoints, displaySegments || new Uint32Array());
  }
  try {
    doc = decode_inspect(bytes);
  } catch (err) {
    inspectError = err;
  }

  if (doc) {
    viewerState.inspect = {
      schema_version: doc.schema_version,
      document_name: doc.document_name,
      detected_version: doc.detected_version,
      kind: doc.kind,
      file_size: doc.file_size,
      container_count: (doc.containers || []).length,
    };
    renderMeta(doc);
  } else if (inspectError && els.meta) {
    els.meta.innerHTML = `<div class="kv"><span>inspect failed</span><code>${esc(
      inspectError.error_class || "unknown",
    )}</code></div><p class="dim">${esc(inspectError.detail || "")}</p>`;
  }

  if (summary) {
    viewerState.summary = {
      vertex_count: summary.vertex_count,
      triangle_count: summary.triangle_count,
      degenerate_triangle_count: summary.degenerate_triangle_count,
      manifold: summary.mesh.manifold,
      mesh: summary.mesh,
      warnings: summary.warnings || [],
    };
    viewerState.gate = renderGate(summary);
    refreshToggles(viewerState.curveCount);
  } else {
    clearGate();
  }
  // The Feature / Spec Tree: the summary's additive block when the
  // export emitted one, the client-side scan over the raw bytes
  // otherwise (the classified-failure parts keep their error panel AND
  // their tree — a name census, never geometry).
  const featureTree =
    summary && summary.feature_tree
      ? summary.feature_tree
      : scanFeatureTree(bytes);
  const hasGeometry =
    (summary && summary.triangle_count > 0) ||
    hasDisplay ||
    (decoded && decoded.triangles.length > 0);
  renderFeatureTree(featureTree, hasGeometry);

  // A decode can succeed and still export no surface. Two outcomes are
  // distinct and never conflated:
  //  - the part carries decoded carriers (points / law-pinned curve
  //    segments): it renders as exactly that, labelled "no surface —
  //    showing N points, M curve segments", and is never described as a
  //    surface render;
  //  - it carries nothing (0 points / 0 curve segments / 0 triangles):
  //    the named §3.4 empty-mesh failure, with the counts still on screen.
  const emptyMesh = summary !== null && summary.triangle_count === 0;
  viewerState.display = hasDisplay
    ? {
        mode: "no-surface",
        label: displayBlock.label,
        pointCount: displayPoints.length / 3,
        curveSegmentCount: displaySegments ? displaySegments.length / 2 : 0,
        drawn: displayGroup
          ? {
              points: displayGroup.children.some((child) => child.isPoints),
              segments: displayGroup.children.some(
                (child) => child.isLineSegments,
              ),
            }
          : { points: false, segments: false },
      }
    : null;
  els.canvas.hidden = !summary || (emptyMesh && !hasDisplay);
  if (exportError) {
    viewerState.error = {
      error_class: exportError.error_class || null,
      detail: exportError.detail || String(exportError),
    };
    showError(
      viewerState.error.error_class || "unknown",
      viewerState.error.detail,
    );
    setStatus(`${file.name}: decode failed`);
    viewerState.status = "failed";
  } else if (emptyMesh && !hasDisplay) {
    const reason =
      `${CHECK_EMPTY_MESH}: ${summary.vertex_count} vertices decoded, ` +
      `${summary.triangle_count} triangles`;
    viewerState.error = {
      error_class: CHECK_EMPTY_MESH,
      detail: `${reason} — the export carries no drawable surface`,
    };
    showError(viewerState.error.error_class, viewerState.error.detail);
    setStatus(`${file.name} — ${reason}`);
    viewerState.status = "failed";
  } else if (hasDisplay) {
    setStatus(
      `${file.name} — ${displayBlock.label} ` +
        "(decoded carriers, not a surface render)",
    );
    viewerState.status = "loaded";
  } else {
    setStatus(
      `${file.name} — ${summary.vertex_count} vertices, ` +
        `${summary.triangle_count} triangles`,
    );
    viewerState.status = "loaded";
  }
  publishState();
  resize();
}

/* ---- loading (Assembly Mode) ---- */

async function loadAssemblyFromCatalog(catalog, preferredRoot = null) {
  activeCatalog = catalog;
  setUIMode("assembly");
  els.drop.classList.add("compact");
  clearGate();
  clearError();
  clearFeatureTree();
  clearScene();
  viewerState.status = "decoding";
  viewerState.error = null;
  viewerState.gate = null;
  viewerState.summary = null;
  viewerState.inspect = null;
  viewerState.assembly = null;
  viewerState.bodies = null;
  viewerState.featureSelection = null;
  publishState();

  const candidates = catalog.getProducts();
  if (candidates.length === 0) {
    throw {
      error_class: "missing-product-file",
      detail: "No .CATProduct file found in uploaded archive or folder",
    };
  }

  let rootProduct = null;
  if (preferredRoot) {
    rootProduct = catalog.resolveProduct(preferredRoot) || catalog.byPath.get(preferredRoot);
  }
  if (!rootProduct) {
    rootProduct = candidates[0];
  }

  viewerState.fileName = rootProduct.name;
  setStatus(`decoding product ${rootProduct.name}…`);

  const bytes = await rootProduct.getBytes();
  const doc = decode_product_structure(bytes);

  // Load into AssemblyScene (instancing, GPU buffer pool, bounds)
  const counts = await assemblyScene.loadAssembly(doc, catalog, {
    decodeExport: decode_export,
    orbit,
    autoFrame: true,
  });

  // Load into AssemblyUI (instance tree, badges, inspector, summary bar)
  assemblyUI.setAssembly(doc, catalog);
  if (candidates.length > 1) {
    assemblyUI.setProductList(candidates, rootProduct.name);
  } else {
    assemblyUI.setProductList([]);
  }

  const sphereData = assemblyScene.computeBoundingSphere("world");
  // Settle into the CATIA isometric view for the loaded product (the
  // autoFrame's plain fit already ran inside loadAssembly).
  orbit.setPreset("iso", {
    center: sphereData.center,
    radius: Math.max(sphereData.radius, 1e-6),
  });

  viewerState.assembly = {
    document: doc,
    catalog: catalog,
    totalInstances: counts.totalInstances,
    placedInstances: counts.placedInstances,
    identityInstances: counts.identityInstances,
    unresolvedInstances: counts.unresolvedInstances,
    undecodableInstances: counts.undecodableInstances,
    uniqueGeometries: counts.uniqueGeometries,
    uniqueMeshAllocations: counts.uniqueGeometries,
    counts: {
      total: counts.totalInstances,
      placed: counts.placedInstances,
      identity: counts.identityInstances,
      unresolved: counts.unresolvedInstances,
      undecodable: counts.undecodableInstances,
    },
    tallies: {
      total: counts.totalInstances,
      placed: counts.placedInstances,
      identity: counts.identityInstances,
      unresolved: counts.unresolvedInstances,
      undecodable: counts.undecodableInstances,
    },
    boundingSphere: {
      center: [sphereData.center.x, sphereData.center.y, sphereData.center.z],
      radius: sphereData.radius,
    },
    instances: Array.from(assemblyScene.instances.values()).map((inst) => ({
      instanceName: inst.userData.instanceName,
      partNumber: inst.userData.partNumber,
      status: inst.userData.placementStatus,
      placementStatus: inst.userData.placementStatus,
      transform: inst.userData.transform,
      isPlacedSpatial: inst.userData.isPlacedSpatial,
      visible: inst.visible,
    })),
  };

  els.canvas.hidden = false;
  const allUnresolved =
    counts.totalInstances > 0 &&
    counts.unresolvedInstances === counts.totalInstances &&
    counts.placedInstances === 0 &&
    counts.identityInstances === 0;
  setStatus(
    allUnresolved
      ? `${rootProduct.name} — ${counts.totalInstances} unresolved instance${counts.totalInstances === 1 ? "" : "s"}: ` +
          `a .CATProduct contains no 3D mesh; drop the folder, a .zip, or select the .CATProduct together with its .CATPart files.`
      : `${rootProduct.name} — ${counts.totalInstances} instance${counts.totalInstances === 1 ? "" : "s"} ` +
          `(${counts.placedInstances} placed, ${counts.identityInstances} identity, ` +
          `${counts.unresolvedInstances} unresolved, ${counts.undecodableInstances} undecodable)`,
  );
  viewerState.status = "loaded";
  publishState();
  resize();
}

/* ---- Input Handling (Single Part vs Multi-File / Assembly) ---- */

async function handleUploadedInputs(inputs) {
  let isSinglePart = false;
  if (inputs instanceof FileList || Array.isArray(inputs)) {
    if (inputs.length === 1) {
      const name = inputs[0].name.toLowerCase();
      if (name.endsWith(".catpart") && !name.endsWith(".zip")) {
        isSinglePart = true;
      }
    }
  } else if (inputs && inputs.name) {
    const name = inputs.name.toLowerCase();
    if (name.endsWith(".catpart") && !name.endsWith(".zip")) {
      isSinglePart = true;
    }
  }

  if (isSinglePart) {
    const file = inputs[0] || inputs;
    await loadFile(file);
    return;
  }

  try {
    const result = await ingestFiles(inputs);
    if (result.hasRootProduct && result.rootProduct) {
      await loadAssemblyFromCatalog(result.catalog, result.rootProduct.name);
    } else if (result.partsCount > 0 && result.productsCount === 0) {
      const firstPart = result.catalog.getParts()[0];
      const bytes = await firstPart.getBytes();
      const fakeFile = new File([bytes], firstPart.name);
      await loadFile(fakeFile);
    } else {
      throw {
        error_class: "missing-product-file",
        detail: "No .CATProduct file found in uploaded files or archive",
      };
    }
  } catch (err) {
    clearScene();
    els.canvas.hidden = true;
    viewerState.status = "failed";
    viewerState.error = {
      error_class: err.error_class || "ingest-error",
      detail: err.detail || String(err),
    };
    showError(viewerState.error.error_class, viewerState.error.detail);
    setStatus("Failed to load assembly");
    publishState();
  }
}

/* ---- inputs listeners ---- */

els.input.addEventListener("change", () => {
  if (els.input.files && els.input.files.length > 0) {
    handleUploadedInputs(els.input.files);
  }
  els.input.value = "";
});

els.drop.addEventListener("click", () => els.input.click());
els.drop.addEventListener("dragover", (ev) => {
  ev.preventDefault();
  els.drop.classList.add("over");
});
els.drop.addEventListener("dragleave", () => els.drop.classList.remove("over"));
els.drop.addEventListener("drop", (ev) => {
  ev.preventDefault();
  els.drop.classList.remove("over");
  if (ev.dataTransfer) {
    handleUploadedInputs(ev.dataTransfer);
  }
});

els.curvesBtn.addEventListener("click", () => {
  showCurves = !showCurves;
  if (curveGroup) curveGroup.visible = showCurves;
  assemblyScene.setCurvesVisible(showCurves);
  refreshToggles(viewerState.curveCount);
  publishState();
});

els.wireBtn.addEventListener("click", () => {
  showWireframe = !showWireframe;
  if (solidMaterial) solidMaterial.wireframe = showWireframe;
  assemblyScene.setWireframe(showWireframe);
  refreshToggles(viewerState.curveCount);
  publishState();
});

els.edgesBtn.addEventListener("click", () => {
  showEdges = !showEdges;
  refreshEdgesVisibility();
  assemblyScene.setEdges(showEdges);
  refreshToggles(viewerState.curveCount);
  publishState();
});

els.shadingBtn.addEventListener("click", () => {
  applyEvenShading(!showEvenShading);
  els.shadingBtn.setAttribute("aria-pressed", showEvenShading ? "true" : "false");
  refreshToggles(viewerState.curveCount);
  publishState();
});

els.materialBtn.addEventListener("click", () => {
  applyMaterialPreset(materialPreset === "native" ? "cad-gray" : "native");
  els.materialBtn.setAttribute("aria-pressed", materialPreset === "native" ? "true" : "false");
});

for (const name of VIEW_NAMES) {
  els.viewButtons[name].addEventListener("click", () => {
    orbit.setPreset(name, currentFit(), () => publishState());
    publishState();
  });
}

els.featureTree.addEventListener("click", (ev) => {
  const button = ev.target.closest("button.feature-row");
  if (!button) return;
  onFeatureRowClick(button);
  publishState();
});

els.bodiesList.addEventListener("click", (ev) => {
  const toggle = ev.target.closest("button.body-toggle");
  if (toggle) {
    const k = Number(toggle.dataset.body);
    const comp = bodiesComponents && bodiesComponents[k];
    if (!comp) return;
    comp.visible = !comp.visible;
    comp.mesh.visible = comp.visible;
    refreshEdgesVisibility();
    const allVisible = bodiesComponents.every((c) => c.visible);
    viewerState.bodies = {
      count: bodiesComponents.length,
      components: bodiesComponents.map((c) => ({ triangles: c.triangles, visible: c.visible })),
      allVisible,
      measuring: false,
    };
    renderBodiesPanel();
    publishState();
    return;
  }
  const showAll = ev.target.closest("button.bodies-show-all");
  if (showAll) {
    for (const comp of bodiesComponents) {
      comp.visible = true;
      comp.mesh.visible = true;
    }
    refreshEdgesVisibility();
    viewerState.bodies = {
      count: bodiesComponents.length,
      components: bodiesComponents.map((c) => ({ triangles: c.triangles, visible: c.visible })),
      allVisible: true,
      measuring: false,
    };
    renderBodiesPanel();
    publishState();
  }
});

/* ---- boot: the wasm module initialises before the first decode ---- */

init()
  .then(() => {
    setStatus("Drop a .CATPart, .CATProduct, or .zip — runs fully in your browser.");
    resize();
  })
  .catch((err) => {
    setStatus("the viewer failed to initialise");
    showError("viewer-init", String(err));
    viewerState.status = "failed";
    publishState();
  });
resize();
publishState();
