"""Synthetic multi-file assembly fixture generator and test harness (Spec F #45 §9.1).

Design Authority: `docs/specs/phase6-assembly-viewer-spec.md` (§9.1).
Prior Fixture Generator: `tests/fixtures_gen.py` (Phase 5 A2 fixture discipline).
Pairing Laws & Constraints: `docs/evidence/2026-11-14-p2-pool-pairing.md`,
`scripts/triage/p26_instance_binding.py`, and `port/src/product/`.

This module generates 4 distinct synthetic assembly fixtures exercising the 4 canonical
classification states defined in the declared P4 Assembly Bar:
1. `fixture_assembly_canonical`: 1 root `.CATProduct` + 3 `.CATPart` files (`Base`, `Arm`, `Bolt`).
   Exercises `Resolved & Placed` with known non-zero translation ([10.0, 20.0, 30.0]) and 90-degree rotation.
2. `fixture_assembly_identity`: 1 root `.CATProduct` with no `_Position` tokens + 2 `.CATPart` files (`Plate`, `Cover`).
   Exercises `Resolved & Identity`.
3. `fixture_assembly_partial`: 1 root `.CATProduct` declaring 4 parts (`Housing`, `Gear`, `Shaft`, `Pin`),
   but user supplies only 2 `.CATPart` files (`Housing`, `Gear`).
   Exercises `Unresolved Part` (verifies nodes are rendered in tree with warning badge, never omitted).
4. `fixture_assembly_undecodable`: 1 root `.CATProduct` carrying legacy undecodable placement tags.
   Exercises `Undecodable Placement` (verifies anti-masking invariant: rejected from identity fallback).

Packaging utilities:
- `package_to_zip`: package any fixture into a `.zip` archive bytes/file for client-side ingestion testing.
- `write_to_directory`: write fixture files to a directory structure on disk.

Python Reference Inspection & Classification:
- `read_product_structure`: decodes `.CATProduct` structure pool, instances, and transforms.
- `classify_assembly`: evaluates instance resolution against uploaded files into the 4 canonical states.
"""

from __future__ import annotations

import dataclasses
import io
import math
import os
import re
import struct
import zipfile
from pathlib import Path
from typing import Any

# --- Binary Framing Constants & Signatures -----------------------------------

MAGIC = b"V5_CFV2\x00"
CNEXTINFOS_LINE = (
    b"NOTHING-CNEXTINFOS-UpdateVersion-StreamBlock-SafeEarlyBlock-"
    b"StrongEarly&V5R21SP0HF0 built on 01-15-2014.20.00"
)
TRAILER_MARKER = b"CB__END\x00"

RECORD_F5 = 0x006C0001
RECORD_ANCHOR = 0x20810002
RECORD_TAIL = b"\x03\x00\xf7\x00\x03\x00\x00\x00"
TABLE_ID_CONTAINERS = 0x00030001

FRAME_MARK = b"\xfe\x7c"
FRAME_TAG_POOL = 0x02

RECORD_129B_MAGIC_R20 = b"\xb5\x13\x27\x79"
RECORD_129B_MAGIC_R20_ALT = b"\xb5\x03\x27\x79"
SEPARATOR_BYTE = 0x80

# `_Position` value-layer headers (P3 position-layer segmentation). The 8d81
# matrix that follows is an explicit instance position, an identity attribute
# frame (constraint/connector placeholder, never bound), or the product-root
# position (excluded).
POSITION_EXPLICIT_HEADER = b"\xe8\xf4\x07\x37"
POSITION_IDENTITY_HEADER = b"\xe9\xf4\x07\x04\x37"
POSITION_ROOT_HEADER = b"\xe8\xe0\x07\x37"
IDENTITY_TRANSFORM = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]

POOL_TOKENS: tuple[str, ...] = (
    "ASMPRODUCT",
    "PRDREP",
    "PRDBAGREP",
    "_Component",
    "_PartNumber",
    "_RefProduct",
    "_InstanceName",
    "_Position",
    "CONNECTOR",
    "CONNECTION",
    "IsRoot",
    "_Version",
    "_Reps",
    "3DIC",
)

CLASS_TOKENS: frozenset[str] = frozenset({
    "ASMPRODUCT",
    "PRDREP",
    "PRDBAGREP",
    "CONNECTOR",
    "CONNECTION",
    "CONNECTORSFAMILY",
    "ASMGEOMETRY",
    "PUBLISHING",
    "IsRoot",
    "ElecLogTerm",
    "ElecLogicalTermination",
    "ElecCavity",
    "AdaptativeSupport",
    "R15HEADER",
})

CONSTRAINT_PREFIXES: tuple[str, ...] = (
    "coincidence",
    "coïncidence",
    "cx_coincidence",
    "surface contact",
    "contact surfacique",
    "cx_surface contact",
    "offset",
    "décalage",
    "fix",
    "fixe",
    "angle",
    "contact linéique",
    "line contact",
    "contact ponctuel",
    "point contact",
    "parallelism",
    "parallélisme",
    "perpendicularity",
    "perpendicularité",
)

DOT_SHAPE = re.compile(r"^.+\.\d{1,4}$")
COLON_SHAPE = re.compile(r"^.+:\d{1,4}$")
USCORE_SHAPE = re.compile(r"^.+_\d{1,4}$")
R15_ENTRY = re.compile(rb"\xfe\xfe?[\x01-\x7f]([\x20-\x7e]{3,60})\x80")
BINARY_SENTINEL = "\x00binary"

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

# --- Data Structures ---------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class AssemblyFixture:
    """A synthetic multi-file assembly fixture."""

    name: str
    product_filename: str
    product_bytes: bytes
    part_files: dict[str, bytes]
    expected_classifications: dict[str, str]
    transforms: dict[str, dict[str, Any]] = dataclasses.field(default_factory=dict)
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)

    @property
    def files(self) -> dict[str, bytes]:
        """All files in the fixture: root product plus all component parts."""
        d = {self.product_filename: self.product_bytes}
        d.update(self.part_files)
        return d


# --- Container & Framing Byte Assembly Primitives ----------------------------


