/* Test Suite for VirtualFileCatalog & Ingestion Coordinator (Phase 6, Ticket P3-V3)
   Design Authority: docs/specs/phase6-assembly-viewer-spec.md §4.1, §4.2, §4.3, §8
   Pure ES module, zero npm dependencies. Run via: node tests/test_viewer_catalog.mjs
*/

import assert from "node:assert/strict";
import zlib from "node:zlib";
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
  traverseFileSystemEntry,
  scanDataTransfer,
  scanFileInput,
  setupDropZone,
  setupFileInput,
  preventWindowDropDefaults,
} from "../site/viewer/ingest.js";

// Helper: In-memory ZIP builder for testing zero-npm unpacker
function createSyntheticZip(entries) {
  const localHeaders = [];
  const cdHeaders = [];
  let offset = 0;

  // CRC32 table
  const table = new Uint32Array(256);
  for (let i = 0; i < 256; i++) {
    let c = i;
    for (let k = 0; k < 8; k++) {
      c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    }
    table[i] = c;
  }

  for (const entry of entries) {
    const raw = Buffer.isBuffer(entry.content)
      ? entry.content
      : Buffer.from(entry.content || "");
    const method = entry.method !== undefined ? entry.method : 8;
    const compressed = method === 8 ? zlib.deflateRawSync(raw) : raw;
    const nameBuf = Buffer.from(entry.path, "utf-8");

    let crc = 0 ^ -1;
    for (let i = 0; i < raw.length; i++) {
      crc = (crc >>> 8) ^ table[(crc ^ raw[i]) & 0xff];
    }
    crc = (crc ^ -1) >>> 0;

    // Local Header (30 bytes + name length)
    const locHdr = Buffer.alloc(30 + nameBuf.length);
    locHdr.writeUInt32LE(0x04034b50, 0); // signature
    locHdr.writeUInt16LE(20, 4); // version needed
    locHdr.writeUInt16LE(0, 6); // flags
    locHdr.writeUInt16LE(method, 8); // compression method
    locHdr.writeUInt16LE(0, 10); // mod time
    locHdr.writeUInt16LE(0, 12); // mod date
    locHdr.writeUInt32LE(crc, 14); // crc32
    locHdr.writeUInt32LE(compressed.length, 18); // comp size
    locHdr.writeUInt32LE(raw.length, 22); // uncomp size
    locHdr.writeUInt16LE(nameBuf.length, 26); // name length
    locHdr.writeUInt16LE(0, 28); // extra length
    nameBuf.copy(locHdr, 30);

    const locOffset = offset;
    localHeaders.push(locHdr, compressed);
    offset += locHdr.length + compressed.length;

    // Central Directory Header (46 bytes + name length)
    const cdHdr = Buffer.alloc(46 + nameBuf.length);
    cdHdr.writeUInt32LE(0x02014b50, 0); // signature
    cdHdr.writeUInt16LE(20, 4); // version made by
    cdHdr.writeUInt16LE(20, 6); // version needed
    cdHdr.writeUInt16LE(0, 8); // flags
    cdHdr.writeUInt16LE(method, 10); // method
    cdHdr.writeUInt16LE(0, 12); // mod time
    cdHdr.writeUInt16LE(0, 14); // mod date
    cdHdr.writeUInt32LE(crc, 16); // crc32
    cdHdr.writeUInt32LE(compressed.length, 20); // comp size
    cdHdr.writeUInt32LE(raw.length, 24); // uncomp size
    cdHdr.writeUInt16LE(nameBuf.length, 28); // name len
    cdHdr.writeUInt16LE(0, 30); // extra len
    cdHdr.writeUInt16LE(0, 32); // comment len
    cdHdr.writeUInt16LE(0, 34); // disk number
    cdHdr.writeUInt16LE(0, 36); // internal attr
    cdHdr.writeUInt32LE(0, 38); // external attr
    cdHdr.writeUInt32LE(locOffset, 42); // relative offset of local header
    nameBuf.copy(cdHdr, 46);

    cdHeaders.push(cdHdr);
  }

  const cdOffset = offset;
  const cdBuf = Buffer.concat(cdHeaders);
  const cdSize = cdBuf.length;

  // End of Central Directory Record (22 bytes)
  const eocd = Buffer.alloc(22);
  eocd.writeUInt32LE(0x06054b50, 0); // EOCD signature
  eocd.writeUInt16LE(0, 4); // disk number
  eocd.writeUInt16LE(0, 6); // disk with CD
  eocd.writeUInt16LE(entries.length, 8); // entries on disk
  eocd.writeUInt16LE(entries.length, 10); // total entries
  eocd.writeUInt32LE(cdSize, 12); // CD size
  eocd.writeUInt32LE(cdOffset, 16); // CD offset
  eocd.writeUInt16LE(0, 20); // comment length

  return Buffer.concat([...localHeaders, cdBuf, eocd]);
}

