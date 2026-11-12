# Evidence: the U3-variant multi-part container reading (stage 7, 2026-11-12, #34)

Bounded structure-decode ticket (dispatch-recipes template, G6 stage 7):
the 93 walk-mismatch composite stores the stage-6 raw-array law leaves
fail-closed (84 start-unpinned / 6 weak-fit / 3 pool-unabsorbed —
`stage6-raw-trigger-probe.csv`).  The standing hypothesis tested: the
list-node payload is a MULTI-PART container — the P1t layout repeating
after the header — complementary to the stage-5 per-rep law (which
handles multiple pool groups + list NODES, not multiple parts inside
one node's payload).  Anchors: ccbb7862 (the 4a note's no-fit open) and
the census stores.  Analysis only — src/ untouched.

Labels: **fact** = byte-measured on the corpus by the committed script;
**inference** = derived, reasoning shown; **unknown** = open.
Below-bar claims (fewer than 3 files) are labeled **candidate**.

## The reading that was tested (and what the bytes say)

The committed decoder (`scripts/triage/multipart_container_decode.py`,
output `multipart-container-files.csv`, one row per store) parses each
payload as:

    [node header][token ff ff 02 00 01][count1 P1g][count2 P1g]
    [4-byte post-count field]
    [PART 1: count1 x f32 (x,y,z) stride 12 — the raw-array packing]
    [sub-sections: edge sub-nodes, vertex sub-nodes, ...]
    [trailer: f32 tolerance + 00 04 02 0a + P1g count]

- **Node header + token + counts** (fact, 93/93): the token sits at
  payload offset 29 on every store; count1 (elem_decl) and count2 are
  P1g counts (1 B, `ff` escapes to u32le — little-endian).  count2 =
  count1 on 47/93; the rest differ (e.g. 88ad0be6 86/140, 12dc542e
  1870/1780, 86205bfb 13269/672) — c2 is NOT always the element count.