def ceil8(n: int) -> int:
    """Round up to the nearest multiple of 8."""
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
        0,  # f7
        0,  # f8 constant
    )
    prefix += struct.pack("<2I", RECORD_ANCHOR, area // 8 + 1)
    return prefix + names + b"\x00" * (area - len(names)) + RECORD_TAIL + guid


def registration_block(tag: int = 0x4E) -> bytes:
    """Writer registration block (B1): tag + length-prefixed strings."""
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
    """One CATStorageProperty block with the given name1/name2 (B3/C3)."""
    block = b"\x34\x12" + b"CATStorageProperty"
    block += b"\x80\x01\x00\x00\x00\x00\x22\x0c\x00\x00\x00"
    block += b"\x34\x01\x01\x00" + b"\x34\x10" + b"CATUnicodeString"
    block += b"\xa0\x02\x00\x00\x00\x00\x34" + bytes([len(name1)]) + name1 + b"\x9f"
    block += b"\xa0\x02\x00\x00\x00\x00\x34"
    block += bytes([len(name2)]) + name2 + b"\x9f"
    block += b"\x3b\x10" + bytes(16) + b"\x9f"
    return block


def catia_identity_block(name2: bytes = b"") -> bytes:
    """One CATStorageProperty identity block named CATIA (C3 phase A)."""
    return storage_property_block(b"CATIA", name2)


def build_catfile(
    *,
    records: tuple[tuple[str, str], ...] = KIND_RECORDS["product"],
    payload: bytes = b"",
    identity_name2: str | bytes | None = None,
    header_dword: int = 0x0000_0100,
    pad_before_table: int = 0x600,
) -> bytes:
    """Assemble a minimal, structurally genuine CATIA V5-shaped container file."""
    header = MAGIC[:8].ljust(8, b"\x00")
    header += struct.pack(">I", header_dword)
    header += b"\x00" * 4  # dword12 patched below
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
    body.append(b"\x00\x00\x00\x00" + CNEXTINFOS_LINE)
    if identity_name2 is not None:
        if isinstance(identity_name2, str):
            identity_name2 = identity_name2.encode("ascii")
        body.append(catia_identity_block(identity_name2))
    body.append(payload)

    registration_offset = sum(len(part) for part in body)
    body.append(registration_block())

    data = b"".join(body)
    final_size = len(data) + 36
    dword12 = final_size - header_dword
    if not 0 <= dword12 <= 0xFFFFFFFF:
        dword12 = 0
    data = data[:12] + struct.pack(">I", dword12) + data[16:]

    trailer = (
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
    return data + trailer


# --- Pool & Transform Record Generators ---------------------------------------


def encode_short_item(text: str | bytes) -> bytes:
    """Law B SHORT item: <u8 len> <len-1 payload bytes>."""
    b = text.encode("utf-8") if isinstance(text, str) else text
    return bytes([len(b) + 1]) + b


def encode_long_item(payload: str | bytes) -> bytes:
    """00-escape LONG item: <00> <u32le n> <n payload bytes>."""
    b = payload.encode("utf-8") if isinstance(payload, str) else payload
    return b"\x00" + struct.pack("<I", len(b)) + b


def encode_structure_pool_record(
    items_payload: bytes, tb_bytes: bytes = b"\xbf"
) -> bytes:
    """Frame items payload into fe 7c 02 record satisfying the Length Law:

    ln == 6 + tb + pool_span.
    """
    tb = len(tb_bytes)
    pool_span = len(items_payload)
    ln = 6 + tb + pool_span
    return b"\xfe\x7c\x02" + struct.pack("<I", ln) + tb_bytes + items_payload


def encode_129b_transform_record(
    translation: tuple[float, float, float] | list[float],
    quaternion: tuple[float, float, float, float] | list[float],
    *,
    object_id: int = 1,
    flags: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0),
    bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0),
    magic: bytes = RECORD_129B_MAGIC_R20,
) -> bytes:
    """Encode one 129-byte full transform record (Spec §2.4).

    Structure:
    - 0x00..0x04: Tag/Magic (b"\\xb5\\x13\\x27\\x79" or b"\\xb5\\x03\\x27\\x79")
    - 0x04..0x08: u32le OmbObjectTag ID
    - 0x08: Invariant separator 0x80
    - 0x09..0x21: Translation [tx, ty, tz] (3 x f64le)
    - 0x21..0x41: Rotation unit quaternion [qw, qx, qy, qz] (4 x f64le), w-first
    - 0x41..0x61: Flags (4 x f64le)
    - 0x61..0x81: Bounding box sentinels / extents (4 x f64le)
    """
    tx, ty, tz = translation
    qw, qx, qy, qz = quaternion
    rec = bytearray(magic[:4])
    rec += struct.pack("<I", object_id)
    rec.append(SEPARATOR_BYTE)
    rec += struct.pack("<3d", tx, ty, tz)
    rec += struct.pack("<4d", qw, qx, qy, qz)
    rec += struct.pack("<4d", *flags)
    rec += struct.pack("<4d", *bbox)
    assert len(rec) == 129
    return bytes(rec)


def encode_r15_reference_entry(name: str | bytes) -> bytes:
    """R15 legacy attribute-reference entry: fe <len> <name> 80 <5B> e8 <4B>."""
    b = name.encode("ascii") if isinstance(name, str) else name
    return (
        b"\xfe"
        + bytes([len(b) + 1])
        + b
        + b"\x80\x00\x00\x00\x00\x00\xe8\x00\x00\x00\x00"
    )


# --- Geometry Generation Helper for Component Parts ---------------------------


# --- Standalone Box Geometry Generator (Clean Manifold Box, A2 Discipline) ---

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

GEOMETRY_FACES = (
    (0x4A, (0.0, 0.0, -1.0), (4, 0, 6, 2)),
    (0x4A, (0.0, 1.0, 0.0), (6, 2, 7, 3)),
    (0x4A, (0.0, 0.0, 1.0), (7, 3, 5, 1)),
    (0x4A, (0.0, -1.0, 0.0), (5, 1, 4, 0)),
    (0x4C, (-1.0, 0.0, 0.0), (0, 1, 3, 2)),
    (0x4C, (1.0, 0.0, 0.0), (4, 6, 7, 5)),
)

