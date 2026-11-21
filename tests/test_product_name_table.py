"""V5R26 name-table pools and `own(D)` attribution (ticket #68).

The snapshot generation writes a structure pool whose body is an interned
*name table*: one `_InstanceName` as vocabulary, no per-instance markers. The
parser passes therefore extract nothing, and the name-table branch fills the
gap under a tight gate:

    framed ∧ no `CATMechProdCont` ∧ `PRDBAGREP` + `3DIC` ∧ len(instances) == 0

Placement is fail-closed: zero `_Position` records means identity; any record
means undecodable (the table order is not an instance order, so no ordinal
binding is sound). Ownership (`own(D) = names(D) − ⋃ names(P)`) belongs to the
walker and subtracts only what a listed child product accounts for.

These fixtures are synthetic, built with the same byte primitives as the
canonical assembly fixtures (`tests/conftest.py` style).
"""

from __future__ import annotations

import struct

from catpart.fixtures_assembly import (
    IDENTITY_TRANSFORM,
    POSITION_EXPLICIT_HEADER,
    build_catfile,
    classify_assembly,
    encode_short_item,
    encode_structure_pool_record,
    own_instance_names,
    read_product_name_table,
    read_product_structure,
    resolve_owned_assembly,
    scan_structure_pool,
)

# The V5R26 head seen in 199/199 snapshot products: schema items, the product
# name as the `_PartNumber` value, the bag schema, and one `_InstanceName`
# declaration. Names follow it.
NAME_TABLE_HEAD = (
    "CATCatalogManager",
    "catalogManager",
    "catalogLinks",
    "",
    "ASMPRODUCT",
    "ASMProduct",
    "_ViewsList",
    "_Connectors",
    "_RepresentedBy",
    "_Component",
    "_PartNumber",
)
NAME_TABLE_SCHEMA_HEAD = (
    "_BagRepsList",
    "_PrdVersion",
    "_PubConnectors",
    "_AttrForLiterals",
    "_RefProduct",
    "_Disciplines",
    "PRDBAGREP",
    "3DIC",
    "_Reps",
    "_InstanceName",
)


def _identity_stream() -> bytes:
    return bytes([
        0xE7, 0xE8, 0xE8, 0xE8,
        0xE7, 0xE8, 0xE8, 0xE8,
        0xE7, 0xE8, 0xE8, 0xE8,
    ])


def _translated_stream(tx: float, ty: float, tz: float) -> bytes:
    out = bytearray(_identity_stream()[:9])
    for value in (tx, ty, tz):
        out.append(0xE6)
        out.extend(struct.pack("<d", value))
    return bytes(out)


def _position_entry(tx: float = 12.5, ty: float = 0.0, tz: float = 14.4) -> bytes:
    return (
        POSITION_EXPLICIT_HEADER
        + b"\x8d\x81"
        + _translated_stream(tx, ty, tz)
        + b"\xfe"
    )


def build_name_table_product(
    name: str,
    names: tuple[str, ...] | list[str],
    *,
    head_extra: tuple[str, ...] = (),
    bag_schema: bool = True,
    position_records: int = 0,
) -> bytes:
    """One synthetic V5R26-shaped `.CATProduct` carrying a name table."""
    items = bytearray()
    for text in NAME_TABLE_HEAD:
        items += encode_short_item(text)
    items += encode_short_item(name)
    for text in head_extra:
        items += encode_short_item(text)
    for text in NAME_TABLE_SCHEMA_HEAD:
        if not bag_schema and text in ("PRDBAGREP", "3DIC"):
            continue
        items += encode_short_item(text)
    for text in names:
        items += encode_short_item(text)
    items += encode_short_item("IsRoot")

    payload = encode_structure_pool_record(bytes(items))
    payload += _position_entry() * position_records
    return build_catfile(payload=payload, identity_name2=name)


# --- Enumeration --------------------------------------------------------------


