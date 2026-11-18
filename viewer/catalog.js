/* Virtual File Catalog & Component Resolution Engine (Phase 6, Ticket P3-V3)
   Design Authority: docs/specs/phase6-assembly-viewer-spec.md §4.2, §6, §8
   Derives from: P1 Product Census (docs/evidence/2026-11-14-p1-product-census.md §3.3)
   
   Governs client-side multi-file ingestion, indexing, and the 248/382 same-repo
   PartNumber stem-join resolution law. Pure ES module, zero npm runtime dependencies.
*/

export const STATUS_RESOLVED = "Resolved";
export const STATUS_UNRESOLVED = "Unresolved";

/**
 * Normalizes relative file paths:
 * - Converts Windows backslashes to forward slashes
 * - Strips leading slashes or relative prefixes (./ or /)
 * - Collapses redundant consecutive slashes
 * - Trims whitespace
 *
 * @param {string} p
 * @returns {string}
 */
export function normalizePath(p) {
  if (!p || typeof p !== "string") return "";
  let s = p.replace(/\\/g, "/").trim();
  s = s.replace(/^(\.\/|\/)+/, "");
  s = s.replace(/\/+/g, "/");
  return s;
}

/**
 * Extracts base filename from a path (e.g. "sub/dir/part.CATPart" -> "part.CATPart").
 *
 * @param {string} pathOrName
 * @returns {string}
 */
export function extractFilename(pathOrName) {
  const norm = normalizePath(pathOrName);
  const idx = norm.lastIndexOf("/");
  return idx === -1 ? norm : norm.slice(idx + 1);
}

/**
 * Extracts stem (basename without file extension).
 * Recognizes CATIA V5 extensions (.CATPart, .CATProduct, .catpart, .catproduct)
 * as well as general file extensions.
 *
 * @param {string} pathOrName
 * @returns {string}
 */
export function extractStem(pathOrName) {
  const filename = extractFilename(pathOrName);
  const lower = filename.toLowerCase();
  if (lower.endsWith(".catpart")) {
    return filename.slice(0, -8);
  }
  if (lower.endsWith(".catproduct")) {
    return filename.slice(0, -11);
  }
  const dotIdx = filename.lastIndexOf(".");
  if (dotIdx > 0) {
    return filename.slice(0, dotIdx);
  }
  return filename;
}

/**
 * Extracts lowercase file extension including leading dot (e.g. ".catpart", ".catproduct").
 *
 * @param {string} pathOrName
 * @returns {string}
 */
export function extractExtension(pathOrName) {
  const filename = extractFilename(pathOrName);
  const dotIdx = filename.lastIndexOf(".");
  if (dotIdx > 0) {
    return filename.slice(dotIdx).toLowerCase();
  }
  return "";
}

/**
 * An entry in the VirtualFileCatalog representing an ingested file.
 */
export class CatalogEntry {
  /**
   * @param {Object} options
   * @param {File|Blob|{name: string, bytes?: Uint8Array, size?: number}} options.file
   * @param {string} [options.path] - Normalized relative path
   * @param {string} [options.name] - Base filename
   * @param {Uint8Array|null} [options.bytes] - Eagerly loaded or extracted byte buffer
   * @param {number|null} [options.size] - File byte size
   */
  constructor({ file, path = null, name = null, bytes = null, size = null }) {
    this.file = file;
    this.path = normalizePath(path || (file && file.name) || "");
    this.name = name || extractFilename(this.path);
    this.stem = extractStem(this.name);
    this.extension = extractExtension(this.name);
    this.bytes = bytes || (file && file.bytes instanceof Uint8Array ? file.bytes : null);
    this.size = size !== null
      ? size
      : ((this.bytes && this.bytes.byteLength) || (file && file.size) || 0);
  }

  /**
   * Retrieves file bytes lazily or eagerly.
   * Works in browser (File/Blob) and Node/in-memory environments.
   *
   * @returns {Promise<Uint8Array>}
   */
  async getBytes() {
    if (this.bytes instanceof Uint8Array) {
      return this.bytes;
    }
    if (this.file && typeof this.file.arrayBuffer === "function") {
      const buf = await this.file.arrayBuffer();
      this.bytes = new Uint8Array(buf);
      return this.bytes;
    }
    if (this.file && this.file.bytes instanceof Uint8Array) {
      this.bytes = this.file.bytes;
      return this.bytes;
    }
    throw new Error(`Unable to read bytes for catalog entry: ${this.path || this.name}`);
  }
}

