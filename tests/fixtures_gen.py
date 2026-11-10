"""Seeded synthetic fixture generator for CATIA V5-shaped files (A2, #12).

The real corpus is gitignored and never present in CI (Spec A #8,
ADR-0003); every test assembles its fixtures from the documented
structures instead. This module is the single generator: byte assembly
primitives, a seeded deterministic front end, and the named corrupted
variants that cover the fitness error-classification classes.

Structural facts exercised (evidence notes, byte ranges):

- 32-byte header: magic ``V5_CFV2\\0`` (bytes 0-8), big-endian dword8
  (bytes 8-12), big-endian dword12 (bytes 12-16, == file size - dword8,
  law H1), eight ``0xFF`` bytes (bytes 16-24) — or, in the dual-region
  variant, two more big-endian dwords — zeros (bytes 24-32).
- Container-name table records (B1 record layout, little-endian): the
  40-byte prefix with constants f5=``0x006c0001``, f6=2, f8=0 and the
  f9 anchor ``0x20810002``, two NUL-terminated ASCII names zero-padded
  to a multiple of 8 (law T1), the constant 8-byte tail, and a 16-byte
  GUID.
- CNEXTINFOS version-marker line after the table region.
- Writer registration block ``[0x4e][u32le 17]"DASSAULT-SYSTEMES"[u32le
  5]"CATIA"[u32le 6]"041803"`` in the payload (B1).
- Trailer: the last 36 bytes, seven big-endian dwords A..G (A=1,
  C==D, E=0, G==dword12) plus the ``CB__END\\0`` marker (B1).
- Identity block with the save-time document name (C3, payload-blocks).

Determinism: the generator is a pure function of ``(kind, seed,
variant)`` — same inputs, byte-identical output. The seed drives the
GUIDs, the payload filler and the table padding only; the structural
skeleton (names, framing, laws) is fixed so every fixture stays
genuine-shaped.

Corrupted variants (fitness classification classes, #14/#26; measured
by ``tests/test_fixturegen.py``):

- ``bad-magic``        -> missing-invariant (``magic-v5-cfv2`` fires).
- ``truncated-table``  -> the record region is cut mid-record with
  dword12 re-patched to the truncated size but the trailer's G field
  left stale: the H1 chain breaks and ``tail-region-chain`` fires
  (missing-invariant). A chain-*consistent* truncation classifies
  clean — partial tables are a legitimate corpus shape (B1/C1b) —
  which the test suite pins as documented parser behavior.
- ``missing-trailer``  -> parser reports ``trailer: null``; legitimate
  shape (262 corpus files), so the expected classification is clean.
- ``junk-payload``     -> random filler in the opaque payload region;
  the parser does not interpret it, so the expected class is clean
  (robustness against false failures).
- ``oversized-dword``  -> header dword8 > file size; missing-invariant
  (``header-dword-below-file-size`` fires).
- ``short-file``       -> fewer than 32 bytes; the parser refuses with
  ValueError, i.e. the ``crash`` class (corpus junk behavior, #26).

Valid variants: ``None`` (ff x 8 header) and ``dual-region`` (the
146-file header generation) — both clean.

Geometry-bearing variants (G4, #32): the payload carries a synthetic
CATStdCont-shaped nested V5_CFV2 stream store (G1/G2/G3 decode model)
whose known f32le pool, ``01 06`` count group and 0x4a/0x4c facet
records mirror the corpus worked example ``10b9ae4a3cd58298`` — the
20 x 100 x 60 box whose six facet records decode to its six faces only
under LEXICOGRAPHIC RANK references (G3 claim F2b), here split into 4 x
0x4a triangle-strip faces and 2 x 0x4c closed-polygon faces (12
triangles, a closed oriented manifold). The pool's walk order is the
corpus box's deliberately non-lexicographic order so the export exercises
the lex-rank mapping (correction C8).

- ``geometry``                  -> valid; exports 12 triangles, closed
  manifold, no warnings.
- ``geometry-open-shell``       -> valid-shaped; the x=20 face record is
  dropped (G3 F6's real sheet-like open shells) and one well-formed
  0x41 triangle-list record carries a degenerate all-same-rank loop
  (skipped per F7): exports 10 triangles with the ``open-shell``,
  ``unresolved-facet-family`` and ``degenerate-triangles-skipped``
  warning classes.
- ``geometry-bad-nested-magic`` -> the nested store's V5_CFV2 magic is
  corrupted in place: no store header, and the CB0001 catalog is not
  re-validatable as a header-less store either -> ``missing-geometry-
  store``.
- ``geometry-truncated-pool``   -> the pool group's count field says 8
  but only 6 vertex records precede the facet region -> ``malformed-
  pool-group`` (G2 P2g violation).
- ``geometry-out-of-range-refs``-> one facet reference points past the
  pool -> ``undecoded-variant`` (G3 open question 2).
- ``geometry-nan-coords``       -> one pool vertex carries a NaN f32le
  coordinate -> ``malformed-pool-vertex`` (G2 P3 violation).
- ``geometry-missing-facet-payload`` -> every facet record is cut after
  its count byte, before its references: no parse survives the tiling
  law -> ``undecoded-variant`` (no exportable facet content).
- ``geometry-composite-index-space`` -> an ``01 02`` edge-group wrapper
  (G3 F8's 6-byte ``02 02 (u16be)(u16be)`` records) marks the composite
  index space -> ``undecoded-variant`` (open question 1).
"""

