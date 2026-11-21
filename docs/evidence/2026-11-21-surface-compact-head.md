# Evidence: the compact `a5 03 34` head — per-lane degrees, multiplicities and a chord-length-free band (2026-11-21)

**Date**: 2026-11-21
**Status**: COMPLETE for L1+L2 on the submarine population (91/94 parts recover a mesh; 3 named exceptions)
**Ticket**: #67 (`W-B surface-compact-head`), parent #50
**Target**: the 94 parts of the TR-1700 S42 submarine snapshot classified `no-evaluable-surface` (`bench-submarine/m1_files.csv`). All 3,743 `a5 03 34` frames in those parts died in `parse_surface_head`; none reached `assess()`.
**Method**: diagnostic `subagents/s2-submarine-surfaces/informe.md` (read-only over the snapshot, 1,145-frame sample plus a 94-part survey) turned into the shipped decoder, `tests/test_surface_compact_head.py` and the Rust twin's tests. Corpus read-only; no binary committed.

---

## 1. Executive summary

The marker has a **third head grammar**. It is not a subtype byte at `payload+8` (that byte falls inside the first knot `f64`). Each direction stores its own degree, knot count and multiplicities:

```
+0   u8  (degree << 2) | 1
+1   u8  (n_knots << 2) | 1
+2   u8  0x0c          implicit clamped multiplicities (degree+1, 1…1, degree+1)
        0x04          an explicit vector of (mult << 2) | 1 bytes after the knots
+3   f64 knots[n_knots]      strictly increasing
     …                       the same block for v
     u8  0x01 | 0x05         opens the pole net
     24 B × poles_u × poles_v
     …                       record tail, 141..3,597 B (not a closure law)
```

`poles = sum(multiplicities) − degree − 1`, which is `(degree + 1) + (n − 2)` for the implicit form. The grid is predicted by the head; the tail is not validated.

The second gate is independent: **96.9 % of the decoded frames fail only the chord-length band** (`ARC_RATIO_BAND = (0.5, 2.0)`). This grammar's parameterisation is not chord-length (median ratio 0.0328 over the 3,731 plausible nets; only 68 fall in the band), so the band is not a coherency law here. Keeping every other check, the compact branch does not apply it; the legacy branch is untouched.

Measured on the 94 parts with the shipped decoder (Python and Rust agree exactly):

| measurement | value |
| :--- | ---: |
| `a5 03 34` candidate frames | 3,743 |
| compact heads decoded | **3,733 (99.73 %)** |
| plausible pole nets (surviving `plausible_net`) | 3,731 |
| parts that recover a mesh | **91 / 94** |
| tessellated patches | **3,683** |
| triangles | **2,134,032** |
| frames refused by the battery | 48 (all `folds`) |
| max corner residual | 1.36e-12 (tolerance 1e-9; 0 violations) |

Counterfactual with the chord-length band kept (L1 only): 16/94 parts, 68 patches, 34,096 triangles.

---

## 2. The grammar, from hex

All three frames below are from the snapshot; offsets are absolute in the part file.

### 2.1 Implicit multiplicities — `ST-Stern-ins.CATPart` frame `0x5a56` (payload 372 B)

```
a5 03 34 | 74 01 00 00 | 09 | 0d 09 0c | 00×8 | 00×6 f0 3f
marker     len = 372    f0   d=3 n=2    knot 0.0     knot 1.0
05 09 0c | 00×8 | 00×6 f0 3f | 01 | …
d=1 n=2    knot 0.0     knot 1.0  net 4×2
```

- `0d = (3<<2)|1`, `09 = (2<<2)|1`, marker `0x0c`; the v lane is `05 09 0c` → degree 1.
- `poles_u = 3+1+(2−2) = 4`, `poles_v = 1+1 = 2`; the net is 192 B at payload `+0x27`.
- Tail 141 B. `assess()` corner residual 0.0; only the arc band refuses it.

### 2.2 Degrees are not pinned to 5 — `ST-Stern-ins.CATPart` frame `0x55f7` (468 B)

```
15 09 0c | 00 00 00 80 0f 8d 00 be | ea 12 e0 02 00 00 f0 3f | …
d=5 n=2    knot ≈ −4.8e-10          knot ≈ 1.00000001
05 09 0c | …
d=1 n=2
```

`poles_u = 6`, `poles_v = 2`; corner residual 1.5e-16. Some records store exact `0.0`/`1.0`, others mantissa noise (~1e-10 relative); neither affects evaluation.

### 2.3 Explicit multiplicities — `BW-Hull-Bow-YL.CATPart` frame `0x6f2e` (1,711 B)

```
15 0d 04 | 3 knots (0.00990, 0.54725, 0.99999) | 19 05 19
d=5 n=3     explicit marker                     mult = 6, 1, 6
15 0d 0c | 3 knots (0.0, 0.5, 1.0) | 01 | poles (7×7)
d=5 n=3     implicit marker
```

`sum(mult) − degree − 1 = 13 − 5 − 1 = 7` poles in u. Corner residual 1.5e-16.

### 2.4 Population census (shipped decoder, 94 parts)

| measure | value |
| :--- | ---: |
| frames / decoded | 3,743 / **3,733** |
| explicit-marker lanes | 632 frames carry at least one `0x04` lane |
| pole markers | `0x01`: 2,549 · `0x05`: 1,184 |
| degrees (u,v) | 1..5 observed per direction; `(3,3)` 1,829 · `(1,2)` 549 · `(3,1)` 320 · `(1,3)` 311 |
| distinct tails | 77 lengths, 141..3,597 B; 141 B: 2,536 frames |
| knots strictly increasing | 3,733 / 3,733 |
| corner residual > 1e-9 | 0 / 3,731 |
| plausible pole nets | 3,731 (2 predicted a non-numeric run) |

