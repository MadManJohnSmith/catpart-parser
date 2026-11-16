/* Test Suite for 3D Spatial Assembly Placement & Scene Graph (Ticket P3-V4)
   Design Authority: docs/specs/phase6-assembly-viewer-spec.md §5 and §8

   Runs under Node.js 18+ ES module loader.
   Tests:
   1. Coordinate transformation B = R_X(-pi/2) and inverse B^{-1} = R_X(+pi/2)
   2. Matrix composition from 7-tuple [tx, ty, tz, qw, qx, qy, qz]
   3. Basis transformation M_Three = B * M_CATIA * B^{-1}
   4. Geometry pooling and GPU buffer deduplication contract
   5. Exploded view displacement math and non-accumulation
   6. Scene graph hierarchy, AssemblyRoot, and userData tagging
   7. Bounding box, bounding sphere, and camera framing
   8. Visibility toggles and instance isolation
   9. Anti-masking invariant: undecodable placements never defaulted to identity
*/

import assert from "node:assert/strict";
import * as THREE from "../site/viewer/three.module.min.js";
import {
  AssemblyScene,
  GeometryPool,
  STATUS_PLACED,
  STATUS_IDENTITY,
  STATUS_UNRESOLVED,
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
  buildCurvesGroup,
  computeAssemblyCentroid,
  computeExplodedPosition,
  computeEulerDegrees,
  computeAxisAngle,
} from "../site/viewer/assembly_scene.js";

const EPSILON = 1e-6;

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

console.log("Running Assembly Scene Graph & Placement test suite (Ticket P3-V4)...\n");

// --- Test 1: Coordinate Transformation B = R_X(-pi/2) ------------------------

{
  console.log("  Testing Basis Transformation B = R_X(-pi/2)...");

  const B = createBasisMatrix();
  const B_inv = createBasisInverseMatrix();

  // Test B * B^{-1} = Identity
  const identity = new THREE.Matrix4().multiplyMatrices(B, B_inv);
  assertMatrixClose(identity, new THREE.Matrix4().identity(), "B * B^{-1} == I");

  // Test vector mapping: (x, y, z) -> (x, z, -y)
  const p1 = new THREE.Vector3(10, 20, 30);
  const p1_three = transformPointBasis(p1, B);
  assertVector3Close(p1_three, new THREE.Vector3(10, 30, -20), "(10, 20, 30) -> (10, 30, -20)");

  // Inverse mapping: (x, z, -y) -> (x, y, z)
  const p1_recovered = p1_three.clone().applyMatrix4(B_inv);
  assertVector3Close(p1_recovered, p1, "Inverse mapping recovers original vector");

  // Pure axes test:
  // CATIA +X (right) -> Three +X (right)
  const right = transformPointBasis(new THREE.Vector3(1, 0, 0), B);
  assertVector3Close(right, new THREE.Vector3(1, 0, 0), "CATIA +X maps to Three +X");

  // CATIA +Y (forward/in-depth) -> Three -Z (into screen)
  const fwd = transformPointBasis(new THREE.Vector3(0, 1, 0), B);
  assertVector3Close(fwd, new THREE.Vector3(0, 0, -1), "CATIA +Y maps to Three -Z");

  // CATIA +Z (up) -> Three +Y (up)
  const up = transformPointBasis(new THREE.Vector3(0, 0, 1), B);
  assertVector3Close(up, new THREE.Vector3(0, 1, 0), "CATIA +Z maps to Three +Y");

  console.log("  ✓ Basis Transformation B = R_X(-pi/2) and inverse verified");
}

// --- Test 2: Matrix Composition from 7-tuple ----------------------------------