// Test Runner
const tests = [];
function test(name, fn) {
  tests.push({ name, fn });
}

/* -------------------------------------------------------------------------- */
/* Test 1: Path normalization and stem/extension extraction                   */
/* -------------------------------------------------------------------------- */
test("normalizePath, extractFilename, extractStem, extractExtension", () => {
  // normalizePath
  assert.equal(normalizePath(""), "");
  assert.equal(normalizePath(null), "");
  assert.equal(normalizePath("sub\\dir\\part.CATPart"), "sub/dir/part.CATPart");
  assert.equal(normalizePath("./models/part.CATPart"), "models/part.CATPart");
  assert.equal(normalizePath("/root//sub///file.CATPart"), "root/sub/file.CATPart");

  // extractFilename
  assert.equal(extractFilename("part.CATPart"), "part.CATPart");
  assert.equal(extractFilename("a/b/c/part.CATPart"), "part.CATPart");
  assert.equal(extractFilename(""), "");

  // extractStem
  assert.equal(extractStem("ac1.CATPart"), "ac1");
  assert.equal(extractStem("AC1.CATPART"), "AC1");
  assert.equal(extractStem("Root.CATProduct"), "Root");
  assert.equal(extractStem("assembly.catproduct"), "assembly");
  assert.equal(extractStem("Part11.1.CATPart"), "Part11.1");
  assert.equal(extractStem("lower_teeth_blend.CATPart"), "lower_teeth_blend");
  assert.equal(extractStem("no_ext"), "no_ext");

  // extractExtension
  assert.equal(extractExtension("part.CATPart"), ".catpart");
  assert.equal(extractExtension("sub/prod.CATProduct"), ".catproduct");
  assert.equal(extractExtension("ARCHIVE.ZIP"), ".zip");
  assert.equal(extractExtension("noextension"), "");
});

