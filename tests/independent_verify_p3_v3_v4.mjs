/* Independent Verification Script for Phase 6 Assembly Viewer Pipeline
   Tickets P3-V3 & P3-V4 (Commits 267402a & 8ef8e0c)
   Author: Independent Verifier Sub-Agent
   Date: 2026-11-16
*/

import assert from "node:assert/strict";
import zlib from "node:zlib";
import * as THREE from "../site/viewer/three.module.min.js";
import {
  VirtualFileCatalog,
  CatalogEntry,
  normalizePath,
  extractFilename,
  extractStem,
  extractExtension,
  STATUS_RESOLVED,
  STATUS_UNRESOLVED,
} from "../site/viewer/catalog.js";
import {
  isZipSignature,
  isZipFile,
  decompressDeflateRaw,
  unpackZip,
  selectRootProduct,
  ingestFiles,
  IngestionCoordinator,
} from "../site/viewer/ingest.js";
import {
  AssemblyScene,
  GeometryPool,
  STATUS_PLACED,
  STATUS_IDENTITY,
  STATUS_UNDECODABLE,
  createBasisMatrix,
  createBasisInverseMatrix,
  transformPointBasis,
  composeCatiaMatrix,
  catiaToThreeMatrix,
  composeThreeMatrix,
  decomposeTransform,
  normalizePartNumber,
  buildBufferGeometry,
  computeAssemblyCentroid,
  computeExplodedPosition,
  computeEulerDegrees,
  computeAxisAngle,
} from "../site/viewer/assembly_scene.js";

const EPSILON = 1e-9;
function assertClose(a, b, msg = "", tol = EPSILON) {
  assert(
    Math.abs(a - b) <= tol,
    `${msg} expected ${b} but got ${a} (diff ${Math.abs(a - b)} > ${tol})`
  );
}

function assertVector3Close(v, expected, msg = "", tol = EPSILON) {
  assertClose(v.x, expected.x, `${msg} [x]`, tol);
  assertClose(v.y, expected.y, `${msg} [y]`, tol);
  assertClose(v.z, expected.z, `${msg} [z]`, tol);
}

function assertMatrixClose(m1, m2, msg = "", tol = EPSILON) {
  const e1 = m1.elements;
  const e2 = m2.elements;
  for (let i = 0; i < 16; i++) {
    assertClose(e1[i], e2[i], `${msg} element[${i}]`, tol);
  }
}

console.log("================================================================================");
console.log("STARTING INDEPENDENT VERIFICATION: P3-V3 & P3-V4 ASSEMBLY VIEWER PIPELINE");
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
// SECTION 1: 248/382 PartNumber Stem-Join Resolution Law (Spec §4.2)
// =============================================================================
console.log("--- Section 1: PartNumber Stem-Join Resolution Law ---");

check("1.1: normalizePath handles Windows slashes, redundant slashes, and relative prefixes", () => {
  assert.equal(normalizePath("foo\\bar\\baz.CATPart"), "foo/bar/baz.CATPart");
  assert.equal(normalizePath("./models//sub///part.CATPart"), "models/sub/part.CATPart");
  assert.equal(normalizePath("/deep//nested\\file.CATProduct"), "deep/nested/file.CATProduct");
  assert.equal(normalizePath("   spaced/path.catpart   "), "spaced/path.catpart");
  assert.equal(normalizePath(""), "");
  assert.equal(normalizePath(null), "");
});

check("1.2: extractStem and extractExtension handle CATIA and non-CATIA cases", () => {
  assert.equal(extractStem("part.CATPart"), "part");
  assert.equal(extractStem("PART.catpart"), "PART");
  assert.equal(extractStem("Assembly.CATProduct"), "Assembly");
  assert.equal(extractStem("Bracket.Rev_1.2.CATPart"), "Bracket.Rev_1.2");
  assert.equal(extractStem("models/sub/part.CATPart"), "part");
  assert.equal(extractExtension("part.CATPart"), ".catpart");
  assert.equal(extractExtension("ASSEMBLY.CATPRODUCT"), ".catproduct");
  assert.equal(extractExtension("no_ext"), "");
});

