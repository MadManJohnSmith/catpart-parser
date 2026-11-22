# W22 graphic-attributes probe — the asked token is absent; the material-property family is the lead (2026-11-22)

**Worker**: W22 (Bloque E18, viewer fidelity) · **Scope**: read-only corpus
probe, no runtime wiring, no parser or export-contract change.
**Probe**: [probe_w22_graphic_attributes.py](../../scripts/triage/probe_w22_graphic_attributes.py)
(`--selftest` 6/6). **Data**:
[w22-graphic-attributes-files.csv](data/w22-graphic-attributes-files.csv)
(1,442 rows),
[w22-graphic-attributes-claims.csv](data/w22-graphic-attributes-claims.csv)
(W22-GA-01..08).

## The dispatch's asked rate — NEGATIVE (measured)

`CATGraphicAttributeSet` appears in **0/1,442** available corpus parts
(W22-GA-01). The whole vis-token family around it is equally absent:
`GraphicAttribute`, `VisProperties`, `CATViz`, `CATMaterialRef` — 0/1,442
each, swept as ASCII, ASCII case variants and UTF-16LE (W22-GA-02).
Every row of the files CSV carries the per-token counts; the
reproduction is the probe itself:

    python3 -I scripts/triage/probe_w22_graphic_attributes.py \
        --corpus-root /home/alan/Documents/Repos/catpart-parser

Interpretation: on this corpus, class-name tokens of the visualization
layer are not stored as ASCII strings the way `CATPrtCont` /
`CATSeeBodyCont` are. Whatever carries native colors/opacities, it is
not the token the dispatch named. (Inference, not fact: the corpus
predates or sidesteps the writer path that emits that class name.)

## The measured lead — fe-framed material-property blocks

A **fe-framed material-property family** exists in **33/1,442 (~2.3%)**
parts (W22-GA-04): blocks of the form

    fe <len = strlen + 1> <Name> 81 <e8|e9> <d4|f4> <T> (04 01 | 01) <value>

— the writer's `len = strlen + 1` framing, the SAME law the feature
names use (W4's `00 07 Sketch` anchors). The measured vocabulary:
Texture, TextureImage, TextureType, RepeatU, RepeatV, Reflectivity,
Transparency, TransparentColor, TransparentMode, Color, Contrast,
TranslationU/V/W — every name >= 1 fe-framed block in the population
(per-name file rates in the files CSV, `prop:<Name>:blocks` columns).

Value classes behind the descriptor (bytes measured; semantics
labeled):

- **`e6` + 8-byte little-endian double** — clean physical values:
  Reflectivity 0.7, 0.495, 0.4, 0.05, 0.1485, 0.3366, 0.2475, 0.3;
  a Color long-form block decodes 0x3FE7777780000000 = 0.7333... =
  11/15 (W22-GA-06). Fact: the decode is byte-exact. Candidate: the
  property semantics.
- **`e8` empty** — no value bytes. Dominates Transparency: 26 empty vs
  1 f64 block corpus-wide (W22-GA-07) — most parts store no per-part
  opacity there.
- **`84 81` + 3 bytes** (short color form) — measured triples include
  (231,231,231), (102,102,102), (0,0,0) (W22-GA-05). Candidate RGB;
  the interpretation is NOT validated against any render.
- **Length-prefixed ASCII strings** for Texture/TextureImage values
  (e.g. `0e "alpine..."`, `0b "timber..."`).

The plain ASCII token `Transparency` also exists in **85/1,442** files
in a DIFFERENT framing (a schema name table, length-prefixed
`0d Transparency` next to `TextureImage`, `TextureType`,
`TranslationU/V/W`, `DrwFeatureMaterial`...) — measured separately
from the value blocks (W22-GA-03).

## What the detector does NOT discriminate (declared, W22-GA-08)

Ordering of properties; per-face vs per-part attribution; the
`81 e8 d4 <T> 01` descriptor variant (4 files); the long color form's
full span (the `e6`-double + trailing bytes seen in one 19-byte block);
whether the 3-byte triples are sRGB or linear. The probe pins byte
patterns and rates only.

## Handoff (for the future native-colors ticket)

1. **Do not wire anything yet.** 33/1,442 files carry the family —
   any runtime color path would light up 2.3% of the corpus and
   nothing else; the honest viewer default stays the CATIA-style
   neutral shading shipped in W22 (flat shading option + crease
   edges).
2. **Decode order**: (a) the `81 e8 d4 <T> 01` variant (4 files) —
   one descriptor byte apart from the dominant form; (b) the long
   color form's full span (boundary law: next `fe <len>` name tag is
   NOT a proven terminator — measure against block preceders); (c)
   the `84 81` short form's semantics against a rendered corpus
   subset (the 33 parts are visually identifiable in the gallery).
3. **Where the blocks live**: first offsets per name are in the files
   CSV (`prop:<Name>:first_offset`); they sit in the parametric
   streams OUTSIDE the named containers (same region-law situation as
   the W4 feature names — framing-scoped, not region-scoped).
4. **Mechanical hygiene**: any follow-up claims CSV lands under
   `docs/evidence/data/*claims*.csv` (gate-covered); rerun this
   probe's `--selftest` after touching `parse_property_block`.
5. **Anchor pairs** for hand inspection (from the exploratory sweep,
   on this host): `corpus/povdoigt/SP-02/CATIA/CATIA_vol/SP02_BETA/First_Back_Shell.CATPart`
   first Color block `fe 06 Color 81 e9 f4 07 04 01 84 81 e7 e7 e7` at
   0x0b80dd-ish window (see the sweep in the W22 session record);
   `corpus/hssnadr/.../command-backshell-el.CATPart` Reflectivity
   `e6 00 00 00 a0 e3 ae df 3f` = 0.4906. The committed CSVs are the
   authoritative per-file anchors (sha16 + first_offset).

## Runtime changes shipped in the same block (E18 viewer)

None of the above is wired. The viewer ships instead: standard CAD
views, the even-shading (flat-shading) material option, the
interactive feature tree and the Bodies visual-component panel —
[marathon/w22-progress.md](marathon/w22-progress.md) carries the full
record.
