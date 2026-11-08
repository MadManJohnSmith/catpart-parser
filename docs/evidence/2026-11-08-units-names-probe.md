# Evidence: units and names probe — document_name adopted, unit system negative (2026-11-08)

Phase A of ticket #25 (C3: units and names extraction). Question: B3's
open question 1 — where do the model unit system (length/mass/angle) and
the displayed part/product name live? Scope per the ticket: the two
already-decoded territories only — (1) the container payload regions (B3
block/region model) and (2) the OSMX/stream territory (the main file area
outside those regions, plus the `CATIA_V5 CB0001\0` tail region from
header dword8). No other territory was opened.

Tool: `scripts/triage/probe_units_names.py` (read-only, mmap,
deterministic; reuses the B3 framing classifiers). Validation run:

    .venv/bin/python -I scripts/triage/probe_units_names.py \
        --sample 3 \
        --include-sha16 0018baa84f3bff6b,b83a2e9d09820603,f3862d22fd9025ff,01f2a48c9151197e,62aa3a4f2d11665a,803c9860f69c88f7,9ee5735167e37ac2,c110aebb4509f3cc,f0479c1606dfcf4b,67b37d06c40d6eed

Sample: 108 files, up to 3 per marked `detected_version` in V5R15–V5R24
(evenly spaced by size, B3's `pick_sample`) plus the 10 B3 step-(a) files
force-included; 9 release buckets, ~100 s wall clock. Method: framed
pattern scan (B3 framing families; printable runs of >= 2 chars, only
framed runs match) for a fixed token vocabulary — 29 unit tokens, 10
spec-tree parameter tokens (model-content context), 10 display-name
property tokens — plus the identity-block walk and the basename search.
Every hit is classified by territory: region / stream / tail. Outputs
committed here: `units-names-probe-files.csv` (per file),
`units-names-probe-hits.csv` (one row per framed token hit, capped 500
per file), `units-names-probe-claims.csv` (per-claim, per-release rates).

## Result

**The model unit system (A1): negative.** No claim validates.

**The display name (A2): negative beyond the CATIA identity block; the
identity block's save-time document name is the only name structure and
is adopted for the parser.**

Claims (rates over the 108-file sample; per-release values in the claims
CSV; label = established when >= 0.98 on the scanned set, else
candidate):

| claim | statement | rate | label |
|---|---|---|---|
| D1 | exactly one `CATIA`-named storage block per file (the identity block) | 108/108 = 1.000 | established |
| D2 | the identity block's name2 parses under the fixed walk `a0 02 00 00 00 00 34 <len> <ascii> <0x9f\|type-tag>` after name1's terminator | 108/108 = 1.000 | established |
| D3 | document_name, when present, equals the manifest basename | 37/40 = 0.925 | candidate — see D3 below: the 3 exceptions are the save-time-name rule working as inferred, not a framing failure |
| D4 | document_name, when present, ends with `.CATPart`/`.CATProduct` | 40/40 = 1.000 | established |
| D5 | the manifest basename occurs as a framed string outside the identity block region | 0/108 = 0.000 | established negative |
| U1 | file carries >= 1 framed unit-family token anywhere | 6/108 = 0.056 | negative (all hits accounted for below) |
| U2 | file carries >= 1 framed unit-family token in stream/tail territory with no drafting namespace | 0/108 = 0.000 | established negative |
| P1 | file carries >= 1 framed display-name property token (PartNumber, Nomenclature, Part1, PartBody, ...) anywhere | 0/108 = 0.000 | established negative |

## The document_name claim (adopted)

The identity block's name2, walked after name1's terminator
(`a0 02 00 00 00 00 34 <len> <ascii> <term>`; empty field is
`34 00 9f`), carries a printable-ASCII document name ending in
`.CATPart`/`.CATProduct` whenever the field is non-empty (D4 40/40).
Presence is **version-dependent**: 40/108 overall, per release
R15 8/9, R16 7/14, R17 12/17, R18 8/9, R19 5/16 — and **0/43 on
R20/R21/R23/R24**. The field is a *save-time* document name, not the
current file name: in 3/40 present cases it differs from the manifest
basename (`Geometrical Bundle1.CATProduct` with a space vs the file
`GeometricalBundle1.CATProduct`, 3 V5R18SP2HF74 products), while 37/40
match exactly. This upgrades B3's *inference* ("the stored name is the
save-time name; renamed files would keep the old one - not verified") to
a measured observation with counterexamples: the emitted field must be
reported as-is and never treated as the current basename.

## The units negative (where we looked)

- **Payload regions.** 34 framed unit-token hits in regions on 4/108
  files (cm/ft/in/kg/km/mg/mm/um as u16le/u8tag/u32le): context dumps
  show all of them are binary coincidences inside packed binary data
  (e.g. u16 value tables where `6b 67` spells "kg"; a `3f 02` byte pair
  misread as a u8 tag+len). No token occurs in a structured group; the
  same files' regions carry no unit vocabulary beyond the scattered
  tokens. This matches B3's bounded probe ("mm x2, cm x2, Pa x2, kg x3
  across the whole sample - not localized further").
- **OSMX/stream territory.** 120 framed unit hits, all in the drafting
  property store of the 2 drafting-namespace products (`Pixel`/`mm`
  drawing scales, B3's documented exception; plus `in`/`km`/`cm` value
  strings of the same store). **Zero unit tokens in stream/tail
  territory on any non-drafting file** (U2 0/108).
- **Tail region** (dword8..EOF): 0 framed token hits of any family.
- **Spec-tree parameter names** (`Volume/Density/Mass/Length/Angle`,
  42 hits, u32le inside geometry-stream regions) are model *content* of
  CAA-sample parts — parameter/attribute names, present only where the
  model defines such parameters, never a document-level unit
  declaration. Explicitly excluded from the unit claims.

A fixed vocabulary of 29 unit tokens over 108 files spanning R15-R24,
framed patterns only, yields no structured occurrence in either
territory. A unit system stored without unit tokens (e.g. as a bare
enum value) cannot be located by byte evidence in this probe and is
recorded as out of reach, not as covered. Per the ticket's stop rule
the search stops at the two named territories.

## Reproduction

```
.venv/bin/python -I scripts/triage/probe_units_names.py --sample 3 \
  --include-sha16 0018baa84f3bff6b,b83a2e9d09820603,f3862d22fd9025ff,01f2a48c9151197e,62aa3a4f2d11665a,803c9860f69c88f7,9ee5735167e37ac2,c110aebb4509f3cc,f0479c1606dfcf4b,67b37d06c40d6eed
```

The probe is stdlib-only and read-only with respect to the corpus. The
D1/D2 rates are tallies over the full sample (not CSV-derived); the hit
rows are complete for the fixed vocabulary under the 500-per-file cap
(no file reached the cap).
