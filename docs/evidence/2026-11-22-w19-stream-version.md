# Evidence: the stream-version census — no compressed sub-stream, no alternate stream header; the GE-V7 tags generalize to a generation-string ladder (W19, B9)

**Date**: 2026-11-22
**Status**: COMPLETE — the B9 question is answered at the stream level on the
whole part population: 0 verified compressed sub-streams, no alternate
writer/stream header, and a measured taxonomy of the version-like
generation strings the CGM stream actually carries. Two new byte laws
established (the SP5HF0 auxiliary-header `dword12` law; the tag
vocabulary); one pointer law declared open with a reopen criterion.
**Target**: the B9 brief — do recent (V5-6R2020+) or old files use another
version header or a compressed sub-stream that the scanner skips because
it expects a fixed magic (`V5_CFV2\0` / `CATIA_V5 CB0001\0` / the pinned
pool/facet signatures)?
**Method**: read-only byte census over the corpus,
`scripts/triage/stream_version_probe.py` (stdlib + the committed
`catpart.geometry.store`/`stream_version` modules; deterministic sha256
order, one mmap at a time, ~40 min). Per file: the shipped locator walk
(stdcont → xdoclink → seebody → other-container) recording spans and
rejections; three scan territories — every `CGMGeom` and `CATPrtCont`
block region (B3 boundary rule) and every located store body — scanned
for framed version-like strings (`[u32le L][L ASCII]`), compression
signatures (zlib FCHECK law, gzip/bzip2/xz/raw-LZMA/lz4/zstd/snappy
images) and fail-closed verified streams; the block writer tag
(`36 08` + 6 printable) at the pinned +112 offset and anywhere in the
first 512 B.
**Data**: `data/stream-version-files.csv` (4,314 rows: one per file ×
territory), `data/stream-version-tags.csv` (125 texts × major),
`data/stream-version-claims.csv` (SV-01..SV-16). Read-only over the
corpus; `src/` gains only the classification module
(`src/catpart/geometry/stream_version.py`, ported 1:1-scan to
`port/src/geometry/stream_version.rs`), wired nowhere in the exporter.

Labels: **fact** = byte-measured here and reproducible from the CSVs
or the probe rerun; **inference** = interpretation, reasoning shown;
**unknown** = open, carried with a reopen criterion.

---

## 1. Executive summary

| Question (B9) | Measured answer |
| :--- | :--- |
| Does any file carry a compressed sub-stream the scanner skips? | **No.** 0/1,438 files carry one verified compressed stream (SV-02) under the fail-closed eof law, across the CGMGeom regions, the `CATPrtCont` regions and the store bodies. zlib candidates occur only as payload coincidences; the raw-LZMA row is signature noise, counted and never verified (SV-04). |
| Do recent (V5-6R2020+) or old files use another version header? | **No header VARIANT exists.** The outer `V5_CFV2\0` magic is 1,818/1,818 (HDR-magic, unchanged); the writer tag is `FINJPL` on **every** scanned block, corpus-wide, all majors R15-R32 + unknown (SV-10); `2X-0` — GE-V7's second tag — has **zero** corpus-wide occurrences (SV-08). |
| What IS the stream-level version content? | A **generation-string vocabulary**: the `[u32le L]"N-0"` ladder (N = 1..29) and the reversed `0-N` family (N ≤ 59) inside the CGM dictionary records — 125 distinct texts corpus-wide (SV-05), concentrated on R21 (137,691 ladder occurrences) and absent on R15/R16/R18/R23/R24+ (SV-06). Presence is content-dependent (dense CGM dictionary files), not writer-version-deterministic (SV-07). |
| Are there stores the locator cannot open for header reasons? | 17 census-level rejections (`malformed-store-header`), **all V5R19SP5HF0**, all on auxiliary (non-export-path) blocks; every one of the 17 files opens via its real store (SV-12/SV-13) — zero file-level flips. Their headers carry a **new law**: `dword12` = the file's document-catalog tail length, validating N6 17/17 (SV-14); `dword8` stays an unknown pointer (SV-15). |
| The no-store population | 121 files locate no store in any probe family — all `detected_version=unknown`, the bag-rep population the missing-store note closed (SV-16). Unchanged by any stream-level law. |

Population: 1,438 `kind=part` `magic_ok=yes` manifest rows (the 1,442-row
report population minus the 4 non-containers), 4,314 territory rows, 0
probe failures (SV-01).

---

## 2. The compression arms (all negative, fail-closed)

The scanner's compressed-sub-stream question has three candidate arms,
each verified before any claim:

