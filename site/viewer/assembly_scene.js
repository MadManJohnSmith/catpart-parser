/* 3D Spatial Assembly Placement & WebGL Scene Graph Engine (Phase 6, Ticket P3-V4)
   Design Authority: docs/specs/phase6-assembly-viewer-spec.md §5 and §8
   Prior Art: site/viewer/catalog.js, site/viewer/ingest.js, site/viewer/viewer.js

   Implements:
   1. Coordinate transformation B = R_X(-pi/2) mapping CATIA Z-up coordinates to Three.js Y-up.
   2. Unit-quaternion and translation matrix composition M_CATIA = T(t) * R(q).
   3. Geometry pooling and GPU buffer sharing across repeated component instances.
   4. Hierarchical AssemblyRoot scene-graph management with tagged instance userData.
   5. Interactive assembly features: exploded view slider, aggregate bounding sphere, auto-framing,
      instance visibility toggle, and instance isolation.
   6. Anti-masking enforcement: undecodable placements are never defaulted to identity.

   Pure ES module style with zero external dependencies beyond Three.js.
*/

import * as THREE from "./three.module.min.js";

// --- Classification Status Constants (Spec §3.2 & §6.2) -----------------------

export const STATUS_PLACED = "placed";
export const STATUS_IDENTITY = "identity";
export const STATUS_UNRESOLVED = "unresolved";
export const STATUS_UNDECODABLE = "undecodable";

// Canonical pairing rules (Spec §2)
export const PAIRING_RULE_TRIPLE = "triple";
export const PAIRING_RULE_DESC_BLOCK = "desc_block";
export const PAIRING_RULE_BARE_PAIR = "bare_pair";

// Rotation angle for basis transformation: -90 degrees (-pi / 2 radians)
export const BASIS_ROTATION_X = -Math.PI / 2;

// --- 1. Coordinate Basis Transformation (B = R_X(-pi/2)) ----------------------

/**
 * Creates the 4x4 change-of-basis matrix B = R_X(-pi/2) mapping CATIA right-handed Z-up
 * coordinates (+X right, +Y forward/in-depth, +Z up) to Three.js right-handed Y-up
 * coordinates (+X right, +Y up, +Z out of screen/south).
 *
 * Geometric mapping:
 *   (x_C, y_C, z_C) -> (x_C, z_C, -y_C)
 *
 * Matrix in standard row-major form:
 *   [ 1,  0, 0, 0 ]
 *   [ 0,  0, 1, 0 ]
 *   [ 0, -1, 0, 0 ]
 *   [ 0,  0, 0, 1 ]
 *
 * Stored with exact integer elements to eliminate minute trigonometric float fuzz.
 *
 * @returns {THREE.Matrix4}
 */
export function createBasisMatrix() {
  return new THREE.Matrix4().set(
    1, 0, 0, 0,
    0, 0, 1, 0,
    0, -1, 0, 0,
    0, 0, 0, 1
  );
}

/**
 * Creates the inverse change-of-basis matrix B^{-1} = R_X(+pi/2) = B^T mapping Three.js
 * Y-up coordinates back to CATIA Z-up coordinates.
 *
 * Geometric mapping:
 *   (x_T, y_T, z_T) -> (x_T, -z_T, y_T)
 *
 * @returns {THREE.Matrix4}
 */
export function createBasisInverseMatrix() {
  return new THREE.Matrix4().set(
    1, 0, -0, 0,
    0, 0, -1, 0,
    0, 1, 0, 0,
    0, 0, 0, 1
  );
}

/**
 * Transforms a 3D coordinate from CATIA space to Three.js space using basis matrix B.
 *
 * @param {THREE.Vector3|number[]} p
 * @param {THREE.Matrix4} [B]
 * @returns {THREE.Vector3}
 */
export function transformPointBasis(p, B = null) {
  const basis = B || createBasisMatrix();
  const v = Array.isArray(p)
    ? new THREE.Vector3(p[0], p[1], p[2])
    : p.clone();
  return v.applyMatrix4(basis);
}

// --- 2. Transform Composition & Quaternion Pipeline ---------------------------

/**
 * Composes a local CATIA 4x4 transform matrix from the 7-tuple:
 *   [tx, ty, tz, qw, qx, qy, qz]
 *
 * CATIA stores unit quaternions with the scalar part qw first (P2.5 §4).
 * Three.js THREE.Quaternion constructor takes arguments in (x, y, z, w) order.
 *
 * @param {number[]} transform - 7-tuple [tx, ty, tz, qw, qx, qy, qz]
 * @returns {THREE.Matrix4} - M_CATIA = T(t) * R(q)
 */
export function composeCatiaMatrix(transform) {
  if (!transform || !Array.isArray(transform) || transform.length < 7) {
    return new THREE.Matrix4().identity();
  }

  const tx = Number(transform[0]);
  const ty = Number(transform[1]);
  const tz = Number(transform[2]);
  const qw = Number(transform[3]);
  const qx = Number(transform[4]);
  const qy = Number(transform[5]);
  const qz = Number(transform[6]);

  // Three.js takes (x, y, z, w)
  const quat = new THREE.Quaternion(qx, qy, qz, qw);
  // Normalize to guard against minute floating-point rounding
  if (quat.lengthSq() > 0) {
    quat.normalize();
  } else {
    quat.set(0, 0, 0, 1);
  }

  const pos = new THREE.Vector3(tx, ty, tz);
  const scale = new THREE.Vector3(1.0, 1.0, 1.0);

  return new THREE.Matrix4().compose(pos, quat, scale);
}

