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

Recovery variants (G6 stage 3a, #34 — the locator recovery extension;
each is the fixture twin of a stage-1 census recovery family):

- ``geometry-seebody-store``    -> the store sits in a ``CATSeeBodyCont``
  block and no ``CATStdCont`` block exists (census case 03efd608,
  no_stdcont family): the container probe recovers it -> exports 12
  triangles, summary ``store_recovery`` = seebody/shipped.
- ``geometry-xdoclink-store``   -> a store-less ``CATStdCont`` block and
  the store in a ``CATXDocLinkCont`` block (census case 01f2a48c,
  next_block_store family, R19) -> exports via the xdoclink probe,
  ``store_recovery`` = xdoclink/shipped.
- ``geometry-overshoot-tail``   -> the stdcont store's ``dword8``
  overshoots the catalog magic by 9 B (G1 correction C3; the shipped
  tail runs past ``CB__END``) -> the relaxed tail law recovers it,
  ``store_recovery`` = stdcont/overshoot.
- ``geometry-padded-tail``      -> the stdcont store's catalog trailer
  sits inside the tail, zero-padded to dword12 = 128 (G1 padded-tail
  variant) -> relaxed tail law ends the tail at its ``CB__END``,
  ``store_recovery`` = stdcont/padded.
- ``geometry-seebody-composite``-> a seebody store carrying the ``01 02``
  edge group: recovered, then the composite gate fires ->
  ``undecoded-variant`` with the recovery named on the error detail.
- ``geometry-seebody-empty``    -> a ``CATSeeBodyCont`` block carrying no
  store (census case 084841b3): the probe matches nothing, fail-closed
  -> ``missing-geometry-store``.
