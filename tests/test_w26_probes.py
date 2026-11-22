"""W26 probe pins (B6): both triage selftests stay gate-covered.

The clustering probe's signature mechanics (buckets, carrier
vocabulary, W13 family counters, signature determinism) and the
residual-carrier probe's classification law (strict exact-count index
runs, the four known classes, fail-closed ``unclassified``) are pinned
in their ``--selftest`` modes; this module keeps them inside ``pytest
-q`` so the local gate cannot silently skip them (the
``test_benchmark_ground_truth`` pattern: ``main(["--selftest"]) == 0``).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "triage"))

import w26_empty_mesh_clusters as clusters  # noqa: E402
import w26_residual_carriers_probe as residual  # noqa: E402


def test_cluster_probe_selftest_is_green() -> None:
    assert clusters.main(["--selftest"]) == 0


def test_residual_probe_selftest_is_green() -> None:
    assert residual.main(["--selftest"]) == 0


def test_population_join_reads_the_committed_csvs() -> None:
    # The clustering CSV carries all 211 rows of the baseline run's
    # empty-mesh population and the ranks CSV one row per cluster; the
    # residual CSV holds the 55 non-U3 unresolved candidates.  These
    # row counts are the W26 evidence register (the note's §1/§3).
    import csv
    from pathlib import Path

    data = Path(__file__).resolve().parent.parent / "docs" / "evidence" / "data"
    with (data / "w26-empty-mesh-clusters.csv").open(newline="") as fh:
        assert len(list(csv.DictReader(fh))) == 211
    with (data / "w26-cluster-ranks.csv").open(newline="") as fh:
        assert len(list(csv.DictReader(fh))) == 102
    with (data / "w26-residual-carriers.csv").open(newline="") as fh:
        assert len(list(csv.DictReader(fh))) == 55
