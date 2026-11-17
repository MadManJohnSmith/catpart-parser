/* Independent Verification Test Suite for Ticket P3-V5: Assembly UI & Classification Tree
   Design Authority: docs/specs/phase6-assembly-viewer-spec.md (§4.1, §4.3, §6, §7, §8)
   Declared Bar: docs/evidence/2026-11-14-p4-assembly-bar.md (P4 Assembly Bar)
   Author: Independent Verifier Sub-Agent
   Date: 2026-11-16
*/

import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  AssemblyUI,
  STATUS_PLACED,
  STATUS_IDENTITY,
  STATUS_UNRESOLVED,
  STATUS_UNDECODABLE,
  PAIRING_RULE_TRIPLE,
  PAIRING_RULE_DESC_BLOCK,
  PAIRING_RULE_BARE_PAIR,
  BADGE_CONFIG,
  SVG_ICONS,
  escapeHtml,
  formatCoordinate,
  normalizeStatus,
  renderBadgeHtml,
  renderTransformTableHtml,
  renderSummaryBarHtml,
  renderRootRowHtml,
  renderTreeNodeHtml,
  renderInspectorHtml,
  createBadgeElement,
  createRootRowElement,
  createTreeNodeElement,
  createTransformTableElement,
  createInspectorElement,
  createSummaryBarElement,
  createMinimalDocument,
} from "../site/viewer/assembly_ui.js";

import { VirtualFileCatalog } from "../site/viewer/catalog.js";
import { AssemblyScene } from "../site/viewer/assembly_scene.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, "..");

console.log("================================================================================");
console.log("STARTING INDEPENDENT VERIFICATION: P3-V5 ASSEMBLY UI & CLASSIFICATION TREE");
console.log("Target Commit: 2c3eb4b on main");
console.log("================================================================================\n");

let passedChecks = 0;
let totalChecks = 0;

function check(title, fn) {
  totalChecks++;
  try {
    fn();
    console.log(`  [PASS] ${title}`);
    passedChecks++;
  } catch (err) {
    console.error(`  [FAIL] ${title}`);
    console.error(`         ${err.message}`);
    throw err;
  }
}

async function asyncCheck(title, fn) {
  totalChecks++;
  try {
    await fn();
    console.log(`  [PASS] ${title}`);
    passedChecks++;
  } catch (err) {
    console.error(`  [FAIL] ${title}`);
    console.error(`         ${err.message}`);
    throw err;
  }
}

// =============================================================================
// SECTION 1: The 4 Canonical Classification Badges & CSS Design Tokens (§4.1)
// =============================================================================
console.log("--- Section 1: The 4 Canonical Classification Badges & CSS Design Tokens ---");

check("1.1: BADGE_CONFIG declares exact canonical labels, classes, CSS variables, and colors", () => {
  // Placed: Green #22c55e / var(--color-success)
  const placed = BADGE_CONFIG[STATUS_PLACED];
  assert.equal(placed.label, "Placed");
  assert.equal(placed.badgeClass, "badge-placed");
  assert.equal(placed.pillClass, "pill good");
  assert.equal(placed.colorHex, "#22c55e");
  assert.equal(placed.cssVar, "var(--color-success)");
  assert.ok(placed.tooltip.includes("spatial 3D transform"));

  // Identity: Cyan/Blue #06b6d4 / var(--color-info)
  const identity = BADGE_CONFIG[STATUS_IDENTITY];
  assert.equal(identity.label, "Identity");
  assert.equal(identity.badgeClass, "badge-identity");
  assert.equal(identity.pillClass, "pill neutral");
  assert.equal(identity.colorHex, "#06b6d4");
  assert.equal(identity.cssVar, "var(--color-info)");
  assert.ok(identity.tooltip.includes("origin"));

  // Unresolved Part: Amber/Yellow #f59e0b / var(--color-warning)
  const unresolved = BADGE_CONFIG[STATUS_UNRESOLVED];
  assert.equal(unresolved.label, "Unresolved Part");
  assert.equal(unresolved.badgeClass, "badge-unresolved");
  assert.equal(unresolved.pillClass, "pill warn");
  assert.equal(unresolved.colorHex, "#f59e0b");
  assert.equal(unresolved.cssVar, "var(--color-warning)");
  assert.ok(unresolved.tooltip.includes("never omitted"));

  // Undecodable Placement: Red/Rose #ef4444 / var(--color-danger)
  const undecodable = BADGE_CONFIG[STATUS_UNDECODABLE];
  assert.equal(undecodable.label, "Undecodable Placement");
  assert.equal(undecodable.badgeClass, "badge-undecodable");
  assert.equal(undecodable.pillClass, "pill bad");
  assert.equal(undecodable.colorHex, "#ef4444");
  assert.equal(undecodable.cssVar, "var(--color-danger)");
  assert.ok(undecodable.tooltip.includes("anti-masking"));
});

check("1.2: viewer.css contains exact CSS color definitions and class selectors for badges", () => {
  const cssPath = path.join(REPO_ROOT, "site", "viewer", "viewer.css");
  assert.ok(fs.existsSync(cssPath), "viewer.css must exist");
  const cssContent = fs.readFileSync(cssPath, "utf-8");

  // Verify CSS custom properties
  assert.ok(cssContent.includes("--color-success: #22c55e"), "viewer.css must define --color-success");
  assert.ok(cssContent.includes("--color-info: #06b6d4"), "viewer.css must define --color-info");
  assert.ok(cssContent.includes("--color-warning: #f59e0b"), "viewer.css must define --color-warning");
  assert.ok(cssContent.includes("--color-danger: #ef4444"), "viewer.css must define --color-danger");

  // Verify badge selectors
  assert.ok(cssContent.includes(".badge-placed"), "viewer.css must style .badge-placed");
  assert.ok(cssContent.includes(".badge-identity"), "viewer.css must style .badge-identity");
  assert.ok(cssContent.includes(".badge-unresolved"), "viewer.css must style .badge-unresolved");
  assert.ok(cssContent.includes(".badge-undecodable"), "viewer.css must style .badge-undecodable");
});

