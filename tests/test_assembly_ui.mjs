/* Test Suite for Interactive Assembly UI & Classification Tree (Ticket P3-V5)
   Design Authority: docs/specs/phase6-assembly-viewer-spec.md §4.1, §4.3, §6, §7, §8
   Pure ES module, zero npm dependencies. Run via: node tests/test_assembly_ui.mjs
*/

import assert from "node:assert/strict";
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
  renderBadgeHtml,
  renderTransformTableHtml,
  renderSummaryBarHtml,
  renderRootRowHtml,
  renderTreeNodeHtml,
  renderInspectorHtml,
  formatCoordinate,
  normalizeStatus,
  createMinimalDocument,
} from "../site/viewer/assembly_ui.js";

import { VirtualFileCatalog } from "../site/viewer/catalog.js";
import { AssemblyScene } from "../site/viewer/assembly_scene.js";

const tests = [];
function test(name, fn) {
  tests.push({ name, fn });
}

console.log("Running Assembly UI & Classification Tree test suite (Ticket P3-V5)...\n");

/* -------------------------------------------------------------------------- */
/* Test 1: The 4 Canonical Classification Badges (§4.1, §3.2)                 */
/* -------------------------------------------------------------------------- */
test("The 4 Canonical Classification Badges render with exact classes, labels, and colors", () => {
  // 1. Placed (Green #22c55e / var(--color-success))
  const placedHtml = renderBadgeHtml(STATUS_PLACED);
  assert.ok(placedHtml.includes("badge-placed"), "Placed badge must have class badge-placed");
  assert.ok(placedHtml.includes("pill good"), "Placed badge must have class pill good");
  assert.ok(placedHtml.includes("Placed"), "Placed badge must display label 'Placed'");
  assert.ok(placedHtml.includes("spatial 3D transform"), "Placed tooltip must explain spatial 3D transform");
  assert.equal(BADGE_CONFIG[STATUS_PLACED].colorHex, "#22c55e");
  assert.equal(BADGE_CONFIG[STATUS_PLACED].cssVar, "var(--color-success)");

  // 2. Identity (Cyan/Blue #06b6d4 / var(--color-info))
  const identityHtml = renderBadgeHtml(STATUS_IDENTITY);
  assert.ok(identityHtml.includes("badge-identity"), "Identity badge must have class badge-identity");
  assert.ok(identityHtml.includes("pill neutral"), "Identity badge must have class pill neutral");
  assert.ok(identityHtml.includes("Identity"), "Identity badge must display label 'Identity'");
  assert.ok(identityHtml.includes("origin"), "Identity tooltip must mention origin");
  assert.equal(BADGE_CONFIG[STATUS_IDENTITY].colorHex, "#06b6d4");
  assert.equal(BADGE_CONFIG[STATUS_IDENTITY].cssVar, "var(--color-info)");

  // 3. Unresolved Part (Amber/Yellow #f59e0b / var(--color-warning))
  const unresolvedHtml = renderBadgeHtml(STATUS_UNRESOLVED);
  assert.ok(unresolvedHtml.includes("badge-unresolved"), "Unresolved badge must have class badge-unresolved");
  assert.ok(unresolvedHtml.includes("pill warn"), "Unresolved badge must have class pill warn");
  assert.ok(unresolvedHtml.includes("Unresolved Part"), "Unresolved badge must display label 'Unresolved Part'");
  assert.ok(unresolvedHtml.includes("missing"), "Unresolved tooltip must mention missing");
  assert.equal(BADGE_CONFIG[STATUS_UNRESOLVED].colorHex, "#f59e0b");
  assert.equal(BADGE_CONFIG[STATUS_UNRESOLVED].cssVar, "var(--color-warning)");

  // 4. Undecodable Placement (Red/Rose #ef4444 / var(--color-danger))
  const undecodableHtml = renderBadgeHtml(STATUS_UNDECODABLE);
  assert.ok(undecodableHtml.includes("badge-undecodable"), "Undecodable badge must have class badge-undecodable");
  assert.ok(undecodableHtml.includes("pill bad"), "Undecodable badge must have class pill bad");
  assert.ok(undecodableHtml.includes("Undecodable Placement"), "Undecodable badge must display label 'Undecodable Placement'");
  assert.ok(undecodableHtml.includes("anti-masking"), "Undecodable tooltip must mention anti-masking");
  assert.equal(BADGE_CONFIG[STATUS_UNDECODABLE].colorHex, "#ef4444");
  assert.equal(BADGE_CONFIG[STATUS_UNDECODABLE].cssVar, "var(--color-danger)");

  // Normalization and case insensitivity
  assert.equal(normalizeStatus("Resolved & Placed"), STATUS_PLACED);
  assert.equal(normalizeStatus("Resolved & Identity"), STATUS_IDENTITY);
  assert.equal(normalizeStatus("Unresolved Part"), STATUS_UNRESOLVED);
  assert.equal(normalizeStatus("Undecodable Placement"), STATUS_UNDECODABLE);
  assert.equal(normalizeStatus("placed"), STATUS_PLACED);
});

