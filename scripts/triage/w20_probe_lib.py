#!/usr/bin/env python3
"""W20 shared probe helpers (read-only triage, 2026-11-22).

The pieces the two W20 entry points share: the sibling-triage loader
(the W12 oracle-lib pattern) and the streaming STL reader (running
bbox + rounded unique-vertex key set; the mesh is never materialized).
"""

from __future__ import annotations

import importlib.util
import math
import struct
import sys
from pathlib import Path

#: Coordinate key grid for coincidence rates (0.01 = 10 um at mm scale;
#: float32 ulp at car-scale magnitudes is <= 0.001, safely inside the
#: half-grid 0.005).
KEY_DIGITS = 2


def load_triage(name: str):
    """A sibling triage script by file path (the W12 oracle-lib loader)."""
    path = Path(__file__).resolve().parent / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, mod)
    spec.loader.exec_module(mod)
    return mod


def coord_key(x, y, z):
    """The packed rounded-coordinate identity key (0.01 grid)."""
    return struct.pack(
        "<3f", round(x, KEY_DIGITS), round(y, KEY_DIGITS), round(z, KEY_DIGITS)
    )


def stream_stl(path: Path) -> dict:
    """Reference STL facts without materializing the mesh: triangle
    count, running vertex bbox, diagonal, unique-vertex key set."""
    with open(path, "rb") as f:
        head = f.read(84)
        if head[:5] == b"solid" and b"facet" in head[:200]:
            raise SystemExit("named-outcome: ascii-stl-unsupported (binary only)")
        n_tri = struct.unpack("<I", head[80:84])[0]
        mins = [math.inf] * 3
        maxs = [-math.inf] * 3
        keys = set()
        n_read = 0
        while True:
            rec = f.read(50)
            if not rec:
                break
            vals = struct.unpack("<12fH", rec)
            for i in range(3):
                x, y, z = vals[3 + i * 3 : 6 + i * 3]
                mins[0] = min(mins[0], x)
                mins[1] = min(mins[1], y)
                mins[2] = min(mins[2], z)
                maxs[0] = max(maxs[0], x)
                maxs[1] = max(maxs[1], y)
                maxs[2] = max(maxs[2], z)
                keys.add(coord_key(x, y, z))
            n_read += 1
    if n_read != n_tri:
        raise SystemExit(f"named-outcome: stl-truncated ({n_read} of {n_tri})")
    diag = math.sqrt(sum((maxs[i] - mins[i]) ** 2 for i in range(3)))
    return {
        "n_tri": n_read,
        "bbox_min": mins,
        "bbox_max": maxs,
        "diag": diag,
        "n_unique_verts": len(keys),
        "keys": keys,
    }


# The body-map probe reads this module as "w20_probe_lib" and aliases
# the reader name it uses.
stream_stl_keys = stream_stl