/**
 * Converts a CATIA local matrix into Three.js basis:
 *   M_Three = B * M_CATIA * B^{-1}
 *
 * @param {THREE.Matrix4} mCatia
 * @param {THREE.Matrix4} [B]
 * @param {THREE.Matrix4} [B_inv]
 * @returns {THREE.Matrix4}
 */
export function catiaToThreeMatrix(mCatia, B = null, B_inv = null) {
  const basis = B || createBasisMatrix();
  const basisInv = B_inv || createBasisInverseMatrix();
  return new THREE.Matrix4().multiplyMatrices(basis, mCatia).multiply(basisInv);
}

/**
 * Directly composes a Three.js-basis matrix from a CATIA 7-tuple:
 *   [tx, ty, tz, qw, qx, qy, qz]
 *
 * @param {number[]} transform
 * @returns {THREE.Matrix4}
 */
export function composeThreeMatrix(transform) {
  const mCatia = composeCatiaMatrix(transform);
  return catiaToThreeMatrix(mCatia);
}

/**
 * Decomposes a Matrix4 into [tx, ty, tz, qw, qx, qy, qz] (w-first quaternion).
 *
 * @param {THREE.Matrix4} matrix
 * @returns {number[]} 7-tuple
 */
export function decomposeTransform(matrix) {
  const pos = new THREE.Vector3();
  const quat = new THREE.Quaternion();
  const scale = new THREE.Vector3();
  matrix.decompose(pos, quat, scale);
  return [pos.x, pos.y, pos.z, quat.w, quat.x, quat.y, quat.z];
}

/**
 * Computes Euler angles in degrees (XYZ order) from a unit quaternion.
 *
 * @param {THREE.Quaternion|number[]} quat - Quaternion object or [qw, qx, qy, qz]
 * @returns {{ x: number, y: number, z: number }} Degrees
 */
export function computeEulerDegrees(quat) {
  const q = quat instanceof THREE.Quaternion
    ? quat
    : new THREE.Quaternion(quat[1], quat[2], quat[3], quat[0]);
  const euler = new THREE.Euler().setFromQuaternion(q, "XYZ");
  return {
    x: (euler.x * 180) / Math.PI,
    y: (euler.y * 180) / Math.PI,
    z: (euler.z * 180) / Math.PI,
  };
}

/**
 * Computes rotation axis and angle (degrees) from a unit quaternion.
 *
 * @param {THREE.Quaternion|number[]} quat - Quaternion object or [qw, qx, qy, qz]
 * @returns {{ axis: THREE.Vector3, angleDeg: number, angleRad: number }}
 */
export function computeAxisAngle(quat) {
  const q = quat instanceof THREE.Quaternion
    ? quat
    : new THREE.Quaternion(quat[1], quat[2], quat[3], quat[0]);
  const wClamped = Math.min(Math.max(q.w, -1.0), 1.0);
  const angleRad = 2.0 * Math.acos(wClamped);
  const s = Math.sqrt(Math.max(0.0, 1.0 - wClamped * wClamped));
  const axis = new THREE.Vector3();
  if (s < 1e-6) {
    axis.set(1.0, 0.0, 0.0);
  } else {
    axis.set(q.x / s, q.y / s, q.z / s);
  }
  return {
    axis,
    angleRad,
    angleDeg: (angleRad * 180) / Math.PI,
  };
}

/**
 * Normalizes a PartNumber string for caching and lookup:
 * - Trims whitespace
 * - Strips file extensions if passed as filename (.CATPart / .catpart)
 *
 * @param {string} partNumber
 * @returns {string}
 */
export function normalizePartNumber(partNumber) {
  if (!partNumber || typeof partNumber !== "string") return "";
  let s = partNumber.trim();
  const lower = s.toLowerCase();
  if (lower.endsWith(".catpart")) {
    s = s.slice(0, -8);
  } else if (lower.endsWith(".catproduct")) {
    s = s.slice(0, -11);
  }
  return s;
}

// --- 3. Geometry Pooling & GPU Buffer Sharing ----------------------------------

/**
 * Manages unique THREE.BufferGeometry allocations and GPU memory lifecycle.
 * Ensures component geometries (e.g. repeated bolts, brackets) are decoded and
 * uploaded to GPU memory exactly once.
 */
export class GeometryPool {
  constructor() {
    /** @type {Map<string, { geometry: THREE.BufferGeometry, curves?: THREE.Group|null, summary?: any, material?: THREE.Material|null, canonicalName: string }>} */
    this.entries = new Map();
    /** @type {Map<string, string>} lowercase -> canonical */
    this.caseIndex = new Map();
  }

  /**
   * Number of unique BufferGeometry allocations stored.
   * @returns {number}
   */
  get size() {
    return this.entries.size;
  }

  /**
   * Alias for size to verify memory footprint contract.
   * @returns {number}
   */
  get uniqueGeometryCount() {
    return this.entries.size;
  }

  /**
   * Checks whether geometry for the given PartNumber is already cached.
   *
   * @param {string} partNumber
   * @returns {boolean}
   */
  has(partNumber) {
    const norm = normalizePartNumber(partNumber);
    if (this.entries.has(norm)) return true;
    return this.caseIndex.has(norm.toLowerCase());
  }

  /**
   * Retrieves the cached geometry pool entry by PartNumber.
   *
   * @param {string} partNumber
   * @returns {{ geometry: THREE.BufferGeometry, curves?: THREE.Group|null, summary?: any, material?: THREE.Material|null }|null}
   */
  get(partNumber) {
    const norm = normalizePartNumber(partNumber);
    const direct = this.entries.get(norm);
    if (direct) return direct;
    const canonical = this.caseIndex.get(norm.toLowerCase());
    return canonical ? this.entries.get(canonical) || null : null;
  }

