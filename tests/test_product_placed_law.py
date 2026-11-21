"""The S7 `placed` refinement of the name-table binding law (Fase 3, L4).

The name table carries no instance order, so no ordinal binding is sound.
The law stays fail-closed (`#R == 0` -> identity, anything else ->
`undecodable`) with one refinement from the S7 binding investigation
(`subagents/s7-vela-8d81-binding/informe.md`): when `#R == #own(D)` and every
record's raw matrix body is byte-identical, the record-to-child permutation
is free — the subset question disappears — so the one matrix places every own
child (order-independent, no ordinal law).

`own(D)` needs the document set, so the refinement fires only in the tree
walker (`resolve_owned_assembly`); a single-document read cannot know which
names a listed sub-product covers and keeps the strict path. These tests
mirror the Rust tests in `port/src/product/{binding,ownership}.rs`.
"""

from __future__ import annotations
import struct
from pathlib import Path

import pytest

from catpart.fixtures_assembly import (
    POSITION_EXPLICIT_HEADER,
    POSITION_IDENTITY_HEADER,
    build_catfile,
    encode_short_item,
    encode_structure_pool_record,
    read_product_structure,
    resolve_owned_assembly,
)
from tests.test_product_name_table import (
    NAME_TABLE_HEAD,
    NAME_TABLE_SCHEMA_HEAD,
    build_name_table_product,
)

SNAP = Path(
    "/home/alan/Downloads/submarine-ssk-tr-1700-s42-ara-san-juan-1.snapshot.20/"
    "Submarine-Tr-1700-S42-Catia"
)


def _position_entry(translation: tuple[float, float, float]) -> bytes:
    stream = bytearray([0xE7, 0xE8, 0xE8, 0xE8, 0xE7, 0xE8, 0xE8, 0xE8, 0xE7])
    for value in translation:
        stream.append(0xE6)
        stream.extend(struct.pack("<d", value))
    return POSITION_EXPLICIT_HEADER + b"\x8d\x81" + bytes(stream) + b"\xfe"


def _identity_frame_entry() -> bytes:
    stream = bytes([
        0xE7, 0xE8, 0xE8, 0xE8,
        0xE7, 0xE8, 0xE8, 0xE8,
        0xE7, 0xE8, 0xE8, 0xE8,
    ])
    return POSITION_IDENTITY_HEADER + b"\x8d\x81" + stream + b"\xfe"


def build_name_table_product_with_entries(
    name: str,
    names: tuple[str, ...] | list[str],
    entries: bytes,
) -> bytes:
    """A V5R26-shaped product whose position layer is `entries` verbatim."""
    items = bytearray()
    for text in NAME_TABLE_HEAD:
        items += encode_short_item(text)
    items += encode_short_item(name)
    for text in NAME_TABLE_SCHEMA_HEAD:
        items += encode_short_item(text)
    for text in names:
        items += encode_short_item(text)
    items += encode_short_item("IsRoot")

    payload = encode_structure_pool_record(bytes(items)) + entries
    return build_catfile(payload=payload, identity_name2=name)


# --- (a) #R == #own(D) with byte-identical matrices -> placed -----------------


def test_placed_law_places_every_own_child_in_the_tree_walk() -> None:
    documents = {
        "Root": build_name_table_product(
            "Root", ("Widget", "Sub", "Leaf", "Own", "Bolt")
        ),
        "Sub": build_name_table_product("Sub", ("Leaf", "Own"), position_records=2),
    }

    tree = resolve_owned_assembly("Root", documents)

    rows = {row["instance_name"]: row for row in tree["instances"]}
    # The parent has no records: identity. The child carries #R == #own(D) == 2
    # byte-identical matrices: every own child places with the one matrix.
    assert rows["Widget"]["placement_status"] == "identity"
    assert rows["Sub"]["placement_status"] == "identity"
    assert rows["Leaf"]["placement_status"] == "placed"
    assert rows["Own"]["placement_status"] == "placed"
    assert rows["Leaf"]["transform"] == [12.5, 0.0, 14.4, 1.0, 0.0, 0.0, 0.0]
    assert rows["Own"]["transform"] == [12.5, 0.0, 14.4, 1.0, 0.0, 0.0, 0.0]
    assert rows["Leaf"]["has_position_attr"] is True
    assert rows["Leaf"]["object_tag"] is None
    assert "placed law" in rows["Leaf"]["classification_detail"]
    assert tree["placed_instances"] == 2
    assert tree["identity_instances"] == 3
    assert tree["undecodable_instances"] == 0


def test_placed_law_fires_for_a_standalone_document_in_the_walk() -> None:
    # No listed name resolves to a product document, so own(D) == names(D) and
    # #R == names is the law's fire condition.
    data = build_name_table_product(
        "Solo", ("Widget", "Bracket", "Nut"), position_records=3
    )

    tree = resolve_owned_assembly("Solo", {"Solo": data})

    assert tree["total_instances"] == 3
    assert tree["placed_instances"] == 3
    assert tree["undecodable_instances"] == 0
    for row in tree["instances"]:
        assert row["placement_status"] == "placed"
        assert row["transform"] == [12.5, 0.0, 14.4, 1.0, 0.0, 0.0, 0.0]


