"""L3 construct-coverage fitness scorer (ADR-0001, Phase 7 / Spec G #47, BR6).

ADR-0001 defines L3 as *construct coverage*. ROADMAP Phase 7's finite-making
amendment pins the denominator to the vocabulary frozen by the BR1 census
(``docs/evidence/data/brep-construct-vocabulary.csv``, 23 constructs): the
headline is ``resolved / 23``, and the corpus-side prevalence rate is
reported alongside but **never gates**.

This module reads committed artifacts only — the frozen vocabulary CSV, the
declarative :data:`RESOLUTION_REGISTRY` and the per-BR claims CSVs — so a CI
run is deterministic and corpus-free. It never decodes a byte: each construct
row delegates its verdict to exactly one claim row in one committed claims
CSV, and the row is rejected when that citation is missing, unreadable or
inconsistent with the declared outcome.

Outcome enum (ticket #58):

``decoded``
    A decoder with validated structure landed; the cited claim carries the
    measured decode/presence rate.
``documented-negative``
    Closed with a documented negative plus ceiling arithmetic.
``documented-open``
    Open with published ceiling arithmetic (Phase 7 accepts this as resolved).
``candidate``
    Evidence landed, semantics still open; the cited claim is labelled
    ``candidate``.
``pending-merge``
    The governing per-BR claims CSV is absent at this commit. This is an
    *absence marker*, not a status: it is never counted as resolved, and it
    names the artifact the owning ticket must land.

Extension point (requirement of ticket #58 / BR6)
-------------------------------------------------
Every per-construct verdict is one row of :data:`RESOLUTION_REGISTRY`. Adding
BR4/BR5 (or the BR6 shell slice) after those branches merge means editing
that table only — never the scoring logic:

1. replace the construct's ``pending-merge`` row with its resolved outcome,
   the committed claims CSV path in ``evidence`` and the exact ``claim_id``;
2. re-run :func:`score_l3` and the claims-CSV hygiene checker.

A ``pending-merge`` row whose ``evidence`` file does appear while the row is
still pending fails closed: evidence landed but nobody resolved the row, so
silently ignoring it would under-report the headline.
"""

from __future__ import annotations

import csv
import dataclasses
import hashlib
import json
from fractions import Fraction
from pathlib import Path

from catpart.fitness import FitnessError
from catpart.fitness.history import load_last_accepted_row

#: Repo-relative frozen denominator (BR1 census, ticket #48).
VOCABULARY_PATH = "docs/evidence/data/brep-construct-vocabulary.csv"

#: Repo-relative append-only fitness history (read only; never appended here).
HISTORY_PATH = "fitness/history.jsonl"

#: The frozen construct count (BR1 / Spec G #47). A vocabulary file that no
#: longer carries exactly these rows is a denominator change, not a rerun.
DENOMINATOR_TOTAL = 23

#: Full-corpus and L2-pass populations, cross-checked below against committed
#: claim rows so the two constants cannot drift from the artifacts.
FULL_CORPUS_PARTS = 1442
L2_PASS_PARTS = 1089

#: Committed claim rows that anchor the two population constants above.
#: ``(claims CSV, claim id, expected observations)``.
POPULATION_ANCHORS: tuple[tuple[str, str, int], ...] = (
    ("docs/evidence/data/br2-planar-claims.csv", "BR2-03_face_files_corpus", FULL_CORPUS_PARTS),
    ("docs/evidence/data/br2-planar-claims.csv", "BR2-01_face_files_l2_pass", L2_PASS_PARTS),
)

#: The four adjudicated outcomes (ticket #58) and the pending-merge absence
#: marker: a resolved row is one of the former, cited by a claim id.
DECODED = "decoded"
DOCUMENTED_NEGATIVE = "documented-negative"
DOCUMENTED_OPEN = "documented-open"
CANDIDATE = "candidate"
#: Absence marker (see module docstring): never resolved.
PENDING_MERGE = "pending-merge"

