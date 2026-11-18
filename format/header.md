# 1. Outer header — bytes 0-32, and the version marker

Parsed by `catpart.header` and `catpart.version` (schema v1: `magic`,
`header_dword`, `header_dword12`, `ff8_at_16_24`, `header_dword16`,
`header_dword20`, `detected_version`).

Evidence: [2026-11-07-container-triage.md](../evidence/2026-11-07-container-triage.md)
("Outer container structure", 1818/1818 magic-verified files),
[2026-11-07-container-table-and-trailer.md](../evidence/2026-11-07-container-table-and-trailer.md)
(law H1 and the dual-region variant) and
[2026-11-08-r19-r21-differential.md](../evidence/2026-11-08-r19-r21-differential.md)
(per-line rates; data in `docs/evidence/data/header-scan.csv`,
`docs/evidence/data/trailer-scan.csv` and
[diff-r19-r21.csv](../evidence/data/differential-r19-r21.csv)).
Claim IDs are the differential CSV's IDs.

## 1.1 Header bytes 0-32

| ID | Bytes | Field | Claim | Label | Scope |
|---|---|---|---|---|---|
| HDR-magic | 0-8 | magic | `56 35 5F 43 46 56 32 00` = ASCII `V5_CFV2\0` on 1818/1818 magic-verified corpus files; 6 further corpus files (mislabeled, non-CATIA) lack it. Reported as-is by the parser; the `magic-v5-cfv2` fitness invariant enforces it. | established | all buckets V5R15-R32 + unknown |
| HDR-dword8-lt-size | 8-12 | dword8 | Big-endian uint32, always < file size (1818/1818). Law H1: on ff x 8 files it is the start offset of the `CATIA_V5 CB0001\0` tail region (page 2, tail-catalog.md). `size - dword8`: median 10280, p25-p75 9308-11694, min 3138, max 124164 — the tail catalog explains the distribution. Reported as-is. | established | corpus-wide |
| HDR-d8-plus-d12 | 12-16 | dword12 | Big-endian uint32, never `0xFFFFFFFF` (0/1818). Law H1: `dword8 + dword12 == file size` (1.000 on R19/R21) and on CB__END-ending files dword12 == trailer G (page 4, trailer.md) — the tail region's length. Reported as-is. | established | corpus-wide |
| HDR-ff8 | 16-24 | ff x 8 / dword16, dword20 | Eight `0xFF` bytes on 1672/1818 (92.0%) — the standard generation; ff x 8 is invariant on every bucket R17+ (1.000 on R19/R20/R21). The 146 exceptions are the dual-region variant: a distinct writer generation whose header continues as two more big-endian dwords — dword16 at 16-20 is the offset of an additional `CATIA_V5 CB0001\0` region in 143/146, dword20 at 20-24 has no validated model. Byte example (R16SP0 `137b897fc0c276e3`): `00 00 18 9a 00 00 11 34` where an R19/R21 file reads `ff ff ff ff ff ff ff ff`. | established (characterization) + open (dword20 semantics) | ff x 8: every bucket R17+; dual region: R15 2 + R16 12 + unknown 132, CAA repos only (B31CAADoc 142, CAA_PrjSrc 4) |
| HDR-zeros-24-28 | 24-32 | zeros | Zeros in all examined samples; bytes 24-28 are zero corpus-wide (`word24_be == 0`, 1.000 on R19/R21). Bytes 28-32 are not captured by any committed scan. | established (24-28) + open (28-32) | corpus (24-28); all lines (28-32 untested) |

The 338 `unknown`-version files are excluded from version-guided
inference but stay in the scans (map decision #4).

## 1.2 The version marker (`detected_version`)

Parsed by `catpart.version`: the primary window is the first 8 KB, the
fallback window the first 64 KB; a release token counts only when
`CNEXTINFOS` occurs within the 128 bytes preceding it (the documented
line carries it 64 bytes back). Everything else is the `unknown` bucket.

| ID | Where | Field | Claim | Label | Scope |
|---|---|---|---|---|---|
| VM-token-8k | ~0xb00-0xde0 (Phase 1 deep sample) | marker line | Plaintext line `NOTHING-CNEXTINFOS-UpdateVersion-StreamBlock-SafeEarlyBlock-StrongEarly&V5RxxSPxHFx built ` near the container-name table. Only the CNEXTINFOS-anchored `V5RxxSPxxHFxx` token is a marker: naive `V5 Rxx` patterns are a documented negative (Phase 1). Present in the first 8 KB on 1402/1818 (77.1%). | established | corpus, releases V5R15-V5R24 observed |
| VM-fallback | first 64 KB | fallback window | Files with no 8 KB match: +78 recovered in the 64 KB window — 1480/1818 (81.4%). The remaining 338 files carry no marker (median size 89 KB) and land in the `unknown` bucket. | established | corpus |
| VM-token-matches | - | token vs line | No file's token contradicts its bucket; the SP/HF suffix varies per file (content). The token appears in the first 8 KB of 97.7% of R19 and 94.9% of R21 files; the rest are recovered by the 64 KB fallback that defines `detected_version`. | established | R19/R21 differential |

Per-file version scope on every other page uses these `detected_version`
buckets (R15...R32, unknown), as measured by this marker.
