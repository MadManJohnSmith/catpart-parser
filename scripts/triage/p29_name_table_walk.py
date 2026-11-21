#!/usr/bin/env python3
"""P2.9 probe: V5R26 name-table enumeration and `own(D)` attribution (#68).

Read-only. Measures, over a directory of `.CATProduct` files:

* the parser blind spot before #68: documents whose marker passes extract
  zero instances;
* which of those carry the V5R26 name-table signature, and how many names
  the new branch enumerates (identity vs undecodable placement);
* the ownership walk `own(D) = names(D) - union(names(P))` for a root:
  total instances and their placement states.

Modes:
    python3 -I scripts/triage/p29_name_table_walk.py --report DIR
    python3 -I scripts/triage/p29_name_table_walk.py --tree DIR ROOT_STEM
    python3 -I scripts/triage/p29_name_table_walk.py --selftest
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import catpart.fixtures_assembly as fa  # noqa: E402


def products(directory: Path) -> dict[str, bytes]:
    return {
        path.stem: path.read_bytes()
        for path in sorted(directory.glob("*.CATProduct"))
    }


def report(directory: Path) -> int:
    docs = products(directory)
    empty = 0
    tables = 0
    names = 0
    undecodable = 0
    for data in docs.values():
        doc = fa.read_product_structure(data)
        if doc["total_instances"] == 0:
            empty += 1
            continue
        if not any(i["pairing_rule"] == "name_table" for i in doc["instances"]):
            continue
        tables += 1
        names += doc["total_instances"]
        undecodable += doc["undecodable_instances"]
    print(f"{directory}")
    print(f"  products                        {len(docs)}")
    print(f"  name-table documents            {tables}")
    print(f"  enumerated names                {names}")
    print(f"  undecodable enumeration         {undecodable}")
    print(f"  documents still empty           {empty}")
    for stem in ("VM-vela-Mast", "MD-MTU-16V-652-MB81"):
        if stem not in docs:
            continue
        doc = fa.read_product_structure(docs[stem])
        print(
            f"  {stem}: {doc['total_instances']} instances "
            f"({doc['identity_instances']} identity, "
            f"{doc['undecodable_instances']} undecodable)"
        )
    return 0


def tree(directory: Path, root: str) -> int:
    docs = products(directory)
    if root not in docs:
        print(f"missing product: {root}", file=sys.stderr)
        return 1
    result = fa.resolve_owned_assembly(root, docs)
    counts = Counter(row["placement_status"] for row in result["instances"])
    print(
        f"{root}: {result['total_instances']} instances "
        f"({counts.get('identity', 0)} identity, "
        f"{counts.get('undecodable', 0)} undecodable)"
    )
    for row in result["instances"][:12]:
        child = row["child_product"] or "-"
        print("  " * row["depth"] + f"{row['instance_name']} [{row['placement_status']}] -> {child}")
    return 0


def selftest() -> int:
    names = ["Widget", "Sub", "Bolt", "Sub-leaf"]
    assert fa.own_instance_names(names, {"Sub": ["Sub-leaf"]}) == [
        "Widget",
        "Sub",
        "Bolt",
    ]
    assert fa.own_instance_names(names, {}) == names

    texts = [
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
        "Table",
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
        "Widget",
        "Bracket",
        "IsRoot",
    ]
    table = fa.read_product_name_table(texts)
    assert table == {"self_name": "Table", "names": ["Widget", "Bracket"]}
    for text in ("CATMechProdCont", "NoBag"):
        broken = list(texts)
        if text == "CATMechProdCont":
            broken[6] = text
        else:
            broken.remove("PRDBAGREP")
            broken.remove("3DIC")
        assert fa.read_product_name_table(broken) is None
    print("selftest: ok")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--report", type=Path, metavar="DIR")
    mode.add_argument("--tree", nargs=2, metavar=("DIR", "ROOT"))
    mode.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        return selftest()
    if args.report:
        return report(args.report)
    directory, root = args.tree
    return tree(Path(directory), root)


if __name__ == "__main__":
    sys.exit(main())
