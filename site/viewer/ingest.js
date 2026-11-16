/* Ingestion Engine & Multi-File Coordinator (Phase 6, Ticket P3-V3)
   Design Authority: docs/specs/phase6-assembly-viewer-spec.md §4.1, §4.2, §4.3, §8
   Derives from: P1 Product Census (docs/evidence/2026-11-14-p1-product-census.md §3.3)

   Governs client-side multi-file ingestion:
   - Recursive directory drop traversal (DataTransferItemList & webkitGetAsEntry)
   - Multi-file picker (<input type="file" multiple webkitdirectory>)
   - In-browser ZIP archive unpacking via standard Web Streams DecompressionStream('deflate-raw')
   - Ingestion coordinator & root assembly selection (single auto-select, multi-candidate disambiguation)
   - Integration with VirtualFileCatalog (248/382 same-repo PartNumber stem-join law)

   Pure ES module, zero npm runtime dependencies.
*/

import {
  VirtualFileCatalog,
  CatalogEntry,
  normalizePath,
  extractFilename,
  extractStem,
  extractExtension,
} from "./catalog.js";

/**
 * Checks if a byte buffer starts with standard ZIP file signature:
 * - 0x04034b50 (PK\x03\x04): standard local file header
 * - 0x06054b50 (PK\x05\x06): empty zip / end of central directory
 * - 0x08074b50 (PK\x07\x08): spanned / data descriptor signature
 *
 * @param {Uint8Array|ArrayBuffer|{bytes?: Uint8Array}} bytesOrBuffer
 * @returns {boolean}
 */
export function isZipSignature(bytesOrBuffer) {
  if (!bytesOrBuffer) return false;
  let u8 = null;
  if (bytesOrBuffer instanceof Uint8Array) {
    u8 = bytesOrBuffer;
  } else if (bytesOrBuffer instanceof ArrayBuffer) {
    u8 = new Uint8Array(bytesOrBuffer, 0, Math.min(bytesOrBuffer.byteLength, 4));
  } else if (bytesOrBuffer && bytesOrBuffer.bytes instanceof Uint8Array) {
    u8 = bytesOrBuffer.bytes;
  }
  if (!u8 || u8.length < 4) return false;
  return (
    u8[0] === 0x50 &&
    u8[1] === 0x4b &&
    ((u8[2] === 0x03 && u8[3] === 0x04) ||
      (u8[2] === 0x05 && u8[3] === 0x06) ||
      (u8[2] === 0x07 && u8[3] === 0x08))
  );
}

/**
 * Checks if a file or filename indicates a ZIP archive.
 *
 * @param {File|Blob|string|{name?: string, type?: string}} fileOrName
 * @returns {boolean}
 */
export function isZipFile(fileOrName) {
  if (!fileOrName) return false;
  if (typeof fileOrName === "string") {
    return fileOrName.trim().toLowerCase().endsWith(".zip");
  }
  if (fileOrName.name && typeof fileOrName.name === "string") {
    if (fileOrName.name.trim().toLowerCase().endsWith(".zip")) return true;
  }
  if (
    fileOrName.type === "application/zip" ||
    fileOrName.type === "application/x-zip-compressed" ||
    fileOrName.type === "application/x-zip"
  ) {
    return true;
  }
  return false;
}

/**
 * Decompresses raw deflate payload using the browser/Node native Web Streams API
 * DecompressionStream('deflate-raw'). Falls back to node:zlib if available in test runners.
 *
 * @param {Uint8Array} compressedBytes
 * @returns {Promise<Uint8Array>}
 */