1. **zlib at territory heads** — every valid pair (CMF `0x78`, RFC 1950
   FCHECK `(0x78 << 8 | flg) % 31 == 0`) in the first 64 B of each
   territory, decompressed with the eof law (output ≥ 256 B and the
   stream reaches its own end). 0 verify.
2. **length-framed zlib** — a valid pair whose preceding u32 (LE or BE,
   at `[pair-4]` or `[pair-8]`) names the remaining span exactly (the
   two honest readings of "a sub-stream with its own length prefix").
   0 verify corpus-wide.
3. **gzip / bzip2 / xz signatures** — every `1F 8B 08`, `BZh[1-9]1AY&SY`
   and `FD 37 7A 58 5A 00` image verified with the stdlib decoders
   under the same law. 0 verify corpus-wide.

The zlib pair count is nonzero per file (payload coincidences — e.g.
file `0018baa8`'s `CATPrtCont` region carries 7 valid pairs, its store
body 4) but no candidate survives decompression: the pairs sit on
f64/record payload, not stream heads (SV-03). The raw-LZMA `5D 00 00`
row (e.g. 39 hits in one `CATPrtCont` region) is the declared
false-positive row and is never a claim (SV-04).

**Detector limits (declared)**: zlib under a CMF other than `0x78`, and
an unframed self-terminating zlib stream sitting *outside* a territory
head with no length prefix, are not discriminated by this census; a
negative here does not exclude them. lz4/zstd/snappy are signature
presence only (no stdlib decoder). The bulk-stream note's entropy
negative (BS-19: no 4 KiB window over 7.9 bits/byte on 128 no-facet
regions) is thereby extended corpus-wide *with* signature
verification.

---

## 3. The generation-string vocabulary (the GE-V7 refinement)

The framing is `[u32le L][L ASCII]` with a version-shaped text (digits,
optional `X`/`x`, 1-3 dash groups) — GE-V7's `03 00 00 00 "2-0"` image,
generalized. The scan reads the text at its **exact** length `L` (a
greedy printable match over-extends a tag followed by ASCII — the
synthetic regression is pinned in `tests/test_stream_version.py` and
the port). Corpus-wide (CGM territory): **125 distinct texts** (SV-05).

### 3.1 The `N-0` ladder (N = 1..29)

Per-major occurrences (exact, `stream-version-tags.csv`):

| major | ladder texts present | occurrences | files (top-6 bound) |
| :--- | ---: | ---: | ---: |
| R15 | 0/29 | 0 | 0 |
| R16 | 0/29 | 0 | 0 |
| R17 | 15/29 | 75 | 1 (`5de8b8fc`, V5R17SP5HF0) |
| R18 | 0/29 | 0 | 0 |
| R19 | 1/29 (`1-0`) | 117 | 5 (all SP0HF0) |
| R20 | 15/29 | 115 | 2 (`369fc90b` — the G3 soup seed; `0a64c44c`) |
| R21 | 29/29 | **137,691** | 23 |
| R23..R32 | 0/29 | 0 | 0 |
| unknown | 4/29 | 98 | 6 |

The anchor `13bb5c0c` (R21, the GE-V7 worked file) carries 6,546 ladder
occurrences in its 8.4 MB CGM region; the densest file is `50cd280f`
(R21, 21,706). The ladder lives in the CGM **dictionary record units**
(~44 B each, observed on the anchor: `0e 04 00 01 00 <seq> 0e 04 00 00
07 00 [u32le L]"N-0" 00 00 01 00 00 01 00 04 00 <u32le> …`) — a
per-record generation field, not a file-level header.

### 3.2 The `0-N` family (N ≤ 59) and the scattered `N-M` texts

The reversed family spans R18-R23 + unknown (SV-07): `0-1` counts
R19 = 523, R21 = 627, R20 = 72, R18 = 5, R23 = 4, unknown = 35; the
max N observed is 59 (`0-58`/`0-59` on R20). Triple-suffix texts
(`0-0-1`, `0-1-0`, …) and `N-M` forms (`6-6` on R20, `7-3` on R24)
occur in ones and twos; the only two store-body tag rows are exactly
those (SV-09).

**The discriminator GE-V7 hoped for does not exist as a writer-version
marker**: R24/R32 files carry zero tags, R15/R16 zero, R21 carries
137,691 — the density follows the CGM dictionary *content* (which
record families the writer emitted), not the writer generation. The
GE-V7 row stays candidate as a content discriminator; its `2X-0` arm
is refuted corpus-wide (SV-08) and its "4/44 files" scale is refined
to the vocabulary above. (Dated correction recorded here; the format
page is not edited from this task.)

---

## 4. The writer tag: one constant, a drifting offset