  /**
   * Stores a decoded geometry in the pool.
   *
   * @param {string} partNumber
   * @param {Object} entry
   * @param {THREE.BufferGeometry} entry.geometry
   * @param {THREE.Group} [entry.curves]
   * @param {any} [entry.summary]
   * @param {THREE.Material} [entry.material]
   * @returns {this}
   */
  set(partNumber, { geometry, curves = null, summary = null, material = null }) {
    if (!geometry) {
      throw new Error(`Cannot register null geometry for PartNumber "${partNumber}"`);
    }
    const norm = normalizePartNumber(partNumber);
    const item = {
      geometry,
      curves,
      summary,
      material,
      canonicalName: norm,
    };
    this.entries.set(norm, item);
    this.caseIndex.set(norm.toLowerCase(), norm);
    return this;
  }

  /**
   * Retrieves an existing geometry or decodes/creates it via the factory callback.
   *
   * @param {string} partNumber
   * @param {() => { geometry: THREE.BufferGeometry, curves?: THREE.Group, summary?: any, material?: THREE.Material }} factoryFn
   * @returns {{ geometry: THREE.BufferGeometry, curves?: THREE.Group, summary?: any, material?: THREE.Material }}
   */
  getOrCreate(partNumber, factoryFn) {
    const existing = this.get(partNumber);
    if (existing) return existing;
    const created = factoryFn();
    this.set(partNumber, created);
    return created;
  }

  /**
   * Returns list of canonical part numbers stored in pool.
   * @returns {string[]}
   */
  getPartNumbers() {
    return Array.from(this.entries.keys());
  }

  /**
   * Enforces full GPU resource disposal lifecycle:
   * disposes all BufferGeometry, Material, and curve buffers, then clears the pool.
   */
  dispose() {
    for (const entry of this.entries.values()) {
      if (entry.geometry && typeof entry.geometry.dispose === "function") {
        entry.geometry.dispose();
      }
      if (entry.material && typeof entry.material.dispose === "function") {
        entry.material.dispose();
      }
      if (entry.curves && typeof entry.curves.traverse === "function") {
        entry.curves.traverse((child) => {
          if (child.geometry && typeof child.geometry.dispose === "function") {
            child.geometry.dispose();
          }
          if (child.material && typeof child.material.dispose === "function") {
            child.material.dispose();
          }
        });
      }
    }
    this.entries.clear();
    this.caseIndex.clear();
  }
}

// --- 4. BufferGeometry and Curve Builder Utilities ----------------------------

/**
 * Builds a THREE.BufferGeometry from decoded vertex coordinates and triangle indices.
 * Computes vertex normals automatically.
 *
 * @param {Float32Array|number[]} vertices
 * @param {Uint32Array|number[]} triangles
 * @returns {THREE.BufferGeometry}
 */
export function buildBufferGeometry(vertices, triangles) {
  const geometry = new THREE.BufferGeometry();
  const vAttr = vertices instanceof Float32Array
    ? new THREE.BufferAttribute(vertices, 3)
    : new THREE.BufferAttribute(new Float32Array(vertices), 3);
  const iAttr = triangles instanceof Uint32Array
    ? new THREE.BufferAttribute(triangles, 1)
    : new THREE.BufferAttribute(new Uint32Array(triangles), 1);

  geometry.setAttribute("position", vAttr);
  geometry.setIndex(iAttr);
  geometry.computeVertexNormals();
  geometry.computeBoundingBox();
  geometry.computeBoundingSphere();
  return geometry;
}

/**
 * Builds a THREE.Group of line loops from decoded curve polyline arrays.
 *
 * @param {Array<Float32Array|number[]>} curves
 * @param {THREE.Material} [material]
 * @returns {THREE.Group}
 */
export function buildCurvesGroup(curves, material = null) {
  const group = new THREE.Group();
  group.name = "CurvesGroup";
  if (!curves || !Array.isArray(curves) || curves.length === 0) {
    return group;
  }

  const mat = material || new THREE.LineBasicMaterial({ color: 0x38e1ff });
  for (const loop of curves) {
    if (!loop || loop.length < 6) continue;
    const geom = new THREE.BufferGeometry();
    const pos = loop instanceof Float32Array
      ? new THREE.BufferAttribute(loop, 3)
      : new THREE.BufferAttribute(new Float32Array(loop), 3);
    geom.setAttribute("position", pos);
    group.add(new THREE.Line(geom, mat.clone()));
  }
  return group;
}

/**
 * Creates default Three.js standard material for assembly mesh rendering.
 *
 * @param {Object} [overrides]
 * @returns {THREE.MeshStandardMaterial}
 */
export function createDefaultAssemblyMaterial(overrides = {}) {
  return new THREE.MeshStandardMaterial({
    color: 0x8fb8d8,
    metalness: 0.1,
    roughness: 0.65,
    side: THREE.DoubleSide,
    ...overrides,
  });
}

// --- 5. Centroid & Exploded View Math ------------------------------------------

/**
 * Computes the aggregate centroid of all placed instances.
 *
 * @param {THREE.Object3D[]|Map<string, THREE.Object3D>} instances
 * @param {"positions"|"bounding_box"} [type="positions"]
 * @returns {THREE.Vector3}
 */