NESTED_CB0001 = b"CATIA_V5 CB0001\x00"
NESTED_FULL_WRAP = b"\x10\x24\x04\xff\xff\x00\x00\x00"
NESTED_VREC = b"\x05\x08\x01"
NESTED_POOL_SUBKIND = b"\x01\x06"
NESTED_CATALOG_LEN = 52


def _facet_rec(marker: int, normal: tuple[float, float, float] | None, refs: tuple[int, ...]) -> bytes:
    rec = bytes([0x01, marker, 0x01, 0xFF]) + struct.pack("<I", len(refs))
    if normal is not None:
        rec += struct.pack("<fff", *normal)
    return rec + bytes([len(refs)]) + bytes(refs)


def build_box_geometry_payload() -> bytes:
    """Build a standalone CATStdCont nested store holding a 20x100x60 closed manifold box."""
    body_parts = [
        NESTED_FULL_WRAP
        + NESTED_POOL_SUBKIND
        + bytes([len(GEOMETRY_POOL_WALK)])
        + b"".join(NESTED_VREC + struct.pack("<fff", *v) for v in GEOMETRY_POOL_WALK)
    ]
    for marker, normal, refs in GEOMETRY_FACES:
        body_parts.append(_facet_rec(marker, normal, refs))
    body = b"".join(body_parts)

    catalog_len = NESTED_CATALOG_LEN
    d8n = 32 + len(body)
    header = MAGIC + struct.pack(">II", d8n, catalog_len) + b"\xff" * 8 + b"\x00" * 8
    catalog = NESTED_CB0001 + struct.pack(">7I", 1, 0, 0xE7, 0xE7, 0, 0, catalog_len) + TRAILER_MARKER
    tail126 = registration_block() + b"\x00" * (126 - 41)
    geom_store = header + body + catalog + tail126

    preamble = 250 - len(storage_property_block(b"CATStdCont", b"CATContainer"))
    return storage_property_block(b"CATStdCont", b"CATContainer") + b"\x00" * preamble + geom_store


def generate_synthetic_part(
    name: str,
    *,
    seed: int = 42,
) -> bytes:
    """Generate a genuine-shaped, geometry-bearing .CATPart file."""
    return build_catfile(
        records=KIND_RECORDS["part"],
        identity_name2=name,
        payload=build_box_geometry_payload(),
        pad_before_table=0x600 + (seed % 8) * 8,
    )


# --- The 4 Canonical Synthetic Assembly Fixtures (§9.1) -----------------------


def fixture_assembly_canonical(seed: int = 42) -> AssemblyFixture:
    """Fixture 1: 1 root `.CATProduct` + 3 `.CATPart` files (`Base`, `Arm`, `Bolt`).

    Exercises `Resolved & Placed` with known non-zero translation ([10.0, 20.0, 30.0])
    and 90-degree rotation around the Z axis.
    """
    product_name = "CanonicalAssembly"
    product_filename = f"{product_name}.CATProduct"

    # Part files with geometry
    part_names = ("Base", "Arm", "Bolt")
    part_files: dict[str, bytes] = {
        f"{pn}.CATPart": generate_synthetic_part(pn, seed=seed + i)
        for i, pn in enumerate(part_names)
    }

    # Structure pool items: Identity Triples with _Position
    items = bytearray()
    items += encode_short_item("ASMPRODUCT")
    items += encode_short_item(product_name)
    for pn in part_names:
        inst_name = f"{pn}.1"
        items += encode_short_item("_Component")
        items += encode_short_item(pn)
        items += encode_short_item("_InstanceName")
        items += encode_short_item(inst_name)
        items += encode_short_item("_Position")
    items += encode_short_item("IsRoot")

    framed_pool = encode_structure_pool_record(bytes(items))

    # Known transforms:
    # 1. Base.1: at identity origin
    t_base = (0.0, 0.0, 0.0)
    q_base = (1.0, 0.0, 0.0, 0.0)

    # 2. Arm.1: known non-zero translation [10.0, 20.0, 30.0] and 90-deg rotation around Z
    t_arm = (10.0, 20.0, 30.0)
    angle_rad = math.pi / 2.0
    qw = math.cos(angle_rad / 2.0)
    qz = math.sin(angle_rad / 2.0)
    q_arm = (qw, 0.0, 0.0, qz)

    # 3. Bolt.1: non-zero offset
    t_bolt = (10.0, 25.0, 35.0)
    q_bolt = (1.0, 0.0, 0.0, 0.0)

    transforms_meta = {
        "Base.1": {"t": list(t_base), "q": list(q_base)},
        "Arm.1": {"t": list(t_arm), "q": list(q_arm)},
        "Bolt.1": {"t": list(t_bolt), "q": list(q_bolt)},
    }

    # Encode 129-byte transform records
    recs = bytearray()
    recs += encode_129b_transform_record(t_base, q_base, object_id=101)
    recs += encode_129b_transform_record(t_arm, q_arm, object_id=102)
    recs += encode_129b_transform_record(t_bolt, q_bolt, object_id=103)

    ctor_block = (
        storage_property_block(b"CATCtorProxyCont", b"CATContainer") + bytes(recs)
    )

    product_bytes = build_catfile(
        records=KIND_RECORDS["product"],
        identity_name2=product_name,
        payload=framed_pool + ctor_block,
    )

    expected_classifications = {
        "Base.1": "placed",
        "Arm.1": "placed",
        "Bolt.1": "placed",
    }

    return AssemblyFixture(
        name="fixture_assembly_canonical",
        product_filename=product_filename,
        product_bytes=product_bytes,
        part_files=part_files,
        expected_classifications=expected_classifications,
        transforms=transforms_meta,
        metadata={"seed": seed, "binding_mode": "sequential_1to1"},
    )