export async function decompressDeflateRaw(compressedBytes) {
  if (!compressedBytes || compressedBytes.byteLength === 0) {
    return new Uint8Array(0);
  }

  if (typeof DecompressionStream !== "undefined") {
    const ds = new DecompressionStream("deflate-raw");
    const writer = ds.writable.getWriter();
    writer.write(compressedBytes);
    writer.close();

    const reader = ds.readable.getReader();
    const chunks = [];
    let totalLength = 0;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value);
      totalLength += value.byteLength;
    }

    const result = new Uint8Array(totalLength);
    let offset = 0;
    for (const chunk of chunks) {
      result.set(chunk, offset);
      offset += chunk.byteLength;
    }
    return result;
  }

  // Node.js fallback in environments where DecompressionStream is not globally exposed
  if (typeof process !== "undefined" && process.versions && process.versions.node) {
    const zlib = await import("zlib");
    return new Promise((resolve, reject) => {
      zlib.inflateRaw(compressedBytes, (err, buf) => {
        if (err) reject(err);
        else resolve(new Uint8Array(buf.buffer, buf.byteOffset, buf.byteLength));
      });
    });
  }

  throw new Error("DecompressionStream('deflate-raw') is not supported in this runtime environment");
}

/**
 * Unpacks a ZIP archive in-memory without third-party npm dependencies.
 * Parses the Central Directory record, locates local headers, and decompresses
 * deflated streams via decompressDeflateRaw.
 *
 * @param {ArrayBuffer|Uint8Array|File|Blob|{bytes: Uint8Array}} input
 * @returns {Promise<Array<{path: string, name: string, bytes: Uint8Array, size: number}>>}
 */
export async function unpackZip(input) {
  let bytes;
  if (input instanceof Uint8Array) {
    bytes = input;
  } else if (input instanceof ArrayBuffer) {
    bytes = new Uint8Array(input);
  } else if (input && typeof input.arrayBuffer === "function") {
    const ab = await input.arrayBuffer();
    bytes = new Uint8Array(ab);
  } else if (input && input.bytes instanceof Uint8Array) {
    bytes = input.bytes;
  } else {
    throw new Error("unpackZip expects an ArrayBuffer, Uint8Array, File, or Blob");
  }

  if (bytes.length < 22) {
    throw new Error(`Invalid ZIP archive: byte size ${bytes.length} is too small`);
  }

  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);

  // Search backwards for End of Central Directory (EOCD) signature 0x06054b50
  // Max comment length is 65535, EOCD fixed size is 22 bytes
  let eocdOffset = -1;
  const maxSearch = Math.min(bytes.length, 65535 + 22);
  const minOffset = bytes.length - maxSearch;

  for (let i = bytes.length - 22; i >= minOffset; i--) {
    if (view.getUint32(i, true) === 0x06054b50) {
      const commentLen = view.getUint16(i + 20, true);
      if (i + 22 + commentLen === bytes.length) {
        eocdOffset = i;
        break;
      }
    }
  }

  // Fallback: match first 0x06054b50 backwards if trailing bytes exist
  if (eocdOffset === -1) {
    for (let i = bytes.length - 22; i >= minOffset; i--) {
      if (view.getUint32(i, true) === 0x06054b50) {
        eocdOffset = i;
        break;
      }
    }
  }

  if (eocdOffset === -1) {
    throw new Error("End of Central Directory (EOCD) signature not found in ZIP archive");
  }

  const totalEntries = view.getUint16(eocdOffset + 10, true);
  const cdSize = view.getUint32(eocdOffset + 12, true);
  const cdOffset = view.getUint32(eocdOffset + 16, true);

  if (cdOffset > bytes.length || cdOffset + cdSize > bytes.length) {
    throw new Error("Corrupted ZIP archive: central directory offset out of bounds");
  }

  const textDecoder = new TextDecoder("utf-8", { fatal: false });
  const extractedFiles = [];

  let curOffset = cdOffset;
  for (let i = 0; i < totalEntries; i++) {
    if (curOffset + 46 > bytes.length) break;
    const sig = view.getUint32(curOffset, true);
    if (sig !== 0x02014b50) {
      // Reached end or non-CDFH signature
      break;
    }

    const method = view.getUint16(curOffset + 10, true);
    const compressedSize = view.getUint32(curOffset + 20, true);
    const uncompressedSize = view.getUint32(curOffset + 24, true);
    const nameLen = view.getUint16(curOffset + 28, true);
    const extraLen = view.getUint16(curOffset + 30, true);
    const commentLen = view.getUint16(curOffset + 32, true);
    const localHeaderOffset = view.getUint32(curOffset + 42, true);

    const nameBytes = bytes.subarray(curOffset + 46, curOffset + 46 + nameLen);
    const rawFilename = textDecoder.decode(nameBytes);
    const normalized = normalizePath(rawFilename);

    curOffset += 46 + nameLen + extraLen + commentLen;

    // Skip directory records
    if (!normalized || rawFilename.endsWith("/") || rawFilename.endsWith("\\")) {
      continue;
    }

    // Skip macOS metadata files and system artifacts
    if (
      normalized.startsWith("__MACOSX/") ||
      extractFilename(normalized).startsWith("._") ||
      extractFilename(normalized) === ".DS_Store"
    ) {
      continue;
    }

    if (localHeaderOffset + 30 > bytes.length) {
      continue;
    }

    const localSig = view.getUint32(localHeaderOffset, true);
    if (localSig !== 0x04034b50) {
      continue;
    }

    const localNameLen = view.getUint16(localHeaderOffset + 26, true);
    const localExtraLen = view.getUint16(localHeaderOffset + 28, true);
    const dataStart = localHeaderOffset + 30 + localNameLen + localExtraLen;

    if (dataStart + compressedSize > bytes.length) {
      throw new Error(`Corrupted ZIP archive: entry payload truncated for ${rawFilename}`);
    }

    const compressedSlice = bytes.subarray(dataStart, dataStart + compressedSize);
    let entryBytes;

    if (method === 0) {
      // Stored (no compression)
      entryBytes = compressedSlice.slice();
    } else if (method === 8) {
      // Deflated
      entryBytes = await decompressDeflateRaw(compressedSlice);
    } else {
      console.warn(`Skipping ZIP entry ${rawFilename}: unsupported compression method ${method}`);
      continue;
    }

    extractedFiles.push({
      path: normalized,
      name: extractFilename(normalized),
      bytes: entryBytes,
      size: uncompressedSize || entryBytes.byteLength,
    });
  }

  return extractedFiles;
}