/* -------------------------------------------------------------------------- */
/* Test 2: Anti-Omission Invariant — Unresolved parts are never omitted       */
/* -------------------------------------------------------------------------- */
test("Anti-Omission Invariant: Unresolved parts are NEVER omitted from instance tree", () => {
  const doc = createMinimalDocument();
  const treeContainer = doc.createElement("div");
  const summaryContainer = doc.createElement("div");

  const ui = new AssemblyUI({
    document: doc,
    treeContainer,
    summaryContainer,
  });

  // Synthetic document with all 4 states
  const productDoc = {
    schema_version: 1,
    product_name: "AntiOmission_Prod1.CATProduct",
    detected_version: "V5R21",
    total_instances: 4,
    instances: [
      {
        instance_name: "Arm_Placed.1",
        part_number: "Arm",
        pairing_rule: PAIRING_RULE_TRIPLE,
        placement_status: STATUS_PLACED,
        transform: [10.0, 20.0, 30.0, 0.7071, 0.0, 0.7071, 0.0],
      },
      {
        instance_name: "Base_Identity.1",
        part_number: "Base",
        pairing_rule: PAIRING_RULE_DESC_BLOCK,
        placement_status: STATUS_IDENTITY,
        transform: null,
      },
      {
        instance_name: "MissingPin_Unresolved.1",
        part_number: "Pin_Missing",
        pairing_rule: PAIRING_RULE_BARE_PAIR,
        placement_status: STATUS_UNRESOLVED,
        transform: null,
      },
      {
        instance_name: "LegacyR15_Undecodable.1",
        part_number: "Pin_Legacy",
        pairing_rule: PAIRING_RULE_TRIPLE,
        placement_status: STATUS_UNDECODABLE,
        transform: null,
        classification_detail: "R15 legacy reference tags undecoded",
      },
    ],
  };

  ui.setAssembly(productDoc);

  // Assert tree has root container and <ul> list
  const rootRow = treeContainer.querySelector(".tree-root-row");
  assert.ok(rootRow, "Tree must include root product row");
  assert.ok(rootRow.getAttribute("data-root-name").includes("AntiOmission_Prod1.CATProduct"));

  const treeList = treeContainer.querySelector(".assembly-tree");
  assert.ok(treeList, "Tree must include .assembly-tree <ul> element");

  const nodes = treeList.querySelectorAll(".tree-node");
  assert.equal(nodes.length, 4, "Instance tree MUST render all 4 declared instances exactly");

  // Specific Anti-Omission check for the unresolved instance:
  const unresolvedNode = treeList.querySelector('[data-instance-id="MissingPin_Unresolved.1"]');
  assert.ok(unresolvedNode, "Unresolved instance MissingPin_Unresolved.1 MUST BE VISIBLE IN TREE (never omitted!)");
  assert.ok(unresolvedNode.classList.contains("status-unresolved"), "Unresolved node must have class status-unresolved");
  assert.ok(unresolvedNode.innerHTML.includes("badge-unresolved"), "Unresolved node must have badge-unresolved element");
  assert.ok(unresolvedNode.innerHTML.includes("Unresolved Part"), "Unresolved node must render label 'Unresolved Part'");

  // Unresolved instance visibility and isolate buttons must be disabled
  const visBtn = unresolvedNode.querySelector(".inst-vis-toggle");
  assert.ok(visBtn, "Visibility toggle button must exist");
  assert.equal(visBtn.disabled, true, "Unresolved instance visibility toggle MUST be disabled");

  const isoBtn = unresolvedNode.querySelector(".inst-isolate-btn");
  assert.ok(isoBtn, "Isolate button must exist");
  assert.equal(isoBtn.disabled, true, "Unresolved instance isolate button MUST be disabled");
});