/* -------------------------------------------------------------------------- */
/* Test 2: VirtualFileCatalog 248/382 Same-Repo Stem-Join Resolution          */
/* -------------------------------------------------------------------------- */
test("VirtualFileCatalog exact and case-insensitive stem matching", () => {
  const catalog = new VirtualFileCatalog();

  // Register synthetic parts and products
  catalog.register({
    name: "ac1.CATPart",
    path: "models/ac1.CATPart",
    bytes: new Uint8Array([1, 2, 3]),
  });
  catalog.register({
    name: "AC2.CATPart",
    path: "parts/AC2.CATPart",
    bytes: new Uint8Array([4, 5, 6]),
  });
  catalog.register({
    name: "Part11.1.CATPart",
    path: "sub/Part11.1.CATPart",
    bytes: new Uint8Array([7, 8]),
  });
  catalog.register({
    name: "lower_teeth_blend.CATPart",
    path: "lower_teeth_blend.CATPart",
    bytes: new Uint8Array([9]),
  });
  catalog.register({
    name: "EngineAssembly.CATProduct",
    path: "EngineAssembly.CATProduct",
    bytes: new Uint8Array([10, 11]),
  });

  // Verify catalog counts
  assert.equal(catalog.size, 5);
  assert.equal(catalog.parts.length, 4);
  assert.equal(catalog.products.length, 1);

  // 1. Exact stem matching
  const ac1 = catalog.resolvePart("ac1");
  assert.ok(ac1, "Should resolve exact stem 'ac1'");
  assert.equal(ac1.name, "ac1.CATPart");
  assert.equal(ac1.stem, "ac1");

  const part11 = catalog.resolvePart("Part11.1");
  assert.ok(part11, "Should resolve exact stem 'Part11.1'");
  assert.equal(part11.name, "Part11.1.CATPart");

  // 2. Exact filename matching
  assert.equal(catalog.resolvePart("ac1.CATPart")?.name, "ac1.CATPart");
  assert.equal(catalog.resolvePart("Part11.1.CATPart")?.name, "Part11.1.CATPart");

  // 3. Exact path matching
  assert.equal(catalog.resolvePart("models/ac1.CATPart")?.name, "ac1.CATPart");
  assert.equal(catalog.resolvePart("sub/Part11.1.CATPart")?.name, "Part11.1.CATPart");

  // 4. Case-insensitive stem matching
  const ac1Upper = catalog.resolvePart("AC1");
  assert.ok(ac1Upper, "Should resolve uppercase 'AC1' to lowercase 'ac1.CATPart'");
  assert.equal(ac1Upper.name, "ac1.CATPart");

  const ac2Lower = catalog.resolvePart("ac2");
  assert.ok(ac2Lower, "Should resolve lowercase 'ac2' to uppercase 'AC2.CATPart'");
  assert.equal(ac2Lower.name, "AC2.CATPart");

  const part11Lower = catalog.resolvePart("part11.1");
  assert.ok(part11Lower, "Should resolve 'part11.1' case-insensitively");
  assert.equal(part11Lower.name, "Part11.1.CATPart");

  const lowerTeethUpper = catalog.resolvePart("LOWER_TEETH_BLEND");
  assert.ok(lowerTeethUpper, "Should resolve 'LOWER_TEETH_BLEND' case-insensitively");
  assert.equal(lowerTeethUpper.name, "lower_teeth_blend.CATPart");

  // 5. Case-insensitive filename & path matching
  assert.equal(catalog.resolvePart("MODELS/AC1.CATPART")?.name, "ac1.CATPart");
  assert.equal(catalog.resolvePart("ac2.catpart")?.name, "AC2.CATPart");

  // 6. Non-existent parts return null
  assert.equal(catalog.resolvePart("missing_part"), null);
  assert.equal(catalog.resolvePart("EngineAssembly"), null, "Product should not resolve as part");
  assert.equal(catalog.resolvePart(""), null);
  assert.equal(catalog.resolvePart(null), null);

  // 7. Product resolution
  const prod = catalog.resolveProduct("EngineAssembly");
  assert.ok(prod, "Should resolve product by exact stem");
  assert.equal(prod.name, "EngineAssembly.CATProduct");

  const prodLower = catalog.resolveProduct("engineassembly.catproduct");
  assert.ok(prodLower, "Should resolve product case-insensitively");
  assert.equal(prodLower.name, "EngineAssembly.CATProduct");
});

/* -------------------------------------------------------------------------- */
/* Test 3: Instance Resolution & Tracking                                     */
/* -------------------------------------------------------------------------- */
test("Instance resolution, status tracking, and listUnresolved", () => {
  const catalog = new VirtualFileCatalog();
  catalog.register({ name: "ac1.CATPart", bytes: new Uint8Array([1]) });
  catalog.register({ name: "bracket.CATPart", bytes: new Uint8Array([2]) });

  // Resolve existing instance
  const r1 = catalog.resolveInstance({
    part_number: "ac1",
    instance_name: "ac1.1",
  });
  assert.equal(r1.status, STATUS_RESOLVED);
  assert.equal(r1.resolved, true);
  assert.equal(r1.instanceId, "ac1.1");
  assert.equal(r1.partNumber, "ac1");
  assert.ok(r1.entry);

  // Resolve missing instance
  const r2 = catalog.resolveInstance({
    part_number: "bolt_m8",
    instance_name: "bolt_m8.1",
  });
  assert.equal(r2.status, STATUS_UNRESOLVED);
  assert.equal(r2.resolved, false);
  assert.equal(r2.instanceId, "bolt_m8.1");
  assert.equal(r2.partNumber, "bolt_m8");
  assert.equal(r2.entry, null);

  // Check getInstanceStatus
  assert.equal(catalog.getInstanceStatus("ac1.1")?.status, STATUS_RESOLVED);
  assert.equal(catalog.getInstanceStatus("bolt_m8.1")?.status, STATUS_UNRESOLVED);

  // Test listUnresolved and listResolved
  const required = ["ac1", "bracket", "bolt_m8", "nut_m8", "AC1.CATPart"];
  const unresolved = catalog.listUnresolved(required);
  assert.deepEqual(unresolved.sort(), ["bolt_m8", "nut_m8"].sort());

  const resolved = catalog.listResolved(required);
  assert.deepEqual(resolved.sort(), ["ac1", "bracket", "AC1.CATPart"].sort());
});

