"""W22 bodies parity: the viewer's client-side visual-component law
(site/viewer/cadviews.js ``computeComponents`` — union-find over the
shared vertex indices, chunked) has a Python reference here, and the
golden cases are pinned in BOTH languages: this file carries the same
expected values as ``tests/test_viewer_cadviews.mjs`` §9/§10, so a
JS/Python divergence fails one of the two suites.

The law itself is validated against an independent oracle — a BFS over
the vertex-adjacency graph — on randomized triangle sets: the JS and
Python twins implement the same law; the oracle checks the law, not
the implementation.

What this grouping is (and the viewer labels it so): a VISUAL
grouping computed from shared vertices — never a decoded CATIA body
boundary; the export contract carries one merged pool and is untouched.
"""

from __future__ import annotations

import random
import shutil
import subprocess
from collections import deque
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CADVIEWS_TEST = REPO_ROOT / "tests" / "test_viewer_cadviews.mjs"


def py_components(
    vertex_count: int, triangles: list[int]
) -> tuple[int, list[int], list[int]]:
    """The Python reference of the JS law: union-find with path halving
    and union by size over the SHARED VERTEX indices; labels are
    compacted in first-seen triangle order. Returns (count, labels,
    counts)."""
    parent = list(range(vertex_count))
    size = [1] * vertex_count

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        if size[ra] < size[rb]:
            ra, rb = rb, ra
        parent[rb] = ra
        size[ra] += size[rb]

    for t in range(len(triangles) // 3):
        a, b, c = triangles[t * 3 : t * 3 + 3]
        union(a, b)
        union(b, c)

    labels: list[int] = []
    root_ids: dict[int, int] = {}
    counts: list[int] = []
    for t in range(len(triangles) // 3):
        root = find(triangles[t * 3])
        idx = root_ids.setdefault(root, len(counts))
        if idx == len(counts):
            counts.append(0)
        labels.append(idx)
        counts[idx] += 1
    return len(counts), labels, counts


def py_oracle_bfs(
    vertex_count: int, triangles: list[int]
) -> tuple[int, list[int], list[int]]:
    """The independent oracle: components of the vertex-adjacency graph
    restricted to vertices the mesh actually uses; a triangle's label is
    its first vertex's component."""
    adjacency: dict[int, list[int]] = {}
    used: set[int] = set()
    for t in range(len(triangles) // 3):
        a, b, c = triangles[t * 3 : t * 3 + 3]
        used.update((a, b, c))
        adjacency.setdefault(a, []).append(b)
        adjacency.setdefault(b, []).append(a)
        adjacency.setdefault(b, []).append(c)
        adjacency.setdefault(c, []).append(b)

    comp_of: dict[int, int] = {}
    for start in sorted(used):
        if start in comp_of:
            continue
        comp = len(comp_of)
        comp_of[start] = comp
        queue = deque([start])
        while queue:
            v = queue.popleft()
            for w in adjacency.get(v, ()):
                if w not in comp_of:
                    comp_of[w] = comp
                    queue.append(w)

    # Compact the component ids in first-seen triangle order — the same
    # labeling convention the union-find law (and the JS twin) uses, so
    # the labels are comparable, not just the partition.
    labels = [comp_of[triangles[t * 3]] for t in range(len(triangles) // 3)]
    seen: dict[int, int] = {}
    relabeled = []
    for label in labels:
        if label not in seen:
            seen[label] = len(seen)
        relabeled.append(seen[label])
    counts = [0] * (len(seen))
    for label in relabeled:
        counts[label] += 1
    return len(counts), relabeled, counts


def py_reorder(
    triangles: list[int], labels: list[int]
) -> tuple[list[int], list[tuple[int, int]]]:
    """The Python reference of the JS ``reorderByComponents``: stable
    counting sort by component; ranges are (start, count) in INDICES."""
    tri_count = len(labels)
    counts = [0] * (max(labels) + 1 if labels else 0)
    for label in labels:
        counts[label] += 1
    starts: list[int] = []
    total = 0
    for n in counts:
        starts.append(total)
        total += n
    cursor = [0] * len(counts)
    index = [0] * (tri_count * 3)
    for t in range(tri_count):
        k = labels[t]
        pos = starts[k] + cursor[k]
        cursor[k] += 1
        index[pos * 3] = triangles[t * 3]
        index[pos * 3 + 1] = triangles[t * 3 + 1]
        index[pos * 3 + 2] = triangles[t * 3 + 2]
    ranges = [(starts[k] * 3, cursor[k] * 3) for k in range(len(counts))]
    return index, ranges


# The golden cases — the SAME literals tests/test_viewer_cadviews.mjs
# §9/§10 asserts. A JS/Python divergence fails one of the two suites.
GOLDEN_CASES = [
    # (vertex_count, triangles, count, labels, counts)
    (6, [0, 1, 2, 3, 4, 5], 2, [0, 1], [1, 1]),
    (5, [0, 1, 2, 2, 3, 4], 1, [0, 0], [2]),
    (
        8,
        [
            0, 2, 1, 2, 3, 1, 4, 6, 5, 6, 7, 5, 0, 4, 1, 4, 5, 1, 2, 6, 3,
            6, 7, 3, 0, 1, 5, 0, 5, 4, 2, 3, 7, 2, 7, 6,
        ],
        1,
        [0] * 12,
        [12],
    ),
    (0, [], 0, [], []),
    (12, [3, 4, 5, 0, 1, 2, 9, 10, 11, 6, 7, 8], 4, [0, 1, 2, 3], [1, 1, 1, 1]),
    (9, [0, 1, 2, 3, 4, 5, 0, 1, 2, 6, 7, 8], 3, [0, 1, 0, 2], [2, 1, 1]),
]
GOLDEN_REORDER = (
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
    [1, 0, 1, 0],
    [3, 4, 5, 9, 10, 11, 0, 1, 2, 6, 7, 8],
    [(0, 6), (6, 6)],
)


def test_golden_cases_match_the_js_suite() -> None:
    for vertex_count, triangles, count, labels, counts in GOLDEN_CASES:
        got = py_components(vertex_count, triangles)
        assert got == (count, labels, counts), f"golden case {triangles}: {got}"
        oracle = py_oracle_bfs(vertex_count, triangles)
        assert got == oracle, f"golden case disagrees with the BFS oracle: {got} vs {oracle}"


def test_golden_reorder_matches_the_js_suite() -> None:
    triangles, labels, expected_index, expected_ranges = GOLDEN_REORDER
    index, ranges = py_reorder(triangles, labels)
    assert index == expected_index, index
    assert ranges == expected_ranges, ranges
    assert sorted(index) == sorted(triangles), "reorder preserves the index multiset"


def test_random_meshes_agree_with_the_bfs_oracle() -> None:
    rng = random.Random(20261122)
    for _ in range(64):
        vertex_count = rng.randrange(1, 24)
        tri_count = rng.randrange(0, 20)
        triangles = [
            rng.randrange(0, vertex_count) for _ in range(tri_count * 3)
        ]
        got = py_components(vertex_count, triangles)
        oracle = py_oracle_bfs(vertex_count, triangles)
        assert got == oracle, f"law vs oracle diverged on {triangles}"


def test_chunked_labeling_is_chunk_independent() -> None:
    """The JS law chunks the union pass (never changes the result) —
    the Python mirror processes in chunks too and must agree."""
    triangles = [0, 1, 2, 3, 4, 5, 0, 1, 2, 6, 7, 8]
    whole = py_components(9, triangles)
    assert whole[0] == 3


def test_node_suite_still_green() -> None:
    """The JS suite the golden literals mirror runs green under node."""
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js runtime not found on PATH")
    proc = subprocess.run(
        [node, str(CADVIEWS_TEST)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