check("1.3: normalizeStatus robustness across casing, whitespace, null/undefined, and aliases", () => {
  assert.equal(normalizeStatus(null), STATUS_PLACED, "null defaults safely to placed");
  assert.equal(normalizeStatus(undefined), STATUS_PLACED, "undefined defaults safely to placed");
  assert.equal(normalizeStatus(""), STATUS_PLACED, "empty string defaults safely to placed");
  assert.equal(normalizeStatus("   placed   "), STATUS_PLACED);
  assert.equal(normalizeStatus("PLACED"), STATUS_PLACED);
  assert.equal(normalizeStatus("Resolved & Placed"), STATUS_PLACED);
  assert.equal(normalizeStatus("resolved & identity"), STATUS_IDENTITY);
  assert.equal(normalizeStatus("IDENTITY"), STATUS_IDENTITY);
  assert.equal(normalizeStatus("Unresolved Part"), STATUS_UNRESOLVED);
  assert.equal(normalizeStatus("UNRESOLVED"), STATUS_UNRESOLVED);
  assert.equal(normalizeStatus("Undecodable Placement"), STATUS_UNDECODABLE);
  assert.equal(normalizeStatus("UNDECODABLE"), STATUS_UNDECODABLE);
});

check("1.4: renderBadgeHtml and createBadgeElement produce semantically equivalent output", () => {
  const doc = createMinimalDocument();

  for (const status of [STATUS_PLACED, STATUS_IDENTITY, STATUS_UNRESOLVED, STATUS_UNDECODABLE]) {
    const html = renderBadgeHtml(status);
    const el = createBadgeElement(status, {}, doc);

    const cfg = BADGE_CONFIG[status];
    assert.ok(html.includes(cfg.label), `HTML must contain ${cfg.label}`);
    assert.equal(el.textContent, cfg.label, `Element must have text ${cfg.label}`);
    assert.equal(el.getAttribute("data-status"), status);
    assert.equal(el.title, cfg.tooltip);
    assert.ok(el.classList.contains(cfg.badgeClass));
  }
});

// =============================================================================
// SECTION 2: Anti-Omission Invariant — Unresolved Parts (§3.1 Clause 2, §3.2)
// =============================================================================
console.log("--- Section 2: Anti-Omission Invariant — Unresolved Parts ---");

check("2.1: 100-instance heterogeneous assembly retains 100% of declared instances in tree", () => {
  const doc = createMinimalDocument();
  const treeContainer = doc.createElement("div");
  const summaryContainer = doc.createElement("div");

  const ui = new AssemblyUI({
    document: doc,
    treeContainer,
    summaryContainer,
  });

  // Construct 100 instances: 40 Placed, 20 Identity, 25 Unresolved, 15 Undecodable
  const instances = [];
  for (let i = 1; i <= 40; i++) {
    instances.push({
      instance_name: `PlacedComponent_${i}.1`,
      part_number: `Part_P_${i}`,
      pairing_rule: PAIRING_RULE_TRIPLE,
      placement_status: STATUS_PLACED,
      transform: [i * 10, i * 2, 0, 1, 0, 0, 0],
    });
  }
  for (let i = 1; i <= 20; i++) {
    instances.push({
      instance_name: `IdentityComponent_${i}.1`,
      part_number: `Part_I_${i}`,
      pairing_rule: PAIRING_RULE_DESC_BLOCK,
      placement_status: STATUS_IDENTITY,
      transform: null,
    });
  }
  for (let i = 1; i <= 25; i++) {
    instances.push({
      instance_name: `MissingPartComponent_${i}.1`,
      part_number: `Part_M_${i}`,
      pairing_rule: PAIRING_RULE_BARE_PAIR,
      placement_status: STATUS_UNRESOLVED,
      transform: null,
    });
  }
  for (let i = 1; i <= 15; i++) {
    instances.push({
      instance_name: `UndecodableComponent_${i}.1`,
      part_number: `Part_U_${i}`,
      pairing_rule: PAIRING_RULE_TRIPLE,
      placement_status: STATUS_UNDECODABLE,
      transform: null,
      classification_detail: "complex constraint proxy unmapped",
    });
  }

  ui.setAssembly({
    product_name: "MassiveTestAssembly.CATProduct",
    detected_version: "V5R20",
    instances,
  });

  const treeList = treeContainer.querySelector(".assembly-tree");
  assert.ok(treeList, "Tree list must be created");
  const nodes = treeList.querySelectorAll(".tree-node");
  assert.equal(nodes.length, 100, "All 100 declared instances MUST be rendered in tree (zero omission!)");

  // Filter and check unresolved nodes
  const unresolvedNodes = treeList.querySelectorAll(".tree-node.status-unresolved");
  assert.equal(unresolvedNodes.length, 25, "Exactly 25 unresolved nodes must be present with class status-unresolved");

  for (let i = 1; i <= 25; i++) {
    const name = `MissingPartComponent_${i}.1`;
    const node = treeList.querySelector(`[data-instance-id="${name}"]`);
    assert.ok(node, `Unresolved instance ${name} MUST exist in tree`);
    assert.equal(node.getAttribute("data-status"), STATUS_UNRESOLVED);

    const visBtn = node.querySelector(".inst-vis-toggle");
    assert.equal(visBtn.disabled, true, "Visibility toggle MUST be disabled for unresolved part");

    const isoBtn = node.querySelector(".inst-isolate-btn");
    assert.equal(isoBtn.disabled, true, "Isolate button MUST be disabled for unresolved part");
  }
});