from __future__ import annotations

import random
import struct

MAGIC = b"V5_CFV2\x00"
CNEXTINFOS_LINE = (
    b"NOTHING-CNEXTINFOS-UpdateVersion-StreamBlock-SafeEarlyBlock-"
    b"StrongEarly&V5R21SP0HF0 built on 01-15-2014.20.00"
)
TRAILER_MARKER = b"CB__END\x00"

#: Constants of the B1 record layout (all little-endian prefix fields).
RECORD_F5 = 0x006C0001
RECORD_ANCHOR = 0x20810002  # f9, bytes 02 00 81 20 little-endian
RECORD_TAIL = b"\x03\x00\xf7\x00\x03\x00\x00\x00"
TABLE_ID_CONTAINERS = 0x00030001

#: Record name pairs by kind: CATPrtCont present -> kind "part" per the
#: kind-law evidence note (K1); CATProdCont/CATMechProdCont without
#: CATPrtCont -> product.
KIND_RECORDS: dict[str, tuple[tuple[str, str], ...]] = {
    "part": (
        ("CATPrtCont", "CATProdCont"),
        ("CATFeatCont", "CATPrtCont"),
        ("CGMGeom", "CATContainer"),
    ),
    "product": (
        ("CATProdCont", "CATContainer"),
        ("CATMechProdCont", "CATContainer"),
    ),
}

VALID_VARIANTS = (None, "dual-region", "geometry", "geometry-open-shell")
CORRUPTED_VARIANTS = (
    "bad-magic",
    "truncated-table",
    "missing-trailer",
    "junk-payload",
    "oversized-dword",
    "short-file",
    # Geometry-bearing corrupted variants (G4, #32): nested-store level.
    "geometry-bad-nested-magic",
    "geometry-composite-index-space",
    "geometry-missing-facet-payload",
    "geometry-nan-coords",
    "geometry-out-of-range-refs",
    "geometry-truncated-pool",
)
GEOMETRY_VARIANTS = ("geometry", "geometry-open-shell") + (
    "geometry-bad-nested-magic",
    "geometry-composite-index-space",
    "geometry-missing-facet-payload",
    "geometry-nan-coords",
    "geometry-out-of-range-refs",
    "geometry-truncated-pool",
)

# --- nested-store geometry (G4, #32) -----------------------------------
# The nested V5_CFV2 store's byte vocabulary (G1/G2/G3 evidence notes).
NESTED_CB0001 = b"CATIA_V5 CB0001\x00"
NESTED_FULL_WRAP = b"\x10\x24\x04\xff\xff\x00\x00\x00"  # G2 P1g wrapper
NESTED_VREC = b"\x05\x08\x01"  # 15-byte vertex record prefix (G2 P1)
NESTED_POOL_SUBKIND = b"\x01\x06"  # vertex pool group (G2 P1g)
NESTED_EDGE_SUBKIND = b"\x01\x02"  # edge group (G3 F8: composite space)
NESTED_CATALOG_LEN = 52  # CB0001 magic (16 B) + 36 B trailer