/* -------------------------------------------------------------------------- */
/* Test 3: Anti-Masking Invariant — Undecodable placements never identity     */
/* -------------------------------------------------------------------------- */
test("Anti-Masking Invariant: Undecodable placements NEVER fall back to origin identity", () => {
  const doc = createMinimalDocument();
  const treeContainer = doc.createElement("div");
  const inspectorContainer = doc.createElement("div");

  const ui = new AssemblyUI({
    document: doc,
    treeContainer,
    inspectorContainer,
  });

  const undecodableRec = {
    instance_name: "Undecodable_Motor.1",
    part_number: "Motor_90W",
    pairing_rule: PAIRING_RULE_TRIPLE,
    placement_status: STATUS_UNDECODABLE,
    transform: null,
    classification_detail: "constraint mesh override: 12 records for 16 instances",
  };

  ui.setAssembly({
    product_name: "TestProduct.CATProduct",
    instances: [undecodableRec],
  });

  // Select the undecodable instance
  ui.selectInstance("Undecodable_Motor.1");

  // Verify inspector content
  const inspectorContent = inspectorContainer.querySelector(".inspector-content");
  assert.ok(inspectorContent, "Inspector content must be rendered");
  assert.equal(inspectorContent.getAttribute("data-instance-id"), "Undecodable_Motor.1");

  const inspectorHtml = inspectorContainer.innerHTML;

  // Anti-masking assertions:
  assert.ok(inspectorHtml.includes("badge-undecodable"), "Inspector must show badge-undecodable");
  assert.ok(inspectorHtml.includes("Undecodable Placement"), "Inspector must display 'Undecodable Placement'");
  assert.ok(inspectorHtml.includes("never defaulted to origin identity"), "Inspector must explicitly state anti-masking notice");
  assert.ok(inspectorHtml.includes("constraint mesh override"), "Inspector must display classification detail");

  // Invariant verification: MUST NOT render false identity transform
  assert.equal(
    inspectorHtml.includes('aria-label="Identity coordinates table"'),
    false,
    "Undecodable placement MUST NOT render identity coordinates table (Clause 3 violation!)"
  );
});

/* -------------------------------------------------------------------------- */
/* Test 4: Instance Selection & Event Dispatch with Transform Details        */
/* -------------------------------------------------------------------------- */
test("Instance click dispatches selection event and updates Inspector with transform details", () => {
  const doc = createMinimalDocument();
  const treeContainer = doc.createElement("div");
  const inspectorContainer = doc.createElement("div");

  let selectedEventFired = false;
  let selectedDetail = null;
  let callbackFired = false;
  let callbackRecord = null;

  const ui = new AssemblyUI({
    document: doc,
    treeContainer,
    inspectorContainer,
    onSelectInstance(record) {
      callbackFired = true;
      callbackRecord = record;
    },
  });

  doc.body.addEventListener("instance-selected", (ev) => {
    selectedEventFired = true;
    selectedDetail = ev.detail;
  });

  const placedRecord = {
    instance_name: "Bracket_Left.1",
    part_number: "Bracket_2026",
    pairing_rule: PAIRING_RULE_TRIPLE,
    placement_status: STATUS_PLACED,
    transform: [-15.5, 32.25, 120.0, 0.70710678, 0.0, 0.0, 0.70710678],
    object_tag: 0x1234,
  };

  ui.setAssembly({
    product_name: "Carrier.CATProduct",
    instances: [placedRecord],
  });

  // Click on the node select button
  const selectBtn = treeContainer.querySelector(".node-select-btn");
  assert.ok(selectBtn, "Node select button must exist");
  selectBtn.click();

  // 1. Verify callback and event
  assert.ok(callbackFired, "onSelectInstance callback must fire on click");
  assert.equal(callbackRecord.instance_name, "Bracket_Left.1");
  assert.ok(selectedEventFired, "instance-selected DOM event must be dispatched");
  assert.equal(selectedDetail.instanceId, "Bracket_Left.1");
  assert.deepEqual(selectedDetail.transform, [-15.5, 32.25, 120.0, 0.70710678, 0.0, 0.0, 0.70710678]);

  // 2. Verify visual selection highlight
  const selectedNode = treeContainer.querySelector('.tree-node[data-instance-id="Bracket_Left.1"]');
  assert.ok(selectedNode.classList.contains("selected"), "Selected tree node must have class 'selected'");

  // 3. Verify Inspector panel transform table
  const inspectorHtml = inspectorContainer.innerHTML;
  assert.ok(inspectorHtml.includes("Bracket_Left.1"), "Inspector must show instance name");
  assert.ok(inspectorHtml.includes("Bracket_2026"), "Inspector must show part number");
  assert.ok(inspectorHtml.includes("triple"), "Inspector must show pairing rule");
  assert.ok(inspectorHtml.includes("0x1234"), "Inspector must show object tag in hex");

  // Translation table verification [X, Y, Z] in mm
  assert.ok(inspectorHtml.includes("-15.5000 mm"), "Transform table must show X translation in mm");
  assert.ok(inspectorHtml.includes("32.2500 mm"), "Transform table must show Y translation in mm");
  assert.ok(inspectorHtml.includes("120.0000 mm"), "Transform table must show Z translation in mm");

  // Quaternion table verification [Qw, Qx, Qy, Qz] w-first
  assert.ok(inspectorHtml.includes("Q<sub>w</sub>"), "Transform table must label scalar Qw");
  assert.ok(inspectorHtml.includes("0.7071"), "Transform table must show Qw value");
});