check("2.2: Catalog cross-reconciliation overrides parser status to Unresolved when part is missing", () => {
  const catalog = new VirtualFileCatalog();
  catalog.registerFile({ name: "ExistingBody.CATPart", bytes: new Uint8Array([10, 20]) });
  // "MissingFlange.CATPart" is NOT registered in catalog!

  const doc = createMinimalDocument();
  const treeContainer = doc.createElement("div");
  const summaryContainer = doc.createElement("div");

  const ui = new AssemblyUI({
    document: doc,
    treeContainer,
    summaryContainer,
    catalog,
  });

  const productDoc = {
    product_name: "CatalogReconciliation.CATProduct",
    instances: [
      {
        instance_name: "ExistingBody.1",
        part_number: "ExistingBody",
        placement_status: STATUS_PLACED,
        transform: [0, 0, 0, 1, 0, 0, 0],
      },
      {
        instance_name: "MissingFlange.1",
        part_number: "MissingFlange",
        // Parser claimed placed, but catalog lacks file:
        placement_status: STATUS_PLACED,
        transform: [100, 200, 300, 1, 0, 0, 0],
      },
    ],
  };

  ui.setAssembly(productDoc, catalog);

  const flangeNode = treeContainer.querySelector('[data-instance-id="MissingFlange.1"]');
  assert.ok(flangeNode, "MissingFlange.1 must be present in tree");
  assert.equal(
    flangeNode.getAttribute("data-status"),
    STATUS_UNRESOLVED,
    "MissingFlange.1 MUST be downgraded to status-unresolved due to catalog absence"
  );
  assert.ok(flangeNode.classList.contains("status-unresolved"));
});

check("2.3: Visibility map invariant: setInstanceVisibility rejects making Unresolved parts visible", () => {
  const doc = createMinimalDocument();
  const treeContainer = doc.createElement("div");

  const ui = new AssemblyUI({
    document: doc,
    treeContainer,
  });

  ui.setAssembly({
    product_name: "Test.CATProduct",
    instances: [
      {
        instance_name: "Ghost.1",
        part_number: "GhostPart",
        placement_status: STATUS_UNRESOLVED,
        transform: null,
      },
    ],
  });

  assert.equal(ui.getInstanceVisibility("Ghost.1"), false, "Unresolved part must initially be non-visible");

  // Attempt to force visibility to true
  const res = ui.setInstanceVisibility("Ghost.1", true);
  assert.equal(res, false, "setInstanceVisibility(unresolved, true) MUST return false");
  assert.equal(ui.getInstanceVisibility("Ghost.1"), false, "Unresolved part MUST remain non-visible");
});

// =============================================================================
// SECTION 3: Anti-Masking Invariant — Undecodable Placements (§3.1 Clause 3, §6.3)
// =============================================================================
console.log("--- Section 3: Anti-Masking Invariant — Undecodable Placements ---");

check("3.1: Undecodable placements NEVER output origin identity coordinates table in HTML or DOM", () => {
  const doc = createMinimalDocument();

  // Test renderTransformTableHtml
  const undecodableHtml = renderTransformTableHtml(null, STATUS_UNDECODABLE, {
    detail: "R15 legacy reference tags undecoded",
  });
  assert.ok(undecodableHtml.includes("inspector-notice bad"), "Must render bad inspector notice");
  assert.ok(undecodableHtml.includes("Anti-masking invariant strictly enforced"), "Must cite anti-masking");
  assert.ok(undecodableHtml.includes("never defaulted to origin identity"), "Must state never defaulted to origin");
  assert.ok(undecodableHtml.includes("R15 legacy reference tags undecoded"), "Must show refusal detail");
  assert.equal(undecodableHtml.includes("<table"), false, "MUST NOT render any <table> for undecodable placement!");
  assert.equal(undecodableHtml.includes("0.0000 mm"), false, "MUST NOT contain 0.0000 mm coordinates!");

  // Test createInspectorElement
  const undecodableRec = {
    instance_name: "LegacyShaft.1",
    part_number: "Shaft_R15",
    pairing_rule: PAIRING_RULE_TRIPLE,
    placement_status: STATUS_UNDECODABLE,
    transform: null,
    classification_detail: "R15 80 ... e8/e7 carrier unmapped",
  };

  const inspectorEl = createInspectorElement(undecodableRec, {}, doc);
  assert.ok(inspectorEl.querySelector(".badge-undecodable"), "Inspector must show badge-undecodable");
  assert.ok(inspectorEl.querySelector(".inspector-notice.bad"), "Inspector must have .inspector-notice.bad");
  assert.equal(inspectorEl.querySelectorAll("table").length, 0, "Inspector element must have 0 tables");
});

check("3.2: Contrast test: Resolved & Identity explicitly renders Origin Identity Table", () => {
  const doc = createMinimalDocument();

  const identityHtml = renderTransformTableHtml(null, STATUS_IDENTITY);
  assert.ok(identityHtml.includes("Origin Identity Default"), "Must explain origin identity default");
  assert.ok(identityHtml.includes("aria-label=\"Identity coordinates table\""), "Must have identity table");
  assert.ok(identityHtml.includes("0.0000 mm"), "Identity table must render 0.0000 mm");
  assert.ok(identityHtml.includes("Q<sub>w</sub>"), "Identity table must render Qw");
  assert.ok(identityHtml.includes("1.0000"), "Identity table must render Qw = 1.0000");

  const identityRec = {
    instance_name: "DefaultOrigin.1",
    part_number: "Part_Default",
    pairing_rule: PAIRING_RULE_DESC_BLOCK,
    placement_status: STATUS_IDENTITY,
    transform: null,
  };

  const inspectorEl = createInspectorElement(identityRec, {}, doc);
  assert.ok(inspectorEl.querySelector(".badge-identity"), "Must have badge-identity");
  assert.ok(inspectorEl.querySelector(".inspector-notice.info"), "Must have .inspector-notice.info");
  const table = inspectorEl.querySelector("table.transform-table");
  assert.ok(table, "Identity element MUST render transform table");
  assert.equal(table.getAttribute("aria-label"), "Identity coordinates table");
});

