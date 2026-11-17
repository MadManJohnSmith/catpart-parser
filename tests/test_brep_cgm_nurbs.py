"""BR5 unit tests: CGM container identity, object dictionary, NURBS
payload detector (ticket #57).

Every fixture is built from the byte patterns observed in the corpus
(worked examples in docs/evidence/2026-11-17-br5-cgm-nurbs.md); the
negative fixtures carry the detector honesty edges:

- the u32-alias guard (a sequential u32le array must NOT flag as a
  knot array — the corpus's object-id arrays alias as denormal f64s);
- the denormal-band floor (aliasing index arrays in ``(0, 1e-8)``);
- the repeat/distinct edge (a strictly increasing array without knot
  multiplicity must NOT flag);
- the weight threshold (a transform-style ``1.0`` pair is not a
  rational-weight run).
"""

from __future__ import annotations

import struct

import pytest

from catpart.brep import cgm_nurbs


def u32le(*vals: int) -> bytes:
    return b"".join(struct.pack("<I", v) for v in vals)


def f64le(*vals: float) -> bytes:
    return b"".join(struct.pack("<d", v) for v in vals)


def utf16(s: str) -> bytes:
    return b"".join(bytes([ord(c), 0]) for c in s)


def storage_block(name: str) -> bytes:
    """A minimal CATStorageProperty block preamble with a doc-type name."""
    return (
        b"\x34\x12"
        b"CATStorageProperty"
        + b"\x80\x01\x00\x00\x00\x00\x22\x0c\x00\x00\x00\x34\x01\x03\x00"
        + b"\x34\x10CATUnicodeString"
        + b"\xa0\x02\x00\x00\x00\x00\x34"
        + bytes([len(name)])
        + name.encode("ascii")
        + b"\x9f"
    )


def cgm_identity_region(cont_name: str = "Cont_4ab1dbcf_2dac_5f11b2db_42be",
                        release: str = "041803P") -> bytes:
    """The CGMGeom preamble shape of the sampled files: the writer id
    at ``+0x6a (106d)`` (``9f 36 08`` frames it), the UTF-16LE
    CATStorageProperty + Cont_ identity fields, the vendor footer."""
    head = b"\x00" * 103 + b"\x9f\x36\x08"
    body = (
        b"FINJPL  "
        + b"\x00\x00\x00\x92"
        + b"\x00\x00\x00\x13\x00\x00\x00\x02\x00\x00\x00\x36\x00\x00\x00"
        + b"\x15\x00\x02\x00\x00\x00\x28\x00\x03\x00"
        + utf16("CATStorageProperty")
        + b"\x00\x00"
        + b"\x50\x00\x00\x00\x14\x00\x02\x00\x00\x00\x42\x00"
        + utf16(cont_name)
        + b"\x00\x0d\x00\x01\x00\x00\x00\x00"
        + b"\x00" * 120
        + b"\x4e\x11\x00\x00\x00"
        + b"DASSAULT-SYSTEMES"
        + b"\x05\x00\x00\x00CATIA"
        + bytes([len(release)]) + b"\x00\x00\x00"
        + release.encode("ascii")
        + b"\x00" * 16
    )
    return head + body


class TestIdentity:
    def test_identity_decode(self):
        data = cgm_identity_region()
        ident = cgm_nurbs.parse_identity(data, 0, len(data))
        assert ident.ok()
        assert ident.writer_offset == 106
        assert ident.cont_name == "Cont_4ab1dbcf_2dac_5f11b2db_42be"
        assert ident.vendor_offset == data.find(b"DASSAULT-SYSTEMES")
        assert ident.release == "041803P"

    def test_identity_without_footer_release(self):
        # Negative edge for the footer claim: vendor present, release
        # token absent -> the footer element fails, the rest stand.
        data = cgm_identity_region(release="XXXXXXX")
        ident = cgm_nurbs.parse_identity(data, 0, len(data))
        assert ident.vendor_offset >= 0
        assert not ident.ok()
        assert ident.release == ""

    def test_identity_missing_writer(self):
        data = cgm_identity_region().replace(b"FINJPL  ", b"XXXXXXXX")
        ident = cgm_nurbs.parse_identity(data, 0, len(data))
        assert ident.writer_offset == -1
        assert not ident.ok()


