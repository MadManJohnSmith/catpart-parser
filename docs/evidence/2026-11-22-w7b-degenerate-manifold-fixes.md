# W7-B — Motor.CATPart's 23 degenerates + the official geometric failures

**Branch**: `marathon/w7b-head-ia`. **Date**: 2026-11-22. **Host**: TARDIS.
Companion note: [2026-11-22-w7b-head-ia-parity.md](2026-11-22-w7b-head-ia-parity.md).
No gate constants moved: `MAX_DEGENERATE_TRIANGLES = 0` and the
manifold gate are untouched; every fix is a decode-law correction in
the facet-record width law.

## The failure map (micro-batch, pre-fix, Python engine = reference)

| file | L2 verdict | degen | tri | boundary | stage |
| :--- | :--- | ---: | ---: | ---: | :--- |
| Motor.CATPart (Ducati, 53 MB) | FAIL degenerate-triangles | 23 | 164,036 | 48,108 | mixedwrite-reps |
| `_NPart#194321` (povdoigt) | FAIL degenerate-triangles | 3 | 51,369 | 18,593 | mixedwrite-reps |
| LedStrips_Smooth (190 MB) | FAIL degenerate-triangles | 33 | 224,435 | 66,273 | manifold=True |
| Guntle.ver5 (Dictor) | FAIL not-manifold | 0 | 2,984 | 1,096 | table-walk |
| LedStrips_5V_final | FAIL not-manifold | 0 | 15,860 | 4,332 | |
| M4x10_Poelier | FAIL not-manifold | 0 | 2,242 | 833 | per-rep |
| M3x16_CHC | FAIL not-manifold | 0 | 1,702 | 1,403 | table-walk |
| frente_&_UPPER_teeth | FAIL not-manifold (+28 degenerates behind it) | 28 | 59,188 | 4,009 | |

Both engines agree on every one of these (parity verified file by
file) — the failures are decode-correctness, not engine divergence.

## Class A — the short-form `nxt` truncation (the degenerate counts)

The L2 `degenerate-triangles-skipped` count comes from PRIMARY strip
loops only (the dup-pin weld is fail-closed on degenerates; the
extended family filters its members under the 2026-11-21 law). Probe
`scripts/triage/w7b_degenerate_probe.py` attributes Motor's 23 to
exactly two 0x42 records: 3 at offset `51508595`, 20 at `53353357`;
`_NPart#194321`'s 3 to one record at `1778227`.

Their loops carry the alternating-ref signature (`[0, 102, 0, 104]`,
`[3, 0, 3, 172, 2, 235]`) — a **u8 half-read of a wider ref stream**.
The wider candidates exist but were excluded: the strip-parser's `nxt`
comes from the STRIP_RE-only header list, and FALSE `01 4x . ff`
headers inside the record's own ref bytes truncate it, so the wider
candidate's `end` runs past `nxt` and dies on the absolute
`end > nxt` gate. This is the short-form analogue of the #65 gap the
extended family already fixed — the in-span candidate headers are the
record's own ref bytes.

- Motor `51508595`: u16be `end = 51508694` lands EXACTLY on a later
  candidate header (a real 0x47); the false `01 44 02 ff` at 51508680
  sits inside its refs. n=42, counts 7×6; the u16 refs (954, 767, 955,
  748, …) are monotone strip joins.
- Motor `53353357`: u16be `end = 53353545` lands exactly on the next
  real 0x42 record; two false headers inside. n=80, counts 20×4.
- `_NPart#194321` `1778227`: **u24be** `end = 1778660` lands exactly on
  a later candidate header; one false header inside. The u24 refs (37,
  35, 444, 872, 1022, … 74069) sweep the full 74,296-element space —
  the u8 reading only ever reaches refs ≤ 254.

**Patch** (`002-short-form-exact-exception.patch`, composite.py +
composite.rs, in lockstep):

1. the exact-tiling slot reads the MERGED boundary list (strip + facet
   header positions) — an end exactly on a facet header is as exact as
   one on a strip header;
2. the #65 exception extends to the short form: an end past `nxt` is
   viable only when it lands exactly on a later merged candidate header
   and swallows no already-accepted record;
3. the accepted-span gate: walk positions inside an exception-admitted
   record's span skip (in-span headers are its own ref bytes).

Every currently-viable candidate keeps its viability and exact flag —
only previously-EXCLUDED candidates can join a vote, and only through
the exact-tiling + no-swallow rule.