The tail is **not** a closure law: the grid is fixed by the head, and a 141-byte tail decodes as readily as a 3,597-byte one. `SURFACE_TAILS = (152, 154)` remains the closure law of the two stored grammars only.

---

## 3. L2 — why the compact branch drops the chord-length band

`arc_ratio = (u_last − u_first) / pole-polygon arc length` assumes a chord-length knot lane. Measured over the 3,731 plausible compact nets:

| measure | value |
| :--- | ---: |
| inside `(0.5, 2.0)` | **68 / 3,731 (1.8 %)** |
| median | 0.0328 |
| frames failing only this check | 3,615 (96.9 %) |
| frames failing `folds` as well | 48 (1.3 %, legitimate refusal) |

Two replacement laws were tested and rejected with data:

- *normalised knot span ≈ 1*: only 1,543 of the 3,615 satisfy it (the parameter window looks inherited from a parent surface);
- *span_u/span_v ∝ arc_u/arc_v*: median ratio 3.14, only 25.4 % inside the band.

What a mis-predicted grid would break is still covered by `corner_residual` (exact on 3,731/3,731) and `plausible_net` (rejects the two merged runs). The compact branch therefore records `arc_applicable = False`: the corner residual, finiteness, pole hull, fold, scale and plausibility gates are unchanged; only the chord-length item is not applicable. `assess()` keeps the band for the two stored grammars.

---

## 4. What the 3 remaining parts are

| part | frames | reason |
| :--- | ---: | :--- |
| `BW-hatch-cargo-torp-up-G.CATPart` | 1 | 3-lane variant (`lane-marker` `0x41/0x57/0xab/0xac`), not decoded |
| `BW-hatch-up-Top-G.CATPart` | 2 | same 3-lane variant |
| `MB-Mani-H.CATPart` | 3 | decodes and then fails `folds` for real (23/22/19 folds) |

The 3-lane variant is 10 frames in 2 parts (0.27 % of the population) and is left as the named next question. Two other frames predict non-numeric runs (one per `ST-bow-plane-cuerpo-YL`, `ST-eskel-sup-T224`); their parts still recover through other patches.

---

## 5. Non-regression

- **Legacy branch untouched.** The compact parser is tried first with a positive predicate (`(b0 & 3) == 1`, `(b1 & 3) == 1`, `b2 ∈ {0x0c, 0x04}`); the two stored grammars start with the tag `u32 5` (`05 00 00 00`), whose second byte fails that predicate, so no legacy payload can enter the compact branch. `assess()` still applies the chord-length band whenever `head.subtype != SUBTYPE_COMPACT`.
- **`d7ed0772`** (`SHA-256 d7ed0772…`): the three measured frames that decode but do not evaluate (`SH-15`: two ~993 m merged nets and one folded, non-station-constant net) are rebuilt synthetically in `tests/test_surface_compact_head.py::test_d7ed0772_legacy_frames_stay_refused` and the Rust twin; all three still refuse on scale, plausibility and folds.
- **Official corpus head census**: all 1,956 corpus `*.CATPart` files were parsed with the baseline (`main @ 1f752f0`) and with this branch, frame by frame (37,460 `a5 03 34` candidates). 37,096 frames decode identically (same subtype and grid), **0 frames are lost or changed**, and the 364 new accepts are compact heads the baseline could not decode, in 14 parts. Those 14 parts export from their facet stores, so the surface fallback never runs: their PLY output is **byte-identical** between baseline and branch (SHA-256 compared). No corpus classification can change.
- **Suites**: Python `879 → 894 passed` (20 skipped, 15 new); Rust `192 → 200` lib tests plus the 6 integration tests.

---

## 6. What is not claimed

- **The 3-lane variant** (10 frames, 2 parts) is not decoded.
- **`marker+7`** (a token such as `0x09`) and the meaning of `0x01` vs `0x05`, `0x0c` vs `0x04` remain observed, not explained.
- **The tail content** (141..3,597 B) is not interpreted; it may still carry trim/display data.
- **No ground-truth mesh** exists: the validation is the decode battery (corners, hull, folds, scale, plausibility), not a CATIA-kernel comparison.
- **No wasm rebuild** (`port/pkg`) in this ticket; the viewer artifact is the coordinator's closing step.

---

## 7. Reproduce

```bash
# Python: head decode + battery + mesh census over the 94 parts
.venv/bin/python -I - <<'PY'
import csv, sys
sys.path.insert(0, "src")
from catpart.geometry import surface
snap = "/home/alan/Downloads/submarine-ssk-tr-1700-s42-ara-san-juan-1.snapshot.20/"
rows = [r for r in csv.DictReader(open("/home/alan/.local/state/catpart-parser/bench-submarine/m1_files.csv"))
        if r["error_class"] == "no-evaluable-surface"]
parts = patches = triangles = 0
for r in rows:
    scan = surface.scan_part(open(snap + r["path"], "rb").read())
    parts += bool(scan.tessellated)
    patches += scan.tessellated
    triangles += len(scan.triangles)
print(parts, patches, triangles)   # 91 3683 2134032
PY

.venv/bin/python -m pytest -q tests/test_surface_compact_head.py
(cd port && cargo test geometry::surface::tests)
```

The same census in the Rust twin prints the identical `91 3683 2134032` over the same 94 files.