- **The 4-byte post-count field** (fact, 93/93, byte values at
  [counts_end, +4)): `00 00 00 00` x58, `00 00 00 01` x19,
  `01 00 01 02` x10, `20 00 00 00` x5, `01 00 01 01` x1.  NOT a
  discriminator by itself: walk-OK stores also open with `00 00 00 00`
  (their zero block).  The 4a note's "tail field" observation (`00 00
  00 01`, and abacf110's `01 00 01` 3B variant) matches the x19 + x10
  classes; semantics stay open.
- **PART 1 as count1 flat triples** (fact, 11/93): all-nice under the
  exporter's finite predicate (|v| < 1e9 — the raw scan's 1e-6 floor
  rejects real near-zero coordinates here: 7d27c73d carries z =
  -1.19e-14, dd610ca5 x = 9.4e-15), x-ascending >= 0.98 on 9/11, and
  the pool re-lists VERBATIM in the region on **6/11** (f21255ac 590/590,
  4d2a06a6 8/8, 7d27c73d 8/8, d51eb38c 5/5, dd610ca5 8/8, f432a0be
  4/4).  The region ends byte-adjacent to the next section (no FF
  trail-escape — exactly the raw law's start-rule rejection).
- **PART 1 as count1 flat f32 PAIRS (8 B)** (fact, 25/93 all-nice; 14
  of them where the triple reading fails: 17930bab, 17dca565,
  1b0eef98, 219c099e, 38d65967, 58ed8b28, 6c6a2e9f, 802a6207,
  86205bfb, 8e8500b1, a722b491, abacf110, ccbb7862, e42e3805): the
  stride-12 scan of a pair array stays nice for exactly (2/3) x count1
  triples — the census's "junk region" break offsets re-measure as
  8 x count1 bytes (e.g. a722b491: 1,620 triples = 19,440 B = 8 x 2,430
  exactly).  This is the stage-3b note's "float-pair data" observed
  directly.  Absorption fails under every axis-projection reading
  (best (x,y) hit 11,495/34,495 on 17930bab, most stores 0) — the
  pairs are NOT pool projections (fact, 14/14).
- **Edge sub-node** (candidate — 2 files, below the 3-file bar):
  `04 04 ff ff` + 4 B sub-header + u16be group count + that many
  `02 <n> <n u8 refs>` polyline groups (the stage-2a POLYLINE law
  inside the payload).  Parsed exactly on the twins 81ad336b /
  e23423d6: 11 groups each, matching the declared count byte, refs all
  < count1.  Present somewhere in 7/93 payloads (7d27c73d carries six
  8 B `30 04 04 ff ff ff d2 d2` records — semantics open).
- **Vertex sub-node** (candidate — 2 files for the re-listing; presence
  fact on 7/93): `04 ff ff` + 4 B post-count field + kind byte + count
  byte + count x (`05 08 01` + 12 B f32).  On 81ad336b / e23423d6 the
  declared count (0x0b = 11) matches 11 records exactly and all 11
  re-listed points are verbatim PART 1 region points.
- **Trailer** (fact as a byte pattern; semantics unknown): f32
  tolerance + `00 04 02 0a` + P1g count.  Parsed at the scan level on
  31/93; the SAME pattern closes walk-OK payloads (0018baa8 `... 00 04
  02 0a 50`, 026d6726 `cd cc 4c 3d | 00 04 02 0a 08` = f32 0.05) with
  store-variable tolerances (0.2, 0.05, 0.01) — it is the U2 trailing
  structure's tail, not a U3 discriminator.
- **The strict P1t-unit chain is REFUTED** (fact, 0/93): a chain of
  self-consistent units (zero block -> 2-bit table -> P1g count ->
  region, the table's shape walk consuming EXACTLY the declared count,
  the region all-nice, unit k+1 starting at region end) parses from the
  payload start on ZERO of the 93 stores.  Dated correction: the
  census's "second-layout probe fits structurally on 41 stores"
  (`residue-family-census.csv` second_layout_ok/second_region_ok, 31
  True/True + 13 count-0) does NOT survive the all-nice + exact-walk
  validation — the loose probe read in-bounds-but-junk regions at a
  table size fixed to ceil(count1/4).

## The verdict that matters: the measured split of the 93

(fact, `multipart-container-files.csv`; unexplained stores named per
store there — columns verdict / unexplained_spans / note.)

| reading | stores | absorbed pool | notes |
|---|---|---|---|
| container-TILED (part 1 fits, every remaining byte a parsed section or trailer) | **1** (f21255ac) | 590/590 | the one store the stage-6 start rule cost the scan's best-rate reading; the container reading recovers it with zero unexplained bytes |
| container-PARTIAL (part 1 fits all-nice; unexplained residue after, named) | **10** (4d2a06a6, 7d27c73d, 81ad336b, 948aa851, cb49f9f4, d51eb38c, d696356b, dd610ca5, e23423d6, f432a0be) | 5 of 10 (plus f21255ac = 6) | the twins 81ad336b/e23423d6 parse their edge+vertex sub-nodes exactly (11 groups, 11 records each) and still leave ~3,044 B unexplained |
| float-PAIR reading (triples fail, count1 x 8 B all-nice) | **14** | 0 (no axis projection absorbs) | includes the ccbb7862 anchor; the pair packing is real, its element semantics are not pinned |
| unexplained by both readings | **68** | — | 32 region-junk + 36 region-overflow; 12*c1 overflows the payload on 41 (the region CANNOT be count1 flat triples), the rest break inside the count1 span |

Absorption + export ladder on the 6 absorbed stores (fact): the gated
families' references all resolve in-bounds against the part-1 element
space (max gated ref < count1 on 6/6); triangulation yields 0 triangles
on f21255ac (7 records, no exportable loops), 4d2a06a6 and 7d27c73d (no
records), and real triangles on d51eb38c (70), dd610ca5 (160),
f432a0be (212).

## Composition with the per-rep absorption law, and the ceiling

- The stage-5 per-rep law composes NATURALLY on top of the container
  reading where it holds: the k-th pool group re-lists in a part
  region, absorption per part, disjoint element spaces, per-rep
  triangulation.  No new absorption machinery is needed (inference).
- **Projected export ceiling** (INFERENCE, not a fitness projection):
  the container reading + absorption + the refs gate gives **<= +6
  composite exports** (the 6 absorbed stores, all baseline
  undecoded-variant rows): 3 with triangles (d51eb38c, dd610ca5,
  f432a0be), 3 vertices-only/empty.  At the stage-6 raw family's
  measured L2 share (15/28 passes, 13 empty-mesh) that projects to
  roughly **+2-3 L2 gate passes** on dev (dev 886 -> ~888-889 of 1,381;
  the bar is 1,105 — +219 to go).
- **Verdict on the lever**: WEAK.  The multi-part container reading as
  hypothesized does NOT materially move the 80% bar.  The 68 unexplained
  stores are the mass, and their packing (mixed-write float streams —
  the region breaking at 8 x count1 bytes and re-filling the payload)
  stays the open question worth more than this lever.  Recommended
  priority stays: E0 (<= +24, zero regression risk) before this.

## If integrated anyway: the falsifiable test (declaration, pre-run)

Trigger ONLY where (a) the table walk raises with the census family
signature AND (b) the stage-6 raw-array law rejects (start-unpinned /
weak / unabsorbed) AND (c) the container part-1 region fits
(12 x count1 <= payload - counts_end - 4) all-nice AND (d) the pool
absorbs verbatim in that region AND (e) gated refs stay < count1.
Declared expected delta (external-changeset gate rule,
dispatch-recipes.md):

- D1: **+6 composite exports** (the 6 stores above — all dev, verified
  from the probe CSV: 4d2a06a6, 7d27c73d, d51eb38c, dd610ca5,
  f21255ac dev; f432a0be dev), all from baseline undecoded-variant
  rows, 0 replacements.
- D2: L2 split **declared from the measured triangulation**: 3 pass +
  3 empty-mesh (0 not-manifold measured at the candidate parse).
- D3: held-out 0 movement (all 6 dev).
- D4: the other 87 trigger stores keep undecoded-variant; details gain
  the container gap; 0 error-class changes elsewhere.
- D5/D6/D7: walk-OK + per-rep + unabsorbed rows byte-identical;
  undecoded-variant 225 -> 219; 0 lost exports, 0 lost passes; replay
  digests identical on every baseline-exported row — a violation =
  STOP.
- D8: performance: the container region check is one linear pass per
  walk-failed store; no explosion expected (inference).

## Named opens (per store, all 93)

1. The 68-store packing: the region is a mixed-write float stream (the
   8 x count1-byte structure on the 14 pair stores; count2 x relation
   open); the exact write-shape law is unknown.  Named per store in the
   CSV (verdict region-junk / region-overflow + spans).
2. The 10 container-partial stores' unexplained spans (named in the
   CSV) — the sub-sections beyond the parsed edge/vertex nodes.
3. The tail field's semantics (5 byte-value classes; the 4a note's open
   carries over).
4. The trailer count's semantics; the tolerance value's meaning.
5. The edge/vertex sub-node 4 B sub-headers (`bf 8d 00 01`-class).
6. count2's semantics when it differs from count1.

## Reproduction

```
ln -s /home/alan/Documents/Repos/catpart-parser/corpus corpus   # gitignored, read-only
python3 -I scripts/triage/multipart_container_decode.py
# -> docs/evidence/data/multipart-container-files.csv (93 rows)
python3 -I scripts/triage/probe_residue_anchor.py ccbb7862      # the anchor's census anatomy
```

Committed artifacts: `multipart-container-files.csv` (per-store), the
claims ledger `multipart-container-claims.csv`, this note.  The decoder
re-uses the committed locators (`classify_residue_family.locate_payload`,
`composite.LIST_TOKEN`/`read_count`) — no law re-derivation beyond the
sections stated above.
