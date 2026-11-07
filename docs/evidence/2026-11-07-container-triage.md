# Evidence: first-pass container triage (2026-11-07)

Scope: all 1818 unique `magic_ok` corpus files (see
`docs/corpus-report.md`), plus a 7-file deep sample and 3 similar-file
pairs. Method: read-only byte analysis with committed scripts —
`scripts/triage/header_scan.py` (corpus-wide, emits
`docs/evidence/data/header-scan.csv`) and
`scripts/triage/deep_sample.py`. Run with `python3 -I`. Digests for every
claim are in the manifest and the scan CSV.

All observations below are byte-level facts; interpretations are marked
*inference*.

## Outer container structure

**Header (bytes 0-32), consistent across the corpus:**

- 0-8: magic `56 35 5F 43 46 56 32 00` — ASCII `V5_CFV2\0`. Present in
  1818/1818 scanned (by construction) and validated against 6 mislabeled
  files that lack it.
- 8-12: dword, **big-endian**, always < file size. `size - dword8` has
  median 10280, p25-p75 = 9308-11694, min 3138 (the 375 MB file,
  ratio 0.99999), max 124164. *Inference: length/offset field covering
  the main payload, followed by a per-file structured tail of ~9-12 KB.
  Not yet proven.*
- 12-16: small varying dword (e.g. `0x00001fa4`). Never `0xFFFFFFFF`
  (0/1818).
- 16-24: eight `0xFF` bytes in **1672/1818 (92.0%)** of files. The 146
  exceptions are an open question.
- 24-32: zeros in all examined samples.

**Container name table (plaintext, offsets ~0x7e4-0xd00 in samples):**
repeating `CATContainer` entries with names — `CATCompoundCont`,
`CATProdCont`, `CATFeatCont`, `CATPrtCont`, `CGMGeom`, `CATMFBRP`,
`CATSeeBodyCont`, `CATBRepModeContainer`, `CATStdCont`, `CATCGRCont`,
`CameraStartupContainer`, `contmeasure`, `CATSiMuGenCont`,
`CATMechProdCont`, `CATCtorProxyCont`, `CATMaterialCont`, `AppliCont`,
`V5USERID`. *Inference: named-section architecture; these names are CAA
concepts (the corpus's CAA documentation trees — B31CAADoc, CAA_PrjSrc,
CAAclean — are the in-house reference for their semantics).*

**Trailer (last bytes):** files end with ASCII `CB__END\0`
(`43 42 5F 5F 45 4E 44 00`) in **1556/1818 (85.6%)**. Preceded by a
per-file dword (samples: `0x2b80`, `0x1c2c`), 8 bytes `…000000e7
000000e7` (constant-looking across files), a `…01` dword, and zeros. In
the near-identical Copia pair below, the trailer's size-like dword grows
by exactly +12 when the file grows by +12 bytes. The 262 files without
`CB__END` concentrate in B31CAADoc ~100 KB CAA samples (all-zero tails) —
likely a different generation; open question.

**Per-file version marker (solves version detection for 81.4%):**
plaintext string at ~0xb00-0xde0:
`NOTHING-CNEXTINFOS-UpdateVersion-StreamBlock-SafeEarlyBlock-StrongEarly&V5RxxSPxHFx built `

- Found in first 8 KB of **1402/1818 (77.1%)**; extended window to 64 KB
  recovers +78 → **1480/1818 (81.4%)**. 338 files have no marker (median
  89 KB size) — open question.
- Distribution (8 KB window): V5R19SP0HF0 ×561, V5R21SP0HF0 ×322,
  V5R20SP0HF0 ×132, V5R19SP5HF0 ×67, V5R16SP4HF0 ×39, V5R16SP0HF0 ×34,
  V5R20SP5HF0 ×32, V5R18SP0HF0 ×29, V5R18SP3HF0 ×21, V5R17SP0HF0 ×20,
  **V5R24SP1HF0 ×18**, V5R21SP2HF0 ×15, V5R17SP5HF0 ×11, V5R15SP0HF0 ×11.
  Multi-release coverage V5R15→V5R24 confirmed. Spot-check: hssnadr files
  say V5R21SP0HF0 and the repo README claims CATIA V5R21 — independent
  agreement.

## Compression status (Phase 1 acceptance)

Files are **not wholly compressed** — the navigable structure (magic,
container table, version marker, trailer) is plaintext. Entropy profiles
(4 KB blocks, deep sample):

- Products and small parts: mean 3.5-6.7 bits/byte, **no high-entropy
  zone** (≥7.2) at all.
- Large parts carry limited high-entropy regions: `head.CATPart`
  (Apoloo13, 18.7 MB) has 44.9% high-entropy blocks in
  0x851968-0x16900096; `Carter de Oleo` (Motor-V6, 1.7 MB) 17% in
  0x503808-0x983040.
- First/last 16 KB are consistently low-to-mid entropy (2.7-5.4):
  structured head and footer.

*Inference: optional compressed (or otherwise high-entropy) geometry
payloads live in the middle of larger parts; boundaries appear findable
via the container table + entropy. Codec unknown.*

## Similar-file comparison — negative result with parser consequences

- `body 1 - TRABALHO MOTOR.CATPart` vs `…- Copia.CATPart` (Motor-V6;
  sizes differ by +12 B): common prefix **11 B**, common suffix **28 B**,
  first-64KB byte agreement 14.8%.
- `Case_Logo_Black` vs `Case_Logo_Blue` (hssnadr): common prefix 9 B.
- `lengua_1` v1 vs v2 (Apoloo13): common prefix 9 B.

*Conclusion: layout is not deterministic across saves — per-file fields
(GUIDs, timestamps, ordering, compression boundaries) dominate from byte
~12 onward. A parser cannot use fixed offsets beyond the 32-byte header;
it must navigate the container-name table.*

## Negative results

- No version information via naive `V5 Rxx` patterns; the marker is the
  specific CNEXTINFO form above.
- `header[12:16]` is never `0xFFFFFFFF` (0/1818).
- First-pass `strings_8k` column in an earlier CSV run was computed over
  64 bytes by mistake; corrected and re-run (this file + CSV reflect the
  corrected run).

## Unknowns / next questions

- Semantics of dword@8 and the trailer fields; the `0x000000e7` pair.
- Container-table record format (name + offsets? bounds?).
- The 146 files without `ff×8` at 16-24 and 338 without version marker.
- Codec of the high-entropy regions in large parts.
- Whether embedded tessellation exists (feeds the L3 fitness component;
  `CGMGeom`/`CATCGRCont` containers are the candidates to inspect).

## Reproduction

```
python3 -I scripts/triage/header_scan.py     # corpus-wide CSV + summary
python3 -I scripts/triage/deep_sample.py     # entropy zones, strings, pairs
```
