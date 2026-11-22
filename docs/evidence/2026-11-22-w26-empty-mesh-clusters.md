# W26: empty-mesh structural clustering + the top non-U3 carrier cluster (2026-11-22)

**Worker**: W26, wave 4, branch `marathon/w26-empty-mesh-clusters`, base
`676537e`. Population: the 211 `failed_check == "empty-mesh"` rows of
`fitness/reports/20261121T103944Z-d2c9ff.json` (207 dev + 4 held-out).
Bloque B6: cluster the population by stable binary signature, rank by
`files × bytes`, attack the top cluster that still has undecoded
carriers. Probes (read-only, selftested): `scripts/triage/w26_empty_mesh_clusters.py`
and `scripts/triage/w26_residual_carriers_probe.py`. CSVs:
`docs/evidence/data/w26-empty-mesh-{clusters,cluster-ranks}.csv` (211 /
102 rows) and `w26-residual-carriers.csv` (55 rows) plus
`w26-empty-mesh-claims.csv` (W26-01..14). **No `src/` or `port/` module
is touched** (the W13 precedent for a no-runtime negative).

## 1. The clustering (W26-01..06; verified against W2)

Signature = joined writer version, sorted container table
(`store.valid_blocks`), located span tags, store shape (pool points /
composite space / in- and out-of-span candidate buckets) and opcode
presence with coarse magnitude buckets (facet markers 0x42/0x4a/0x4c,
curve families, the W13 `d2 d2 50/51` and `30 04` families) — magnitude
never splits a class (buckets `0 / 1-99 / 100-9999 / >=10000`), and the
version is joined, not hashed, so a re-detect cannot split a structural
cluster. Cluster = exact signature match. **211 files → 102 clusters.**

The census columns reproduce the committed W2 baseline exactly on all
211 rows (pool points 95,819; in-span candidates 178,240; accepted
in-span records 6,206; spans 124; composite-space files 19) — the join
is sound before any ranking is read.

Ranked by `files × bytes`:

| class | files | bytes | share | note |
| :--- | ---: | ---: | ---: | :--- |
| pool+facet (U3) | 10 | 247,163,403 | 89.0% | **C01** is `PalmDown5motors2` alone (237,851,950 B) |
| zero-carrier | 107 | 14,710,337 | 5.3% | 39 clusters; the structural floor |
| curves-only | 73 | 9,665,285 | 3.5% | in-span `33 32`/`33 37` wireframe |
| outside-only | 10 | 3,562,332 | 1.3% | 46 strip-shaped regex hits, no spans |
| pool-only | 9 | 1,836,324 | 0.7% | 7 non-U3 (36 points) + 2 U3 |
| facet-only | 2 | 658,449 | 0.2% | C55 + C62 |

The 12 U3-flagged files (the W2b element-region oracle's eligible
stores) hold 247,449,426 B (89.1%) and 95,783 of the population's 95,819
pool points.

## 2. The skip: the top cluster is the refuted U3-variant (W26-02, W26-14)

The brief's skip rule fires on rank 1: `C01` (and the whole `pool+facet`
class plus the 2 U3 `pool-only` members) is the U3-variant composite
family whose element region does not decode under any committed law —
W2 spent its two mapping attempts (pool/lex/shifted mappings refuted by
the stored-normal oracle at ≤ 36% agreement) and W2b spent the direct
indirectory oracle (negative, 12 stores). The family's attempt budget
is exhausted; attacking it a third time would break the
2-attempts-per-family rule, so the top cluster is **skipped and
documented**, and the next-ranked cluster with carriers is attacked.

## 3. The attack: C06 (outside-only), then the whole non-U3 residue (W26-07..12)

**C06** (4 files, 1,074,474 B, 15 candidates outside all located spans)
is the top non-U3 cluster by `files × bytes`. Its carriers turn out to
be the visible part of a population-wide residue: every non-U3
unresolved candidate the committed facet scan leaves — 55 across 11
outside-only/facet-only/pool-only clusters (49 outside-span + 6
in-span; markers 0x41/0x44/0x45/0x46/0x47/0x48/0x49/0x4a/0x4c/0x4e).

Attempt 1 (facts + the pairing law, one family):
`w26_residual_carriers_probe.py` extracts per-candidate byte facts and
applies the **strict** W13-#2 reopening law — a declared mult-3 count N
backed by a contiguous u16le run of exactly N words, every word < N,
non-zero (the W2b F5 inter-record shape). The loose "long in-bounds
run" reading is vacuous on stream bytes (every u16 word is < 65535) and
is not used. **0/55 fire** — no candidate indexes an external array.

Attempt 2 (inline geometry, second family): the facts run doubles as
the census for an inline-geometry law. C06's 0x41/0x45 opener class (10
records, 3 files) carries per-file opener constants (`2562`/`10`) and
**0** inline f32 zones — object-ID tables, not geometry. C69's 0x45
family (8 records at a regular 4,294-B stride, declared `64`/`254`)
and the 18/55 (32.7%) extended-header `0xea`-ty class (0x46/0x48/0x4e;
f64-field object bodies with ID refs) are object-stream content with no
declared arrays. C55's five in-span 0x4c hits front a 127,771-B inline
f32 position table (stride-12 grids with constant y = 20.0 — the
CAAPriChangePattern instance grids) with **no connectivity tail**:
vertices-only content, so `triangle_count` stays 0 and `empty-mesh`
cannot flip even under a perfect point decode; the committed law
correctly refuses the header (no counts/refs follow it).

**Outcome: NEGATIVE measured, both families closed within budget.**
Flips 0 (nothing wired — there is no honest triangle carrier outside
U3 to wire a law for); regressions 0 by construction; the L2 verdict
vocabulary is untouched.

## 4. Rates

- Clustering: 102 signature classes / 211 files; top-class concentration
  89.1% of bytes in the U3 family.
- Zero-carrier floor: 107/211 files (50.7%) carry nothing any committed
  law can pair or walk.
- Non-U3 pool carriers: 36 points on 7 files, all composite-index space.
- Strict pairing law: 0/55 candidates fire (W13-#2 stays unfired).
- Inline-geometry census: 0 geometry zones on the C06 opener class;
  6-7 nice-f32 windows per C69 0x45 record (object fields, not arrays);
  C55's position table has 0 connectivity words.
- Flips: 0/211 (0 wired); regressions: 0.

## 5. Reopening criteria

1. **U3 element-region decode** (the W2/W2b criteria unchanged): lands
   the only triangle carriers in the population — 89.1% of bytes,
   95,783 pool points, 6,206 accepted records, plus W2's measured
   counts-less 0x49 assembly waiting in `brep_mesh.py`.
2. A future sample whose outside-span candidates show a declared
   mult-3 count with an exact-count in-bounds u16le run (the strict
   law this round measured, committed in the probe): the pairing law
   is then writable against the W2b F5 grammar.
3. A connectivity tail appearing after an inline position table (C55's
   shape plus refs): re-measure the 0x4c-inline family as a strip
   variant against the committed strip grammar (W17's lane).

## 6. Verification

- `w26_empty_mesh_clusters.py --selftest`: 6 pins (buckets, carrier
  vocabulary edges, W13 counters, signature determinism).
- `w26_residual_carriers_probe.py --selftest`: 9 pins (count window,
  run counter, ASCII tail, stride detector with the zero-block guard,
  the four classes, fail-closed `unclassified`).
- `tests/test_w26_probes.py` runs both through `main(["--selftest"])`
  so the pins stay gate-covered.
- Census verification: all 211 rows reproduce the W2 baseline's pool /
  candidate / record counts exactly (see §1).