export function computeAssemblyCentroid(instances, type = "positions") {
  const list = instances instanceof Map
    ? Array.from(instances.values())
    : Array.from(instances || []);

  const placed = list.filter((inst) => {
    const status = inst.userData && inst.userData.placementStatus;
    return status === STATUS_PLACED || status === STATUS_IDENTITY;
  });

  if (placed.length === 0) {
    return new THREE.Vector3(0, 0, 0);
  }

  if (type === "bounding_box") {
    const box = new THREE.Box3();
    let hasValidBox = false;
    for (const inst of placed) {
      const instBox = new THREE.Box3();
      inst.traverse((child) => {
        if (child.isMesh && child.geometry) {
          if (!child.geometry.boundingBox) child.geometry.computeBoundingBox();
          if (child.geometry.boundingBox) {
            instBox.union(child.geometry.boundingBox);
          }
        }
      });
      if (!instBox.isEmpty()) {
        instBox.applyMatrix4(inst.matrix);
        box.union(instBox);
        hasValidBox = true;
      }
    }
    if (hasValidBox && !box.isEmpty()) {
      const center = new THREE.Vector3();
      box.getCenter(center);
      return center;
    }
  }

  // Default: average of instance base positions
  const centroid = new THREE.Vector3(0, 0, 0);
  for (const inst of placed) {
    const basePos = (inst.userData && inst.userData.basePosition)
      ? inst.userData.basePosition
      : new THREE.Vector3().setFromMatrixPosition(inst.matrix);
    centroid.add(basePos);
  }
  centroid.divideScalar(placed.length);
  return centroid;
}

/**
 * Calculates exploded translation for an instance given aggregate centroid and slider scale lambda.
 *
 * Formula (§5.4):
 *   d_i = pos_i - centroid
 *   pos_i(lambda) = pos_i + lambda * d_i
 *
 * If ||d_i|| < 1e-6 (instance at centroid), falls back to default upward displacement.
 *
 * @param {THREE.Vector3} basePos
 * @param {THREE.Vector3} centroid
 * @param {number} scale - Lambda >= 0
 * @param {Object} [options]
 * @param {boolean} [options.normalized=false]
 * @param {number} [options.scaleFactor]
 * @returns {THREE.Vector3}
 */
export function computeExplodedPosition(basePos, centroid, scale, options = {}) {
  const d = basePos.clone().sub(centroid);
  const lenSq = d.lengthSq();

  if (lenSq < 1e-12) {
    // Instance placed at exact centroid: fallback direction along +Z in CATIA coordinates
    d.set(0, 0, 1.0);
  }

  if (options.normalized) {
    d.normalize();
    const factor = typeof options.scaleFactor === "number" ? options.scaleFactor : 10.0;
    return basePos.clone().addScaledVector(d, scale * factor);
  }

  // Linear outward translation along d_i
  return basePos.clone().addScaledVector(d, scale);
}

// --- 6. Scene Graph Engine (AssemblyScene & AssemblyRoot) ----------------------

/**
 * The 3D Spatial Assembly Placement & WebGL Scene Graph Engine.
 *
 * Architecture:
 *   Three.Scene (Default Y-up world)
 *     └── AssemblyRoot (THREE.Group: rotation.x = -Math.PI / 2, matrix = B)
 *           ├── Instance_1 (THREE.Group: local matrix in CATIA coords)
 *           │     └── Mesh (shared BufferGeometry A)
 *           ├── Instance_2 (THREE.Group: local matrix in CATIA coords)
 *           │     └── Mesh (shared BufferGeometry B)
 *           └── Instance_3 (THREE.Group: local matrix in CATIA coords)
 *                 └── Mesh (shared BufferGeometry A)  <-- Reuses Geometry A!
 */
export class AssemblyScene {
  /**
   * @param {THREE.Scene|null} [scene=null] - The parent Three.js scene (or null for headless tests)
   * @param {Object} [options={}]
   * @param {THREE.Material} [options.defaultMaterial]
   * @param {boolean} [options.applyRootBasis=true] - Whether to apply R_X(-pi/2) basis rotation to AssemblyRoot
   */
  constructor(scene = null, options = {}) {
    this.scene = scene;
    this.options = options;

    this.basisMatrix = createBasisMatrix();
    this.basisInverseMatrix = createBasisInverseMatrix();

    // Top-level AssemblyRoot node
    this.root = new THREE.Group();
    this.root.name = "AssemblyRoot";

    const applyBasis = options.applyRootBasis !== false;
    if (applyBasis) {
      // Pin AssemblyRoot orientation to B = R_X(-pi/2)
      this.root.rotation.x = BASIS_ROTATION_X;
      this.root.matrix.copy(this.basisMatrix);
      this.root.matrixAutoUpdate = false;
    }

    if (this.scene) {
      this.scene.add(this.root);
    }

    /** @type {GeometryPool} */
    this.geometryPool = new GeometryPool();

    /** @type {Map<string, THREE.Group>} instanceName -> instanceNode */
    this.instances = new Map();

    /** @type {number} Current exploded scale lambda */
    this.explodedScale = 0.0;

    /** @type {THREE.Vector3} Aggregate centroid of placed instances */
    this.assemblyCentroid = new THREE.Vector3(0, 0, 0);

    /** @type {THREE.Box3} Aggregate bounding box in CATIA coordinates */
    this.catiaBoundingBox = new THREE.Box3();

    /** @type {THREE.Box3} Aggregate bounding box in Three.js world coordinates */
    this.worldBoundingBox = new THREE.Box3();

    /** @type {THREE.Sphere} Aggregate bounding sphere in world coordinates */
    this.worldBoundingSphere = new THREE.Sphere();

    /** @type {THREE.Material} */
    this.defaultMaterial = options.defaultMaterial || createDefaultAssemblyMaterial();

    /** @type {string|null} ID of currently isolated instance */
    this.isolatedInstanceId = null;

    /** @type {boolean} Global wireframe state */
    this.wireframe = false;

    /** @type {boolean} Global curves visibility state */
    this.curvesVisible = false;
  }