/* -------------------------------------------------------------------------- */
/* Test 4: Catalog Summary & Lifecycle                                        */
/* -------------------------------------------------------------------------- */
test("Catalog summary and clear lifecycle", () => {
  const catalog = new VirtualFileCatalog();
  catalog.register({ name: "p1.CATPart", bytes: new Uint8Array([1]) });
  catalog.register({ name: "p2.CATPart", bytes: new Uint8Array([2]) });
  catalog.register({ name: "root.CATProduct", bytes: new Uint8Array([3]) });

  catalog.resolveInstance("p1");
  catalog.resolveInstance("p2");
  catalog.resolveInstance("missing");

  const s1 = catalog.summary();
  assert.equal(s1.total, 3);
  assert.equal(s1.parts, 2);
  assert.equal(s1.products, 1);
  assert.equal(s1.instancesTracked, 3);

  // Clear catalog
  catalog.clear();
  const s2 = catalog.summary();
  assert.equal(s2.total, 0);
  assert.equal(s2.parts, 0);
  assert.equal(s2.products, 0);
  assert.equal(s2.instancesTracked, 0);
  assert.equal(catalog.resolvePart("p1"), null);
});

/* -------------------------------------------------------------------------- */
/* Test 5: ZIP Signature and File Detection                                   */
/* -------------------------------------------------------------------------- */
test("isZipSignature and isZipFile detection", () => {
  // Signatures
  assert.equal(isZipSignature(new Uint8Array([0x50, 0x4b, 0x03, 0x04])), true);
  assert.equal(isZipSignature(new Uint8Array([0x50, 0x4b, 0x05, 0x06])), true);
  assert.equal(isZipSignature(new Uint8Array([0x50, 0x4b, 0x07, 0x08])), true);
  assert.equal(isZipSignature(new Uint8Array([0x50, 0x4b, 0x01, 0x02])), false);
  assert.equal(isZipSignature(new Uint8Array([1, 2, 3, 4])), false);
  assert.equal(isZipSignature(new Uint8Array([0x50, 0x4b])), false);
  assert.equal(isZipSignature(null), false);

  // File objects / names
  assert.equal(isZipFile("archive.zip"), true);
  assert.equal(isZipFile("ARCHIVE.ZIP"), true);
  assert.equal(isZipFile({ name: "models.zip" }), true);
  assert.equal(isZipFile({ type: "application/zip" }), true);
  assert.equal(isZipFile({ type: "application/x-zip-compressed" }), true);
  assert.equal(isZipFile("model.CATPart"), false);
  assert.equal(isZipFile(null), false);
});

/* -------------------------------------------------------------------------- */
/* Test 6: In-Memory Zero-Dependency ZIP Extraction                           */
/* -------------------------------------------------------------------------- */
test("unpackZip decompresses STORED and DEFLATE entries with nested paths", async () => {
  const zipBuffer = createSyntheticZip([
    { path: "README.txt", content: "Assembly instructions", method: 0 }, // Stored
    { path: "assembly/root.CATProduct", content: "<product>root</product>", method: 8 }, // Deflated
    { path: "assembly/parts/p1.CATPart", content: "part1_payload", method: 8 },
    { path: "assembly/parts/P2.CATPart", content: "part2_payload", method: 8 },
    { path: "__MACOSX/._root.CATProduct", content: "dummy macos metadata", method: 0 }, // Should be skipped
    { path: "assembly/empty_dir/", content: "", method: 0 }, // Should be skipped
  ]);

  const extracted = await unpackZip(new Uint8Array(zipBuffer));
  assert.equal(extracted.length, 4, "Should extract exactly 4 non-metadata files");

  const byPath = new Map(extracted.map((f) => [f.path, f]));

  // Verify Stored entry
  const readme = byPath.get("README.txt");
  assert.ok(readme);
  assert.equal(new TextDecoder().decode(readme.bytes), "Assembly instructions");
  assert.equal(readme.size, Buffer.from("Assembly instructions").length);

  // Verify Deflated entries
  const root = byPath.get("assembly/root.CATProduct");
  assert.ok(root);
  assert.equal(new TextDecoder().decode(root.bytes), "<product>root</product>");

  const p1 = byPath.get("assembly/parts/p1.CATPart");
  assert.ok(p1);
  assert.equal(new TextDecoder().decode(p1.bytes), "part1_payload");

  const p2 = byPath.get("assembly/parts/P2.CATPart");
  assert.ok(p2);
  assert.equal(new TextDecoder().decode(p2.bytes), "part2_payload");
});

