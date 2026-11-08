# 7. Cross-validation across the marked lines

Evidence:
[2026-11-08-r19-r21-differential.md](../evidence/2026-11-08-r19-r21-differential.md)
(ticket #21) and the per-claim data it is computed from:
[differential-r19-r21.csv](../evidence/data/differential-r19-r21.csv)
(78 claims), the per-release claims CSVs
([container-payloads-claims.csv](../evidence/data/container-payloads-claims.csv),
[units-names-probe-claims.csv](../evidence/data/units-names-probe-claims.csv),
[geometry-payloads-claims.csv](../evidence/data/geometry-payloads-claims.csv))
and the per-file corpus scans (`header-scan.csv`, `trailer-scan.csv`,
`container-table.csv`, `container-tree-scan.csv`, `tail-scan.csv`),
whose `detected_version` column carries the marked lines
V5R15-V5R32 + unknown.

## 7.1 The bar and the harness

- **Labels** (used on every page): **established** = rate >= 0.98 on
  the scanned set, or a corpus-wide law with zero exceptions on its
  stated scope; **candidate** = below that bar; **open** = no validated
  claim (semantics unproven / untested). Negative results that were
  measured are established (negative).
- **Acceptance rule** (Spec B): a claim enters `docs/format/` only with
  byte ranges, at least two independent files (different digests), and
  cross-version status; a field below the consistency bar is labeled
  candidate, not documented fact.
- **The harness** is the committed read-only scan scripts (stdlib,
  `python3 -I`, outputs under `docs/evidence/data/`): `header_scan.py`,
  `decode_container_table.py`, `decode_trailer.py`,
  `verify_kind_law.py`, `verify_container_tree.py`,
  `decode_tail_region.py`, `decode_container_payloads.py`,
  `probe_units_names.py`, `decode_geometry_payloads.py`,
  `version_differential.py`. Every claim on pages 1-6 is recomputable
  from these; the differential CSV is recomputed from the committed
  scans only (no corpus read needed except `--bytes`).

## 7.2 Coverage across marked lines (V5R15-V5R32 + unknown)

| Claim family | Where validated | Scope | Worst per-release rate | Label |
|---|---|---|---|---|
| Corpus-wide laws: header H1 chain, magic; table T1/T3 + anchor; trailer A/C==D/E/G + registration; kind K1; tree negative | `decode_container_table` / `decode_trailer` / `verify_kind_law` / `verify_container_tree` over all 1818 files | every bucket R15-R32 + unknown (per-file `detected_version` in the CSVs) | 1.000 (zero exceptions on the validated scope) | established |
| Tail-catalog laws (TL-*): constants, e0 laws, Y-copies, seq, end block, accounting, R1/R2, B-pointer laws | `decode_tail_region` on the 1516 main-scope files | all buckets; per-release walk coverage 0.24 (R16) - 1.00 (R25+), with W2/W3 at 100% of files in every bucket where any entry parses and R3b 0.889-1.000 per bucket | 1.000 on the validated scope (walk coverage itself 0.24) | established (laws) + open (walk coverage) |
| Payload-block claims (PL-*): C2 region rule, C3b tag34, C6 cardinality, C7 negative, C1b join | `decode_container_payloads`, 114-file sample | 13 buckets R15-R32 | C2/C6/C7 1.000; C3b 0.940 (R20, binary coincidences); C1b 0.929 (R17) | established (C2/C3b/C6/C7) + candidate (C1b) |
| Identity claims (D1/D2/D4) and negatives (D5/U2/P1) | `probe_units_names`, 108-file sample | 9 buckets R15-R24 | 1.000 (positives) / 0.000 (negatives) | established |
| Geometry claims (V1-V8): cardinality, nested store, strip records, specificity, CGM delta law | `decode_geometry_payloads`, 81-file scan | 14 buckets R15-R32 + unknown | V1/V2 1.000; V3 0.667 (R16/R23, 3-6 file samples); V5 0.5 (R18; 0/1 on the single unknown-bucket file, a small-part miss); V6 0.000 (specificity) | established (V1-V6, V8) |

The differential's **identical** verdict means the same law at the same
or indistinguishable rate on both lines; its per-claim note column
carries the small rate differences and their classification (e.g.
TL-tiling-full 0.909 R19 vs 0.789 R21 of walk-complete files — the
residual gaps carry nested sub-catalog bytes on both lines, same
phenomenon).

## 7.3 The R19/R21 differential verdicts (ticket #21)

Result **(established, 78-claim differential)**: the decoded structures
are **structurally identical across R19 and R21** — every constant, law
and framing of the header, container name table (T1-T3), directory laws
(L4-L7), kind law (K1), trailer fields (A-G), tail catalog (constants,
entry model, Y-copies, seq, end block, length accounting, R1/R2,
B-pointer laws) and the payload-block model (C2/C3b/C6/C7) holds at the
same or indistinguishable rates, most at 100%
([differential-r19-r21.csv](../evidence/data/differential-r19-r21.csv)):
**78 claims — 58 identical, 8 differs, 12 untested**.

Pairing caveat: the buckets are not repo-matched beyond one repository —
SSadayuki/B31CAADoc is the only repo holding both lines (87 R19 + 35
R21 + 69 R20). Every bucket-level rate difference below was checked
against the B31 same-repo rates before being called a version change;
three apparent differences flipped to content variation that way
(TR-C-mode-e7, TR-reg-tag-M, part of TL-walk-ok).

The 8 "differs" claims and their format-document consequences:

| Diff. ID | Structure | Verdict | Consequence in pages 1-6 | Label | Scope |
|---|---|---|---|---|---|
| HDR-dual-region | header | version-scoped constant: the dual-region header is absent since R17 (0/1004 on the pair); the corpus's 146 dual files are R15 (2) + R16 (12) + unknown (132), CAA repos only | header.md 1.1 ff x 8 row scope | established | R19/R21 buckets + R20 spot-check |
| TR-F-eq-0 | trailer | version-scoped constant: F == 0 on every file of every bucket from R19 on (1004/1004, 0 exceptions through R32); F == 1 belongs to R15-R18 + unknown | trailer.md 4.1 F row scope | established | R19/R21 buckets + R20 spot-check |
| ID-doc-name | identity block | the one clean writer-version change: `document_name` present on R15-R19 (declining to 5/16) and absent from R20 on (byte-verified at `0a64c44c`) | payload-blocks.md 5.2 version scope | established | R19/R21 buckets + R20 spot-check |
| TL-cnt-law | tail catalog | size-confounded: the cntB slot's high byte is nonzero on 33 parts >= 18.6 MB (R20 16, R21 15, R24 2; 0 on R19, whose largest file is 8.9 MB — R19 untested at that size); the count still reads cntA + 1 in the low byte (33/33) | tail-catalog.md 2.2 cnt row | established (low byte) + open (high byte) | R19/R21 buckets + R20 spot-check |
| TL-walk-ok | tail catalog | decoder-coverage difference (a statistic, not a law): 0.764 R19 vs 0.639 R21; same break families (flag stops, name stops) at content-shifted offsets; parts walk worse than products on both lines | tail-catalog.md 2.2 walk row | open | R19/R21 buckets + R20 spot-check |
| PL-C4b-u16le | payload blocks | framing statistic, driver unresolved: the u16le share collapses 0.241 (R19) -> 0.003 (R20/R21) — R19's sample files are small, R20/R21's are large parts; an equal-context comparison is new-decoding work (B6+) | payload-blocks.md 5.5 C4b row | open (driver) | R19/R21 buckets (114-file sample) |
| TR-C-mode-e7 | trailer | corpus-mix artifact reclassified as content by the same-repo pairing (B31 R19 70% vs R21 51%; povdoigt R19 0/559) | trailer.md 4.1 C-value row | established (classification) | R19/R21 buckets, B31-paired |
| TR-reg-tag-M | trailer | corpus-mix artifact: the registration tag M/N is repo-dependent, not version-dependent (B31 all-N on both lines; R21 repos disagree) | trailer.md 4.2 tag paragraph | established (classification) | R19/R21 buckets, B31-paired |

R20 spot-check (settles the change points a flip candidate could hide):

- `document_name`: R20 = 0/12 with the empty name2 form byte-verified —
  the flip happened between R19 and R20, not R19 and R21.
- cntB high byte: already present at R20 (16/189, e.g.
  `17930babf0fd01a8` cntA = 49, cntB = 5682) — it enters with the
  large-part generation, not with R21.
- F = 0 already constant at R20 (189/189); dual-region absent;
  everything else intermediate (e7 share 81.0%, walk coverage 0.603,
  reg-tag M-share 0.598 — consistent with the content classifications).

## 7.4 The untested list (12 claims — stays untested in v1)

Inherited open questions, re-scoped to the pair by B5; none is newly
blocked. Per the bounded-dispatch rule (ticket #22) they stay untested
here — decoding them is post-Phase-2 work.

| Diff. ID | Untested claim | Why | Label | Scope |
|---|---|---|---|---|
| UT-dual-dwords | dword16/dword20 semantics | no dual-region header on R19/R21 (0/1004); the variant is R15/R16/unknown only, where B2's two dword20 hypotheses already failed | open | all marked lines (untested) |
| UT-header-28-32 | header bytes 28-32 are zero | no committed scan reads bytes 28-32 (header-scan.csv carries bytes 24-28 only); untested on every line | open | all marked lines (untested) |
| UT-F-nonzero | trailer F = 1 / F = 2 semantics | F is 0 on all 1193 R19/R20/R21 CB__END files; nonzero F occurs only outside the pair | open | all marked lines (untested) |
| UT-reg-tag-meaning | meaning of the registration tag M vs N | both values occur on both lines and the split is repo-dependent within one release (R21: dolganin 30 M/63, huanhuan233 15 M/62); no byte-level model distinguishes M from N files | open | all marked lines (untested) |
| UT-cnt-high-byte | cntB high-byte semantics on large parts | the value is open everywhere; the 33 affected files are >= 18.6 MB and R19's corpus max is 8.9 MB, so an equal-size comparison is impossible in this corpus | open | all marked lines (untested) |
| UT-tail-var8 | the 8 file-dependent tail-header bytes (+11..+19) | file-dependent on both lines with overlapping value sets (256-distinct-byte samples); no version-scoped model exists | open | all marked lines (untested) |
| UT-e0-M-driver | what sets M (the entry-0 length quantum 86 + 20k) | the law holds 100% on both lines; the driver (name0 content/length?) is open | open | all marked lines (untested) |
| UT-reg-others | what distinguishes the trailer's B-target registration block from the other identical-format occurrences | the 41-byte pattern occurs 3-22 (R19) / 3-20 (R21) times per file with no distinguishing bytes known | open | all marked lines (untested) |
| UT-tag-0x55 | the tail-header tag 0x55 | occurs only on the 8 no-trailer unknown-version files; absent from R19/R21 (tag is 0x4e on 100% of both lines) | open | all marked lines (untested) |
| UT-osmx-cb0001 | whether every OSMX / CB0001 region end is a real stream header | the region rule byte-verifies boundaries only (B3 open question 2); no version-scoped test exists | open | all marked lines (untested) |
| UT-u32le-subformat | the u32le attribute-string sub-format inside stream regions | candidate framing only (C4/C4b); no per-version model to test | open | all marked lines (untested) |
| UT-strip-semantics | strip-record primitive semantics (triangles vs polylines, vertex pool) | the grammar is a byte-level fact on both lines; the semantics are inferred and need a controlled decode pass; not version-scoped | open | all marked lines (untested) |

## 7.5 Corrections recorded in v1

Corrections and precisions the evidence chain produced (recorded, not
massaged — the dispatch hard rule):

| Was | Now | Source |
|---|---|---|
| the writer registration block(s) the trailer's B pointer targets, framed as tail content (B2 ticket) | B < dword8 on 1556/1556 — the block is a payload block; the tail merely names its region | B2 |
| "constant 0x000000e7 pair, semantics unproven" (Phase 1) | C == D == the final region record's length, stored twice by the xrec form; the value is file-dependent | B2 |
| "0x000000e7 on most R19/R21 parts" (B1 mode) | corpus-mix artifact: the share follows the repo mix (povdoigt R19 0/559; B31 R19 70%; B31 R21 51%) | B5 |
| "0x4e on most R15-R18 and R21, 0x4d on most R19/R20 and R23+" (B1 tag reading) | repo-dependent, not version-dependent (B31 all-N on both lines; R21 repos disagree) | B5 |
| "the count field exceeds one byte" (B2 cnt exceptions) | the count still reads cntA + 1 in the LOW byte on 33/33; only the high byte's meaning is new territory | B5 |
| "the 146 files without ff x 8 are an open question" (Phase 1) | an R15/R16/unknown generation (CAA repos only), absent from every bucket R17+ | B1 + B5 |
| "156 ff x 8 files without CB__END (all-zero tails)" (B1) | the zero region is the tail END; the tail start carries a normal catalog without end block/trailer | B2 |
| "per-file structured tail of ~9-12 KB" (Phase 1) | a region catalog whose length (dword12) and record count (cntB) the header states | B2 |
| "+12-byte Copia pair" (Phase 1) | +18 on size, dword8 and B; the quoted `0x2b80` is G/dword12, unchanged | B1 |
| early model `f1 == 5*idx + 11` | f1 is a per-row stream value; the corpus law is the directory join D1 | B1 |
| f3 `0x00040001` described as "the AppliCont row" (1441 rows) | 0x00040001 holds 1441 rows: 1198 AppliCont + 243 others; AppliCont also sits in 0x00030001 in 235 files (weight 11) | container-tree note |
| R3 tiling validated on walk-complete files (mostly small) | does not extend to the large-file stream bulk (resync walk; deep-sample correction) | B4 |
| B3 inference "the stored name is the save-time name; not verified" | measured: equals the current basename 37/40; the 3 exceptions are renamed files keeping the save-time name | C3 phase A |

## 7.6 Reproduction

    python3 -I scripts/triage/version_differential.py                 # differential CSV + summary
    python3 -I scripts/triage/version_differential.py --repo SSadayuki/B31CAADoc   # paired view
    python3 -I scripts/triage/check_format_claims.py                  # claim hygiene of pages 1-6