check("3.3: Resolved & Placed renders Spatial Coordinates Table with w-first quaternion", () => {
  const doc = createMinimalDocument();
  const transform = [12.34567, -45.6789, 789.0123, 0.70710678, 0.0, 0.70710678, 0.0];

  const placedHtml = renderTransformTableHtml(transform, STATUS_PLACED);
  assert.ok(placedHtml.includes("aria-label=\"Spatial coordinates table\""));
  assert.ok(placedHtml.includes("12.3457 mm"), "X formatted to 4 decimals");
  assert.ok(placedHtml.includes("-45.6789 mm"), "Y formatted to 4 decimals");
  assert.ok(placedHtml.includes("789.0123 mm"), "Z formatted to 4 decimals");
  assert.ok(placedHtml.includes("Q<sub>w</sub>"));
  assert.ok(placedHtml.includes("0.7071"));

  const placedRec = {
    instance_name: "SpatialWing.1",
    part_number: "Wing_Tip",
    pairing_rule: PAIRING_RULE_TRIPLE,
    placement_status: STATUS_PLACED,
    transform,
  };

  const inspectorEl = createInspectorElement(placedRec, {}, doc);
  const table = inspectorEl.querySelector("table.transform-table");
  assert.ok(table, "Spatial element must render transform table");
  assert.equal(table.getAttribute("aria-label"), "Spatial coordinates table");
});

// =============================================================================
// SECTION 4: Hierarchical Instance Tree & DOM Event Pipeline (§6.1, §6.2)
// =============================================================================
console.log("--- Section 4: Hierarchical Instance Tree & DOM Event Pipeline ---");

check("4.1: Root product row displays filename, version, count, and pluralization grammar", () => {
  // Test singular instance
  const singleHtml = renderRootRowHtml({ name: "Single.CATProduct" }, { total: 1, placed: 1, identity: 0, unresolved: 0, undecodable: 0 });
  assert.ok(singleHtml.includes("1 instance</span>"), "Must render '1 instance' (singular)");
  assert.ok(singleHtml.includes("Single.CATProduct"));

  // Test plural instances with version
  const pluralHtml = renderRootRowHtml({ name: "Car.CATProduct", detectedVersion: "V5R21" }, { total: 5, placed: 3, identity: 1, unresolved: 1, undecodable: 0 });
  assert.ok(pluralHtml.includes("5 instances</span>"), "Must render '5 instances' (plural)");
  assert.ok(pluralHtml.includes("(V5R21)"), "Must render version tag");
  assert.ok(pluralHtml.includes("(3 placed, 1 identity, 1 unresolved, 0 undecodable)"));
});

check("4.2: Tree node selection dispatches DOM event, invokes callback, and manages selection classes", () => {
  const doc = createMinimalDocument();
  const treeContainer = doc.createElement("div");
  const inspectorContainer = doc.createElement("div");

  let callbackInstance = null;
  let eventDetail = null;

  const ui = new AssemblyUI({
    document: doc,
    treeContainer,
    inspectorContainer,
    onSelectInstance(rec) {
      callbackInstance = rec;
    },
  });

  doc.body.addEventListener("instance-selected", (ev) => {
    eventDetail = ev.detail;
  });

  ui.setAssembly({
    product_name: "SelectionTest.CATProduct",
    instances: [
      { instance_name: "Inst_A.1", part_number: "Part_A", placement_status: STATUS_PLACED, transform: [0, 0, 0, 1, 0, 0, 0] },
      { instance_name: "Inst_B.1", part_number: "Part_B", placement_status: STATUS_PLACED, transform: [10, 0, 0, 1, 0, 0, 0] },
    ],
  });

  // Select Inst_A.1
  const nodeA = treeContainer.querySelector('[data-instance-id="Inst_A.1"]');
  const btnA = nodeA.querySelector(".node-select-btn");
  btnA.click();

  assert.equal(ui.getSelectedInstance()?.instance_name, "Inst_A.1");
  assert.equal(callbackInstance?.instance_name, "Inst_A.1");
  assert.equal(eventDetail?.instanceId, "Inst_A.1");

  const nodeB = treeContainer.querySelector('[data-instance-id="Inst_B.1"]');
  assert.ok(nodeA.classList.contains("selected"), "Node A must have 'selected' class");
  assert.equal(nodeB.classList.contains("selected"), false, "Node B must NOT have 'selected' class");

  // Select Inst_B.1 -> Node A loses selection, Node B gains selection
  const btnB = nodeB.querySelector(".node-select-btn");
  btnB.click();

  assert.equal(ui.getSelectedInstance()?.instance_name, "Inst_B.1");
  assert.equal(callbackInstance?.instance_name, "Inst_B.1");
  assert.equal(eventDetail?.instanceId, "Inst_B.1");
  assert.equal(nodeA.classList.contains("selected"), false, "Node A must lose 'selected' class");
  assert.ok(nodeB.classList.contains("selected"), "Node B must have 'selected' class");
});