check("1.3: VirtualFileCatalog stem resolution priority chain (exact, case-insensitive, suffix, paths)", () => {
  const cat = new VirtualFileCatalog();

  // Register diverse files
  cat.register({ name: "ac1.CATPart", bytes: new Uint8Array([1, 2, 3]) }, "models/ac1.CATPart");
  cat.register({ name: "BRACKET_BASE.CATPart", bytes: new Uint8Array([4, 5]) }, "parts/BRACKET_BASE.CATPart");
  cat.register({ name: "Pin_10mm.catpart", bytes: new Uint8Array([6]) }, "Pin_10mm.catpart");
  cat.register({ name: "Complex.Part.v2.CATPart", bytes: new Uint8Array([7]) }, "sub/Complex.Part.v2.CATPart");
  cat.register({ name: "Product1.CATProduct", bytes: new Uint8Array([8]) }, "Product1.CATProduct");

  // 1. Exact stem
  assert.equal(cat.resolvePart("ac1")?.name, "ac1.CATPart");

  // 2. Case-insensitive stem
  assert.equal(cat.resolvePart("AC1")?.name, "ac1.CATPart");
  assert.equal(cat.resolvePart("bracket_base")?.name, "BRACKET_BASE.CATPart");
  assert.equal(cat.resolvePart("pin_10mm")?.name, "Pin_10mm.catpart");

  // 3. Exact filename with extension
  assert.equal(cat.resolvePart("ac1.CATPart")?.name, "ac1.CATPart");
  assert.equal(cat.resolvePart("AC1.CATPart")?.name, "ac1.CATPart");
  assert.equal(cat.resolvePart("ac1.catpart")?.name, "ac1.CATPart");

  // 4. Relative path
  assert.equal(cat.resolvePart("models/ac1.CATPart")?.name, "ac1.CATPart");
  assert.equal(cat.resolvePart("parts/bracket_base.catpart")?.name, "BRACKET_BASE.CATPart");

  // 5. Complex stem with multiple dots
  assert.equal(cat.resolvePart("Complex.Part.v2")?.name, "Complex.Part.v2.CATPart");
  assert.equal(cat.resolvePart("complex.part.v2")?.name, "Complex.Part.v2.CATPart");

  // 6. Non-existent part returns null
  assert.equal(cat.resolvePart("NonExistentPart"), null);
  assert.equal(cat.resolvePart(""), null);
  assert.equal(cat.resolvePart(null), null);
});

check("1.4: Unresolved part tracking and non-dropping invariant", () => {
  const cat = new VirtualFileCatalog();
  cat.register({ name: "Bolt.CATPart", bytes: new Uint8Array([1]) });

  const instances = [
    { instance_name: "Bolt.1", part_number: "Bolt" },
    { instance_name: "Bolt.2", part_number: "Bolt" },
    { instance_name: "Nut.1", part_number: "Nut_M8" },
    { instance_name: "Washer.1", part_number: "Washer_8" },
  ];

  const resolvedList = cat.resolveInstances(instances);
  assert.equal(resolvedList.length, 4);

  assert.equal(resolvedList[0].status, STATUS_RESOLVED);
  assert.equal(resolvedList[0].resolved, true);
  assert.equal(resolvedList[1].status, STATUS_RESOLVED);
  assert.equal(resolvedList[1].resolved, true);

  assert.equal(resolvedList[2].status, STATUS_UNRESOLVED);
  assert.equal(resolvedList[2].resolved, false);
  assert.equal(resolvedList[2].entry, null);
  assert.equal(resolvedList[3].status, STATUS_UNRESOLVED);
  assert.equal(resolvedList[3].resolved, false);

  // Invariant: Unresolved instances are preserved in tracking map and never dropped
  assert.equal(cat.getInstanceStatus("Nut.1")?.status, STATUS_UNRESOLVED);
  assert.equal(cat.getInstanceStatus("Washer.1")?.status, STATUS_UNRESOLVED);

  const missing = cat.listUnresolved(instances);
  assert.deepEqual(missing.sort(), ["Nut_M8", "Washer_8"].sort());

  const present = cat.listResolved(instances);
  assert.deepEqual(present, ["Bolt"]);
});