- ``geometry-othercontainer-store`` -> the store in a
  ``CATBRepModeContainer`` block (stage-12 #34: the other-container
  probe family, the census's dominant recovery region) -> exports via
  the stage-12 probe, ``store_recovery`` = other-container/shipped
  with ``container_name`` = CATBRepModeContainer.
- ``geometry-overshoot-bad-tail`` -> an overshoot store whose corrected
  tail also violates N6 (C != D): neither tail family recovers,
  fail-closed -> ``malformed-store-header``.
- ``geometry-othercontainer-composite`` -> the composite-gate store
  inside a ``CATBRepModeContainer`` block: recovered by the stage-12
  probe, then the composite gate fires -> ``undecoded-variant`` naming
  the block on the error detail.
- ``geometry-othercontainer-bad-tail`` -> the neither-family-recovers
  store inside a ``CATBRepModeContainer`` block: the stage-12 probe
  raises the shipped ``malformed-store-header`` rejection (fail-closed
  — the same rules as the named families).
- ``geometry-othercontainer-behind-empty-stdcont`` /
  ``geometry-stdcont-precedence`` -> the stage-12 probe fires only
  when nothing located before it (a store-less ``CATStdCont`` block
  does not block the probe) and never overrides a located
  ``CATStdCont`` store.
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

VALID_VARIANTS = (
    None,
    "dual-region",
    "geometry",
    "geometry-open-shell",
    # Composite-law variants (G6 stage 2c/3d, #34): the identity law
    # decodes both forms; slanted quads, curve-entry loops and the
    # u16be no-repeat rule are the law's shapes.
    "geometry-composite-law",
    # Stage-3a recovery variants (#34): valid-shaped, export pass.
    "geometry-seebody-store",
    "geometry-xdoclink-store",
    "geometry-overshoot-tail",
    "geometry-padded-tail",
    # Stage-12 recovery variants (#34, 2026-11-13): the store in a
    # CATBRepModeContainer block (the other-container probe family —
    # the corpus's dominant recovery region, census section 2), behind
    # a store-less CATStdCont block, and the stdcont-precedence pin.
    "geometry-othercontainer-store",
    "geometry-othercontainer-behind-empty-stdcont",
    "geometry-stdcont-precedence",
    # Stage-13 second-chance element-space positives (#34, 2026-11-13):
    # the composite element-space structure WITHOUT its routing markers
    # (no `01 02` edge group / opener) — the clean path fails with the
    # no-pool or refs-beyond raise and the second-chance route re-routes
    # to the unchanged composite decode (the stage-13 finding).
    "geometry-unrouted-elementspace-refs-beyond",
    "geometry-unrouted-elementspace-no-pool",
    # Stage-3d identity-law variants (#34): both forms export under the
    # table walk + element-index refs.
    "geometry-composite-law-big",
    "geometry-composite-law-slanted",
    "geometry-composite-law-curve-entries",
    "geometry-composite-law-u16be",
    # Stage-5 law variants (#34, 2026-11-12): the stage-4b width laws
    # (u24be for element counts above 65,535; the plane tiebreak over
    # interleaved families) and the per-rep decomposition (a rep that
    # does not absorb stays unexported).
    "geometry-composite-law-u24be",
    "geometry-composite-law-width-plane",
    "geometry-composite-law-multi-rep",
    "geometry-composite-law-multi-rep-partial",
    # Stage-6 law variant (#34, 2026-11-12): the stage-4a raw-array law
    # (the walk-mismatch residue exports through the trail-escape-pinned
    # raw f32 triples).
    "geometry-composite-law-raw-array",
    # Stage-9 law variants (#34, 2026-11-12): the stage-8 mixed-write
    # locator/predicate artifacts — the STRIP_RE false match inside the
    # point region truncates the single-rep window (the full-body per-
    # rep scan recovers it), the zero-block extent candidates fix the
    # layout() overshoot, the flat law decodes the near-zero coordinates
    # the raw scan's 1e-6 floor rejects, and the per-rep composition
    # exports multi-rep walk-mismatch stores.
    "geometry-composite-law-raw-array-strip-false-match",
    "geometry-composite-law-table-overshoot",
    "geometry-composite-law-flat-near-zero",
    "geometry-composite-law-mixedwrite-multi-rep",
    # Stage-10 E0-b dup-pin variants (#34, 2026-11-12): the restricted
    # curve-entry law's shapes — the battery-supported positives fire;
    # the nonplanar / normal-less / non-empty / multi-rep negatives
    # keep the conservative rule.
    "geometry-composite-law-e0b-dup-pin",
    "geometry-composite-law-e0b-single-loop",
    "geometry-composite-law-e0b-nonplanar",
    "geometry-composite-law-e0b-normal-less",
    "geometry-composite-law-e0b-nonempty",
    "geometry-composite-law-e0b-multi-rep-conservative",
    "geometry-composite-law-e0b-multi-rep-unsupported-veto",
    "geometry-composite-law-e0b-unpinnable",
)
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
    # Stage-3a fail-closed negatives (#34): recovered-then-failing,
    # probe-matches-nothing, and neither-tail-family-recovers.
    "geometry-seebody-composite",
    "geometry-seebody-empty",
    "geometry-overshoot-bad-tail",
    # Stage-12 fail-closed negatives (#34, 2026-11-13): recovered-then-
    # composite-failing and broken-tail stores in an other-container
    # block (the same fail-closed rules as the named families).
    "geometry-othercontainer-composite",
    "geometry-othercontainer-bad-tail",
    # Composite-law corrupted variants (G6 stage 3d, #34): the fail-
    # closed ladder's specific gaps.  The stage-2c nonplanar variant is
    # retired (2026-11-11): under the identity law non-coplanarity is
    # not a decode gap (multi-plane strips are legitimate geometry) —
    # the plane law is the coplanarity battery, not an export gate.
    "geometry-composite-law-walk-mismatch",
    "geometry-composite-law-unabsorbed",
    # Stage-6 raw-array fail-closed negatives (#34, 2026-11-12): the
    # start rule cannot pin a trail-escape (wrong offset) / the pool is
    # not re-listed in the triples / a walk-EXACT non-finite coordinate
    # is not the raw family (the trigger-ordering pin).
    "geometry-composite-law-raw-array-wrong-offset",
    "geometry-composite-law-raw-array-unabsorbed",
    "geometry-composite-law-walk-nan",
    # Stage-9 fail-closed negative (#34, 2026-11-12): a multi-rep
    # walk-mismatch store whose second pool group carries a 9th vertex
    # no decoded region re-lists (the sub-node records' residue) — the
    # element index is unpinned, the store stays fail-closed for export.
    "geometry-composite-law-mixedwrite-multi-rep-subnode",
    # Stage-12 recovery positive (#34, 2026-11-13): see above.
    "geometry-othercontainer-composite-law",
    # Stage-13 second-chance fail-closed negatives (#34, 2026-11-13):
    # the second-chance element-space route declines and the ORIGINAL
    # clean-path error re-raises unchanged (no token node / a walk-
    # failing node).
    "geometry-unrouted-elementspace-no-node",
    "geometry-unrouted-elementspace-walk-mismatch",
)
GEOMETRY_VARIANTS = (
    "geometry",
    "geometry-open-shell",
    "geometry-seebody-store",
    "geometry-xdoclink-store",
    "geometry-overshoot-tail",
    "geometry-padded-tail",
    "geometry-othercontainer-store",
    "geometry-othercontainer-behind-empty-stdcont",
    "geometry-stdcont-precedence",
) + (
    "geometry-bad-nested-magic",
    "geometry-composite-index-space",
    "geometry-missing-facet-payload",
    "geometry-nan-coords",
    "geometry-out-of-range-refs",
    "geometry-truncated-pool",
    "geometry-seebody-composite",
    "geometry-seebody-empty",
    "geometry-overshoot-bad-tail",
    # Stage-12 fail-closed negatives (#34, 2026-11-13): recovered-then-
    # composite-failing and broken-tail stores in an other-container
    # block (the same fail-closed rules as the named families).
    "geometry-othercontainer-composite",
    "geometry-othercontainer-bad-tail",
)
COMPOSITE_VARIANTS = (
    "geometry-composite-law",
    # Stage-13 second-chance element-space variants (#34, 2026-11-13):
    # the element space without its routing markers (positives export
    # through the second-chance route; negatives keep the original
    # clean-path error).
    "geometry-unrouted-elementspace-refs-beyond",
    "geometry-unrouted-elementspace-no-pool",
    "geometry-unrouted-elementspace-no-node",
    "geometry-unrouted-elementspace-walk-mismatch",
    "geometry-composite-law-big",
    "geometry-composite-law-slanted",
    "geometry-composite-law-curve-entries",
    "geometry-composite-law-u16be",
    "geometry-composite-law-u24be",
    # Stage-12 recovery positive (#34, 2026-11-13): the composite-law
    # store inside a CATBRepModeContainer block — a recovered store
    # EXPORTING through the composite path (store_recovery must ride
    # on composite summaries too).
    "geometry-othercontainer-composite-law",
    "geometry-composite-law-width-plane",
    "geometry-composite-law-multi-rep",
    "geometry-composite-law-multi-rep-partial",
    "geometry-composite-law-walk-mismatch",
    "geometry-composite-law-unabsorbed",
    "geometry-composite-law-raw-array",
    "geometry-composite-law-raw-array-wrong-offset",
    "geometry-composite-law-raw-array-unabsorbed",
    "geometry-composite-law-walk-nan",
    "geometry-composite-law-raw-array-strip-false-match",
    "geometry-composite-law-table-overshoot",
    "geometry-composite-law-flat-near-zero",
    "geometry-composite-law-mixedwrite-multi-rep",
    "geometry-composite-law-mixedwrite-multi-rep-subnode",
    "geometry-composite-law-e0b-dup-pin",
    "geometry-composite-law-e0b-single-loop",
    "geometry-composite-law-e0b-nonplanar",
    "geometry-composite-law-e0b-normal-less",
    "geometry-composite-law-e0b-nonempty",
    "geometry-composite-law-e0b-multi-rep-conservative",
    "geometry-composite-law-e0b-multi-rep-unsupported-veto",
    "geometry-composite-law-e0b-unpinnable",
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


def _facet_record(marker: int, normal, refs: tuple[int, ...], width: int = 1) -> bytes:
    """One facet record in the G3 grammar (F1): 4-byte header ``01 <mk>
    <ty=1> ff``, u32le n, the 12-byte normal when the marker carries
    one, one loop-count byte (k=1, summing to n — the tiling law needs
    count bytes for n > 0, as the corpus 0x41 records show), then the
    references (u8 lexicographic ranks on the clean stores; u8, u16be
    or — stage-4b, element counts above 65,535 — u24be element indices
    on the composite stores, per the width rule)."""
    rec = bytes([0x01, marker, 0x01, 0xFF]) + struct.pack("<I", len(refs))
    if normal is not None:
        rec += struct.pack("<fff", *normal)
    if width == 1:
        return rec + bytes([len(refs)]) + bytes(refs)
    if width == 2:
        return (
            rec
            + bytes([len(refs)])
            + b"".join(struct.pack(">H", r) for r in refs)
        )
    return (
        rec
        + bytes([len(refs)])
        + b"".join(struct.pack(">I", r)[1:] for r in refs)
    )


def _geometry_box_edges_lex() -> tuple[tuple[int, int], ...]:
    """The box's 12 edges as lex-rank pairs (F8: the 01 02 edge table's
    endpoints are lex-adjacent pool vertices)."""
    return (
        (0, 1), (0, 2), (0, 4), (1, 3), (1, 5), (2, 3),
        (2, 6), (3, 7), (4, 5), (4, 6), (5, 7), (6, 7),
    )


# --- composite-store fixtures (G6 stages 2c->3d, #34) --------------------
#
# Synthetic composite stores whose list node carries a point region
# encoded under the stage-3b table law (P1t: 2-bit per-element table of
# EXACTLY ceil(elem/4) bytes + a P1g write count + the region) and
# whose facet records reference 0-based element indices in region
# order (M2b identity, stage 3d).  The pool is re-listed verbatim
# (absorbed).  Variants:
#
# - geometry-composite-law               small form, curve entries 0;
#                                        exports 12 triangles, closed.
# - geometry-composite-law-big           big form: a 10x10x10 grid
#                                        (1,000 elements, write count
#                                        1,108 > 255 -> the ff-escape
#                                        count), u16be refs, exports
#                                        the box's 12 triangles.
# - geometry-composite-law-slanted       small form with one slanted
#                                        quad (coplanar vs the stored
#                                        normal, no axis-constant
#                                        coordinate) — exports under
#                                        the coplanar-vs-normal plane
#                                        law.
# - geometry-composite-law-curve-entries small form with 3 skip slots
#                                        (curve entries); one extra
#                                        loop references a skip slot
#                                        (not exported, U4 — named
#                                        warning), the box exports.
# - geometry-composite-law-u16be         big form + one record whose
#                                        u8 misread repeats refs
#                                        inside the loop: the stage-3b
#                                        no-repeated-refs rule picks
#                                        u16be.
# - geometry-composite-law-u24be         stage-4b width gap 1: a
#                                        65,600-element grid (> 65,535)
#                                        whose face records carry
#                                        u24be refs (top corners up to
#                                        65,599) and tile exactly only
#                                        at width 3 -> the box exports.
# - geometry-composite-law-width-plane   stage-4b width gap 2: one
#                                        record whose u8/u16be parses
#                                        tie on (tiling, repeats, oob)
#                                        over interleaved filler bytes;
#                                        the u8 read is nonplanar vs
#                                        the stored normal, the u16be
#                                        read coplanar -> the plane
#                                        tiebreak picks u16be.
# - geometry-composite-law-multi-rep     stage-4b per-rep law: two
#                                        reps (pool group k re-lists in
#                                        the k-th node's region), the
#                                        stage-3d single-rep reading
#                                        fails absorption -> both reps
#                                        export merged.
# - geometry-composite-law-multi-rep-partial  as above, but rep 1's
#                                        pool carries a 9th vertex no
#                                        region re-lists -> rep 1 stays
#                                        unexported (per-rep fail-
#                                        closed), rep 0 exports.
# - geometry-composite-law-walk-mismatch corrupted: the declared write
#                                        count exceeds what the table
#                                        encodes -> walk-exact failure
#                                        (undecoded-variant).
# - geometry-composite-law-unabsorbed    corrupted: the pool carries a
#                                        vertex the node list does not
#                                        re-list -> undecoded-variant.
# - geometry-composite-law-raw-array     stage-4a raw-array law (stage-6
#                                        integration): the element space
#                                        rides as raw f32 triples past
#                                        the header (no table, no write
#                                        count); the trail-escape byte
#                                        pins start 40 -> exports
#                                        through the raw path.
# - geometry-composite-law-raw-array-wrong-offset  corrupted: the
#                                        escape byte sits one past every
#                                        candidate start's array end ->
#                                        the start rule pins nothing
#                                        (fail-closed).
# - geometry-composite-law-raw-array-unabsorbed  corrupted: a 9th pool
#                                        vertex the triples do not
#                                        re-list -> absorption not
#                                        established (fail-closed).
# - geometry-composite-law-walk-nan      corrupted: the walk is EXACT
#                                        but a coordinate is non-finite
#                                        -> not the raw-array family
#                                        (trigger-ordering pin: the
#                                        walk's own failure stands).
# - geometry-composite-law-raw-array-strip-false-match  stage-8
#                                        artifact 1 (stage-9 #34): the
#                                        point region carries a STRIP_RE
#                                        false match (01 45 00 ff across
#                                        two nice floats) -> the
#                                        single-rep window truncates the
#                                        node mid-region, the raw law's
#                                        12*elem_decl span no longer
#                                        fits -> the full-body per-rep
#                                        scan recovers the raw region.
# - geometry-composite-law-table-overshoot  stage-8 artifact 2: the
#                                        region opens with 16+ full-write
#                                        slots, the 2-bit table's own
#                                        leading bytes are zero and
#                                        layout()'s zero-group skip
#                                        overshoots INTO the table -> the
#                                        extent candidates select the
#                                        unique walk-exact extent.
# - geometry-composite-law-flat-near-zero  stage-8 artifact 3: four
#                                        non-pool triples carry near-zero
#                                        coordinates (|v| ~ 1e-14) -> the
#                                        raw scan's 1e-6 floor weak-fits
#                                        (nice 0.667 < 0.98) -> the flat
#                                        law (start pinned by counts_end,
#                                        exporter predicate) decodes.
# - geometry-composite-law-mixedwrite-multi-rep  the stage-9
#                                        composition: two raw-layout
#                                        reps, each pool group absorbed
#                                        by its diagonal rep's region ->
#                                        both export merged (stage
#                                        identity-mixedwrite-reps).
# - geometry-composite-law-mixedwrite-multi-rep-subnode  corrupted: rep
#                                        1's pool carries a 9th vertex no
#                                        region re-lists -> absorption
#                                        not established (sub-node
#                                        residue, fail-closed).
# - geometry-composite-law-e0b-dup-pin   stage-10: skip slots at
#                                        elements 2/6/10; one record
#                                        with TWO dropped loops, both
#                                        normal-carrying and coplanar
#                                        under the dup pin -> the E0-b
#                                        law fires, the pinned loops
#                                        export (4 triangles).
# - geometry-composite-law-e0b-single-loop  the one-dropped-loop
#                                        positive (the 4ad53b87 shape).
# - geometry-composite-law-e0b-nonplanar one coplanar + one NONPLANAR
#                                        dropped loop (3dff4d93): not
#                                        battery-supported -> the
#                                        conservative rule holds.
# - geometry-composite-law-e0b-normal-less  one coplanar + one on a
#                                        normal-less 0x42 strip
#                                        (08f2eccb): untestable ->
#                                        conservative.
# - geometry-composite-law-e0b-nonempty  the box exports AND carries a
#                                        battery-supported dropped
#                                        loop: not empty-mesh -> the
#                                        store-level conservative
#                                        gate holds (471-passing).
# - geometry-composite-law-e0b-multi-rep-conservative  rep 1 carries a
#                                        battery-supported dropped
#                                        loop, rep 0 exports its box:
#                                        no rep-level fire (store-
#                                        level gate).
# - geometry-composite-law-e0b-multi-rep-unsupported-veto  BOTH reps
#                                        empty: rep 0 carries a
#                                        NORMAL-LESS dropped loop,
#                                        rep 1 the supported one —
#                                        one unsupported rep vetoes
#                                        the store fire (review F1).
# - geometry-composite-law-e0b-unpinnable  the dropped loop's skip
#                                        slot is ELEMENT 0: no
#                                        preceding written element
#                                        to weld to (review F4).

COMPOSITE_POOL_WALK = (
    (0.0, 10.0, 0.0),
    (20.0, 10.0, 0.0),
    (0.0, 110.0, 0.0),
    (20.0, 110.0, 0.0),
    (0.0, 110.0, 60.0),
    (20.0, 110.0, 60.0),
    (0.0, 10.0, 60.0),
    (20.0, 10.0, 60.0),
)

#: The merged element space: the pool corners plus the four z-edge
#: midpoints, lexicographically sorted (the node list itself — the
#: pool is absorbed, re-listed verbatim, curve entries 0).
COMPOSITE_POINTS = (
    (0.0, 10.0, 0.0),
    (0.0, 10.0, 30.0),
    (0.0, 10.0, 60.0),
    (0.0, 110.0, 0.0),
    (0.0, 110.0, 30.0),
    (0.0, 110.0, 60.0),
    (20.0, 10.0, 0.0),
    (20.0, 10.0, 30.0),
    (20.0, 10.0, 60.0),
    (20.0, 110.0, 0.0),
    (20.0, 110.0, 30.0),
    (20.0, 110.0, 60.0),
)

#: The six box faces as facet records over the element indices (the
#: same record shapes as the clean box: 4 x 0x4a strips + 2 x 0x4c
#: polygons, 12 triangles, a closed oriented manifold; every triangle
#: winds CCW against its outward normal).
COMPOSITE_FACES = (
    (0x4A, (0.0, 0.0, -1.0), (6, 0, 9, 3)),
    (0x4A, (0.0, 1.0, 0.0), (11, 9, 5, 3)),
    (0x4A, (0.0, 0.0, 1.0), (2, 8, 5, 11)),
    (0x4A, (0.0, -1.0, 0.0), (6, 8, 0, 2)),
    (0x4C, (-1.0, 0.0, 0.0), (0, 2, 5, 3)),
    (0x4C, (1.0, 0.0, 0.0), (6, 9, 11, 8)),
)

COMPOSITE_EDGES = (
    (0, 3), (3, 9), (9, 6), (6, 0),
    (2, 5), (5, 11), (11, 8), (8, 2),
    (0, 2), (3, 5), (6, 8), (9, 11),
)

#: The slanted-corner-quad variant (the coplanar-vs-normal plane law):
#: the y~10 face's four corners are coplanar on a slanted plane
#: (normal (120, -1200, -40); no axis-constant coordinate — the old
#: axis-constant reading rejected exactly this shape), while every
#: other face stays axis-planar so the box stays closed.
COMPOSITE_SLANTED_POINTS = (
    (0.0, 8.0, 60.0),
    (0.0, 10.0, 0.0),
    (0.0, 110.0, 0.0),
    (0.0, 110.0, 30.0),
    (0.0, 110.0, 60.0),
    (20.0, 10.0, 0.0),
    (20.0, 10.0, 30.0),
    (20.0, 10.0, 60.0),
    (20.0, 12.0, 0.0),
    (20.0, 110.0, 0.0),
    (20.0, 110.0, 30.0),
    (20.0, 110.0, 60.0),
)

#: Face corners as coordinates, resolved to lex indices by the builder.
COMPOSITE_SLANTED_FACES = (
    (0x4A, (0.0, 0.0, -1.0), ((20.0, 12.0, 0.0), (0.0, 10.0, 0.0),
                              (20.0, 110.0, 0.0), (0.0, 110.0, 0.0))),
    (0x4A, (0.0, 1.0, 0.0), ((20.0, 110.0, 60.0), (20.0, 110.0, 0.0),
                             (0.0, 110.0, 60.0), (0.0, 110.0, 0.0))),
    (0x4A, (0.0, 0.0, 1.0), ((0.0, 8.0, 60.0), (20.0, 10.0, 60.0),
                             (0.0, 110.0, 60.0), (20.0, 110.0, 60.0))),
    (0x4A, (120.0, -1200.0, -40.0), ((20.0, 12.0, 0.0), (20.0, 10.0, 60.0),
                                     (0.0, 10.0, 0.0), (0.0, 8.0, 60.0))),
    (0x4C, (-1.0, 0.0, 0.0), ((0.0, 10.0, 0.0), (0.0, 8.0, 60.0),
                              (0.0, 110.0, 60.0), (0.0, 110.0, 0.0))),
    (0x4C, (1.0, 0.0, 0.0), ((20.0, 12.0, 0.0), (20.0, 110.0, 0.0),
                             (20.0, 110.0, 60.0), (20.0, 10.0, 60.0))),
)

#: The slanted variant's pool: the box's 8 quad corners (two of which
#: moved with the slanted face) — re-listed verbatim by the node list.
COMPOSITE_SLANTED_POOL = (
    (0.0, 10.0, 0.0),
    (20.0, 12.0, 0.0),
    (0.0, 110.0, 0.0),
    (20.0, 110.0, 0.0),
    (0.0, 110.0, 60.0),
    (20.0, 110.0, 60.0),
    (0.0, 8.0, 60.0),
    (20.0, 10.0, 60.0),
)

#: The big-form variant's element space: a 10 x 10 x 10 grid in lex
#: order (1,000 elements, all written; the region's write count 1,108
#: exceeds one byte -> the ff-escape P1g count).
COMPOSITE_GRID_SIDE = 10


def _composite_grid_points():
    return [
        (float(x), float(y), float(z))
        for x in range(COMPOSITE_GRID_SIDE)
        for y in range(COMPOSITE_GRID_SIDE)
        for z in range(COMPOSITE_GRID_SIDE)
    ]


def _composite_grid_element(x: int, y: int, z: int) -> int:
    return (x * COMPOSITE_GRID_SIDE + y) * COMPOSITE_GRID_SIDE + z


#: The grid box's faces over element indices (the 8 corners of the
#: 0..9 cube): 4 x 0x4a strips + 2 x 0x4c rings, 12 triangles.
COMPOSITE_GRID_FACES = (
    (0x4A, (0.0, 0.0, -1.0), (900, 0, 990, 90)),
    (0x4A, (0.0, 1.0, 0.0), (999, 990, 99, 90)),
    (0x4A, (0.0, 0.0, 1.0), (9, 909, 99, 999)),
    (0x4A, (0.0, -1.0, 0.0), (900, 909, 0, 9)),
    (0x4C, (-1.0, 0.0, 0.0), (0, 9, 99, 90)),
    (0x4C, (1.0, 0.0, 0.0), (900, 990, 999, 909)),
)

COMPOSITE_GRID_POOL_WALK = (
    (0.0, 0.0, 0.0),
    (9.0, 0.0, 0.0),
    (0.0, 9.0, 0.0),
    (9.0, 9.0, 0.0),
    (0.0, 9.0, 9.0),
    (9.0, 9.0, 9.0),
    (0.0, 0.0, 9.0),
    (9.0, 0.0, 9.0),
)


# --- stage-5 law fixtures (G6 stage 4b integration, #34, 2026-11-12) -----

#: The u24be variant's element space: a 40 x 40 x 41 grid (65,600
#: elements > 65,535 — a 2-byte ref cannot index the top corners; the
#: stage-4b width gap 1, 13bb5c0c's law).
COMPOSITE_U24_SHAPE = (40, 40, 41)


def _composite_u24_points():
    nx, ny, nz = COMPOSITE_U24_SHAPE
    return [
        (float(x), float(y), float(z))
        for x in range(nx)
        for y in range(ny)
        for z in range(nz)
    ]


def _composite_u24_element(x: int, y: int, z: int) -> int:
    nx, ny, nz = COMPOSITE_U24_SHAPE
    return (x * ny + y) * nz + z


#: The u24 grid box's faces over element indices (the 8 corners of the
#: 0..39 / 0..39 / 0..40 cube; same strip/ring topology as the 10-grid
#: box, so the export is a closed oriented manifold).  The top corners
#: exceed 65,535 (max 65,599): only a u24be parse can carry them.
COMPOSITE_U24_FACES = (
    (0x4A, (0.0, 0.0, -1.0), (63960, 0, 65559, 1599)),
    (0x4A, (0.0, 1.0, 0.0), (65599, 65559, 1639, 1599)),
    (0x4A, (0.0, 0.0, 1.0), (40, 64000, 1639, 65599)),
    (0x4A, (0.0, -1.0, 0.0), (63960, 64000, 0, 40)),
    (0x4C, (-1.0, 0.0, 0.0), (0, 40, 1639, 1599)),
    (0x4C, (1.0, 0.0, 0.0), (63960, 65559, 65599, 64000)),
)

#: The u24 grid's pool: the box's 8 corners (re-listed verbatim by the
#: node list; deliberate non-lex walk order, as in the 10-grid).
COMPOSITE_U24_POOL_WALK = (
    (0.0, 0.0, 0.0),
    (39.0, 0.0, 0.0),
    (0.0, 39.0, 0.0),
    (39.0, 39.0, 0.0),
    (0.0, 39.0, 40.0),
    (39.0, 39.0, 40.0),
    (0.0, 0.0, 40.0),
    (39.0, 0.0, 40.0),
)


def _composite_u24_edges() -> tuple[tuple[int, int], ...]:
    """The box's 12 edges over x <= 38 corners (every index <= 65,535,
    so the decorative 02 02 edge records stay u16be — the edge-table
    law's width set; the FACET records carry the >65,535 refs)."""
    g = _composite_u24_element
    return (
        (g(0, 0, 0), g(38, 0, 0)), (g(0, 0, 0), g(0, 39, 0)),
        (g(0, 0, 0), g(0, 0, 40)), (g(38, 0, 0), g(38, 39, 0)),
        (g(38, 0, 0), g(38, 0, 40)), (g(0, 39, 0), g(38, 39, 0)),
        (g(0, 39, 0), g(0, 39, 40)), (g(0, 0, 40), g(38, 0, 40)),
        (g(0, 0, 40), g(38, 0, 40)), (g(38, 39, 0), g(38, 39, 40)),
        (g(38, 39, 0), g(0, 39, 40)), (g(38, 0, 40), g(38, 39, 40)),
    )


#: The narrow-width tiebreak fixture's record (stage-4b width gap 2,
#: ef30cb2f's law): u16be refs (10, 260, 520, 770 — all z=0, coplanar
#: against the stored normal (0,0,1)) whose byte stream ALSO parses as
#: u8 refs (0, 10, 1, 4 — the high/low interleaving, nonplanar: z =
#: 0,0,1,4).  Three interleaved filler bytes follow, so neither parse
#: tiles onto the next header and u8/u16be tie on (tiling, repeats,
#: oob) — the committed narrower-width rule picked the u8 misread; the
#: stage-4b plane tiebreak picks u16be.
COMPOSITE_WIDTH_PLANE_REFS = (10, 260, 520, 770)
COMPOSITE_WIDTH_PLANE_NORMAL = (0.0, 0.0, 1.0)
COMPOSITE_WIDTH_PLANE_FILLER = b"\x0c\x0d\x0e"


def _composite_width_plane_record() -> bytes:
    return (
        bytes([0x01, 0x4A, 0x01, 0xFF])
        + struct.pack("<I", len(COMPOSITE_WIDTH_PLANE_REFS))
        + struct.pack("<fff", *COMPOSITE_WIDTH_PLANE_NORMAL)
        + bytes([len(COMPOSITE_WIDTH_PLANE_REFS)])
        + b"".join(struct.pack(">H", r) for r in COMPOSITE_WIDTH_PLANE_REFS)
        + COMPOSITE_WIDTH_PLANE_FILLER
    )


def _composite_elements(points, skip_slots=()):
    """(slot_value, point_or_None) per element in region order.

    The written points' slots follow the LCP law with the origin as the
    initial state (x-change = 0 -> [x][y][z], y-change = 3 -> [y][z],
    else 2 -> [z]); the skip slots (curve entries, U4) carry value 1
    and no coordinates.  ``points`` must be the region-order (lex)
    list.
    """
    skips = set(skip_slots)
    total = len(points) + len(skips)
    elements = []
    wi = 0
    px = py = 0.0
    for i in range(total):
        if i in skips:
            elements.append((1, None))
            continue
        x, y, z = points[wi]
        if x != px:
            slot = 0
        elif y != py:
            slot = 3
        else:
            slot = 2
        elements.append((slot, (x, y, z)))
        px, py = x, y
        wi += 1
    return elements


def _pack_slots(slots) -> bytes:
    """LSB-first 2-bit packing of the per-element slot values."""
    out = bytearray((len(slots) + 3) // 4)
    for i, v in enumerate(slots):
        out[i // 4] |= v << (2 * (i % 4))
    return bytes(out)


def _p1g_count(n: int) -> bytes:
    """P1g count: one byte when it fits, ff escaping to u32le."""
    return bytes([n]) if n < 0xFF else b"\xff" + struct.pack("<I", n)


def _composite_node_payload(elements, write_count_override: int | None = None):
    """The list node's payload under the P1t layout (stage 3b).

    29-B header + token + the declared counts (P1g) + the zero block +
    the 2-bit table (EXACTLY ceil(elem/4) bytes) + the P1g write count
    + the point region + a trailing region (U2).  The table's slots
    delimit the region writes, so the walk consumes exactly the
    declared count; ``write_count_override`` lies about it (the
    walk-mismatch variant's corruption).
    """
    words: list[bytes] = []
    for slot, pt in elements:
        if slot == 1:
            continue
        x, y, z = pt
        if slot == 0:
            words.append(struct.pack("<fff", x, y, z))
        elif slot == 3:
            words.append(struct.pack("<ff", y, z))
        else:
            words.append(struct.pack("<f", z))
    elem_decl = len(elements)
    header = (
        struct.pack("<I", 1)  # 00 00 00 01
        + struct.pack("<I", 7)  # node id
        + struct.pack("<I", 0)  # flags
        + struct.pack("<fff", 10.0, 60.0, 30.0)  # origin
        + struct.pack("<I", 3)  # kind
        + b"\x00"  # trailing header byte (the 29-B corpus header)
    )
    body = header
    body += LIST_TOKEN_MARKER
    body += _p1g_count(elem_decl) + _p1g_count(elem_decl)
    body += b"\x00\x00\x00\x00"  # the zero block
    body += _pack_slots([slot for slot, _pt in elements])
    # the P1g count counts f32 WORDS (3 per [x][y][z], 2 per [y][z],
    # 1 per [z]), not writes
    words_written = sum(
        (3 if s == 0 else 2 if s == 3 else 1)
        for s, _pt in elements
        if s != 1
    )
    write_count = words_written if write_count_override is None else write_count_override
    body += _p1g_count(write_count)
    body += b"".join(words)
    body += b"\x00\x00\x00\x00" + b"\x00\x04\x02\x0a" + b"\x02"  # trailing (U2)
    return body


LIST_TOKEN_MARKER = b"\xff\xff\x02\x00\x01"


def _composite_store(variant: str) -> bytes:
    """A composite store: pool + edge group + the list node (point
    region under the stage-3b table law) + facet records whose
    references are 0-based element indices in region order."""
    if variant.startswith("geometry-unrouted-elementspace"):
        return _unrouted_elementspace_store(variant)
    if variant in (
        "geometry-composite-law-multi-rep",
        "geometry-composite-law-multi-rep-partial",
        "geometry-composite-law-e0b-multi-rep-conservative",
        "geometry-composite-law-e0b-multi-rep-unsupported-veto",
    ):
        return _composite_multi_rep_store(variant)
    if variant in (
        "geometry-composite-law-raw-array",
        "geometry-composite-law-raw-array-wrong-offset",
        "geometry-composite-law-raw-array-unabsorbed",
        "geometry-composite-law-raw-array-strip-false-match",
        "geometry-composite-law-flat-near-zero",
    ):
        return _composite_raw_store(variant)
    if variant in (
        "geometry-composite-law-mixedwrite-multi-rep",
        "geometry-composite-law-mixedwrite-multi-rep-subnode",
    ):
        return _composite_mixedwrite_multi_rep_store(variant)
    if variant == "geometry-composite-law-table-overshoot":
        return _composite_table_overshoot_store()
    if variant == "geometry-composite-law-big":
        points = _composite_grid_points()
        elements = _composite_elements(points)
        pool_walk = COMPOSITE_GRID_POOL_WALK
        faces = COMPOSITE_GRID_FACES
        width = 2
        extra_record = None
        write_count_override = None
    elif variant == "geometry-composite-law-u16be":
        points = _composite_grid_points()
        elements = _composite_elements(points)
        pool_walk = COMPOSITE_GRID_POOL_WALK
        faces = COMPOSITE_GRID_FACES
        width = 2
        # The no-repeated-refs rule fixture: n = 4, u16be k = 1 (count
        # byte 4) + 4 u16be refs (1, 258, 769, 770 — distinct); the u8
        # misread with k = 5 (counts 4,0,0,0,0) + 4 u8 refs (3,1,3,2)
        # tiles exactly too but repeats refs inside the loop, so the
        # stage-3b rank picks u16be.  Both parses end at the same byte.
        extra_record = (
            bytes([0x01, 0x4C, 0x01, 0xFF])
            + struct.pack("<I", 4)
            + struct.pack("<fff", 0.0, 1.0, 0.0)
            + bytes([4, 0, 0, 0, 0])
            + bytes([0x00, 0x01, 0x01, 0x02, 0x03, 0x01, 0x03, 0x02])
        )
        write_count_override = None
    elif variant == "geometry-composite-law-u24be":
        # The stage-4b u24be width law: 65,600 elements (> 65,535 — a
        # 2-byte ref cannot index the top corners at 65,599); the box's
        # face records carry u24be refs and tile exactly only at
        # width 3.
        points = _composite_u24_points()
        elements = _composite_elements(points)
        pool_walk = COMPOSITE_U24_POOL_WALK
        faces = COMPOSITE_U24_FACES
        width = 3
        extra_record = None
        write_count_override = None
    elif variant == "geometry-composite-law-width-plane":
        # The stage-4b plane tiebreak: the extra record's u8/u16be
        # candidates tie on (tiling, repeats, oob) — three interleaved
        # filler bytes keep both off the next header — and the u8 read
        # is nonplanar against the stored normal while the u16be read
        # is coplanar, so the plane law picks u16be.
        points = _composite_grid_points()
        elements = _composite_elements(points)
        pool_walk = COMPOSITE_GRID_POOL_WALK
        faces = COMPOSITE_GRID_FACES
        width = 2
        extra_record = _composite_width_plane_record()
        write_count_override = None
    elif variant == "geometry-composite-law-slanted":
        points = list(COMPOSITE_SLANTED_POINTS)
        elements = _composite_elements(points)
        pool_walk = COMPOSITE_SLANTED_POOL
        faces = tuple(
            (mk, normal, tuple(points.index(c) for c in corners))
            for mk, normal, corners in COMPOSITE_SLANTED_FACES
        )
        width = 1
        extra_record = None
        write_count_override = None
    else:
        points = list(COMPOSITE_POINTS)
        skip_slots = ()
        pool_walk = COMPOSITE_POOL_WALK
        if variant == "geometry-composite-law-curve-entries":
            # 3 curve entries at element indices 4, 9, 14; the element
            # space is 15 slots over the 12 written points.
            skip_slots = (4, 9, 14)
            elements = _composite_elements(points, skip_slots)
            # written rank -> element index: walk past every skip at or
            # before the position (cascading)
            def _elem(r: int) -> int:
                e = r
                for s in skip_slots:
                    if s <= e:
                        e += 1
                    else:
                        break
                return e

            faces = tuple(
                (mk, normal, tuple(_elem(r) for r in refs))
                for mk, normal, refs in COMPOSITE_FACES
            )
            # one extra loop references a skip slot (element 4) plus
            # written points 0, 5, 6: not exportable (U4), named.
            extra_record = _facet_record(
                0x4C, (0.0, 0.0, -1.0), (4, _elem(0), _elem(5), _elem(6))
            )
            width = 1
            write_count_override = None
        elif variant.startswith("geometry-composite-law-e0b"):
            # Stage-10 E0-b dup-pin fixtures (#34, 2026-11-12): skip
            # slots at ELEMENT indices 2, 6, 10 over the 12-point box;
            # each pin welds to the preceding written element — element
            # 1 = P1 (0,10,30), element 5 = P4 (0,110,30), element 9 =
            # P7 (20,10,30).  The e0b records' loops are given in
            # ELEMENT indices; the pinned points sit on the box's
            # y=10 / y=110 faces, so a dup-pinned loop is coplanar with
            # the stored normal (0,1,0) — the battery-supported E0-b
            # shape (the landed analysis's restricted subset).
            skip_slots = (2, 6, 10)
            if variant == "geometry-composite-law-e0b-unpinnable":
                # the unpinnable variant's skip slot is ELEMENT 0 (see
                # the variant branch below): the walk-back has no
                # preceding written element to weld to.
                skip_slots = (0,)
            elements = _composite_elements(points, skip_slots)

            def _e0b_record(
                marker: int, normal, loops: tuple[tuple[int, ...], ...]
            ) -> bytes:
                # one facet record with k = len(loops) count bytes (the
                # multi-loop record form; _facet_record writes k = 1)
                refs = [r for loop in loops for r in loop]
                rec = bytes([0x01, marker, 0x01, 0xFF])
                rec += struct.pack("<I", len(refs))
                if normal is not None:
                    rec += struct.pack("<fff", *normal)
                return rec + bytes(len(loop) for loop in loops) + bytes(refs)

            # skip 2 pins P1: coplanar fan (rank 1,0,6),(1,6,2) on y=10
            skip_loop_a = (2, 0, 8, 3)
            # skip 6 pins P4: coplanar fan (4,3,9),(4,9,5) on y=110
            skip_loop_b = (6, 4, 12, 7)
            # skip 6 pins P4 but the loop also carries P1 (y=10):
            # NONPLANAR under the pin (the 3dff4d93 shape)
            skip_loop_bad = (6, 4, 12, 1)
            faces = ()
            width = 1
            write_count_override = None
            if variant == "geometry-composite-law-e0b-dup-pin":
                # 2 dropped loops, BOTH coplanar under the pin: the law
                # fires (the 2fca9bc4 / 505bbe1f shape).
                extra_record = _e0b_record(
                    0x4C, (0.0, 1.0, 0.0), (skip_loop_a, skip_loop_b)
                )
            elif variant == "geometry-composite-law-e0b-single-loop":
                # 1 dropped loop, coplanar: fires (the 4ad53b87 /
                # 4ae0392d shape).
                extra_record = _facet_record(0x4C, (0.0, 1.0, 0.0), skip_loop_a)
            elif variant == "geometry-composite-law-e0b-nonplanar":
                # one coplanar + one NONPLANAR dropped loop: not
                # battery-supported -> the conservative rule holds.
                extra_record = _facet_record(
                    0x4C, (0.0, 1.0, 0.0), skip_loop_a
                ) + _e0b_record(0x4C, (0.0, 1.0, 0.0), (skip_loop_bad,))
            elif variant == "geometry-composite-law-e0b-normal-less":
                # one coplanar loop + one on a NORMAL-LESS 0x42 strip
                # (the 08f2eccb mixed-coverage shape): untestable ->
                # the conservative rule holds.
                extra_record = _facet_record(
                    0x4C, (0.0, 1.0, 0.0), skip_loop_a
                ) + _facet_record(0x42, None, skip_loop_b)
            elif variant == "geometry-composite-law-e0b-unpinnable":
                # the UNPINNABLE arm (stage-10 review F4): the dropped
                # loop's skip slot is ELEMENT 0 — no preceding written
                # element exists to weld to — so the law rejects before
                # the battery and the store keeps the conservative rule.
                extra_record = _facet_record(
                    0x4C, (0.0, 0.0, -1.0), (0, 6, 9, 3)
                )
            else:  # geometry-composite-law-e0b-nonempty
                # the box exports its 12 triangles AND carries a
                # battery-supported dropped loop: the primary mesh is
                # NOT empty -> the store-level conservative gate holds
                # (the 471-passing stores' shape).  The box's faces are
                # written over WRITTEN indices — remapped through the
                # skip layout (the curve-entries variant's _elem walk).
                def _elem(r: int) -> int:
                    e = r
                    for s in skip_slots:
                        if s <= e:
                            e += 1
                        else:
                            break
                    return e

                faces = tuple(
                    (mk, normal, tuple(_elem(r) for r in refs))
                    for mk, normal, refs in COMPOSITE_FACES
                )
                extra_record = _facet_record(0x4C, (0.0, 1.0, 0.0), skip_loop_a)
        else:
            elements = _composite_elements(points)
            faces = COMPOSITE_FACES
            width = 1
            extra_record = None
            write_count_override = (
                17 + 2 if variant == "geometry-composite-law-walk-mismatch" else None
            )
            if variant == "geometry-composite-law-walk-nan":
                # Walk-exact with a non-finite coordinate (stage-6
                # trigger-ordering pin): the walk's own failure — the
                # raw-array law must not swallow it (the probe walk is
                # exact, so the store is not the walk-mismatch family).
                slot, (x, y, _z) = elements[5]
                elements[5] = (slot, (x, y, float("nan")))
    if variant == "geometry-composite-law-unabsorbed":
        # The pool carries a vertex the node list does not re-list:
        # the unabsorbed variant (pool absorption not established).
        pool_walk = COMPOSITE_POOL_WALK + ((0.0, 0.0, 999.5),)

    node_payload = _composite_node_payload(elements, write_count_override)
    if variant == "geometry-composite-law-u24be":
        # The u24 grid box's 12 edges over x <= 38 corners (every index
        # <= 65,535: the decorative 02 02 edge records stay u16be — the
        # edge-table law's width set; the FACET records carry the
        # >65,535 refs the u24be law exists for).
        edge_records = b"".join(
            b"\x02\x02" + struct.pack(">HH", a, b)
            for a, b in _composite_u24_edges()
        )
    elif variant in (
        "geometry-composite-law-big",
        "geometry-composite-law-u16be",
        "geometry-composite-law-width-plane",
    ):
        # The grid box's 12 edges as u16be element-index pairs (the F8
        # 6-byte 02 02 record form; grid corner indices).
        g = _composite_grid_element
        edges = (
            (g(0, 0, 0), g(9, 0, 0)), (g(0, 0, 0), g(0, 9, 0)),
            (g(0, 0, 0), g(0, 0, 9)), (g(9, 0, 0), g(9, 9, 0)),
            (g(9, 0, 0), g(9, 0, 9)), (g(0, 9, 0), g(9, 9, 0)),
            (g(0, 9, 0), g(0, 9, 9)), (g(0, 0, 9), g(9, 0, 9)),
            (g(0, 0, 9), g(9, 0, 9)), (g(9, 9, 0), g(9, 9, 9)),
            (g(9, 9, 0), g(0, 9, 9)), (g(9, 0, 9), g(9, 9, 9)),
        )
        edge_records = b"".join(
            b"\x02\x02" + struct.pack(">HH", a, b) for a, b in edges
        )
    else:
        edge_records = b"".join(
            b"\x02\x02" + struct.pack(">BB", a, b) for a, b in COMPOSITE_EDGES
        )
    body_parts = [
        NESTED_FULL_WRAP
        + NESTED_POOL_SUBKIND
        + bytes([len(pool_walk)])
        + b"".join(
            NESTED_VREC + struct.pack("<fff", *v) for v in pool_walk
        ),
        # The composite marker: an 01 02 edge group whose records are
        # the box's 12 edges as element indices (F8/E2).
        NESTED_FULL_WRAP
        + NESTED_EDGE_SUBKIND
        + bytes([12])
        + edge_records,
        b"\x04\x04\xfd\xff" + node_payload,
    ]
    for marker, normal, refs in faces:
        body_parts.append(_facet_record(marker, normal, refs, width=width))
    if extra_record is not None:
        body_parts.append(extra_record)
    body = b"".join(body_parts)

    catalog_len = NESTED_CATALOG_LEN
    d8n = 32 + len(body)
    header = (
        MAGIC
        + struct.pack(">II", d8n, catalog_len)
        + b"\xff" * 8
        + b"\x00" * 8
    )
    catalog = NESTED_CB0001 + struct.pack(
        ">7I", 1, 0, 0xE7, 0xE7, 0, 0, catalog_len
    ) + TRAILER_MARKER
    tail126 = registration_block() + b"\x00" * (126 - 41)
    return header + body + catalog + tail126


def _unrouted_elementspace_store(variant: str) -> bytes:
    """Stage-13 second-chance element-space fixtures (#34, 2026-11-13).

    The composite element-space structure (the list node's point region
    + facet records over 0-based element indices) WITHOUT its routing
    markers: no ``01 02`` edge group and no ``ff ..`` opener, so
    ``pool.has_composite_space`` is false and the clean path owns the
    store.  The base box's facet records reference elements 0..11
    while the pool re-lists only 8 corners — the corpus refs-beyond
    family's exact shape (stage-13 note section 2).

    - ``...-refs-beyond``: pool wrapper + node + facets.  The clean
      path raises ``facet references beyond the pool`` (max ref 11 >=
      pool 8); the second-chance route decodes the node region (the
      pool absorbs verbatim) and exports all 12 points / 12 triangles.
    - ``...-no-pool``: node + facets, NO pool wrapper.  The clean path
      raises the G2 P8 no-pool error; the composite decode runs with an
      empty pool (the absorption gate is vacuous) and exports the 12
      node points.
    - ``...-no-node``: facets only.  The second chance declines (no
      token-bearing list node) and the ORIGINAL no-pool error
      re-raises unchanged (the fail-closed negative).
    - ``...-walk-mismatch``: node + facets, the node's declared write
      count does not match its region (the stage-6 walk-mismatch
      signature); every composite gate raises and the ORIGINAL no-pool
      error re-raises unchanged.
    """
    points = list(COMPOSITE_POINTS)
    elements = _composite_elements(points)
    body_parts = []
    with_pool = variant == "geometry-unrouted-elementspace-refs-beyond"
    with_node = variant != "geometry-unrouted-elementspace-no-node"
    if with_pool:
        body_parts.append(
            NESTED_FULL_WRAP
            + NESTED_POOL_SUBKIND
            + bytes([len(COMPOSITE_POOL_WALK)])
            + b"".join(
                NESTED_VREC + struct.pack("<fff", *v) for v in COMPOSITE_POOL_WALK
            )
        )
    if with_node:
        node_payload = _composite_node_payload(elements)
        if variant == "geometry-unrouted-elementspace-walk-mismatch":
            # the walk-mismatch signature: the declared write count
            # exceeds the region's words, so the walk ends short of the
            # declared region (decode_region raises).
            node_payload = _composite_node_payload(
                elements, write_count_override=17 + 2
            )
        body_parts.append(b"\x04\x04\xfd\xff" + node_payload)
    for marker, normal, refs in COMPOSITE_FACES:
        body_parts.append(_facet_record(marker, normal, refs))
    body = b"".join(body_parts)

    catalog_len = NESTED_CATALOG_LEN
    d8n = 32 + len(body)
    header = (
        MAGIC
        + struct.pack(">II", d8n, catalog_len)
        + b"\xff" * 8
        + b"\x00" * 8
    )
    catalog = NESTED_CB0001 + struct.pack(
        ">7I", 1, 0, 0xE7, 0xE7, 0, 0, catalog_len
    ) + TRAILER_MARKER
    tail126 = registration_block() + b"\x00" * (126 - 41)
    return header + body + catalog + tail126


def _composite_multi_rep_store(variant: str) -> bytes:
    """A two-rep composite store (stage-4b per-rep law, #34).

    Rep k = (the k-th ``01 06`` pool group, the k-th token-bearing list
    node, the facet records in that node's territory).  Rep 0 is the
    12-point box; rep 1 the same box translated +200 in x with its own
    pool group and its own node — each pool re-lists verbatim in
    exactly its own rep's region (the body-order diagonal).  The
    stage-3d single-rep reading fails the absorption gate here (the
    pool concatenates BOTH groups, rep 0's region re-lists only its
    own); the per-rep reading exports both reps' geometry merged.

    ``geometry-composite-law-multi-rep-partial`` adds a 9th vertex to
    rep 1's pool group that no region re-lists: rep 1 stays unexported
    (per-rep fail-closed — a rep that does not absorb is not guessed),
    rep 0 exports alone.
    """
    pts0 = list(COMPOSITE_POINTS)
    pts1 = [(x + 200.0, y, z) for x, y, z in COMPOSITE_POINTS]
    pool0 = COMPOSITE_POOL_WALK
    pool1 = tuple((x + 200.0, y, z) for x, y, z in COMPOSITE_POOL_WALK)
    if variant == "geometry-composite-law-multi-rep-partial":
        # the un-absorbed 9th vertex of rep 1's pool group
        pool1 = pool1 + ((999.5, 10.0, 0.0),)
    elements0 = _composite_elements(pts0)
    rep0_records = COMPOSITE_FACES
    if variant == "geometry-composite-law-e0b-multi-rep-conservative":
        # stage-10 (#34): rep 1 carries skip slots (2, 6, 10 — the pins
        # are P1/P4/P7 +200x) and ONE battery-supported dropped loop;
        # rep 0 exports its box, so the store's mesh is NOT empty and
        # the store-level conservative gate holds (a rep-level fire
        # would regress the store's L2 state).
        elements1 = _composite_elements(pts1, (2, 6, 10))
        rep1_records = ((0x4C, (0.0, 1.0, 0.0), (2, 0, 8, 3)),)
    elif variant == "geometry-composite-law-e0b-multi-rep-unsupported-veto":
        # stage-10 review F1 (#34): BOTH reps' primary triangulations
        # are empty — rep 0 carries a NORMAL-LESS (untestable) dropped
        # loop, rep 1 the battery-supported dropped loop.  The store's
        # mesh is empty, so the store-level gate decides: one
        # unsupported rep keeps the WHOLE store conservative (the
        # gate's None-candidate veto; the F1 bug fired rep 1's pins
        # here and zeroed the curve-entry counters).
        elements0 = _composite_elements(pts0, (2, 6, 10))
        elements1 = _composite_elements(pts1, (2, 6, 10))
        rep0_records = ((0x42, None, (2, 0, 8, 3)),)
        rep1_records = ((0x4C, (0.0, 1.0, 0.0), (2, 0, 8, 3)),)
    else:
        elements1 = _composite_elements(pts1)
        rep1_records = COMPOSITE_FACES
    body_parts = [
        NESTED_FULL_WRAP
        + NESTED_POOL_SUBKIND
        + bytes([len(pool0)])
        + b"".join(
            NESTED_VREC + struct.pack("<fff", *v) for v in pool0
        ),
        NESTED_FULL_WRAP
        + NESTED_POOL_SUBKIND
        + bytes([len(pool1)])
        + b"".join(
            NESTED_VREC + struct.pack("<fff", *v) for v in pool1
        ),
        # the edge group: the box's 12 edges over rep 0's element
        # indices (decorative; edge tables do not triangulate)
        NESTED_FULL_WRAP
        + NESTED_EDGE_SUBKIND
        + bytes([12])
        + b"".join(
            b"\x02\x02" + struct.pack(">BB", a, b) for a, b in COMPOSITE_EDGES
        ),
        b"\x04\x04\xfd\xff" + _composite_node_payload(elements0),
    ]
    for marker, normal, refs in rep0_records:
        body_parts.append(_facet_record(marker, normal, refs, width=1))
    body_parts.append(b"\x04\x04\xfd\xff" + _composite_node_payload(elements1))
    for marker, normal, refs in rep1_records:
        body_parts.append(_facet_record(marker, normal, refs, width=1))
    body = b"".join(body_parts)

    catalog_len = NESTED_CATALOG_LEN
    d8n = 32 + len(body)
    header = (
        MAGIC
        + struct.pack(">II", d8n, catalog_len)
        + b"\xff" * 8
        + b"\x00" * 8
    )
    catalog = NESTED_CB0001 + struct.pack(
        ">7I", 1, 0, 0xE7, 0xE7, 0, 0, catalog_len
    ) + TRAILER_MARKER
    tail126 = registration_block() + b"\x00" * (126 - 41)
    return header + body + catalog + tail126


def _composite_raw_node_payload(points, escape: str = "end") -> bytes:
    """A walk-mismatch list-node payload carrying the stage-4a raw-array
    layout (G6 stage 6, #34): ``[token][count1][count2][tail][elem_decl
    x [x][y][z] stride 12, x ascending][FF][count3 u32le][trail]`` — no
    zero block, no 2-bit table, no write count: the declared P1t prefix
    does not describe this payload (the table walk overruns at element
    0, the raw-array law's trigger signature).

    The array starts at 40 (4-aligned, inside the committed candidate
    range 32..64); the tail-escape byte ``payload[start + 12*elem_decl]``
    is ``0xFF`` and no other candidate start's array end carries one
    (the start rule pins start 40 uniquely — count3 480 = ``e0 01 00
    00``, then zero trail bytes).

    ``escape="wrong"`` moves the escape byte one past every candidate's
    array end (offset array_end + 1): the trail-escape condition
    selects 0 candidate starts -> the start rule stays fail-closed.
    """
    header = (
        struct.pack("<I", 1)  # 00 00 00 01
        + struct.pack("<I", 7)  # node id
        + struct.pack("<I", 0)  # flags
        + struct.pack("<fff", 10.0, 60.0, 30.0)  # origin
        + struct.pack("<I", 3)  # kind
        + b"\x00"  # trailing header byte (the 29-B corpus header)
    )
    body = header
    body += LIST_TOKEN_MARKER
    body += _p1g_count(len(points)) + _p1g_count(len(points))
    body += b"\x00\x00\x00\x01"  # the tail field (the observed 4-B form)
    start = 40
    assert len(body) == start, "the raw array must start 4-aligned at 40"
    body += b"".join(struct.pack("<fff", *p) for p in points)
    end = start + 12 * len(points)
    if escape == "end":
        body += b"\xff" + struct.pack("<I", 480) + b"\x00\x00\x00\x00"
    elif escape == "wrong":
        # one byte of filler, THEN the escape: payload[end] != 0xff for
        # every candidate start (0 selections, fail-closed)
        body += b"\x00\xff" + struct.pack("<I", 480) + b"\x00\x00\x00"
    else:  # pragma: no cover - builder guard
        raise ValueError(f"unknown escape placement: {escape}")
    assert len(body) > end
    return body


#: The stage-9 false-match floats (artifact 1): adjacent f32s whose
#: little-endian bytes ``00 00 01 45`` and ``00 ff 00 42`` contain the
#: STRIP_RE sequence ``01 45 00 ff`` — a false strip header INSIDE the
#: point region.  Both floats are nice raw coordinates (2064.0 and
#: ~35.97), so the region stays a valid raw/flat reading.
STRIP_FALSE_MATCH_Y = struct.unpack("<f", bytes.fromhex("00000145"))[0]
STRIP_FALSE_MATCH_Z = struct.unpack("<f", bytes.fromhex("00ff0042"))[0]

#: The stage-9 near-zero coordinates (artifact 3): the note's measured
#: values (7d27c73d z = -1.19e-14, dd610ca5 x = 9.4e-15) — real
#: tessellation coordinates the raw scan's 1e-6 floor rejects and the
#: exporter predicate accepts.
NEAR_ZERO_A = struct.unpack("<f", struct.pack("<f", -1.19e-14))[0]
NEAR_ZERO_B = struct.unpack("<f", struct.pack("<f", 9.4e-15))[0]


def _composite_raw_store(variant: str) -> bytes:
    """A composite store whose list node carries the stage-4a raw-array
    layout (G6 stage 6, #34).

    ``geometry-composite-law-raw-array``: the 12-point box's element
    space rides as raw f32 triples (x-ascending, all nice); the pool
    re-lists verbatim in the triples; the facet records reference the
    array indices — the store exports through the raw path (stage
    ``identity-raw-array``, closed manifold).

    ``geometry-composite-law-raw-array-wrong-offset``: the trail-escape
    byte sits one past every candidate start's array end — the start
    rule cannot pin a start.  Stage 9 note: the flat law (no escape
    required) decodes the same region, so the store exports through the
    mixed-write composition (the raw start rule's fail-closed arm is
    pinned at unit level).

    ``geometry-composite-law-raw-array-unabsorbed``: the pool carries a
    9th vertex the triples do not re-list — strong fit, but absorption
    is not established -> fail-closed (the scan's 6/35 non-absorbed
    strong-fit stores; the composition fails on the same ground).

    ``geometry-composite-law-raw-array-strip-false-match`` (stage-8
    artifact 1, #34 stage 9): a 13th triple carries the STRIP_RE false
    match ``01 45 00 ff`` (two adjacent nice floats) — the single-rep
    window truncates the node mid-region, the raw law's 12*elem_decl
    span no longer fits the truncated payload (0 escape candidates),
    and the full-body per-rep scan recovers the raw region (stage
    ``identity-mixedwrite-reps``).

    ``geometry-composite-law-flat-near-zero`` (stage-8 artifact 3, #34
    stage 9): the four non-pool triples carry near-zero coordinates
    (|v| ~ 1e-14) — the raw law weak-fits under its 1e-6 floor (nice
    8/12 = 0.667 < 0.98, the d51eb38c shape) and the flat law (start
    pinned by counts_end, the exporter predicate) decodes the region
    (stage ``identity-mixedwrite-reps``).
    """
    points = list(COMPOSITE_POINTS)
    pool_walk = COMPOSITE_POOL_WALK
    escape = "end"
    if variant == "geometry-composite-law-raw-array-wrong-offset":
        escape = "wrong"
    elif variant == "geometry-composite-law-raw-array-unabsorbed":
        pool_walk = COMPOSITE_POOL_WALK + ((0.0, 0.0, 999.5),)
    elif variant == "geometry-composite-law-raw-array-strip-false-match":
        # the false match rides the 13th triple's (y, z): adjacent
        # floats whose bytes contain 01 45 00 ff (nice coordinates, so
        # the region stays a valid raw reading on the FULL payload)
        points = points + [(30.0, STRIP_FALSE_MATCH_Y, STRIP_FALSE_MATCH_Z)]
    elif variant == "geometry-composite-law-flat-near-zero":
        # the four z-edge midpoints (non-pool elements) carry near-zero
        # coordinates: the pool corners stay clean nice floats (exact
        # f32 absorption), the raw nice rate drops to 8/12
        points = [
            (x, y, z)
            for x, y, z in COMPOSITE_POINTS
        ]
        for i, (x, y, z) in enumerate(points):
            if (x, y, z) in (
                (0.0, 10.0, 30.0),
                (0.0, 110.0, 30.0),
                (20.0, 10.0, 30.0),
                (20.0, 110.0, 30.0),
            ):
                nz = NEAR_ZERO_A if i % 2 == 0 else NEAR_ZERO_B
                points[i] = (x, nz, z)
    node_payload = _composite_raw_node_payload(points, escape=escape)
    body_parts = [
        NESTED_FULL_WRAP
        + NESTED_POOL_SUBKIND
        + bytes([len(pool_walk)])
        + b"".join(
            NESTED_VREC + struct.pack("<fff", *v) for v in pool_walk
        ),
        NESTED_FULL_WRAP
        + NESTED_EDGE_SUBKIND
        + bytes([12])
        + b"".join(
            b"\x02\x02" + struct.pack(">BB", a, b) for a, b in COMPOSITE_EDGES
        ),
        b"\x04\x04\xfd\xff" + node_payload,
    ]
    for marker, normal, refs in COMPOSITE_FACES:
        body_parts.append(_facet_record(marker, normal, refs, width=1))
    body = b"".join(body_parts)

    catalog_len = NESTED_CATALOG_LEN
    d8n = 32 + len(body)
    header = (
        MAGIC
        + struct.pack(">II", d8n, catalog_len)
        + b"\xff" * 8
        + b"\x00" * 8
    )
    catalog = NESTED_CB0001 + struct.pack(
        ">7I", 1, 0, 0xE7, 0xE7, 0, 0, catalog_len
    ) + TRAILER_MARKER
    tail126 = registration_block() + b"\x00" * (126 - 41)
    return header + body + catalog + tail126


def _composite_mixedwrite_multi_rep_store(variant: str) -> bytes:
    """A two-rep walk-mismatch composite store (stage-9 composition,
    #34 stage 9): both reps ride the stage-4a raw-array layout, so the
    single-rep table walk raises and the raw-array law declines the
    store (the concatenated pool spans both groups; no single region
    re-lists it all) — the stage-8 mixed-write composition decodes both
    nodes on the full-body window, absorbs each pool group by its
    diagonal rep's region, and exports both reps' boxes merged (stage
    ``identity-mixedwrite-reps``).

    ``geometry-composite-law-mixedwrite-multi-rep-subnode`` adds a 9th
    vertex to rep 1's pool group that no region re-lists (the 05 08 01
    sub-node records' residue): the element index is unpinned, the
    store stays fail-closed for export (the stage-8 note's integration
    item (e); the corpus bad44bdf class).
    """
    pts0 = list(COMPOSITE_POINTS)
    pts1 = [(x + 200.0, y, z) for x, y, z in COMPOSITE_POINTS]
    pool0 = COMPOSITE_POOL_WALK
    pool1 = tuple((x + 200.0, y, z) for x, y, z in COMPOSITE_POOL_WALK)
    if variant == "geometry-composite-law-mixedwrite-multi-rep-subnode":
        pool1 = pool1 + ((999.5, 10.0, 0.0),)
    body_parts = [
        NESTED_FULL_WRAP
        + NESTED_POOL_SUBKIND
        + bytes([len(pool0)])
        + b"".join(
            NESTED_VREC + struct.pack("<fff", *v) for v in pool0
        ),
        NESTED_FULL_WRAP
        + NESTED_POOL_SUBKIND
        + bytes([len(pool1)])
        + b"".join(
            NESTED_VREC + struct.pack("<fff", *v) for v in pool1
        ),
        NESTED_FULL_WRAP
        + NESTED_EDGE_SUBKIND
        + bytes([12])
        + b"".join(
            b"\x02\x02" + struct.pack(">BB", a, b) for a, b in COMPOSITE_EDGES
        ),
        b"\x04\x04\xfd\xff" + _composite_raw_node_payload(pts0),
    ]
    for marker, normal, refs in COMPOSITE_FACES:
        body_parts.append(_facet_record(marker, normal, refs, width=1))
    body_parts.append(b"\x04\x04\xfd\xff" + _composite_raw_node_payload(pts1))
    for marker, normal, refs in COMPOSITE_FACES:
        body_parts.append(_facet_record(marker, normal, refs, width=1))
    body = b"".join(body_parts)

    catalog_len = NESTED_CATALOG_LEN
    d8n = 32 + len(body)
    header = (
        MAGIC
        + struct.pack(">II", d8n, catalog_len)
        + b"\xff" * 8
        + b"\x00" * 8
    )
    catalog = NESTED_CB0001 + struct.pack(
        ">7I", 1, 0, 0xE7, 0xE7, 0, 0, catalog_len
    ) + TRAILER_MARKER
    tail126 = registration_block() + b"\x00" * (126 - 41)
    return header + body + catalog + tail126


def _composite_table_overshoot_store() -> bytes:
    """A table-law composite store whose region opens with 20 full-write
    slots (stage-8 artifact 2, #34 stage 9): the 2-bit table's first 4
    bytes are zero (16 leading full-write slots), so the committed
    layout() zero-group skip overshoots INTO the table, the P1g count
    reads a region byte (0) and the walk fails at element 0 ("0 left of
    the declared 0" — the 221df959 shape).  The stage-8 extent law
    selects the unique walk-exact extent (the true table at
    counts_end + 4; the shifted extent reads a zero count and cannot
    walk exact) -> the store exports through the mixed-write
    composition (stage ``identity-mixedwrite-reps``)."""
    # 20 elements, strictly ascending x off the LCP origin (x = 1 + 3i:
    # every slot 0 = full write, so the table's first 4 bytes are zero);
    # the box corners sit at COMPOSITE_FACES's corner indices
    corner_idx = (0, 2, 3, 5, 6, 8, 9, 11)
    points = []
    for i in range(20):
        if i in corner_idx:
            k = corner_idx.index(i)
            y = 10.0 if k in (0, 1, 4, 5) else 110.0
            z = 0.0 if k in (0, 1, 2, 3) else 60.0
            points.append((1.0 + 3.0 * i, y, z))
        else:
            points.append((1.0 + 3.0 * i, 50.0, 30.0))
    corner_points = tuple(points[i] for i in corner_idx)
    elements = _composite_elements(points)
    node_payload = _composite_node_payload(elements)
    body_parts = [
        NESTED_FULL_WRAP
        + NESTED_POOL_SUBKIND
        + bytes([len(corner_points)])
        + b"".join(
            NESTED_VREC + struct.pack("<fff", *v) for v in corner_points
        ),
        NESTED_FULL_WRAP
        + NESTED_EDGE_SUBKIND
        + bytes([12])
        + b"".join(
            b"\x02\x02" + struct.pack(">BB", a, b) for a, b in COMPOSITE_EDGES
        ),
        b"\x04\x04\xfd\xff" + node_payload,
    ]
    for marker, normal, refs in COMPOSITE_FACES:
        body_parts.append(_facet_record(marker, normal, refs, width=1))
    body = b"".join(body_parts)

    catalog_len = NESTED_CATALOG_LEN
    d8n = 32 + len(body)
    header = (
        MAGIC
        + struct.pack(">II", d8n, catalog_len)
        + b"\xff" * 8
        + b"\x00" * 8
    )
    catalog = NESTED_CB0001 + struct.pack(
        ">7I", 1, 0, 0xE7, 0xE7, 0, 0, catalog_len
    ) + TRAILER_MARKER
    tail126 = registration_block() + b"\x00" * (126 - 41)
    return header + body + catalog + tail126


def _composite_payload(variant: str) -> bytes:
    if variant == "geometry-othercontainer-composite-law":
        return _nested_store_block(
            b"CATBRepModeContainer", _composite_store("geometry-composite-law")
        )
    preamble = 250 - len(storage_property_block(b"CATStdCont", b"CATContainer"))
    return (
        storage_property_block(b"CATStdCont", b"CATContainer")
        + b"\x00" * preamble
        + _composite_store(variant)
    )


def _geometry_store(variant: str) -> bytes:
    """The nested V5_CFV2 stream store: 32-byte header (big-endian
    dword8 = catalog offset, dword12 = catalog tail length, N2), body,
    minimal catalog (CB0001 magic + 36 B trailer satisfying the G1 N6
    laws: CB__END, C == D, G == tail length) and the 126 B inter-block
    tail with the writer registration block (N9).

    Stage-3a tail variants (#34): ``geometry-overshoot-tail`` overshoots
    dword8 by 9 B (G1 C3 — the shipped tail end runs past ``CB__END``);
    ``geometry-padded-tail`` zero-pads the 52-B catalog to dword12 =
    128 (G1 padded-tail — the trailer sits inside the tail);
    ``geometry-overshoot-bad-tail`` breaks C == D on top of the
    overshoot, so neither tail family recovers (fail-closed)."""
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
    if variant in ("geometry-composite-index-space", "geometry-seebody-composite"):
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
    d12n = NESTED_CATALOG_LEN
    after_catalog = b""
    if variant in ("geometry-overshoot-tail", "geometry-overshoot-bad-tail"):
        # G1 C3: dword8 overshoots the catalog magic by k = 9 (a corpus
        # family value); the shipped tail window inherits the same
        # overshoot and runs k B past CB__END.
        d8n += OVERSHOOT_K
        after_catalog = b"\x00" * OVERSHOOT_K
    elif variant == "geometry-padded-tail":
        # G1 padded-tail: the trailer sits inside the tail; dword12 is
        # rounded up and the difference is zero padding.
        d12n = PADDED_TAIL_LEN
    nested_magic = b"V5_CFV3\x00" if variant == "geometry-bad-nested-magic" else MAGIC
    header = nested_magic + struct.pack(">II", d8n, d12n) + b"\xff" * 8 + b"\x00" * 8
    catalog = NESTED_CB0001 + struct.pack(
        ">7I", 1, 0, 0xE7, 0xE8 if variant == "geometry-overshoot-bad-tail" else 0xE7, 0, 0, catalog_len
    ) + TRAILER_MARKER
    tail126 = registration_block() + b"\x00" * (126 - 41)
    if variant == "geometry-padded-tail":
        padding = b"\x00" * (PADDED_TAIL_LEN - NESTED_CATALOG_LEN)
        return header + body + catalog + padding + tail126
    return header + body + catalog + after_catalog + tail126


#: Stage-3a tail-variant constants (#34): the dword8 overshoot k (the
#: census family spans 5..28, mode 13; 9 appears twice) and the padded
#: dword12 (corpus rounds to 3,072/4,096; the fixture uses a small one).
OVERSHOOT_K = 9
PADDED_TAIL_LEN = 128


def _nested_store_block(name: bytes, store_bytes: bytes | None) -> bytes:
    """One storage block carrying (or not carrying) a nested store.

    With a store, the preamble lands its origin at block + 250 (G1 N1h:
    the 248..268 window covers 1,051/1,056 corpus header stores); with
    ``None`` the block region is marker-free filler (G1 N10's
    store-less family)."""
    block = storage_property_block(name, b"CATContainer")
    if store_bytes is None:
        return block + b"\x00" * 96
    preamble = 250 - len(block)
    return block + b"\x00" * preamble + store_bytes


def _geometry_payload(variant: str) -> bytes:
    """The storage blocks + property preambles + nested store(s).

    Default: one ``CATStdCont`` block carrying the store. The stage-3a
    recovery variants place the store per its census family (#34):
    ``geometry-seebody-store``/``-seebody-composite``/``-seebody-empty``
    in a ``CATSeeBodyCont`` block (no ``CATStdCont`` block at all — the
    no_stdcont family), ``geometry-xdoclink-store`` in a
    ``CATXDocLinkCont`` block behind a store-less ``CATStdCont`` block
    (the next_block_store family)."""
    if variant in ("geometry-seebody-store", "geometry-seebody-composite"):
        return _nested_store_block(b"CATSeeBodyCont", _geometry_store(variant))
    if variant == "geometry-seebody-empty":
        return _nested_store_block(b"CATSeeBodyCont", None)
    if variant == "geometry-xdoclink-store":
        return _nested_store_block(b"CATStdCont", None) + _nested_store_block(
            b"CATXDocLinkCont", _geometry_store(variant)
        )
    if variant == "geometry-othercontainer-store":
        return _nested_store_block(b"CATBRepModeContainer", _geometry_store(variant))
    if variant == "geometry-othercontainer-behind-empty-stdcont":
        return _nested_store_block(b"CATStdCont", None) + _nested_store_block(
            b"CATBRepModeContainer", _geometry_store("geometry")
        )
    if variant == "geometry-stdcont-precedence":
        return _nested_store_block(
            b"CATStdCont", _geometry_store("geometry")
        ) + _nested_store_block(b"CATBRepModeContainer", _geometry_store("geometry"))
    if variant == "geometry-othercontainer-composite":
        return _nested_store_block(
            b"CATBRepModeContainer",
            _geometry_store("geometry-composite-index-space"),
        )
    if variant == "geometry-othercontainer-bad-tail":
        return _nested_store_block(
            b"CATBRepModeContainer",
            _geometry_store("geometry-overshoot-bad-tail"),
        )
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

    if variant in COMPOSITE_VARIANTS:
        # Composite-store payload (G6 stage 2c #34): the store bytes are
        # a pure function of the variant; the same nesting as the
        # geometry fixtures.
        return build_catpart(
            header_dword=0x0000_0100,
            payload=_composite_payload(variant),
            pad_before_table=0x600 + (seed % 8) * 8,
            identity_name2=document_name,
        )

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
