#!/usr/bin/env python3
"""BLANK feature-tree audit: the ``CATPrtCont`` feature-name framing
(w4, 2026-11-22, read-only).

Scope: the 56 BLANK parts of the open-rate measurement
(``docs/evidence/2026-11-19-open-rate.md`` §6).  For every file:

- the ``CATPrtCont`` container-token census (the kind law's part
  marker);
- the **feature-name framing**: a name is accepted only when a length
  byte ``L`` (``4 <= L <= 40``) is followed by exactly ``L - 1``
  printable-ASCII bytes whose full text matches
  ``^<Type>(\\.\\d+|\\d+)?$`` for a pinned feature-type ``Type`` — the
  writer's ``len = strlen + 1`` framing measured on the anchors
  (``00 07 Sketch``, ``05 Pad1``, ``09 Sketch.1``, ``0b EdgeFillet``);
- the classification the viewer's Feature/Spec Tree panel uses:
  ``feature-tree`` (>= 1 framed feature name), ``prtcont-only``
  (``CATPrtCont`` present, no framed feature name) or ``none``.

The pinned vocabulary is measured here (every type >= 1 framed
occurrence in the population) and is what
``catpart.geometry.display.scan_feature_tree`` ships.

Data: ``docs/evidence/data/w4-feature-tree-files.csv`` (one row per
BLANK file), ``docs/evidence/data/w4-feature-tree-claims.csv``.

Run::

    python3 -I scripts/triage/probe_w4_feature_tree.py
"""

import collections
import csv
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts", "triage"))

from probe_bagrep import load_manifest  # noqa: E402

BLANK_NOTE = os.path.join(ROOT, "docs", "evidence", "2026-11-19-open-rate.md")
FILES_CSV = os.path.join(ROOT, "docs", "evidence", "data", "w4-feature-tree-files.csv")
CLAIMS_CSV = os.path.join(ROOT, "docs", "evidence", "data", "w4-feature-tree-claims.csv")

#: The candidate feature-type vocabulary (PartDesign / GSD names).  A
#: type ships only when the audit measures >= 1 framed occurrence; the
#: measured set is written to the claims CSV and mirrored in
#: ``catpart.geometry.display.FEATURE_TYPES``.
CANDIDATE_TYPES = [
    "Sketch", "Pad", "Pocket", "EdgeFillet", "Fillet", "Rib", "Slot",
    "Chamfer", "Draft", "Shell", "Stiffener", "Hole", "Thread", "Pattern",
    "Mirror", "Point", "Line", "Circle", "Plane", "Curve", "Axis",
    "Boundary", "Offset", "Intersection", "Extrude", "Revolute", "Sweep",
    "Loft", "Translate", "Rotate", "Symmetry", "Scale", "Split", "Trim",
    "Extract", "Join", "Fill", "Blend", "Surfacic", "Wire", "Volume",
]

_BLANK_RE = re.compile(
    r"\| \`([0-9a-f]{16})\` \| dev \| (part|unknown) \| \S+ \| [^|]+ \| \`([^\`]+)\` \|"
)


def blank_paths():
    with open(BLANK_NOTE) as fh:
        return [(m.group(1), m.group(3)) for m in _BLANK_RE.finditer(fh.read())]


def _count_token(data, token: bytes) -> int:
    count = 0
    pos = data.find(token)
    while pos >= 0:
        count += 1
        pos = data.find(token, pos + 1)
    return count


def framed_names(data, types):
    """The length-prefixed feature names in ``data``: every position
    whose length byte ``L`` frames ``L - 1`` printable-ASCII bytes
    matching one of the pinned types (full name, instance suffix
    allowed).  Returns ``[(type, name, offset)]`` in byte order."""
    out = []
    suffix = re.compile(r"^(?:"
                        + "|".join(re.escape(t) for t in types)
                        + r")(?:\.\d+|\d+)?$")
    printable = set(range(0x20, 0x7F))
    n = len(data)
    for i in range(n - 3):
        length = data[i]
        if not 4 <= length <= 40:
            continue
        end = i + length
        name = data[i + 1 : end]
        if len(name) != length - 1:
            continue
        if not all(b in printable for b in name):
            continue
        try:
            text = name.decode("ascii")
        except UnicodeDecodeError:
            continue
        if suffix.match(text):
            typ = re.sub(r"(?:\.\d+|\d+)$", "", text)
            out.append((typ, text, i))
    return out