// =============================================================================
// SECTION 2: In-Browser ZIP Extraction & Root Product Disambiguation (Spec §4.1, §4.3)
// =============================================================================
console.log("\n--- Section 2: In-Browser ZIP Extraction & Root Disambiguation ---");

// Helper: build synthetic ZIP
function makeZip(files) {
  const localHdrs = [];
  const cdHdrs = [];
  let offset = 0;

  const crcTable = new Uint32Array(256);
  for (let i = 0; i < 256; i++) {
    let c = i;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    crcTable[i] = c;
  }

  for (const f of files) {
    const raw = Buffer.isBuffer(f.content) ? f.content : Buffer.from(f.content || "");
    const method = f.method !== undefined ? f.method : 8; // 8 = deflate
    const comp = method === 8 ? zlib.deflateRawSync(raw) : raw;
    const nameBuf = Buffer.from(f.path, "utf-8");

    let crc = 0 ^ -1;
    for (let i = 0; i < raw.length; i++) {
      crc = (crc >>> 8) ^ crcTable[(crc ^ raw[i]) & 0xff];
    }
    crc = (crc ^ -1) >>> 0;

    const loc = Buffer.alloc(30 + nameBuf.length);
    loc.writeUInt32LE(0x04034b50, 0);
    loc.writeUInt16LE(20, 4);
    loc.writeUInt16LE(0, 6);
    loc.writeUInt16LE(method, 8);
    loc.writeUInt32LE(crc, 14);
    loc.writeUInt32LE(comp.length, 18);
    loc.writeUInt32LE(raw.length, 22);
    loc.writeUInt16LE(nameBuf.length, 26);
    loc.writeUInt16LE(0, 28);
    nameBuf.copy(loc, 30);

    const locOffset = offset;
    localHdrs.push(loc, comp);
    offset += loc.length + comp.length;

    const cd = Buffer.alloc(46 + nameBuf.length);
    cd.writeUInt32LE(0x02014b50, 0);
    cd.writeUInt16LE(20, 4);
    cd.writeUInt16LE(20, 6);
    cd.writeUInt16LE(0, 8);
    cd.writeUInt16LE(method, 10);
    cd.writeUInt32LE(crc, 16);
    cd.writeUInt32LE(comp.length, 20);
    cd.writeUInt32LE(raw.length, 24);
    cd.writeUInt16LE(nameBuf.length, 28);
    cd.writeUInt32LE(locOffset, 42);
    nameBuf.copy(cd, 46);

    cdHdrs.push(cd);
  }

  const cdBuf = Buffer.concat(cdHdrs);
  const eocd = Buffer.alloc(22);
  eocd.writeUInt32LE(0x06054b50, 0);
  eocd.writeUInt16LE(files.length, 8);
  eocd.writeUInt16LE(files.length, 10);
  eocd.writeUInt32LE(cdBuf.length, 12);
  eocd.writeUInt32LE(offset, 16);

  return Buffer.concat([...localHdrs, cdBuf, eocd]);
}

await asyncCheck("2.1: unpackZip extracts DEFLATE and STORED entries and filters metadata", async () => {
  const zipBuf = makeZip([
    { path: "assembly/Product1.CATProduct", content: "PROD_DATA", method: 8 },
    { path: "assembly/parts/Part001.CATPart", content: "PART001_DATA", method: 8 },
    { path: "assembly/parts/Part002.CATPart", content: "PART002_STORED", method: 0 },
    { path: "__MACOSX/._Product1.CATProduct", content: "GARBAGE", method: 0 },
    { path: "assembly/.DS_Store", content: "DS_STORE", method: 0 },
    { path: "assembly/empty_dir/", content: "", method: 0 },
  ]);

  const extracted = await unpackZip(new Uint8Array(zipBuf));
  assert.equal(extracted.length, 3, "Only 3 true files extracted (metadata and dirs filtered)");

  const names = extracted.map((e) => e.name).sort();
  assert.deepEqual(names, ["Part001.CATPart", "Part002.CATPart", "Product1.CATProduct"]);

  const prod = extracted.find((e) => e.name === "Product1.CATProduct");
  assert.equal(Buffer.from(prod.bytes).toString("utf-8"), "PROD_DATA");

  const p2 = extracted.find((e) => e.name === "Part002.CATPart");
  assert.equal(Buffer.from(p2.bytes).toString("utf-8"), "PART002_STORED");
});

