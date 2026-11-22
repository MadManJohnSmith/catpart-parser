# W10 marathon progress (not-manifold tail of W1-B) — round v1

Branch `marathon/w10-notmanifold-tail`, base 11a7230 (W1-B's
multi-region law). Worker W10, 2026-11-22. Bench state dir (not
committed): `~/.local/state/catpart-parser/w10/`. Every figure traces
to the committed artifacts named below.

## The residue, measured (not the brief's 29/5/6)

`docs/evidence/data/marathon-w1b-multiregion-claims.csv` (W1-B, 757
rows) leaves **40 not-manifold = 27 still-broken + 10 single-node + 3
head-record declines**. The brief's composition (29/5/6) named the
projection classes, not the post-landing classes; all work below keys
on the CSV.

The three hypotheses re-scope once measured:

- **U2 (head-records) is a container family, not a guard bug.** Every
  declined head window carries records that sit INSIDE the payloads of
  walk-FAILING token nodes (LS-Valv-75's three 0x4A records live
  inside the 42,020 B / 39,374 B node payloads whose regions fail the
  P1t walk; BW-chain-vertical carries 30+ failing 304-element period
  nodes). The failing nodes' layouts decode under no table-start shift
  0..8 (probe `probe_u2_variants.py`), carry exactly one LIST_TOKEN
  with no decodable sub-region (`probe_container.py`), and their
  `00 00 00 01` post-count bytes mark a second layout family (the
  codebase's named U3-variant residue). Prepending the head records to
  rep 0 — the only attribution the committed law could express —
  BREAKS the one part whose merge would otherwise adopt:
  LS-Valv-75's 3-rep reading is manifold with 0 degenerates
  (646 triangles), prepending yields 11 degenerates and a
  not-manifold mesh (`probe_u2_adopt.py`). LS-Muzzle and
  BW-Proa-A01B75 fail the adoption gate regardless (36 / 58-74
  degenerate per-rep emissions). **Negative with reopening**: a decode
  law for the `00 00 00 01` container family is the prerequisite;
  the head guard itself stays untouched.
- **U1 (per-rep seam) was blocked by a probe bug, then measured.** The
  27 still-broken parts are NOT head-guarded (an earlier probe
  mis-read `parse_strip_records`' ``(records, n)`` tuple as truthy —
  corrected). The per-rep seam ceiling (`probe_u1_ceiling.py`):
  arming the primary-loop seam per rep with the MERGED mesh's area
  reference makes **10 of 27** adoptable (manifold + degenerate-free):
  MB-Cargo_torp_down45 (21 sliver drops), MD-cylinder head-A1/B2/B4
  (6/4/4), MD-hatch_down_31 (7), ST-timon-Up (6), MD-Exhaust
  manifold-A1 (2), MB-base-tubes-YR / MB-toilet-02 /
  VM-pipe-gas-flow-up-YR (1 each). The precedent the reopening
  criterion demanded is measured on committed artifacts: **138 of the
  270 multi-node corpus passers carry `primary-loop-manifold-skip`
  drops** (the W1-era baseline CSV joined with W1-B's multi-node
  census) — passing siblings with the same structure whose pass
  depends on the 1%-of-whole-part-area sliver rule.
- **U3 (single-node) splits in two.** The ntu quartet
  (ntu-57/57YL/58/58YL) is the stage-8 leading-zero-table family: its
  12 period nodes per part carry >= 16 leading full-write slots, the
  committed layout skip overshoots INTO the table, and the committed
  extent law (`_table_decode_extents`) recovers the unique walk-exact
  extent (write_count == the table's word demand, 128 words for 44
  elements). The other six (MB-handwell-trpcgK, VM-Hydraulic_25,
  MD-charging generator-A1/A3/B2/B4) decode under no (element_count,
  shift) candidate coherent with their declared counts
  (`probe_bruteforce.py`) — another structure, reopened unnamed.

## The laws (units landed)

1. **The multi-region node scan's extent recovery**
   (`_region_decode_with_extent` / port `region_decode_with_extent`):
   a token node whose primary walk fails gets the committed stage-8
   extent law as a second chance — the unique walk-exact extent is
   recovered, zero or several stay declined (fail-closed), and the
   recovered reps are named in `multiregion_extent_reps`. `layout()`
   is untouched: the corpus census (`census_zeroblocks.jsonl`, 757
   parts) finds **21,614 walk-exact nodes, exactly one with more than
   one leading zero block** (ntu-58YL's 3-block node, which walks
   exact) — a one-block layout law would have flipped that node, the
   scan-scoped fallback cannot (it only runs on walk failures).
2. **The per-rep seam second chance** (`_decode_multiregion`'s
   two-pass emit, port `mr_emit_reps`): on a merged mesh the strict
   reading does not resolve, every rep re-emits with the primary-loop
   seam armed at `PRIMARY_LOOP_AREA_REL` of the MERGED mesh's area —
   the store-level law's reference semantics (#34: a rep-local sliver
   is compared against the whole part) — and stands ONLY where the
   armed reading is itself manifold and degenerate-free; any other
   outcome keeps the strict emission byte-for-byte. The strict
   reading's adoptions (W1-B's 251 + every passer) never reach the
   second pass, so their decode cost and bytes are unchanged.