/**
 * Traverses a FileSystemEntry (file or directory) recursively.
 * Handles FileSystemDirectoryReader.readEntries batching loop.
 *
 * @param {any} entry - WebKit FileSystemEntry (FileEntry or DirectoryEntry)
 * @returns {Promise<Array<{file: File, path: string, name: string, size: number}>>}
 */
export async function traverseFileSystemEntry(entry) {
  const list = [];
  await _walkEntry(entry, list);
  return list;
}

async function _walkEntry(entry, list) {
  if (!entry) return;

  if (entry.isFile) {
    const file = await new Promise((resolve, reject) => {
      entry.file(resolve, reject);
    });
    const relPath = entry.fullPath ? entry.fullPath.replace(/^\/+/, "") : file.name;
    list.push({
      file,
      path: normalizePath(relPath),
      name: file.name,
      size: file.size,
    });
  } else if (entry.isDirectory) {
    const reader = entry.createReader();
    // readEntries returns entries in batches of ~100. Must loop until empty.
    while (true) {
      const batch = await new Promise((resolve, reject) => {
        reader.readEntries(resolve, reject);
      });
      if (!batch || batch.length === 0) break;
      for (const child of batch) {
        await _walkEntry(child, list);
      }
    }
  }
}

/**
 * Scans a Drag-and-Drop DataTransfer object for files and directories.
 * Uses webkitGetAsEntry when available for directory recursion.
 *
 * @param {DataTransfer} dataTransfer
 * @returns {Promise<Array<{file?: File, path: string, name: string, size?: number, bytes?: Uint8Array}>>}
 */
