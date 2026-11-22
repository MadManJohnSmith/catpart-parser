#!/usr/bin/env python3
"""P3.0 probe: STEP assembly oracle for the W5 placement ground truth (#W5).

Read-only. Extracts, from an AP203/AP214 `.stp` exported by the same CATIA
snapshot the `.CATProduct` subset came from:

* the root product name (first PRODUCT entity) and its shape representation;
* every NEXT_ASSEMBLY_USAGE_OCCURRENCE: instance name, parent/child
  product-definition ids;
* the per-instance transform, from the CONTEXT_DEPENDENT_SHAPE_REPRESENTATION
  / ITEM_DEFINED_TRANSFORMATION pair that references the occurrence's product
  definition shape: M = A2 * A1^-1 with A1/A2 the two AXIS2_PLACEMENT_3D of
  the transformation, rotation as a 3x3 matrix + translation vector;
* the axis placement of the root SHAPE_REPRESENTATION (the assembly frame).

Output JSON (per file): root, placement frame, and one row per NAUO with
identity flag. This is the W5 oracle input: instance-name -> matrix, used to
score per-instance position error of the binary placement decode.

Modes:
    python3 -I scripts/triage/p30_step_oracle.py --instances FILE.stp OUT.json
    python3 -I scripts/triage/p30_step_oracle.py --selftest
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

_ENT_RE = re.compile(rb"^#(\d+)=\s*([A-Z_0-9]+)\s*\((.*)\)\s*;\s*$", re.S)
_COMPLEX_RE = re.compile(rb"^#(\d+)=\s*\((.*)\)\s*;\s*$", re.S)
_SUBBLOCK_RE = re.compile(rb"([A-Z_0-9]+)\(([^()]*)\)")
_OF_INTEREST = {
    "NEXT_ASSEMBLY_USAGE_OCCURRENCE",
    "CONTEXT_DEPENDENT_SHAPE_REPRESENTATION",
    "ITEM_DEFINED_TRANSFORMATION",
    "AXIS2_PLACEMENT_3D",
    "CARTESIAN_POINT",
    "DIRECTION",
    "PRODUCT_DEFINITION_SHAPE",
    "SHAPE_REPRESENTATION",
    "SHAPE_REPRESENTATION_RELATIONSHIP",
    "REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION",
    "PRODUCT_DEFINITION",
    "PRODUCT_DEFINITION_FORMATION",
    "PRODUCT",
}
# Wide entities can span lines; keep scanning until parens balance.
_MAX_RECORD = 4096


def _split_top(args: bytes) -> list[bytes]:
    """Split STEP parameter list on top-level commas."""
    parts: list[bytes] = []
    depth = 0
    start = 0
    in_str = False
    i = 0
    while i < len(args):
        b = args[i]
        if in_str:
            if b == 0x27:  # '
                if i + 1 < len(args) and args[i + 1] == 0x27:
                    i += 1
                else:
                    in_str = False
        elif b == 0x27:
            in_str = True
        elif b == 0x28:  # (
            depth += 1
        elif b == 0x29:  # )
            depth -= 1
        elif b == 0x2C and depth == 0:  # ,
            parts.append(args[start:i])
            start = i + 1
        i += 1
    parts.append(args[start:])
    return parts


def _ref(arg: bytes) -> int | None:
    """`#123` -> 123, `*`/`$`/anything else -> None."""
    a = arg.strip()
    if a.startswith(b"#"):
        try:
            return int(a[1:])
        except ValueError:
            return None
    return None


def _str(arg: bytes) -> str:
    a = arg.strip()
    if a.startswith(b"'") and a.endswith(b"'"):
        a = a[1:-1]
    return a.replace(b"''", b"'").decode("utf-8", "replace")


def _floats(arg: bytes) -> list[float]:
    return [float(x) for x in _split_top(arg.strip(b"() \t"))]


def parse_step_assembly(path: Path) -> dict:
    """Parse the assembly skeleton of one STEP file (streaming, line-based)."""
    points: dict[int, tuple[float, float, float]] = {}
    directions: dict[int, tuple[float, float, float]] = {}
    placements: dict[int, dict] = {}
    nauos: dict[int, dict] = {}
    idts: dict[int, dict] = {}
    cdsrs: list[dict] = []
    pds: dict[int, int] = {}  # PRODUCT_DEFINITION_SHAPE -> definition ref
    shape_reps: dict[int, dict] = {}
    products: dict[int, str] = {}
    prod_defs: dict[int, int] = {}  # PRODUCT_DEFINITION -> PRODUCT ref
    formations: dict[int, int] = {}  # PRODUCT_DEFINITION_FORMATION -> PRODUCT
    rrw_transform: dict[int, int] = {}  # complex entity -> IDT ref

    buf = b""
    with open(path, "rb") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            if not line.startswith(b"#") and not buf:
                continue  # section keyword or blank, no record pending
            if buf:
                line = buf + b" " + line
                buf = b""
            m = _ENT_RE.match(line)
            cm = None if m else _COMPLEX_RE.match(line)
            if m is None and cm is None:
                # incomplete record: buffer for continuation lines
                if line.count(b"(") > line.count(b")") and len(line) < _MAX_RECORD:
                    buf = line
                continue
            # wide geometry entities never carry assembly structure
            eid = int((m or cm).group(1))
            if m is None:
                for sub_t, sub_a in _SUBBLOCK_RE.findall(cm.group(2)):
                    if sub_t == b"REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION":
                        r = _ref(sub_a)
                        if r is not None:
                            rrw_transform[eid] = r
                continue
            etype = m.group(2).decode()
            if etype not in _OF_INTEREST:
                continue
            args = _split_top(m.group(3))
            if etype == "CARTESIAN_POINT":
                vals = _floats(args[1])
                points[eid] = (vals[0], vals[1], vals[2])
            elif etype == "DIRECTION":
                vals = _floats(args[1])
                n = math.sqrt(sum(v * v for v in vals[:3])) or 1.0
                directions[eid] = (vals[0] / n, vals[1] / n, vals[2] / n)
            elif etype == "AXIS2_PLACEMENT_3D":
                # (name, axis#D3, location#P, ref_direction#D3)
                placements[eid] = {
                    "axis": _ref(args[1]) if len(args) > 1 else None,
                    "loc": _ref(args[2]) if len(args) > 2 else None,
                    "ref": _ref(args[3]) if len(args) > 3 else None,
                }
            elif etype == "NEXT_ASSEMBLY_USAGE_OCCURRENCE":
                # (id, name, descr, parent_pd, child_pd, ref)
                nauos[eid] = {
                    "name": _str(args[1]) if len(args) > 1 else "",
                    "parent": _ref(args[3]) if len(args) > 3 else None,
                    "child": _ref(args[4]) if len(args) > 4 else None,
                }
            elif etype == "ITEM_DEFINED_TRANSFORMATION":
                # (name[, description], transform_item_1, transform_item_2)
                refs = [r for a in args if (r := _ref(a)) is not None]
                idts[eid] = {
                    "name": _str(args[0]),
                    "a1": refs[0] if refs else None,
                    "a2": refs[1] if len(refs) > 1 else None,
                }
            elif etype == "CONTEXT_DEPENDENT_SHAPE_REPRESENTATION":
                # (representation_relation, represented_product_relation)
                cdsrs.append(
                    {"rel": _ref(args[0]), "pds": _ref(args[1])}
                )
            elif etype == "PRODUCT_DEFINITION_SHAPE":
                # (name, descr, definition)
                pds[eid] = _ref(args[2])
            elif etype == "SHAPE_REPRESENTATION":
                shape_reps[eid] = {"name": _str(args[0]), "items": len(args) - 2}
            elif etype == "PRODUCT_DEFINITION":
                # (id, descr, formation, frame_of_reference)
                prod_defs[eid] = formations.get(_ref(args[2]), -1)
            elif etype == "PRODUCT_DEFINITION_FORMATION":
                # (id, descr, product)
                r = _ref(args[2])
                if r is not None:
                    formations[eid] = r
            elif etype == "PRODUCT":
                products[eid] = _str(args[0])

    # placement -> rotation matrix + translation
    for pid, pl in placements.items():
        z = directions.get(pl["axis"], (0.0, 0.0, 1.0))
        x = directions.get(pl["ref"], (1.0, 0.0, 0.0))
        # Gram-Schmidt on (x, z): y = z x x, x' = y x z
        y = (
            z[1] * x[2] - z[2] * x[1],
            z[2] * x[0] - z[0] * x[2],
            z[0] * x[1] - z[1] * x[0],
        )
        xn = (
            y[1] * z[2] - y[2] * z[1],
            y[2] * z[0] - y[0] * z[2],
            y[0] * z[1] - y[1] * z[0],
        )
        pl["rot"] = [list(xn), list(y), list(z)]
        pl["pos"] = points.get(pl["loc"], (0.0, 0.0, 0.0))

    # NAUO -> transform via CDSR chains. CATIA exports the PDS's definition
    # as the NAUO itself (#299 -> #9199); generic AP214 may instead point at
    # the child product definition — both joins are tried.
    nauo_by_child: dict[int, int] = {}
    for eid, n in nauos.items():
        if n["child"] is not None:
            nauo_by_child.setdefault(n["child"], eid)
    inst_transform: dict[int, dict] = {}
    for cdsr in cdsrs:
        rel = cdsr["rel"]
        pds_ref = cdsr["pds"]
        if pds_ref is None or pds_ref not in pds:
            continue
        pd = pds[pds_ref]
        if pd is None:
            continue
        nauo_eid = pd if pd in nauos else nauo_by_child.get(pd)
        if nauo_eid is None:
            continue
        idt = idts.get(rrw_transform.get(rel, rel))
        if idt is None:
            continue
        a1, a2 = placements.get(idt["a1"]), placements.get(idt["a2"])
        if a1 is None or a2 is None or "rot" not in a1 or "rot" not in a2:
            continue
        inst_transform[nauo_eid] = {"a1": a1, "a2": a2}

    instances = []
    for eid, n in nauos.items():
        row = {
            "nauo": eid,
            "name": n["name"],
            "parent_pd": n["parent"],
            "child_pd": n["child"],
            "parent_product": products.get(prod_defs.get(n["parent"], -1), None),
            "child_product": products.get(prod_defs.get(n["child"], -1), None),
        }
        t = inst_transform.get(eid)
        if t is None:
            row["transform"] = None
            row["identity"] = None
        else:
            m = _compose(t["a2"], _inverse(t["a1"]))
            row["transform"] = {
                "rot": m[0],
                "pos": list(m[1]),
            }
            row["identity"] = _is_identity(m[0], m[1])
        instances.append(row)
    return {
        "file": path.name,
        "products": products,
        "instances": instances,
    }


def _inverse(pl: dict) -> tuple[list[list[float]], tuple[float, float, float]]:
    r = pl["rot"]
    t = pl["pos"]
    # rotation matrices are orthonormal: inverse = transpose
    rt = [[r[0][0], r[1][0], r[2][0]], [r[0][1], r[1][1], r[2][1]], [r[0][2], r[1][2], r[2][2]]]
    ti = (
        -(rt[0][0] * t[0] + rt[0][1] * t[1] + rt[0][2] * t[2]),
        -(rt[1][0] * t[0] + rt[1][1] * t[1] + rt[1][2] * t[2]),
        -(rt[2][0] * t[0] + rt[2][1] * t[1] + rt[2][2] * t[2]),
    )
    return rt, ti


def _compose(
    a: dict, b_inv: tuple[list[list[float]], tuple[float, float, float]]
) -> tuple[list[list[float]], tuple[float, float, float]]:
    """A * B^-1."""
    ra, ta = a["rot"], a["pos"]
    rb, tb = b_inv
    r = [
        [sum(ra[i][k] * rb[k][j] for k in range(3)) for j in range(3)]
        for i in range(3)
    ]
    t = tuple(
        sum(ra[i][k] * tb[k] for k in range(3)) + ta[i] for i in range(3)
    )
    return r, t


def _is_identity(r: list[list[float]], t: tuple[float, float, float]) -> bool:
    tol = 1e-9
    for i in range(3):
        for j in range(3):
            if abs(r[i][j] - (1.0 if i == j else 0.0)) > 1e-6:
                return False
    return all(abs(v) <= tol for v in t)


def selftest() -> int:
    """Synthetic STEP: three instances, CATIA placement convention.

    Per AP214 CDSR/RRWT: transform_item_1 is the child document's frame
    (identity here), transform_item_2 the component's slot in assembly
    coordinates. A1 sits at (100,200,300); B1 is rotated 90 degrees about Z
    at (0,5,0); C1 sits at the assembly origin (identity).
    """
    step = """ISO-10303-21;
