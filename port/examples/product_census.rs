//! Product placement A/B census (maintainer harness, not part of the gate).
//!
//! Walks every manifest `kind=product` row through `port::product::parse_product`
//! and reports the corpus placement ledger:
//!
//! ```text
//! FILES=… TOTAL=… PLACED=… IDENTITY=… UNDECODABLE=… PLACED_FILES=…
//! ```
//!
//! `dump <sha16>` prints every instance's placement status and 7-tuple, which is
//! the before/after diff used by
//! `docs/evidence/2026-11-18-p3-position-layer-segmentation.md`.
//!
//! Usage (from `port/`):
//! ```text
//! cargo run --example product_census -- ../manifests/corpus-manifest.csv /path/to/repo
//! cargo run --example product_census -- ../manifests/corpus-manifest.csv /path/to/repo dump 81b1fe655b83f7ee
//! ```

use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::PathBuf;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let manifest = PathBuf::from(&args[1]);
    let corpus = PathBuf::from(&args[2]);
    let f = File::open(&manifest).expect("manifest");
    let mut rdr = BufReader::new(f);
    let mut header = String::new();
    rdr.read_line(&mut header).expect("manifest header");
    let cols: Vec<&str> = header.trim_end().split(',').collect();
    let kind_i = cols.iter().position(|c| *c == "kind").expect("kind column");
    let path_i = cols
        .iter()
        .position(|c| *c == "local_path")
        .expect("local_path column");
    let sha_i = cols
        .iter()
        .position(|c| *c == "sha256")
        .expect("sha256 column");

    if args.get(3).is_some_and(|m| m == "dump") {
        let want = args.get(4).expect("sha16");
        for line in rdr.lines() {
            let line = line.expect("manifest row");
            let f: Vec<&str> = line.split(',').collect();
            if f.len() <= path_i || f[kind_i] != "product" || !f[sha_i].starts_with(want) {
                continue;
            }
            let data = std::fs::read(corpus.join(f[path_i])).expect("product file");
            let doc = port::product::parse_product(&data).expect("product decode");
            println!("doc {}", f[sha_i]);
            for i in &doc.instances {
                let transform = i
                    .transform
                    .map(|t| {
                        t.iter()
                            .map(|v| format!("{v:.9}"))
                            .collect::<Vec<_>>()
                            .join(",")
                    })
                    .unwrap_or_else(|| "-".to_string());
                println!(
                    "  {} {} {} {}",
                    i.instance_name,
                    i.part_number,
                    i.placement_status.as_str(),
                    transform
                );
            }
        }
        return;
    }

    let mut total = 0usize;
    let mut placed = 0usize;
    let mut identity = 0usize;
    let mut undecodable = 0usize;
    let mut files = 0usize;
    let mut placed_files = 0usize;
    for line in rdr.lines() {
        let line = line.expect("manifest row");
        let f: Vec<&str> = line.split(',').collect();
        if f.len() <= path_i || f[kind_i] != "product" {
            continue;
        }
        let Ok(data) = std::fs::read(corpus.join(f[path_i])) else {
            continue;
        };
        match port::product::parse_product(&data) {
            Ok(doc) => {
                files += 1;
                total += doc.total_instances;
                placed += doc.placed_instances;
                identity += doc.identity_instances;
                undecodable += doc
                    .instances
                    .iter()
                    .filter(|i| i.placement_status == port::product::PlacementStatus::Undecodable)
                    .count();
                if doc.placed_instances > 0 {
                    placed_files += 1;
                }
            }
            Err(e) => eprintln!("ERR {} {}", f[path_i], e),
        }
    }
    println!(
        "FILES={files} TOTAL={total} PLACED={placed} IDENTITY={identity} UNDECODABLE={undecodable} PLACED_FILES={placed_files}"
    );
}