check("2.2: selectRootProduct single vs multi-product disambiguation (§4.3)", () => {
  // Single product case
  const single = [new CatalogEntry({ name: "Sub1.CATProduct" })];
  const resSingle = selectRootProduct(single);
  assert.equal(resSingle.rootProduct?.name, "Sub1.CATProduct");
  assert.equal(resSingle.candidates.length, 1);

  // Multi-product heuristic disambiguation
  const multi = [
    new CatalogEntry({ name: "SubAssembly_Arm.CATProduct", path: "robot/sub/SubAssembly_Arm.CATProduct" }),
    new CatalogEntry({ name: "Robot_IsRoot.CATProduct", path: "robot/Robot_IsRoot.CATProduct" }),
    new CatalogEntry({ name: "SubAssembly_Gripper.CATProduct", path: "robot/sub/SubAssembly_Gripper.CATProduct" }),
  ];

  const resMulti = selectRootProduct(multi);
  // Robot_IsRoot has +100 score for IsRoot and shallower depth
  assert.equal(resMulti.rootProduct?.name, "Robot_IsRoot.CATProduct");
  assert.equal(resMulti.candidates.length, 3);

  // Preferred root override
  const resOverride = selectRootProduct(multi, null, { preferredRoot: "SubAssembly_Gripper" });
  assert.equal(resOverride.rootProduct?.name, "SubAssembly_Gripper.CATProduct");
});

await asyncCheck("2.3: IngestionCoordinator master pipeline handles ZIP archive drop", async () => {
  const zipBuf = makeZip([
    { path: "Car/MainAssembly_Root.CATProduct", content: "ROOT", method: 8 },
    { path: "Car/Wheel.CATPart", content: "WHEEL_BYTES", method: 8 },
    { path: "Car/Chassis.CATPart", content: "CHASSIS_BYTES", method: 8 },
  ]);

  const coordinator = new IngestionCoordinator();
  const res = await coordinator.ingest({ name: "CarAssembly.zip", bytes: new Uint8Array(zipBuf) });

  assert.equal(res.totalFiles, 3);
  assert.equal(res.productsCount, 1);
  assert.equal(res.partsCount, 2);
  assert.equal(res.hasRootProduct, true);
  assert.equal(res.rootProduct?.name, "MainAssembly_Root.CATProduct");
  assert.equal(coordinator.catalog.resolvePart("Wheel")?.name, "Wheel.CATPart");
  assert.equal(coordinator.catalog.resolvePart("Chassis")?.name, "Chassis.CATPart");
});

// =============================================================================
// SECTION 3: Basis Transformation B = R_X(-pi/2) & Mathematical Invariance
// =============================================================================
console.log("\n--- Section 3: Basis Transformation B = R_X(-pi/2) & Mathematical Invariance ---");

check("3.1: Change-of-basis matrix B and orthogonal inverse B^{-1} = B^T", () => {
  const B = createBasisMatrix();
  const B_inv = createBasisInverseMatrix();

  // B elements in column-major order as stored in Three.Matrix4:
  // Row 0: [1,  0, 0, 0]
  // Row 1: [0,  0, 1, 0]
  // Row 2: [0, -1, 0, 0]
  // Row 3: [0,  0, 0, 1]
  const eB = B.elements;
  assert.equal(eB[0], 1);  assert.equal(eB[4], 0);  assert.equal(eB[8], 0);   assert.equal(eB[12], 0);
  assert.equal(eB[1], 0);  assert.equal(eB[5], 0);  assert.equal(eB[9], 1);   assert.equal(eB[13], 0);
  assert.equal(eB[2], 0);  assert.equal(eB[6], -1); assert.equal(eB[10], 0);  assert.equal(eB[14], 0);
  assert.equal(eB[3], 0);  assert.equal(eB[7], 0);  assert.equal(eB[11], 0);  assert.equal(eB[15], 1);

  // Orthogonal inverse: B * B^T = I
  const prod = new THREE.Matrix4().multiplyMatrices(B, B_inv);
  assertMatrixClose(prod, new THREE.Matrix4().identity(), "B * B^{-1} == I");
});