def fixture_assembly_identity(seed: int = 42) -> AssemblyFixture:
    """Fixture 2: 1 root `.CATProduct` with no `_Position` tokens + 2 `.CATPart` files (`Plate`, `Cover`).

    Exercises `Resolved & Identity`. Both components exist and resolve, but the format
    carries no placement attributes, falling back legitimately to origin identity.
    """
    product_name = "IdentityAssembly"
    product_filename = f"{product_name}.CATProduct"

    part_names = ("Plate", "Cover")
    part_files: dict[str, bytes] = {
        f"{pn}.CATPart": generate_synthetic_part(pn, seed=seed + i)
        for i, pn in enumerate(part_names)
    }

    # Structure pool items: NO _Position tokens
    items = bytearray()
    items += encode_short_item("ASMPRODUCT")
    items += encode_short_item(product_name)
    for pn in part_names:
        inst_name = f"{pn}.1"
        items += encode_short_item("_Component")
        items += encode_short_item(pn)
        items += encode_short_item("_InstanceName")
        items += encode_short_item(inst_name)
    items += encode_short_item("IsRoot")

    framed_pool = encode_structure_pool_record(bytes(items))

    product_bytes = build_catfile(
        records=KIND_RECORDS["product"],
        identity_name2=product_name,
        payload=framed_pool,
    )

    expected_classifications = {
        "Plate.1": "identity",
        "Cover.1": "identity",
    }

    return AssemblyFixture(
        name="fixture_assembly_identity",
        product_filename=product_filename,
        product_bytes=product_bytes,
        part_files=part_files,
        expected_classifications=expected_classifications,
        metadata={"seed": seed, "has_position_tokens": False},
    )


def fixture_assembly_partial(seed: int = 42) -> AssemblyFixture:
    """Fixture 3: 1 root `.CATProduct` declaring 4 parts (`Housing`, `Gear`, `Shaft`, `Pin`),

    but user supplies only 2 `.CATPart` files (`Housing`, `Gear`).
    Exercises `Unresolved Part` (verifies nodes are rendered in tree with warning badge, never omitted).
    """
    product_name = "PartialAssembly"
    product_filename = f"{product_name}.CATProduct"

    declared_parts = ("Housing", "Gear", "Shaft", "Pin")
    supplied_parts = ("Housing", "Gear")

    # Only supply 2 part files
    part_files: dict[str, bytes] = {
        f"{pn}.CATPart": generate_synthetic_part(pn, seed=seed + i)
        for i, pn in enumerate(supplied_parts)
    }

    # Structure pool declares all 4 parts
    items = bytearray()
    items += encode_short_item("ASMPRODUCT")
    items += encode_short_item(product_name)
    for pn in declared_parts:
        inst_name = f"{pn}.1"
        items += encode_short_item("_Component")
        items += encode_short_item(pn)
        items += encode_short_item("_InstanceName")
        items += encode_short_item(inst_name)
        items += encode_short_item("_Position")
    items += encode_short_item("IsRoot")

    framed_pool = encode_structure_pool_record(bytes(items))

    # Transform records for all 4 declared instances
    recs = bytearray()
    recs += encode_129b_transform_record(
        (0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0), object_id=201
    )
    recs += encode_129b_transform_record(
        (15.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0), object_id=202
    )
    recs += encode_129b_transform_record(
        (30.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0), object_id=203
    )
    recs += encode_129b_transform_record(
        (45.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0), object_id=204
    )

    ctor_block = (
        storage_property_block(b"CATCtorProxyCont", b"CATContainer") + bytes(recs)
    )

    product_bytes = build_catfile(
        records=KIND_RECORDS["product"],
        identity_name2=product_name,
        payload=framed_pool + ctor_block,
    )

    expected_classifications = {
        "Housing.1": "placed",
        "Gear.1": "placed",
        "Shaft.1": "unresolved",
        "Pin.1": "unresolved",
    }

    return AssemblyFixture(
        name="fixture_assembly_partial",
        product_filename=product_filename,
        product_bytes=product_bytes,
        part_files=part_files,
        expected_classifications=expected_classifications,
        metadata={
            "seed": seed,
            "declared_parts": list(declared_parts),
            "supplied_parts": list(supplied_parts),
            "missing_parts": ["Shaft", "Pin"],
        },
    )


def fixture_assembly_undecodable(seed: int = 42) -> AssemblyFixture:
    """Fixture 4: 1 root `.CATProduct` carrying legacy undecodable placement tags.

    Exercises `Undecodable Placement` (verifies anti-masking invariant: rejected from identity fallback).
    """
    product_name = "UndecodableAssembly"
    product_filename = f"{product_name}.CATProduct"

    part_names = ("Bracket",)
    part_files: dict[str, bytes] = {
        f"{pn}.CATPart": generate_synthetic_part(pn, seed=seed) for pn in part_names
    }

    # Carrier with R15 legacy reference tags (\xfe <len> <tag> \x80 ... \xe8 ...)
    # No framed fe 7c 02 pool record, triggering R15-ref classification
    legacy_payload = bytearray()
    legacy_tags = (
        "ASMPRODUCT",
        "_PartNumber",
        "_InstanceName",
        "_Position",
        "Bracket",
        "Bracket.1",
        "Bracket.2",
    )
    for tag in legacy_tags:
        legacy_payload += encode_r15_reference_entry(tag)

    product_bytes = build_catfile(
        records=KIND_RECORDS["product"],
        identity_name2=product_name,
        payload=bytes(legacy_payload),
    )

    expected_classifications = {
        "Bracket.1": "undecodable",
        "Bracket.2": "undecodable",
    }

    return AssemblyFixture(
        name="fixture_assembly_undecodable",
        product_filename=product_filename,
        product_bytes=product_bytes,
        part_files=part_files,
        expected_classifications=expected_classifications,
        metadata={"seed": seed, "pool_form": "r15-ref", "undecodable_tags": True},
    )


# --- Packaging Utilities -----------------------------------------------------


def package_to_zip(
    fixture: AssemblyFixture | dict[str, bytes],
    out_path: str | Path | None = None,
) -> bytes:
    """Package an assembly fixture into a standard ZIP archive.

    If out_path is specified, writes the archive to disk.
    Returns the raw ZIP archive bytes in all cases.
    """
    files = fixture.files if isinstance(fixture, AssemblyFixture) else fixture
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for filename in sorted(files.keys()):
            zf.writestr(filename, files[filename])

    zip_bytes = buf.getvalue()
    if out_path is not None:
        p = Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(zip_bytes)
    return zip_bytes