def test_single_document_read_stays_fail_closed() -> None:
    # The same bytes through the single-document API: own(D) needs the
    # document set, so the refinement cannot fire there and any record count
    # stays undecodable (never identity — anti-masking).
    data = build_name_table_product(
        "Solo", ("Widget", "Bracket", "Nut"), position_records=3
    )

    doc = read_product_structure(data)

    assert doc["total_instances"] == 3
    assert doc["placed_instances"] == 0
    assert doc["undecodable_instances"] == 3
    for inst in doc["instances"]:
        assert inst["placement_status"] == "undecodable"
        assert inst["transform"] is None
    assert any(w["class"] == "position-binding-open-v5r26" for w in doc["warnings"])


# --- (b) #R == #own(D) with differing matrices -> undecodable -----------------


def test_placed_law_never_fires_on_differing_matrices() -> None:
    # Same count, different bodies: the permutation is not free, the subset is
    # unresolvable -> fail closed (anti-masking: transform stays None).
    data = build_name_table_product_with_entries(
        "Mixed",
        ("Widget", "Bracket"),
        _position_entry((12.5, 0.0, 14.4)) + _position_entry((1.0, 2.0, 3.0)),
    )

    tree = resolve_owned_assembly("Mixed", {"Mixed": data})

    assert tree["total_instances"] == 2
    assert tree["placed_instances"] == 0
    assert tree["undecodable_instances"] == 2
    for row in tree["instances"]:
        assert row["placement_status"] == "undecodable"
        assert row["transform"] is None

    # The single-document read refuses the same way.
    doc = read_product_structure(data)
    assert doc["undecodable_instances"] == 2


def test_placed_law_never_fires_with_an_identity_frame() -> None:
    # An identity frame is a constraint/connector placeholder (Clause 3): a
    # record set containing one never places, even at matching counts.
    data = build_name_table_product_with_entries(
        "Frames",
        ("Widget", "Bracket"),
        _position_entry((12.5, 0.0, 14.4)) + _identity_frame_entry(),
    )

    tree = resolve_owned_assembly("Frames", {"Frames": data})

    assert tree["placed_instances"] == 0
    assert tree["undecodable_instances"] == 2
    for row in tree["instances"]:
        assert row["transform"] is None


# --- (c) #R != #own(D) (vela: 5 != 18) -> undecodable -------------------------


def test_vela_shape_count_mismatch_stays_undecodable() -> None:
    # Vela regression: 18 own children, 5 byte-identical records — the count
    # law fails, the subset (which 5 of 18) has no key in the bytes.
    names = tuple(f"Part{i}" for i in range(18))
    data = build_name_table_product("VelaShape", names, position_records=5)

    tree = resolve_owned_assembly("VelaShape", {"VelaShape": data})

    assert tree["total_instances"] == 18
    assert tree["placed_instances"] == 0
    assert tree["undecodable_instances"] == 18
    for row in tree["instances"]:
        assert row["placement_status"] == "undecodable"
        assert row["transform"] is None


@pytest.mark.skipif(not SNAP.exists(), reason="snapshot not present")
def test_vela_real_file_fails_closed_and_tree_places_the_children() -> None:
    vela = SNAP / "VM-vela-Mast.CATProduct"
    tube = SNAP / "VM-Tube-exhaust-gas.CATProduct"
    snork = SNAP / "VM-varios-snork-System.CATProduct"
    if not (vela.exists() and tube.exists() and snork.exists()):
        pytest.skip("vela tree documents not present")

    # Single-document read: 44 names, every one undecodable (5 != 18).
    doc = read_product_structure(vela.read_bytes())
    assert doc["total_instances"] == 44
    assert doc["placed_instances"] == 0
    assert doc["undecodable_instances"] == 44
    assert any(w["class"] == "position-binding-open-v5r26" for w in doc["warnings"])

    # Tree walk: the root's 18 own children stay undecodable, but the child
    # documents with #R == #own(D) byte-identical place their children (2 + 3,
    # the STP-verified non-identity nodes).
    documents = {p.stem: p.read_bytes() for p in SNAP.glob("*.CATProduct")}
    tree = resolve_owned_assembly("VM-vela-Mast", documents)

    assert tree["total_instances"] == 45
    assert tree["placed_instances"] == 5
    assert tree["identity_instances"] == 22
    assert tree["undecodable_instances"] == 18

    placed = {
        row["instance_name"]: row
        for row in tree["instances"]
        if row["placement_status"] == "placed"
    }
    assert set(placed) == {
        "VM-exhaust-gas-YL",
        "VM-exhaust-gas-YR",
        "VM-compart-YL",
        "VM-compart-YR",
        "VM-varios-221G",
    }
    for row in placed.values():
        assert row["transform"][:3] == pytest.approx(
            [-1.17e-10, -2.241189628468, 2179.45706044845], abs=1e-9
        )
        assert row["transform"][3:] == pytest.approx([1.0, 0.0, 0.0, 0.0], abs=1e-9)
