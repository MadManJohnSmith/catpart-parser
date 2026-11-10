# catpart-parser

Reader for CATIA V5 `.CATPart`/`.CATProduct` binaries built by reverse
engineering the file format for interoperability, without a CATIA
installation. Work is corpus-driven (fitness over a fixed file set) and
evidence-driven (every format claim tied to observed bytes).

## Language

### Corpus

**Corpus**:
The fixed set of public `.CATPart`/`.CATProduct` files the project measures
itself against, recorded as digests and source URLs in a manifest; binaries
are never committed.
_Avoid_: file set, dataset

**Dev split**:
The subset of the Corpus on which the Fitness headline is measured and
climbed.
_Avoid_: training set

**Held-out split**:
The disjoint subset of the Corpus used only to verify increments; its
Fitness is reported but never climbed.
_Avoid_: test set, validation set

### Format

**Container**:
A named section of the CATIA V5 container format (e.g. `CATProdCont`,
`CATFeatCont`), listed in the file's plaintext container-name table.
_Avoid_: chunk, block

**Version marker**:
The embedded plaintext CNEXTINFOS string stating the exact release and
service pack that wrote the file.
_Avoid_: header version

**Trailer**:
The structure terminating a file with `CB__END\0`, carrying size-like
fields.
_Avoid_: footer

### Fitness

**Fitness**:
One headline scalar per capability level (L1-L3) that an agent session
tries to increase; components are reported alongside but never collapsed
into the headline.
_Avoid_: score, scorecard

**Clean parse**:
A file parse that terminates without error, emits JSON valid against the
repo's versioned schema, and satisfies the minimal invariants (units
present, feature tree present when the file has one). L1's Fitness is the
share of the Corpus that is a Clean parse.
_Avoid_: successful parse, exit-0 parse

**Construct**:
A documented structural element of the CATIA V5 format (a section type, a
table, a parameter block). L3's Fitness is the share of Constructs in
`docs/format/` that the parser supports with verified semantics.
_Avoid_: feature, element

**Feature tree**:
The L1 name for the container-name table's record inventory — the
file's containers as an ordered list (name, parent_name, table_id,
index, guid, weight), emitted by `catpart-inspect` as `containers[]`.
There is **no instance hierarchy**: the measured corpus shows
`parent_name` is a base-class annotation (5-value vocabulary), not a
within-file parent pointer (ticket #24, 2026-11-08 note), so no tree
field is emitted. CATIA's full specification tree (Sketches, Pads and
other features) is out of L1 scope; a real instance-hierarchy claim
would be new B-branch work.
_Avoid_: specification tree

**Fitness history**:
The committed append-only record of every measured run — accepted or
rejected — that lets any session or CI run see the trend and the cost of
failed attempts.
_Avoid_: changelog, log

**No-regret rule**:
The acceptance rule for an increment: the change is kept only if the
headline rises on the Dev split and does not fall on the Held-out split.
Extended by #33 (2026-11-10): the rule aggregates both levels — accepted
when no comparable split regressed (L2 is protective) and at least one
comparable level's Dev rose, so an L2-only improvement with a flat
headline is acceptable (reason recorded); the first L2-bearing run
against a pre-L2 baseline keeps L1's protection.
_Avoid_: acceptance test, gate