**Result**: Motor 23→0 (PASS, +145 real triangles), NPart 3→0 (PASS,
+360), frente's 28 degenerates →0. head_ia 24 MB byte-unchanged
(regression check).

## Class B — facet-header exact tiling invisible to the short vote (M4x10)

M4x10's 8 kept over-use loops all came from 0x42 records whose u16be
reading ends exactly ON the next 0x47 FACET header (`20635818` →
`end = 20635839 = 01 47 04 02 01 ff`). The header sits INSIDE `nxt`
(no exception needed) — but the exact-tiling slot compared against the
STRIP-ONLY list, so the candidate ranked non-exact and lost the width
tiebreak to the u8 half-read (whose junk loops then over-used edges and
were KEPT by the seam's >1%-area rule — the manifold break).

The merged-boundary exact slot (patch item 1 above) fixes this class:
M4x10 not-manifold → **PASS** (tri 2,242 → 2,349, boundary 833 → 595).
frente_teeth's not-manifold falls with it (its misreads were the same
shape) → **PASS** (tri 59,188 → 60,499, boundary 4,009 → 3,083).

## Class C — full ties preferred the half-read (Guntle, M3x16, LedStrips_5V, LedStrips_Smooth)

The three not-manifold files keep ONE over-use loop each (probe
`scripts/triage/w7b_kept_overuse_probe.py`) from records where BOTH
readings are clean: viable, in-bounds, repeats=False on both (Guntle
`3836322`: u8 `[8,195,9,27]`/`[8,212,9,10]` vs u16be
`[2243,2331,2148,2314]`) — the rank ties through every quality slot and
the width slot picks the NARROWER half-read. The kept over-use breaks
the manifold gate. LedStrips_Smooth's 33 degenerates are the same tie
class with the degenerate-emission symptom (its misread strips carry
the repeated-coordinate windows).

**Patch** (`003-vote-ties-prefer-wider.patch`, vote.py + vote.rs): the
width slot flips to `255 - width` — full ties prefer the wider
candidate. The narrower preference was the last-resort tiebreak of the
#62/#65 law; on these ties it kept the u8 half-read standing. The
wider readings fix all four:

| file | before | after |
| :--- | :--- | :--- |
| Guntle.ver5 | not-manifold, 2,984 tri, boundary 1,096 | **PASS**, 3,093 tri, boundary 1,037 |
| M3x16_CHC | not-manifold, 1,702 tri, boundary 1,403 | **PASS**, 1,702 tri, boundary 1,402 |
| LedStrips_5V_final | not-manifold, 15,860 tri, boundary 4,332 | **PASS**, 16,130 tri, boundary 4,260 |
| LedStrips_Smooth | FAIL degenerate-triangles (33), 224,435 tri, boundary 66,273 | **PASS**, 229,732 tri (+5,297), boundary 38,888 (−27,385) |

(Smooth's 33 degenerates ride the same tie class — its misread strips
emit the degenerate windows; the wider readings carry none — and the
wider parses recover 5,297 real triangles.)

and every already-passing micro-batch file STAYS PASS with strictly
more geometry (head24 478,979→480,662 tri / boundary 9,241→8,784;
Motor +1,167 tri; frente 60,499→66,444 tri / boundary 3,083→2,066;
M4x10 2,349→2,426; NPart 51,729→51,826; head_ia 231 MB 640,369→649,136
tri / boundary 7,831→5,482).

**Risk, stated**: the flip is corpus-wide (every full tie through
exact/oob/repeats/nonplanar resolves wider). The micro-batch validates
it positively on 10 files; the Orquestador's 1,413-file re-run is the
corpus-wide validator. If it regresses, the narrower preference is the
one-line revert.

## Also fixed in passing — the dropped relaxed counters (parity)

`identity-table-walk` and `identity-raw-array` Rust paths dropped
`relaxed_loops_accepted`/`relaxed_loops_declined` from the summary
(the twin rides them on `**loop_stats` on every path,
composite.py:1619-1621; only the mixedwrite/per-rep path had the
emission). Guntle.ver5 and M3x16_CHC diverged by key presence alone
(PLYs identical). Patch `004-relaxed-counters-table-walk.patch`
(composite.rs, two `if … > 0` emission blocks mirroring
decode_per_rep's d8554e0-era fix).

## Final sweep (all patches, both engines)

See the progress doc's log — 10/10 micro-batch files: L2 PASS where the
gate passes, byte-identical PLYs and semantically identical summaries
on every file.