{
  console.log("  Testing Matrix Composition from 7-tuple [tx, ty, tz, qw, qx, qy, qz]...");

  // 1. Identity transform [0, 0, 0, 1, 0, 0, 0]
  const mIdent = composeCatiaMatrix([0, 0, 0, 1, 0, 0, 0]);
  assertMatrixClose(mIdent, new THREE.Matrix4().identity(), "Identity 7-tuple produces identity matrix");

  // 2. Pure translation [15.5, -25.0, 100.2, 1, 0, 0, 0]
  const mTrans = composeCatiaMatrix([15.5, -25.0, 100.2, 1, 0, 0, 0]);
  const pos = new THREE.Vector3();
  mTrans.decompose(pos, new THREE.Quaternion(), new THREE.Vector3());
  assertVector3Close(pos, new THREE.Vector3(15.5, -25.0, 100.2), "Pure translation matches");

  // 3. 90-degree rotation around X axis (CATIA):
  // qw = cos(45 deg) = sqrt(2)/2, qx = sin(45 deg) = sqrt(2)/2, qy = 0, qz = 0
  const s2 = Math.SQRT1_2;
  const mRotX = composeCatiaMatrix([0, 0, 0, s2, s2, 0, 0]);
  // Rotating (0, 1, 0) around X by +90 deg -> (0, 0, 1)
  const vY = new THREE.Vector3(0, 1, 0).applyMatrix4(mRotX);
  assertVector3Close(vY, new THREE.Vector3(0, 0, 1), "90 deg around X maps (0,1,0) -> (0,0,1)");

  // 4. 90-degree rotation around Z axis (CATIA):
  // qw = sqrt(2)/2, qx = 0, qy = 0, qz = sqrt(2)/2
  const mRotZ = composeCatiaMatrix([0, 0, 0, s2, 0, 0, s2]);
  // Rotating (1, 0, 0) around Z by +90 deg -> (0, 1, 0)
  const vX = new THREE.Vector3(1, 0, 0).applyMatrix4(mRotZ);
  assertVector3Close(vX, new THREE.Vector3(0, 1, 0), "90 deg around Z maps (1,0,0) -> (0,1,0)");

  // 5. Combined translation + rotation round-trip
  const original7 = [10.0, 20.0, 30.0, s2, 0, s2, 0]; // 90 deg around Y
  const mCombined = composeCatiaMatrix(original7);
  const decomp = decomposeTransform(mCombined);
  assertClose(decomp[0], 10.0, "round-trip tx");
  assertClose(decomp[1], 20.0, "round-trip ty");
  assertClose(decomp[2], 30.0, "round-trip tz");
  assertClose(Math.abs(decomp[3]), s2, "round-trip qw");
  assertClose(decomp[4], 0.0, "round-trip qx");
  assertClose(Math.abs(decomp[5]), s2, "round-trip qy");
  assertClose(decomp[6], 0.0, "round-trip qz");

  // 6. Non-normalized quaternion guard (e.g. [0, 0, 0, 2, 0, 0, 0])
  const mUnnorm = composeCatiaMatrix([0, 0, 0, 2.0, 0, 0, 0]);
  assertMatrixClose(mUnnorm, new THREE.Matrix4().identity(), "Unnormalized quat is normalized");

  console.log("  ✓ Matrix Composition from 7-tuple verified");
}

// --- Test 3: Coordinate Conversion M_Three = B * M_CATIA * B^{-1} --------------