  /**
   * Total number of registered instances.
   * @returns {number}
   */
  get totalInstances() {
    return this.instances.size;
  }

  /**
   * Total unique BufferGeometry allocations cached in the pool.
   * @returns {number}
   */
  get uniqueGeometryCount() {
    return this.geometryPool.uniqueGeometryCount;
  }

  /**
   * Registers a decoded part geometry in the geometry pool.
   *
   * @param {string} partNumber
   * @param {THREE.BufferGeometry} geometry
   * @param {THREE.Group|null} [curves=null]
   * @param {any} [summary=null]
   * @param {THREE.Material|null} [material=null]
   * @returns {this}
   */
  registerGeometry(partNumber, geometry, curves = null, summary = null, material = null) {
    this.geometryPool.set(partNumber, {
      geometry,
      curves,
      summary,
      material: material || this.defaultMaterial,
    });
    return this;
  }

  /**
   * Adds an instance to the assembly scene graph.
   *
   * @param {Object} record
   * @param {string} record.instance_name - Unique instance name (e.g. "Part001.1", "ac1:1")
   * @param {string} record.part_number - Component part number (e.g. "Part001", "Bolt_M8")
   * @param {string} [record.placement_status="placed"] - "placed" | "identity" | "unresolved" | "undecodable"
   * @param {number[]|null} [record.transform=null] - 7-tuple [tx, ty, tz, qw, qx, qy, qz]
   * @param {string} [record.pairing_rule]
   * @param {boolean} [record.has_position_attr]
   * @param {string} [record.classification_detail]
   * @param {Object} [options={}]
   * @param {THREE.BufferGeometry} [options.geometry] - Explicit geometry override
   * @param {THREE.Material} [options.material] - Explicit material override
   * @param {THREE.Group} [options.curves] - Explicit curves override
   * @returns {THREE.Group} - The created instance scene-graph node
   */
  addInstance(record, options = {}) {
    if (!record || !record.instance_name) {
      throw new Error("Cannot add instance: record must contain instance_name");
    }

    const instanceName = String(record.instance_name);
    const partNumber = String(record.part_number || "");
    const placementStatus = String(record.placement_status || STATUS_PLACED).toLowerCase();

    // 1. Resolve geometry from options or geometry pool
    let geomEntry = null;
    if (options.geometry) {
      geomEntry = {
        geometry: options.geometry,
        curves: options.curves || null,
        material: options.material || this.defaultMaterial,
      };
    } else if (partNumber && this.geometryPool.has(partNumber)) {
      geomEntry = this.geometryPool.get(partNumber);
    }

    // 2. Compose local transform matrix
    let localMatrix = new THREE.Matrix4();
    let basePos = new THREE.Vector3(0, 0, 0);
    let baseQuat = new THREE.Quaternion(0, 0, 0, 1);
    const baseScale = new THREE.Vector3(1, 1, 1);
    let isPlacedSpatial = false;

    if (placementStatus === STATUS_PLACED && record.transform && record.transform.length >= 7) {
      localMatrix = composeCatiaMatrix(record.transform);
      localMatrix.decompose(basePos, baseQuat, baseScale);
      isPlacedSpatial = true;
    } else if (placementStatus === STATUS_IDENTITY) {
      localMatrix.identity();
      basePos.set(0, 0, 0);
      baseQuat.set(0, 0, 0, 1);
      isPlacedSpatial = true;
    } else {
      // STATUS_UNRESOLVED or STATUS_UNDECODABLE:
      // Invariant: MUST NEVER default an undecodable placement to origin identity.
      // Anti-masking rule (Clause 3 of declared P4 Bar).
      localMatrix.identity();
      isPlacedSpatial = false;
    }

    // 3. Create the instance node in the scene graph
    const instanceGroup = new THREE.Group();
    instanceGroup.name = instanceName;
    instanceGroup.matrixAutoUpdate = false;
    instanceGroup.matrix.copy(localMatrix);
    instanceGroup.matrixWorldNeedsUpdate = true;

    // Attach mesh referencing shared BufferGeometry if resolved
    if (geomEntry && geomEntry.geometry) {
      const mat = options.material || geomEntry.material || this.defaultMaterial;
      const mesh = new THREE.Mesh(geomEntry.geometry, mat);
      mesh.name = `${instanceName}__mesh`;
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      instanceGroup.add(mesh);

      // Attach curve overlay if present
      if (geomEntry.curves) {
        const curvesClone = geomEntry.curves.clone(true);
        curvesClone.name = `${instanceName}__curves`;
        curvesClone.visible = this.curvesVisible;
        instanceGroup.add(curvesClone);
      }
    }

    // Hide undecodable or unresolved instances from spatial rendering
    if (!isPlacedSpatial || placementStatus === STATUS_UNDECODABLE) {
      instanceGroup.visible = false;
    }

    // 4. Tag userData with required contract fields
    const threeMatrix = catiaToThreeMatrix(localMatrix, this.basisMatrix, this.basisInverseMatrix);
    instanceGroup.userData = {
      instanceName,
      partNumber,
      placementStatus,
      originalMatrix: localMatrix.clone(),
      currentMatrix: localMatrix.clone(),
      catiaMatrix: localMatrix.clone(),
      threeMatrix,
      transform: (record.transform && Array.isArray(record.transform)) ? [...record.transform] : null,
      pairingRule: record.pairing_rule || null,
      hasPositionAttr: !!record.has_position_attr,
      classificationDetail: record.classification_detail || null,
      basePosition: basePos.clone(),
      baseQuaternion: baseQuat.clone(),
      baseScale: baseScale.clone(),
      isPlacedSpatial,
    };

    // 5. Add to AssemblyRoot and registry
    this.root.add(instanceGroup);
    this.instances.set(instanceName, instanceGroup);

    // Refresh bounds and centroid
    this._recomputeBoundsAndCentroid();

    return instanceGroup;
  }

