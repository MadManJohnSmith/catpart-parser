//! The W11 analytic-scanner parity gate: the Rust ``scan_part`` against
//! the Python-generated committed CSV
//! (``docs/evidence/data/w11-analytic-files.csv``).
//!
//! The CSV is the probe's measured taxonomy (the Python twin's output);
//! this test re-runs the Rust scanner on the same corpus files and
//! asserts the taxonomy columns match row by row — the Python = Rust
//! parity the B8 bar asks for, on real bytes. The corpus is not
//! committed: rows whose file the checkout's ``corpus/`` does not
//! carry are skipped, and the whole test skips when the CSV or the
//! corpus is absent (the CI-safe arm; the corpus-free parity lives in
//! the mirrored unit fixtures of ``src/geometry/analytic.rs``).

use std::path::Path;

use port::geometry::analytic::scan_part;

const FILES_CSV: &str = "docs/evidence/data/w11-analytic-files.csv";

struct Row {
    sha16: String,
    corpus_path: String,
    verdict: String,
    store_body_size: Option<usize>,
    plane_records: usize,
    template_planes: usize,
    object_records: usize,
    scene_records: usize,
    bulk_dialect: String,
    a5_surface_frames: usize,
    nurbs_knot_runs: usize,
    nurbs_weight_runs: usize,
}

fn load_rows() -> Option<Vec<Row>> {
    let manifest_dir = Path::new(env!("CARGO_MANIFEST_DIR"));
    let csv_path = manifest_dir.join("../").join(FILES_CSV);
    let text = std::fs::read_to_string(csv_path).ok()?;
    let mut rows = Vec::new();
    for (index, line) in text.lines().enumerate() {
        if index == 0 || line.trim().is_empty() {
            continue;
        }
        let fields: Vec<&str> = line.split(',').collect();
        if fields.len() < 24 {
            continue;
        }
        rows.push(Row {
            sha16: fields[0].to_string(),
            corpus_path: fields[2].to_string(),
            verdict: fields[6].to_string(),
            store_body_size: fields[7].parse::<usize>().ok(),
            object_records: fields[8].parse().unwrap_or(0),
            plane_records: fields[9].parse().unwrap_or(0),
            template_planes: fields[10].parse().unwrap_or(0),
            scene_records: fields[13].parse().unwrap_or(0),
            bulk_dialect: fields[15].to_string(),
            a5_surface_frames: fields[24].parse().unwrap_or(0),
            nurbs_knot_runs: fields[22].parse().unwrap_or(0),
            nurbs_weight_runs: fields.get(23).and_then(|v| v.parse().ok()).unwrap_or(0),
        });
    }
    Some(rows)
}

#[test]
fn the_rust_scan_matches_the_committed_taxonomy() {
    let rows = match load_rows() {
        Some(rows) if !rows.is_empty() => rows,
        _ => {
            eprintln!("skipping: {FILES_CSV} missing or unparsable");
            return;
        }
    };
    let manifest_dir = Path::new(env!("CARGO_MANIFEST_DIR"));
    let corpus = manifest_dir.join("../corpus");
    if !corpus.exists() {
        eprintln!("skipping: the checkout carries no corpus/ (worktree)");
        return;
    }
    let mut compared = 0usize;
    for row in &rows {
        let path = corpus.join(&row.corpus_path);
        if !path.exists() {
            eprintln!("skipping row {}: no corpus file", row.sha16);
            continue;
        }
        let data = std::fs::read(&path).expect("read corpus file");
        let scan = scan_part(&data);
        assert_eq!(scan.verdict, row.verdict, "verdict drift on {}", row.sha16);
        assert_eq!(
            scan.store_body_size, row.store_body_size,
            "store body size drift on {}",
            row.sha16
        );
        assert_eq!(
            scan.object_records, row.object_records,
            "object record drift on {}",
            row.sha16
        );
        assert_eq!(
            scan.plane_records.len(),
            row.plane_records,
            "plane count drift on {}",
            row.sha16
        );
        assert_eq!(
            scan.template_planes, row.template_planes,
            "template plane drift on {}",
            row.sha16
        );
        assert_eq!(
            scan.scene_records, row.scene_records,
            "scene record drift on {}",
            row.sha16
        );
        assert_eq!(
            scan.bulk_dialect.unwrap_or(""),
            row.bulk_dialect,
            "bulk dialect drift on {}",
            row.sha16
        );
        assert_eq!(
            scan.a5_surface_frames, row.a5_surface_frames,
            "a5 frame drift on {}",
            row.sha16
        );
        assert_eq!(
            scan.nurbs_knot_runs, row.nurbs_knot_runs,
            "knot run drift on {}",
            row.sha16
        );
        assert_eq!(
            scan.nurbs_weight_runs, row.nurbs_weight_runs,
            "weight run drift on {}",
            row.sha16
        );
        compared += 1;
    }
    // the population must actually be compared when the corpus is here
    assert!(
        compared >= 10,
        "the population rows must resolve against the corpus (compared {compared})"
    );
    eprintln!("parity compared {compared}/{} rows", rows.len());
}