def write_to_directory(
    fixture: AssemblyFixture | dict[str, bytes],
    dir_path: str | Path,
) -> Path:
    """Write an assembly fixture to a directory structure on disk.

    Creates parent directories if necessary and writes each file verbatim.
    Returns the resolved Path of the directory.
    """
    files = fixture.files if isinstance(fixture, AssemblyFixture) else fixture
    p = Path(dir_path).resolve()
    p.mkdir(parents=True, exist_ok=True)
    for filename, content in files.items():
        file_path = p / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content)
    return p


# --- Python Reference Reader & Assembly Classifier ---------------------------


def is_token(t: str) -> bool:
    """Check if item text represents an attribute name token."""
    return t.startswith("_")


def is_class_token(t: str) -> bool:
    """Check if item text represents an object class anchor token."""
    return t in CLASS_TOKENS


def is_constraint_name(name: str) -> bool:
    """Check if name represents an assembly constraint rather than a part instance."""
    prefix = name.split(".")[0].strip().lower()
    return any(prefix.startswith(cst) for cst in CONSTRAINT_PREFIXES)


def walk_chain(data: bytes, start: int, end: int) -> list[tuple[str, bytes]]:
    """Decode typed item chain in [start, end)."""
    items = []
    i = start
    while i < end:
        lead = data[i]
        if lead == 0x00:
            if i + 5 > end:
                return []
            str_len = struct.unpack_from("<I", data, i + 1)[0]
            if str_len == 0 or i + 5 + str_len > end:
                return []
            items.append(("L", data[i + 5 : i + 5 + str_len]))
            i += 5 + str_len
        else:
            total_len = lead
            if total_len == 0 or i + total_len > end:
                return []
            items.append(("S", data[i + 1 : i + total_len]))
            i += total_len
    return items


def scan_structure_pool(data: bytes) -> tuple[int, int, list[str]] | None:
    """Scan and decode the framed structure pool if present."""
    candidates = []
    i = 0
    while i < len(data) - 7:
        if data[i : i + 2] == FRAME_MARK and data[i + 2] == FRAME_TAG_POOL:
            ln = struct.unpack_from("<I", data, i + 3)[0]
            for tb in (0, 1, 2):
                payload_start = i + 7 + tb
                payload_end = i + 1 + ln
                if (
                    int(ln) == 6 + tb + (payload_end - payload_start)
                    and payload_end <= len(data)
                ):
                    chain = walk_chain(data, payload_start, payload_end)
                    if chain:
                        texts = [
                            payload.decode("utf-8", "replace")
                            for _, payload in chain
                        ]
                        tok_count = sum(1 for t in texts if t in POOL_TOKENS)
                        if tok_count >= 2:
                            candidates.append((tok_count, len(texts), texts))
            i += 6
        i += 1

    if not candidates:
        return None
    # Pick candidate with max vocabulary tokens, then max items
    candidates.sort(key=lambda c: (c[0], c[1]), reverse=True)
    return candidates[0]


def r15_reference_count(data: bytes) -> int:
    """Count R15 legacy attribute reference entries."""
    hits = 0
    for m in R15_ENTRY.finditer(data):
        name_bytes = m.group(1)
        name_len = len(name_bytes)
        off = m.start(1)
        if off > 0 and data[off - 1] == name_len + 1:
            try:
                name_str = name_bytes.decode("ascii")
                if name_str.startswith("_") or name_str in POOL_TOKENS:
                    hits += 1
            except UnicodeDecodeError:
                pass
    return hits


def parse_129b_transform_records(data: bytes) -> list[dict[str, Any]]:
    """Scan and parse all valid 129-byte transform records in data."""
    records = []
    i = 0
    n = len(data)
    while i <= n - 129:
        if (
            (data[i : i + 2] == b"\xb5\x13" or data[i : i + 2] == b"\xb5\x03")
            and data[i + 2] == 0x27
            and data[i + 8] == SEPARATOR_BYTE
        ):
            oid = struct.unpack_from("<I", data, i + 4)[0]
            doubles = struct.unpack_from("<15d", data, i + 9)
            if all(math.isfinite(d) for d in doubles):
                t = doubles[0:3]
                q = doubles[3:7]
                norm2 = q[0] ** 2 + q[1] ** 2 + q[2] ** 2 + q[3] ** 2
                if abs(norm2 - 1.0) <= 1e-9:
                    records.append({
                        "object_id": oid,
                        "translation": list(t),
                        "quaternion": list(q),
                        "offset": i,
                    })
                    i += 129
                    continue
        i += 1
    return records


def _parse_run_length_floats(stream: bytes, count: int) -> list[float] | None:
    """Decode `count` run-length IEEE-754 values (e8/e7/e9/e6 tags)."""
    vals: list[float] = []
    p = 0
    while p < len(stream) and len(vals) < count:
        tag = stream[p]
        if tag == 0xE8:
            vals.append(0.0)
            p += 1
        elif tag == 0xE7:
            vals.append(1.0)
            p += 1
        elif tag == 0xE9:
            vals.append(-1.0)
            p += 1
        elif tag == 0xE6 and p + 9 <= len(stream):
            v = struct.unpack_from("<d", stream, p + 1)[0]
            if not math.isfinite(v):
                return None
            vals.append(v)
            p += 9
        else:
            return None
    return vals if len(vals) == count else None


def _det3(r: list[list[float]]) -> float:
    return (
        r[0][0] * (r[1][1] * r[2][2] - r[1][2] * r[2][1])
        - r[0][1] * (r[1][0] * r[2][2] - r[1][2] * r[2][0])
        + r[0][2] * (r[1][0] * r[2][1] - r[1][1] * r[2][0])
    )


def _is_proper_rotation(r: list[list[float]], tol: float = 1e-4) -> bool:
    def norm(u: list[float]) -> float:
        return math.sqrt(sum(x * x for x in u))

    def dot(u: list[float], v: list[float]) -> float:
        return sum(a * b for a, b in zip(u, v))

    if abs(_det3(r) - 1.0) > tol:
        return False
    if any(abs(norm(row) - 1.0) > tol for row in r):
        return False
    return all(abs(dot(r[i], r[j])) <= tol for i in range(3) for j in range(i + 1, 3))