class TestDictionary:
    def test_idrun_u32_count(self):
        # R20/R21 form: [marker][x u32][flag][count u32][ids][00 00]
        rec = (
            b"\x02\x00\x04\x00" + u32le(9) + b"\x00" + u32le(5)
            + u32le(3, 4, 5, 6, 7) + b"\x00\x00"
        )
        scan = cgm_nurbs.scan_dictionary(rec, 0, len(rec))
        assert len(scan.runs) == 1
        run = scan.runs[0]
        assert run.marker == 2
        assert run.x == 9
        assert run.flag == 0
        assert run.ids == (3, 4, 5, 6, 7)
        assert scan.objects == 5
        assert run.end == len(rec)

    def test_idrun_u16_count(self):
        # R19 form (byte-verified on 1d4214e5): u16le count, ids at +11.
        rec = (
            b"\x09\x00\x04\x00" + u32le(9) + b"\x00" + b"\x05\x00"
            + u32le(3, 4, 5, 6, 7) + b"\x00\x00"
        )
        scan = cgm_nurbs.scan_dictionary(rec, 0, len(rec))
        assert len(scan.runs) == 1
        assert scan.runs[0].ids == (3, 4, 5, 6, 7)
        assert scan.objects == 5

    def test_idrun_rejects_bad_terminator(self):
        rec = (
            b"\x02\x00\x04\x00" + u32le(9) + b"\x00" + u32le(5)
            + u32le(3, 4, 5, 6, 7) + b"\x01\x00"
        )
        assert cgm_nurbs.scan_dictionary(rec, 0, len(rec)).runs == ()

    def test_idrun_rejects_out_of_range_id(self):
        # A misparse (the corpus's marker-8 mid-list anomaly) yields
        # ids >= 2^28: rejected, not silently decoded.
        rec = (
            b"\x02\x00\x04\x00" + u32le(9) + b"\x00" + u32le(2)
            + u32le(3, 0x18000000) + b"\x00\x00"
        )
        assert cgm_nurbs.scan_dictionary(rec, 0, len(rec)).runs == ()

    def test_offset_markers_counted(self):
        rec = (
            b"\x01\x00\x04\x00" + u32le(2) + b"\x00\x00\x02\x00"
            + u32le(8) + u32le(0x38) + b"\x00" + b"\xdb\xb2\x11\x5f"
            + b"\xc8\x26"
            + b"\x02\x00\x04\x00" + u32le(9) + b"\x00" + u32le(1)
            + u32le(3) + b"\x00\x00"
        )
        scan = cgm_nurbs.scan_dictionary(rec, 0, len(rec))
        assert scan.offset_markers == 1
        assert scan.objects == 1

    def test_large_run_dental_shape(self):
        # The 17930bab dental mold's big run: count = 106,912
        # sequential ids from 0x1f.
        count = 106_912
        rec = (
            b"\x05\x00\x04\x00" + u32le(0x1d) + b"\x00" + u32le(count)
            + u32le(*range(0x1F, 0x1F + count)) + b"\x00\x00"
        )
        scan = cgm_nurbs.scan_dictionary(rec, 0, len(rec))
        assert len(scan.runs) == 1
        assert scan.objects == count
        assert scan.max_id == 0x1F + count - 1


class TestNurbsSignatures:
    def test_knot_array_detected(self):
        # Cubic B-spline knot vector: multiplicity 4 at both ends.  A
        # negative value before the array breaks the zero-run so the
        # detected span is exactly the knot vector.
        knots = (0.0, 0.0, 0.0, 0.0, 0.25, 0.5, 0.75, 1.0, 1.0, 1.0, 1.0)
        data = f64le(-1.0) + f64le(*knots) + f64le(-1.0)
        sig = cgm_nurbs.nurbs_signatures(data, 0, len(data))
        assert len(sig.knot_runs) == 1
        run = sig.knot_runs[0]
        assert run.offset == 8
        assert run.count == len(knots)
        assert run.distinct == 5
        assert run.repeats == 6
        assert run.lo == 0.0 and run.hi == 1.0

    def test_u32_alias_rejected(self):
        # Sequential u32le values around 0x40401000 alias as
        # non-decreasing normal f64s (~32.5) — the chain guard must
        # reject them (the corpus's object-id arrays).
        vals = [0x40401000 + k for k in range(32)]
        data = u32le(*vals) + b"\x00" * 16
        sig = cgm_nurbs.nurbs_signatures(data, 0, len(data))
        assert sig.knot_runs == ()

    def test_denormal_alias_rejected(self):
        # The corpus's index arrays alias as denormal f64 runs
        # (~1e-310): the (0, 1e-8) band cut rejects them.
        vals = [0x1A1000 + k for k in range(64)]
        data = u32le(*vals)
        sig = cgm_nurbs.nurbs_signatures(data, 0, len(data))
        assert sig.knot_runs == ()

    def test_strictly_increasing_rejected(self):
        # No repeats -> no knot-multiplicity evidence -> rejected.
        data = f64le(0.0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875)
        sig = cgm_nurbs.nurbs_signatures(data, 0, len(data))
        assert sig.knot_runs == ()

    def test_weight_run_detected(self):
        data = b"\x00" * 8 + f64le(1.0, 1.0, 1.0, 1.0) + b"\x00" * 16
        sig = cgm_nurbs.nurbs_signatures(data, 0, len(data))
        assert len(sig.weight_runs) == 1
        assert sig.weight_runs[0][1] == 4

    def test_transform_pair_not_weight_run(self):
        # A transform-style scale pair (two 1.0s) is below the >= 4
        # threshold: no weight signature.
        data = f64le(1.0, 1.0) + b"\x00" * 16
        sig = cgm_nurbs.nurbs_signatures(data, 0, len(data))
        assert sig.weight_runs == ()

    def test_short_run_rejected(self):
        # Seven values is below the >= 8 knot-array floor.
        knots = (0.0, 0.0, 0.0, 0.25, 0.5, 1.0, 1.0)
        data = f64le(*knots)
        sig = cgm_nurbs.nurbs_signatures(data, 0, len(data))
        assert sig.knot_runs == ()

    def test_all_four_byte_phases_scanned(self):
        knots = (0.0, 0.0, 0.0, 0.0, 0.25, 0.5, 0.75, 1.0, 1.0, 1.0, 1.0)
        for phase in (0, 2, 4, 6):
            data = b"\x00" * (16 + phase) + f64le(*knots) + b"\x00" * 16
            sig = cgm_nurbs.nurbs_signatures(data, 0, len(data))
            assert len(sig.knot_runs) == 1, f"phase {phase} missed"

    def test_no_signature_in_dictionary(self):
        # A pure structure region (identity + id-runs) carries no NURBS
        # payload signature — the corpus-wide BR5-03 negative, at unit
        # scale.
        region = cgm_identity_region() + (
            b"\x02\x00\x04\x00" + u32le(9) + b"\x00" + u32le(5)
            + u32le(3, 4, 5, 6, 7) + b"\x00\x00"
        )
        sig = cgm_nurbs.nurbs_signatures(region, 0, len(region))
        assert sig.knot_runs == ()
        assert sig.weight_runs == ()
        assert not sig.present


