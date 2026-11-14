/* The Phase 5 viewer (spec docs/specs/phase5-viewer-spec.md §5): a
   hand-written ES module over the two §2.3 WASM entries and the one
   vendored, pinned three.js module. No bundler, no framework, no
   node_modules — the site's zero-runtime-dependency property.

   Surface: drag-drop / file-picker of a .CATPart; orbit/zoom +
   wireframe/solid on the decoded mesh; the §3.4 sanity gate (gate.js,
   the _score_export mirror); the schema-v1 metadata panel; the curve
   overlay over the decoded polyline loops (the §2.3 additive `curves`
   — pre-weld point sequences, NOT part of the summary); and the
   classified-failure display — a failing decode shows its
   { error_class, detail }, never a blank screen.

   Memory honesty (§10 risk 8): desktop-target only. The file is held
   as an ArrayBuffer, copied into the WASM linear memory, and decoded
   into new typed arrays — ≈3x transient peak; the largest corpus file
   is ~120 MB. Every load disposes the previous scene's GPU resources.
   No margin is declared anywhere in this app (§3.4 — that is V5's
   owner-approved declaration, not the viewer's). */

import * as THREE from "./three.module.min.js";
import init, { decode_export, decode_inspect } from "./pkg/port.js";
import { MAX_DEGENERATE_TRIANGLES, scoreExport } from "./gate.js";
import { attachOrbit } from "./orbit.js";

const els = {
  drop: document.getElementById("drop"),
  input: document.getElementById("file-input"),
  status: document.getElementById("status"),
  canvas: document.getElementById("scene"),
  errorPanel: document.getElementById("error-panel"),
  errorClass: document.getElementById("error-class"),
  errorDetail: document.getElementById("error-detail"),
  gate: document.getElementById("gate"),
  meta: document.getElementById("meta"),
  curvesBtn: document.getElementById("curve-toggle"),
  wireBtn: document.getElementById("wire-toggle"),
  curveState: document.getElementById("curve-state"),
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

function disposeMesh() {
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
}

/* ---- rendering the decoded result ---- */

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
  els.gate.innerHTML = `<p class="dim">no export — the decode failed (see the classified error)</p>`;
}

function esc(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function renderMeta(doc) {
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
   panels render, machine-readable for the local Playwright acceptance
   (scripts/viewer_acceptance.py) — read-only, never required to use
   the page. */
const viewerState = {
  status: "idle",
  fileName: null,
  gate: null,
  error: null,
  summary: null,
  inspect: null,
  curveCount: 0,
  curvesVisible: false,
  wireframe: false,
};

function publishState() {
  viewerState.curvesVisible = showCurves;
  viewerState.wireframe = showWireframe;
  window.viewer = viewerState;
}

/* ---- loading ---- */

async function loadFile(file) {
  // Once a file is in, the drop zone slims to a "load another" bar.
  els.drop.classList.add("compact");
  // Every panel resets per load — the previous file's gate, toggles
  // and mesh never leak into this one's display.
  clearGate();
  clearError();
  disposeMesh();
  showCurves = false;
  refreshToggles(0);
  viewerState.status = "decoding";
  viewerState.fileName = file.name;
  viewerState.error = null;
  viewerState.gate = null;
  viewerState.summary = null;
  viewerState.inspect = null;
  viewerState.curveCount = 0;
  publishState();
  setStatus(`decoding ${file.name} (${file.size.toLocaleString("en")} B)…`);
  const bytes = new Uint8Array(await file.arrayBuffer());
  // The §2.3 entries are whole-buffer; each throws the classified
  // { error_class, detail } object on failure. The two seams fail
  // independently: the metadata panel shows the inspect refusal, the
  // main panel the export refusal.
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
  } else if (inspectError) {
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
    };
    viewerState.gate = renderGate(summary);
    refreshToggles(viewerState.curveCount);
  } else {
    clearGate();
  }
  // Nothing to draw on a refused decode: the classified error takes
  // the stage's place (never a blank screen — §5).
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

/* ---- inputs ---- */

els.input.addEventListener("change", () => {
  const file = els.input.files && els.input.files[0];
  if (file) loadFile(file);
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
  const file = ev.dataTransfer && ev.dataTransfer.files && ev.dataTransfer.files[0];
  if (file) loadFile(file);
});
els.curvesBtn.addEventListener("click", () => {
  showCurves = !showCurves;
  if (curveGroup) curveGroup.visible = showCurves;
  refreshToggles(viewerState.curveCount);
  publishState();
});
els.wireBtn.addEventListener("click", () => {
  showWireframe = !showWireframe;
  if (solidMaterial) solidMaterial.wireframe = showWireframe;
  refreshToggles(viewerState.curveCount);
  publishState();
});

/* ---- boot: the wasm module initialises before the first decode ---- */

init()
  .then(() => {
    setStatus("Drop a .CATPart — the decode runs fully in your browser.");
    resize();
  })
  .catch((err) => {
    // The one failure the classified seam cannot carry: the WASM
    // module itself did not load. Still never a blank screen.
    setStatus("the viewer failed to initialise");
    showError("viewer-init", String(err));
    viewerState.status = "failed";
    publishState();
  });
resize();
publishState();
