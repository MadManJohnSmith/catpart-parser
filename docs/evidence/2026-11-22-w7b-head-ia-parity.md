# W7-B — the last Python≡Rust divergence (head_ia, 61/62 declines)

**Branch**: `marathon/w7b-head-ia` (base dae7dd1). **Date**: 2026-11-22.
**Host**: TARDIS. The corpus file lives only in the Orquestador's
micro-batch (`/tmp/w7b/`, sha256-verified tar `7cd7e547…417724`); no
binary is committed.

## The divergence, reproduced

The official corpus's single engine divergence is the 231 MB
`Apoloo13/ASE_III/diseño_3d/moldes/head/head_ia.CATPart`
(sha256 `ae85fae7…`). Both engines export it; the summaries diverge:

| counter | Python | Rust |
| :--- | ---: | ---: |
| `extended_header_declined` | 62 | 61 |
| `extended_members_filtered` | 533 | 503 |
| `extended_header_triangles` | 609,707 | 610,059 |
| `triangle_count` | 640,369 | 640,721 |
| `mesh.boundary_edge_count` | 7,831 | 7,737 |

The 24 MB twin (`modelos_originales/head_ia.CATPart`, `ccbb7862…`)
exports byte-identical PLYs on both engines (verified before and after
the fix) — the divergence is one store of the big twin only. The PLY
vertex blocks of the big twin are byte-identical too, so the pool decode
is not involved; the divergence starts mid-mesh (face ~474,372).

## Root cause (probe: `scripts/triage/w7b_facet_ff4_probe.py`)

`facets.facet_headers` — the 6-byte extended-header candidate
discovery — disagrees on positions whose bytes carry `ff` at **both**
+4 and +5 (`01 [41-4f] . . ff ff`):

- Python matches the record with `FACET_HEADER_RE` (the 6-byte
  alternative needs `ff` at +5) but filters with
  `header_len(data, m.start()) == 6`; `header_len` derives the length
  ff-first over (4, 5, 6), so `ff` at +4 wins and returns **5** — the
  position is DROPPED (it is the observed 0x4b/0x4e 5-byte gap form
  there).
- The Rust `facets::facet_headers` decides via `header_form_len`
  (+3, then +5 — it never consults +4) and KEPT the position as a
  6-byte candidate.

The whole-file probe finds exactly one such position in the diverging
store: `229648727: 01 43 0c 1d ff ff`. The Rust side's extra candidate
header never parses as a record (`parse_extended_facet_records`
re-derives `header_len == 6` and skips it) — it corrupts the
candidate-boundary bookkeeping only: with it in `hdrs`, the extended
record at `229647190` (0x47, n=492) sees its width-3 candidate's end
(`+1476`) as an exact tile (`nxt_eff`), so the vote's exact-tiling slot
flips to u24be. Without it (Python), all three width candidates tie on
`exact=1` and the narrower-width slot picks u8.

Per-record vote dumps (probe `scripts/triage/w7b_vote_probe.py`, the
Rust twin env-gated `W7B_DUMP` in a temporary build):

```text
Python: w1 end=229647743 exact=False key=(1,0,1,0,0,0,1,0)  <- winner (width slot)
        w3 end=229648727 exact=False key=(1,0,1,0,0,0,3,0)
Rust:   w1 end=229647743 exact=False key=(1,0,1,0,0,0,1,0)
        w3 end=229648727 exact=True  key=(0,0,1,0,0,0,3,0)  <- winner (exact slot)
```

One record changes width → different refs → 30 more degenerate members
classified on Python (533 vs 503), one more record declined on Python
(62 vs 61), and +352 triangles on Rust. The tiebreak candidates
(vote/tiebreak vs candidate order vs the CLI counter) resolve to the
**vote boundary bookkeeping** — the width vote itself, the candidate
enumeration order and the counter aggregation are faithful twins.

## The proposed patch (handoff — facets.rs is W1-B territory)

`scripts/triage/w7b-handoff/001-facet-headers-ff-at-plus4.patch`: in
`facets::facet_headers`, the `Some(6)` arm pushes only when
`data[i + 4] != 0xFF` (the consume-skip stays `i += 6` — the Python
regex also consumed the 6 bytes before dropping the position). One
condition; `header_len` itself is untouched.

## Verification (patch applied locally, both engines)

| file | PLY | summary JSON |
| :--- | :--- | :--- |
| head_ia 231 MB (`ae85fae7`) | byte-identical | semantically identical |
| head_ia 24 MB (`ccbb7862`) | byte-identical | semantically identical |

The big twin's `extended_header_declined` lands at **62 on both
engines**; the corpus parity target is closed with the Python reading
(the reference) preserved bit-for-bit — the 24 MB twin's export is
byte-unchanged by the patch (`cmp` against the pre-patch export).

Residual note: the summary JSONs' key ORDER still differs (the Rust
`CompositeInfo` serializes `relaxed_loops_*` after
`extended_members_filtered`, the Python dict builds them before). The
harness compares semantically (the §3.2 class level) and the PLYs are
byte-identical, so this is cosmetic — but the fidelity-cli's docstring
pins "field declaration order = the Python dict construction order";
flagged to the Orquestador as a cosmetic follow-up, not part of the
parity gate.
