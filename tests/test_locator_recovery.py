"""Stage 3a: the locator recovery extension (G6 #34, the L5 lever).

Corpus-free external behavior on synthetic fixtures, one per recovery
family (seebody store, xdoclink store, overshoot tail, padded tail):
the locate-level provenance (:class:`catpart.geometry.store.StoreSpan`
``container``/``tail_law``), the classification through the package
export seam (``store_recovery`` on the success summary, the probe named
on the failure detail), the fail-closed negatives (a probe that matches
nothing stays ``missing-geometry-store``; a tail neither family recovers
stays ``malformed-store-header``) and the shipped-law byte-stability on
normal stores.

Census counterparts: docs/evidence/2026-11-10-l2-grind-classification.md
sections 5-6 (the recovery table and the two G1-documented tail
variants), docs/evidence/2026-11-09-nested-store.md (N10's families).
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


def locate_span(variant: str, container: str):
    """Locate the variant's store directly through the package API.

    Probes the named container's blocks the way the exporter does
    (stage 3a): ``locate_store`` over each block of the family, with
    the container tag recorded on the span.
    """
    data = build_fixture("part", seed=7, variant=variant)
    d8_outer = int.from_bytes(data[8:12], "big")
    blocks = store.valid_blocks(data)
    names = {"stdcont": "CATStdCont", "xdoclink": "CATXDocLinkCont", "seebody": "CATSeeBodyCont"}
    for blk in [b for b, nm in blocks if nm == names[container]]:
        span = store.locate_store(data, blk, blocks, d8_outer, container=container)
        if span is not None:
            return span
    return None


# --- locate-level provenance: one span per recovery family --------------

def test_seebody_store_locates_with_probe_provenance() -> None:
    span = locate_span("geometry-seebody-store", "seebody")
    assert span is not None
    assert span.container == "seebody"
    assert span.tail_law == "shipped"
    assert span.origin_kind == "v5header"
    assert span.body_lo == span.origin + store.HEADER_LEN
    assert span.body_hi == span.origin + int.from_bytes(
        build_fixture("part", seed=7, variant="geometry-seebody-store")[
            span.origin + 8 : span.origin + 12
        ],
        "big",
    )


def test_xdoclink_store_locates_with_probe_provenance() -> None:
    span = locate_span("geometry-xdoclink-store", "xdoclink")
    assert span is not None
    assert span.container == "xdoclink"
    assert span.tail_law == "shipped"
    # the store-less CATStdCont region locates nothing (G1 N10)
    assert locate_span("geometry-xdoclink-store", "stdcont") is None


def test_overshoot_tail_locates_under_the_relaxed_law() -> None:
    span = locate_span("geometry-overshoot-tail", "stdcont")
    assert span is not None
    assert span.container == "stdcont"
    assert span.tail_law == "overshoot"
    # k = 9: the header's dword8 overshoots the catalog magic; the
    # recovered tail is read from the true magic with length dword12.
    data = build_fixture("part", seed=7, variant="geometry-overshoot-tail")
    d8n = int.from_bytes(data[span.origin + 8 : span.origin + 12], "big")
    assert span.origin + d8n - span.body_hi == 9
    assert span.catalog_len == 52


def test_padded_tail_locates_under_the_relaxed_law() -> None:
    span = locate_span("geometry-padded-tail", "stdcont")
    assert span is not None
    assert span.container == "stdcont"
    assert span.tail_law == "padded"
    # the trailer sits inside the zero padding: the recovered tail ends
    # at its CB__END and G names the true catalog length (N4w).
    assert span.catalog_len == 52


# --- classify through the package export seam ---------------------------

def test_recovered_stores_export_through_the_probes(tmp_path: Path, capsys) -> None:
    # The four recovery families all decode the same 12-triangle box;
    # each summary names how the store was recovered.
    expected = {
        "geometry-seebody-store": {"container": "seebody", "tail_law": "shipped"},
        "geometry-xdoclink-store": {"container": "xdoclink", "tail_law": "shipped"},
        "geometry-overshoot-tail": {"container": "stdcont", "tail_law": "overshoot"},
        "geometry-padded-tail": {"container": "stdcont", "tail_law": "padded"},
    }
    for variant, recovery in expected.items():
        code, captured = run_export(tmp_path, capsys, variant)
        assert code == 0, (variant, captured.err)
        summary = json.loads(captured.out)
        validate(summary, load_schema(SUMMARY_SCHEMA))
        assert summary["vertex_count"] == 8
        assert summary["triangle_count"] == 12
        assert summary["mesh"]["closed"] is True
        assert summary["store_recovery"] == recovery


def test_recovered_composite_keeps_its_class_with_provenance(
    tmp_path: Path, capsys
) -> None:
    # A recovered seebody store carrying the 01 02 edge group fails the
    # composite gate exactly as a stdcont composite store would; the
    # error detail names the stage-2c N1 reason AND the probe (the
    # integrated stack: stage-2c classification + stage-3a provenance).
    code, captured = run_export(tmp_path, capsys, "geometry-seebody-composite")
    assert code == 1
    error = json.loads(captured.err)
    assert error["error_class"] == "undecoded-variant"
    assert "composite store without a token-bearing list node" in error["detail"]
    assert "recovered via the seebody probe, shipped tail law" in error["detail"]


# --- fail-closed: the probes change nothing they do not match -----------

def test_seebody_block_without_store_stays_missing(tmp_path: Path, capsys) -> None:
    # Census case 084841b3's shape: a seebody region carrying no store.
    code, captured = run_export(tmp_path, capsys, "geometry-seebody-empty")
    assert code == 1
    error = json.loads(captured.err)
    assert error["error_class"] == "missing-geometry-store"
    assert "CATXDocLinkCont/CATSeeBodyCont" in error["detail"]


def test_unrecoverable_tail_stays_malformed(tmp_path: Path, capsys) -> None:
    # Overshoot k = 9 but the corrected tail breaks C == D: neither
    # recovery family applies, the shipped rejection stands.
    code, captured = run_export(tmp_path, capsys, "geometry-overshoot-bad-tail")
    assert code == 1
    error = json.loads(captured.err)
    assert error["error_class"] == "malformed-store-header"
    assert "matches neither stage-3a recovery family" in error["detail"]


def test_plain_fixture_probe_scope_unchanged(tmp_path: Path, capsys) -> None:
    # No storage blocks at all: the extension probes nothing and the
    # classification is unchanged (the 112 no-CATStdCont corpus parts).
    code, captured = run_export(tmp_path, capsys, None)
    assert code == 1
    assert json.loads(captured.err)["error_class"] == "missing-geometry-store"


# --- shipped-law byte-stability on normal stores -------------------------

def test_normal_store_summary_has_no_recovery_record(tmp_path: Path, capsys) -> None:
    # The golden fixture exports through the shipped stdcont law: no
    # store_recovery key, identical decode (the suite's byte-stability
    # contract on pre-stage-3a behavior).
    code, captured = run_export(tmp_path, capsys, "geometry")
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    validate(summary, load_schema(SUMMARY_SCHEMA))
    assert "store_recovery" not in summary
    assert summary["triangle_count"] == 12
    assert summary["mesh"]["closed"] is True


def test_recovery_fixtures_classify_clean_through_fitness(tmp_path: Path) -> None:
    # Cross-ticket seam (A2/#14): the recovery fixtures are genuine
    # CATIA V5 containers — L1 reads them clean, the locate extension
    # does not touch container inventory.
    from catpart.fitness.runner import _classify_file

    for variant in (
        "geometry-seebody-store",
        "geometry-xdoclink-store",
        "geometry-overshoot-tail",
        "geometry-padded-tail",
    ):
        path = tmp_path / f"{variant}.CATPart"
        path.write_bytes(build_fixture("part", seed=4, variant=variant))
        classification, error, output = _classify_file(path)
        assert classification == "clean", (variant, error)
        assert output is not None and output["kind"] == "part"
