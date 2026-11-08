"""The minimal invariants over the ``catpart-inspect`` output (C1).

The clean-parse checklist (Spec C): exit 0 + schema-valid + invariants.
The v1 output can express evidence-backed invariants beyond v0's single
dword check; each invariant cites the evidence note and rates that make
it a corpus-wide law within its stated scope. Tested directly (the
module is a documented seam of the fitness runner, like
``catpart.version``) and through the runner classification in
``test_fitness_runner.py``.
"""

from __future__ import annotations

import pytest

from catpart.fitness.invariants import INVARIANTS, check_invariants


def v1_report(**overrides) -> dict:
    """A minimal schema-valid v1 report, structurally genuine by default."""
    report = {
        "schema_version": 1,
        "magic": "V5_CFV2",
        "header_dword": 1024,
        "header_dword12": 4096,
        "ff8_at_16_24": True,
        "header_dword16": None,
        "header_dword20": None,
        "file_size": 5120,
        "detected_version": "V5R19SP0HF0",
        "kind": "part",
        "containers": [
            {
                "name": "CATPrtCont",
                "parent_name": "CATProdCont",
                "table_id": 196609,
                "index": 1,
                "stream_id": 1,
                "weight": 11,
                "guid": "0" * 32,
            }
        ],
        "trailer": {
            "a": 1,
            "registration_offset": 256,
            "c": 0xE7,
            "d": 0xE7,
            "e": 0,
            "f": 0,
            "tail_region_length": 4096,
            "registration": {
                "tag": "N",
                "company": "DASSAULT-SYSTEMES",
                "product": "CATIA",
                "code": "041803",
            },
        },
    }
    report.update(overrides)
    return report


def test_v1_invariants_exist_with_evidence_citing_names() -> None:
    names = [name for name, _ in INVARIANTS]
    assert names == [
        "header-dword-below-file-size",
        "magic-v5-cfv2",
        "tail-region-chain",
        "trailer-constants",
        "container-kind-known",
    ]


def test_all_invariants_hold_on_a_genuine_report() -> None:
    assert check_invariants(v1_report()) is None


# --- magic (Phase 1 evidence: 1818/1818 magic_ok files; 6 known exceptions) --


@pytest.mark.parametrize("magic", ["V5_CFV2", "XX_CFV2", "", "V5_CFV2X"])
def test_magic_invariant(magic: str) -> None:
    failure = check_invariants(v1_report(magic=magic))
    if magic == "V5_CFV2":
        assert failure is None
    else:
        assert failure is not None
        assert failure.startswith("magic-v5-cfv2:")


# --- tail-region chain (law H1, scoped to the trailer being present) --------


def test_tail_region_chain_holds() -> None:
    report = v1_report(header_dword=1024, header_dword12=4096, file_size=5120)
    assert check_invariants(report) is None


def test_tail_region_chain_dword_sum_violation() -> None:
    report = v1_report(header_dword=1024, header_dword12=4096, file_size=6000)
    failure = check_invariants(report)
    assert failure is not None
    assert failure.startswith("tail-region-chain:")


def test_tail_region_chain_trailer_g_violation() -> None:
    report = v1_report(
        header_dword=1024, header_dword12=4096, file_size=5120
    )
    report["trailer"]["tail_region_length"] = 4095
    failure = check_invariants(report)
    assert failure is not None
    assert failure.startswith("tail-region-chain:")


def test_tail_region_chain_not_applicable_without_trailer() -> None:
    # The laws are scoped to CB__END-ending files; without a trailer the
    # chain is not checkable and does not fire (the 262-file no-trailer
    # family stays clean on this invariant).
    report = v1_report(trailer=None)
    assert check_invariants(report) is None


# --- trailer constants (A==1, C==D: 1556/1556 CB__END-ending files) ---------


def test_trailer_constants_a_violation() -> None:
    report = v1_report()
    report["trailer"]["a"] = 2
    failure = check_invariants(report)
    assert failure is not None
    assert failure.startswith("trailer-constants:")


def test_trailer_constants_c_d_violation() -> None:
    report = v1_report()
    report["trailer"]["d"] = 0xE8
    failure = check_invariants(report)
    assert failure is not None
    assert failure.startswith("trailer-constants:")


def test_trailer_constants_not_applicable_without_trailer() -> None:
    assert check_invariants(v1_report(trailer=None)) is None


def test_trailer_e_is_not_enforced() -> None:
    # E is 0 on 1555/1556 files only - the one exception is real (a
    # dual-region file), so E is reported as-is, never an invariant.
    report = v1_report()
    report["trailer"]["e"] = 4089
    assert check_invariants(report) is None


# --- kind known when the table is present (kind law K1: 1810/1810) ----------


def test_kind_known_with_containers() -> None:
    assert check_invariants(v1_report(kind="part")) is None
    assert check_invariants(v1_report(kind="product")) is None


def test_kind_unknown_without_table_is_clean() -> None:
    # The 8 no-table corpus files: kind unknown, containers empty.
    report = v1_report(kind="unknown", containers=[])
    assert check_invariants(report) is None


def test_kind_unknown_with_table_violates() -> None:
    # A with-table file must yield part or product (0/1810 corpus
    # counterexamples); unknown here means the parse contradicts the
    # documented law.
    report = v1_report(kind="unknown")
    failure = check_invariants(report)
    assert failure is not None
    assert failure.startswith("container-kind-known:")


# --- units-present: defined, NOT enforced (C3 phase A documented negative) --


def test_units_present_is_not_enforced_without_a_documented_claim() -> None:
    # The clean-parse checklist names "units present"; C3 phase A probed
    # the two decoded territories for a model unit system and found none
    # (docs/evidence/2026-11-08-units-names-probe.md), so the invariant
    # is defined with its documented exceptions (C2 precedent) and no
    # file is penalized: a report without any units field is clean.
    assert "units-present" not in [name for name, _ in INVARIANTS]
    report = v1_report()
    report.pop("document_name", None)
    assert check_invariants(report) is None


def test_units_present_unaffected_by_document_name() -> None:
    # document_name (the adopted name claim) carries no units semantics:
    # present or null, the checklist outcome is the same.
    assert check_invariants(v1_report(document_name="Part1.CATPart")) is None
    assert check_invariants(v1_report(document_name=None)) is None