def test_name_table_enumerates_names_in_table_order_as_identity() -> None:
    names = ("Widget", "Bracket", "Nut")
    data = build_name_table_product("TableAssembly", names)

    doc = read_product_structure(data)

    assert doc["pool_form"] == "framed"
    assert doc["total_instances"] == 3
    assert doc["placed_instances"] == 0
    assert doc["identity_instances"] == 3
    assert doc["undecodable_instances"] == 0
    # The table order is preserved exactly: A1/A3 arrive alphabetized while
    # B4/B2 keep the logical order, so the parser must never sort or reorder.
    assert [inst["instance_name"] for inst in doc["instances"]] == list(names)
    for inst in doc["instances"]:
        assert inst["part_number"] == inst["instance_name"]
        assert inst["pairing_rule"] == "name_table"
        assert inst["has_position_attr"] is False
        assert inst["placement_status"] == "identity"
        assert inst["transform"] == IDENTITY_TRANSFORM
        assert inst["object_tag"] is None

    assert any(w["class"] == "name-table-v5r26" for w in doc["warnings"])
    assert not any(
        w["class"] == "position-binding-open-v5r26" for w in doc["warnings"]
    )

    classifications = classify_assembly(
        doc,
        {"Widget.CATPart": b"", "Bracket.CATPart": b"", "Nut.CATPart": b""},
    )
    assert classifications == {
        "Widget": "identity",
        "Bracket": "identity",
        "Nut": "identity",
    }


def test_name_table_preserves_alphabetized_order() -> None:
    # Measured A1/A3 shape: the pool is alphabetized, the document order is not.
    names = ("aardvark", "mike", "zulu")
    doc = read_product_structure(build_name_table_product("A1", names))

    assert [inst["instance_name"] for inst in doc["instances"]] == list(names)


def test_name_table_position_records_stay_undecodable() -> None:
    data = build_name_table_product(
        "PositionedTable", ("Widget", "Bracket"), position_records=2
    )

    doc = read_product_structure(data)

    assert doc["total_instances"] == 2
    assert doc["placed_instances"] == 0
    assert doc["identity_instances"] == 0
    assert doc["undecodable_instances"] == 2
    for inst in doc["instances"]:
        # Anti-masking: a document with position records never lands identity.
        assert inst["has_position_attr"] is True
        assert inst["placement_status"] == "undecodable"
        assert inst["transform"] is None
    assert any(
        w["class"] == "position-binding-open-v5r26" for w in doc["warnings"]
    )

    # Resolution does not mask the placement refusal.
    classifications = classify_assembly(
        doc, {"Widget.CATPart": b"", "Bracket.CATPart": b""}
    )
    assert classifications == {"Widget": "undecodable", "Bracket": "undecodable"}


# --- Gate negatives -----------------------------------------------------------


def test_gate_rejects_pools_with_catmechprodcont() -> None:
    data = build_name_table_product(
        "MechProduct", ("Widget", "Bracket"), head_extra=("CATMechProdCont",)
    )

    doc = read_product_structure(data)

    assert doc["total_instances"] == 0
    assert not any(w["class"] == "name-table-v5r26" for w in doc["warnings"])
    assert not any(
        w["class"] == "position-binding-open-v5r26" for w in doc["warnings"]
    )


def test_gate_rejects_pools_without_bag_schema() -> None:
    data = build_name_table_product(
        "NoBag", ("Widget", "Bracket"), bag_schema=False
    )

    doc = read_product_structure(data)

    assert doc["total_instances"] == 0
    assert not any(w["class"] == "name-table-v5r26" for w in doc["warnings"])


def test_gate_requires_zero_instances_from_the_passes() -> None:
    # A marker triple in the body: the existing pairing law wins and the
    # name-table branch never runs (the law is additive).
    names = ("Base", "_InstanceName", "Base.1", "Other")
    doc = read_product_structure(build_name_table_product("Mixed", names))

    assert doc["total_instances"] == 1
    assert doc["instances"][0]["instance_name"] == "Base.1"
    assert doc["instances"][0]["part_number"] == "Base"
    assert doc["instances"][0]["pairing_rule"] == "triple"
    assert not any(w["class"] == "name-table-v5r26" for w in doc["warnings"])