{
  console.log("  Testing Basis-Converted Matrix M_Three = B * M_CATIA * B^{-1}...");

  const B = createBasisMatrix();
  const B_inv = createBasisInverseMatrix();

  // 1. Pure translation (10, 20, 30) in CATIA:
  // In Three.js coordinates, translation must be (10, 30, -20)
  const mCatiaTrans = composeCatiaMatrix([10, 20, 30, 1, 0, 0, 0]);
  const mThreeTrans = catiaToThreeMatrix(mCatiaTrans, B, B_inv);

  const threePos = new THREE.Vector3();
  mThreeTrans.decompose(threePos, new THREE.Quaternion(), new THREE.Vector3());
  assertVector3Close(threePos, new THREE.Vector3(10, 30, -20), "Translation mapped to (10, 30, -20)");

  // 2. Point equivalence: (M_Three * B * p) == B * (M_CATIA * p)
  // For any point p in CATIA space:
  const testPoints = [
    new THREE.Vector3(0, 0, 0),
    new THREE.Vector3(1, 0, 0),
    new THREE.Vector3(0, 5, 0),
    new THREE.Vector3(-2, 3, 10),
  ];

  const mCatiaComplex = composeCatiaMatrix([15, -10, 25, Math.SQRT1_2, 0, 0, Math.SQRT1_2]);
  const mThreeComplex = catiaToThreeMatrix(mCatiaComplex, B, B_inv);

  for (const p of testPoints) {
    // Left: transform point by M_CATIA in CATIA space, then project to Three via B
    const lhs = p.clone().applyMatrix4(mCatiaComplex).applyMatrix4(B);
    // Right: project point to Three via B, then transform by M_Three
    const rhs = p.clone().applyMatrix4(B).applyMatrix4(mThreeComplex);
    assertVector3Close(lhs, rhs, `Point equivalence for p=(${p.x},${p.y},${p.z})`);
  }

  // 3. Rotation around CATIA Z-axis (up) maps to rotation around Three.js Y-axis (up)
  const angle = Math.PI / 3; // 60 deg
  const qw = Math.cos(angle / 2);
  const qz = Math.sin(angle / 2);
  const mCatiaRotZ = composeCatiaMatrix([0, 0, 0, qw, 0, 0, qz]);
  const mThreeRotY = catiaToThreeMatrix(mCatiaRotZ, B, B_inv);

  const qThree = new THREE.Quaternion();
  mThreeRotY.decompose(new THREE.Vector3(), qThree, new THREE.Vector3());

  // Expected rotation in Three.js around +Y: qy = sin(angle/2), qw = cos(angle/2)
  const qExpected = new THREE.Quaternion(0, Math.sin(angle / 2), 0, Math.cos(angle / 2));
  assertClose(Math.abs(qThree.dot(qExpected)), 1.0, "CATIA Z rotation maps to Three Y rotation");

  console.log("  ✓ Basis-Converted Matrix M_Three = B * M_CATIA * B^{-1} verified");
}

// --- Test 4: Geometry Pooling & GPU Buffer Sharing -----------------------------

