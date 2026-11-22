"""The S7 `placed` refinement of the name-table binding law (Fase 3, L4).

The name table carries no instance order, so no ordinal binding is sound.
The law stays fail-closed (`#R == 0` -> identity, anything else ->
`undecodable`) with two refinements, both walker-only (they need the
document set):

* S7 (`subagents/s7-vela-8d81-binding/informe.md`): when `#R == #own(D)` and
  every record's raw matrix body is byte-identical, the record-to-child
  permutation is free — the subset question disappears — so the one matrix
  places every own child (order-independent, no ordinal law).
* W5 law C (2026-11-22): a matrix body byte-identical across two or more
  documents of the walked set is a shared connector frame, never an instance
  placement — the corpus carries the `T = (-0.0, -2.241, 2179.457)` body in
  13 unrelated documents, and the STEP oracle places those documents'
  children at the parent origin (VM-vela-Mast: Z within [-88.7, +31.7] mm,
  where the matrix would put them at Z = +2179.457 mm). Refused records
  never bind; a document whose records are ALL refused (or Clause 3 identity
  frames) carries no instance placements and decodes identity; a document
  mixing refused records with anything else stays fail-closed. This
  corrects the S7-era reading of the vela/bow/flooding/MB81 "placed" rows:
  the 19 rows the pre-W5 walk placed with the shared body are connector
  frames, and the oracle refutes their Z (position error 2179.457 mm).

`own(D)` needs the document set, so the refinements fire only in the tree
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

SNAP_CANDIDATES = (
    Path(
        "/home/alan/Downloads/submarine-ssk-tr-1700-s42-ara-san-juan-1.snapshot.20/"
        "Submarine-Tr-1700-S42-Catia"
    ),
    Path(
        "/tmp/w5/w5-oracle-subset/"
        "submarine-ssk-tr-1700-s42-ara-san-juan-1.snapshot.20/"
        "Submarine-Tr-1700-S42-Catia"
    ),
)
SNAP = next((p for p in SNAP_CANDIDATES if p.exists()), SNAP_CANDIDATES[0])


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


# --- (d) W5 law C: shared connector bodies ------------------------------------


def test_shared_connector_body_refused_across_documents() -> None:
    # One matrix body in two unrelated documents: a shared connector frame.
    # Neither document places; both decode identity with the law-C detail.
    entry = _position_entry((12.5, 0.0, 14.4))
    documents = {
        "Left": build_name_table_product_with_entries(
            "Left", ("Widget",), entry
        ),
        "Right": build_name_table_product_with_entries(
            "Right", ("Bracket",), entry
        ),
    }

    tree = resolve_owned_assembly("Left", documents)

    assert tree["total_instances"] == 1
    assert tree["placed_instances"] == 0
    assert tree["identity_instances"] == 1
    assert tree["undecodable_instances"] == 0
    row = tree["instances"][0]
    assert row["placement_status"] == "identity"
    assert row["transform"] == [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]
    assert row["has_position_attr"] is True
    assert "connector-frame records: all 1" in row["classification_detail"]
    assert "(W5 law C)" in row["classification_detail"]
    assert any(
        w["class"] == "connector-frame-records-v5r26" for w in tree["warnings"]
    )


def test_shared_body_blocks_s7_even_at_matching_count() -> None:
    # #R == #own(D) == 2 with byte-identical matrices would fire S7 — but the
    # same body also sits in an unrelated document, so the records are
    # connector frames and the whole set refuses to identity.
    entry = _position_entry((12.5, 0.0, 14.4))
    documents = {
        "Solo": build_name_table_product_with_entries(
            "Solo", ("Widget", "Bracket"), entry * 2
        ),
        "Elsewhere": build_name_table_product_with_entries(
            "Elsewhere", ("Nut",), entry
        ),
    }

    tree = resolve_owned_assembly("Solo", documents)

    assert tree["placed_instances"] == 0
    assert tree["identity_instances"] == 2
    assert tree["undecodable_instances"] == 0
    for row in tree["instances"]:
        assert row["placement_status"] == "identity"
        assert "connector-frame records: all 2" in row["classification_detail"]


def test_mixed_refusal_stays_fail_closed() -> None:
    # A shared body next to a unique body: the shared record refuses, the
    # unique one cannot be attributed either (S7 needs the whole set
    # identical and count-matched) -> undecodable, never identity.
    documents = {
        "Mixed": build_name_table_product_with_entries(
            "Mixed",
            ("Widget", "Bracket"),
            _position_entry((12.5, 0.0, 14.4)) + _position_entry((9.0, 0.0, 0.0)),
        ),
        "Elsewhere": build_name_table_product_with_entries(
            "Elsewhere", ("Nut",), _position_entry((12.5, 0.0, 14.4))
        ),
    }

    tree = resolve_owned_assembly("Mixed", documents)

    assert tree["placed_instances"] == 0
    assert tree["undecodable_instances"] == 2
    for row in tree["instances"]:
        assert row["placement_status"] == "undecodable"
        assert row["transform"] is None
        assert "connector-frame refusal blocks binding" in (
            row["classification_detail"]
        )


def test_unique_body_keeps_the_s7_placement() -> None:
    # The S7 shape still places when the body appears in exactly one
    # document of the walked set (the swbd nut-bt family at HEAD).
    entry = _position_entry((12.5, 0.0, 14.4))
    documents = {
        "Solo": build_name_table_product_with_entries(
            "Solo", ("Widget", "Bracket"), entry * 2
        ),
        "Elsewhere": build_name_table_product_with_entries(
            "Elsewhere", ("Nut",), _position_entry((1.0, 2.0, 3.0))
        ),
    }

    tree = resolve_owned_assembly("Solo", documents)

    assert tree["placed_instances"] == 2
    for row in tree["instances"]:
        assert row["placement_status"] == "placed"
        assert row["transform"] == [12.5, 0.0, 14.4, 1.0, 0.0, 0.0, 0.0]


def test_single_document_read_stays_strict_under_law_c() -> None:
    # The single-document read has no document set, so law C cannot classify
    # anything there: any record count stays undecodable (never identity).
    data = build_name_table_product(
        "Solo", ("Widget", "Bracket", "Nut"), position_records=3
    )

    doc = read_product_structure(data)

    assert doc["undecodable_instances"] == 3
    for inst in doc["instances"]:
        assert inst["placement_status"] == "undecodable"


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
def test_vela_real_file_fails_closed_and_tree_decodes_identity() -> None:
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

    # Tree walk under W5 law C: the 5 explicit records carry the body that is
    # byte-identical across 13 unrelated documents (the shared connector
    # frame). The whole document refuses to instance placements, and its 18
    # own children plus the subtree decode identity — the STEP-oracle state
    # (all children baked at the parent origin, Z within [-88.7, +31.7] mm).
    documents = {p.stem: p.read_bytes() for p in SNAP.glob("*.CATProduct")}
    tree = resolve_owned_assembly("VM-vela-Mast", documents)

    assert tree["total_instances"] == 45
    assert tree["placed_instances"] == 0
    assert tree["identity_instances"] == 45
    assert tree["undecodable_instances"] == 0
    assert any(
        w["class"] == "connector-frame-records-v5r26" for w in tree["warnings"]
    )
    root_rows = [row for row in tree["instances"] if row["depth"] == 0]
    assert len(root_rows) == 18
    for row in root_rows:
        assert row["placement_status"] == "identity"
        assert "connector-frame records: all 5" in row["classification_detail"]


@pytest.mark.skipif(not SNAP.exists(), reason="snapshot not present")
def test_swbd_nut_family_keeps_the_unique_body_placement() -> None:
    # The 5 swbd nut-bt rows place with a body unique to their document
    # (T = (0.14, 145.91, 0.0) mm): law C does not refuse it, S7 holds.
    documents = {p.stem: p.read_bytes() for p in SNAP.glob("*.CATProduct")}
    if "MD-swbd-panel-0A1w" not in documents:
        pytest.skip("swbd tree documents not present")

    tree = resolve_owned_assembly("MD-swbd-panel-0A1w", documents)

    assert tree["total_instances"] == 43
    assert tree["placed_instances"] == 5
    placed = {
        row["instance_name"]: row
        for row in tree["instances"]
        if row["placement_status"] == "placed"
    }
    assert set(placed) == {
        "MD-nut-bt-17",
        "MD-nut-bt-18",
        "MD-nut-bt-19",
        "MD-nut-bt-20",
        "MD-nut-bt-21",
    }
    for row in placed.values():
        assert row["transform"][:3] == pytest.approx(
            [0.140466423462, 145.90604277158, 0.0], abs=1e-6
        )