export async function scanDataTransfer(dataTransfer) {
  if (!dataTransfer) return [];
  const entries = [];

  const items = dataTransfer.items;
  if (items && items.length > 0) {
    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      if (item.kind && item.kind !== "file") continue;
      const entry = item.webkitGetAsEntry ? item.webkitGetAsEntry() : null;
      if (entry) {
        const walked = await traverseFileSystemEntry(entry);
        entries.push(...walked);
      } else {
        const file = item.getAsFile ? item.getAsFile() : null;
        if (file) {
          entries.push({
            file,
            path: normalizePath(file.webkitRelativePath || file.name),
            name: file.name,
            size: file.size,
          });
        }
      }
    }
  } else if (dataTransfer.files && dataTransfer.files.length > 0) {
    for (let i = 0; i < dataTransfer.files.length; i++) {
      const file = dataTransfer.files[i];
      entries.push({
        file,
        path: normalizePath(file.webkitRelativePath || file.name),
        name: file.name,
        size: file.size,
      });
    }
  }

  return entries;
}

/**
 * Scans an HTMLInputElement or FileList (<input type="file" multiple webkitdirectory>).
 *
 * @param {HTMLInputElement|FileList|File[]} inputOrFiles
 * @returns {Array<{file: File, path: string, name: string, size: number}>}
 */
export function scanFileInput(inputOrFiles) {
  const files = inputOrFiles && inputOrFiles.files ? inputOrFiles.files : inputOrFiles;
  if (!files || (typeof files[Symbol.iterator] !== "function" && typeof files.length !== "number")) {
    return [];
  }
  const result = [];
  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    if (!file) continue;
    result.push({
      file,
      path: normalizePath(file.webkitRelativePath || file.name),
      name: file.name,
      size: file.size,
    });
  }
  return result;
}

/**
 * Disambiguates and selects the root .CATProduct from a list of products (§4.3).
 *
 * Law:
 * 1. If exactly 1 product: automatically selected as root.
 * 2. If multiple products:
 *    - Heuristic score: prioritizes names containing IsRoot, Root, Assembly, Main, Top,
 *      or matching the root directory stem.
 *    - Allows override via options.preferredRoot.
 *    - Always returns complete candidate list for UI switcher (<select id="root-product-select">).
 *
 * @param {CatalogEntry[]} products
 * @param {VirtualFileCatalog} [catalog]
 * @param {Object} [options]
 * @param {string} [options.preferredRoot]
 * @returns {{rootProduct: CatalogEntry|null, candidates: CatalogEntry[]}}
 */