/**
 * In-Memory Virtual File Catalog.
 *
 * Implements the 248/382 same-repo PartNumber resolution law (P1 §3.3):
 * Part numbers declared in CATProduct pools join corpus part files by stem.
 * Lookup checks:
 * 1. Exact path match
 * 2. Exact filename match (e.g. "ac1.CATPart")
 * 3. Exact stem match (e.g. "ac1")
 * 4. Exact filename with .CATPart / .catpart suffix
 * 5. Case-normalized path match
 * 6. Case-normalized filename match (e.g. "AC1.CATPart" -> "ac1.catpart")
 * 7. Case-normalized stem match (e.g. "LOWER_teeth_blend..." -> "lower_teeth_blend...")
 */
export class VirtualFileCatalog {
  constructor() {
    /** @type {CatalogEntry[]} */
    this.entries = [];
    /** @type {Map<string, CatalogEntry>} */
    this.byPath = new Map();
    /** @type {Map<string, CatalogEntry>} */
    this.byLowerPath = new Map();
    /** @type {Map<string, CatalogEntry>} */
    this.byExactName = new Map();
    /** @type {Map<string, CatalogEntry>} */
    this.byLowerName = new Map();
    /** @type {Map<string, CatalogEntry>} */
    this.exactStems = new Map();
    /** @type {Map<string, CatalogEntry>} */
    this.lowerStems = new Map();
    /** @type {CatalogEntry[]} */
    this.products = [];
    /** @type {CatalogEntry[]} */
    this.parts = [];
    /** @type {Map<string, { status: string, partNumber: string, instanceId: string, resolved: boolean, entry: CatalogEntry|null }>} */
    this.instanceStatus = new Map();
  }

  /**
   * Resets all internal stores.
   */
  clear() {
    this.entries = [];
    this.byPath.clear();
    this.byLowerPath.clear();
    this.byExactName.clear();
    this.byLowerName.clear();
    this.exactStems.clear();
    this.lowerStems.clear();
    this.products = [];
    this.parts = [];
    this.instanceStatus.clear();
  }

  /**
   * Total number of registered entries.
   * @returns {number}
   */
  get size() {
    return this.entries.length;
  }

  /**
   * Registers a file or entry into the catalog.
   *
   * @param {CatalogEntry|File|{file?: any, path?: string, name?: string, bytes?: Uint8Array, size?: number}} entryOrFile
   * @param {string} [relativePath]
   * @returns {CatalogEntry}
   */
  register(entryOrFile, relativePath = null) {
    let entry;
    if (entryOrFile instanceof CatalogEntry) {
      entry = entryOrFile;
    } else if (entryOrFile && (entryOrFile.file || entryOrFile.bytes)) {
      entry = new CatalogEntry({
        file: entryOrFile.file || entryOrFile,
        path: relativePath || entryOrFile.path || entryOrFile.name,
        name: entryOrFile.name,
        bytes: entryOrFile.bytes,
        size: entryOrFile.size,
      });
    } else {
      entry = new CatalogEntry({
        file: entryOrFile,
        path: relativePath || (entryOrFile && entryOrFile.name) || "",
      });
    }

    this.entries.push(entry);

    // Index by relative path
    if (entry.path) {
      this.byPath.set(entry.path, entry);
      this.byLowerPath.set(entry.path.toLowerCase(), entry);
    }

    // Index by filename
    if (entry.name) {
      this.byExactName.set(entry.name, entry);
      this.byLowerName.set(entry.name.toLowerCase(), entry);
    }

    // Index by stem
    if (entry.stem) {
      this.exactStems.set(entry.stem, entry);
      this.lowerStems.set(entry.stem.toLowerCase(), entry);
    }

    // Category lists
    if (entry.extension === ".catproduct") {
      this.products.push(entry);
    } else if (entry.extension === ".catpart") {
      this.parts.push(entry);
    }

    return entry;
  }

  /**
   * Helper alias to register a file with an optional relative path.
   *
   * @param {File|Blob|{name: string, bytes?: Uint8Array}} file
   * @param {string} [relativePath]
   * @returns {CatalogEntry}
   */
  registerFile(file, relativePath = null) {
    return this.register(file, relativePath);
  }