def _catalog_tail(catalog_len: int) -> bytes:
    """A 64-byte nested-catalog tail satisfying the N6 trailer laws
    (``G == catalog_len`` names the magic+tail window length)."""
    tail = bytearray(64)
    tail[-8:] = b"CB__END\x00"
    # Write the trailer fields directly (slicing a bytearray copies).
    tail[-36 + 8: -36 + 12] = struct.pack(">I", catalog_len)  # C
    tail[-36 + 12: -36 + 16] = struct.pack(">I", catalog_len)  # D
    tail[-36 + 24: -36 + 28] = struct.pack(">I", catalog_len)  # G
    return bytes(tail)


def synthetic_part() -> bytes:
    """A minimal part: CATSeeBodyCont block + a CATStdCont region with
    a valid V5_CFV2 nested-store header + CB0001 catalog."""
    seebody = storage_block("CATSeeBodyCont") + b"\x00" * 64
    d8 = 96  # catalog offset from the store origin
    catalog = b"CATIA_V5 CB0001\x00" + _catalog_tail(16 + 64)
    d12 = len(catalog)
    header = (
        b"V5_CFV2\x00"
        + struct.pack(">I", d8)
        + struct.pack(">I", d12)
        + b"\xff" * 8
        + b"\x00" * 8
    )
    body = b"\x00" * (d8 - len(header))
    stdcont = storage_block("CATStdCont") + header + body + catalog
    filler = b"\x00" * 32
    data = filler + seebody + stdcont + b"\x00" * 16
    # dword8 of the outer header: an end boundary above every block.
    return data[:8] + struct.pack(">I", len(data)) + data[12:]


class TestTop01Carrier:
    def test_carrier_present(self):
        data = synthetic_part()
        carrier = cgm_nurbs.top01_carrier(data)
        assert carrier.seebody_block is True
        assert carrier.store_root == "stdcont"

    def test_carrier_absent(self):
        data = b"\x00" * 128
        carrier = cgm_nurbs.top01_carrier(data)
        assert carrier.seebody_block is False
        assert carrier.store_root is None


class TestValidRegions:
    def test_region_bounds(self):
        data = synthetic_part()
        regs = cgm_nurbs.valid_regions(data)
        names = [nm for _, nm, _ in regs]
        assert names == ["CATSeeBodyCont", "CATStdCont"]
        # The CATSeeBodyCont region ends where CATStdCont starts.
        blocks = {nm: blk for blk, nm, _ in regs}
        assert regs[0][2] == blocks["CATStdCont"]

    def test_cgm_block_found_in_identity_region(self):
        pre = storage_block("CGMGeom")
        data = pre + cgm_identity_region()
        regs = cgm_nurbs.valid_regions(data)
        cgm = [(b, e) for b, nm, e in regs if nm == "CGMGeom"]
        assert len(cgm) == 1
        blk, end = cgm[0]
        ident = cgm_nurbs.parse_identity(data, blk, end)
        assert ident.ok()
        # Writer id at block-relative +106 (105d/106d observed), after
        # the block preamble the fixture prepends.
        assert ident.writer_offset == len(pre) + 106
        assert ident.cont_name == "Cont_4ab1dbcf_2dac_5f11b2db_42be"
        assert ident.region_size == end - blk


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
