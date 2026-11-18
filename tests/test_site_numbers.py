"""The public site's hard-coded fitness quotes, pinned to the committed row.

``site/index.html`` carries the L1 headline as static markup and rewrites
only the L2 Dev percentage at publish time from the embedded history
payload (``site/fitness.js``). The rest is hand-written, so it drifts
silently: the L2 held-out tile kept ``90.16% / 55 of 61`` for the whole
stage-15 landing even though run ``20261113T231506Z-c2ab64`` moved the
scalar to ``56/61``.

This pin reads every displayed L1/L2 number from the last accepted row of
``fitness/history.jsonl`` — the committed source the rest of the ladder
already trusts — and fails the gate when a new accepted row is not
mirrored on the site. Corpus-free by construction: the history and the
pages are both committed artifacts.

Formatting follows the pages' own convention: percentages to two
decimals, pass/total counts with thousands separators on the index tiles.
"""

from __future__ import annotations

import re
from pathlib import Path

from catpart.fitness.history import load_last_accepted_row

REPO_ROOT = Path(__file__).resolve().parents[1]
HISTORY_PATH = REPO_ROOT / "fitness" / "history.jsonl"
INDEX_PATH = REPO_ROOT / "site" / "index.html"
GRIND_PATH = REPO_ROOT / "site" / "grind.html"

#: One index stat tile: label, value cell (the unit span carries the '%'),
#: detail line. Pages never nest markup inside these three cells.
_STAT = re.compile(
    r'<div class="stat"><div class="k">(?P<label>[^<]+)</div>'
    r'<div class="v[^"]*"[^>]*>(?P<value>[^<]*)<span class="unit">%</span></div>'
    r'<div class="d">(?P<detail>[^<]*)</div></div>'
)


def pct(rate: float) -> str:
    """A rate as the pages print it: two decimals, never a bare fraction."""
    return f"{rate * 100:.2f}"


def num(count: int) -> str:
    """A pass/total count as the index tiles print it (thousands separator)."""
    return f"{count:,}"


def last_row() -> dict:
    row = load_last_accepted_row(HISTORY_PATH)
    assert row is not None, f"{HISTORY_PATH}: no accepted row to quote"
    return row


def stat_tiles(page: str) -> dict[str, tuple[str, str]]:
    tiles = {
        match.group("label").strip(): (match.group("value"), match.group("detail"))
        for match in _STAT.finditer(page)
    }
    assert tiles, f"{INDEX_PATH}: no stat tiles parsed — the tile markup changed shape"
    return tiles


def test_l1_tile_quotes_the_last_accepted_row() -> None:
    l1 = last_row()["scalars"]["L1"]
    dev, held_out = l1["dev"], l1["held-out"]
    value, detail = stat_tiles(INDEX_PATH.read_text(encoding="utf-8"))["L1 clean-parse (Dev)"]

    assert value == pct(dev["rate"])
    assert detail == (
        f"{num(dev['clean'])} / {num(dev['total'])} files"
        f" · held-out {held_out['clean']}/{held_out['total']}"
    )


def test_l2_held_out_tile_quotes_the_last_accepted_row() -> None:
    # The tile that drifted: static percentage plus pass/total prose.
    l2 = last_row()["scalars"]["L2"]
    held_out = l2["held-out"]
    value, detail = stat_tiles(INDEX_PATH.read_text(encoding="utf-8"))["L2 held-out"]

    assert value == pct(held_out["rate"])
    assert detail == f"{held_out['pass']} / {held_out['total']} unseen parts pass sanity"


def test_l2_dev_tile_keeps_one_live_source() -> None:
    # Dev is rewritten from the published payload, so its value cell must
    # stay a placeholder: a second hard-coded copy is how the held-out tile
    # went stale. The caption is static and must match the committed row.
    l2 = last_row()["scalars"]["L2"]
    dev = l2["dev"]
    value, detail = stat_tiles(INDEX_PATH.read_text(encoding="utf-8"))["L2 geometry-sanity (Dev)"]

    assert not any(char.isdigit() for char in value), (
        f"the L2 Dev value cell hard-codes {value!r}; it is filled at publish time"
    )
    assert detail == (
        f"{num(dev['pass'])} / {num(dev['total'])} parts"
        f" · bar re-adjusted {pct(dev['rate'])}%"
    )


def test_roadmap_pill_and_chart_legends_quote_the_committed_populations() -> None:
    # The L2 roadmap row and the two chart legend entries are the other
    # static quotes of the same scalar's pass/total pairs.
    l2 = last_row()["scalars"]["L2"]
    dev, held_out = l2["dev"], l2["held-out"]
    page = INDEX_PATH.read_text(encoding="utf-8")

    assert f'<span class="pill good">{pct(dev["rate"])}% · closed</span>' in page
    assert f"L2 dev ({num(dev['total'])} parts)" in page
    assert f"L2 held-out ({held_out['total']} parts)" in page


def test_every_static_percentage_on_the_index_is_in_the_committed_row() -> None:
    # The drift shape is a percentage from an older accepted row left
    # behind next to the current one. Whatever the markup grows, every
    # stat value and roadmap pill must still be one of the scalars the
    # last accepted row records.
    scalars = last_row()["scalars"]
    known = {
        pct(scalars["L1"]["dev"]["rate"]),
        pct(scalars["L1"]["held-out"]["rate"]),
        pct(scalars["L2"]["dev"]["rate"]),
        pct(scalars["L2"]["held-out"]["rate"]),
    }
    page = INDEX_PATH.read_text(encoding="utf-8")
    displayed = set(
        re.findall(r'<div class="v[^"]*"[^>]*>(\d+\.\d{2})<span class="unit">%</span>', page)
        + re.findall(r'<span class="pill[^"]*">(\d+\.\d{2})%', page)
    )

    assert displayed, "no static percentages found on site/index.html"
    assert displayed <= known, (
        f"site/index.html displays {sorted(displayed - known)} from an older "
        f"accepted row; the last accepted row records {sorted(known)}"
    )


def test_grind_headline_quotes_the_last_accepted_l2_rate() -> None:
    # grind.html's lead sentence states the climb's current endpoint; it is
    # the only other page quoting a fitness percentage in prose.
    l2 = last_row()["scalars"]["L2"]
    lead = " ".join(GRIND_PATH.read_text(encoding="utf-8").split())
    match = re.search(r"to (\d+\.\d{2})% ", lead)
    assert match, f"{GRIND_PATH}: the climb headline no longer quotes a percentage"
    assert match.group(1) == pct(l2["dev"]["rate"])
