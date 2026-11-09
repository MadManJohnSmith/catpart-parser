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

VALID_VARIANTS = (None, "dual-region")
CORRUPTED_VARIANTS = (
    "bad-magic",
    "truncated-table",
    "missing-trailer",
    "junk-payload",
    "oversized-dword",
    "short-file",
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


def catia_identity_block(name2: bytes = b"") -> bytes:
    """One CATStorageProperty identity block (C3 phase A claims D1/D2).

    Byte layout observed in the corpus (docs/evidence/
    2026-11-08-units-names-probe.md): the B3 block header, name1
    ``CATIA`` tag34-framed and 0x9f-terminated, then the name2 field
    ``a0 02 00 00 00 00 34 <len> <ascii> 9f`` (empty: ``34 00 9f``),
    then the ``3b 10`` marker with the identity block's 16 zero bytes
    (null GUID) and a trailing ``9f``.
    """
    block = b"\x34\x12" + b"CATStorageProperty"
    block += b"\x80\x01\x00\x00\x00\x00\x22\x0c\x00\x00\x00"
    block += b"\x34\x01\x01\x00" + b"\x34\x10" + b"CATUnicodeString"
    block += b"\xa0\x02\x00\x00\x00\x00\x34\x05" + b"CATIA" + b"\x9f"
    block += b"\xa0\x02\x00\x00\x00\x00\x34"
    block += bytes([len(name2)]) + name2 + b"\x9f"
    block += b"\x3b\x10" + bytes(16) + b"\x9f"
    return block


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
    (``None`` or ``"dual-region"``) or one named corrupted variant (see
    the module docstring for the expected fitness classification of
    each). ``document_name`` stores a save-time name in the identity
    block (the C3 ``document_name`` claim; ``None`` omits the block).
    """
    if kind not in KIND_RECORDS:
        raise ValueError(f"unknown kind: {kind!r}")
    if variant not in VALID_VARIANTS + CORRUPTED_VARIANTS:
        raise ValueError(f"unknown variant: {variant!r}")

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
