"""Stage 12: the other-container locator probe (G6 #34, 2026-11-13).

Corpus-free external behavior on synthetic fixtures: the stage-12
recovery family probes every remaining valid block whatever its
doc-type name — same locate law, same fail-closed rules, fired only
when the three named families found nothing. Positives (the store in a
``CATBRepModeContainer`` block exports, provenance names the block),
the gating pins (a store-less ``CATStdCont`` block does not block the
probe; a located ``CATStdCont`` store wins unchanged), and the
fail-closed negatives (recovered-then-composite-failing names the
block on the error detail; a broken tail stays
``malformed-store-header``).

Census counterparts: docs/evidence/2026-11-13-noncomposite-census.md
section 2 (53/178 recoverable; 12 export+pass; CATBRepModeContainer 39
/ CameraStartupContainer 8 / contmeasure 2 / four others 1 each).
"""

from __future__ import annotations

import json
from pathlib import Path

from catpart.geometry import store
from catpart.schema import load_schema
from catpart.schema.validate import validate
from fixtures_gen import build_fixture

SUMMARY_SCHEMA = "export-summary-v1"


def run_export(tmp_path: Path, capsys, variant: str, seed: int = 7):
    """Export one variant through the CLI seam; return (code, captured)."""
    from catpart.cli import main_export

    path = tmp_path / f"{variant}.CATPart"
    path.write_bytes(build_fixture("part", seed=seed, variant=variant))
    code = main_export([str(path)])
    return code, capsys.readouterr()


def locate_other_span(variant: str) -> store.StoreSpan | None:
    """Locate the variant's store the way the stage-12 family does:
    ``locate_store`` over every block that is none of the three named
    probe containers, with the ``other-container`` tag recorded."""
    data = build_fixture("part", seed=7, variant=variant)
    d8_outer = int.from_bytes(data[8:12], "big")
    blocks = store.valid_blocks(data)
    for blk, nm in blocks:
        if nm in store.NAMED_PROBE_CONTAINERS:
            continue
        span = store.locate_store(
            data, blk, blocks, d8_outer, container=store.CONTAINER_OTHER
        )
        if span is not None:
            return span
    return None


# --- locate-level provenance --------------------------------------------

def test_othercontainer_store_locates_with_probe_provenance() -> None:
    span = locate_other_span("geometry-othercontainer-store")
    assert span is not None
    assert span.container == "other-container"
    assert span.tail_law == "shipped"
    assert span.origin_kind == "v5header"
    assert span.body_lo == span.origin + store.HEADER_LEN


# --- classify through the package export seam ---------------------------

def test_othercontainer_store_exports_naming_the_block(
    tmp_path: Path, capsys
) -> None:
    # The stage-12 census's dominant shape: a full-signature store in a
    # CATBRepModeContainer region no earlier probe visits. The summary
    # names the family AND the block's own doc-type name.
    code, captured = run_export(tmp_path, capsys, "geometry-othercontainer-store")
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    validate(summary, load_schema(SUMMARY_SCHEMA))
    assert summary["vertex_count"] == 8
    assert summary["triangle_count"] == 12
    assert summary["mesh"]["closed"] is True
    assert summary["store_recovery"] == {
        "container": "other-container",
        "tail_law": "shipped",
        "container_name": "CATBRepModeContainer",
    }


def test_probe_fires_behind_a_storeless_stdcont_block(
    tmp_path: Path, capsys
) -> None:
    # Gating pin: a CATStdCont block carrying no store locates nothing
    # and does not block the stage-12 family (the corpus parts carry
    # store-less stdcont regions; xdoclink/seebody run first and find
    # nothing, then the other-container probe recovers).
    code, captured = run_export(
        tmp_path, capsys, "geometry-othercontainer-behind-empty-stdcont"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    assert summary["store_recovery"]["container"] == "other-container"


def test_located_stdcont_store_wins_unchanged(tmp_path: Path, capsys) -> None:
    # Precedence pin: with a real CATStdCont store present, the export
    # is the shipped law's — no probe runs, no store_recovery key (the
    # pre-stage-3a/pre-stage-12 byte-stability contract).
    code, captured = run_export(tmp_path, capsys, "geometry-stdcont-precedence")
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    assert "store_recovery" not in summary
    assert summary["triangle_count"] == 12
    assert summary["mesh"]["closed"] is True


# --- fail-closed: the new family changes nothing it does not match ------

def test_othercontainer_recovered_composite_names_block(
    tmp_path: Path, capsys
) -> None:
    # Recovered-then-failing keeps its classification with the probe
    # AND the block name on the error detail (the integrated stack:
    # stage-2c classification + stage-12 provenance).
    code, captured = run_export(tmp_path, capsys, "geometry-othercontainer-composite")
    assert code == 1
    error = json.loads(captured.err)
    assert error["error_class"] == "undecoded-variant"
    assert "composite store without a token-bearing list node" in error["detail"]
    assert (
        "recovered via the other-container (CATBRepModeContainer) probe, "
        "shipped tail law" in error["detail"]
    )


def test_othercontainer_bad_tail_stays_malformed(tmp_path: Path, capsys) -> None:
    # A V5_CFV2 header in an other-container region that neither tail
    # family recovers raises the shipped rejection — fail-closed, the
    # same rules as a broken stdcont header (corpus incidence of this
    # shape: 0 — census probe_malformed = 0).
    code, captured = run_export(tmp_path, capsys, "geometry-othercontainer-bad-tail")
    assert code == 1
    error = json.loads(captured.err)
    assert error["error_class"] == "malformed-store-header"
    assert "matches neither stage-3a recovery family" in error["detail"]


# --- provenance on the composite decode path ----------------------------

def test_recovered_composite_summary_carries_provenance(
    tmp_path: Path, capsys
) -> None:
    # The stage-12 census's 12 corpus passes are recovered stores that
    # EXPORT through the composite path — provenance must ride on
    # composite summaries too (not only the clean path's).
    code, captured = run_export(
        tmp_path, capsys, "geometry-othercontainer-composite-law"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    validate(summary, load_schema(SUMMARY_SCHEMA))
    assert summary["triangle_count"] >= 1
    assert "composite" in summary  # the composite decode path served it
    assert summary["store_recovery"] == {
        "container": "other-container",
        "tail_law": "shipped",
        "container_name": "CATBRepModeContainer",
    }


# --- L1 cross-check ------------------------------------------------------

def test_othercontainer_fixtures_classify_clean_through_fitness(
    tmp_path: Path,
) -> None:
    # The new fixtures are genuine CATIA V5 containers: L1 reads them
    # clean; the stage-12 probe does not touch container inventory.
    from catpart.fitness.runner import _classify_file

    for variant in (
        "geometry-othercontainer-store",
        "geometry-othercontainer-behind-empty-stdcont",
        "geometry-stdcont-precedence",
        "geometry-othercontainer-composite-law",
    ):
        path = tmp_path / f"{variant}.CATPart"
        path.write_bytes(build_fixture("part", seed=4, variant=variant))
        classification, error, output = _classify_file(path)
        assert classification == "clean", (variant, error)
        assert output is not None and output["kind"] == "part"