{
  console.log("  Testing Geometry Pooling & GPU Buffer Sharing (Contract Verification)...");

  const pool = new GeometryPool();

  // Create two distinct mock geometries (e.g. Bolt and Bracket)
  const geomBolt = buildBufferGeometry(
    new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0]),
    new Uint32Array([0, 1, 2])
  );
  const geomBracket = buildBufferGeometry(
    new Float32Array([0, 0, 0, 2, 0, 0, 0, 2, 0]),
    new Uint32Array([0, 1, 2])
  );

  // Register in pool
  pool.set("Bolt_M8", { geometry: geomBolt });
  pool.set("Bracket_L", { geometry: geomBracket });

  // 1. Unique geometry count must equal 2
  assert.equal(pool.size, 2, "Pool size == 2");
  assert.equal(pool.uniqueGeometryCount, 2, "uniqueGeometryCount == 2");

  // 2. Case-insensitive normalization retrieval
  assert(pool.has("Bolt_M8"), "has('Bolt_M8')");
  assert(pool.has("bolt_m8"), "has('bolt_m8') (case-insensitive)");
  assert(pool.has("Bolt_M8.CATPart"), "has('Bolt_M8.CATPart') (extension stripped)");
  assert.equal(pool.get("bolt_m8").geometry, geomBolt, "get('bolt_m8') retrieves geomBolt");

  // 3. Create AssemblyScene with 14 bolts and 4 brackets (18 total instances)
  const assembly = new AssemblyScene(null);
  assembly.registerGeometry("Bolt_M8", geomBolt);
  assembly.registerGeometry("Bracket_L", geomBracket);

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
      instance_name: `Bracket_L.${j}`,
      part_number: "Bracket_L",
      placement_status: "placed",
      transform: [0, j * 20, 0, 1, 0, 0, 0],
    });
  }

  assert.equal(assembly.totalInstances, 18, "Total instances == 18");
  assert.equal(assembly.uniqueGeometryCount, 2, "Unique geometry allocations == 2 (Proof of memory footprint)");

  // 4. Verify shared BufferGeometry references across all 14 bolts
  const bolt1 = assembly.getInstance("Bolt_M8.1");
  const bolt14 = assembly.getInstance("Bolt_M8.14");
  const meshBolt1 = bolt1.children.find((c) => c.isMesh);
  const meshBolt14 = bolt14.children.find((c) => c.isMesh);

  assert(meshBolt1, "Bolt 1 has mesh");
  assert(meshBolt14, "Bolt 14 has mesh");
  assert.equal(meshBolt1.geometry, geomBolt, "Bolt 1 mesh shares geomBolt");
  assert.equal(meshBolt14.geometry, geomBolt, "Bolt 14 mesh shares geomBolt");
  assert.equal(meshBolt1.geometry, meshBolt14.geometry, "Identical BufferGeometry reference shared between instances");

  // 5. Verify Bracket meshes share geomBracket, distinct from geomBolt
  const bracket1 = assembly.getInstance("Bracket_L.1");
  const meshBracket1 = bracket1.children.find((c) => c.isMesh);
  assert.equal(meshBracket1.geometry, geomBracket, "Bracket 1 shares geomBracket");
  assert.notEqual(meshBolt1.geometry, meshBracket1.geometry, "Bolt and Bracket geometries are distinct");

  // 6. Verify disposal lifecycle
  let disposedGeoms = 0;
  geomBolt.dispose = () => { disposedGeoms++; };
  geomBracket.dispose = () => { disposedGeoms++; };
  assembly.dispose();
  assert.equal(disposedGeoms, 2, "dispose() called on both shared BufferGeometry instances");
  assert.equal(assembly.totalInstances, 0, "Instances cleared on dispose");
  assert.equal(assembly.uniqueGeometryCount, 0, "Geometry pool cleared on dispose");

  console.log("  ✓ Geometry Pooling & GPU Buffer Sharing contract verified");
}

// --- Test 5: Exploded View Displacement Math -----------------------------------