Every scanned block (first 512 B) carries the `36 08` + 6-printable
tag, and the text is **`FINJPL` in all 15,786 blocks, corpus-wide, all
majors** (SV-10) — a format constant, not a version discriminator. The
bulk-stream note's pinned `block+112` position is a **minority law**
(~10% of blocks; SV-11): the tag's offset drifts with the block
preamble (per-family offsets like 110/122/130/138 on one file). The
census reports both (the +112 law result and the found-offset scan) so
a future writer-tag change cannot hide behind the offset drift.

---

## 5. The 17 auxiliary store headers (SP5HF0 dual-catalog family)

The census's other-container probe family raises `malformed-store-header`
on 17 files (the named families — the exporter's actual path — raise
**zero** corpus-wide; SV-12 was measured by re-walking the corpus with
the shipped `locate_store`):

| fact | value |
| :--- | :--- |
| files / rejections | 17 files, 17 rejections, **all `V5R19SP5HF0`** (one writer build) |
| block names | CATPart 8, CameraStartupContainer 7, CATIA 1, CATTTRSCont 1 |
| header shape | `V5_CFV2\0` + ff×8 ✓ + zeros×8 ✓ (the N2 field laws HOLD) |
| `dword12` | 2,686..2,710 — equals the file's **document-catalog tail length**; that tail (from the file's first `CATIA_V5 CB0001\0`) validates the N6 laws (ends `CB__END\0`, C == D, G == length) **17/17** (SV-14) |
| `dword8` | points at no catalog under any shipped reading: not `j + d8n` (no CB0001 at the target), not `blk + d8n`, not file-absolute `d8n` (SV-15) |

Worked example (`0e4bc645f64c4f4b`, V5R19SP5HF0): header at j = 2,366
(block `CATPart` at 2,053), dword8 = 39,126, dword12 = 2,690; the
file's catalogs sit at 126,970 (document — its 2,690-B tail VALIDATES
N6) and 139,526 (outer, dword8 + dword12 = 150,588 = size). The bytes
at the pointed target (41,492) are f64-shaped geometry, not a catalog.

**Zero file-level flips** (SV-13): all 17 files open via their real
stores — 15 MESH `pass` + 2 DISPLAY `empty-mesh` in
`data/open-rate-files.csv`. The exporter never reaches these blocks
(it probes other-container only when nothing located, and something
located). The 2-attempt budget on the `dword8` pointer law is spent:
(1) the three relative readings; (2) the file-absolute reading plus
the d12-catalog relation (which produced the SV-14 law but no pointer).

**Reopen criterion (SV-15)**: the family reopens when a law derives the
document-catalog position from the auxiliary header's `dword8` (or any
other header field) and fails-closed on the 17 — or when a writer build
emits the same header shape with a pool-bearing body, which today it
does not (the dual-catalog bodies are the bag-rep payload class, and
the missing-store note measured 0 pool groups under the L-SN spans).

---

## 6. What this does and does not say

- **It says the stream level has no hidden compression and no alternate
  header generation** on this corpus: the fixed-magic scanner is not
  skipping compressed sub-streams in the CGM/`CATPrtCont`/store-body
  territories, and no recent (R32, the corpus's only V5-6R2020+ file)
  or old (R15-R17) writer introduces a stream-header variant.
- **It does not decode the CGM record stream** the ladder lives in —
  the ~44-B dictionary units, their `N-0`/`0-N` semantics and the
  unframed CGM residue stay the open territory the cgm-grid probe
  stopped at (its §7 verdict is untouched).
- **The `unknown`-version no-store population is unchanged** (121
  files): the stream-level levers find nothing there — their carrier
  is the bag-rep payload class, per the missing-store note.
- **No source was modified** beyond the new classification module and
  its port; the exporter is untouched, so no L2 rate can move.

---

## 7. Reproduction

```bash
.venv/bin/python -I scripts/triage/stream_version_probe.py \
    --corpus-root /home/alan/catpart-parser
# -> docs/evidence/data/stream-version-files.csv (4,314 rows)
# -> docs/evidence/data/stream-version-tags.csv   (125 texts x major)

.venv/bin/python -m pytest tests/test_stream_version.py -q   # 35 synthetic tests
cargo test  --manifest-path port/Cargo.toml geometry::stream_version  # 7 port tests
```

The probe is deterministic (sha256 order, one mmap at a time, bounded
verification budget of 4,096 attempts per territory); the corpus is
opened read-only. The claims CSV (`stream-version-claims.csv`,
SV-01..SV-16) is the machine-readable layer; every prose figure above
is a row there or arithmetic on rows.