check("3.2: Coordinate mapping: CATIA Z-up (+X right, +Y fwd, +Z up) -> Three Y-up (+X right, +Y up, +Z out)", () => {
  const B = createBasisMatrix();

  const pX = transformPointBasis(new THREE.Vector3(100, 0, 0), B);
  assertVector3Close(pX, new THREE.Vector3(100, 0, 0), "CATIA +X maps to Three +X");

  const pY = transformPointBasis(new THREE.Vector3(0, 100, 0), B);
  assertVector3Close(pY, new THREE.Vector3(0, 0, -100), "CATIA +Y (north) maps to Three -Z (into screen)");

  const pZ = transformPointBasis(new THREE.Vector3(0, 0, 100), B);
  assertVector3Close(pZ, new THREE.Vector3(0, 100, 0), "CATIA +Z (up) maps to Three +Y (up)");
});

check("3.3: W-first quaternion mapping: [qw, qx, qy, qz] -> THREE.Quaternion(qx, qy, qz, qw)", () => {
  // Test asymmetric rotation (e.g. 45 deg around X, 30 deg around Y, 60 deg around Z)
  const euler = new THREE.Euler((45 * Math.PI) / 180, (30 * Math.PI) / 180, (60 * Math.PI) / 180, "XYZ");
  const qExpected = new THREE.Quaternion().setFromEuler(euler);

  // In CATIA 7-tuple: [tx, ty, tz, qw, qx, qy, qz]
  const record7 = [10, 20, 30, qExpected.w, qExpected.x, qExpected.y, qExpected.z];
  const mCatia = composeCatiaMatrix(record7);

  const decompPos = new THREE.Vector3();
  const decompQuat = new THREE.Quaternion();
  mCatia.decompose(decompPos, decompQuat, new THREE.Vector3());

  assertVector3Close(decompPos, new THREE.Vector3(10, 20, 30), "Translation preserved in CATIA matrix");
  assertClose(Math.abs(decompQuat.dot(qExpected)), 1.0, "Quaternion recovered matches expected orientation", 1e-7);
});

check("3.4: Mathematical Invariance: M_Three * B * p == B * M_CATIA * p for arbitrary transforms", () => {
  const B = createBasisMatrix();
  const B_inv = createBasisInverseMatrix();

  // Test 10 distinct random transforms and 10 random points each
  for (let tIdx = 0; tIdx < 10; tIdx++) {
    const tx = (Math.random() - 0.5) * 1000;
    const ty = (Math.random() - 0.5) * 1000;
    const tz = (Math.random() - 0.5) * 1000;

    // Random unit quaternion
    const u1 = Math.random(), u2 = Math.random(), u3 = Math.random();
    const qw = Math.sqrt(1 - u1) * Math.sin(2 * Math.PI * u2);
    const qx = Math.sqrt(1 - u1) * Math.cos(2 * Math.PI * u2);
    const qy = Math.sqrt(u1) * Math.sin(2 * Math.PI * u3);
    const qz = Math.sqrt(u1) * Math.cos(2 * Math.PI * u3);

    const mCatia = composeCatiaMatrix([tx, ty, tz, qw, qx, qy, qz]);
    const mThree = catiaToThreeMatrix(mCatia, B, B_inv);

    for (let pIdx = 0; pIdx < 10; pIdx++) {
      const p = new THREE.Vector3(
        (Math.random() - 0.5) * 500,
        (Math.random() - 0.5) * 500,
        (Math.random() - 0.5) * 500
      );

      // LHS: Transform point in CATIA space, then map to Three space via B
      const lhs = p.clone().applyMatrix4(mCatia).applyMatrix4(B);

      // RHS: Map point to Three space via B, then transform via M_Three
      const rhs = p.clone().applyMatrix4(B).applyMatrix4(mThree);

      assertVector3Close(lhs, rhs, `Invariance trial tIdx=${tIdx}, pIdx=${pIdx}`, 1e-7);
    }
  }
});