/* -------------------------------------------------------------------------- */
/* Test 5: Visibility Toggle & Scene Callback                                 */
/* -------------------------------------------------------------------------- */
test("Visibility toggle triggers callback, updates UI state, and calls scene.setInstanceVisibility", () => {
  const doc = createMinimalDocument();
  const treeContainer = doc.createElement("div");

  // Mock scene tracking visibility
  const visibilityCalls = [];
  const mockScene = {
    setInstanceVisibility(id, bool) {
      visibilityCalls.push({ id, bool });
      return true;
    },
  };

  let callbackInstanceId = null;
  let callbackVisible = null;

  const ui = new AssemblyUI({
    document: doc,
    treeContainer,
    scene: mockScene,
    onToggleVisibility(id, visible) {
      callbackInstanceId = id;
      callbackVisible = visible;
    },
  });

  const instanceRecord = {
    instance_name: "Bolt_M6.1",
    part_number: "Bolt_M6",
    placement_status: STATUS_PLACED,
    transform: [0, 0, 0, 1, 0, 0, 0],
  };

  ui.setAssembly({
    product_name: "Fasteners.CATProduct",
    instances: [instanceRecord],
  });

  const visBtn = treeContainer.querySelector(".inst-vis-toggle");
  assert.ok(visBtn, "Visibility toggle button must exist");
  assert.equal(ui.getInstanceVisibility("Bolt_M6.1"), true, "Initial visibility should be true");

  // Click 1: Toggle from visible (true) -> hidden (false)
  visBtn.click();

  assert.equal(callbackInstanceId, "Bolt_M6.1");
  assert.equal(callbackVisible, false, "Callback must receive visible=false");
  assert.equal(ui.getInstanceVisibility("Bolt_M6.1"), false);
  assert.deepEqual(visibilityCalls[0], { id: "Bolt_M6.1", bool: false }, "Scene must receive setInstanceVisibility(id, false)");
  assert.ok(visBtn.classList.contains("is-hidden"), "Button should have is-hidden class when hidden");

  // Click 2: Toggle from hidden (false) -> visible (true)
  visBtn.click();

  assert.equal(callbackVisible, true, "Callback must receive visible=true");
  assert.equal(ui.getInstanceVisibility("Bolt_M6.1"), true);
  assert.deepEqual(visibilityCalls[1], { id: "Bolt_M6.1", bool: true }, "Scene must receive setInstanceVisibility(id, true)");
  assert.equal(visBtn.classList.contains("is-hidden"), false, "Button should remove is-hidden class when visible");
});

