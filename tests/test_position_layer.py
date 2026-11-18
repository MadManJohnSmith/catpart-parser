"""The `_Position` 8d81 value layer and its counted binding law.

These tests pin the byte-level segmentation used to prefer the `_Position`
stream over the 129-byte `CATCtorProxyCont` constraint/connector frames:

- explicit header `e8 f4 07 37`
- identity header `e9 f4 07 04 37`
- product-root header `e8 e0 07 37` (excluded)

They mirror the Rust tests in `port/src/product/{transforms,binding}.rs`.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from catpart.fixtures_assembly import (
    POSITION_EXPLICIT_HEADER,
    POSITION_IDENTITY_HEADER,
    POSITION_ROOT_HEADER,
    _bind_legacy_129b,
    _bind_position_layer,
    parse_position_matrix_records,
    read_product_structure,
)

MARKER = b"\x8d\x81"


def _identity_stream() -> bytes:
    return bytes([0xE7, 0xE8, 0xE8, 0xE8, 0xE7, 0xE8, 0xE8, 0xE8, 0xE7, 0xE8, 0xE8, 0xE8])


def _translated_stream(tx: float, ty: float, tz: float) -> bytes:
    out = bytearray([0xE7, 0xE8, 0xE8, 0xE8, 0xE7, 0xE8, 0xE8, 0xE8, 0xE7])
    for value in (tx, ty, tz):
        out.append(0xE6)
        out.extend(struct.pack("<d", value))
    return bytes(out)


def _entry(header: bytes, stream: bytes) -> bytes:
    return header + MARKER + stream + b"\xfe"


def _instance(name: str, has_pos: bool = True) -> dict:
    return {
        "instance_name": name,
        "part_number": name.split(".")[0].split(":")[0],
        "pairing_rule": "triple",
        "has_position_attr": has_pos,
        "placement_status": "placed" if has_pos else "identity",
        "transform": None,
        "object_tag": None,
        "classification_detail": None,
    }


def test_position_headers_classify_and_root_is_excluded():
    data = b"".join([
        _entry(POSITION_ROOT_HEADER, _identity_stream()),
        _entry(POSITION_EXPLICIT_HEADER, _translated_stream(12.5, 0.0, 14.4)),
        _entry(POSITION_IDENTITY_HEADER, _identity_stream()),
    ])

    records = parse_position_matrix_records(data)

    assert [r["kind"] for r in records] == ["explicit", "identity"]
    assert records[0]["translation"] == [12.5, 0.0, 14.4]
    assert records[1]["translation"] == [0.0, 0.0, 0.0]


def test_bind_position_layer_keeps_identity_as_undecodable_placeholder():
    # Coso shape: 6 explicit + 1 identity frame for 7 instances.
    instances = [
        _instance("Part4.1"),
        _instance("Part5.1"),
        _instance("Part5.1.2"),
        _instance("Part7.1"),
        _instance("Part7.2"),
        _instance("Part5.1.1"),
        _instance("Part5.1.1.1"),
    ]
    data = b"".join([
        _entry(POSITION_EXPLICIT_HEADER, _translated_stream(-10.0, 11.0, 2.0)),
        _entry(POSITION_IDENTITY_HEADER, _identity_stream()),
        _entry(POSITION_EXPLICIT_HEADER, _translated_stream(9.0, 11.0, 6.0)),
        _entry(POSITION_EXPLICIT_HEADER, _translated_stream(-9.0, 46.0, 11.0)),
        _entry(POSITION_EXPLICIT_HEADER, _translated_stream(-16.0, -18.0, 2.0)),
        _entry(POSITION_EXPLICIT_HEADER, _translated_stream(-5.0, -6.0, 6.0)),
        _entry(POSITION_EXPLICIT_HEADER, _translated_stream(-1.0, 32.0, 6.0)),
    ])

    mode = _bind_position_layer(instances, parse_position_matrix_records(data))

    assert mode == "position_stream_8d81"
    assert instances[0]["transform"][:3] == [-10.0, 11.0, 2.0]
    # The identity frame keeps ordinal position 1 -> Part5.1, but is never bound.
    assert instances[1]["placement_status"] == "undecodable"
    assert instances[1]["transform"] is None
    # The following explicit record still binds Part5.1.2: the order did not shift.
    assert instances[2]["transform"][:3] == [9.0, 11.0, 6.0]
    assert sum(1 for i in instances if i["placement_status"] == "placed") == 6


def test_bind_position_layer_root_ref_stays_undecodable():
    # Servo shape: ac2:1, ac1:1, main:1; 3 explicit + 1 identity.
    instances = [_instance("ac2:1"), _instance("ac1:1"), _instance("main:1")]
    data = b"".join([
        _entry(POSITION_EXPLICIT_HEADER, _translated_stream(0.0, 0.0, -22.9)),
        _entry(POSITION_EXPLICIT_HEADER, _translated_stream(43.2, 51.3, 0.0)),
        _entry(POSITION_EXPLICIT_HEADER, _translated_stream(43.2, 51.3, -1.7)),
        _entry(POSITION_IDENTITY_HEADER, _identity_stream()),
    ])

    mode = _bind_position_layer(instances, parse_position_matrix_records(data))

    assert mode == "position_stream_8d81"
    assert instances[0]["transform"][:3] == [0.0, 0.0, -22.9]
    assert instances[1]["transform"][:3] == [43.2, 51.3, 0.0]
    assert instances[2]["placement_status"] == "undecodable"
    assert instances[2]["transform"] is None
    assert "positional precedence" in instances[2]["classification_detail"]
    assert "43.200" in instances[2]["classification_detail"]


CORPUS = Path(__file__).resolve().parents[1] / "corpus"
COSO = CORPUS / "Apoloo13/ASE_III/diseño_3d/prueba_tensor_cable/coso.CATProduct"
SERVO = (
    CORPUS
    / "Apoloo13/ASE_III/diseño_3d/lengua/lengua_v2/servo_STS3215_03a v1.CATProduct"
)


@pytest.mark.skipif(not COSO.exists(), reason="corpus not present")
def test_corpus_coso_binds_position_stream_with_identity_placeholder():
    doc = read_product_structure(COSO.read_bytes())

    assert doc["total_instances"] == 7
    assert doc["placed_instances"] == 6
    assert doc["undecodable_instances"] == 1
    assert doc["instances"][1]["instance_name"] == "Part5.1"
    assert doc["instances"][1]["placement_status"] == "undecodable"
    assert doc["instances"][1]["transform"] is None
    assert any(w["class"] == "position-stream-8d81" for w in doc["warnings"])


@pytest.mark.skipif(not SERVO.exists(), reason="corpus not present")
def test_corpus_servo_binds_position_stream_with_root_precedence():
    doc = read_product_structure(SERVO.read_bytes())

    assert doc["total_instances"] == 3
    assert doc["placed_instances"] == 2
    assert doc["undecodable_instances"] == 1
    assert doc["instances"][2]["instance_name"] == "main:1"
    assert doc["instances"][2]["placement_status"] == "undecodable"
    assert doc["instances"][2]["transform"] is None
    assert "positional precedence" in doc["instances"][2]["classification_detail"]


def test_legacy_129b_count_mismatch_never_masks_to_identity():
    # Mesh shape: 3 positioned instances, 5 records. Strict path fails closed.
    instances = [_instance("A.1"), _instance("B.1"), _instance("C.1")]
    records = [
        {"object_id": i, "translation": [float(i), 0.0, 0.0], "quaternion": [1.0, 0.0, 0.0, 0.0]}
        for i in range(5)
    ]

    mode = _bind_legacy_129b(instances, records, pool_has_position=True)

    assert mode == "undecodable"
    for inst in instances:
        assert inst["placement_status"] == "undecodable"
        assert inst["transform"] is None
