"""L3 construct-coverage scorer (ticket #58, BR6 / Phase 7, Spec G #47).

Two layers, no mocks:

- the real-repo run scores the committed artifacts and pins the numbers the
  evidence note quotes (23/23 resolved, no pending rows, no-regret context read
  from the last accepted history row without appending);
- failure injection over copies of those same committed CSVs proves the
  scorer can reject an uncited row, an unknown construct, a changed
  denominator, population drift, a declared label/construct that disagrees
  with the cited row and a landed artifact behind a pending row — the "no
  status without a citation" contract must be able to fail.

Everything runs corpus-free: the scorer reads repository files only, and the
fixtures are byte copies of them.
"""

from __future__ import annotations

import csv
import dataclasses
import json
import subprocess
import sys
from pathlib import Path

import pytest

from catpart.fitness import FitnessError
from catpart.fitness.history import load_last_accepted_row
from catpart.fitness.l3 import (
    CANDIDATE,
    DECODED,
    DENOMINATOR_TOTAL,
    DOCUMENTED_NEGATIVE,
    DOCUMENTED_OPEN,
    FULL_CORPUS_PARTS,
    L2_PASS_PARTS,
    PENDING_MERGE,
    RESOLUTION_REGISTRY,
    Resolution,
    VOCABULARY_PATH,
    L3Error,
    dumps,
    render_summary,
    score_l3,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "triage" / "score_l3_constructs.py"
BR2_CLAIMS = "docs/evidence/data/br2-planar-claims.csv"
BR3_CLAIMS = "docs/evidence/data/br3-curves-claims.csv"
BR4_CLAIMS = "docs/evidence/data/br4-quadrics-claims.csv"
BR5_CLAIMS = "docs/evidence/data/br5-cgm-nurbs-claims.csv"
SHELL_CLAIMS = "docs/evidence/data/br6-shell-claims.csv"
ARTIFACTS = (
    VOCABULARY_PATH,
    BR2_CLAIMS,
    BR3_CLAIMS,
    BR4_CLAIMS,
    BR5_CLAIMS,
    SHELL_CLAIMS,
)
REGISTRY_BY_ID = {row.construct_id: row for row in RESOLUTION_REGISTRY}


def fixture_root(tmp_path: Path) -> Path:
    """A root holding byte copies of the committed artifacts the scorer reads."""
    root = tmp_path / "repo"
    for rel in ARTIFACTS:
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((REPO_ROOT / rel).read_bytes())
    return root


def with_row(construct_id: str, replacement: Resolution) -> tuple[Resolution, ...]:
    """Return a registry copy with one construct's row replaced."""
    return tuple(
        replacement if row.construct_id == construct_id else row
        for row in RESOLUTION_REGISTRY
    )


def edit_claim(root: Path, rel: str, claim_id: str, **fields: str) -> None:
    """Rewrite one claims-CSV row's fields in a fixture copy."""
    path = root / rel
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        header = list(reader.fieldnames or [])
        rows = list(reader)
    touched = 0
    for row in rows:
        if row["claim"] == claim_id:
            row.update(fields)
            touched += 1
    assert touched == 1, f"{claim_id} appears {touched} times in {rel}"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


# --- real-repo run: the committed headline -------------------------------


def test_real_repo_headline_is_the_frozen_denominator_coverage() -> None:
    score = score_l3(REPO_ROOT)
    document = score.to_json()
    assert document["denominator"]["frozen_rows"] == DENOMINATOR_TOTAL == 23
    assert document["denominator"]["source"] == VOCABULARY_PATH
    assert document["denominator"]["sha256"] == (
        "2b2f54d9fbabe0f09082357e0469a22286fc2e48e4930098c782a2317c9ff611"
    ), "the vocabulary pin moved: regenerate BR6L3-24 before accepting"
    assert score.total == 23
    assert score.resolved == 23
    assert document["headline"] == {
        "resolved": 23,
        "total": 23,
        "rate": 1.0,
        "exact": "23/23",
    }
    assert document["by_outcome"] == {
        "decoded": 14,
        "documented-negative": 3,
        "documented-open": 4,
        "candidate": 2,
        "pending-merge": 0,
    }
    assert score.resolved + score.by_outcome[PENDING_MERGE] == score.total


def test_real_repo_every_row_cites_a_claim_in_a_committed_csv() -> None:
    score = score_l3(REPO_ROOT)
    assert score.by_outcome[PENDING_MERGE] == 0
    for row in score.constructs:
        assert row.outcome != PENDING_MERGE, row.construct_id
        assert row.claim_id, row.construct_id
        assert (REPO_ROOT / row.evidence).is_file(), row.evidence
        assert row.citation is not None, row.construct_id
        assert row.citation["scope"], row.construct_id
        assert row.citation["label"] in {
            "fact",
            "established",
            "candidate",
            "open (ceiling)",
        }, row.construct_id


def test_real_repo_construct_verdicts_are_the_committed_ones() -> None:
    score = score_l3(REPO_ROOT)
    outcomes = {row.construct_id: row.outcome for row in score.constructs}
    assert outcomes["TOP-01"] == DECODED
    assert outcomes["TOP-02"] == DOCUMENTED_NEGATIVE
    assert outcomes["TOP-03"] == DECODED
    assert outcomes["TOP-04"] == DECODED
    assert outcomes["CRV-04"] == DOCUMENTED_OPEN
    assert outcomes["CRV-05"] == DOCUMENTED_OPEN
    assert outcomes["CRV-06"] == DOCUMENTED_NEGATIVE
    assert outcomes["CRV-08"] == CANDIDATE
    assert outcomes["SRF-02"] == DECODED
    assert outcomes["SRF-03"] == DECODED
    assert outcomes["SRF-04"] == DECODED
    assert outcomes["SRF-05"] == DOCUMENTED_OPEN
    assert outcomes["SRF-06"] == DOCUMENTED_OPEN
    assert outcomes["SRF-07"] == CANDIDATE
    assert outcomes["SRF-08"] == DOCUMENTED_NEGATIVE


def test_real_repo_family_counts_cover_the_23_constructs() -> None:
    document = score_l3(REPO_ROOT).to_json()
    assert document["denominator"]["family_counts"] == {
        "topology": 7,
        "curve": 8,
        "surface": 8,
    }
    assert sum(document["denominator"]["family_counts"].values()) == DENOMINATOR_TOTAL


def test_corpus_rate_is_reported_alongside_and_never_gates() -> None:
    document = score_l3(REPO_ROOT).to_json()
    context = document["corpus_context"]
    assert context["gating"] is False
    assert context["corpus_parts"] == FULL_CORPUS_PARTS
    assert context["l2_pass_parts"] == L2_PASS_PARTS
    assert context["construct_file_slots"] == DENOMINATOR_TOTAL * FULL_CORPUS_PARTS
    # The headline is the resolved-construct ratio, never the corpus presence
    # rate: a catalogue with a different prevalence cannot move it.
    assert document["headline"]["rate"] == 1.0
    assert document["headline"]["rate"] != context["presence_rate"]
    assert context["construct_file_slots_used"] == sum(
        row["census"]["corpus_occurrences"] for row in document["constructs"]
    )


def test_no_regret_context_reads_the_last_accepted_row_without_appending() -> None:
    history = REPO_ROOT / "fitness" / "history.jsonl"
    before = history.read_bytes()
    document = score_l3(REPO_ROOT).to_json()
    context = document["no_regret"]
    expected = load_last_accepted_row(history)
    assert expected is not None
    assert context["run_id"] == expected["run_id"]
    assert context["L1"] == expected["scalars"]["L1"]
    assert context["L2"] == expected["scalars"]["L2"]
    assert context["read_only"] is True
    assert history.read_bytes() == before, "the scorer must never append to history.jsonl"


def test_scoring_is_deterministic() -> None:
    first = dumps(score_l3(REPO_ROOT))
    second = dumps(score_l3(REPO_ROOT))
    assert first == second
    json.loads(first)  # the document is valid JSON


def test_summary_reports_headline_outcomes_and_corpus_rate() -> None:
    summary = render_summary(score_l3(REPO_ROOT))
    assert "23/23 resolved" in summary
    assert "decoded 14" in summary
    assert "documented-open 4" in summary
    assert "candidate 2" in summary
    assert "documented-negative 3" in summary
    assert "pending-merge 0" in summary
    assert "never gating" in summary
    assert "no-regret context" in summary
    assert "TOP-04" in summary and "SRF-08" in summary


# --- failure injection: no status without a citation ---------------------


def test_uncited_row_is_rejected_before_scoring() -> None:
    with pytest.raises(L3Error, match="requires the exact claim id"):
        Resolution(
            construct_id="TOP-04",
            outcome=DECODED,
            evidence=BR2_CLAIMS,
            claim_id="",
            owner="BR2",
        )


def test_claim_id_absent_from_the_cited_csv_is_rejected(tmp_path: Path) -> None:
    registry = with_row(
        "TOP-04",
        dataclasses.replace(
            REGISTRY_BY_ID["TOP-04"], claim_id="BR2-99_not_a_claim"
        ),
    )
    with pytest.raises(L3Error, match="BR2-99_not_a_claim.*is not"):
        score_l3(fixture_root(tmp_path), registry=registry)


def test_citation_with_a_contradicting_label_is_rejected(tmp_path: Path) -> None:
    # BR2-18 is labelled candidate; citing it as a decoded verdict is a
    # miscitation even though the claim id exists.
    registry = with_row(
        "TOP-04",
        dataclasses.replace(
            REGISTRY_BY_ID["TOP-04"],
            claim_id="BR2-18_triangle_list_normal_records",
        ),
    )
    with pytest.raises(L3Error, match="does not justify outcome"):
        score_l3(fixture_root(tmp_path), registry=registry)


def test_declared_claim_label_mismatch_is_rejected(tmp_path: Path) -> None:
    # BR5's TOP-02 ceiling row is labelled fact; declaring another token
    # must fail closed and name both values.
    registry = with_row(
        "TOP-02",
        dataclasses.replace(REGISTRY_BY_ID["TOP-02"], claim_label="candidate"),
    )
    with pytest.raises(
        L3Error, match="labelled 'fact', not the declared claim_label 'candidate'"
    ):
        score_l3(fixture_root(tmp_path), registry=registry)


def test_declared_claim_label_exact_match_is_accepted(tmp_path: Path) -> None:
    registry = with_row(
        "TOP-02",
        dataclasses.replace(REGISTRY_BY_ID["TOP-02"], claim_label="fact"),
    )
    score = score_l3(fixture_root(tmp_path), registry=registry)
    row = next(row for row in score.constructs if row.construct_id == "TOP-02")
    assert row.outcome == DOCUMENTED_NEGATIVE
    assert row.citation is not None
    assert row.citation["label"] == "fact"


def test_documented_negative_still_needs_the_declared_label(tmp_path: Path) -> None:
    # With no claim_label the outcome table governs: BR5's fact-labelled
    # ceiling row cannot justify documented-negative on its own.
    registry = with_row(
        "TOP-02",
        dataclasses.replace(REGISTRY_BY_ID["TOP-02"], claim_label=""),
    )
    with pytest.raises(L3Error, match="does not justify outcome"):
        score_l3(fixture_root(tmp_path), registry=registry)


def test_inherited_bound_needs_the_declared_claim_construct(tmp_path: Path) -> None:
    # SRF-06 inherits SRF-05's upper-bound row; without the declaration the
    # construct-attribution guard rejects the citation.
    registry = with_row(
        "SRF-06",
        dataclasses.replace(REGISTRY_BY_ID["SRF-06"], claim_construct=""),
    )
    with pytest.raises(L3Error, match="attributed to 'SRF-05'"):
        score_l3(fixture_root(tmp_path), registry=registry)


def test_declared_claim_construct_mismatch_is_rejected(tmp_path: Path) -> None:
    registry = with_row(
        "SRF-06",
        dataclasses.replace(REGISTRY_BY_ID["SRF-06"], claim_construct="SRF-06"),
    )
    with pytest.raises(
        L3Error, match="not the declared claim_construct 'SRF-06'"
    ):
        score_l3(fixture_root(tmp_path), registry=registry)


def test_ambiguous_claim_id_without_scope_is_rejected(tmp_path: Path) -> None:
    registry = with_row(
        "CRV-01",
        dataclasses.replace(REGISTRY_BY_ID["CRV-01"], claim_scope=""),
    )
    with pytest.raises(L3Error, match="appears 2 times"):
        score_l3(fixture_root(tmp_path), registry=registry)


def test_wrong_claim_scope_is_rejected(tmp_path: Path) -> None:
    registry = with_row(
        "CRV-01",
        dataclasses.replace(REGISTRY_BY_ID["CRV-01"], claim_scope="nowhere"),
    )
    with pytest.raises(L3Error, match="matches 0 rows"):
        score_l3(fixture_root(tmp_path), registry=registry)


def test_unique_claim_id_with_wrong_declared_scope_is_rejected(tmp_path: Path) -> None:
    # TOP-04's claim id is unique, so the scope filter must still run: a
    # declared scope that the selected row does not carry is a miscitation.
    registry = with_row(
        "TOP-04",
        dataclasses.replace(
            REGISTRY_BY_ID["TOP-04"], claim_scope="L2-pass population"
        ),
    )
    with pytest.raises(L3Error, match="not the declared"):
        score_l3(fixture_root(tmp_path), registry=registry)


def test_citation_to_another_constructs_row_is_rejected(tmp_path: Path) -> None:
    # The BR3 CSV declares each row's construct; citing CRV-03's row as
    # TOP-04's evidence must fail even though the id, scope and label agree.
    registry = with_row(
        "TOP-04",
        dataclasses.replace(
            REGISTRY_BY_ID["TOP-04"],
            evidence=BR3_CLAIMS,
            claim_id="C03_conic_decode_ok",
            claim_scope="corpus",
        ),
    )
    with pytest.raises(L3Error, match="attributed to 'CRV-03'"):
        score_l3(fixture_root(tmp_path), registry=registry)


def test_blank_label_is_rejected(tmp_path: Path) -> None:
    root = fixture_root(tmp_path)
    edit_claim(root, BR2_CLAIMS, "BR2-03_face_files_corpus", label="")
    with pytest.raises(L3Error, match="does not justify outcome"):
        score_l3(root)


def test_missing_evidence_csv_is_rejected(tmp_path: Path) -> None:
    registry = with_row(
        "TOP-04",
        dataclasses.replace(
            REGISTRY_BY_ID["TOP-04"], evidence="docs/evidence/data/br9-absent-claims.csv"
        ),
    )
    with pytest.raises(L3Error, match="does not exist"):
        score_l3(fixture_root(tmp_path), registry=registry)


def test_evidence_path_outside_docs_evidence_is_rejected(tmp_path: Path) -> None:
    registry = with_row(
        "TOP-04",
        dataclasses.replace(REGISTRY_BY_ID["TOP-04"], evidence="../br2-planar-claims.csv"),
    )
    with pytest.raises(L3Error, match="repo-relative"):
        score_l3(fixture_root(tmp_path), registry=registry)


def test_unknown_outcome_is_rejected() -> None:
    with pytest.raises(L3Error, match="unknown outcome"):
        Resolution(
            construct_id="TOP-04",
            outcome="probably-decoded",
            evidence=BR2_CLAIMS,
            claim_id="BR2-03_face_files_corpus",
            owner="BR2",
        )


# --- failure injection: denominator --------------------------------------


def test_unknown_construct_in_the_vocabulary_is_rejected(tmp_path: Path) -> None:
    root = fixture_root(tmp_path)
    registry = tuple(
        dataclasses.replace(row, construct_id="TOP-99")
        if row.construct_id == "TOP-04"
        else row
        for row in RESOLUTION_REGISTRY
    )
    with pytest.raises(L3Error, match="unknown construct"):
        score_l3(root, registry=registry)


def test_vocabulary_construct_without_a_registry_row_is_rejected(tmp_path: Path) -> None:
    root = fixture_root(tmp_path)
    with pytest.raises(L3Error, match="unknown construct"):
        score_l3(root, registry=RESOLUTION_REGISTRY[:-1])


def test_registry_row_without_a_vocabulary_construct_is_rejected(tmp_path: Path) -> None:
    root = fixture_root(tmp_path)
    extra = Resolution(
        construct_id="TOP-99",
        outcome=PENDING_MERGE,
        evidence="docs/evidence/data/br9-absent-claims.csv",
        claim_id="",
        owner="BR9",
    )
    with pytest.raises(L3Error, match="missing from the frozen vocabulary"):
        score_l3(root, registry=RESOLUTION_REGISTRY + (extra,))


def test_denominator_row_removed_is_rejected(tmp_path: Path) -> None:
    root = fixture_root(tmp_path)
    path = root / VOCABULARY_PATH
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    with pytest.raises(L3Error, match="missing from the frozen vocabulary"):
        score_l3(root)


def test_denominator_row_duplicated_is_rejected(tmp_path: Path) -> None:
    root = fixture_root(tmp_path)
    path = root / VOCABULARY_PATH
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(lines + lines[1:2]) + "\n", encoding="utf-8")
    with pytest.raises(L3Error, match="duplicate construct id"):
        score_l3(root)