  /**
   * Ingests a decoded ProductStructureDocument and associates component .CATPart files
   * from a VirtualFileCatalog.
   *
   * @param {Object} productDoc - Decoded product structure document
   * @param {Object} [catalog=null] - VirtualFileCatalog instance from catalog.js
   * @param {Object} [options={}]
   * @param {(bytes: Uint8Array) => { vertices: Float32Array, triangles: Uint32Array, curves: Float32Array[], summary: any }} [options.decodeExport]
   * @param {any} [options.orbit] - Camera orbit controller to auto-frame
   * @param {boolean} [options.autoFrame=true]
   * @returns {Promise<{ totalInstances: number, placedInstances: number, identityInstances: number, unresolvedInstances: number, undecodableInstances: number, uniqueGeometries: number }>}
   */
  async loadAssembly(productDoc, catalog = null, options = {}) {
    if (!productDoc || !Array.isArray(productDoc.instances)) {
      throw new Error("Invalid product structure: missing instances array");
    }

    // Reset previous assembly state and GPU geometry pool (§5.3)
    this.clear();
    this.geometryPool.dispose();

    const decodeFn = options.decodeExport;

    // 1. Resolve and decode geometries
    for (const record of productDoc.instances) {
      const partNumber = record.part_number;
      if (!partNumber) continue;

      if (!this.geometryPool.has(partNumber) && catalog && typeof catalog.resolvePart === "function") {
        const catEntry = catalog.resolvePart(partNumber);
        if (catEntry && typeof catEntry.getBytes === "function" && decodeFn) {
          try {
            const bytes = await catEntry.getBytes();
            if (bytes && bytes.length > 0) {
              const decoded = decodeFn(bytes);
              if (decoded && decoded.vertices && decoded.triangles) {
                const geometry = buildBufferGeometry(decoded.vertices, decoded.triangles);
                const curves = decoded.curves ? buildCurvesGroup(decoded.curves) : null;
                this.registerGeometry(partNumber, geometry, curves, decoded.summary);
              }
            }
          } catch (err) {
            // Non-fatal part decode failure; logged and marked unresolved
            console.warn(`Failed to decode part "${partNumber}":`, err);
          }
        }
      }
    }

    // 2. Instantiate all declared instances
    for (const record of productDoc.instances) {
      let status = record.placement_status || STATUS_PLACED;
      // If part is not in geometry pool, mark as unresolved
      if (!this.geometryPool.has(record.part_number)) {
        status = STATUS_UNRESOLVED;
      }

      this.addInstance({
        ...record,
        placement_status: status,
      });
    }

    // 3. Compute final bounds and centroid
    this._recomputeBoundsAndCentroid();

    // 4. Auto-frame camera if requested
    if (options.autoFrame !== false && options.orbit) {
      this.frameCamera(options.orbit);
    }

    return {
      totalInstances: this.instances.size,
      placedInstances: this.getInstancesByStatus(STATUS_PLACED).length,
      identityInstances: this.getInstancesByStatus(STATUS_IDENTITY).length,
      unresolvedInstances: this.getInstancesByStatus(STATUS_UNRESOLVED).length,
      undecodableInstances: this.getInstancesByStatus(STATUS_UNDECODABLE).length,
      spatialInstances: this.getPlacedInstances().length,
      uniqueGeometries: this.geometryPool.uniqueGeometryCount,
    };
  }

  /**
   * Recomputes aggregate bounding box and centroid across all placed instances.
   * @private
   */
  _recomputeBoundsAndCentroid() {
    this.catiaBoundingBox.makeEmpty();
    this.worldBoundingBox.makeEmpty();

    const placed = this.getPlacedInstances();
    if (placed.length === 0) {
      this.assemblyCentroid.set(0, 0, 0);
      this.worldBoundingSphere.set(new THREE.Vector3(0, 0, 0), 0);
      return;
    }

    // Compute bounding box in local CATIA coordinates (inside AssemblyRoot)
    for (const inst of placed) {
      const instBox = new THREE.Box3();
      inst.traverse((child) => {
        if (child.isMesh && child.geometry) {
          if (!child.geometry.boundingBox) child.geometry.computeBoundingBox();
          if (child.geometry.boundingBox) {
            instBox.union(child.geometry.boundingBox);
          }
        }
      });
      if (!instBox.isEmpty()) {
        instBox.applyMatrix4(inst.matrix);
        this.catiaBoundingBox.union(instBox);
      }
    }

    // World bounding box (transformed by AssemblyRoot's basis matrix)
    if (!this.catiaBoundingBox.isEmpty()) {
      this.worldBoundingBox.copy(this.catiaBoundingBox).applyMatrix4(this.root.matrix);
      this.worldBoundingBox.getBoundingSphere(this.worldBoundingSphere);
    }

    // Compute centroid of base positions
    this.assemblyCentroid.copy(computeAssemblyCentroid(this.instances, "positions"));
  }

  /**
   * Retrieves an instance node by name.
   * @param {string} instanceName
   * @returns {THREE.Group|null}
   */
  getInstance(instanceName) {
    return this.instances.get(instanceName) || null;
  }