#: The corpus box 10b9ae4a3cd58298's pool in walk order (G2 worked
#: example): the 8 corners of the 20 x 100 x 60 mm box, deliberately NOT
#: in lexicographic order.
GEOMETRY_POOL_WALK = (
    (0.0, 0.0, 0.0),
    (20.0, 0.0, 0.0),
    (0.0, 100.0, 0.0),
    (20.0, 100.0, 0.0),
    (0.0, 100.0, 60.0),
    (20.0, 100.0, 60.0),
    (0.0, 0.0, 60.0),
    (20.0, 0.0, 60.0),
)

#: lex[rank] = walk position: the lexicographic ranks of (x, y, z) over
#: GEOMETRY_POOL_WALK (G3 claim F2 / correction C8). Facet references
#: are ranks into this map.
GEOMETRY_LEX = (0, 6, 2, 4, 1, 7, 3, 5)

#: The six box faces as facet records: (marker, outward normal, lex-rank
#: refs). The four 0x4a strip faces reuse the corpus box's verified
#: reference tuples (G2 worked example / G3 F2b, 12/12 sign-positive);
#: the two x-faces are 0x4c closed polygons in ring order (G3 F4: the
#: Newell normal equals the stored normal, sign +).
GEOMETRY_FACES = (
    (0x4A, (0.0, 0.0, -1.0), (4, 0, 6, 2)),
    (0x4A, (0.0, 1.0, 0.0), (6, 2, 7, 3)),
    (0x4A, (0.0, 0.0, 1.0), (7, 3, 5, 1)),
    (0x4A, (0.0, -1.0, 0.0), (5, 1, 4, 0)),
    (0x4C, (-1.0, 0.0, 0.0), (0, 1, 3, 2)),
    (0x4C, (1.0, 0.0, 0.0), (4, 6, 7, 5)),
)