OUTCOME_ORDER: tuple[str, ...] = (
    DECODED,
    DOCUMENTED_NEGATIVE,
    DOCUMENTED_OPEN,
    CANDIDATE,
    PENDING_MERGE,
)
RESOLVED_OUTCOMES = frozenset(OUTCOME_ORDER) - {PENDING_MERGE}

#: Claim ``label`` values each outcome may cite. Labels are the claims CSV's
#: own confidence vocabulary (BR2: fact/candidate; BR3: established/
#: candidate/open (ceiling)); a citation whose label contradicts the declared
#: outcome is a miscitation, so it fails closed.
LABELS_BY_OUTCOME: dict[str, frozenset[str]] = {
    DECODED: frozenset({"fact", "established"}),
    DOCUMENTED_NEGATIVE: frozenset({"negative", "documented-negative"}),
    DOCUMENTED_OPEN: frozenset({"open", "open (ceiling)", "documented-open"}),
    CANDIDATE: frozenset({"candidate"}),
}

VOCABULARY_COLUMNS: tuple[str, ...] = (
    "construct_id",
    "family",
    "name",
    "carrier_container",
    "record_signature",
    "semantic_type",
    "status",
    "corpus_occurrences",
    "rate_l2_pass",
)

SCHEMA = "l3-construct-coverage-v0"


class L3Error(FitnessError):
    """The L3 headline cannot be scored from the committed artifacts.

    Raised for operator-facing failures: a changed denominator, a registry
    row without a live citation, a pending row whose evidence already landed,
    a malformed vocabulary/claims artifact, or a population anchor drift.
    """


@dataclasses.dataclass(frozen=True)
class Resolution:
    """One construct's declarative verdict (the registry row).

    ``evidence`` is repo-relative and must live under ``docs/evidence/``.
    ``claim_id`` is the exact row id inside that CSV; ``pending-merge`` rows
    carry an empty ``claim_id`` and the path the owning ticket must land.
    ``claim_scope`` disambiguates the claim ids that BR3 records once per
    scope (``corpus`` / ``l2-pass``); it is required exactly when the id is
    not unique in its CSV. ``owner`` is the BR ticket tag that owns the
    verdict.
    """

    construct_id: str
    outcome: str
    evidence: str
    claim_id: str
    owner: str
    claim_scope: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        if self.outcome not in OUTCOME_ORDER:
            raise L3Error(
                f"registry row {self.construct_id}: unknown outcome "
                f"{self.outcome!r} (expected one of {', '.join(OUTCOME_ORDER)})"
            )
        if self.outcome == PENDING_MERGE:
            if self.claim_id:
                raise L3Error(
                    f"registry row {self.construct_id}: a pending-merge row "
                    "cannot carry a claim id"
                )
            if self.claim_scope:
                raise L3Error(
                    f"registry row {self.construct_id}: a pending-merge row "
                    "cannot carry a claim scope"
                )
        elif not self.claim_id.strip():
            raise L3Error(
                f"registry row {self.construct_id}: outcome {self.outcome!r} "
                "requires the exact claim id that justifies it"
            )