  /**
   * Checks whether an instance is present.
   * @param {string} instanceName
   * @returns {boolean}
   */
  hasInstance(instanceName) {
    return this.instances.has(instanceName);
  }

  /**
   * Returns all instance scene nodes.
   * @returns {THREE.Group[]}
   */
  getAllInstances() {
    return Array.from(this.instances.values());
  }

  /**
   * Returns all placed spatial instances (STATUS_PLACED and STATUS_IDENTITY).
   * @returns {THREE.Group[]}
   */
  getPlacedInstances() {
    return Array.from(this.instances.values()).filter((inst) => {
      const status = inst.userData && inst.userData.placementStatus;
      return (status === STATUS_PLACED || status === STATUS_IDENTITY) && inst.userData.isPlacedSpatial;
    });
  }

  /**
   * Returns instances filtered by placement status.
   * @param {string} status
   * @returns {THREE.Group[]}
   */
  getInstancesByStatus(status) {
    const s = String(status).toLowerCase();
    return Array.from(this.instances.values()).filter(
      (inst) => inst.userData && inst.userData.placementStatus === s
    );
  }

  // --- Interactive Exploded View ---------------------------------------------

  /**
   * Applies an exploded view displacement to all placed instances.
   *
   * @param {number} scale - Lambda >= 0
   * @param {Object} [options={}]
   * @param {THREE.Vector3} [options.centroid]
   * @returns {number} The applied scale
   */
  setExplodedScale(scale, options = {}) {
    const lambda = Math.max(0.0, Number(scale) || 0.0);
    this.explodedScale = lambda;

    const centroid = options.centroid || this.assemblyCentroid;
    const placed = this.getPlacedInstances();

    for (const inst of placed) {
      const userData = inst.userData;
      if (!userData || !userData.basePosition) continue;

      const newPos = computeExplodedPosition(userData.basePosition, centroid, lambda, options);

      // Re-compose matrix with displaced position while strictly preserving orientation and scale
      inst.matrix.compose(newPos, userData.baseQuaternion, userData.baseScale);
      userData.currentMatrix.copy(inst.matrix);
      inst.matrixWorldNeedsUpdate = true;
    }

    return lambda;
  }

  /**
   * Current exploded view scale.
   * @returns {number}
   */
  getExplodedScale() {
    return this.explodedScale;
  }

  // --- Auto-Framing & Bounding Spheres -----------------------------------------

  /**
   * Computes the aggregate bounding box.
   *
   * @param {"catia"|"world"} [space="world"]
   * @returns {THREE.Box3}
   */
  computeBoundingBox(space = "world") {
    this._recomputeBoundsAndCentroid();
    return space === "catia"
      ? this.catiaBoundingBox.clone()
      : this.worldBoundingBox.clone();
  }

  /**
   * Computes the aggregate bounding sphere.
   *
   * @param {"catia"|"world"} [space="world"]
   * @returns {{ center: THREE.Vector3, radius: number, sphere: THREE.Sphere }}
   */
  computeBoundingSphere(space = "world") {
    this._recomputeBoundsAndCentroid();
    if (space === "catia") {
      const sphere = new THREE.Sphere();
      this.catiaBoundingBox.getBoundingSphere(sphere);
      return { center: sphere.center, radius: sphere.radius, sphere };
    }
    return {
      center: this.worldBoundingSphere.center.clone(),
      radius: this.worldBoundingSphere.radius,
      sphere: this.worldBoundingSphere.clone(),
    };
  }

  /**
   * Retrieves or computes the aggregate bounding sphere.
   *
   * @param {"catia"|"world"} [space="world"]
   * @returns {{ center: THREE.Vector3, radius: number, sphere: THREE.Sphere }}
   */
  getBoundingSphere(space = "world") {
    return this.computeBoundingSphere(space);
  }

  /**
   * Frames the camera orbit on the aggregate bounding sphere.
   *
   * @param {any} orbit - Orbit controller with frame(center, radius) method (site/viewer/orbit.js)
   * @param {THREE.Camera} [camera=null]
   * @returns {THREE.Sphere}
   */
  frameCamera(orbit, camera = null) {
    const { center, radius, sphere } = this.computeBoundingSphere("world");
    const safeRadius = Math.max(radius, 1e-4);

    if (orbit && typeof orbit.frame === "function") {
      orbit.frame(center, safeRadius);
    } else if (camera) {
      camera.position.set(center.x, center.y + safeRadius * 1.5, center.z + safeRadius * 2.0);
      camera.lookAt(center);
    }
    return sphere;
  }

  /**
   * Frames the camera orbit on a specific instance's bounding sphere.
   *
   * @param {string} instanceId
   * @param {any} orbit
   * @param {THREE.Camera} [camera=null]
   * @returns {THREE.Sphere|null}
   */
  frameInstance(instanceId, orbit, camera = null) {
    const inst = this.getInstance(instanceId);
    if (!inst) return null;

    const box = new THREE.Box3();
    inst.traverse((child) => {
      if (child.isMesh && child.geometry) {
        if (!child.geometry.boundingBox) child.geometry.computeBoundingBox();
        if (child.geometry.boundingBox) {
          box.union(child.geometry.boundingBox);
        }
      }
    });

    if (box.isEmpty()) return null;

    // Transform by instance local matrix and AssemblyRoot matrix to reach world space
    box.applyMatrix4(inst.matrix).applyMatrix4(this.root.matrix);
    const sphere = new THREE.Sphere();
    box.getBoundingSphere(sphere);
    const safeRadius = Math.max(sphere.radius, 1e-4);

    if (orbit && typeof orbit.frame === "function") {
      orbit.frame(sphere.center, safeRadius);
    } else if (camera) {
      camera.position.set(sphere.center.x, sphere.center.y + safeRadius * 1.5, sphere.center.z + safeRadius * 2.0);
      camera.lookAt(sphere.center);
    }
    return sphere;
  }