def test_jointly_extended_denominator_is_rejected(tmp_path: Path) -> None:
    # A vocabulary row and a registry row added together would satisfy the
    # id-for-id match; the frozen-count guard must still reject the change.
    root = fixture_root(tmp_path)
    path = root / VOCABULARY_PATH
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        header = list(reader.fieldnames or [])
        rows = list(reader)
    rows.append(
        {
            "construct_id": "TOP-99",
            "family": "topology",
            "name": "Extra",
            "carrier_container": "none",
            "record_signature": "none",
            "semantic_type": "topology",
            "status": "frozen",
            "corpus_occurrences": "0",
            "rate_l2_pass": "1.0",
        }
    )
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    extra = Resolution(
        construct_id="TOP-99",
        outcome=PENDING_MERGE,
        evidence="docs/evidence/data/br9-absent-claims.csv",
        claim_id="",
        owner="BR9",
    )
    with pytest.raises(L3Error, match="frozen denominator is 24"):
        score_l3(root, registry=RESOLUTION_REGISTRY + (extra,))


def test_non_frozen_vocabulary_row_is_rejected(tmp_path: Path) -> None:
    root = fixture_root(tmp_path)
    path = root / VOCABULARY_PATH
    text = path.read_text(encoding="utf-8").replace(",frozen,", ",candidate,", 1)
    path.write_text(text, encoding="utf-8")
    with pytest.raises(L3Error, match="not frozen"):
        score_l3(root)


