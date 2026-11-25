# acc-Cont-Lft: the single-rep reading, the 13 reps and the manifold mask (2026-11-25)

**Status**: analysis-only, recorded 2026-11-25. No code change and no fitness
row in this note. It explains why the historical "spaghetti" appeared in
`acc-Cont-Lft.CATPart` and why the part still exports a fragment after the
W1 half-read fix: the single-rep mesh is `manifold = True`, so the
multi-region second chance never fires.

**Part**: `Submarine-Tr-1700-S42-Catia/acc-Cont-Lft.CATPart`, 406,528 B,
`sha256 fb08de961335c36753728c734b06201dc24241b74f342396a10590f59961947c`
(Submarino snapshot 20). All figures below were re-measured on
2026-11-25 with the shipped Python chain; the Rust port carries the
same laws and the W1 parity was byte-identical.

## What the body actually is

`_scan_token_nodes` over the located store body
`[0x40630, 0x5eb8c)` finds **13 token nodes** (rep 0 … 12), not
one: 12 walk-exact table nodes plus the `00 00 00 01` container at
node 5. The single-rep reading uses node 0's 220 elements; the other
12 nodes' own regions are ignored.

| rep | node offset | kind | c1 = elements | payload B | walk end |
|---:|---:|---|---:|---:|---:|
| 0 | `0x406ea` | table walk | 220 | 3,872 | 1,860 |
| 1 | `0x41671` | table walk | 212 | 3,836 | 1,794 |
| 2 | `0x425d4` | table walk | 1,278 | 29,927 | 14,749 |
| 3 | `0x49b22` | table walk | 570 | 25,133 | 6,060 |
| 4 | `0x4fdb6` | table walk | 228 | 5,759 | 2,486 |
| 5 | `0x5149c` | container (`00 00 00 01`) | 256 | 19,192 | window 3,120 |
| 6 | `0x55ffb` | table walk | 117 | 2,298 | 1,023 |
| 7 | `0x5695c` | table walk | 186 | 4,262 | 1,664 |
| 8 | `0x57a69` | table walk | 38 | 1,350 | 379 |
| 9 | `0x58016` | table walk | 38 | 1,336 | 371 |
| 10 | `0x585b5` | table walk | 114 | 18,290 | 1,022 |
| 11 | `0x5cd8e` | table walk | 38 | 1,188 | 335 |
| 12 | `0x5d299` | table walk | 38 | 6,383 | 335 |

## The spaghetti mechanism

The single-rep reading (`identity-table-walk`) resolves the **whole
store body** against the list node's region — `find_list_node` picks the
largest list-token payload, which is node 0 here, and the record scan
uses its 220 elements. That is the committed shape for a one-period
body; on this 13-rep body it is a misresolution:

1. The record scan sees 282 candidate positions and parses 142
   records from the 13 reps (96 short + 46 extended), all against
   node 0's 220 points.
2. Several reps have `c1 <= 228` (nodes 1, 4, 6, 7, 8, 9, 10, 11, 12),
   so their narrow references land inside `[0..219]` and pass the
   in-bounds gate instead of declining.
3. The surviving loops over-use edges. `primary_loop_seam` declines
   **96** loops and `primary_loop_relist_skips` drops **19** more —
   **115** loops forced out in total.
4. The remaining mix still satisfies `mesh_stats(...).manifold == True`
   (and `degenerate == 0`). The part therefore passes L2 as
   **220 vertices / 563 triangles / 137 boundary edges**, but the
   triangles are node 0's territory read through the other reps' record
   stream, not the part's surface.

Before the W1 half-read fix the same collision kept the u8 garbage in
the emission (1,405 triangles, 35 degenerates, `not-manifold`). W1
declined the `0x5255e` u8-over-u16be record family and the L2 class
flipped to `pass` (1,405 → 563 triangles) — correct as a fail-closed
classification, but it also made the mesh manifold, which is the state
that hides the remaining misresolution.

## What the multi-region reading resolves

`_decode_multiregion` over the same body resolves each rep against its
own element space (the W1-B law, plus the W17 container rep):

- **13 reps** (12 table-walk + 1 container), 0 out-of-bounds reps;
- **3,305 vertices / 6,602 triangles**, manifold, 0 degenerate,
  **12 boundary edges** (the open-shell band), 86 extended records;
- stage `identity-multiregion` with `multiregion_container_reps = 1`.

The earlier W1-B claims row records the pre-container projection as
12 reps / 4,649 triangles; W17 adds the container rep, which is why the
current reading is 13 reps / 6,602 triangles
(`docs/evidence/data/marathon-w1b-multiregion-claims.csv`, row 704;
`docs/evidence/marathon/w17-progress.md`).

## Why it is still not adopted

The caller's fire gate is:

```python
if triangles and (degenerate or not mesh.mesh_stats(list(triangles)).manifold):
    ... _decode_multiregion(...)
```

The single-rep emission has `degenerate == 0` and `manifold == True`,
so the route is never called for this part. The W1-B design deliberately
keeps every passing store byte-identical (270 multi-node stores pass
through the single-rep reading and must not churn), so widening the gate
to "any multi-node body" would re-decode and change a large population.

A narrower reopening criterion, if the corpus ever demands it, is a
**rep-count vs element-space mismatch**: when a store carries several
walk-exact token nodes and the single-rep emission covers only node 0's
element count, the multi-region reading is a candidate even when the
single-rep mesh is manifold. That is a measured policy change, not a
bug fix: it needs its own A/B (pass→pass byte-identity on the 270
multi-node passers) and an owner decision. This note records the gap;
it does **not** flip the gate.

## Reproduction

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
from catpart.geometry import composite, mesh
from catpart.geometry.export import _export_store_data

p = Path(".../Submarine-Tr-1700-S42-Catia/acc-Cont-Lft.CATPart")
data = p.read_bytes()
spans = []
summary, _verts, tris = _export_store_data(data, spans)
print(summary["composite"], len(tris), mesh.mesh_stats(list(tris)))
for lo, hi in spans:
    print("nodes", len(composite._scan_token_nodes(data, lo, hi)))
    status, result, failure = composite._decode_multiregion(data, lo, hi)
    print(status, failure)
    if result:
        pts, mrtris, deg, info, _ = result
        print(info["multiregion_reps"], len(mrtris), deg,
              mesh.mesh_stats(list(mrtris)))
PY
```

Expected: `identity-table-walk`, 563 triangles, `manifold=True`,
`boundary_edges=137`, `primary_loop_skips=96`,
`primary_loop_relist_skips=19`, 46/46 extended records declined;
`_decode_multiregion` returns `ok` with 13 reps / 6,602 triangles /
0 degenerate / 12 boundary edges.

## Related evidence

- [W1 progress](marathon/w1-progress.md) — the `0x5255e`
  u8-over-u16be half-read and the 1,405 → 563 triangle flip.
- [W1-B progress](marathon/w1b-progress.md) — the
  multi-region law and the 12-rep / 4,649-triangle projection.
- [W17 progress](marathon/w17-progress.md) — the container
  rep (`multiregion_container_reps = 1`).
- [W26 compact see-body note](2026-11-24-seebody-compact-face-gp.md) —
  a different empty-mesh route; unrelated to this store family.