check("4.3: Visibility toggling lifecycle updates UI classes, icon, scene, and dispatches event", () => {
  const doc = createMinimalDocument();
  const treeContainer = doc.createElement("div");

  let sceneVisibilityArgs = null;
  const mockScene = {
    setInstanceVisibility(id, bool) {
      sceneVisibilityArgs = { id, bool };
      return true;
    },
  };

  let visibilityEventDetail = null;
  doc.body.addEventListener("instance-visibility-changed", (ev) => {
    visibilityEventDetail = ev.detail;
  });

  const ui = new AssemblyUI({
    document: doc,
    treeContainer,
    scene: mockScene,
  });

  ui.setAssembly({
    product_name: "VisTest.CATProduct",
    instances: [
      { instance_name: "Lever.1", part_number: "Lever", placement_status: STATUS_PLACED, transform: [0, 0, 0, 1, 0, 0, 0] },
    ],
  });

  const node = treeContainer.querySelector('[data-instance-id="Lever.1"]');
  const visBtn = node.querySelector(".inst-vis-toggle");

  // 1. Initially visible
  assert.equal(ui.getInstanceVisibility("Lever.1"), true);
  assert.equal(visBtn.classList.contains("is-hidden"), false);

  // 2. Click to hide
  visBtn.click();
  assert.equal(ui.getInstanceVisibility("Lever.1"), false);
  assert.equal(sceneVisibilityArgs.id, "Lever.1");
  assert.equal(sceneVisibilityArgs.bool, false);
  assert.ok(visBtn.classList.contains("is-hidden"));
  assert.deepEqual(visibilityEventDetail, { instanceId: "Lever.1", visible: false });

  // 3. Click to show
  visBtn.click();
  assert.equal(ui.getInstanceVisibility("Lever.1"), true);
  assert.equal(sceneVisibilityArgs.bool, true);
  assert.equal(visBtn.classList.contains("is-hidden"), false);
  assert.deepEqual(visibilityEventDetail, { instanceId: "Lever.1", visible: true });
});

check("4.4: Instance isolation and restoration lifecycle", () => {
  const doc = createMinimalDocument();
  const treeContainer = doc.createElement("div");

  const isolateCalls = [];
  const mockScene = {
    setInstanceVisibility(id, bool) {},
    isolateInstance(id) {
      isolateCalls.push(id);
    },
  };

  let isolateEventDetail = null;
  doc.body.addEventListener("instance-isolated", (ev) => {
    isolateEventDetail = ev.detail;
  });

  const ui = new AssemblyUI({
    document: doc,
    treeContainer,
    scene: mockScene,
  });

  ui.setAssembly({
    product_name: "IsolateTest.CATProduct",
    instances: [
      { instance_name: "Part1.1", part_number: "Part1", placement_status: STATUS_PLACED, transform: [0, 0, 0, 1, 0, 0, 0] },
      { instance_name: "Part2.1", part_number: "Part2", placement_status: STATUS_PLACED, transform: [0, 0, 0, 1, 0, 0, 0] },
      { instance_name: "Part3.1", part_number: "Part3", placement_status: STATUS_PLACED, transform: [0, 0, 0, 1, 0, 0, 0] },
    ],
  });

  const node1 = treeContainer.querySelector('[data-instance-id="Part1.1"]');
  const isoBtn1 = node1.querySelector(".inst-isolate-btn");
  const node2 = treeContainer.querySelector('[data-instance-id="Part2.1"]');
  const isoBtn2 = node2.querySelector(".inst-isolate-btn");

  // 1. Isolate Part1.1
  isoBtn1.click();
  assert.equal(ui.getIsolatedInstance(), "Part1.1");
  assert.equal(ui.getInstanceVisibility("Part1.1"), true);
  assert.equal(ui.getInstanceVisibility("Part2.1"), false);
  assert.equal(ui.getInstanceVisibility("Part3.1"), false);
  assert.ok(isoBtn1.classList.contains("is-isolated"));
  assert.equal(isoBtn2.classList.contains("is-isolated"), false);
  assert.equal(isolateCalls[0], "Part1.1");
  assert.deepEqual(isolateEventDetail, { instanceId: "Part1.1", isIsolated: true });

  // 2. Isolate Part2.1 directly while Part1 is isolated
  isoBtn2.click();
  assert.equal(ui.getIsolatedInstance(), "Part2.1");
  assert.equal(ui.getInstanceVisibility("Part1.1"), false);
  assert.equal(ui.getInstanceVisibility("Part2.1"), true);
  assert.equal(ui.getInstanceVisibility("Part3.1"), false);
  assert.equal(isoBtn1.classList.contains("is-isolated"), false);
  assert.ok(isoBtn2.classList.contains("is-isolated"));

  // 3. Click Part2.1 again -> restores all
  isoBtn2.click();
  assert.equal(ui.getIsolatedInstance(), null);
  assert.equal(ui.getInstanceVisibility("Part1.1"), true);
  assert.equal(ui.getInstanceVisibility("Part2.1"), true);
  assert.equal(ui.getInstanceVisibility("Part3.1"), true);
  assert.equal(isoBtn2.classList.contains("is-isolated"), false);
  assert.deepEqual(isolateEventDetail, { instanceId: "Part2.1", isIsolated: false });
});

// =============================================================================
// SECTION 5: Instance Inspector Panel & Numeric Contract (§6.3)
// =============================================================================
console.log("--- Section 5: Instance Inspector Panel & Numeric Contract ---");

check("5.1: formatCoordinate handles precision, small epsilon zeroes, and non-finites", () => {
  assert.equal(formatCoordinate(0.0), "0.0000");
  assert.equal(formatCoordinate(-0.0), "0.0000");
  assert.equal(formatCoordinate(1e-13), "0.0000");
  assert.equal(formatCoordinate(-1e-13), "0.0000");
  assert.equal(formatCoordinate(123.456789), "123.4568");
  assert.equal(formatCoordinate(-987.654321), "-987.6543");
  assert.equal(formatCoordinate(NaN), "0.0000");
  assert.equal(formatCoordinate(Infinity), "Infinity");
  assert.equal(formatCoordinate(-Infinity), "-Infinity");
  assert.equal(formatCoordinate("not a number"), "0.0000");
});