/* -------------------------------------------------------------------------- */
/* Test 7: Root Product Resolution & Disambiguation (§4.3)                    */
/* -------------------------------------------------------------------------- */
test("selectRootProduct single auto-select and multi-candidate heuristic", () => {
  // Case 0: No products
  const empty = selectRootProduct([]);
  assert.equal(empty.rootProduct, null);
  assert.deepEqual(empty.candidates, []);

  // Case 1: Exactly 1 product -> auto-select
  const single = [new CatalogEntry({ name: "Car.CATProduct" })];
  const rSingle = selectRootProduct(single);
  assert.equal(rSingle.rootProduct?.name, "Car.CATProduct");
  assert.equal(rSingle.candidates.length, 1);

  // Case 2: Multiple products -> heuristic selection
  const multiple = [
    new CatalogEntry({ name: "Bracket_SubAssembly.CATProduct", path: "sub/Bracket_SubAssembly.CATProduct" }),
    new CatalogEntry({ name: "Vehicle_IsRoot.CATProduct", path: "Vehicle_IsRoot.CATProduct" }),
    new CatalogEntry({ name: "Wheel_Unit.CATProduct", path: "sub/Wheel_Unit.CATProduct" }),
  ];
  const rMulti = selectRootProduct(multiple);
  assert.equal(rMulti.candidates.length, 3);
  assert.equal(
    rMulti.rootProduct?.name,
    "Vehicle_IsRoot.CATProduct",
    "Heuristic should prioritize product with 'IsRoot' at root level"
  );

  // Case 3: Override via preferredRoot
  const rPref = selectRootProduct(multiple, null, { preferredRoot: "Wheel_Unit" });
  assert.equal(rPref.rootProduct?.name, "Wheel_Unit.CATProduct");
});

/* -------------------------------------------------------------------------- */
/* Test 8: Ingestion Coordinator ingestFiles Master Pipeline                  */
/* -------------------------------------------------------------------------- */
test("ingestFiles processes files, unpacks ZIPs, and returns IngestionResult", async () => {
  // Construct a ZIP buffer containing 1 product and 2 parts
  const zipBuffer = createSyntheticZip([
    { path: "chassis/RootAssembly.CATProduct", content: "product_data", method: 8 },
    { path: "chassis/parts/ac1.CATPart", content: "part1_data", method: 8 },
    { path: "chassis/parts/AC2.CATPart", content: "part2_data", method: 8 },
  ]);

  const rawZipFile = {
    name: "chassis.zip",
    bytes: new Uint8Array(zipBuffer),
  };

  const result = await ingestFiles(rawZipFile);

  assert.ok(result.catalog instanceof VirtualFileCatalog);
  assert.equal(result.hasRootProduct, true);
  assert.equal(result.isMultiProduct, false);
  assert.equal(result.rootProduct?.name, "RootAssembly.CATProduct");
  assert.equal(result.candidates.length, 1);
  assert.equal(result.partsCount, 2);
  assert.equal(result.productsCount, 1);

  // Verify that the catalog can resolve parts unpacked from the ZIP
  const ac1 = result.catalog.resolvePart("ac1");
  assert.ok(ac1, "Should resolve ac1 from ZIP");
  assert.equal(new TextDecoder().decode(ac1.bytes), "part1_data");

  const ac2 = result.catalog.resolvePart("AC2");
  assert.ok(ac2, "Should resolve AC2 from ZIP");
  assert.equal(new TextDecoder().decode(ac2.bytes), "part2_data");

  // Case: Ingesting parts without any product
  const partsOnly = await ingestFiles([
    { name: "part_a.CATPart", bytes: new Uint8Array([1]) },
    { name: "part_b.CATPart", bytes: new Uint8Array([2]) },
  ]);
  assert.equal(partsOnly.hasRootProduct, false);
  assert.equal(partsOnly.rootProduct, null);
  assert.equal(partsOnly.partsCount, 2);
  assert.equal(partsOnly.productsCount, 0);
});

