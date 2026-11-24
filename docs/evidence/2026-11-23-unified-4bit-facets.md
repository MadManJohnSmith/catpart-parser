# Unified 4-bit facet law (2026-11-23)

**Status**: landed on `feat/unified-4bit-facets` (`abba0a7` + the
`0x41` guard fix `cadbb44`); Rust port in the same branch. The
ground-truth A/B on Audi R8 and Motor is green; Aston Vulcan and the
knurling screw are still pending on this machine (the artifacts are not
in the checkout).

## The law

The facet marker is a 4-bit mask over the extended header's primitive
bytes (the short form keeps its committed count-table grammar):

| bit | primitive | field |
|---|---|---|
| 0 | triangles | `ty` (independent 3-ref triangles) |
| 1 | strips | `b3` (count-table entries with strip semantics) |
| 2 | polygons | `b4` (count-table entries with closed-polygon fan semantics) |
| 3 | normal | 12-byte f32le normal after the `u32le n` |

- 5-byte forms (two primitives): `0x43` (ty+b3), `0x45` (ty+b4),
  `0x46` (b3+b4), `0x4b` (ty+b3+normal), `0x4d` (ty+b4+normal),
  `0x4e` (b3+b4+normal).
- 6-byte forms (three primitives): `0x47` (ty+b3+b4), `0x4f`
  (ty+b3+b4+normal).
- `0x41` (bit0 only) is the no-count triangle list:
  `01 41 ty ff` + `u32le n`, `n == 3*ty`, refs directly after `n`.
- `0x44` (bit2 only) is the closed-polygon fan without normal
  (`0x4c` without the 12-byte payload).

The counts law is `n == 3*ty + sum(counts)`; the ref width is the
committed vote (u8/u16be, u24be above 65,535 elements). The 5-byte and
6-byte records are emitted through the existing extended-record
manifold gate (per-record `EdgeGuard.admit`, degenerate members
filtered and named).

## The 0x41 guard (the canary)

The first cut used a sum-only count-table probe (`_has_count_table`).
That is wrong on real bytes: small u16 refs (`00 03`, `01 02`) sum to
`n` by coincidence and the probe stole 13/275 `0x41` records on the
knurling screw, 5/87 on Audi and 17/943 on Motor. The probe is gone.

The final order is:

1. The committed count law votes first.
2. If its winner trips the `#66`/`W1` anti-half-read battery, the record
   is unresolvable and the no-count reading does **not** resurrect it
   (the Audi `0x301e912` canary, reproduced byte-for-byte by
   `tests/test_composite_export.py::test_composite_relaxed_u8_half_read_of_a_u16le_stream_is_declined`).
3. A clean or absent count winner lets the `0x41` no-count triangle
   list claim the bytes.
4. The same battery runs on the no-count winner.

The `0x41` overlap span follows the same law: an accepted `0x41` with
`counts == (3,)*ty` and `n == 3*ty` ends at `offset + 8 + width*n`
(no count table), so the extended parser is not fenced off by a phantom
table.

## Ground-truth A/B (the gate)

`scripts/benchmark_ground_truth.py`, exact vertex-set nearest search.
Both parts: 0 degenerates, `manifold = True`.

| part | CATPart tris | reference tris | area CATPart (mm²) | area reference (mm²) | area_ratio | chamfer (mm) | Hausdorff max (mm) | p95 (mm) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Audi R8 (`AUDINSKLOPIC_AllCATPart`) | 225,958 | 225,973 | 46,027,812.55 | 46,039,200.71 | **0.9997526** | 0.0002016 | 0.0006945 | 0.0004697 |
| Motor (`Motor.CATPart`) | 251,380 | 251,380 | 1,919,658.286 | 1,919,658.371 | **0.99999996** | 0.0000321 | 0.0000850 | 0.0000596 |

