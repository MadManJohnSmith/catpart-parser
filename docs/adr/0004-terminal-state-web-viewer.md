# ADR-0004: Terminal state — client-side web viewer in Rust/WASM; closure at v1.0

The roadmap previously ended at Phase 5 "L3 B-rep … may remain partial
indefinitely" — an open-ended commitment with a moving denominator
(`docs/format/` grows as reverse engineering discovers constructs). We
decided (owner, 2026-11-10): the project's terminal goal is a web
viewer that parses arbitrary `.CATPart`/`.CATProduct` files entirely
client-side, built as a Rust→WASM port of the Python decode pipeline —
upfront cost explicitly accepted in exchange for native-level fluidity.
The port must prove Fidelity to the Python reference over the corpus,
because Python stays the fitness seam (ADR-0001) and the only
implementation the corpus validates. L3 B-rep stays in scope after the
viewer and assemblies, with its construct-coverage denominator frozen
by its own census. The project closes at v1.0 (tagged release, final
report, frozen corpus, public repo, no maintenance promise), and phase
bars carry a pre-authorized revision rule: a demonstrated reachable
ceiling below a bar re-adjusts that bar to ceiling − declared margin,
with the arithmetic published.

## Considered Options

- Pyodide (run the actual Python in the browser): rejected — ~10 MB
  runtime and slow decode contradict the fluidity requirement; remains
  the documented fallback if the WASM port stalls.
- TypeScript port: rejected — same double-maintenance cost as Rust
  without the sustained decode performance on large meshes.
- Viewer over an offline-converted corpus (the browser never parses
  CATIA): rejected — the owner wants arbitrary user files opened in the
  browser, not a curated gallery.
- Close the project at L2 and declare B-rep out of scope: rejected by
  the owner — the terminal goal is a usable viewer plus precise
  geometry, not mesh-only.

## Consequences

- Two implementations of the decoder exist from Phase 5 on; the
  fidelity harness (port output identical to the Python reference over
  the corpus, measured locally per ADR-0003) is mandatory acceptance,
  not nice-to-have. CI covers the port with synthetic fixtures only.
- Assemblies and B-rep become bounded phases with census-first tickets
  — neither can silently stay "partial indefinitely"; a phase closes by
  acceptance or by the pre-authorized negative path.
- `v1.0` is a verifiable state: the tag exists with every phase closed
  or negatived, or the project is not done.
