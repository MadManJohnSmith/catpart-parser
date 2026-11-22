#!/usr/bin/env python3
"""W7-B triage probe: instrument the width vote of the ONE diverging
extended record (offset 229647190 in head_ia 231 MB, ae85fae7) — dump
every candidate's rank key the Python vote sees for that record only.
"""

import sys

TARGET = 229647190


def main() -> int:
    path = sys.argv[1]
    import catpart.geometry.composite as comp
    import catpart.geometry.vote as vote_mod

    orig_parse = comp.parse_extended_facet_records
    orig_vote = vote_mod.vote_ref_width
    state = {"active": False}

    def wrapped_parse(data, lo, hi, element_count=None, elements=None,
                      shipped_spans=()):
        state["active"] = lo <= TARGET < hi
        try:
            return orig_parse(data, lo, hi, element_count,
                              elements=elements, shipped_spans=shipped_spans)
        finally:
            state["active"] = False

    def vote_probe(data, n, candidates, element_count=None, normal=None,
                   elements=None, repeats_ranked=True):
        cands = list(candidates)
        if state["active"] and any(c.counts_end > TARGET for c in cands) and \
                all(c.counts_end - TARGET < 4_000_000 for c in cands):
            print(f"--- vote call: n={n} elem_count={element_count} "
                  f"repeats_ranked={repeats_ranked} normal={normal is not None}")
            for c in cands:
                refs = vote_mod.read_refs(data, c.counts_end, n, c.width, c.little)
                repeats = vote_mod.groups_repeat(refs, c.tri_count, c.counts)
                oob = vote_mod.refs_oob(refs, element_count)
                skips = ({i for i, (_v, pt) in enumerate(elements) if pt is None}
                         if elements is not None else None)
                np = vote_mod.loop_plane_penalty(refs, c.tri_count, c.counts,
                                                normal, elements, skips)
                key = vote_mod._rank_key(c, oob, repeats, np)
                print(f"  cand w={c.width} end={c.end} exact={c.exact} "
                      f"counts_end={c.counts_end} oob={oob} repeats={repeats} "
                      f"nonplanar={np} key={key}")
        return orig_vote(data, n, cands, element_count=element_count,
                         normal=normal, elements=elements,
                         repeats_ranked=repeats_ranked)

    comp.parse_extended_facet_records = wrapped_parse
    comp.vote_ref_width = vote_probe

    from catpart.cli import main_export
    sys.argv = ["catpart-export", path, "-o", "/tmp/w7b-run/probe-py.ply"]
    return main_export()


if __name__ == "__main__":
    sys.exit(main())
