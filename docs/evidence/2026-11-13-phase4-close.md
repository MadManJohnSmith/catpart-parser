# Evidence: Phase 4 close — final failure classification and the render sanity gate (2026-11-13, #34)

Close-sequence artifacts per handoff item 5 (owner decision cont. 23:
land the two measured levers, then close under the ROADMAP's
pre-authorized bar-revision rule).

## The final fitness row

`20261113T231506Z-c2ab64` (accepted): **L2 dev 1,033/1,381 = 74.80%**,
held-out 56/61 = 91.80%, L1 flat 1745/1751 + 73/73, exports 1,173.
The climb: 76 (5.50%, 2026-11-10) -> 1,033 (74.80%, 2026-11-13) —
+957 dev passes across 15 stages, every stage independently reviewed,
every row append-only, 0 lost passes at every step.

## The failure classification (fact, CSV-composable from
`stage15-identity-export-files.csv`)

| class | dev | held-out | mechanism (byte-closed, stages 12-14 + review) |
|---|---|---|---|
| **pass** | 1,033 | 56 | — |
| fail-closed `missing-geometry-store` | 125 | 0 | no V5_CFV2 header the probes reach (121 CB0001 catalogs); stage-12 extension landed, residual unreachable-by-construction |
| fail-closed `undecoded-variant` | 140 | 4 | 128 no-pool stores carry ZERO facet records (38 scene-graph directories, 90 template-node layout failures incl. 8 wireframes — structurally incapable); 12 composite (the UV family's element semantics: coordinates not in the payload; bad44bdf's residue unpinnable, byte-verified) |
| exported `empty-mesh` | 58 | 0 | 55 `no-facet-records` (43 zero `01 4x ff` candidates + 12 all-decline verified individually; 839552c2's one parseable record sits outside the decode windows); 3 `records-without-loops` (0x49 n==3*type all-skip / degenerate / no byte law) |
| exported `not-manifold` | 25 | 1 | 15 `content-fins` (distinct non-coplanar sheets IN the bytes), 10 `coplanar-overlap` (books in the bytes, stored plane normals agree), 1 unpinnable residue (3dff4d93: the dup-pin fires, the mesh stays not-manifold) |
| **total fail** | 348 | 5 | — |

(Sum: dev 1,033+125+140+58+25 = 1,381; held-out 56+0+4+0+1 = 61.)

The stage-15 levers landed exactly their measured ceilings (+32 = 24
dup-pin-ALL + 8 unordered dedup, review-verified); every remaining
failure class is closed against any committed-evidence law — the
honest hypothetical via content levers is 0 (the stage-13/14 grants
collapsed under byte verification). Per the pre-authorized rule, the
L2 bar re-adjusts to the measured ceiling **74.80% (margin 0)** with
documented negatives.

## The render sanity gate (G3 precedent, PASS)

Coordinator software render (stdlib-only orthographic raster, three
views, flat shading, painter sort — `render_sanity_close.py`, session
artifact; PNGs committed under `docs/evidence/data/close-renders/`)
over a 6-store Dev subset spanning the stage-15 flips and the size
range, exported through the shipped `catpart-export`:

| store (sha16) | verts/tris | flip | verdict |
|---|---|---|---|
| 25aeb5a0 | 29,866/1,852 | dup-pin | PASS — separation plate: V-cutout + slots (top), circular bore + arc (front) |
| ef61cfc2 | 190,839/5,180 | dup-pin | PASS — rounded-square housing, side flanges, center boss |
| 1d256d12 | 11,773/20 | dedup | PASS — H-beam with end plates |
| 396a9d79 | 14,058/4,025 | dedup | PASS — symmetric machined plate, cross ribs, slots, fillets |
| 1b1ae784 | 60/32 | dup-pin (held-out) | PASS — valve pin: dodecagon section, curved sheet |
| 442c55a8 | 916/624 | pre-existing pass | PASS — clean double circle (fibre retreint) |

No scrambled triangles, no inverted-face noise, shading consistent
across views. Named stdlib limitations: painter sort without a
z-buffer (large intersecting depth ranges can layer arbitrarily —
e.g. ef61cfc2's dark fan is consistent with an internal folded baffle
OR painter order); percentile-clamped normalization (2-98) because
decoded stores carry unused pool vertices that stretch the bbox.

## Reproduction

```
.venv/bin/catpart-export -o <sha16>.ply corpus/<local_path>     # the 6 subset rows
python3 -I ~/.local/state/catpart-parser/render_sanity_close.py <sha16>...
```
(The rasterizer is a session artifact, stdlib-only; the PNGs are
committed evidence.)