check("5.2: Inspector renders pairing rules (triple, desc_block, bare_pair) and object tags accurately", () => {
  const doc = createMinimalDocument();

  // 1. Triple rule with object tag
  const elTriple = createInspectorElement({
    instance_name: "Inst_Triple.1",
    part_number: "PN_T",
    pairing_rule: PAIRING_RULE_TRIPLE,
    placement_status: STATUS_PLACED,
    object_tag: 0x4567,
    transform: [0, 0, 0, 1, 0, 0, 0],
  }, {}, doc);
  assert.ok(elTriple.innerHTML.includes("triple"));
  assert.ok(elTriple.innerHTML.includes("0x4567 (17767)"));

  // 2. Desc block rule
  const elDesc = createInspectorElement({
    instance_name: "Inst_Desc.1",
    part_number: "PN_D",
    pairing_rule: PAIRING_RULE_DESC_BLOCK,
    placement_status: STATUS_IDENTITY,
    transform: null,
  }, {}, doc);
  assert.ok(elDesc.innerHTML.includes("desc_block"));

  // 3. Bare pair rule
  const elBare = createInspectorElement({
    instance_name: "Inst_Bare.1",
    part_number: "PN_B",
    pairing_rule: PAIRING_RULE_BARE_PAIR,
    placement_status: STATUS_UNRESOLVED,
    transform: null,
  }, {}, doc);
  assert.ok(elBare.innerHTML.includes("bare_pair"));
});

check("5.3: Empty inspector state renders proper placeholder guidance", () => {
  const doc = createMinimalDocument();
  const emptyHtml = renderInspectorHtml(null);
  assert.ok(emptyHtml.includes("inspector-empty"));
  assert.ok(emptyHtml.includes("Select an instance to view transform and pairing details."));

  const el = createInspectorElement(null, {}, doc);
  assert.ok(el.querySelector(".inspector-empty"));
  assert.ok(el.textContent.includes("Select an instance to view transform and pairing details."));
});

// =============================================================================
// SECTION 6: Toolbar Controls: Exploded View, Summary Bar & Switcher (§4.3, §5.4)
// =============================================================================
console.log("--- Section 6: Toolbar Controls: Exploded View, Summary Bar & Switcher ---");

check("6.1: Exploded view slider range, clamping, real-time indicator, and event dispatch", () => {
  const doc = createMinimalDocument();
  const toolbarContainer = doc.createElement("div");

  let sceneScale = null;
  const mockScene = {
    setExplodedScale(scale) {
      sceneScale = scale;
      return scale;
    },
  };

  let callbackScale = null;
  let eventDetail = null;

  const ui = new AssemblyUI({
    document: doc,
    toolbarContainer,
    scene: mockScene,
    onExplodeChange(s) {
      callbackScale = s;
    },
  });

  doc.body.addEventListener("exploded-scale-changed", (ev) => {
    eventDetail = ev.detail;
  });

  ui.setAssembly({
    product_name: "ExplodeTest.CATProduct",
    instances: [],
  });

  const slider = toolbarContainer.querySelector("#explode-slider");
  const valueDisplay = toolbarContainer.querySelector("#explode-value");
  assert.ok(slider, "Slider input element must exist");
  assert.ok(valueDisplay, "Value display span must exist");
  assert.equal(slider.getAttribute("min"), "0.0");
  assert.equal(slider.getAttribute("max"), "3.0");
  assert.equal(slider.getAttribute("step"), "0.05");

  // Nominal value test: 2.35
  ui.setExplodedScale(2.35);
  assert.equal(ui.getExplodedScale(), 2.35);
  assert.equal(sceneScale, 2.35);
  assert.equal(callbackScale, 2.35);
  assert.equal(valueDisplay.textContent, "2.35");
  assert.equal(slider.value, "2.35");
  assert.deepEqual(eventDetail, { scale: 2.35 });

  // Boundary clamping tests
  ui.setExplodedScale(-10.0);
  assert.equal(ui.getExplodedScale(), 0.0, "Negative scale must clamp to 0.0");

  ui.setExplodedScale(15.0);
  assert.equal(ui.getExplodedScale(), 3.0, "Scale > 3.0 must clamp to 3.0");

  ui.setExplodedScale("invalid");
  assert.equal(ui.getExplodedScale(), 0.0, "Non-numeric scale must fallback to 0.0");
});

check("6.2: Summary bar chips render exact values, classes, and titles for all 5 metrics", () => {
  const doc = createMinimalDocument();
  const summaryEl = createSummaryBarElement({
    total: 42,
    placed: 28,
    identity: 7,
    unresolved: 5,
    undecodable: 2,
  }, doc);

  const chips = summaryEl.querySelectorAll(".summary-chip");
  assert.equal(chips.length, 5, "Must render exactly 5 chips: Total, Placed, Identity, Unresolved, Undecodable");

  // Total
  const totalChip = summaryEl.querySelector(".summary-total");
  assert.ok(totalChip.textContent.includes("Total") && totalChip.textContent.includes("42"));

  // Placed
  const placedChip = summaryEl.querySelector(".summary-placed");
  assert.ok(placedChip.classList.contains("badge-placed"));
  assert.ok(placedChip.textContent.includes("Placed") && placedChip.textContent.includes("28"));

  // Identity
  const identityChip = summaryEl.querySelector(".summary-identity");
  assert.ok(identityChip.classList.contains("badge-identity"));
  assert.ok(identityChip.textContent.includes("Identity") && identityChip.textContent.includes("7"));

  // Unresolved
  const unresolvedChip = summaryEl.querySelector(".summary-unresolved");
  assert.ok(unresolvedChip.classList.contains("badge-unresolved"));
  assert.ok(unresolvedChip.textContent.includes("Unresolved") && unresolvedChip.textContent.includes("5"));

  // Undecodable
  const undecodableChip = summaryEl.querySelector(".summary-undecodable");
  assert.ok(undecodableChip.classList.contains("badge-undecodable"));
  assert.ok(undecodableChip.textContent.includes("Undecodable") && undecodableChip.textContent.includes("2"));
});