// =============================================================================
// SECTION 4: Zero-Duplication GPU Memory Pooling Contract (Spec §1.3, §5.3)
// =============================================================================
console.log("\n--- Section 4: Zero-Duplication GPU Memory Pooling Contract ---");

check("4.1: Repeated instances share identical BufferGeometry reference without duplication", () => {
  const assembly = new AssemblyScene(null);

  const boltGeom = buildBufferGeometry(
    new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0]),
    new Uint32Array([0, 1, 2])
  );
  const bracketGeom = buildBufferGeometry(
    new Float32Array([0, 0, 0, 5, 0, 0, 0, 5, 0]),
    new Uint32Array([0, 1, 2])
  );
  const pinGeom = buildBufferGeometry(
    new Float32Array([0, 0, 0, 2, 0, 0, 0, 2, 0]),
    new Uint32Array([0, 1, 2])
  );

  assembly.registerGeometry("Bolt_M8", boltGeom);
  assembly.registerGeometry("Bracket_Main", bracketGeom);
  assembly.registerGeometry("Pin_5mm", pinGeom);

  // 14 bolts, 4 brackets, 6 pins (24 total instances, 3 unique geometries)
  for (let i = 1; i <= 14; i++) {
    assembly.addInstance({
      instance_name: `Bolt_M8.${i}`,
      part_number: "Bolt_M8",
      placement_status: "placed",
      transform: [i * 10, 0, 0, 1, 0, 0, 0],
    });
  }
  for (let j = 1; j <= 4; j++) {
    assembly.addInstance({
      instance_name: `Bracket_Main.${j}`,
      part_number: "Bracket_Main",
      placement_status: "placed",
      transform: [0, j * 25, 0, 1, 0, 0, 0],
    });
  }
  for (let k = 1; k <= 6; k++) {
    assembly.addInstance({
      instance_name: `Pin_5mm.${k}`,
      part_number: "Pin_5mm",
      placement_status: "placed",
      transform: [0, 0, k * 15, 1, 0, 0, 0],
    });
  }

  assert.equal(assembly.totalInstances, 24, "Total instances is 24");
  assert.equal(assembly.uniqueGeometryCount, 3, "Geometry pool holds exactly 3 unique BufferGeometry instances");

  // Verify memory sharing: all 14 bolts point to boltGeom reference
  for (let i = 1; i <= 14; i++) {
    const inst = assembly.getInstance(`Bolt_M8.${i}`);
    const mesh = inst.children.find((c) => c.isMesh);
    assert(mesh, `Bolt ${i} has mesh`);
    assert.equal(mesh.geometry, boltGeom, `Bolt ${i} shares boltGeom reference`);
  }

  // All 4 brackets point to bracketGeom reference
  for (let j = 1; j <= 4; j++) {
    const inst = assembly.getInstance(`Bracket_Main.${j}`);
    const mesh = inst.children.find((c) => c.isMesh);
    assert.equal(mesh.geometry, bracketGeom, `Bracket ${j} shares bracketGeom reference`);
  }

  // Lifecycle disposal: verify dispose() cleans up geometry
  let boltDisposed = false;
  boltGeom.dispose = () => { boltDisposed = true; };
  assembly.dispose();

  assert.equal(boltDisposed, true, "boltGeom.dispose() called on assembly.dispose()");
  assert.equal(assembly.totalInstances, 0, "Scene cleared");
  assert.equal(assembly.uniqueGeometryCount, 0, "Pool cleared");
});

// =============================================================================
// SECTION 5: Anti-Masking Invariant (Clause 3 of P4 Bar)
// =============================================================================
console.log("\n--- Section 5: Anti-Masking Invariant (Clause 3 of P4 Bar) ---");