The Motor count matches the reference exactly; the Audi count is 15
triangles below (the reference's tessellation, not missing surface:
the area ratio is 0.99975 and the nearest-vertex distances are < 0.001
mm).

**Python ≡ Rust**: `fidelity-cli export` produces byte-identical PLYs on
both parts (Audi 225,958 / 114,314; Motor 251,380 / 125,754).

### The 0x43 large-panel audit (cd88)

`cd88ae9d4d51a439` (TouchRows_Wires) gains 6,290 triangles from the
5-byte records and closes from 1,044 boundary edges to 0. The area
grows 4,314.66 -> 33,057.56. The top 1% of the added faces carry ~70%
of that area, which is the signature of large missing panels rather
than a fan misread: every added face lands on a boundary edge of the
base mesh (the result is a closed manifold) and the added median face
area (0.56) matches the base median (0.50). It remains the one delta
that should be re-checked against a reference mesh when one is
available.

## Official-corpus re-pins

All re-measured parts stay `manifold = True` with
`degenerate_triangle_count = 0`; the stores that now close are named.

| part | old pin | new pin | closed |
|---|---:|---:|---|
| `13bb5c0c` LedStrips | 229,732 | 270,136 | no |
| `2fb5b092` | 1,753 | 2,293 | no |
| `44e63faa` | 2,524 | 4,502 | yes |
| `4a32f59c` | 2,451 | 3,438 | no |
| `4abf3eea` | 1,973 | 3,196 | no |
| `612c5e7c` | 4,593 | 6,703 | no |
| `6ab9e107` | 959 | 1,387 | no |
| `97a0a420` | 9,106 | 24,882 | yes |
| `a61588e5` | 3,023 | 7,208 | yes |
| `ba090026` | 4,395 | 7,562 | no |
| `bc235805` | 1,753 | 2,293 | no |
| `c9fdd852` | 17,785 | 19,242 | yes |
| `cd76cab5` | 1,617 | 2,240 | yes |
| `d31ea2c1` | 2,633 | 3,530 | no |
| `d4127e6b` | 5,094 | 6,774 | yes |
| `b912cbef` (dedup no-regression) | 51,826 | 74,122 | yes |
| `cd88ae9d` (relist pin) | 3,420 | 9,710 | yes |
| `545707b9` (dedup case) | 2,978 | 4,072 | no |
| `labios/main` | 8,995 | 9,622 | yes |

`labios` is the cleanest official-corpus case: +627 triangles,
+73.69 mm² (7,024.81 -> 7,098.50, +1.05%) and 651 boundary edges close
with 0 degenerates.

## Verification

```bash
# the canary + the new positive law
.venv/bin/python -m pytest tests/test_composite_export.py -q \
  -k "relaxed_u8_half_read or 0x41_no_count"

# the A/B
.venv/bin/python scripts/benchmark_ground_truth.py \
  --catpart .../AUDINSKLOPIC_AllCATPart.CATPart \
  --reference .../AUDINSKLOPIC_AllCATPart_stl.stl
.venv/bin/python scripts/benchmark_ground_truth.py \
  --catpart .../Motor.CATPart --reference .../Motor.stl

# Python ≡ Rust
port/target/release/fidelity-cli export .../AUDINSKLOPIC_AllCATPart.CATPart /tmp/rs-audi.ply
cmp /tmp/rs-audi.ply /tmp/py-audi.ply
```

## Pending

- Aston Vulcan A/B: the OBJ reference run did not finish on this
  machine (killed after >45 min in the exact vertex search); the
  area/Hausdorff pair should be re-run with a coarser `--cell-size` or
  on Gallyfrey.
- Knurling screw: the `.CATPart` is not in this checkout; the reported
  13,590 triangles / closed / boundary 0 cannot be reproduced here.
- Full Python suite + `scripts/check.sh` (cargo, wasm-pack, pkg sync,
  node) before the merge.
- W3 + W15 re-merge and the Submarino sweep are the next landing steps,
  not part of this note.