/* -------------------------------------------------------------------------- */
/* Test 9: IngestionCoordinator Class Lifecycle                               */
/* -------------------------------------------------------------------------- */
test("IngestionCoordinator manages persistent catalog state", async () => {
  const coord = new IngestionCoordinator();

  const fileList = [
    { name: "MainAssembly.CATProduct", bytes: new Uint8Array([1]) },
    { name: "AuxAssembly.CATProduct", bytes: new Uint8Array([2]) },
    { name: "p1.CATPart", bytes: new Uint8Array([3]) },
  ];

  const res = await coord.ingest(fileList);
  assert.equal(res.isMultiProduct, true);
  assert.equal(coord.rootProduct?.name, "MainAssembly.CATProduct");

  // Switch root product
  const switched = coord.setRootProduct("AuxAssembly");
  assert.equal(switched?.name, "AuxAssembly.CATProduct");
  assert.equal(coord.rootProduct?.name, "AuxAssembly.CATProduct");

  // Clear coordinator
  coord.clear();
  assert.equal(coord.rootProduct, null);
  assert.equal(coord.catalog.size, 0);
});

/* -------------------------------------------------------------------------- */
/* Test 10: Recursive Directory Traversal & Batching Reader                   */
/* -------------------------------------------------------------------------- */
test("traverseFileSystemEntry handles nested directories and batching reader", async () => {
  // Mock FileEntry
  function mockFile(name, fullPath, content) {
    return {
      isFile: true,
      isDirectory: false,
      name,
      fullPath,
      file(cb) {
        cb({
          name,
          size: content.length,
          arrayBuffer: async () => Buffer.from(content).buffer,
        });
      },
    };
  }

  // Mock DirectoryEntry with batching (returning in 2 batches of 1 then empty)
  const f1 = mockFile("p1.CATPart", "/assembly/p1.CATPart", "p1");
  const f2 = mockFile("p2.CATPart", "/assembly/sub/p2.CATPart", "p2");

  const subDir = {
    isFile: false,
    isDirectory: true,
    name: "sub",
    fullPath: "/assembly/sub",
    createReader() {
      let callCount = 0;
      return {
        readEntries(cb) {
          if (callCount === 0) {
            callCount++;
            cb([f2]);
          } else {
            cb([]);
          }
        },
      };
    },
  };

  const rootDir = {
    isFile: false,
    isDirectory: true,
    name: "assembly",
    fullPath: "/assembly",
    createReader() {
      let callCount = 0;
      return {
        readEntries(cb) {
          if (callCount === 0) {
            callCount++;
            cb([f1]);
          } else if (callCount === 1) {
            callCount++;
            cb([subDir]);
          } else {
            cb([]);
          }
        },
      };
    },
  };

  const walked = await traverseFileSystemEntry(rootDir);
  assert.equal(walked.length, 2);
  assert.equal(walked[0].path, "assembly/p1.CATPart");
  assert.equal(walked[1].path, "assembly/sub/p2.CATPart");
});

/* -------------------------------------------------------------------------- */
/* Test 11: scanDataTransfer and scanFileInput                                */
/* -------------------------------------------------------------------------- */
test("scanDataTransfer and scanFileInput handle standard DOM inputs", async () => {
  // Mock DataTransfer with items
  const mockDt = {
    items: [
      {
        kind: "file",
        webkitGetAsEntry: () => ({
          isFile: true,
          isDirectory: false,
          name: "bracket.CATPart",
          fullPath: "/models/bracket.CATPart",
          file: (cb) => cb({ name: "bracket.CATPart", size: 100 }),
        }),
      },
      {
        kind: "string", // non-file item, should be ignored
      },
    ],
  };

  const scanned = await scanDataTransfer(mockDt);
  assert.equal(scanned.length, 1);
  assert.equal(scanned[0].path, "models/bracket.CATPart");
  assert.equal(scanned[0].name, "bracket.CATPart");

  // Mock FileInput
  const mockInput = {
    files: [
      { name: "part1.CATPart", webkitRelativePath: "folder/part1.CATPart", size: 50 },
      { name: "part2.CATPart", webkitRelativePath: "", size: 60 },
    ],
  };
  const fromInput = scanFileInput(mockInput);
  assert.equal(fromInput.length, 2);
  assert.equal(fromInput[0].path, "folder/part1.CATPart");
  assert.equal(fromInput[1].path, "part2.CATPart");
});