HEADER;
ENDSEC;
DATA;
#1=PRODUCT('ROOT','x','',(#2));
#2=PRODUCT_CATEGORY('','');
#3=PRODUCT_DEFINITION_FORMATION('','',#1);
#4=PRODUCT_DEFINITION('','',#3,#5);
#5=APPLICATION_CONTEXT('');
#6=PRODUCT('CHILD-A','x','',(#2));
#7=PRODUCT_DEFINITION_FORMATION('','',#6);
#8=PRODUCT_DEFINITION('','',#7,#5);
#9=PRODUCT('CHILD-B','x','',(#2));
#10=PRODUCT_DEFINITION_FORMATION('','',#9);
#11=PRODUCT_DEFINITION('','',#10,#5);
#12=PRODUCT('CHILD-C','x','',(#2));
#13=PRODUCT_DEFINITION_FORMATION('','',#12);
#14=PRODUCT_DEFINITION('','',#13,#5);
#15=APPLICATION_CONTEXT('');
#16=DIRECTION('',(0.0,0.0,1.0));
#17=DIRECTION('',(1.0,0.0,0.0));
#18=CARTESIAN_POINT('',(100.0,200.0,300.0));
#19=AXIS2_PLACEMENT_3D('',#16,#18,#17);
#20=CARTESIAN_POINT('',(0.0,5.0,0.0));
#21=DIRECTION('',(0.0,1.0,0.0));
#22=AXIS2_PLACEMENT_3D('',#16,#20,#21);
#23=CARTESIAN_POINT('',(0.0,0.0,0.0));
#24=AXIS2_PLACEMENT_3D('',#16,#23,#17);
#25=AXIS2_PLACEMENT_3D('',#16,#23,#17);
#26=PRODUCT_DEFINITION_SHAPE('','',#8);
#27=PRODUCT_DEFINITION_SHAPE('','',#11);
#28=PRODUCT_DEFINITION_SHAPE('','',#14);
#29=NEXT_ASSEMBLY_USAGE_OCCURRENCE('A1','A1','A1',#4,#8,$);
#30=NEXT_ASSEMBLY_USAGE_OCCURRENCE('B1','B1','B1',#4,#11,$);
#31=NEXT_ASSEMBLY_USAGE_OCCURRENCE('C1','C1','C1',#4,#14,$);
#40=SHAPE_REPRESENTATION('',(#19,#22,#24),#15);
#41=SHAPE_REPRESENTATION('',(#25),#15);
#42=SHAPE_REPRESENTATION('',(#25),#15);
#43=SHAPE_REPRESENTATION('',(#25),#15);
#44=(REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION(#45)SHAPE_REPRESENTATION_RELATIONSHIP()REPRESENTATION_RELATIONSHIP('','',#40,#41));
#45=ITEM_DEFINED_TRANSFORMATION('A1',#25,#19);
#46=(REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION(#47)SHAPE_REPRESENTATION_RELATIONSHIP()REPRESENTATION_RELATIONSHIP('','',#40,#42));
#47=ITEM_DEFINED_TRANSFORMATION('B1',#25,#22);
#48=(REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION(#49)SHAPE_REPRESENTATION_RELATIONSHIP()REPRESENTATION_RELATIONSHIP('','',#40,#43));
#49=ITEM_DEFINED_TRANSFORMATION('C1',#25,#24);
#50=CONTEXT_DEPENDENT_SHAPE_REPRESENTATION(#44,#26);
#51=CONTEXT_DEPENDENT_SHAPE_REPRESENTATION(#46,#27);
#52=CONTEXT_DEPENDENT_SHAPE_REPRESENTATION(#48,#28);
ENDSEC;
END-ISO-10303-21;
"""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".stp", delete=False) as fh:
        fh.write(step.encode())
        tmp = Path(fh.name)
    out = parse_step_assembly(tmp)
    tmp.unlink()
    rows = {r["name"]: r for r in out["instances"]}
    assert set(rows) == {"A1", "B1", "C1"}, rows
    a, b, c = rows["A1"], rows["B1"], rows["C1"]
    assert a["parent_product"] == "ROOT" and a["child_product"] == "CHILD-A", a
    assert a["identity"] is False, a
    assert [abs(x) for x in a["transform"]["pos"]] == [100.0, 200.0, 300.0], a
    assert b["identity"] is False, b
    assert abs(b["transform"]["pos"][1] - 5.0) < 1e-9, b
    assert abs(b["transform"]["rot"][0][1] - 1.0) < 1e-9, b  # 90 deg about Z
    assert c["identity"] is True, c
    print("selftest ok: A1 +slot, B1 +90degZ, C1 identity")
    return 0


def instances_mode(path: Path, out: Path) -> int:
    result = parse_step_assembly(path)
    out.write_text(json.dumps(result, indent=1))
    n = len(result["instances"])
    ident = sum(1 for r in result["instances"] if r["identity"] is True)
    placed = sum(1 for r in result["instances"] if r["identity"] is False)
    notrans = sum(1 for r in result["instances"] if r["identity"] is None)
    print(f"{path.name}: {n} NAUO ({ident} identity, {placed} transformed, {notrans} no transform)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--instances", nargs=2, metavar=("FILE.stp", "OUT.json"))
    mode.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    return instances_mode(Path(args.instances[0]), Path(args.instances[1]))


if __name__ == "__main__":
    sys.exit(main())