  /**
   * Resolves a part number to a CatalogEntry using the 248/382 same-repo join law.
   *
   * Checks in strict priority order:
   * 1. Exact path match
   * 2. Exact filename match
   * 3. Exact stem match
   * 4. Exact filename with .CATPart or .catpart suffix
   * 5. Case-normalized path match
   * 6. Case-normalized filename match
   * 7. Case-normalized stem match
   * 8. Stripped extension variations
   *
   * @param {string} partNumber
   * @returns {CatalogEntry|null}
   */
  resolvePart(partNumber) {
    if (!partNumber || typeof partNumber !== "string") {
      return null;
    }
    const clean = partNumber.trim();
    if (!clean) return null;

    const filename = extractFilename(clean);
    const stem = extractStem(clean);
    const lowerClean = clean.toLowerCase();
    const lowerFilename = filename.toLowerCase();
    const lowerStem = stem.toLowerCase();

    // 1. Exact path match
    if (this.byPath.has(clean)) {
      const e = this.byPath.get(clean);
      if (e.extension === ".catpart" || !e.extension) return e;
    }

    // 2. Exact filename match
    if (this.byExactName.has(filename)) {
      const e = this.byExactName.get(filename);
      if (e.extension === ".catpart" || !e.extension) return e;
    }

    // 3. Exact stem match
    if (this.exactStems.has(stem)) {
      const e = this.exactStems.get(stem);
      if (e.extension === ".catpart" || !e.extension) return e;
    }
    if (this.exactStems.has(clean)) {
      const e = this.exactStems.get(clean);
      if (e.extension === ".catpart" || !e.extension) return e;
    }

    // 4. Exact filename with .CATPart / .catpart suffix
    if (this.byExactName.has(stem + ".CATPart")) {
      return this.byExactName.get(stem + ".CATPart");
    }
    if (this.byExactName.has(stem + ".catpart")) {
      return this.byExactName.get(stem + ".catpart");
    }

    // 5. Case-normalized path match
    if (this.byLowerPath.has(lowerClean)) {
      const e = this.byLowerPath.get(lowerClean);
      if (e.extension === ".catpart" || !e.extension) return e;
    }

    // 6. Case-normalized filename match
    if (this.byLowerName.has(lowerFilename)) {
      const e = this.byLowerName.get(lowerFilename);
      if (e.extension === ".catpart" || !e.extension) return e;
    }
    if (this.byLowerName.has(lowerStem + ".catpart")) {
      return this.byLowerName.get(lowerStem + ".catpart");
    }

    // 7. Case-normalized stem match
    if (this.lowerStems.has(lowerStem)) {
      const e = this.lowerStems.get(lowerStem);
      if (e.extension === ".catpart" || !e.extension) return e;
    }
    if (this.lowerStems.has(lowerClean)) {
      const e = this.lowerStems.get(lowerClean);
      if (e.extension === ".catpart" || !e.extension) return e;
    }

    // 8. If clean ends with .catpart case-insensitively, check stripped stem
    if (lowerClean.endsWith(".catpart")) {
      const stripped = clean.slice(0, -8);
      if (this.exactStems.has(stripped)) {
        return this.exactStems.get(stripped);
      }
      if (this.lowerStems.has(stripped.toLowerCase())) {
        return this.lowerStems.get(stripped.toLowerCase());
      }
    }

    // 9. Fallback: check parts list directly for matching stem
    for (const part of this.parts) {
      if (part.stem === stem || part.stem.toLowerCase() === lowerStem) {
        return part;
      }
    }

    return null;
  }

  /**
   * Resolves a product name or path to a .CATProduct CatalogEntry.
   *
   * @param {string} productName
   * @returns {CatalogEntry|null}
   */
  resolveProduct(productName) {
    if (!productName || typeof productName !== "string") return null;
    const clean = productName.trim();
    if (!clean) return null;

    const filename = extractFilename(clean);
    const stem = extractStem(clean);
    const lowerStem = stem.toLowerCase();

    // 1. By exact path
    if (this.byPath.has(clean)) return this.byPath.get(clean);

    // 2. By exact name
    if (this.byExactName.has(filename)) return this.byExactName.get(filename);

    // 3. Exact stem in products
    const prodExact = this.products.find((p) => p.stem === stem);
    if (prodExact) return prodExact;

    // 4. Exact name with .CATProduct
    if (this.byExactName.has(stem + ".CATProduct")) {
      return this.byExactName.get(stem + ".CATProduct");
    }

    // 5. Case-insensitive path
    if (this.byLowerPath.has(clean.toLowerCase())) {
      return this.byLowerPath.get(clean.toLowerCase());
    }

    // 6. Case-insensitive name
    if (this.byLowerName.has(filename.toLowerCase())) {
      return this.byLowerName.get(filename.toLowerCase());
    }

    // 7. Case-insensitive stem
    const prodLower = this.products.find((p) => p.stem.toLowerCase() === lowerStem);
    if (prodLower) return prodLower;

    return null;
  }