/* -------------------------------------------------------------------------- */
/* Test 12: Corrupt ZIP handling and edge cases                               */
/* -------------------------------------------------------------------------- */
test("unpackZip rejects invalid or corrupted zip archives cleanly", async () => {
  // Too small
  await assert.rejects(
    async () => unpackZip(new Uint8Array([1, 2, 3])),
    /too small/i
  );

  // Missing EOCD signature
  const nonZip = new Uint8Array(100);
  await assert.rejects(
    async () => unpackZip(nonZip),
    /End of Central Directory/i
  );

  // Empty zip (valid structure, 0 entries)
  const emptyZip = createSyntheticZip([]);
  const extracted = await unpackZip(new Uint8Array(emptyZip));
  assert.equal(extracted.length, 0);
});

/* -------------------------------------------------------------------------- */
/* Test 13: CatalogEntry.getBytes Lazy Loading                                */
/* -------------------------------------------------------------------------- */
test("CatalogEntry.getBytes reads bytes lazily from file or buffer", async () => {
  // Eager bytes
  const e1 = new CatalogEntry({
    name: "eager.CATPart",
    bytes: new Uint8Array([1, 2, 3]),
  });
  const b1 = await e1.getBytes();
  assert.deepEqual(Array.from(b1), [1, 2, 3]);

  // Lazy arrayBuffer from File/Blob mock
  const e2 = new CatalogEntry({
    name: "lazy.CATPart",
    file: {
      name: "lazy.CATPart",
      size: 4,
      async arrayBuffer() {
        return new Uint8Array([4, 5, 6, 7]).buffer;
      },
    },
  });
  assert.equal(e2.bytes, null, "Bytes should be null initially before getBytes");
  const b2 = await e2.getBytes();
  assert.deepEqual(Array.from(b2), [4, 5, 6, 7]);
  assert.ok(e2.bytes instanceof Uint8Array, "Bytes should be cached after first read");
});

/* -------------------------------------------------------------------------- */
/* Test 14: setupDropZone, setupFileInput, and preventWindowDropDefaults      */
/* -------------------------------------------------------------------------- */
test("setupDropZone, setupFileInput, and preventWindowDropDefaults attach listeners", async () => {
  const events = new Map();
  const mockElement = {
    classList: {
      add: (c) => {},
      remove: (c) => {},
    },
    addEventListener(name, handler) {
      events.set(name, handler);
    },
    removeEventListener(name, handler) {
      events.delete(name);
    },
  };

  let ingested = null;
  const cleanup = setupDropZone(mockElement, {
    onIngest(res) {
      ingested = res;
    },
  });

  assert.ok(events.has("dragover"));
  assert.ok(events.has("dragleave"));
  assert.ok(events.has("drop"));

  // Fire mock drop event
  const dropHandler = events.get("drop");
  await dropHandler({
    preventDefault() {},
    dataTransfer: {
      files: [{ name: "quick.CATPart", size: 10 }],
    },
  });

  assert.ok(ingested);
  assert.equal(ingested.partsCount, 1);

  // Test cleanup
  cleanup();
  assert.equal(events.size, 0);

  // Test preventWindowDropDefaults
  const winEvents = new Map();
  const mockWin = {
    addEventListener: (n, h) => winEvents.set(n, h),
    removeEventListener: (n, h) => winEvents.delete(n),
  };
  const cleanupWin = preventWindowDropDefaults(mockWin);
  assert.ok(winEvents.has("dragover"));
  assert.ok(winEvents.has("drop"));
  cleanupWin();
  assert.equal(winEvents.size, 0);
});

/* -------------------------------------------------------------------------- */
/* Execute All Tests                                                          */
/* -------------------------------------------------------------------------- */
async function run() {
  console.log("Running VirtualFileCatalog & Ingestion Coordinator test suite...\n");
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
  console.log(`\nAll ${passed}/${tests.length} tests passed successfully.`);
}

run();