#: The declarative per-construct resolution table — THE extension point.
#:
#: BR2/BR3 rows are resolvable at this base commit. BR4 (SRF-02..SRF-07),
#: BR5 (TOP-01, TOP-02, CRV-06, SRF-08) and the BR6 shell slice (TOP-03) are
#: pending-merge: their claims CSVs are absent here, so no verdict is
#: invented. After those merges land, replace each pending row with its
#: ``outcome`` + ``claim_id`` (see the module docstring).
RESOLUTION_REGISTRY: tuple[Resolution, ...] = (
    # --- pending-merge: governing claims CSV absent at this base commit ----
    Resolution(
        construct_id="TOP-01",
        outcome=PENDING_MERGE,
        evidence="docs/evidence/data/br5-cgm-nurbs-claims.csv",
        claim_id="",
        owner="BR5",
        note="body carrier lands with the BR5 CGM/NURBS merge",
    ),
    Resolution(
        construct_id="TOP-02",
        outcome=PENDING_MERGE,
        evidence="docs/evidence/data/br5-cgm-nurbs-claims.csv",
        claim_id="",
        owner="BR5",
        note="lump closure lands with the BR5 CGM/NURBS merge",
    ),
    Resolution(
        construct_id="TOP-03",
        outcome=PENDING_MERGE,
        evidence="docs/evidence/data/br6-shell-claims.csv",
        claim_id="",
        owner="BR6-shell",
        note=(
            "shell census lands with the BR6 shell slice; the expected artifact "
            "name is declared here and corrected at integration if the slice "
            "commits another"
        ),
    ),
    Resolution(
        construct_id="CRV-06",
        outcome=PENDING_MERGE,
        evidence="docs/evidence/data/br5-cgm-nurbs-claims.csv",
        claim_id="",
        owner="BR5",
        note="NURBS curve verdict lands with the BR5 CGM/NURBS merge",
    ),
    Resolution(
        construct_id="SRF-02",
        outcome=PENDING_MERGE,
        evidence="docs/evidence/data/br4-quadrics-claims.csv",
        claim_id="",
        owner="BR4",
        note="cylinder recognition lands with the BR4 quadrics merge",
    ),
    Resolution(
        construct_id="SRF-03",
        outcome=PENDING_MERGE,
        evidence="docs/evidence/data/br4-quadrics-claims.csv",
        claim_id="",
        owner="BR4",
        note="cone recognition lands with the BR4 quadrics merge",
    ),
    Resolution(
        construct_id="SRF-04",
        outcome=PENDING_MERGE,
        evidence="docs/evidence/data/br4-quadrics-claims.csv",
        claim_id="",
        owner="BR4",
        note="sphere recognition lands with the BR4 quadrics merge",
    ),
    Resolution(
        construct_id="SRF-05",
        outcome=PENDING_MERGE,
        evidence="docs/evidence/data/br4-quadrics-claims.csv",
        claim_id="",
        owner="BR4",
        note="torus verdict lands with the BR4 quadrics merge",
    ),
    Resolution(
        construct_id="SRF-06",
        outcome=PENDING_MERGE,
        evidence="docs/evidence/data/br4-quadrics-claims.csv",
        claim_id="",
        owner="BR4",
        note="revolution verdict lands with the BR4 quadrics merge",
    ),
    Resolution(
        construct_id="SRF-07",
        outcome=PENDING_MERGE,
        evidence="docs/evidence/data/br4-quadrics-claims.csv",
        claim_id="",
        owner="BR4",
        note="extrusion verdict lands with the BR4 quadrics merge",
    ),
    Resolution(
        construct_id="SRF-08",
        outcome=PENDING_MERGE,
        evidence="docs/evidence/data/br5-cgm-nurbs-claims.csv",
        claim_id="",
        owner="BR5",
        note="NURBS surface verdict lands with the BR5 CGM/NURBS merge",
    ),
    # --- BR2: planar faces, loops and the record-local plane --------------
    Resolution(
        construct_id="TOP-04",
        outcome=DECODED,
        evidence="docs/evidence/data/br2-planar-claims.csv",
        claim_id="BR2-03_face_files_corpus",
        owner="BR2",
        note="facet-record decode; L2 tie-out BR2-01",
    ),
    Resolution(
        construct_id="TOP-05",
        outcome=DECODED,
        evidence="docs/evidence/data/br2-planar-claims.csv",
        claim_id="BR2-04_planar_files_corpus",
        owner="BR2",
        note="count-width loop delimitation; L2 tie-out BR2-02",
    ),
    Resolution(
        construct_id="SRF-01",
        outcome=DECODED,
        evidence="docs/evidence/data/br2-planar-claims.csv",
        claim_id="BR2-10_plane_coplanar_poolonly",
        owner="BR2",
        note=(
            "record-local plane + orientation; surface identity and composite "
            "stores stay open (BR2-13/BR2-19/BR2-20)"
        ),
    ),
    # --- BR3: boundary curves, edge/vertex tables, conic ceilings ---------
    Resolution(
        construct_id="TOP-06",
        outcome=DECODED,
        evidence="docs/evidence/data/br3-curves-claims.csv",
        claim_id="T06_census_presence",
        claim_scope="corpus",
        owner="BR3",
        note="edge grammar re-validated; E1 residue named by T06_edge_residue_files",
    ),
    Resolution(
        construct_id="TOP-07",
        outcome=DECODED,
        evidence="docs/evidence/data/br3-curves-claims.csv",
        claim_id="T07_pool_count_law",
        claim_scope="corpus",
        owner="BR3",
        note="pool structural validator (P1-P3); presence T07_census_presence",
    ),
    Resolution(
        construct_id="CRV-01",
        outcome=DECODED,
        evidence="docs/evidence/data/br3-curves-claims.csv",
        claim_id="C01_line_block_finite",
        claim_scope="corpus",
        owner="BR3",
        note="40-B block layout decoded; G2 field semantics stay open (C01_line_prep_law)",
    ),
    Resolution(
        construct_id="CRV-02",
        outcome=DECODED,
        evidence="docs/evidence/data/br3-curves-claims.csv",
        claim_id="C02_circle_decode_ok",
        claim_scope="corpus",
        owner="BR3",
        note="18-B circle layout + finite non-zero radius; pool cross-check C02_circle_pool_law",
    ),
    Resolution(
        construct_id="CRV-03",
        outcome=DECODED,
        evidence="docs/evidence/data/br3-curves-claims.csv",
        claim_id="C03_conic_decode_ok",
        claim_scope="corpus",
        owner="BR3",
        note="30-B conic layout + direction law; axis reading of (a, b) is candidate",
    ),
    Resolution(
        construct_id="CRV-04",
        outcome=DOCUMENTED_OPEN,
        evidence="docs/evidence/data/br3-curves-claims.csv",
        claim_id="C04_parabola_ceiling",
        claim_scope="corpus",
        owner="BR3",
        note="no eccentricity field decoded; carrier ceiling published",
    ),
    Resolution(
        construct_id="CRV-05",
        outcome=DOCUMENTED_OPEN,
        evidence="docs/evidence/data/br3-curves-claims.csv",
        claim_id="C05_hyperbola_ceiling",
        claim_scope="corpus",
        owner="BR3",
        note="no eccentricity field decoded; carrier ceiling published",
    ),
    Resolution(
        construct_id="CRV-07",
        outcome=DECODED,
        evidence="docs/evidence/data/br3-curves-claims.csv",
        claim_id="C07_polyline_strips",
        claim_scope="corpus",
        owner="BR3",
        note="n > 2 polyline strip decode; element-space binding stays composite (F8)",
    ),
    Resolution(
        construct_id="CRV-08",
        outcome=CANDIDATE,
        evidence="docs/evidence/data/br3-curves-claims.csv",
        claim_id="C08_midring_dir_law",
        claim_scope="corpus",
        owner="BR3",
        note="parameter-carrier evidence only; trim-bound semantics stay open",
    ),
)


