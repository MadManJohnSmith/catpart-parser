# Phase 5 V4 (ticket #43): the WASM boundary + the viewer shell

**Status: implemented on the V4 worktree branch, 2026-11-14; coordinator
review pending.** Design authority: `docs/specs/phase5-viewer-spec.md`
— this note cites §2.1 (crate layout, dependency policy), §2.3 (the
WASM boundary: two whole-buffer entries, typed arrays, classified
errors, the additive curves), §2.2 (the numeric contract), §3.4 (the
in-browser gate mirrors `_score_export`), §5 (the viewer shell:
committed artifacts, vendored pinned three.js, no bundler/framework/
node_modules), §6 V4 (ticket scope), §7 (CI gains the shipped-artifact
steps), §10 risks 5/6/8/9; the ticket is #43, the decode it exposes is
V3 (#42). Nothing is merged or pushed: commits live on the worktree
branch only.

## What landed

### 1. The WASM boundary (§2.3) — `port/src/wasm_boundary.rs`

- `decode_inspect(bytes) -> JsValue` — the schema-v1 inspect document,
  built by the new shared `port/src/inspect.rs`
  (`build_inspect_document`): the document struct and the short-buffer
  refusal moved OUT of `bin/fidelity-cli.rs` so the field declaration
  order (§2.1: the Python dict construction order of
  `build_inspect_report`) is single-sourced between the native CLI
  seam (§2.4) and the boundary. `fidelity-cli inspect` output is
  byte-identical to before (the fixture-mode harness re-ran green —
  the pytest pass below includes it).
- `decode_export(bytes) -> { summary, vertices: Float32Array,
  triangles: Uint32Array, curves: Array<Float32Array> }` — whole-buffer,
  no streaming; `summary` crosses via `serde_wasm_bindgen` (the
  §2.3-prescribed dependency), the mesh and curves cross as real typed
  arrays. The boundary's ONLY numeric operation is the exact `f64 ->
  f32` narrowing of the pool coordinates (§2.2's widening point makes
  it bit-exact recovery, not a rounding decision) — the file performs
  no decode arithmetic and carries no `suboptimal_flops` allow.
- **Failure**: both entries return `Result<JsValue, JsValue>`; the
  `Err` value IS the classified error object `{ error_class, detail }`
  (the generated glue throws it as a JS exception whose payload is
  that object). The vocabulary is the twin's: the geometry classes at
  the twin's raise sites (`geometry/errors.rs` constants); the inspect
  seam's L1-reachable refusals classify `crash` (the Python side's own
  classification for every exception raised while producing the output
  — `runner.py::_classify_file`; the A2 table pins short-file →
  crash). One boundary-specific arm, documented in the module header:
  an EMPTY buffer on `decode_export` — the twin's unclassified mmap
  `ValueError`, mirrored by the native CLI as a panic — classifies
  `crash` here, because the viewer must display a failure, never a
  blank screen (§5) and a wasm trap is not a classified error.
- **The curve exposure rides the boundary** (§2.3: additive, NOT part
  of the Fidelity definition): `ExportOutcome` grows `curves:
  Vec<Vec<(f64, f64, f64)>>` (empty on the non-composite path), fed
  from `CompositeDecode.curves` which V3 carried for exactly this
  handoff. The summary and the PLY never contain it; the harness does
  not see it.
- Dependencies added at V4 (recorded here per §2.3 and on the ticket):
  `serde-wasm-bindgen 0.6.5` (the §2.3-prescribed summary conversion;
  0.6 is the current major — the crate line is 0.6.5, not 0.8) and
  `js-sys 0.3.107` (the typed-array constructors the §2.3 shapes
  require; same wasm-bindgen family, same release cadence — pairs with
  the already-pinned `wasm-bindgen 0.2.130`, which did NOT bump).

### 2. Packaging (§5, owner decision 2026-11-13: COMMIT)

- wasm-pack **0.15.1 pinned** (recorded per §2.1 here and on the
  ticket). Install tarball
  `wasm-pack-v0.15.1-x86_64-unknown-linux-musl.tar.gz`, sha256
  `410101009739b9d01c7d5affaaad6e9c9a24b4cba6791a4805db8e89b9bf7af2`
  (verified locally and re-verified in CI's install step).
- `wasm-pack build --target web --release` produces `port/pkg/` —
  **committed** (port.js glue 14,999 B; port_bg.wasm 305,474 B, sha256
  `8c8bc1c73484271b334dbc8ff1a44678d817a20a3b40f44008405b5e60f43e4f`;
  port.d.ts / port_bg.wasm.d.ts / package.json alongside). The
  publication copy `site/viewer/pkg/` is committed byte-identical
  (`cmp`-verified) — §5's "pkg output copied at build": gh-pages stays
  a pure function of committed content, so the published tree must
  carry its own copy. `scripts/publish_fitness.py` is untouched and
  copies `site/` verbatim (byte-read + token-replace only; the .wasm
  publishes byte-exact — `rglob("*")` has no extension filter).
- **wasm-opt disabled** (`[package.metadata.wasm-pack.profile.release]
  wasm-opt = false`): the shipped artifact is rustc's output verbatim —
  a binaryen re-optimization pass has no business near a bit-exact
  decode (§2.2), and CI avoids a second pinned-binary download.
- The gate/CI build to a check dir OUTSIDE the committed `pkg/`
  (`--out-dir target/wasm-pack-check`): packaging is proven to succeed
  without touching reviewed artifacts; refreshing `pkg/` is a
  deliberate maintainer step (`wasm-pack build --target web --release`,
  then delete the generated `pkg/.gitignore` and copy to
  `site/viewer/pkg/`).

### 3. three.js vendored (§5: pinned, sha256-recorded, no CDN)

- **three@0.170.0**, `build/three.module.min.js`, 691,648 bytes,
  sha256 `08fd7545d13d2c7fb65ab691530a802dafefd638596501854f267d0fb13c39e7`,
  vendored at `site/viewer/three.module.min.js`. Source URL
  `https://unpkg.com/three@0.170.0/build/three.module.min.js`; the
  digest was cross-checked against a second independent CDN
  (`https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.min.js`)
  — identical. Version rationale: r0.170 is the last release line whose
  `build/three.module.min.js` is a SINGLE self-contained ES module
  (from r0.175 the build splits into `three.module.js` +
  `three.core.js`, which would vendor two files); §5 says "three.js
  ships as a single vendored ES module". Zero `import` statements in
  the vendored file (verified). The pin floats only by a deliberate,
  dated re-vendor (§5).

### 4. The viewer shell — `site/viewer/` (§5)

Hand-written ES modules, the site's zero-dependency property: no
bundler, no framework, no node_modules (Playwright is a local dev
dependency only, never in the tree — see §6).

- `viewer.html` — the shell (drop zone, canvas, controls, gate +
  metadata panels, classified-failure panel); joins the site nav
  (`common.js` gained the Viewer entry — a one-list change).
- `viewer.js` — the app: drag-drop / file-picker of a `.CATPart`;
  orbit/zoom + wireframe/solid toggle (three.js `wireframe` material
  flag); the metadata panel rendering the schema-v1 document (document
  name, detected version, kind, file size, magic, trailer, container
  inventory table); the curve overlay over the decoded polyline loops
  (per-loop `THREE.Line`, toggle-tracked, disabled with a count when
  the store exports no dropped loops); the classified-failure display
  — a failing decode shows `{ error_class, detail }` in a dedicated
  panel, the empty canvas is hidden (nothing to draw), the gate panel
  says "no export", and the drop zone stays usable: never a blank
  screen. The two seams fail independently (an inspect refusal renders
  in the metadata panel; an export refusal in the error panel). Every
  load disposes the previous scene's GPU resources; the drop zone
  slims to a "load another" bar after a load. A `window.viewer`
  state object mirrors what the panels render (the scripted checks
  read it; the page does not require it).
- `orbit.js` — hand-written orbit + wheel-dolly (desktop pointer
  events; §1's desktop target). Not vendored: the orbit controller is
  ~90 lines of site code, keeping the vendored surface at exactly the
  one pinned three.js module.
- `gate.js` — **the §3.4 gate mirror**: `scoreExport(summary)`
  reimplements `_score_export` exactly (the law at
  `src/catpart/fitness/runner.py:309-329`): same check order (empty →
  manifold → finite plausible bbox → degenerate ≤ 0), same constants
  (`MAX_DEGENERATE_TRIANGLES = 0` imported, not re-typed), same
  failed-check vocabulary (`empty-mesh`, `not-manifold`,
  `nonfinite-bbox`, `degenerate-triangles`), the plausibility check
  mirrors `_bbox_plausible` (finite on all six bounds, min ≤ max per
  axis) and the bbox records null when implausible. **No margin is
  declared or hard-coded anywhere in the viewer** — the §3.4 margin is
  V5's owner-approved declaration; this display is rate-agnostic (the
  hard stop, respected).
- Memory honesty (§10 risk 8): desktop-target only, stated on the
  page itself. The file is held as an ArrayBuffer, copied into the
  WASM linear memory, and decoded into new typed arrays — ≈3×
  transient peak; the largest corpus file is ~120 MB.

### 5. CI + gate (§7 step 6) — CI RUNS the shipped artifact

- `.github/workflows/ci.yml`'s port job gains: the pinned
  sha256-verified wasm-pack install (no curl|sh), `wasm-pack build
  --target web --release` (check dir), and `wasm-pack test --node` —
  the wasm-bindgen tests under Node on the §7 fixture subset. Node
  pinned 22 via `actions/setup-node@v6`; `~/.cache/wasm-pack` joins
  the cargo cache paths.
- `scripts/check.sh` mirrors the same two steps after the cargo steps
  (the #38 rule), failing loudly with the pinned install command when
  wasm-pack is absent — the same pattern as the V0 cargo check.
- Playwright stays LOCAL (§7): `scripts/viewer_acceptance.py` is a
  standalone local tool, not a pytest, not CI.

### 6. The wasm-bindgen Node tests (§7: the small fixture subset)

`port/tests/wasm.rs` (whole-file `#[cfg(target_arch = "wasm32")]` —
the native test binary compiles empty; the gate's native `cargo test`
is unaffected) runs **6 tests under Node**:

1. `inspect_document_canonical` — schema v1, kind part, version
   V5R21SP0HF0, 3 containers, trailer present.
2. `inspect_document_short_file_refuses_crash` — the crash class +
   the twin's ValueError prose.
3. `export_canonical_summary_and_typed_arrays` — v 8 / t 12, closed
   manifold, bbox max (20, 100, 60) — values captured from
   `catpart-export` on the identical bytes (2026-11-14); asserts REAL
   `Float32Array`/`Uint32Array` instances (24 / 36 elements) and empty
   curves on the clean path.
4. `export_composite_curve_exposure_at_the_boundary` — the composite
   curve-entry fixture exports 12 triangles, the summary block carries
   `loops_curve_entry: 1` (what Fidelity compares), and the ADDITIVE
   curves array carries exactly 1 dropped-loop polyline (a Float32Array
   of xyz triples).
5. `export_classified_failures_match_the_twin_vocabulary` — one
   corrupted variant per class: `missing-geometry-store`
   (bad-nested-magic), `malformed-pool-group` (truncated-pool),
   `malformed-pool-vertex` (nan-coords), `undecoded-variant`
   (out-of-range-refs); non-empty details; the store-less short file
   exports `missing-geometry-store` (the twin's class for it — no
   invented crash class).
6. `export_empty_buffer_classifies_crash` — the boundary-specific arm
   (the module header's rationale).

The fixture bytes are the GENERATED source arrays
`port/tests/fixtures/mod.rs` (`scripts/gen_wasm_fixture_data.py`, a
pure function of `tests/fixtures_gen.py`): committed fixture BINARIES
are impossible (the A2 binary guard rejects any tracked file whose
first 8 bytes are the `V5_CFV2` magic) and the Node harness has no fs
(wasm32-unknown-unknown std). `tests/test_wasm_fixture_data.py` pins
the committed file byte-identical to a fresh regeneration and pins the
subset's shape (canonical + the classified classes) — the subset can
never silently drift from the generator the fixture-mode harness
drives.

### 7. The V4 note item — powf on wasm32 (one sentence, as briefed)

On wasm32, Rust's `powf` resolves to the libm crate rather than glibc;
the V3 review already quantified the decision margins on the real
decision surface (closest corpus call to the `PLANE_TOL` boundary:
1.06e-5; min nonzero nn ≈ 1.0 — spec §2.2 / §11 register entry
2026-11-14), so a differently-rounded pow cannot flip a corpus
decision, and the in-browser decode inherits that proof.

## Acceptance evidence (commands + counts, run 2026-11-14)

### Local Playwright fixture checks (headless Chromium, local-only)

Playwright pinned `1.65.2` (local pip install into the worktree's
`.venv`, never committed; Chromium headless shell 159.0.8154.6 via
`playwright install chromium`). Command:

    .venv/bin/python scripts/viewer_acceptance.py

Output (verbatim):

    viewer acceptance — PASS
      - canonical fixture: loaded, gate pass, 8 vertices / 12 triangles, finite bbox [0, 0, 0]..[20, 100, 60]
      - metadata panel: schema v1 fields present (version, kind, 3 containers)
      - curve overlay: 1 decoded loop(s), toggle off->on->off (aria-pressed tracked)
      - corrupted fixture: classified error shown (malformed-pool-vertex, 99-char detail), page alive
      - no server component: 10 requests, all on the serving origin; zero uncaught page errors
    serving command: python3 -m http.server 8931 --bind 127.0.0.1 --directory <worktree>/site (read-only static)

- The serving is **read-only static files only** (`python3 -m
  http.server`, GET-only): exactly the §6 V4 acceptance's "no server
  component" — the viewer's 10 requests all stay on the serving origin
  (the vendored module, the pkg glue + wasm, the page files), zero
  external requests, zero uncaught page errors.
- The checks drive the file-picker path (`set_input_files`) over the
  A2 fixtures generated in-process from `tests/fixtures_gen.py` (the
  same generator the Fidelity harness drives; fixtures live in a
  temp dir, never committed — the binary guard).
- Screenshots reviewed by hand: the canonical box renders (orbit
  framed, controls live), the curve-entry store shows the overlay
  toggle pressed with 1 loop and the `curve-entry-loops-unexported` /
  `unused-pool-vertices` warnings listed, and the corrupted fixture
  shows `Decode failed — malformed-pool-vertex` with the G2 P3
  detail while the gate panel reads "no export — the decode failed".

### wasm-pack build + wasm-bindgen Node tests

    cd port && wasm-pack build --target web --release   # ✓ port/pkg/
    wasm-pack test --node                               # 6 passed; 0 failed

### The gate, end-to-end (scripts/check.sh — the local copy of ci.yml)

    scripts/check.sh

Result (2026-11-14, this branch):

- ruff: All checks passed!
- pytest: **368 passed, 7 skipped** in 22.9 s (V3 closed at 366 + 7;
  +2 = the wasm fixture-data pin's two tests). The fixture-mode
  Fidelity harness re-ran inside it against the refactored inspect
  seam: 334/334 fixture rows match, all refusal classes equal — the
  CLI refactor changed no behavior.
- cargo build native + wasm32-unknown-unknown ✓
- cargo fmt --check ✓ · cargo clippy --locked -- -D warnings ✓
- cargo test: **97 passed** (V3 closed at 95; +2 = `inspect.rs`'s
  refusal/schema tests)
- wasm-pack build --target web --release ✓
- wasm-pack test --node: **6 passed, 0 failed**

CI runtime expectation: the port job grows by the wasm-pack install
(seconds) + one release wasm build (tens of seconds, warm cache) + the
Node test run (seconds) — within the §7 stated weight (the whole
workflow stays ~5-10 min cold). Measured CI runtime lands with the
first pushed run (this branch is not pushed; the coordinator's merge
push will show it).

## What V4 deliberately does NOT do (the hard stops, respected)

- No in-browser reproduction harness (V5's — the automated L2
  population run with the margin declaration): the viewer computes and
  displays the per-file gate outcome, but nothing drives a population
  or aggregates a rate.
- No publication to gh-pages (V6): nothing pushed, the publish flow
  untouched.
- No changes to `src/catpart/`, `fitness/`, or the spec (git status
  shows none); the §3.4 margin is undeclared — no margin value appears
  in the viewer or this note.
- No curve-record re-decoding beyond the landed laws (§10 risk 9): the
  overlay consumes exactly the §2.3 `curves` V3's decode produces.

## Known gaps / partial results

- None blocking named. One cosmetic: the gate panel's bounding-box
  rendering truncates to 8 significant digits for display only (the
  gate MATH uses the full f64 values from the boundary; the display is
  not the compared artifact — the V5 comparison consumes
  `scoreExport`'s numeric record, not the HTML).