def test_read_product_name_table_signature() -> None:
    data = build_name_table_product("TableAssembly", ("Widget", "Bracket"))
    pool = scan_structure_pool(data)
    assert pool is not None

    table = read_product_name_table(pool[2])

    assert table is not None
    assert table["self_name"] == "TableAssembly"
    assert table["names"] == ["Widget", "Bracket"]


# --- Ownership ----------------------------------------------------------------


def test_own_instance_names_subtracts_only_listed_products() -> None:
    names = ["Widget", "Sub", "Bolt", "Sub-leaf", "Sub-own"]
    child_tables = {"Sub": ["Sub-leaf", "Sub-own", "Grandchild"]}

    assert own_instance_names(names, child_tables) == ["Widget", "Sub", "Bolt"]
    # A name with no product document stays own, and order is preserved.
    assert own_instance_names(names, {}) == names


def test_resolve_owned_assembly_attributes_children_to_their_document() -> None:
    documents = {
        "Root.CATProduct": build_name_table_product(
            "Root", ("Widget", "Sub", "Sub-leaf", "Sub-own", "Bolt")
        ),
        "Sub.CATProduct": build_name_table_product(
            "Sub", ("Sub-leaf", "Sub-own")
        ),
    }

    tree = resolve_owned_assembly("Root", documents)

    assert tree["root"] == "Root"
    assert tree["total_instances"] == 5
    rows = tree["instances"]
    # Depth-first pre-order: a child product's own rows follow the row that
    # listed it, before the parent resumes.
    assert [row["instance_name"] for row in rows] == [
        "Widget",
        "Sub",
        "Sub-leaf",
        "Sub-own",
        "Bolt",
    ]
    assert [row["depth"] for row in rows] == [0, 0, 1, 1, 0]
    assert [row["parent_index"] for row in rows] == [None, None, 1, 1, None]
    assert rows[1]["child_product"] == "Sub"
    assert rows[0]["child_product"] is None
    # Root carries no records; the child product carries none either.
    assert tree["identity_instances"] == 5
    assert tree["undecodable_instances"] == 0
    for row in rows:
        assert row["pairing_rule"] == "name_table"
        assert row["placement_status"] == "identity"


def test_resolve_owned_assembly_composes_child_undecodable_status() -> None:
    documents = {
        "Root": build_name_table_product("Root", ("Widget", "Sub")),
        "Sub": build_name_table_product(
            "Sub", ("Sub-leaf", "Sub-own"), position_records=1
        ),
    }

    tree = resolve_owned_assembly("Root", documents)

    rows = {row["instance_name"]: row for row in tree["instances"]}
    assert set(rows) == {"Widget", "Sub", "Sub-leaf", "Sub-own"}
    # The root's own children are identity; the child document's rows inherit
    # its own fail-closed placement, never the parent's.
    assert rows["Widget"]["placement_status"] == "identity"
    assert rows["Sub"]["placement_status"] == "identity"
    assert rows["Sub-leaf"]["placement_status"] == "undecodable"
    assert rows["Sub-own"]["placement_status"] == "undecodable"
    assert rows["Sub-leaf"]["depth"] == 1
    assert tree["identity_instances"] == 2
    assert tree["undecodable_instances"] == 2


def test_resolve_owned_assembly_never_invents_instances() -> None:
    # `Ghost` is listed but has no document: it stays own (never subtracted,
    # never descended).
    documents = {"Root": build_name_table_product("Root", ("Widget", "Ghost"))}

    tree = resolve_owned_assembly("Root", documents)

    assert [row["instance_name"] for row in tree["instances"]] == [
        "Widget",
        "Ghost",
    ]
    assert tree["instances"][1]["child_product"] is None
