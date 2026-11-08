"""Container-name table record parsing (schema v1).

Evidence: docs/evidence/2026-11-07-container-table-and-trailer.md ("B1").
The Phase 1 open question ("name + offsets? bounds?") resolved to a
fixed-layout record, one per container row, located by the anchor dword
``02 00 81 20`` (little-endian ``0x20810002``) at record offset S+32;
every one of the 19300 records on 1810 corpus files parsed under the
model with zero rejected anchor positions. Record layout (all
multi-byte fields **little-endian**, from S):

- S+0  f1  stream-position value; join key with the (unparsed) directory
  table (law D1).
- S+4  f2  per-record weight: 11 (9455 recs), 12 (4930), 13 (3070),
  21 (1198, the AppliCont row), then rarer values.
- S+8  f3  table id: ``0x00030001`` (17488 recs), ``0x00040001`` (1441
  rows, 1198 of them the AppliCont row), ``0x00050001`` (371) — exactly
  three values corpus-wide (law T3).
- S+12 idx 1-based index within the table id (skips observed).
- S+16 f5  constant ``0x006c0001``; S+20 f6 constant 2; S+28 f8
  constant 0; S+32 f9 constant ``0x20810002`` (the anchor).
- S+24 f7  small value (0/1/8/2/9/... observed; semantics unproven, not
  reported).
- S+36 f10 names-area 8-byte slots + 1.
- S+40 names: ``name1 00 name2 00``, printable ASCII, zero-padded so
  the names area is a multiple of 8 bytes (law T1:
  ``f10 == ceil((len(name1)+len(name2)+2)/8) + 1``, 19300/19300; padding
  bytes verified zero).
- then  8 bytes tail constant ``03 00 f7 00 03 00 00 00``.
- then 16 bytes GUID (per-record object id).

Record size = ``64 + 8*ceil((len(name1)+len(name2)+2)/8)`` (law T2);
satellite blobs (tags ``04 00 c0 20`` / ``04 00 fc 3f``, e.g. the
``V5USERID`` row) and other gaps sit between records on 382 files and
are skipped by the anchor scan.

The scan mirrors the evidence procedure exactly: anchor positions from
byte 32 through the first 2 MB of the file (the validated window of the
B1 decode), each candidate fully validated against the model before it
is reported; a position failing any element is skipped. The directory
table (laws D1-D3) is documented but deliberately unparsed — no L1
output field needs it.

The kind law (docs/evidence/2026-11-07-container-kind-law.md): a table
naming ``CATPrtCont`` belongs to a part (1436/1436 with-table parts),
one naming ``CATProdCont``/``CATMechProdCont`` without ``CATPrtCont``
to a product (374/374 with-table products); with no table the kind is
unknown (8 corpus files).
"""

from __future__ import annotations

import dataclasses

#: Evidence-validated scan window (B1: "the table scan reads only the
#: first 2 MB of each file").
SCAN_WINDOW = 2 * 1024 * 1024

ANCHOR = 0x20810002  # f9, bytes 02 00 81 20 little-endian
F5_CONST = 0x006C0001
TABLE_IDS = (0x00030001, 0x00040001, 0x00050001)
RECORD_TAIL = b"\x03\x00\xf7\x00\x03\x00\x00\x00"

#: Kind-law container names (docs/evidence/2026-11-07-container-kind-law.md).
PART_CONTAINER = "CATPrtCont"
PRODUCT_CONTAINERS = ("CATProdCont", "CATMechProdCont")

KIND_PART = "part"
KIND_PRODUCT = "product"
KIND_UNKNOWN = "unknown"