## Measured effect (Submarino snapshot, 757 parts, the W1 probe)

The A/B bench rows: `~/.local/state/catpart-parser/w10/out-w10-ab/`
(not committed; the residue rows are committed as
`docs/evidence/data/marathon-w10-tail-claims.csv`, 40 rows, one per
not-manifold residue part, with the per-part cause and the ceiling
probe's sliver-drop counts).

- **L2 pass 683 -> 703 (+20)**, rate 90.22 % -> 92.87 %
- **not-manifold 40 -> 20 (-20)**: the 4 ntu parts through the extent
  recovery (12 period reps each, e.g. ntu-57: 708 triangles,
  boundary 316) and 16 still-broken parts through the per-rep seam —
  the ceiling probe's 10 adoptables plus 6 more whose armed reading
  resolves under the full entry pipeline (the entry seam, dedup,
  relist and dup-pin weld all run before the fire gate; the probe
  measured the bare multi-region reading only)
- degenerate-triangles 19 -> 19 unchanged; empty-mesh 13 -> 13
  unchanged; the 2 `l2_status=fail` rows (no failed_check — the
  export-error era rows) unchanged
- **0 new degenerate-triangles, 0 class changes, 0 timeouts** (a
  class-change census over all 757 rows: the only flipped class is
  not-manifold -> pass)
- the remaining 20 not-manifold: 13 still-broken whose armed reading
  does not resolve (kept over-uses are real surface, or the reps emit
  degenerates), 6 single-node of the unnamed brute-force negative
  family, 1 head-record decline of the container family (LS-Valv-75;
  LS-Muzzle and BW-Proa are counted in the still-broken set — their
  merge carries degenerates regardless of the head records)

## Parity, tests, gates

- Python tests: `test_composite_multiregion_extent_recovery_adopts_leading_zero_table`
  (a two-period body whose period 1 opens with 16 full-write slots —
  the x-interleaved box remap keeps the records' planarity — adopts
  with `multiregion_extent_reps == 1`); the W1-B twins unchanged.
- Port twins: `multiregion_extent_recovery_adopts_leading_zero_table`
  constructs the same bytes function-level (the twin's
  `mr_node_payload` write count now excludes skip-slot words — the
  Python fixture's law); `region_decode_with_extent` +
  `mr_emit_reps`/`mr_adoptable` mirror the scan fallback and the
  two-pass seam.
- **Parity PLY byte-identical Py=Rust, 11/11 parts** (sha256-compared,
  the release `fidelity-cli export` vs the Python seam): the 4 ntu
  parts, 5 seam-adopted representatives (MB-Cargo_torp_down45,
  MD-cylinder head-A1, ST-timon-Up, MB-toilet-02,
  VM-pipe-gas-flow-up-YR) and the 2 W1-B controls
  (MB-Frames-middle-centr-YL, BW-Eske-33dZ-YR — the passers'
  bytes unchanged).
- Gates: ruff clean (repo-wide); pytest **947 passed / 21 skipped**
  (1 process; the skips are environmental — playwright absent, one
  corpus-relative fixture); cargo test **230 passed**; cargo fmt
  clean; clippy -D warnings clean (the gate's lib invocation); the
  wasm32 build (plain cargo, NOT wasm-pack) compiles.