def test_population_anchor_drift_is_rejected(tmp_path: Path) -> None:
    root = fixture_root(tmp_path)
    edit_claim(root, BR2_CLAIMS, "BR2-03_face_files_corpus", observations="1441")
    with pytest.raises(L3Error, match="disagrees with the scorer population"):
        score_l3(root)


# --- failure injection: pending-merge is an absence marker ---------------


def test_pending_merge_is_not_counted_as_resolved(tmp_path: Path) -> None:
    registry = with_row(
        "TOP-04",
        dataclasses.replace(
            REGISTRY_BY_ID["TOP-04"],
            outcome=PENDING_MERGE,
            evidence="docs/evidence/data/br9-absent-claims.csv",
            claim_id="",
            claim_scope="",
        ),
    )
    score = score_l3(fixture_root(tmp_path), registry=registry)
    assert score.resolved == 22
    assert score.by_outcome[PENDING_MERGE] == 1
    row = next(row for row in score.constructs if row.construct_id == "TOP-04")
    assert row.citation is None
    assert row.claim_id == ""


def test_landed_evidence_behind_a_pending_row_is_rejected(tmp_path: Path) -> None:
    # BR2's claims CSV exists; a pending row pointing at it means evidence
    # landed but nobody resolved the row — the scorer must not silently
    # under-report the headline.
    registry = with_row(
        "TOP-04",
        dataclasses.replace(
            REGISTRY_BY_ID["TOP-04"],
            outcome=PENDING_MERGE,
            evidence=BR2_CLAIMS,
            claim_id="",
            claim_scope="",
        ),
    )
    with pytest.raises(L3Error, match="still pending-merge"):
        score_l3(fixture_root(tmp_path), registry=registry)