{
  console.log("  Testing Exploded View Displacement Math & Non-Accumulation...");

  const assembly = new AssemblyScene(null);
  const dummyGeom = buildBufferGeometry([0, 0, 0, 1, 0, 0, 0, 1, 0], [0, 1, 2]);
  assembly.registerGeometry("PartA", dummyGeom);

  // Place 4 instances symmetrically around origin (0, 0, 0)
  // Centroid = (0, 0, 0)
  assembly.addInstance({
    instance_name: "InstEast",
    part_number: "PartA",
    placement_status: "placed",
    transform: [10, 0, 0, 1, 0, 0, 0],
  });
  assembly.addInstance({
    instance_name: "InstWest",
    part_number: "PartA",
    placement_status: "placed",
    transform: [-10, 0, 0, 1, 0, 0, 0],
  });
  assembly.addInstance({
    instance_name: "InstNorth",
    part_number: "PartA",
    placement_status: "placed",
    transform: [0, 20, 0, 1, 0, 0, 0],
  });
  assembly.addInstance({
    instance_name: "InstSouth",
    part_number: "PartA",
    placement_status: "placed",
    transform: [0, -20, 0, 1, 0, 0, 0],
  });

  // Verify aggregate centroid
  assertVector3Close(assembly.assemblyCentroid, new THREE.Vector3(0, 0, 0), "Aggregate centroid == (0,0,0)");

  const instE = assembly.getInstance("InstEast");
  const instN = assembly.getInstance("InstNorth");

  // 1. At scale lambda = 0: positions remain at base positions
  assembly.setExplodedScale(0.0);
  assert.equal(assembly.getExplodedScale(), 0.0);
  let posE = new THREE.Vector3().setFromMatrixPosition(instE.matrix);
  let posN = new THREE.Vector3().setFromMatrixPosition(instN.matrix);
  assertVector3Close(posE, new THREE.Vector3(10, 0, 0), "Scale 0.0: InstEast at (10, 0, 0)");
  assertVector3Close(posN, new THREE.Vector3(0, 20, 0), "Scale 0.0: InstNorth at (0, 20, 0)");

  // 2. At scale lambda = 1.0:
  // d_E = (10, 0, 0) - (0, 0, 0) = (10, 0, 0)
  // pos_E(1.0) = (10, 0, 0) + 1.0 * (10, 0, 0) = (20, 0, 0)
  // d_N = (0, 20, 0) - (0, 0, 0) = (0, 20, 0)
  // pos_N(1.0) = (0, 20, 0) + 1.0 * (0, 20, 0) = (0, 40, 0)
  assembly.setExplodedScale(1.0);
  assert.equal(assembly.getExplodedScale(), 1.0);
  posE.setFromMatrixPosition(instE.matrix);
  posN.setFromMatrixPosition(instN.matrix);
  assertVector3Close(posE, new THREE.Vector3(20, 0, 0), "Scale 1.0: InstEast at (20, 0, 0)");
  assertVector3Close(posN, new THREE.Vector3(0, 40, 0), "Scale 1.0: InstNorth at (0, 40, 0)");

  // 3. At scale lambda = 0.5:
  // pos_E(0.5) = (10, 0, 0) + 0.5 * (10, 0, 0) = (15, 0, 0)
  assembly.setExplodedScale(0.5);
  posE.setFromMatrixPosition(instE.matrix);
  assertVector3Close(posE, new THREE.Vector3(15, 0, 0), "Scale 0.5: InstEast at (15, 0, 0)");

  // 4. Non-accumulation test: slider moved repeatedly 0 -> 2.5 -> 1.0 -> 0.0
  assembly.setExplodedScale(2.5);
  posE.setFromMatrixPosition(instE.matrix);
  assertVector3Close(posE, new THREE.Vector3(35, 0, 0), "Scale 2.5: InstEast at (35, 0, 0)");

  assembly.setExplodedScale(0.0);
  posE.setFromMatrixPosition(instE.matrix);
  assertVector3Close(posE, new THREE.Vector3(10, 0, 0), "Reset scale 0.0 restores exact base position");

  // 5. Rotation preservation:
  // Add rotated instance (90 deg around X) and assert orientation is preserved through explosion
  const s2 = Math.SQRT1_2;
  const instRot = assembly.addInstance({
    instance_name: "InstRot",
    part_number: "PartA",
    placement_status: "placed",
    transform: [5, 5, 5, s2, s2, 0, 0],
  });

  const qInitial = new THREE.Quaternion();
  instRot.matrix.decompose(new THREE.Vector3(), qInitial, new THREE.Vector3());

  assembly.setExplodedScale(1.8);
  const qExploded = new THREE.Quaternion();
  instRot.matrix.decompose(new THREE.Vector3(), qExploded, new THREE.Vector3());

  assertClose(Math.abs(qInitial.dot(qExploded)), 1.0, "Rotation quaternion strictly preserved during explosion");

  console.log("  ✓ Exploded View displacement math and non-accumulation verified");
}

// --- Test 6: Scene Graph Hierarchy, AssemblyRoot & userData --------------------