/* -------------------------------------------------------------------------- */
/* Test 6: Camera Focus / Isolate Instance                                    */
/* -------------------------------------------------------------------------- */
test("Camera isolate button calls scene.isolateInstance and updates UI button state", () => {
  const doc = createMinimalDocument();
  const treeContainer = doc.createElement("div");

  const isolateCalls = [];
  const mockScene = {
    setInstanceVisibility(id, bool) {},
    isolateInstance(id) {
      isolateCalls.push(id);
      return id;
    },
  };

  let isolatedCallbackId = null;
  let isolatedCallbackState = null;

  const ui = new AssemblyUI({
    document: doc,
    treeContainer,
    scene: mockScene,
    onIsolateInstance(id, isIso) {
      isolatedCallbackId = id;
      isolatedCallbackState = isIso;
    },
  });

  ui.setAssembly({
    product_name: "Housing.CATProduct",
    instances: [
      { instance_name: "Shell_Top.1", part_number: "Shell_Top", placement_status: STATUS_PLACED, transform: [0, 0, 0, 1, 0, 0, 0] },
      { instance_name: "Shell_Bottom.1", part_number: "Shell_Bottom", placement_status: STATUS_PLACED, transform: [0, 0, 0, 1, 0, 0, 0] },
    ],
  });

  const node = treeContainer.querySelector('[data-instance-id="Shell_Top.1"]');
  const isoBtn = node.querySelector(".inst-isolate-btn");
  assert.ok(isoBtn, "Isolate button must exist");

  // 1. Isolate Shell_Top.1
  isoBtn.click();

  assert.equal(ui.getIsolatedInstance(), "Shell_Top.1");
  assert.equal(isolatedCallbackId, "Shell_Top.1");
  assert.equal(isolatedCallbackState, true);
  assert.equal(isolateCalls[0], "Shell_Top.1");
  assert.ok(isoBtn.classList.contains("is-isolated"), "Button must have is-isolated class");

  // 2. Click again: Restore all
  isoBtn.click();

  assert.equal(ui.getIsolatedInstance(), null);
  assert.equal(isolatedCallbackState, false);
  assert.equal(isolateCalls[1], null);
  assert.equal(isoBtn.classList.contains("is-isolated"), false, "Button must remove is-isolated class");
});

/* -------------------------------------------------------------------------- */
/* Test 7: Toolbar Exploded View Slider (lambda in [0.0, 3.0])                */
/* -------------------------------------------------------------------------- */
test("Exploded View slider updates real-time display and calls scene.setExplodedScale", () => {
  const doc = createMinimalDocument();
  const toolbarContainer = doc.createElement("div");

  let sceneExplodeScale = null;
  const mockScene = {
    setExplodedScale(scale) {
      sceneExplodeScale = scale;
      return scale;
    },
  };

  let callbackScale = null;

  const ui = new AssemblyUI({
    document: doc,
    toolbarContainer,
    scene: mockScene,
    onExplodeChange(scale) {
      callbackScale = scale;
    },
  });

  ui.setAssembly({
    product_name: "Gearbox.CATProduct",
    instances: [],
  });

  const slider = toolbarContainer.querySelector("#explode-slider");
  const valueDisplay = toolbarContainer.querySelector("#explode-value");

  assert.ok(slider, "Exploded slider input must exist");
  assert.ok(valueDisplay, "Exploded value display must exist");
  assert.equal(slider.getAttribute("min"), "0.0");
  assert.equal(slider.getAttribute("max"), "3.0");
  assert.equal(valueDisplay.textContent, "0.00");

  // Set scale programmatically
  ui.setExplodedScale(1.85);

  assert.equal(ui.getExplodedScale(), 1.85);
  assert.equal(sceneExplodeScale, 1.85);
  assert.equal(callbackScale, 1.85);
  assert.equal(valueDisplay.textContent, "1.85");
  assert.equal(slider.value, "1.85");

  // Clamping test: scale < 0 clamps to 0.0, scale > 3.0 clamps to 3.0
  ui.setExplodedScale(-0.5);
  assert.equal(ui.getExplodedScale(), 0.0);

  ui.setExplodedScale(5.0);
  assert.equal(ui.getExplodedScale(), 3.0);
});

/* -------------------------------------------------------------------------- */
/* Test 8: Summary Bar Counts Verification                                    */
/* -------------------------------------------------------------------------- */
test("Summary Bar renders correct totals and canonical status breakdowns", () => {
  const doc = createMinimalDocument();
  const summaryContainer = doc.createElement("div");

  const ui = new AssemblyUI({
    document: doc,
    summaryContainer,
  });

  const counts = {
    total: 10,
    placed: 6,
    identity: 2,
    unresolved: 1,
    undecodable: 1,
  };

  ui.renderSummary(counts);

  const html = summaryContainer.innerHTML;
  assert.ok(html.includes("Total") && html.includes("10"), "Summary must display total count 10");
  assert.ok(html.includes("Placed") && html.includes("6"), "Summary must display placed count 6");
  assert.ok(html.includes("Identity") && html.includes("2"), "Summary must display identity count 2");
  assert.ok(html.includes("Unresolved") && html.includes("1"), "Summary must display unresolved count 1");
  assert.ok(html.includes("Undecodable") && html.includes("1"), "Summary must display undecodable count 1");
});