def test_pending_row_cannot_carry_a_claim_id() -> None:
    with pytest.raises(L3Error, match="cannot carry a claim id"):
        Resolution(
            construct_id="TOP-04",
            outcome=PENDING_MERGE,
            evidence=BR2_CLAIMS,
            claim_id="BR2-03_face_files_corpus",
            owner="BR2",
        )


def test_pending_row_cannot_carry_a_claim_label() -> None:
    with pytest.raises(L3Error, match="cannot carry a claim label"):
        Resolution(
            construct_id="TOP-04",
            outcome=PENDING_MERGE,
            evidence="docs/evidence/data/br9-absent-claims.csv",
            claim_id="",
            owner="BR9",
            claim_label="fact",
        )


# --- CLI contract --------------------------------------------------------


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT), "--root", str(REPO_ROOT), *args],
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_cli_writes_json_document_and_summary(tmp_path: Path) -> None:
    json_out = tmp_path / "l3.json"
    summary_out = tmp_path / "l3.txt"
    proc = run_cli("--json-out", str(json_out), "--summary-out", str(summary_out))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    document = json.loads(json_out.read_text(encoding="utf-8"))
    assert document["headline"]["exact"] == "23/23"
    summary = summary_out.read_text(encoding="utf-8")
    assert summary.startswith("L3 construct coverage (frozen denominator): 23/23")
    assert json_out.read_text(encoding="utf-8").endswith("\n")


def test_cli_defaults_to_json_on_stdout_and_summary_on_stderr() -> None:
    proc = run_cli()
    assert proc.returncode == 0, proc.stderr
    document = json.loads(proc.stdout)
    assert document["schema"] == "l3-construct-coverage-v0"
    assert "23/23 resolved" in proc.stderr


def test_cli_fails_closed_on_a_broken_root(tmp_path: Path) -> None:
    root = fixture_root(tmp_path)
    (root / VOCABULARY_PATH).unlink()
    proc = subprocess.run(
        [sys.executable, "-I", str(SCRIPT), "--root", str(root)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 1
    assert "score-l3: error:" in proc.stderr
    assert proc.stdout == ""


# --- the scorer's error type is a fitness error --------------------------


def test_l3_error_is_a_fitness_error() -> None:
    assert issubclass(L3Error, FitnessError)