  /**
   * Resolves an instance and tracks its resolution status.
   *
   * @param {string|{part_number?: string, partNumber?: string, instance_name?: string, instanceName?: string, name?: string}} instanceOrPartNumber
   * @returns {{ status: string, partNumber: string, instanceId: string, resolved: boolean, entry: CatalogEntry|null }}
   */
  resolveInstance(instanceOrPartNumber) {
    let partNumber = "";
    let instanceId = "";

    if (typeof instanceOrPartNumber === "string") {
      partNumber = instanceOrPartNumber;
      instanceId = instanceOrPartNumber;
    } else if (instanceOrPartNumber && typeof instanceOrPartNumber === "object") {
      partNumber = instanceOrPartNumber.part_number || instanceOrPartNumber.partNumber || instanceOrPartNumber.name || "";
      instanceId = instanceOrPartNumber.instance_name || instanceOrPartNumber.instanceName || partNumber;
    }

    const entry = this.resolvePart(partNumber);
    const status = entry ? STATUS_RESOLVED : STATUS_UNRESOLVED;
    const result = {
      instanceId,
      partNumber,
      status,
      resolved: entry !== null,
      entry,
    };

    if (instanceId) {
      this.instanceStatus.set(instanceId, result);
    }
    return result;
  }

  /**
   * Resolves an array of instances and records their status.
   *
   * @param {Array<string|Object>} instances
   * @returns {Array<{ status: string, partNumber: string, instanceId: string, resolved: boolean, entry: CatalogEntry|null }>}
   */
  resolveInstances(instances) {
    if (!Array.isArray(instances)) return [];
    return instances.map((inst) => this.resolveInstance(inst));
  }

  /**
   * Returns a deduplicated array of all missing (unresolved) component names.
   *
   * @param {Iterable<string|Object>} requiredPartNumbers
   * @returns {string[]}
   */
  listUnresolved(requiredPartNumbers) {
    if (!requiredPartNumbers) return [];
    const missing = new Set();
    for (const item of requiredPartNumbers) {
      const pn = typeof item === "string"
        ? item
        : (item && (item.part_number || item.partNumber || item.name)) || "";
      if (pn && !this.resolvePart(pn)) {
        missing.add(pn);
      }
    }
    return Array.from(missing);
  }

  /**
   * Returns a deduplicated array of all resolved component names.
   *
   * @param {Iterable<string|Object>} requiredPartNumbers
   * @returns {string[]}
   */
  listResolved(requiredPartNumbers) {
    if (!requiredPartNumbers) return [];
    const resolved = new Set();
    for (const item of requiredPartNumbers) {
      const pn = typeof item === "string"
        ? item
        : (item && (item.part_number || item.partNumber || item.name)) || "";
      if (pn && this.resolvePart(pn)) {
        resolved.add(pn);
      }
    }
    return Array.from(resolved);
  }

  /**
   * Returns all registered .CATProduct entries.
   * @returns {CatalogEntry[]}
   */
  getProducts() {
    return this.products.slice();
  }

  /**
   * Returns all registered .CATPart entries.
   * @returns {CatalogEntry[]}
   */
  getParts() {
    return this.parts.slice();
  }

  /**
   * Returns all registered entries.
   * @returns {CatalogEntry[]}
   */
  getAllEntries() {
    return this.entries.slice();
  }

  /**
   * Returns tracked instance resolution status.
   * @param {string} instanceId
   * @returns {Object|null}
   */
  getInstanceStatus(instanceId) {
    return this.instanceStatus.get(instanceId) || null;
  }

  /**
   * Returns a summary tally of catalog contents.
   * @returns {{ total: number, products: number, parts: number, instancesTracked: number }}
   */
  summary() {
    return {
      total: this.entries.length,
      products: this.products.length,
      parts: this.parts.length,
      instancesTracked: this.instanceStatus.size,
    };
  }
}