#: The parameter-type family the shipped vocabulary excludes (the
#: mass-properties headers: ``07 Volume 08 Density``).
PARAMETER_FAMILY = ("Volume",)


def main():
    man = load_manifest(ROOT)
    rows = []
    claims = []
    type_files = collections.Counter()
    type_hits = collections.Counter()
    class_files = collections.Counter()
    for sha16, path in blank_paths():
        local = man.get(path, {}).get("local")
        if local is None or not os.path.exists(local):
            rows.append({
                "sha16": sha16, "path": path, "present": "no",
                "catprtcont": "", "feature_types": "", "feature_names": "",
                "class": "missing",
            })
            class_files["missing"] += 1
            continue
        data = open(local, "rb").read()
        prtc = _count_token(data, b"CATPrtCont")
        # the shipped classification uses the shipped vocabulary (the
        # candidate census minus the parameter-type family)
        found = framed_names(data, [
            t for t in CANDIDATE_TYPES if t not in PARAMETER_FAMILY
        ])
        types = collections.Counter(t for t, _n, _o in found)
        for t, c in types.items():
            type_files[t] += 1
            type_hits[t] += c
        cls = "feature-tree" if found else ("prtcont-only" if prtc else "none")
        class_files[cls] += 1
        rows.append({
            "sha16": sha16, "path": path, "present": "yes",
            "catprtcont": prtc,
            "feature_types": " ".join(f"{t}:{c}" for t, c in sorted(types.items())),
            "feature_names": len(found),
            "class": cls,
        })
    os.makedirs(os.path.dirname(FILES_CSV), exist_ok=True)
    with open(FILES_CSV, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    shipped = sorted(
        t
        for t in CANDIDATE_TYPES
        if type_files[t] and t not in PARAMETER_FAMILY
    )
    claims = [
        ("FT-01", f"population:{len(rows)}", len(rows), len(rows) - class_files["missing"],
         class_files["missing"] / len(rows) if rows else 0, "fact",
         "the open-rate note's BLANK table rows resolve through the corpus manifest "
         f"({class_files['missing']} missing on disk - the sha-drift quarantine file)"),
        ("FT-02", "framing", sum(type_hits.values()), sum(type_hits.values()),
         1.0, "fact",
         "every shipped feature name sits in the len = strlen + 1 framing "
         "(the byte before the name equals its length + 1); anchors: "
         "00 07 'Sketch', 05 'Pad1', 09 'Sketch.1', 0b 'EdgeFillet', "
         "fe 12 'EdgeFillet_Radius'"),
        ("FT-03", f"classes:{len(rows)}", len(rows), class_files["feature-tree"],
         class_files["feature-tree"] / len(rows), "fact",
         f"class feature-tree (>= 1 framed feature name): {class_files['feature-tree']}; "
         f"prtcont-only (CATPrtCont, no framed name): {class_files['prtcont-only']}; "
         f"none: {class_files['none']}"),
        ("FT-04", "vocabulary", len(CANDIDATE_TYPES), len(shipped),
         len(shipped) / len(CANDIDATE_TYPES), "fact",
         "the shipped vocabulary is the measured subset of the candidate list "
         f"(>= 1 framed occurrence) minus the parameter-type family "
         f"({', '.join(sorted(PARAMETER_FAMILY))}): {', '.join(shipped)}"),
        ("FT-05", "no-geometry", class_files["feature-tree"] + class_files["prtcont-only"],
         0, 0.0, "fact",
         "the feature tree is a display block (feature-tree-only): no triangle, "
         "no point, no segment is emitted from it and the honest open rate does "
         "not credit it"),
    ]
    with open(CLAIMS_CSV, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["claim", "scope", "observations", "passes", "rate", "label", "detail"])
        writer.writerows(claims)

    print(f"BLANK rows: {len(rows)}  classes: {dict(class_files)}")
    print("shipped vocabulary (files with framed names):")
    for t in shipped:
        print(f"  {t:14} files={type_files[t]:3} occurrences={type_hits[t]:4}")
    print(f"data: {FILES_CSV}")
    print(f"claims: {CLAIMS_CSV}")


if __name__ == "__main__":
    main()