@dataclasses.dataclass(frozen=True)
class ConstructScore:
    """One frozen construct's row: census figures plus its cited verdict."""

    construct_id: str
    family: str
    name: str
    outcome: str
    owner: str
    evidence: str
    claim_id: str
    note: str
    corpus_occurrences: int
    corpus_rate: float
    rate_l2_pass: float
    citation: dict | None

    def to_json(self) -> dict:
        return {
            "construct_id": self.construct_id,
            "family": self.family,
            "name": self.name,
            "outcome": self.outcome,
            "owner": self.owner,
            "evidence": self.evidence,
            "claim_id": self.claim_id,
            "note": self.note,
            "citation": self.citation,
            "census": {
                "corpus_occurrences": self.corpus_occurrences,
                "corpus_rate": self.corpus_rate,
                "rate_l2_pass": self.rate_l2_pass,
            },
        }


@dataclasses.dataclass(frozen=True)
class L3Score:
    """The scored L3 document (JSON-shaped, deterministic, no wall clock)."""

    vocabulary_sha256: str
    family_counts: dict[str, int]
    constructs: tuple[ConstructScore, ...]
    no_regret: dict | None

    @property
    def total(self) -> int:
        return len(self.constructs)

    @property
    def resolved(self) -> int:
        return sum(1 for row in self.constructs if row.outcome in RESOLVED_OUTCOMES)

    @property
    def by_outcome(self) -> dict[str, int]:
        return {
            outcome: sum(1 for row in self.constructs if row.outcome == outcome)
            for outcome in OUTCOME_ORDER
        }

    @property
    def presence_slots_used(self) -> int:
        return sum(row.corpus_occurrences for row in self.constructs)

    @property
    def presence_slots(self) -> int:
        return self.total * FULL_CORPUS_PARTS

    def to_json(self) -> dict:
        """Serialize the document; ``resolved``/``total`` are exact counts."""
        return {
            "schema": SCHEMA,
            "generated_by": "catpart.fitness.l3",
            "gate": (
                "the construct-coverage headline gates Phase 7 acceptance; "
                "the corpus rate is reported alongside and never gates"
            ),
            "denominator": {
                "source": VOCABULARY_PATH,
                "sha256": self.vocabulary_sha256,
                "frozen_rows": self.total,
                "family_counts": dict(self.family_counts),
            },
            "headline": {
                "resolved": self.resolved,
                "total": self.total,
                "rate": self.resolved / self.total,
                "exact": f"{self.resolved}/{self.total}",
            },
            "by_outcome": self.by_outcome,
            "corpus_context": {
                "corpus_parts": FULL_CORPUS_PARTS,
                "l2_pass_parts": L2_PASS_PARTS,
                "construct_file_slots_used": self.presence_slots_used,
                "construct_file_slots": self.presence_slots,
                "presence_rate": self.presence_slots_used / self.presence_slots,
                "gating": False,
                "note": (
                    "census file-presence over the full corpus (BR1 columns), "
                    "construct x part slots; reported, never gating"
                ),
            },
            "constructs": [row.to_json() for row in self.constructs],
            "no_regret": self.no_regret,
        }