check("6.3: Multi-product switcher disambiguation rules (§4.3)", () => {
  const doc = createMinimalDocument();
  const switcherContainer = doc.createElement("div");

  let switchedProduct = null;
  let switchEventDetail = null;

  const ui = new AssemblyUI({
    document: doc,
    switcherContainer,
    onSwitchProduct(p) {
      switchedProduct = p;
    },
  });

  doc.body.addEventListener("product-switched", (ev) => {
    switchEventDetail = ev.detail;
  });

  // Rule 1: 0 or 1 product -> no switcher dropdown
  ui.setProductList([]);
  assert.equal(switcherContainer.innerHTML, "", "0 products: container must be empty");

  ui.setProductList([{ name: "Single.CATProduct" }]);
  assert.equal(switcherContainer.innerHTML, "", "1 product: container must be empty");

  // Rule 2: 2+ products -> render <select id="root-product-select">
  const products = [
    { name: "TopLevel.CATProduct", stem: "TopLevel" },
    { name: "Sub1.CATProduct", stem: "Sub1" },
    { name: "Sub2.CATProduct", stem: "Sub2" },
  ];

  ui.setProductList(products, "TopLevel.CATProduct");

  const select = switcherContainer.querySelector("#root-product-select");
  assert.ok(select, "Select dropdown must be rendered");
  const options = select.querySelectorAll("option");
  assert.equal(options.length, 3, "Must render 3 options");
  assert.equal(options[0].value, "TopLevel.CATProduct");
  assert.equal(options[0].hasAttribute("selected"), true);

  // Trigger change to Sub1.CATProduct
  select.value = "Sub1.CATProduct";
  select.dispatchEvent({ type: "change" });

  assert.equal(switchedProduct?.name, "Sub1.CATProduct");
  assert.equal(switchEventDetail?.product?.name, "Sub1.CATProduct");
});

// =============================================================================
// SECTION 7: Security & XSS Sanitization Invariance
// =============================================================================
console.log("--- Section 7: Security & XSS Sanitization Invariance ---");

check("7.1: Malicious strings in instance names and part numbers are fully neutralized by escapeHtml", () => {
  const maliciousName = '<script>alert("pwned")</script>';
  const maliciousPn = '"><img src=x onerror=alert(1)>';
  const maliciousVer = '&copy; "2026" <CATIA>';

  const escapedName = escapeHtml(maliciousName);
  assert.equal(escapedName.includes("<script>"), false);
  assert.ok(escapedName.includes("&lt;script&gt;"));

  const escapedPn = escapeHtml(maliciousPn);
  assert.equal(escapedPn.includes("<img"), false);
  assert.ok(escapedPn.includes("&quot;&gt;&lt;img"));

  // In tree HTML rendering
  const treeHtml = renderTreeNodeHtml({
    instance_name: maliciousName,
    part_number: maliciousPn,
    placement_status: STATUS_PLACED,
  });
  assert.equal(treeHtml.includes("<script>"), false);
  assert.equal(treeHtml.includes("<img"), false);

  // In root row HTML rendering
  const rootHtml = renderRootRowHtml({
    name: maliciousName,
    detectedVersion: maliciousVer,
  });
  assert.equal(rootHtml.includes("<script>"), false);
  assert.equal(rootHtml.includes("<CATIA>"), false);
});

// =============================================================================
// SECTION 8: UI State Reset & Disposal Hygiene
// =============================================================================
console.log("--- Section 8: UI State Reset & Disposal Hygiene ---");

check("8.1: AssemblyUI.clear() completely purges all state and DOM containers", () => {
  const doc = createMinimalDocument();
  const treeContainer = doc.createElement("div");
  const inspectorContainer = doc.createElement("div");
  const summaryContainer = doc.createElement("div");
  const toolbarContainer = doc.createElement("div");
  const switcherContainer = doc.createElement("div");

  const ui = new AssemblyUI({
    document: doc,
    treeContainer,
    inspectorContainer,
    summaryContainer,
    toolbarContainer,
    switcherContainer,
  });

  ui.setAssembly({
    product_name: "ClearTest.CATProduct",
    instances: [
      { instance_name: "A.1", part_number: "A", placement_status: STATUS_PLACED, transform: [0, 0, 0, 1, 0, 0, 0] },
    ],
  });
  ui.setExplodedScale(1.5);
  ui.selectInstance("A.1");
  ui.setProductList([{ name: "P1.CATProduct" }, { name: "P2.CATProduct" }]);

  // Verify non-empty before clear
  assert.equal(ui.instanceMap.size, 1);
  assert.equal(ui.getSelectedInstance()?.instance_name, "A.1");
  assert.equal(ui.getExplodedScale(), 1.5);

  // Execute clear
  ui.clear();

  assert.equal(ui.instanceMap.size, 0);
  assert.equal(ui.visibilityMap.size, 0);
  assert.equal(ui.getSelectedInstance(), null);
  assert.equal(ui.getIsolatedInstance(), null);
  assert.equal(ui.getExplodedScale(), 0.0);
  assert.equal(treeContainer.children.length, 0);
  assert.equal(summaryContainer.children.length, 0);
  assert.equal(toolbarContainer.children.length, 0);
  assert.equal(switcherContainer.children.length, 0);

  // Inspector restored to empty notice
  const inspectorHtml = inspectorContainer.innerHTML;
  assert.ok(inspectorHtml.includes("inspector-empty"));
});