{
  console.log("  Testing Scene Graph Hierarchy, AssemblyRoot, and userData Tagging...");

  const parentScene = new THREE.Scene();
  const assembly = new AssemblyScene(parentScene);

  // 1. AssemblyRoot node verification
  assert(assembly.root instanceof THREE.Group, "assembly.root is THREE.Group");
  assert.equal(assembly.root.name, "AssemblyRoot", "assembly.root name == 'AssemblyRoot'");
  assert.equal(parentScene.children.includes(assembly.root), true, "AssemblyRoot added to parent Scene");

  // Basis orientation matrix R_X(-pi/2) pinned
  assertMatrixClose(assembly.root.matrix, createBasisMatrix(), "AssemblyRoot has B = R_X(-pi/2) matrix");

  // 2. Add an instance and inspect userData
  const geom = buildBufferGeometry([0, 0, 0, 1, 0, 0, 0, 1, 0], [0, 1, 2]);
  assembly.registerGeometry("Part001", geom);

  const instNode = assembly.addInstance({
    instance_name: "Part001.1",
    part_number: "Part001",
    placement_status: "placed",
    transform: [10, 20, 30, 1, 0, 0, 0],
    pairing_rule: "triple",
    has_position_attr: true,
  });

  assert(assembly.root.children.includes(instNode), "Instance added to AssemblyRoot children");
  assert.equal(instNode.name, "Part001.1", "Instance node named correctly");

  const ud = instNode.userData;
  assert.equal(ud.instanceName, "Part001.1", "userData.instanceName");
  assert.equal(ud.partNumber, "Part001", "userData.partNumber");
  assert.equal(ud.placementStatus, "placed", "userData.placementStatus");
  assert(ud.originalMatrix instanceof THREE.Matrix4, "userData.originalMatrix is Matrix4");
  assert(ud.currentMatrix instanceof THREE.Matrix4, "userData.currentMatrix is Matrix4");
  assert(ud.catiaMatrix instanceof THREE.Matrix4, "userData.catiaMatrix is Matrix4");
  assert(ud.threeMatrix instanceof THREE.Matrix4, "userData.threeMatrix is Matrix4");
  assert.deepEqual(ud.transform, [10, 20, 30, 1, 0, 0, 0], "userData.transform matches input");

  console.log("  ✓ Scene Graph Hierarchy and userData tagging verified");
}

// --- Test 7: Bounding Box, Bounding Sphere & Camera Framing -------------------

{
  console.log("  Testing Aggregate Bounding Box, Bounding Sphere & Camera Framing...");

  const assembly = new AssemblyScene(null);
  // Triangle with extent [0, 0, 0] to [10, 10, 10]
  const geom = buildBufferGeometry([0, 0, 0, 10, 0, 0, 0, 10, 10], [0, 1, 2]);
  assembly.registerGeometry("BoxPart", geom);

  assembly.addInstance({
    instance_name: "Box.1",
    part_number: "BoxPart",
    placement_status: "placed",
    transform: [0, 0, 0, 1, 0, 0, 0],
  });
  assembly.addInstance({
    instance_name: "Box.2",
    part_number: "BoxPart",
    placement_status: "placed",
    transform: [100, 0, 0, 1, 0, 0, 0],
  });

  // Local CATIA bounding box spans X: [0, 110], Y: [0, 10], Z: [0, 10]
  const catiaBox = assembly.computeBoundingBox("catia");
  assertClose(catiaBox.min.x, 0, "catiaBox min.x");
  assertClose(catiaBox.max.x, 110, "catiaBox max.x");

  // World bounding sphere
  const sphere = assembly.computeBoundingSphere("world");
  assert(Number.isFinite(sphere.radius), "World sphere radius is finite");
  assert(sphere.radius > 50.0, "World sphere radius > 50");

  // Auto-framing mock orbit
  let framedCenter = null;
  let framedRadius = null;
  const mockOrbit = {
    frame(center, radius) {
      framedCenter = center.clone();
      framedRadius = radius;
    },
  };

  assembly.frameCamera(mockOrbit);
  assert(framedCenter !== null, "orbit.frame was invoked");
  assertVector3Close(framedCenter, sphere.center, "framedCenter matches sphere center");
  assertClose(framedRadius, sphere.radius, "framedRadius matches sphere radius");

  console.log("  ✓ Aggregate Bounding Box, Bounding Sphere & Camera Framing verified");
}