check("5.1: Undecodable and Unresolved instances are never defaulted to origin (0,0,0)", () => {
  const assembly = new AssemblyScene(null);
  const dummyGeom = buildBufferGeometry([0, 0, 0, 1, 0, 0, 0, 1, 0], [0, 1, 2]);
  assembly.registerGeometry("PartA", dummyGeom);

  // Placed instance at (50, 50, 50)
  assembly.addInstance({
    instance_name: "Placed.1",
    part_number: "PartA",
    placement_status: STATUS_PLACED,
    transform: [50, 50, 50, 1, 0, 0, 0],
  });

  // Identity instance (explicitly no _Position in CATIA, rendered at origin)
  assembly.addInstance({
    instance_name: "Ident.1",
    part_number: "PartA",
    placement_status: STATUS_IDENTITY,
  });

  // Undecodable instance (has _Position, but cannot decode)
  const undecNode = assembly.addInstance({
    instance_name: "Undecodable.1",
    part_number: "PartA",
    placement_status: STATUS_UNDECODABLE,
    has_position_attr: true,
  });

  // Unresolved instance (missing part file)
  const unresNode = assembly.addInstance({
    instance_name: "Missing.1",
    part_number: "MissingPart",
    placement_status: STATUS_UNRESOLVED,
  });

  // Invariant verification:
  // 1. isPlacedSpatial must be false
  assert.equal(undecNode.userData.isPlacedSpatial, false);
  assert.equal(unresNode.userData.isPlacedSpatial, false);

  // 2. Scene node must be invisible
  assert.equal(undecNode.visible, false);
  assert.equal(unresNode.visible, false);

  // 3. Excluded from getPlacedInstances()
  const placedList = assembly.getPlacedInstances();
  assert.equal(placedList.length, 2, "Only Placed.1 and Ident.1 are in getPlacedInstances()");
  assert(!placedList.includes(undecNode), "Undecodable node not in placedList");
  assert(!placedList.includes(unresNode), "Unresolved node not in placedList");

  // 4. Centroid does NOT include undecodable/unresolved instances at origin
  // Placed.1 is at (50,50,50), Ident.1 is at (0,0,0). Centroid is (25, 25, 25).
  // If undecodable/unresolved were falsely included at (0,0,0), centroid would be (50/4, 50/4, 50/4) = (12.5, 12.5, 12.5).
  assertVector3Close(assembly.assemblyCentroid, new THREE.Vector3(25, 25, 25), "Centroid strictly excludes undecodable/unresolved");

  // 5. Exploded view does NOT displace undecodable instances
  assembly.setExplodedScale(2.0);
  assert.equal(undecNode.visible, false, "Undecodable instance remains invisible during explosion");
});

check("5.2: Isolation and clearIsolation preserve hidden state of undecodable instances", () => {
  const assembly = new AssemblyScene(null);
  const dummyGeom = buildBufferGeometry([0, 0, 0, 1, 0, 0, 0, 1, 0], [0, 1, 2]);
  assembly.registerGeometry("PartA", dummyGeom);

  assembly.addInstance({ instance_name: "P1", part_number: "PartA", placement_status: STATUS_PLACED, transform: [10, 0, 0, 1, 0, 0, 0] });
  assembly.addInstance({ instance_name: "P2", part_number: "PartA", placement_status: STATUS_PLACED, transform: [20, 0, 0, 1, 0, 0, 0] });
  assembly.addInstance({ instance_name: "Undec", part_number: "PartA", placement_status: STATUS_UNDECODABLE });

  // Isolate P1
  assembly.isolateInstance("P1");
  assert.equal(assembly.getInstanceVisibility("P1"), true);
  assert.equal(assembly.getInstanceVisibility("P2"), false);
  assert.equal(assembly.getInstanceVisibility("Undec"), false);

  // Clear isolation: P1 and P2 restored, Undec MUST remain false
  assembly.clearIsolation();
  assert.equal(assembly.getInstanceVisibility("P1"), true);
  assert.equal(assembly.getInstanceVisibility("P2"), true);
  assert.equal(assembly.getInstanceVisibility("Undec"), false, "clearIsolation does NOT leak Undec to visible");
});

console.log("\n================================================================================");
console.log(`INDEPENDENT VERIFICATION COMPLETE: ${passedChecks}/${totalChecks} CHECKS PASSED`);
console.log("================================================================================\n");