def _ceil8(n: int) -> int:
    return ((n + 7) // 8) * 8


@dataclasses.dataclass(frozen=True)
class ContainerRecord:
    """One validated container-name table record (B1 layout).

    Field names follow the JSON contract; the evidence-note names are
    ``stream_id``=f1, ``weight``=f2, ``table_id``=f3, ``index``=idx.
    """

    name: str
    parent_name: str
    table_id: int
    index: int
    stream_id: int
    weight: int
    guid: str

    def to_json(self) -> dict:
        return {
            "name": self.name,
            "parent_name": self.parent_name,
            "table_id": self.table_id,
            "index": self.index,
            "stream_id": self.stream_id,
            "weight": self.weight,
            "guid": self.guid,
        }


def _parse_record(buf: bytes, s: int) -> tuple[ContainerRecord, int] | None:
    """Parse and validate one container-name record at offset ``s``.

    Returns ``(record, end_offset)`` — the end offset is where law T2
    places the next record — or ``None`` when any layout element of the
    model is violated (bounds, T3 constants, f3 table id, names, T1
    padding/tail): the anchor position is then simply not a record.
    """
    if s < 0 or s + 40 > len(buf):
        return None
    f1 = int.from_bytes(buf[s : s + 4], "little")
    f2 = int.from_bytes(buf[s + 4 : s + 8], "little")
    f3 = int.from_bytes(buf[s + 8 : s + 12], "little")
    idx = int.from_bytes(buf[s + 12 : s + 16], "little")
    f5 = int.from_bytes(buf[s + 16 : s + 20], "little")
    f6 = int.from_bytes(buf[s + 20 : s + 24], "little")
    f8 = int.from_bytes(buf[s + 28 : s + 32], "little")
    f9 = int.from_bytes(buf[s + 32 : s + 36], "little")
    f10 = int.from_bytes(buf[s + 36 : s + 40], "little")
    if not (f5 == F5_CONST and f6 == 2 and f8 == 0 and f9 == ANCHOR):
        return None
    if f3 not in TABLE_IDS:
        return None
    # names: two printable ASCII NUL-terminated strings starting at S+40
    p = s + 40
    n1 = buf.find(b"\x00", p)
    if n1 < 0 or n1 == p:
        return None
    n2 = buf.find(b"\x00", n1 + 1)
    if n2 < 0 or n2 == n1 + 1:
        return None
    if n2 - p > 256:
        return None
    try:
        name1 = buf[p:n1].decode("ascii")
        name2 = buf[n1 + 1 : n2].decode("ascii")
    except UnicodeDecodeError:
        return None
    if not (name1.isprintable() and name2.isprintable()):
        return None
    total = (n2 + 1) - p
    area = _ceil8(total)
    end_names = p + area
    if end_names + 8 + 16 > len(buf):
        return None
    if any(buf[n2 + 1 : end_names]):
        return None  # law T1: padding bytes verified zero
    if buf[end_names : end_names + 8] != RECORD_TAIL:
        return None
    if f10 != area // 8 + 1:
        return None  # law T1
    guid = bytes(buf[end_names + 8 : end_names + 24])
    return (
        ContainerRecord(
            name=name1,
            parent_name=name2,
            table_id=f3,
            index=idx,
            stream_id=f1,
            weight=f2,
            guid=guid.hex(),
        ),
        end_names + 24,
    )


_ANCHOR_BYTES = ANCHOR.to_bytes(4, "little")


def parse_container_table(data) -> list[ContainerRecord]:
    """Return the validated table records of ``data``, in file order.

    ``data`` is any bytes-like buffer supporting slicing and ``find()``
    (``bytes`` or a read-only :class:`mmap.mmap`); the scan covers the
    evidence-validated first :data:`SCAN_WINDOW` bytes, starting after
    the 32-byte header. Anchor positions that fail the record model are
    skipped (0 such positions exist corpus-wide on the 1810 with-table
    files); files without a table yield ``[]`` (8 corpus files).
    """
    buf = bytes(data[:SCAN_WINDOW])
    records: list[ContainerRecord] = []
    pos = buf.find(_ANCHOR_BYTES)
    while pos >= 0:
        if pos < 32:
            # Inside the header no record can start; skip the anchor.
            pos = buf.find(_ANCHOR_BYTES, pos + 1)
            continue
        parsed = _parse_record(buf, pos - 32)
        if parsed is not None:
            record, end = parsed
            records.append(record)
            pos = buf.find(_ANCHOR_BYTES, end)
        else:
            pos = buf.find(_ANCHOR_BYTES, pos + 1)
    return records


def detect_kind(records: list[ContainerRecord]) -> str:
    """Return the file kind from the table records (kind law K1).

    Evidence: docs/evidence/2026-11-07-container-kind-law.md —
    ``CATPrtCont`` among the record names means a part (1436/1436
    with-table corpus parts), ``CATProdCont``/``CATMechProdCont`` without
    ``CATPrtCont`` a product (374/374 with-table products; 2 parts carry
    the mechanical-product container next to ``CATPrtCont``, so the part
    name decides), ``unknown`` with no table (8 corpus files).
    """
    names = {record.name for record in records}
    if PART_CONTAINER in names:
        return KIND_PART
    if any(name in names for name in PRODUCT_CONTAINERS):
        return KIND_PRODUCT
    return KIND_UNKNOWN