def _mat3_to_quat(r: list[list[float]]) -> list[float]:
    m00, m01, m02 = r[0]
    m10, m11, m12 = r[1]
    m20, m21, m22 = r[2]
    tr = m00 + m11 + m22
    if tr > 0.0:
        s = math.sqrt(tr + 1.0) * 2.0
        qw, qx, qy, qz = 0.25 * s, (m21 - m12) / s, (m02 - m20) / s, (m10 - m01) / s
    elif m00 > m11 and m00 > m22:
        s = math.sqrt(max(1.0 + m00 - m11 - m22, 0.0)) * 2.0
        qw, qx, qy, qz = (m21 - m12) / s, 0.25 * s, (m01 + m10) / s, (m02 + m20) / s
    elif m11 > m22:
        s = math.sqrt(max(1.0 + m11 - m00 - m22, 0.0)) * 2.0
        qw, qx, qy, qz = (m02 - m20) / s, (m01 + m10) / s, 0.25 * s, (m12 + m21) / s
    else:
        s = math.sqrt(max(1.0 + m22 - m00 - m11, 0.0)) * 2.0
        qw, qx, qy, qz = (m10 - m01) / s, (m02 + m20) / s, (m12 + m21) / s, 0.25 * s
    q_norm = math.sqrt(qw * qw + qx * qx + qy * qy + qz * qz)
    if q_norm > 1e-12:
        qw, qx, qy, qz = qw / q_norm, qx / q_norm, qy / q_norm, qz / q_norm
    if qw < 0.0:
        qw, qx, qy, qz = -qw, -qx, -qy, -qz
    return [qw, qx, qy, qz]


def parse_position_matrix_records(data: bytes) -> list[dict[str, Any]]:
    """Scan the `_Position` value layer (8d81 matrices) in document order.

    The attribute header immediately before the marker classifies the record:
    explicit (`e8 f4 07 37`), identity (`e9 f4 07 04 37`), or product-root
    (`e8 e0 07 37`, excluded).
    """
    records: list[dict[str, Any]] = []
    idx = 0
    while True:
        pos = data.find(b"\x8d\x81", idx)
        if pos < 0:
            break
        pre = data[max(0, pos - 8) : pos]
        if pre.endswith(POSITION_IDENTITY_HEADER):
            kind = "identity"
        elif pre.endswith(POSITION_EXPLICIT_HEADER):
            kind = "explicit"
        else:
            idx = pos + 2
            continue
        vals = _parse_run_length_floats(data[pos + 2 :], 12)
        if vals is not None:
            r = [vals[0:3], vals[3:6], vals[6:9]]
            if _is_proper_rotation(r) and all(abs(x) <= 1e7 for x in vals[9:12]):
                records.append({
                    "kind": kind,
                    "translation": vals[9:12],
                    "quaternion": _mat3_to_quat(r),
                    "offset": pos,
                })
        idx = pos + 2
    return records


def _bind_legacy_129b(
    instances: list[dict[str, Any]],
    records: list[dict[str, Any]],
    pool_has_position: bool,
) -> str:
    """Mirror Rust `compute_bindings`/`bind_instances` for the 129-byte layer.

    Kept as the strict path: a count mismatch marks the positioned instances
    undecodable (never identity).
    """
    if not pool_has_position:
        for inst in instances:
            inst["placement_status"] = "identity"
            inst["transform"] = list(IDENTITY_TRANSFORM)
            inst["object_tag"] = None
            inst["classification_detail"] = (
                "no _Position attribute declared in structure pool (identity at origin)"
            )
        return "unplaced"

    n_placed = sum(1 for inst in instances if inst["has_position_attr"])
    n_rec = len(records)
    if n_rec == 0:
        mode = "identity_default"
    elif n_rec == n_placed:
        mode = "sequential_1to1"
    elif n_rec == n_placed + 1:
        mode = "root_plus_sequential"
    elif n_rec == 2 and n_placed == 3 and instances and (
        instances[-1]["instance_name"].startswith("main")
        or instances[-1]["part_number"].startswith("main")
    ):
        mode = "sequential_1to1"
    else:
        mode = "undecodable"

    placed_idx = 0
    for inst in instances:
        if not inst["has_position_attr"]:
            inst["placement_status"] = "identity"
            inst["transform"] = list(IDENTITY_TRANSFORM)
            inst["object_tag"] = None
            inst["classification_detail"] = (
                "instance lacks _Position attribute (identity at origin)"
            )
            continue

        if mode == "identity_default":
            inst["placement_status"] = "placed"
            inst["transform"] = list(IDENTITY_TRANSFORM)
            inst["object_tag"] = None
            inst["classification_detail"] = (
                "CATIA default identity placement (no override records declared)"
            )
        elif mode == "sequential_1to1" and placed_idx < n_rec:
            rec = records[placed_idx]
            t, q = rec["translation"], rec["quaternion"]
            inst["placement_status"] = "placed"
            inst["transform"] = [t[0], t[1], t[2], q[0], q[1], q[2], q[3]]
            inst["object_tag"] = rec["object_id"]
            inst["classification_detail"] = None
        elif mode == "root_plus_sequential" and placed_idx + 1 < n_rec:
            rec = records[placed_idx + 1]
            t, q = rec["translation"], rec["quaternion"]
            inst["placement_status"] = "placed"
            inst["transform"] = [t[0], t[1], t[2], q[0], q[1], q[2], q[3]]
            inst["object_tag"] = rec["object_id"]
            inst["classification_detail"] = None
        else:
            inst["placement_status"] = "undecodable"
            inst["transform"] = None
            inst["object_tag"] = None
            inst["classification_detail"] = (
                f"undecodable placement: {n_rec} transform records for "
                f"{n_placed} placed instances (constraint mesh override)"
            )
        placed_idx += 1
    return mode