/* -------------------------------------------------------------------------- */
/* Test 9: Multi-Product Assembly Switcher (§4.3)                             */
/* -------------------------------------------------------------------------- */
test("Multi-product switcher handles selection and change notifications", () => {
  const doc = createMinimalDocument();
  const switcherContainer = doc.createElement("div");

  let switchedProduct = null;

  const ui = new AssemblyUI({
    document: doc,
    switcherContainer,
    onSwitchProduct(prod) {
      switchedProduct = prod;
    },
  });

  // 1. Single product: switcher remains empty
  ui.setProductList([{ name: "OnlyOne.CATProduct" }]);
  assert.equal(switcherContainer.innerHTML, "", "Switcher should not show for single product");

  // 2. Multi-product dataset: switcher renders select dropdown
  const products = [
    { name: "RootProduct.CATProduct", stem: "RootProduct" },
    { name: "SubAssembly_A.CATProduct", stem: "SubAssembly_A" },
    { name: "SubAssembly_B.CATProduct", stem: "SubAssembly_B" },
  ];

  ui.setProductList(products, "RootProduct.CATProduct");

  const select = switcherContainer.querySelector("#root-product-select");
  assert.ok(select, "Select dropdown must be rendered for multi-product dataset");
  assert.ok(select.innerHTML.includes("SubAssembly_A.CATProduct"));

  // Trigger change
  select.value = "SubAssembly_A.CATProduct";
  select.dispatchEvent({ type: "change" });

  assert.ok(switchedProduct, "onSwitchProduct callback must fire on select change");
  assert.equal(switchedProduct.name, "SubAssembly_A.CATProduct");
});

/* -------------------------------------------------------------------------- */
/* Test 10: Integration with VirtualFileCatalog and AssemblyScene             */
/* -------------------------------------------------------------------------- */
test("Full Integration: VirtualFileCatalog resolution and AssemblyScene coordination", () => {
  const catalog = new VirtualFileCatalog();
  catalog.registerFile({ name: "Base.CATPart", bytes: new Uint8Array([1, 2, 3]) });
  // Note: "MissingBracket.CATPart" is intentionally omitted from catalog!

  const doc = createMinimalDocument();
  const treeContainer = doc.createElement("div");
  const summaryContainer = doc.createElement("div");
  const inspectorContainer = doc.createElement("div");

  const scene = new AssemblyScene(null, { applyRootBasis: false });

  const ui = new AssemblyUI({
    document: doc,
    treeContainer,
    summaryContainer,
    inspectorContainer,
    scene,
    catalog,
  });

  const productDoc = {
    product_name: "CatalogCoordination.CATProduct",
    instances: [
      {
        instance_name: "Base.1",
        part_number: "Base",
        placement_status: STATUS_PLACED,
        transform: [10, 20, 30, 1, 0, 0, 0],
      },
      {
        instance_name: "MissingBracket.1",
        part_number: "MissingBracket", // Not in catalog!
        placement_status: STATUS_PLACED, // Parser declared placed, but catalog lacks file!
        transform: [0, 0, 0, 1, 0, 0, 0],
      },
    ],
  };

  ui.setAssembly(productDoc, catalog);

  // MissingBracket should be reconciled as unresolved because catalog lacks part!
  const missingNode = treeContainer.querySelector('[data-instance-id="MissingBracket.1"]');
  assert.ok(missingNode, "Missing bracket must be visible in tree");
  assert.ok(missingNode.classList.contains("status-unresolved"), "Missing bracket must be marked status-unresolved");
  assert.ok(missingNode.innerHTML.includes("badge-unresolved"), "Missing bracket must render badge-unresolved");

  // Base.1 is resolved and placed
  const baseNode = treeContainer.querySelector('[data-instance-id="Base.1"]');
  assert.ok(baseNode, "Base instance must be visible in tree");
  assert.ok(baseNode.classList.contains("status-placed"), "Base instance must be marked status-placed");

  // Tree selection updates inspector
  ui.selectInstance("MissingBracket.1");
  const inspectorHtml = inspectorContainer.innerHTML;
  assert.ok(inspectorHtml.includes("Unresolved Part"));
  assert.ok(inspectorHtml.includes("missing from uploaded catalog"));
});

/* -------------------------------------------------------------------------- */
/* Execute All Tests                                                          */
/* -------------------------------------------------------------------------- */
async function run() {
  let passed = 0;
  for (const { name, fn } of tests) {
    try {
      await fn();
      console.log(`  ✓ ${name}`);
      passed++;
    } catch (err) {
      console.error(`  ✗ ${name}`);
      console.error(err);
      process.exit(1);
    }
  }
  console.log(`\nAll ${passed}/${tests.length} Assembly UI & Classification Tree tests passed successfully!`);
}

run();