  /**
   * Retrieves comprehensive transform inspector details for an instance:
   * raw 7-tuple, translation [tx, ty, tz] in mm, quaternion [qw, qx, qy, qz],
   * computed Euler angles in degrees, and rotation axis/angle.
   *
   * @param {string} instanceId
   * @returns {Object|null}
   */
  getInstanceTransformInfo(instanceId) {
    const inst = this.getInstance(instanceId);
    if (!inst || !inst.userData) return null;

    const ud = inst.userData;
    const basePos = ud.basePosition || new THREE.Vector3();
    const baseQuat = ud.baseQuaternion || new THREE.Quaternion(0, 0, 0, 1);

    const eulerDeg = computeEulerDegrees(baseQuat);
    const { axis, angleDeg, angleRad } = computeAxisAngle(baseQuat);

    return {
      instanceName: ud.instanceName,
      partNumber: ud.partNumber,
      placementStatus: ud.placementStatus,
      pairingRule: ud.pairingRule,
      hasPositionAttr: ud.hasPositionAttr,
      translation: [basePos.x, basePos.y, basePos.z],
      quaternion: [baseQuat.w, baseQuat.x, baseQuat.y, baseQuat.z],
      eulerDeg,
      axis: [axis.x, axis.y, axis.z],
      angleDeg,
      angleRad,
      rawTransform: ud.transform,
      classificationDetail: ud.classificationDetail,
    };
  }

  // --- Visibility & Isolation Controls ----------------------------------------

  /**
   * Sets visibility of an instance by name.
   *
   * @param {string} instanceId
   * @param {boolean} visible
   * @returns {boolean} Whether instance was found
   */
  setInstanceVisibility(instanceId, visible) {
    const inst = this.getInstance(instanceId);
    if (!inst) return false;
    inst.visible = !!visible;
    return true;
  }

  /**
   * Gets visibility of an instance by name.
   *
   * @param {string} instanceId
   * @returns {boolean}
   */
  getInstanceVisibility(instanceId) {
    const inst = this.getInstance(instanceId);
    return inst ? inst.visible : false;
  }

  /**
   * Toggles visibility of an instance.
   *
   * @param {string} instanceId
   * @returns {boolean}
   */
  toggleInstanceVisibility(instanceId) {
    const inst = this.getInstance(instanceId);
    if (!inst) return false;
    inst.visible = !inst.visible;
    return inst.visible;
  }

  /**
   * Isolates an instance: hides all other instances.
   * If instanceId is null or matches current isolation, restores all instances.
   *
   * @param {string|null} instanceId
   * @returns {string|null} The currently isolated instance ID, or null
   */
  isolateInstance(instanceId) {
    if (!instanceId || this.isolatedInstanceId === instanceId) {
      return this.clearIsolation();
    }

    const target = this.getInstance(instanceId);
    if (!target) return null;

    this.isolatedInstanceId = instanceId;
    for (const inst of this.instances.values()) {
      inst.visible = (inst.name === instanceId);
    }
    return instanceId;
  }

  /**
   * Clears active isolation, restoring visibility of all placed instances.
   *
   * @returns {null}
   */
  clearIsolation() {
    this.isolatedInstanceId = null;
    for (const inst of this.instances.values()) {
      const isSpatial = inst.userData && inst.userData.isPlacedSpatial;
      inst.visible = !!isSpatial;
    }
    return null;
  }

  /**
   * Sets visibility of all instances at once.
   *
   * @param {boolean} visible
   */
  setAllVisibility(visible) {
    for (const inst of this.instances.values()) {
      inst.visible = !!visible;
    }
  }

  /**
   * Sets wireframe mode on all instance materials.
   *
   * @param {boolean} wireframe
   */
  setWireframe(wireframe) {
    this.wireframe = !!wireframe;
    for (const inst of this.instances.values()) {
      inst.traverse((child) => {
        if (child.isMesh && child.material) {
          child.material.wireframe = this.wireframe;
        }
      });
    }
  }

  /**
   * Toggles visibility of curve overlays across all instances.
   *
   * @param {boolean} visible
   */
  setCurvesVisible(visible) {
    this.curvesVisible = !!visible;
    for (const inst of this.instances.values()) {
      inst.traverse((child) => {
        if (child.name && child.name.endsWith("__curves")) {
          child.visible = this.curvesVisible;
        }
      });
    }
  }

  // --- Reset & Disposal Lifecycle ---------------------------------------------

  /**
   * Clears all instance nodes from the AssemblyRoot without disposing the shared geometry pool.
   */
  clear() {
    for (const inst of this.instances.values()) {
      this.root.remove(inst);
    }
    this.instances.clear();
    this.explodedScale = 0.0;
    this.isolatedInstanceId = null;
    this.catiaBoundingBox.makeEmpty();
    this.worldBoundingBox.makeEmpty();
    this.assemblyCentroid.set(0, 0, 0);
  }

  /**
   * Completely disposes all GPU geometry, material, and curve resources,
   * removes the AssemblyRoot from the scene, and cleans up all state.
   */
  dispose() {
    this.clear();
    this.geometryPool.dispose();
    if (this.scene) {
      this.scene.remove(this.root);
    }
  }
}
