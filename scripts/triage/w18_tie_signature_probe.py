#!/usr/bin/env python3
"""W18 triage probe: full-tie width votes vs the W1 half-read signature.

Instruments :func:`catpart.geometry.vote.vote_ref_width` and logs every
vote where the winner was decided by the WIDTH SLOT over a tied u8
candidate — a candidate pair whose rank keys differ only in the width
slot (the patch-003 ``255 - width`` arm). For each such tie it records
whether the narrow (u8) candidate's ref block carries the W1
anti-half-read signature (even bytes 0x00 over the 2n span, n >= 8,
u16be re-read outside the element space) — the gate condition the W18
half-read law proposes.

Output: one JSON line per tie on stdout (plus a per-file count line),
so the accepted-003 tie set can be compared against the signature the
gate would require.

Usage: python3 scripts/triage/w18_tie_signature_probe.py <file.CATPart> [...]
"""

import json
import sys


def u8_signature(data, counts_end, n, element_count):
    """The W1 signature measured on a u8 candidate's block (probe view:
    ``len(data)`` stands in for the caller's section bound ``hi``)."""
    fits = counts_end + 2 * n <= len(data)
    span = range(0, 2 * n, 2)
    even_zero = fits and all(data[counts_end + j] == 0 for j in span)
    u16_oob = fits and element_count is not None and any(
        int.from_bytes(data[counts_end + j : counts_end + j + 2], "big")
        >= element_count
        for j in span
    )
    return {"fits": fits, "even_zero": even_zero, "u16_oob": u16_oob}


def _selftest() -> int:
    """Two pinned edges of the signature's discriminating power.

    (a) a W1-signed block (even bytes 0x00, n >= 8, u16be re-read OOB)
    is detected; (b) a Guntle-class byte-interleave half-read (in-bounds
    u16be re-read, nonzero even bytes) is NOT — the documented
    non-discrimination that defeats the proposed tie gate.
    """
    cases = [
        # 8 u16be refs [250..255, 0, 0]: every even byte 0x00, re-read
        # refs 250..255 >= elem 220 -> OOB. Signed: True.
        (
            bytes.fromhex("00fa00fb00fc00fd00fe00ff00000000"),
            220,
            True,
        ),
        # Guntle 3815992's real block: [0x0871, 0x093a, 0x08de, 0x0967]
        # x2, all in-bounds for elem 3990. Signed: False (the miss).
        (
            bytes.fromhex("0871093a08de0967") * 2,
            3990,
            False,
        ),
    ]
    ok = True
    for i, (data, elem, want) in enumerate(cases):
        got = u8_signature(data, 0, len(data) // 2, elem)
        hit = got["even_zero"] and got["u16_oob"]
        status = "ok" if hit == want else "FAIL"
        ok = ok and hit == want
        print(json.dumps({"case": i, "want": want, "got": hit,
                          "sig": got, "status": status}))
    return 0 if ok else 1


def main() -> int:
    paths = sys.argv[1:]
    if paths == ["--selftest"]:
        return _selftest()
    import catpart.geometry.vote as vote_mod

    orig_vote = vote_mod.vote_ref_width

    def probing_vote(data, n, candidates, element_count=None, normal=None,
                     elements=None, repeats_ranked=True):
        cands = list(candidates)
        won = orig_vote(data, n, cands, element_count=element_count,
                        normal=normal, elements=elements,
                        repeats_ranked=repeats_ranked)
        if won is None:
            return won
        won_width = won[2]
        keys = []
        for c in cands:
            refs = vote_mod.read_refs(data, c.counts_end, n, c.width, c.little)
            rep = vote_mod.groups_repeat(refs, c.tri_count, c.counts)
            if rep and not repeats_ranked:
                keys.append(None)
                continue
            oob = vote_mod.refs_oob(refs, element_count)
            skips = ({i for i, (_v, pt) in enumerate(elements) if pt is None}
                     if elements is not None else None)
            np_ = vote_mod.loop_plane_penalty(refs, c.tri_count, c.counts,
                                              normal, elements, skips)
            keys.append(vote_mod._rank_key(c, oob, rep, np_))
        # winner's key
        win_idx = next(i for i, c in enumerate(cands) if c.width == won_width
                       and keys[i] is not None)
        win_key = keys[win_idx]
        for i, c in enumerate(cands):
            if i == win_idx or keys[i] is None or c.width == won_width:
                continue
            k = keys[i]
            # full tie except the width slot (index 6)?
            if (k[:6] == win_key[:6] and k[7] == win_key[7]):
                sig = (u8_signature(data, c.counts_end, n, element_count)
                       if c.width == 1 else None)
                print(json.dumps({
                    "counts_end": c.counts_end,
                    "n": n,
                    "elem": element_count,
                    "tri": c.tri_count,
                    "relaxed": c.relaxed_u16,
                    "winner_width": won_width,
                    "narrow_width": c.width,
                    "narrow_exact": c.exact,
                    "winner_exact": cands[win_idx].exact,
                    "narrow_refs4": vote_mod.read_refs(
                        data, c.counts_end, min(n, 4), c.width, c.little),
                    "winner_refs4": won[0][:4],
                    "sig": sig,
                }, ensure_ascii=False), flush=True)
        return won

    vote_mod.vote_ref_width = probing_vote

    import catpart.geometry.composite as comp
    comp.vote_ref_width = probing_vote

    from catpart.fitness.runner import _measure_l2
    from pathlib import Path

    for p in paths:
        path = Path(p)
        rec = _measure_l2(path, Path("/tmp") / ("w18sig-" + path.stem + ".ply"))
        print(json.dumps({"file": str(path), "status": rec["status"],
                          "failed_check": rec["failed_check"],
                          "triangles": rec["triangle_count"]},
                         ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