// --- Test 8: Visibility & Isolation Controls ----------------------------------

{
  console.log("  Testing Visibility Toggles & Instance Isolation...");

  const assembly = new AssemblyScene(null);
  const geom = buildBufferGeometry([0, 0, 0, 1, 0, 0, 0, 1, 0], [0, 1, 2]);
  assembly.registerGeometry("P", geom);

  assembly.addInstance({ instance_name: "InstA", part_number: "P", placement_status: "placed", transform: [0, 0, 0, 1, 0, 0, 0] });
  assembly.addInstance({ instance_name: "InstB", part_number: "P", placement_status: "placed", transform: [10, 0, 0, 1, 0, 0, 0] });
  assembly.addInstance({ instance_name: "InstC", part_number: "P", placement_status: "placed", transform: [20, 0, 0, 1, 0, 0, 0] });

  // 1. Toggle visibility of single instance
  assert.equal(assembly.getInstanceVisibility("InstA"), true);
  assembly.setInstanceVisibility("InstA", false);
  assert.equal(assembly.getInstanceVisibility("InstA"), false);
  assembly.toggleInstanceVisibility("InstA");
  assert.equal(assembly.getInstanceVisibility("InstA"), true);

  // 2. Isolate instance
  assembly.isolateInstance("InstB");
  assert.equal(assembly.getInstanceVisibility("InstA"), false, "InstA hidden during isolation");
  assert.equal(assembly.getInstanceVisibility("InstB"), true, "InstB visible during isolation");
  assert.equal(assembly.getInstanceVisibility("InstC"), false, "InstC hidden during isolation");

  // 3. Clear isolation
  assembly.clearIsolation();
  assert.equal(assembly.getInstanceVisibility("InstA"), true, "InstA restored after isolation");
  assert.equal(assembly.getInstanceVisibility("InstB"), true, "InstB restored after isolation");
  assert.equal(assembly.getInstanceVisibility("InstC"), true, "InstC restored after isolation");

  // 4. Toggle isolation on same instance
  assembly.isolateInstance("InstB");
  assert.equal(assembly.getInstanceVisibility("InstA"), false);
  assembly.isolateInstance("InstB"); // Calling again clears isolation
  assert.equal(assembly.getInstanceVisibility("InstA"), true, "Second isolate call toggles/clears isolation");

  console.log("  ✓ Visibility Toggles & Instance Isolation verified");
}

// --- Test 9: Anti-Masking Invariant & 4-State Classification -------------------

{
  console.log("  Testing Anti-Masking Invariant (Clause 3 of P4 Assembly Bar)...");

  const assembly = new AssemblyScene(null);
  const geom = buildBufferGeometry([0, 0, 0, 1, 0, 0, 0, 1, 0], [0, 1, 2]);
  assembly.registerGeometry("ValidPart", geom);

  // Placed instance
  const instPlaced = assembly.addInstance({
    instance_name: "Valid.1",
    part_number: "ValidPart",
    placement_status: STATUS_PLACED,
    transform: [10, 20, 30, 1, 0, 0, 0],
  });
  assert.equal(instPlaced.userData.placementStatus, STATUS_PLACED);
  assert.equal(instPlaced.visible, true);
  assert.equal(instPlaced.userData.isPlacedSpatial, true);

  // Identity instance
  const instIdent = assembly.addInstance({
    instance_name: "Valid.2",
    part_number: "ValidPart",
    placement_status: STATUS_IDENTITY,
  });
  assert.equal(instIdent.userData.placementStatus, STATUS_IDENTITY);
  assert.equal(instIdent.visible, true);
  assert.equal(instIdent.userData.isPlacedSpatial, true);

  // Unresolved instance (missing CATPart file)
  const instUnres = assembly.addInstance({
    instance_name: "Missing.1",
    part_number: "MissingPart",
    placement_status: STATUS_UNRESOLVED,
  });
  assert.equal(instUnres.userData.placementStatus, STATUS_UNRESOLVED);
  assert.equal(instUnres.visible, false);
  assert.equal(instUnres.userData.isPlacedSpatial, false);

  // Undecodable instance: MUST NEVER be defaulted to origin identity!
  const instUndec = assembly.addInstance({
    instance_name: "Undecodable.1",
    part_number: "ValidPart",
    placement_status: STATUS_UNDECODABLE,
    has_position_attr: true,
  });
  assert.equal(instUndec.userData.placementStatus, STATUS_UNDECODABLE);
  // Anti-masking rule: undecodable instance is NOT rendered as valid spatial instance
  assert.equal(instUndec.visible, false, "Undecodable instance is hidden from 3D scene (never masked)");
  assert.equal(instUndec.userData.isPlacedSpatial, false, "isPlacedSpatial is false");

  // Verify that undecodable instances do NOT contaminate aggregate bounding box or centroid
  const placedList = assembly.getPlacedInstances();
  assert.equal(placedList.length, 2, "Only 2 instances are placed spatial (Valid.1 and Valid.2)");
  assert(!placedList.includes(instUndec), "Undecodable instance excluded from placed instances");

  console.log("  ✓ Anti-Masking Invariant (Clause 3 of P4 Bar) strictly enforced");
}