def ceil8(n: int) -> int:
    return ((n + 7) // 8) * 8


def container_record(
    name: str,
    parent_name: str,
    *,
    stream_id: int = 1,
    weight: int = 11,
    table_id: int = TABLE_ID_CONTAINERS,
    index: int = 1,
    guid: bytes = bytes(16),
) -> bytes:
    """One container-name table record in the B1 layout (law T1/T3)."""
    names = name.encode("ascii") + b"\x00" + parent_name.encode("ascii") + b"\x00"
    area = ceil8(len(names))
    prefix = struct.pack(
        "<8I",
        stream_id,
        weight,
        table_id,
        index,
        RECORD_F5,
        2,  # f6 constant
        0,  # f7 (small value; 0 is the corpus mode)
        0,  # f8 constant
    )
    prefix += struct.pack("<2I", RECORD_ANCHOR, area // 8 + 1)  # f9, f10 (law T1)
    return prefix + names + b"\x00" * (area - len(names)) + RECORD_TAIL + guid


def registration_block(tag: int = 0x4E) -> bytes:
    """The writer registration block (B1): tag + length-prefixed strings."""
    return (
        bytes([tag])
        + struct.pack("<I", 17)
        + b"DASSAULT-SYSTEMES"
        + struct.pack("<I", 5)
        + b"CATIA"
        + struct.pack("<I", 6)
        + b"041803"
    )


def storage_property_block(name1: bytes, name2: bytes = b"") -> bytes:
    """One CATStorageProperty block with the given name1/name2 (B3/C3).

    Byte layout observed in the corpus (docs/evidence/
    2026-11-08-units-names-probe.md): the B3 block header, name1
    tag34-framed and 0x9f-terminated, then the name2 field
    ``a0 02 00 00 00 00 34 <len> <ascii> 9f`` (empty: ``34 00 9f``),
    then the ``3b 10`` marker with the block's 16 zero bytes (null GUID)
    and a trailing ``9f``. The G1 nested-store probe (decode_nested_
    store.valid_blocks) recognizes a block by this header.
    """
    block = b"\x34\x12" + b"CATStorageProperty"
    block += b"\x80\x01\x00\x00\x00\x00\x22\x0c\x00\x00\x00"
    block += b"\x34\x01\x01\x00" + b"\x34\x10" + b"CATUnicodeString"
    block += b"\xa0\x02\x00\x00\x00\x00\x34" + bytes([len(name1)]) + name1 + b"\x9f"
    block += b"\xa0\x02\x00\x00\x00\x00\x34"
    block += bytes([len(name2)]) + name2 + b"\x9f"
    block += b"\x3b\x10" + bytes(16) + b"\x9f"
    return block


def catia_identity_block(name2: bytes = b"") -> bytes:
    """One CATStorageProperty identity block named CATIA (C3 phase A
    claims D1/D2) — :func:`storage_property_block` with name1 CATIA."""
    return storage_property_block(b"CATIA", name2)


def build_catpart(
    *,
    magic: bytes = MAGIC,
    header_dword: int = 0x0001_0000,
    records: tuple[tuple[str, str], ...] = KIND_RECORDS["part"],
    with_marker: bool = True,
    with_trailer: bool = True,
    with_registration: bool = True,
    dual_region: bool = False,
    payload: bytes = b"\x12\x34\x56\x78" * 8,
    pad_before_table: int = 0x700,
    identity_name2: str | bytes | None = None,
) -> bytes:
    """Assemble a minimal, structurally genuine CATIA V5-shaped file.

    ``dual_region=True`` emits the 146-file variant header (two more
    big-endian dwords at 16-24 instead of the eight ``0xFF`` bytes, B1
    evidence note). The header dword12 and the trailer G field are the
    law-H1 chain values (dword8 + dword12 == file size, G == dword12);
    a deliberately malformed ``header_dword`` larger than the file gets
    dword12 = 0 so the fixture itself stays well-formed at the byte
    level while violating the invariant under test.

    ``identity_name2`` (C3 phase A) appends a CATStorageProperty
    identity block to the payload: a ``str`` is stored as its ASCII
    name2 (the save-time document name), ``bytes`` verbatim (for
    malformed-walk fixtures), ``None`` (default) omits the block
    entirely (the parser must then report a null document_name).
    """
    header = magic[:8].ljust(8, b"\x00")
    header += struct.pack(">I", header_dword)
    header += b"\x00" * 4  # dword12 patched below, big-endian
    if dual_region:
        # Two more big-endian dwords instead of the ff x8 marker; the
        # corpus values are region offsets the parser reports as-is.
        header += struct.pack(">II", 0x0000_0010, 0x0000_0020)
    else:
        header += b"\xff" * 8
    header += b"\x00" * 8
    assert len(header) == 32

    body = [header, b"\x00" * pad_before_table]
    for i, (name, parent_name) in enumerate(records):
        body.append(
            container_record(
                name,
                parent_name,
                stream_id=1 + 5 * i,
                index=i + 1,
                guid=struct.pack(">QQ", 0, 0x1AE0 + i),
            )
        )
    if with_marker:
        body.append(b"\x00\x00\x00\x00" + CNEXTINFOS_LINE)
    if identity_name2 is not None:
        if isinstance(identity_name2, str):
            identity_name2 = identity_name2.encode("ascii")
        body.append(catia_identity_block(identity_name2))
    body.append(payload)

    registration_offset = 0
    if with_trailer and with_registration:
        registration_offset = sum(len(part) for part in body)
        body.append(registration_block())

    data = b"".join(body)
    final_size = len(data) + (36 if with_trailer else 0)
    dword12 = final_size - header_dword
    if not 0 <= dword12 <= 0xFFFFFFFF:
        dword12 = 0
    data = data[:12] + struct.pack(">I", dword12) + data[16:]

    if with_trailer:
        # Trailer model (B1): A=1, B=registration offset, C==D, E=0,
        # F=0, G==dword12, then the CB__END\0 marker.
        data += (
            struct.pack(
                ">7I",
                1,
                registration_offset,
                0xE7,
                0xE7,
                0,
                0,
                dword12,
            )
            + TRAILER_MARKER
        )
    return data


def _facet_record(marker: int, normal, refs: tuple[int, ...]) -> bytes:
    """One facet record in the G3 grammar (F1): 4-byte header ``01 <mk>
    <ty=1> ff``, u32le n, the 12-byte normal when the marker carries
    one, one loop-count byte (k=1, summing to n — the tiling law needs
    count bytes for n > 0, as the corpus 0x41 records show), then the
    u8 lexicographic-rank references."""
    rec = bytes([0x01, marker, 0x01, 0xFF]) + struct.pack("<I", len(refs))
    if normal is not None:
        rec += struct.pack("<fff", *normal)
    return rec + bytes([len(refs)]) + bytes(refs)


def _geometry_box_edges_lex() -> tuple[tuple[int, int], ...]:
    """The box's 12 edges as lex-rank pairs (F8: the 01 02 edge table's
    endpoints are lex-adjacent pool vertices)."""
    return (
        (0, 1), (0, 2), (0, 4), (1, 3), (1, 5), (2, 3),
        (2, 6), (3, 7), (4, 5), (4, 6), (5, 7), (6, 7),
    )


def _geometry_store(variant: str) -> bytes:
    """The nested V5_CFV2 stream store: 32-byte header (big-endian
    dword8 = catalog offset, dword12 = catalog tail length, N2), body,
    minimal catalog (CB0001 magic + 36 B trailer satisfying the G1 N6
    laws: CB__END, C == D, G == tail length) and the 126 B inter-block
    tail with the writer registration block (N9)."""
    faces = list(GEOMETRY_FACES)
    if variant == "geometry-out-of-range-refs":
        marker, normal, refs = faces[0]
        faces[0] = (marker, normal, (4, 0, 6, 200))  # 200 >= pool size 8
    if variant == "geometry-open-shell":
        faces = faces[:5]  # drop the x=20 face: real sheet-like shell (F6)

    pool_walk = list(GEOMETRY_POOL_WALK)
    if variant == "geometry-nan-coords":
        # G2 P3 violation: NaN f32le coordinate in the 4th walked vertex.
        x, y, z = pool_walk[3]
        pool_walk[3] = (float("nan"), y, z)
    vertices = pool_walk
    if variant == "geometry-truncated-pool":
        # G2 P2g violation: count field 8, only 6 records before facets.
        vertices = pool_walk[:6]

    body_parts = [
        NESTED_FULL_WRAP
        + NESTED_POOL_SUBKIND
        + bytes([8])
        + b"".join(NESTED_VREC + struct.pack("<fff", *v) for v in vertices)
    ]
    if variant == "geometry-composite-index-space":
        # G3 F8's edge-table sketch: 6-byte `02 02 (u16be)(u16be)`
        # records — the composite index-space marker (open question 1).
        body_parts.append(
            NESTED_FULL_WRAP
            + NESTED_EDGE_SUBKIND
            + b"".join(
                b"\x02\x02" + struct.pack(">HH", a, b)
                for a, b in _geometry_box_edges_lex()
            )
        )
    for marker, normal, refs in faces:
        if variant == "geometry-missing-facet-payload":
            # Cut after the count byte, before the references: no
            # (width, k) parse survives the tiling law.
            rec = bytes([0x01, marker, 0x01, 0xFF]) + struct.pack("<I", len(refs))
            rec += struct.pack("<fff", *normal) + bytes([len(refs), 0, 0])
            body_parts.append(rec)
        else:
            body_parts.append(_facet_record(marker, normal, refs))
    if variant == "geometry-open-shell":
        # A well-formed 0x41 triangle-list record (F9 byte law n == 3*ty)
        # whose single loop repeats one rank: the strip reading is
        # degenerate and skipped (F7), the marker surfaces as an
        # unresolved facet family.
        body_parts.append(_facet_record(0x41, None, (0, 0, 0)))
    body = b"".join(body_parts)

    catalog_len = NESTED_CATALOG_LEN
    d8n = 32 + len(body)
    nested_magic = b"V5_CFV3\x00" if variant == "geometry-bad-nested-magic" else MAGIC
    header = (
        nested_magic
        + struct.pack(">II", d8n, catalog_len)
        + b"\xff" * 8
        + b"\x00" * 8
    )
    catalog = NESTED_CB0001 + struct.pack(
        ">7I", 1, 0, 0xE7, 0xE7, 0, 0, catalog_len
    ) + TRAILER_MARKER
    tail126 = registration_block() + b"\x00" * (126 - 41)
    return header + body + catalog + tail126


def _geometry_payload(variant: str) -> bytes:
    """The CATStdCont block + property preamble + nested store.

    The preamble lands the store origin at block + 250 (G1 N1h: the
    248..268 window covers 1,051/1,056 corpus header stores)."""
    preamble = 250 - len(storage_property_block(b"CATStdCont", b"CATContainer"))
    return (
        storage_property_block(b"CATStdCont", b"CATContainer")
        + b"\x00" * preamble
        + _geometry_store(variant)
    )


def build_fixture(
    kind: str = "part",
    *,
    seed: int = 0,
    variant: str | None = None,
    document_name: str | None = None,
) -> bytes:
    """Seeded deterministic fixture: same ``(kind, seed, variant)`` ->
    byte-identical output.

    ``kind`` selects the record table ("part" or "product", kind-law
    K1). The seed drives GUIDs, payload filler and table padding only —
    the structural skeleton is fixed. ``variant`` selects a valid shape
    (``None``, ``"dual-region"``, or a geometry-bearing nested-store
    variant) or one named corrupted variant (see the module docstring
    for the expected fitness/export classification of each).
    ``document_name`` stores a save-time name in the identity block
    (the C3 ``document_name`` claim; ``None`` omits the block).
    """
    if kind not in KIND_RECORDS:
        raise ValueError(f"unknown kind: {kind!r}")
    if variant not in VALID_VARIANTS + CORRUPTED_VARIANTS:
        raise ValueError(f"unknown variant: {variant!r}")

    if variant in GEOMETRY_VARIANTS:
        # Nested-store payload (G4 #32): the seed drives only the table
        # padding, as in A2; the store bytes are a pure function of the
        # variant so the expected pool/facet decode stays fixed. The
        # small plausible header dword keeps the H1 chain (A2's choice).
        return build_catpart(
            header_dword=0x0000_0100,
            payload=_geometry_payload(variant),
            pad_before_table=0x600 + (seed % 8) * 8,
            identity_name2=document_name,
        )

    rng = random.Random(seed)
    records = KIND_RECORDS[kind]
    pad_before_table = 0x600 + (seed % 8) * 8
    payload = bytes(rng.randrange(256) for _ in range(64)) if variant == "junk-payload" else struct.pack(
        ">Q", rng.getrandbits(64)
    ) * 8
    rng.getrandbits(64)  # burned to keep later draws on the writer's stream

    data = build_catpart(
        magic=b"X5_BADMAG" if variant == "bad-magic" else MAGIC,
        # A plausible small dword8 (the corpus tail is 3-124 KB; the
        # fixtures are ~2-3 KB, so it must sit below the file size for
        # the H1 chain to hold — only the oversized variant breaks it).
        header_dword=0xFFFF_FFFF if variant == "oversized-dword" else 0x0000_0100,
        records=records,
        dual_region=variant == "dual-region",
        with_trailer=variant != "missing-trailer",
        payload=payload,
        pad_before_table=pad_before_table,
        identity_name2=document_name,
    )

    if variant == "short-file":
        return data[:16]  # below the 32-byte header: parser refuses (crash class)
    if variant == "truncated-table":
        # Cut into the first record, after the 40-byte prefix but before
        # the names area ends, so the record model cannot complete. The
        # trailer (kept whole) carries the ORIGINAL dword12 in its G
        # field while the header dword12 is re-patched to the truncated
        # size: the H1 chain breaks by construction (tail-region-chain).
        first_record_start = 32 + pad_before_table
        cut = first_record_start + 48
        data = data[:cut] + data[-36:]
        # Re-patch header dword12 for the truncated size (the stale G
        # is the corruption under test).
        dword12 = len(data) - 0x0000_0100
        if not 0 <= dword12 <= 0xFFFFFFFF:
            dword12 = 0
        data = data[:12] + struct.pack(">I", dword12) + data[16:]
    return data