def _bind_position_layer(
    instances: list[dict[str, Any]], records: list[dict[str, Any]]
) -> str | None:
    """Bind instances to the `_Position` layer under a counted law.

    Mirrors Rust `port::product::binding::bind_position_layer`.
    """
    n_positioned = sum(1 for inst in instances if inst["has_position_attr"])
    if not records or n_positioned == 0:
        return None

    last = instances[-1]
    last_is_root_ref = last["has_position_attr"] and (
        last["instance_name"].startswith("main") or last["part_number"].startswith("main")
    )
    explicit = [r for r in records if r["kind"] == "explicit"]

    if last_is_root_ref:
        n_bind = n_positioned - 1
        if n_bind == 0 or len(explicit) < n_bind:
            return None
        chosen = explicit[:n_bind]
        if len(explicit) > n_bind:
            t = explicit[n_bind]["translation"]
            root_ref_detail = (
                "root assembly reference excluded by positional precedence "
                f"(explicit row {n_bind + 1} exists: T=({t[0]:.3f}, {t[1]:.3f}, {t[2]:.3f}); "
                f"rows 1..{n_bind} bind the children)"
            )
        else:
            root_ref_detail = "root assembly reference excluded by positional precedence"
    elif len(explicit) == n_positioned:
        chosen = explicit
        root_ref_detail = None
    elif len(records) == n_positioned:
        chosen = records
        root_ref_detail = None
    else:
        return None

    cursor = 0
    last_index = len(instances) - 1
    for index, inst in enumerate(instances):
        if not inst["has_position_attr"]:
            inst["placement_status"] = "identity"
            inst["transform"] = list(IDENTITY_TRANSFORM)
            inst["object_tag"] = None
            inst["classification_detail"] = "instance lacks _Position attribute (identity at origin)"
            continue
        if last_is_root_ref and index == last_index:
            inst["placement_status"] = "undecodable"
            inst["transform"] = None
            inst["object_tag"] = None
            inst["classification_detail"] = root_ref_detail
            continue
        if cursor < len(chosen):
            rec = chosen[cursor]
            if rec["kind"] == "identity":
                # Identity frame: keep the ordinal position, never bind its matrix.
                inst["placement_status"] = "undecodable"
                inst["transform"] = None
                inst["object_tag"] = None
                inst["classification_detail"] = (
                    f"identity 8d81 frame at 0x{rec['offset']:x} is a "
                    "constraint/connector placeholder, not an instance _Position (Clause 3)"
                )
            else:
                t, q = rec["translation"], rec["quaternion"]
                inst["transform"] = [t[0], t[1], t[2], q[0], q[1], q[2], q[3]]
                inst["object_tag"] = None
                inst["placement_status"] = "placed"
                inst["classification_detail"] = None
        else:
            inst["placement_status"] = "undecodable"
            inst["transform"] = None
            inst["object_tag"] = None
            inst["classification_detail"] = "position layer exhausted before this instance"
        cursor += 1
    return "position_stream_8d81"


