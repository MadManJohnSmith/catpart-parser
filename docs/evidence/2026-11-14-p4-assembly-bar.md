# P4 — the Phase 6 assembly bar: derivation and declaration

**Declared: 2026-11-14 (owner decision, pre-implementation per the
pre-commitment-gating pattern — dispatch-recipes.md). The bar is
recorded here BEFORE the `_Position` encode probe (P2.5) and the
viewer assembly mode (P3) exist.**

## The arithmetic it derives from (all committed, verifier-reproduced)

- Population: 380 byte-verified CATIA products (382 manifest rows).
- Framed pools: 253 (R18-R26 = 230 at 100% chain tiling — the clean
  version scope; the R15-era 106 form + 21 unframed are open classes).
- Identity pairs DECODED: 225 files with >= 1 decoded (PartNumber,
  InstanceName) pairing (triple 216 fact / desc-block 17 / bare-only 9
  inference) — P2 #53.
- PartNumber -> part-file resolution: the same-repo stem join 248/382
  (40/382 cross-repo collision control, candidate class) — P1 #46.
- Placed-instance ceiling: 260 files carry `_Position` (68.1%); the
  value encoding is OPEN — proven not a pool item (P2: 0 numeric
  successors in-chain).

## The declared bar (the viewer's assembly mode, P3)

1. **Instance structure**: the mode lists each product's instances as
   (PartNumber, InstanceName) with 100% agreement against the
   committed pairing law on the framed population (253; the R18-R26
   clean scope at 100%).
2. **Resolution**: each instance's PartNumber resolves to a part file
   by part number (the user supplies the product and its referenced
   part files together, per the ROADMAP; the 248/382 join arithmetic
   is the corpus-scale reference). Unresolved instances display
   classified — never hidden.
3. **Placement**: instances render with DECODED transforms — the
   `_Position` value encoding MUST decode (the P2.5 probe) for the
   placed class. Identity placement is the fallback ONLY for the
   no-`_Position` class (120 files). There is NO identity-fallback
   masking for undecoded transforms: undecodable placement displays
   classified as such.

## The conditional exit (the only one)

If the P2.5 probe proves the `_Position` value encoding undecodable
within its bounded effort, the documented-negative path applies
(ADR-0004's pre-authorized rule): the negative is published with its
evidence, and the bar decision returns to the owner. The bar is never
silently downgraded to identity-fallback to make it pass.

## What this bar deliberately does not demand

- No assembly-tree nesting requirement beyond the decoded pairs (the
  8 in-corpus sub-product refs stay a reported figure, not a gate).
- No numeric rate threshold on the transform decode (the encoding is
  an open class — a pre-threshold would be arbitrary; the decode rate
  over the 260-file class is PUBLISHED with the P2.5 evidence).
- No CATXDocLinkCont link-table decode (2 files, no population).