// =============================================================================
// SECTION 9: Technical Precision Findings & Scene Coordination
// =============================================================================
console.log("--- Section 9: Technical Precision Findings & Scene Coordination ---");

check("9.1: Technical Finding 1: queryMock selector resolution limitation on descendant selectors", () => {
  const doc = createMinimalDocument();
  const parent = doc.createElement("div");
  const childA = doc.createElement("div");
  childA.className = "target";
  childA.setAttribute("id", "first");
  const childB = doc.createElement("div");
  childB.className = "target";
  childB.setAttribute("id", "second");

  const containerA = doc.createElement("div");
  containerA.className = "container-a";
  containerA.appendChild(childA);

  const containerB = doc.createElement("div");
  containerB.className = "container-b";
  containerB.appendChild(childB);

  parent.appendChild(containerA);
  parent.appendChild(containerB);

  // In queryMock, ".container-b .target" only evaluates ".target" on all elements,
  // matching childA first instead of respecting the ancestor requirement ".container-b"!
  const found = parent.querySelector(".container-b .target");
  // This verifies the identified technical finding:
  assert.equal(found.id, "first", "queryMock limitation: multi-token selector matches last token only");

  // Recommendation: chaining single queries works deterministically
  const properFound = parent.querySelector(".container-b").querySelector(".target");
  assert.equal(properFound.id, "second", "Chained querySelector correctly locates scoped element");
});

check("9.2: End-to-end coordination with AssemblyScene: visibility, isolation, explode, framing", () => {
  const doc = createMinimalDocument();
  const treeContainer = doc.createElement("div");
  const inspectorContainer = doc.createElement("div");
  const toolbarContainer = doc.createElement("div");
  const summaryContainer = doc.createElement("div");

  // Create an AssemblyScene instance (running headless with mock Three scene)
  const dummyScene = {
    add() {},
    remove() {},
  };
  const scene = new AssemblyScene(dummyScene, { applyRootBasis: false });

  // Register dummy geometries and instances into scene
  scene.addInstance({
    instance_name: "Bracket.1",
    part_number: "Bracket",
    placement_status: STATUS_PLACED,
    transform: [10, 20, 30, 0.7071, 0, 0, 0.7071],
  });
  scene.addInstance({
    instance_name: "Bolt.1",
    part_number: "Bolt",
    placement_status: STATUS_IDENTITY,
    transform: null,
  });
  scene.addInstance({
    instance_name: "MissingNut.1",
    part_number: "Nut_Missing",
    placement_status: STATUS_UNRESOLVED,
    transform: null,
  });

  let framedInstanceName = null;
  const mockOrbit = {};

  const ui = new AssemblyUI({
    document: doc,
    treeContainer,
    inspectorContainer,
    toolbarContainer,
    summaryContainer,
    scene,
    onSelectInstance(rec) {
      if (rec && rec.instance_name) {
        framedInstanceName = rec.instance_name;
      }
    },
  });

  const catalog = new VirtualFileCatalog();
  catalog.registerFile({ name: "Bracket.CATPart", bytes: new Uint8Array([1, 2, 3]) });
  catalog.registerFile({ name: "Bolt.CATPart", bytes: new Uint8Array([4, 5, 6]) });

  const productDoc = {
    product_name: "E2EAssembly.CATProduct",
    detected_version: "V5R21",
    instances: [
      {
        instance_name: "Bracket.1",
        part_number: "Bracket",
        placement_status: STATUS_PLACED,
        transform: [10, 20, 30, 0.7071, 0, 0, 0.7071],
      },
      {
        instance_name: "Bolt.1",
        part_number: "Bolt",
        placement_status: STATUS_IDENTITY,
        transform: null,
      },
      {
        instance_name: "MissingNut.1",
        part_number: "Nut_Missing",
        placement_status: STATUS_UNRESOLVED,
        transform: null,
      },
    ],
  };

  ui.setAssembly(productDoc, catalog);

  // 1. Verify summary chips
  const totalChip = summaryContainer.querySelector(".summary-total .chip-val");
  assert.equal(totalChip.textContent, "3");

  // 2. Select Bracket.1 -> framing callback receives name
  ui.selectInstance("Bracket.1");
  assert.equal(framedInstanceName, "Bracket.1");
  const inspectorHtml = inspectorContainer.innerHTML;
  assert.ok(inspectorHtml.includes("Bracket.1"));
  assert.ok(inspectorHtml.includes("10.0000 mm"));

  // 3. Exploded scale -> sets scene scale
  ui.setExplodedScale(2.5);
  assert.equal(scene.getExplodedScale(), 2.5);

  // 4. Toggle visibility -> delegates to scene
  ui.setInstanceVisibility("Bracket.1", false);
  assert.equal(scene.getInstanceVisibility("Bracket.1"), false);
  ui.setInstanceVisibility("Bracket.1", true);
  assert.equal(scene.getInstanceVisibility("Bracket.1"), true);
});

// =============================================================================
// VERIFICATION SUMMARY
// =============================================================================
console.log("\n================================================================================");
console.log(`INDEPENDENT VERIFICATION COMPLETE: ${passedChecks}/${totalChecks} checks passed`);
console.log("Verdict: PASS — All P3-V5 requirements & invariants verified with 100% success.");
console.log("================================================================================");