def _read_csv(root: Path, rel: str) -> tuple[list[str], list[dict[str, str]]]:
    """Read one committed CSV under ``root``; fail closed with its path."""
    path = root / rel
    try:
        with path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            header = reader.fieldnames or []
            rows = [dict(row) for row in reader]
    except FileNotFoundError as exc:
        raise L3Error(f"{rel}: committed artifact not found") from exc
    except (OSError, csv.Error) as exc:
        raise L3Error(f"{rel}: unreadable CSV: {exc}") from exc
    if not header:
        raise L3Error(f"{rel}: CSV has no header row")
    return header, rows


def _float_field(value: str, rel: str, claim: str, field: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise L3Error(f"{rel}:{claim}: {field} is not a number: {value!r}") from exc


def _int_field(value: str, rel: str, claim: str, field: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise L3Error(f"{rel}:{claim}: {field} is not an integer: {value!r}") from exc
    if parsed < 0:
        raise L3Error(f"{rel}:{claim}: {field} is negative: {parsed}")
    return parsed


def _evidence_path(root: Path, rel: str, construct_id: str) -> Path:
    """Resolve a citation path, refusing escapes out of ``docs/evidence/``."""
    path = Path(rel)
    parts = path.parts
    if path.is_absolute() or not parts or ".." in parts:
        raise L3Error(f"{construct_id}: evidence path must be repo-relative: {rel!r}")
    if parts[:2] != ("docs", "evidence") or path.suffix != ".csv":
        raise L3Error(
            f"{construct_id}: evidence must be a committed CSV under "
            f"docs/evidence/: {rel!r}"
        )
    return root / rel


def _claim_rows(root: Path, rel: str) -> list[dict[str, str]]:
    header, rows = _read_csv(root, rel)
    if "claim" not in header:
        raise L3Error(f"{rel}: claims CSV has no 'claim' column")
    return rows


def _resolve_citation(
    root: Path,
    resolution: Resolution,
    cached: dict[str, list[dict[str, str]]],
) -> dict:
    """Return the citation block for one row (empty for pending-merge rows)."""
    if resolution.outcome == PENDING_MERGE:
        path = _evidence_path(root, resolution.evidence, resolution.construct_id)
        if path.exists():
            raise L3Error(
                f"{resolution.construct_id}: {resolution.evidence} exists but the "
                f"registry row is still pending-merge — record {resolution.owner}'s "
                "outcome and claim id in RESOLUTION_REGISTRY"
            )
        return {}

    path = _evidence_path(root, resolution.evidence, resolution.construct_id)
    if not path.is_file():
        raise L3Error(
            f"{resolution.construct_id}: cited evidence {resolution.evidence} "
            "does not exist"
        )
    rows = cached.get(resolution.evidence)
    if rows is None:
        rows = cached[resolution.evidence] = _claim_rows(root, resolution.evidence)
    matches = [row for row in rows if row.get("claim") == resolution.claim_id]
    if not matches:
        raise L3Error(
            f"{resolution.construct_id}: claim id {resolution.claim_id!r} is not "
            f"in {resolution.evidence}"
        )
    if len(matches) > 1:
        if not resolution.claim_scope:
            raise L3Error(
                f"{resolution.construct_id}: claim id {resolution.claim_id!r} "
                f"appears {len(matches)} times in {resolution.evidence}; set "
                "claim_scope to the row's scope"
            )
        matches = [
            row for row in matches if (row.get("scope") or "") == resolution.claim_scope
        ]
        if len(matches) != 1:
            raise L3Error(
                f"{resolution.construct_id}: claim id {resolution.claim_id!r} with "
                f"scope {resolution.claim_scope!r} matches {len(matches)} rows in "
                f"{resolution.evidence}"
            )
    row = matches[0]

    construct = (row.get("construct") or "").strip()
    if "construct" in row and construct != resolution.construct_id:
        raise L3Error(
            f"{resolution.construct_id}: claims row {resolution.claim_id!r} is "
            f"attributed to {construct!r} in {resolution.evidence}"
        )

    scope = (row.get("scope") or "").strip()
    if resolution.claim_scope and scope != resolution.claim_scope:
        raise L3Error(
            f"{resolution.construct_id}: claims row {resolution.claim_id!r} has scope "
            f"{scope!r}, not the declared {resolution.claim_scope!r}"
        )

    label = (row.get("label") or "").strip()
    allowed = LABELS_BY_OUTCOME.get(resolution.outcome, frozenset())
    if label not in allowed:
        raise L3Error(
            f"{resolution.construct_id}: claims row {resolution.claim_id!r} is "
            f"labelled {label!r}, which does not justify outcome "
            f"{resolution.outcome!r} (allowed: {', '.join(sorted(allowed)) or 'none'})"
        )

    citation: dict = {
        "scope": row.get("scope", ""),
        "observations": row.get("observations", ""),
        "passes": row.get("passes", ""),
        "rate": row.get("rate", ""),
        "label": label,
    }
    for field in ("observations", "passes"):
        value = citation[field]
        if value:
            _int_field(value, resolution.evidence, resolution.claim_id, field)
    if citation["rate"]:
        _float_field(citation["rate"], resolution.evidence, resolution.claim_id, "rate")
    return citation


def load_vocabulary(
    root: Path, registry: tuple[Resolution, ...] = RESOLUTION_REGISTRY
) -> tuple[list[dict[str, str]], str]:
    """Load and validate the frozen denominator; return ``(rows, sha256)``.

    Fail-closed checks: required columns, frozen status, duplicate ids, and an
    exact id-for-id match against the registry (a differing vocabulary is a
    denominator change, which invalidates every history comparison).
    """
    path = root / VOCABULARY_PATH
    try:
        raw = path.read_bytes()
    except FileNotFoundError as exc:
        raise L3Error(f"{VOCABULARY_PATH}: frozen vocabulary not found") from exc
    except OSError as exc:
        raise L3Error(f"{VOCABULARY_PATH}: unreadable: {exc}") from exc
    header, rows = _read_csv(root, VOCABULARY_PATH)
    missing = [column for column in VOCABULARY_COLUMNS if column not in header]
    if missing:
        raise L3Error(f"{VOCABULARY_PATH}: missing columns: {', '.join(missing)}")

    seen: set[str] = set()
    for row in rows:
        construct_id = (row.get("construct_id") or "").strip()
        if not construct_id:
            raise L3Error(f"{VOCABULARY_PATH}: row with an empty construct_id")
        if construct_id in seen:
            raise L3Error(f"{VOCABULARY_PATH}: duplicate construct id {construct_id}")
        seen.add(construct_id)
        if (row.get("status") or "").strip() != "frozen":
            raise L3Error(
                f"{VOCABULARY_PATH}: {construct_id} is not frozen "
                f"(status {(row.get('status') or '').strip()!r}); the L3 "
                "denominator admits frozen constructs only"
            )

    registry_ids = [resolution.construct_id for resolution in registry]
    if len(registry_ids) != len(set(registry_ids)):
        duplicates = sorted({pid for pid in registry_ids if registry_ids.count(pid) > 1})
        raise L3Error(
            f"RESOLUTION_REGISTRY: duplicate construct rows: {', '.join(duplicates)}"
        )
    registry_set = set(registry_ids)
    unknown = sorted(seen - registry_set)
    if unknown:
        raise L3Error(
            "unknown construct in the frozen vocabulary (no RESOLUTION_REGISTRY "
            f"row): {', '.join(unknown)}"
        )
    unscored = sorted(registry_set - seen)
    if unscored:
        raise L3Error(
            "RESOLUTION_REGISTRY row missing from the frozen vocabulary: "
            f"{', '.join(unscored)}"
        )
    if len(seen) != DENOMINATOR_TOTAL:
        raise L3Error(
            f"{VOCABULARY_PATH}: frozen denominator is {len(seen)} constructs, "
            f"expected {DENOMINATOR_TOTAL} (BR1 freeze)"
        )
    return rows, hashlib.sha256(raw).hexdigest()


def _check_populations(root: Path) -> None:
    """Cross-check the population constants against committed claim rows."""
    cached: dict[str, list[dict[str, str]]] = {}
    for rel, claim_id, expected in POPULATION_ANCHORS:
        rows = cached.get(rel)
        if rows is None:
            rows = cached[rel] = _claim_rows(root, rel)
        matches = [row for row in rows if row.get("claim") == claim_id]
        if len(matches) != 1:
            raise L3Error(
                f"{rel}: population anchor {claim_id!r} appears {len(matches)} times"
            )
        observations = _int_field(
            matches[0].get("observations", ""), rel, claim_id, "observations"
        )
        if observations != expected:
            raise L3Error(
                f"{rel}:{claim_id}: observations {observations} disagrees with the "
                f"scorer population constant {expected}"
            )


def _no_regret_context(root: Path) -> dict | None:
    """The last accepted history row's frozen L1/L2 scalars (read only)."""
    path = root / HISTORY_PATH
    if not path.is_file():
        return None
    row = load_last_accepted_row(path)
    if row is None:
        return None
    scalars = row["scalars"]
    return {
        "source": HISTORY_PATH,
        "run_id": row["run_id"],
        "timestamp": row["timestamp"],
        "corpus_digest": row["corpus_digest"],
        "accepted": row["accepted"],
        "L1": scalars["L1"],
        "L2": scalars["L2"],
        "L3": scalars.get("L3"),
        "read_only": True,
    }


def score_l3(
    root: Path,
    registry: tuple[Resolution, ...] = RESOLUTION_REGISTRY,
) -> L3Score:
    """Score the L3 headline from the committed artifacts under ``root``.

    ``registry`` is a parameter only so tests can inject a modified table; the
    committed scorer always uses :data:`RESOLUTION_REGISTRY`.
    """
    root = Path(root)
    rows, vocabulary_sha256 = load_vocabulary(root, registry)
    _check_populations(root)

    by_id = {resolution.construct_id: resolution for resolution in registry}
    cached: dict[str, list[dict[str, str]]] = {}
    family_counts: dict[str, int] = {}
    constructs: list[ConstructScore] = []
    for row in rows:
        construct_id = row["construct_id"].strip()
        resolution = by_id[construct_id]
        family = (row.get("family") or "").strip()
        family_counts[family] = family_counts.get(family, 0) + 1
        occurrences = _int_field(
            row.get("corpus_occurrences", ""), VOCABULARY_PATH, construct_id,
            "corpus_occurrences",
        )
        if occurrences > FULL_CORPUS_PARTS:
            raise L3Error(
                f"{VOCABULARY_PATH}:{construct_id}: corpus_occurrences "
                f"{occurrences} exceeds the {FULL_CORPUS_PARTS}-part corpus"
            )
        rate_l2_pass = _float_field(
            row.get("rate_l2_pass", ""), VOCABULARY_PATH, construct_id, "rate_l2_pass"
        )
        if not 0.0 <= rate_l2_pass <= 1.0:
            raise L3Error(
                f"{VOCABULARY_PATH}:{construct_id}: rate_l2_pass {rate_l2_pass} "
                "is outside [0, 1]"
            )
        constructs.append(
            ConstructScore(
                construct_id=construct_id,
                family=family,
                name=(row.get("name") or "").strip(),
                outcome=resolution.outcome,
                owner=resolution.owner,
                evidence=resolution.evidence,
                claim_id=resolution.claim_id,
                note=resolution.note,
                corpus_occurrences=occurrences,
                corpus_rate=occurrences / FULL_CORPUS_PARTS,
                rate_l2_pass=rate_l2_pass,
                citation=_resolve_citation(root, resolution, cached) or None,
            )
        )

    score = L3Score(
        vocabulary_sha256=vocabulary_sha256,
        family_counts=family_counts,
        constructs=tuple(constructs),
        no_regret=_no_regret_context(root),
    )
    if score.resolved + score.by_outcome[PENDING_MERGE] != score.total:
        raise L3Error(
            "internal inconsistency: resolved + pending-merge != frozen denominator"
        )
    return score


def render_summary(score: L3Score) -> str:
    """Human-readable summary: headline, outcome split, per-construct table."""
    lines: list[str] = []
    headline = Fraction(score.resolved, score.total)
    lines.append(
        "L3 construct coverage (frozen denominator): "
        f"{score.resolved}/{score.total} resolved ({float(headline):.4f})"
    )
    split = " | ".join(
        f"{outcome} {count}" for outcome, count in score.by_outcome.items()
    )
    lines.append(f"  outcomes: {split}")
    lines.append(
        "corpus rate (reported, never gating): "
        f"{score.presence_slots_used}/{score.presence_slots} construct-file slots "
        f"({score.presence_slots_used / score.presence_slots:.4f})"
    )
    lines.append("")

    header = ("construct", "family", "name", "outcome", "citation")
    table: list[tuple[str, ...]] = [header]
    for row in score.constructs:
        citation = (
            f"{Path(row.evidence).name}:{row.claim_id}"
            if row.claim_id
            else f"{Path(row.evidence).name} (absent at this commit)"
        )
        table.append((row.construct_id, row.family, row.name, row.outcome, citation))
    widths = [max(len(line[column]) for line in table) for column in range(len(header))]
    for index, line in enumerate(table):
        rendered = "  ".join(
            value.ljust(widths[column]) for column, value in enumerate(line)
        ).rstrip()
        lines.append(rendered)
        if index == 0:
            lines.append("  ".join("-" * width for width in widths))
    lines.append("")

    no_regret = score.no_regret
    if no_regret is None:
        lines.append(f"no-regret context: {HISTORY_PATH} has no accepted row")
    else:
        l1_dev = no_regret["L1"]["dev"]["rate"]
        l1_held = no_regret["L1"]["held-out"]["rate"]
        l2_dev = no_regret["L2"]["dev"]["rate"]
        l2_held = no_regret["L2"]["held-out"]["rate"]
        lines.append(
            f"no-regret context (read-only, last accepted row {no_regret['run_id']}, "
            f"{no_regret['timestamp']}): "
            f"L1 dev {l1_dev:.4f} held-out {l1_held:.4f} | "
            f"L2 dev {l2_dev:.4f} held-out {l2_held:.4f}"
        )
    return "\n".join(lines) + "\n"


def dumps(score: L3Score) -> str:
    """The JSON document as committed (stable key order, no wall clock)."""
    return json.dumps(score.to_json(), indent=2) + "\n"