def read_product_structure(data: bytes) -> dict[str, Any]:
    """Parse a .CATProduct binary buffer into a structured document.

    Mirrors Rust `port::product::parse_product` and the ProductStructureDocument
    schema in Spec F #45 §7.1.
    """
    if not data:
        raise ValueError("empty buffer: cannot decode product structure from 0 bytes")
    if len(data) < 32:
        raise ValueError(f"buffer too short for CATIA container header: {len(data)} bytes")

    detected_version = "Unknown"
    match = re.search(rb"(?:V5|V6)R\d{1,2}(?:SP\d{1,2})?(?:HF\d{1,2})?", data[:0x8000])
    if match:
        detected_version = match.group(0).decode("ascii", "replace")

    pool_cand = scan_structure_pool(data)
    r15_count = r15_reference_count(data)

    if pool_cand is not None:
        pool_form = "framed"
        _, _, texts = pool_cand
    elif r15_count >= 3:
        pool_form = "r15-ref"
        texts = []
    else:
        pool_form = "unframed"
        texts = []

    product_name = "Product"
    for i, t in enumerate(texts):
        if t == "ASMPRODUCT" and i + 1 < len(texts):
            next_t = texts[i + 1]
            if not is_token(next_t) and not is_class_token(next_t) and next_t != BINARY_SENTINEL:
                product_name = next_t
                break

    instances: list[dict[str, Any]] = []
    warnings: list[dict[str, str]] = []

    if pool_form == "framed":
        pool_has_position = "_Position" in texts
        n = len(texts)
        consumed = set()

        # Pass 1: explicit markers (_InstanceName and Description Blocks)
        for i in range(n):
            if texts[i] == "_InstanceName":
                # Check Description Block
                if i >= 2 and texts[i - 2] == "_DescriptionInst":
                    pn = texts[i - 3] if i >= 3 and not is_token(texts[i - 3]) else texts[i - 1].split(":")[0]
                    inst = texts[i - 1] if ":" in texts[i - 1] else texts[i + 1]
                    if not is_constraint_name(inst):
                        has_pos = (i + 2 < n and texts[i + 2] == "_Position") or pool_has_position
                        instances.append({
                            "instance_name": inst,
                            "part_number": pn,
                            "pairing_rule": "desc_block",
                            "has_position_attr": has_pos,
                            "placement_status": "placed" if has_pos else "identity",
                            "transform": None,
                        })
                    consumed.add(i - 1)
                    consumed.add(i + 1)
                elif i > 0 and i + 1 < n:
                    prev_t = texts[i - 1]
                    next_t = texts[i + 1]
                    if not is_token(prev_t) and not is_token(next_t) and not is_class_token(prev_t):
                        if not is_constraint_name(next_t):
                            has_pos = (i + 2 < n and texts[i + 2] == "_Position") or pool_has_position
                            instances.append({
                                "instance_name": next_t,
                                "part_number": prev_t,
                                "pairing_rule": "triple",
                                "has_position_attr": has_pos,
                                "placement_status": "placed" if has_pos else "identity",
                                "transform": None,
                            })
                        consumed.add(i - 1)
                        consumed.add(i + 1)

        # Pass 2: bare pairs (dot- and colon-shaped instance names)
        for i in range(n):
            if i in consumed:
                continue
            curr = texts[i]
            is_dot = DOT_SHAPE.match(curr)
            is_colon = COLON_SHAPE.match(curr)
            if (not is_dot and not is_colon) or is_constraint_name(curr):
                continue
            if i > 0 and texts[i - 1] == "ASMPRODUCT":
                continue
            stem = curr.rsplit(".", 1)[0] if is_dot else curr.rsplit(":", 1)[0]
            if (
                i > 0
                and not is_token(texts[i - 1])
                and not is_class_token(texts[i - 1])
                and texts[i - 1] == stem
            ):
                pn = texts[i - 1]
            else:
                pn = stem
            has_pos = (i + 1 < n and texts[i + 1] == "_Position") or pool_has_position
            instances.append({
                "instance_name": curr,
                "part_number": pn,
                "pairing_rule": "bare_pair",
                "has_position_attr": has_pos,
                "placement_status": "placed" if has_pos else "identity",
                "transform": None,
            })
            consumed.add(i)
            if is_colon and i + 1 < n and USCORE_SHAPE.match(texts[i + 1]):
                consumed.add(i + 1)

        # Bind decoded transforms. The 129-byte layer is a constraint/connector
        # frame on dual-layer files; prefer the `_Position` 8d81 layer when the
        # legacy gate would place. Count mismatches fail closed to undecodable.
        raw_recs = parse_129b_transform_records(data)
        mode = None
        if raw_recs:
            n_pos = sum(1 for inst in instances if inst["has_position_attr"])
            last_is_root_ref = bool(instances) and instances[-1]["has_position_attr"] and (
                instances[-1]["instance_name"].startswith("main")
                or instances[-1]["part_number"].startswith("main")
            )
            legacy_places = (
                len(raw_recs) == n_pos
                or len(raw_recs) == n_pos + 1
                or (len(raw_recs) == 2 and n_pos == 3 and last_is_root_ref)
            )
            position_recs = (
                parse_position_matrix_records(data) if legacy_places else []
            )
            mode = None
            if position_recs:
                mode = _bind_position_layer(instances, position_recs)
            if mode is not None:
                pass
            elif position_recs:
                n_explicit = sum(1 for r in position_recs if r["kind"] == "explicit")
                n_identity = len(position_recs) - n_explicit
                for inst in instances:
                    if not inst["has_position_attr"]:
                        continue
                    inst["placement_status"] = "undecodable"
                    inst["transform"] = None
                    inst["object_tag"] = None
                    inst["classification_detail"] = (
                        f"position layer count mismatch: {n_explicit} explicit + "
                        f"{n_identity} identity records for {n_pos} positioned instances"
                    )
            else:
                _bind_legacy_129b(instances, raw_recs, pool_has_position)
        elif pool_has_position:
            for inst in instances:
                if not inst["has_position_attr"]:
                    inst["placement_status"] = "identity"
                    inst["transform"] = list(IDENTITY_TRANSFORM)
                    inst["classification_detail"] = (
                        "instance lacks _Position attribute (identity at origin)"
                    )

        if mode == "position_stream_8d81":
            warnings.append({
                "class": "position-stream-8d81",
                "detail": (
                    "placement bound from the _Position 8d81 layer "
                    f"({len(position_recs)} records; 129-byte layer not used)"
                ),
            })

    elif pool_form == "r15-ref":
        warnings.append({
            "class": "r15-legacy-reference-form",
            "detail": "R15 attribute-reference form detected; structure pool is unframed",
        })
        # Extract any candidate names from R15 tags
        inst_names = []
        for m in R15_ENTRY.finditer(data):
            tag_bytes = m.group(1)
            try:
                tag_str = tag_bytes.decode("ascii")
                if DOT_SHAPE.match(tag_str) and not is_constraint_name(tag_str):
                    inst_names.append(tag_str)
            except UnicodeDecodeError:
                pass
        for inst in inst_names:
            pn = inst.rsplit(".", 1)[0]
            instances.append({
                "instance_name": inst,
                "part_number": pn,
                "pairing_rule": "bare_pair",
                "has_position_attr": True,
                "placement_status": "undecodable",
                "transform": None,
            })
    else:
        warnings.append({
            "class": "unframed-pool",
            "detail": "no framed structure pool or R15 reference entries found",
        })

    placed_count = sum(1 for i in instances if i["placement_status"] == "placed")
    identity_count = sum(1 for i in instances if i["placement_status"] == "identity")
    undecodable_count = sum(1 for i in instances if i["placement_status"] == "undecodable")

    return {
        "schema_version": 1,
        "product_name": product_name,
        "detected_version": detected_version,
        "pool_form": pool_form,
        "total_instances": len(instances),
        "placed_instances": placed_count,
        "identity_instances": identity_count,
        "undecodable_instances": undecodable_count,
        "instances": instances,
        "warnings": warnings,
    }


def classify_assembly(
    product_doc: dict[str, Any],
    available_files: set[str] | list[str] | dict[str, Any],
) -> dict[str, str]:
    """Evaluate instance resolution against available files into the 4 canonical states:

    1. 'Resolved & Placed' ('placed')
    2. 'Resolved & Identity' ('identity')
    3. 'Unresolved Part' ('unresolved')
    4. 'Undecodable Placement' ('undecodable')

    Returns mapping of instance_name -> canonical state string.
    """
    if isinstance(available_files, dict):
        names = set(available_files.keys())
    else:
        names = set(available_files)

    # Normalize filenames and base stems for case-insensitive lookup
    normalized_stems = {}
    for fn in names:
        base = os.path.basename(fn)
        stem = base.rsplit(".", 1)[0]
        normalized_stems[base.lower()] = base
        normalized_stems[stem.lower()] = base

    is_r15 = product_doc.get("pool_form") == "r15-ref"

    classifications = {}
    for inst in product_doc.get("instances", []):
        inst_name = inst["instance_name"]
        pn = inst["part_number"]
        pn_lower = pn.lower()

        # Check resolution in uploaded files
        part_resolved = (
            pn_lower in normalized_stems
            or f"{pn_lower}.catpart" in normalized_stems
        )

        if not part_resolved:
            classifications[inst_name] = "unresolved"
        elif is_r15 or inst.get("placement_status") == "undecodable":
            classifications[inst_name] = "undecodable"
        elif not inst.get("has_position_attr"):
            classifications[inst_name] = "identity"
        else:
            classifications[inst_name] = "placed"

    return classifications
