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
import { MAX_DEGENERATE_TRIANGLES, scoreExport } from "./gate.js";
import { attachOrbit } from "./orbit.js";
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
  meta: document.getElementById("meta"),
  metaPanel: document.getElementById("meta-panel"),
  curvesBtn: document.getElementById("curve-toggle"),
  wireBtn: document.getElementById("wire-toggle"),
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
const key = new THREE.DirectionalLight(0xffffff, 1.8);
key.position.set(1, 2, 1.5);
scene.add(key);
const orbit = attachOrbit(els.canvas, camera);

let meshObject = null;
let curveGroup = null;
let solidMaterial = null;
let showCurves = false;
let showWireframe = false;

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
  if (mode === "assembly") {
    if (els.assemblyPanel) els.assemblyPanel.hidden = false;
    if (els.inspectorPanel) els.inspectorPanel.hidden = false;
    if (els.explodedToolbar) els.explodedToolbar.hidden = false;
    if (els.gatePanel) els.gatePanel.hidden = true;
    if (els.metaPanel) els.metaPanel.hidden = true;
    viewerState.mode = "assembly";
  } else {
    if (els.assemblyPanel) els.assemblyPanel.hidden = true;
    if (els.inspectorPanel) els.inspectorPanel.hidden = true;
    if (els.explodedToolbar) els.explodedToolbar.hidden = true;
    if (els.gatePanel) els.gatePanel.hidden = false;
    if (els.metaPanel) els.metaPanel.hidden = false;
    viewerState.mode = "part";
  }
}

function clearScene() {
  for (const obj of [meshObject, curveGroup]) {
    if (!obj) continue;
    scene.remove(obj);
    obj.traverse((child) => {
      if (child.geometry) child.geometry.dispose();
      if (child.material) child.material.dispose();
    });
  }
  meshObject = null;
  curveGroup = null;
  assemblyScene.clear();
  if (assemblyUI) assemblyUI.clear();
}

function disposeMesh() {
  clearScene();
}

/* ---- rendering the decoded result (Part Mode) ---- */

function buildMesh(vertices, triangles) {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(vertices, 3));
  geometry.setIndex(new THREE.BufferAttribute(triangles, 1));
  geometry.computeVertexNormals();
  solidMaterial = new THREE.MeshStandardMaterial({
    color: 0x8fb8d8,
    metalness: 0.1,
    roughness: 0.65,
    wireframe: showWireframe,
    side: THREE.DoubleSide, // open shells are legitimate (G3 F6)
  });
  meshObject = new THREE.Mesh(geometry, solidMaterial);
  scene.add(meshObject);

  // Frame the bounding sphere the summary reports (already the pool's
  // extents; the Float32Array coordinates are the same values).
  geometry.computeBoundingSphere();
  const sphere = geometry.boundingSphere;
  orbit.frame(sphere.center, Math.max(sphere.radius, 1e-6));
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
  assembly: null,
};

function publishState() {
  viewerState.curvesVisible = showCurves;
  viewerState.wireframe = showWireframe;
  window.viewer = viewerState;
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
  viewerState.assembly = null;
  publishState();
  setStatus(`decoding ${file.name} (${file.size.toLocaleString("en")} B)…`);
  const bytes = new Uint8Array(await file.arrayBuffer());
  let summary = null;
  let doc = null;
  let exportError = null;
  let inspectError = null;
  try {
    const result = decode_export(bytes);
    summary = result.summary;
    buildMesh(result.vertices, result.triangles);
    buildCurves(result.curves);
    viewerState.curveCount = result.curves.length;
  } catch (err) {
    exportError = err;
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
  els.canvas.hidden = !summary;
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
  clearScene();
  viewerState.status = "decoding";
  viewerState.error = null;
  viewerState.gate = null;
  viewerState.summary = null;
  viewerState.inspect = null;
  viewerState.assembly = null;
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
  setStatus(
    `${rootProduct.name} — ${counts.totalInstances} instance${counts.totalInstances === 1 ? "" : "s"} ` +
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