// --- Test 10: Transform Inspector & Single-Instance Framing -------------------

{
  console.log("  Testing Transform Inspector Details & Single-Instance Framing...");

  const assembly = new AssemblyScene(null);
  const geom = buildBufferGeometry([0, 0, 0, 5, 0, 0, 0, 5, 5], [0, 1, 2]);
  assembly.registerGeometry("PartX", geom);

  // 90 deg around X: qw = sqrt(2)/2, qx = sqrt(2)/2
  const s2 = Math.SQRT1_2;
  assembly.addInstance({
    instance_name: "PartX.1",
    part_number: "PartX",
    placement_status: STATUS_PLACED,
    transform: [12.5, -45.0, 78.2, s2, s2, 0, 0],
    pairing_rule: "bare_pair",
    has_position_attr: true,
  });

  const info = assembly.getInstanceTransformInfo("PartX.1");
  assert(info !== null, "info retrieved");
  assert.equal(info.instanceName, "PartX.1");
  assert.equal(info.partNumber, "PartX");
  assert.equal(info.pairingRule, "bare_pair");
  assert.equal(info.hasPositionAttr, true);
  assertClose(info.translation[0], 12.5);
  assertClose(info.translation[1], -45.0);
  assertClose(info.translation[2], 78.2);

  // Euler angles: 90 deg around X -> x ~ 90, y ~ 0, z ~ 0
  assertClose(info.eulerDeg.x, 90.0, "Euler X degrees");
  assertClose(info.eulerDeg.y, 0.0, "Euler Y degrees");
  assertClose(info.eulerDeg.z, 0.0, "Euler Z degrees");

  // Axis/angle: axis should be [1, 0, 0], angle ~ 90 deg
  assertClose(info.axis[0], 1.0, "Rotation axis X");
  assertClose(info.axis[1], 0.0, "Rotation axis Y");
  assertClose(info.axis[2], 0.0, "Rotation axis Z");
  assertClose(info.angleDeg, 90.0, "Rotation angle degrees");

  // Test frameInstance
  let framedInstCenter = null;
  let framedInstRadius = null;
  const mockOrbit = {
    frame(center, radius) {
      framedInstCenter = center.clone();
      framedInstRadius = radius;
    },
  };

  const sphere = assembly.frameInstance("PartX.1", mockOrbit);
  assert(sphere !== null, "frameInstance returned sphere");
  assert(framedInstCenter !== null, "orbit.frame called");
  assert(framedInstRadius > 0, "framedInstRadius > 0");

  console.log("  ✓ Transform Inspector Details & Single-Instance Framing verified");
}

console.log("\nAll 10/10 Assembly Scene Graph & Placement tests passed successfully!");