export function selectRootProduct(products, catalog = null, options = {}) {
  if (!products || products.length === 0) {
    return {
      rootProduct: null,
      candidates: [],
    };
  }

  const candidates = products.slice();

  if (candidates.length === 1) {
    return {
      rootProduct: candidates[0],
      candidates,
    };
  }

  // Check user preference / explicit override
  if (options.preferredRoot && typeof options.preferredRoot === "string") {
    const pref = options.preferredRoot.trim().toLowerCase();
    const match = candidates.find(
      (p) =>
        p.name.toLowerCase() === pref ||
        p.stem.toLowerCase() === pref ||
        p.path.toLowerCase() === pref
    );
    if (match) {
      return { rootProduct: match, candidates };
    }
  }

  // Heuristic Selection (§4.3):
  // Check terminal tokens, IsRoot tokens, and common root assembly naming conventions
  const scoreProduct = (entry) => {
    const stemLower = entry.stem.toLowerCase();
    const nameLower = entry.name.toLowerCase();
    const pathLower = entry.path.toLowerCase();
    let score = 0;

    if (stemLower.includes("isroot")) score += 100;
    if (stemLower.endsWith("root") || stemLower.startsWith("root")) score += 50;
    if (stemLower.includes("root")) score += 30;
    if (stemLower.includes("main")) score += 25;
    if (stemLower.includes("assembly")) score += 20;
    if (stemLower.includes("top")) score += 15;

    // Prefer shallowest relative path depth (closer to root folder)
    const depth = (entry.path.match(/\//g) || []).length;
    score -= depth * 5;

    return score;
  };

  let best = candidates[0];
  let bestScore = scoreProduct(best);

  for (let i = 1; i < candidates.length; i++) {
    const curScore = scoreProduct(candidates[i]);
    if (curScore > bestScore) {
      bestScore = curScore;
      best = candidates[i];
    }
  }

  return {
    rootProduct: best,
    candidates,
  };
}

/**
 * Result structure returned by ingestFiles and IngestionCoordinator.
 * @typedef {Object} IngestionResult
 * @property {VirtualFileCatalog} catalog - The populated catalog instance
 * @property {CatalogEntry|null} rootProduct - The selected root .CATProduct entry
 * @property {CatalogEntry[]} candidates - List of all ingested .CATProduct entries
 * @property {number} totalFiles - Total files registered in the catalog
 * @property {number} partsCount - Number of registered .CATPart files
 * @property {number} productsCount - Number of registered .CATProduct files
 * @property {boolean} hasRootProduct - Whether a valid root product was resolved
 * @property {boolean} isMultiProduct - Whether multiple candidate products were found
 */

/**
 * Master multi-file ingestion pipeline coordinator.
 *
 * Accepts arbitrary collections of inputs:
 * - DataTransfer (drag-and-drop)
 * - HTMLInputElement (<input type="file">)
 * - FileList or File[]
 * - In-memory object arrays { name, path, bytes, size }
 * - ZIP archives (unpacked in-browser via unpackZip)
 *
 * Registers all files into a VirtualFileCatalog and identifies the root product.
 *
 * @param {any} inputs
 * @param {Object} [options]
 * @param {VirtualFileCatalog} [options.catalog]
 * @param {string} [options.preferredRoot]
 * @returns {Promise<IngestionResult>}
 */
export async function ingestFiles(inputs, options = {}) {
  const catalog = options.catalog || new VirtualFileCatalog();
  const rawList = [];

  if (!inputs) {
    return _buildIngestionResult(catalog, options);
  }

  // 1. Flatten heterogeneous input sources into candidate descriptor list
  if (typeof DataTransfer !== "undefined" && inputs instanceof DataTransfer) {
    const scanned = await scanDataTransfer(inputs);
    rawList.push(...scanned);
  } else if (inputs && inputs.items && inputs.files) {
    // DataTransfer duck-typing
    const scanned = await scanDataTransfer(inputs);
    rawList.push(...scanned);
  } else if (inputs && inputs.files) {
    // HTMLInputElement
    rawList.push(...scanFileInput(inputs));
  } else if (
    Array.isArray(inputs) ||
    (typeof inputs === "object" && typeof inputs[Symbol.iterator] === "function")
  ) {
    for (const item of inputs) {
      if (item && (item.isFile || item.isDirectory)) {
        const walked = await traverseFileSystemEntry(item);
        rawList.push(...walked);
      } else {
        rawList.push(item);
      }
    }
  } else {
    // Single file, blob, or buffer descriptor
    rawList.push(inputs);
  }

  // 2. Process candidate list, automatically detecting and expanding ZIP archives
  for (const item of rawList) {
    if (!item) continue;

    if (item instanceof CatalogEntry) {
      catalog.register(item);
      continue;
    }

    let candidateBytes = item.bytes || null;
    const candidateName = item.name || (typeof item === "string" ? item : "");
    const candidatePath = item.path || candidateName;

    // Check if candidate is a ZIP archive
    let isZip = isZipFile(item);

    if (!isZip) {
      if (candidateBytes) {
        isZip = isZipSignature(candidateBytes);
      } else if (
        item.file &&
        typeof item.file.slice === "function" &&
        typeof item.file.arrayBuffer === "function"
      ) {
        try {
          const slice = await item.file.slice(0, 4).arrayBuffer();
          isZip = isZipSignature(new Uint8Array(slice));
        } catch {
          // Ignore slice probe error
        }
      } else if (item instanceof Uint8Array || item instanceof ArrayBuffer) {
        const probe = item instanceof Uint8Array ? item : new Uint8Array(item);
        isZip = isZipSignature(probe);
      }
    }

    if (isZip) {
      let zipBuffer = candidateBytes;
      if (!zipBuffer) {
        if (item.file && typeof item.file.arrayBuffer === "function") {
          zipBuffer = await item.file.arrayBuffer();
        } else if (typeof item.arrayBuffer === "function") {
          zipBuffer = await item.arrayBuffer();
        } else if (item instanceof Uint8Array || item instanceof ArrayBuffer) {
          zipBuffer = item;
        }
      }

      if (zipBuffer) {
        const unpacked = await unpackZip(zipBuffer);
        for (const fileRecord of unpacked) {
          // Recursive ZIP support: if an unpacked entry is itself a ZIP, unpack it
          if (isZipFile(fileRecord) || isZipSignature(fileRecord.bytes)) {
            try {
              const nested = await unpackZip(fileRecord.bytes);
              for (const n of nested) {
                catalog.register(n, n.path);
              }
              continue;
            } catch {
              // Register as regular file if recursive unpack fails
            }
          }
          catalog.register(fileRecord, fileRecord.path);
        }
        continue;
      }
    }

    // Standard file registration into catalog
    catalog.register(item, candidatePath);
  }

  return _buildIngestionResult(catalog, options);
}

function _buildIngestionResult(catalog, options = {}) {
  const products = catalog.getProducts();
  const parts = catalog.getParts();
  const { rootProduct, candidates } = selectRootProduct(products, catalog, options);

  return {
    catalog,
    rootProduct,
    candidates,
    totalFiles: catalog.size,
    partsCount: parts.length,
    productsCount: products.length,
    hasRootProduct: rootProduct !== null,
    isMultiProduct: candidates.length > 1,
  };
}

/**
 * Ingestion Coordinator class providing persistent session state for viewer UI.
 */
export class IngestionCoordinator {
  /**
   * @param {Object} [options]
   * @param {VirtualFileCatalog} [options.catalog]
   * @param {string} [options.preferredRoot]
   */
  constructor(options = {}) {
    this.catalog = options.catalog || new VirtualFileCatalog();
    this.rootProduct = null;
    this.candidates = [];
    this.options = options;
  }

  /**
   * Ingests files into this coordinator's catalog.
   *
   * @param {any} inputs
   * @returns {Promise<IngestionResult>}
   */
  async ingest(inputs) {
    const result = await ingestFiles(inputs, {
      ...this.options,
      catalog: this.catalog,
    });
    this.rootProduct = result.rootProduct;
    this.candidates = result.candidates;
    return result;
  }

  /**
   * Switches the active root product by CatalogEntry, stem, or name.
   *
   * @param {CatalogEntry|string} entryOrName
   * @returns {CatalogEntry|null}
   */
  setRootProduct(entryOrName) {
    if (!entryOrName) {
      this.rootProduct = null;
      return null;
    }
    if (entryOrName instanceof CatalogEntry) {
      this.rootProduct = entryOrName;
      return this.rootProduct;
    }
    const resolved = this.catalog.resolveProduct(entryOrName);
    if (resolved) {
      this.rootProduct = resolved;
    }
    return this.rootProduct;
  }

  /**
   * Clears all ingested catalog entries and resets state.
   */
  clear() {
    this.catalog.clear();
    this.rootProduct = null;
    this.candidates = [];
  }
}

/**
 * Attaches drag-and-drop handlers to a DOM element (or document).
 *
 * @param {HTMLElement|Document} dropElement
 * @param {Object} [callbacks]
 * @param {(result: IngestionResult, event: DragEvent) => void} [callbacks.onIngest]
 * @param {(error: Error, event: DragEvent) => void} [callbacks.onError]
 * @param {(event: DragEvent) => void} [callbacks.onDragOver]
 * @param {(event: DragEvent) => void} [callbacks.onDragLeave]
 * @returns {() => void} Cleanup function to detach event listeners
 */
export function setupDropZone(dropElement, callbacks = {}) {
  if (!dropElement || typeof dropElement.addEventListener !== "function") {
    return () => {};
  }

  const { onIngest, onError, onDragOver, onDragLeave } = callbacks;

  const handleDragOver = (ev) => {
    ev.preventDefault();
    if (dropElement.classList && typeof dropElement.classList.add === "function") {
      dropElement.classList.add("over");
    }
    if (typeof onDragOver === "function") onDragOver(ev);
  };

  const handleDragLeave = (ev) => {
    if (dropElement.classList && typeof dropElement.classList.remove === "function") {
      dropElement.classList.remove("over");
    }
    if (typeof onDragLeave === "function") onDragLeave(ev);
  };

  const handleDrop = async (ev) => {
    ev.preventDefault();
    if (dropElement.classList && typeof dropElement.classList.remove === "function") {
      dropElement.classList.remove("over");
    }
    try {
      const result = await ingestFiles(ev.dataTransfer);
      if (typeof onIngest === "function") {
        onIngest(result, ev);
      }
    } catch (err) {
      if (typeof onError === "function") {
        onError(err, ev);
      } else {
        console.error("Drop ingestion error:", err);
      }
    }
  };

  dropElement.addEventListener("dragover", handleDragOver);
  dropElement.addEventListener("dragleave", handleDragLeave);
  dropElement.addEventListener("drop", handleDrop);

  return function cleanup() {
    dropElement.removeEventListener("dragover", handleDragOver);
    dropElement.removeEventListener("dragleave", handleDragLeave);
    dropElement.removeEventListener("drop", handleDrop);
  };
}

/**
 * Attaches change handler to a multi-file <input type="file"> element.
 *
 * @param {HTMLInputElement} inputElement
 * @param {Object} [callbacks]
 * @param {(result: IngestionResult, event: Event) => void} [callbacks.onIngest]
 * @param {(error: Error, event: Event) => void} [callbacks.onError]
 * @returns {() => void} Cleanup function to detach event listeners
 */
export function setupFileInput(inputElement, callbacks = {}) {
  if (!inputElement || typeof inputElement.addEventListener !== "function") {
    return () => {};
  }

  const { onIngest, onError } = callbacks;

  const handleChange = async (ev) => {
    try {
      const result = await ingestFiles(inputElement.files);
      if (typeof onIngest === "function") {
        onIngest(result, ev);
      }
    } catch (err) {
      if (typeof onError === "function") {
        onError(err, ev);
      } else {
        console.error("File input ingestion error:", err);
      }
    } finally {
      inputElement.value = "";
    }
  };

  inputElement.addEventListener("change", handleChange);

  return function cleanup() {
    inputElement.removeEventListener("change", handleChange);
  };
}

/**
 * Sets up document-level drop handling to prevent accidental navigation on drops outside zone.
 *
 * @param {Document|Window} [doc]
 * @returns {() => void} Cleanup function
 */
export function preventWindowDropDefaults(doc = typeof window !== "undefined" ? window : null) {
  if (!doc || typeof doc.addEventListener !== "function") {
    return () => {};
  }
  const prevent = (ev) => ev.preventDefault();
  doc.addEventListener("dragover", prevent, false);
  doc.addEventListener("drop", prevent, false);
  return () => {
    doc.removeEventListener("dragover", prevent, false);
    doc.removeEventListener("drop", prevent, false);
  };
}
