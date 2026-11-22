//! V5R26 name-table ownership and tree walking (ticket #68, W-C).
//!
//! Authority: the s3-product-assemblies diagnosis
//! (`docs/evidence/2026-11-21-product-name-table.md`).
//!
//! The structure pool of this generation is a bag of interned names: a
//! document lists its own children **and** the leaves of the sub-products it
//! references. The parser can only enumerate; a walker that holds the whole
//! document set restores the tree with the ownership law
//!
//! ```text
//! own(D) = [n for n in names(D) if n not in ⋃ names(P)]
//! products(names(D)) = {n : a document for n exists in the set}
//! ```
//!
//! A name that resolves to a part, or to nothing, stays own. The recursion
//! descends only into names backed by a product document; a document without
//! the name-table signature contributes no names, so the law never invents
//! instances.

#![allow(clippy::suboptimal_flops)]

use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet};

use serde::{Deserialize, Serialize};

use super::binding::{PlacementStatus, bind_name_table};
use super::framing::find_structure_pool;
use super::pairing::{
    PairingRule, ProductInstanceRecord, extract_name_table_instances, read_name_table,
};
use super::pool::decode_pool_texts;
use super::transforms::{PositionKind, scan_position_matrix_streams};

/// One additive warning of the reconstructed tree.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct OwnedTreeWarning {
    pub class: String,
    pub detail: String,
}

/// One instance of the reconstructed name-table tree.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct OwnedInstanceRecord {
    pub instance_name: String,
    pub part_number: String,
    pub pairing_rule: PairingRule,
    pub has_position_attr: bool,
    pub placement_status: PlacementStatus,
    pub transform: Option<[f64; 7]>,
    pub object_tag: Option<u32>,
    pub classification_detail: Option<String>,
    /// Tree depth; the root document's own children are depth 0.
    pub depth: usize,
    /// Index of the row that listed this name, `None` at the root document.
    pub parent_index: Option<usize>,
    /// Name of the child product document when one exists, else `None`.
    pub child_product: Option<String>,
}

/// The reconstructed tree for one root product.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct OwnedTreeDocument {
    pub schema_version: u32,
    pub root: String,
    pub total_instances: usize,
    pub placed_instances: usize,
    pub identity_instances: usize,
    pub undecodable_instances: usize,
    pub warnings: Vec<OwnedTreeWarning>,
    pub instances: Vec<OwnedInstanceRecord>,
}

/// Ownership law over already-enumerated tables; order is preserved.
pub fn own_children(
    names: &[String],
    child_name_tables: &BTreeMap<String, Vec<String>>,
) -> Vec<String> {
    let mut covered: BTreeSet<&str> = BTreeSet::new();
    for name in names {
        if let Some(child_names) = child_name_tables.get(name) {
            covered.extend(child_names.iter().map(String::as_str));
        }
    }
    names
        .iter()
        .filter(|name| !covered.contains(name.as_str()))
        .cloned()
        .collect()
}

/// Strip a bare `.CATProduct` suffix (and any directory components).
fn normalize_stem(key: &str) -> String {
    let base = key.rsplit(['/', '\\']).next().unwrap_or(key);
    if base.to_ascii_lowercase().ends_with(".catproduct") {
        base[..base.len() - ".catproduct".len()].to_string()
    } else {
        base.to_string()
    }
}

struct Walker<'a> {
    docs: BTreeMap<String, &'a [u8]>,
    names_cache: BTreeMap<String, Option<Vec<String>>>,
    records_cache: BTreeMap<String, Option<Vec<ProductInstanceRecord>>>,
    /// W5 law C: matrix bodies byte-identical across two or more documents of
    /// the walked set — shared connector frames, never instance placements.
    shared_bodies: HashSet<Vec<u8>>,
    rows: Vec<OwnedInstanceRecord>,
    visiting: BTreeSet<String>,
}

impl Walker<'_> {
    fn names_for(&mut self, name: &str) -> Option<Vec<String>> {
        if let Some(cached) = self.names_cache.get(name) {
            return cached.clone();
        }
        let names = self.docs.get(name).and_then(|data| {
            let pool = find_structure_pool(data)?;
            let texts = decode_pool_texts(&pool.items);
            read_name_table(&texts).map(|table| table.names)
        });
        self.names_cache.insert(name.to_string(), names.clone());
        names
    }

    fn records_for(&mut self, name: &str, n_own: usize) -> Option<Vec<ProductInstanceRecord>> {
        if let Some(cached) = self.records_cache.get(name) {
            return cached.clone();
        }
        let records = self.docs.get(name).and_then(|data| {
            let pool = find_structure_pool(data)?;
            let texts = decode_pool_texts(&pool.items);
            let mut records = extract_name_table_instances(&texts)?;
            // The walker holds the document set, so `own(D)` is known here and
            // the S7 placed refinement may fire (`#R == #own(D)` with
            // byte-identical matrices, none of them shared connector frames).
            // `bind_name_table` stays fail-closed when the count mismatches,
            // the matrices differ, or a shared connector body is present.
            bind_name_table(&mut records, data, Some(n_own), Some(&self.shared_bodies));
            Some(records)
        });
        self.records_cache.insert(name.to_string(), records.clone());
        records
    }

    fn visit(&mut self, name: &str, depth: usize, parent_index: Option<usize>) {
        if self.visiting.contains(name) {
            return;
        }
        let Some(names) = self.names_for(name) else {
            return;
        };
        let mut child_tables = BTreeMap::new();
        for child in &names {
            if let Some(child_names) = self.names_for(child) {
                child_tables.insert(child.clone(), child_names);
            }
        }
        let own = own_children(&names, &child_tables);
        let Some(records) = self.records_for(name, own.len()) else {
            return;
        };
        let by_name: HashMap<&str, &ProductInstanceRecord> = records
            .iter()
            .map(|record| (record.instance_name.as_str(), record))
            .collect();

        self.visiting.insert(name.to_string());
        for child in own {
            let Some(record) = by_name.get(child.as_str()) else {
                continue;
            };
            let child_product = self.docs.contains_key(&child).then(|| child.clone());
            self.rows.push(OwnedInstanceRecord {
                instance_name: record.instance_name.clone(),
                part_number: record.part_number.clone(),
                pairing_rule: record.pairing_rule,
                has_position_attr: record.has_position_attr,
                placement_status: record.placement_status,
                transform: record.transform,
                object_tag: record.object_tag,
                classification_detail: record.classification_detail.clone(),
                depth,
                parent_index,
                child_product: child_product.clone(),
            });
            let index = self.rows.len() - 1;
            if child_product.is_some() {
                self.visit(&child, depth + 1, Some(index));
            }
        }
        self.visiting.remove(name);
    }
}

/// Walk the V5R26 name-table tree under `root` with `own(D)` attribution.
///
/// `documents` maps product stems (or bare `.CATProduct` filenames) to their
/// bytes. Rows are emitted depth-first in table order at each level, so the
/// result follows the documents, never a guessed ordinal.
pub fn resolve_owned_assembly(
    root: &str,
    documents: &BTreeMap<String, Vec<u8>>,
) -> OwnedTreeDocument {
    let docs: BTreeMap<String, &[u8]> = documents
        .iter()
        .map(|(key, data)| (normalize_stem(key), data.as_slice()))
        .collect();

    // W5 law C census: a matrix body byte-identical across two or more
    // documents of the walked set is a shared connector frame (never an
    // instance placement). Every document of the set participates, not only
    // the visited ones — connector frames propagate through references across
    // unrelated subtrees.
    let mut body_docs: HashMap<Vec<u8>, BTreeSet<String>> = HashMap::new();
    for (name, data) in &docs {
        for rec in scan_position_matrix_streams(data) {
            body_docs
                .entry(rec.matrix_body.clone())
                .or_default()
                .insert(name.clone());
        }
    }
    let shared_bodies: HashSet<Vec<u8>> = body_docs
        .into_iter()
        .filter(|(_, names)| names.len() >= 2)
        .map(|(body, _)| body)
        .collect();
    let n_refused_docs = docs
        .iter()
        .filter(|(_name, data)| {
            let records = scan_position_matrix_streams(data);
            !records.is_empty()
                && records.iter().all(|rec| {
                    rec.kind == PositionKind::Identity || shared_bodies.contains(&rec.matrix_body)
                })
        })
        .count();

    let mut walker = Walker {
        docs,
        names_cache: BTreeMap::new(),
        records_cache: BTreeMap::new(),
        shared_bodies: shared_bodies.clone(),
        rows: Vec::new(),
        visiting: BTreeSet::new(),
    };
    walker.visit(root, 0, None);

    let total = walker.rows.len();
    let count = |status: PlacementStatus| {
        walker
            .rows
            .iter()
            .filter(|row| row.placement_status == status)
            .count()
    };
    let warnings = if shared_bodies.is_empty() {
        Vec::new()
    } else {
        vec![OwnedTreeWarning {
            class: "connector-frame-records-v5r26".to_string(),
            detail: format!(
                "{} _Position matrix body(ies) appear byte-identical in >= 2 documents of \
                 the walked set; {} document(s) carry only such connector frames (W5 law C) \
                 and their instances decode identity",
                shared_bodies.len(),
                n_refused_docs
            ),
        }]
    };
    OwnedTreeDocument {
        schema_version: 1,
        root: root.to_string(),
        total_instances: total,
        placed_instances: count(PlacementStatus::Placed),
        identity_instances: count(PlacementStatus::Identity),
        undecodable_instances: count(PlacementStatus::Undecodable),
        warnings,
        instances: walker.rows,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::product::IDENTITY_TRANSFORM;

    /// Build a minimal, genuine-shaped V5R26 product with a name table and
    /// `translations.len()` explicit position records, record `i` carrying
    /// `translations[i]`.
    fn name_table_product_translations(
        name: &str,
        names: &[&str],
        translations: &[[f64; 3]],
    ) -> Vec<u8> {
        let mut data = vec![0u8; 32];
        data[..8].copy_from_slice(b"V5_CFV2\x00");
        data.extend_from_slice(b"\x00\x00CNEXTINFOS\x00\x00B24\x00\x00");

        let mut payload = Vec::new();
        let mut push = |text: &str| {
            payload.push((text.len() + 1) as u8);
            payload.extend_from_slice(text.as_bytes());
        };
        for text in [
            "CATCatalogManager",
            "catalogManager",
            "catalogLinks",
            "",
            "ASMPRODUCT",
            "ASMProduct",
            "_ViewsList",
            "_Connectors",
            "_RepresentedBy",
            "_Component",
            "_PartNumber",
        ] {
            push(text);
        }
        push(name);
        for text in [
            "_BagRepsList",
            "_PrdVersion",
            "_PubConnectors",
            "_AttrForLiterals",
            "_RefProduct",
            "_Disciplines",
            "PRDBAGREP",
            "3DIC",
            "_Reps",
            "_InstanceName",
        ] {
            push(text);
        }
        for text in names {
            push(text);
        }
        push("IsRoot");

        let tb = 1;
        let ln = (6 + tb + payload.len()) as u32;
        data.extend_from_slice(&crate::product::framing::FRAME_MARK);
        data.push(crate::product::framing::FRAME_TAG_POOL);
        data.extend_from_slice(&ln.to_le_bytes());
        data.push(0xBF);
        data.extend_from_slice(&payload);

        for t in translations {
            data.extend_from_slice(&crate::product::transforms::POSITION_EXPLICIT_HEADER);
            data.extend_from_slice(&crate::product::transforms::R15_MATRIX_MARKER);
            data.extend_from_slice(&[0xE7, 0xE8, 0xE8, 0xE8]);
            data.extend_from_slice(&[0xE7, 0xE8, 0xE8, 0xE8]);
            data.push(0xE7);
            for v in t {
                data.push(0xE6);
                data.extend_from_slice(&v.to_le_bytes());
            }
            data.push(0xFE);
        }
        data
    }

    /// The standard helper: `position_records` identical records at the
    /// S7-era translation (12.5, 0.0, 14.4).
    fn name_table_product(name: &str, names: &[&str], position_records: usize) -> Vec<u8> {
        name_table_product_translations(name, names, &vec![[12.5, 0.0, 14.4]; position_records])
    }

    fn documents(pairs: &[(&str, Vec<u8>)]) -> BTreeMap<String, Vec<u8>> {
        pairs
            .iter()
            .map(|(name, data)| ((*name).to_string(), data.clone()))
            .collect()
    }

    #[test]
    fn own_children_subtracts_only_listed_product_tables() {
        let names: Vec<String> = ["Widget", "Sub", "Bolt", "Sub-leaf", "Sub-own"]
            .iter()
            .map(|s| (*s).to_string())
            .collect();
        let child_tables: BTreeMap<String, Vec<String>> = [(
            "Sub".to_string(),
            vec!["Sub-leaf".to_string(), "Sub-own".to_string()],
        )]
        .into_iter()
        .collect();

        assert_eq!(
            own_children(&names, &child_tables),
            vec!["Widget", "Sub", "Bolt"]
        );
        assert_eq!(own_children(&names, &BTreeMap::new()), names);
    }

    #[test]
    fn owned_walk_attributes_children_to_their_document() {
        let docs = documents(&[
            (
                "Root.CATProduct",
                name_table_product("Root", &["Widget", "Sub", "Sub-leaf", "Sub-own", "Bolt"], 0),
            ),
            (
                "Sub.CATProduct",
                name_table_product("Sub", &["Sub-leaf", "Sub-own"], 0),
            ),
        ]);

        let tree = resolve_owned_assembly("Root", &docs);

        assert_eq!(tree.root, "Root");
        assert_eq!(tree.total_instances, 5);
        let names: Vec<&str> = tree
            .instances
            .iter()
            .map(|row| row.instance_name.as_str())
            .collect();
        assert_eq!(names, vec!["Widget", "Sub", "Sub-leaf", "Sub-own", "Bolt"]);
        assert_eq!(
            tree.instances
                .iter()
                .map(|row| row.depth)
                .collect::<Vec<_>>(),
            vec![0, 0, 1, 1, 0]
        );
        assert_eq!(
            tree.instances
                .iter()
                .map(|row| row.parent_index)
                .collect::<Vec<_>>(),
            vec![None, None, Some(1), Some(1), None]
        );
        assert_eq!(tree.instances[1].child_product.as_deref(), Some("Sub"));
        assert!(tree.instances[0].child_product.is_none());
        assert_eq!(tree.identity_instances, 5);
        assert_eq!(tree.undecodable_instances, 0);
        for row in &tree.instances {
            assert_eq!(row.pairing_rule, PairingRule::NameTable);
            assert_eq!(row.placement_status, PlacementStatus::Identity);
        }
    }

    #[test]
    fn owned_walk_composes_child_fail_closed_status() {
        let docs = documents(&[
            ("Root", name_table_product("Root", &["Widget", "Sub"], 0)),
            (
                "Sub",
                name_table_product("Sub", &["Sub-leaf", "Sub-own"], 1),
            ),
        ]);

        let tree = resolve_owned_assembly("Root", &docs);

        let rows: HashMap<&str, &OwnedInstanceRecord> = tree
            .instances
            .iter()
            .map(|row| (row.instance_name.as_str(), row))
            .collect();
        assert_eq!(rows["Widget"].placement_status, PlacementStatus::Identity);
        assert_eq!(rows["Sub"].placement_status, PlacementStatus::Identity);
        assert_eq!(
            rows["Sub-leaf"].placement_status,
            PlacementStatus::Undecodable
        );
        assert!(rows["Sub-leaf"].transform.is_none());
        assert_eq!(rows["Sub-leaf"].depth, 1);
        assert_eq!(tree.identity_instances, 2);
        assert_eq!(tree.undecodable_instances, 2);
    }

    #[test]
    fn owned_walk_applies_the_placed_refinement() {
        // The child document carries #R == #own(D) with byte-identical
        // matrices: the walker supplies own(D), so the S7 refinement places
        // every own child with the one matrix (order-free). The parent still
        // has no records and stays identity.
        let docs = documents(&[
            ("Root", name_table_product("Root", &["Widget", "Sub"], 0)),
            (
                "Sub",
                name_table_product("Sub", &["Sub-leaf", "Sub-own"], 2),
            ),
        ]);

        let tree = resolve_owned_assembly("Root", &docs);

        let rows: HashMap<&str, &OwnedInstanceRecord> = tree
            .instances
            .iter()
            .map(|row| (row.instance_name.as_str(), row))
            .collect();
        assert_eq!(rows["Widget"].placement_status, PlacementStatus::Identity);
        assert_eq!(rows["Sub"].placement_status, PlacementStatus::Identity);
        assert_eq!(rows["Sub-leaf"].placement_status, PlacementStatus::Placed);
        assert_eq!(rows["Sub-own"].placement_status, PlacementStatus::Placed);
        assert_eq!(
            rows["Sub-leaf"].transform,
            Some([12.5, 0.0, 14.4, 1.0, 0.0, 0.0, 0.0])
        );
        assert_eq!(
            rows["Sub-own"].transform,
            Some([12.5, 0.0, 14.4, 1.0, 0.0, 0.0, 0.0])
        );
        assert!(tree.identity_instances == 2 && tree.placed_instances == 2);
        assert_eq!(tree.undecodable_instances, 0);
    }

    #[test]
    fn owned_walk_never_invents_a_child_without_a_document() {
        let docs = documents(&[("Root", name_table_product("Root", &["Widget", "Ghost"], 0))]);

        let tree = resolve_owned_assembly("Root", &docs);

        let names: Vec<&str> = tree
            .instances
            .iter()
            .map(|row| row.instance_name.as_str())
            .collect();
        assert_eq!(names, vec!["Widget", "Ghost"]);
        assert!(tree.instances[1].child_product.is_none());
    }

    // --- W5 law C: shared connector bodies ---------------------------------

    #[test]
    fn owned_walk_refuses_shared_connector_bodies() {
        // One matrix body in two unrelated documents: a shared connector
        // frame. Neither document places; both decode identity with the
        // law-C detail and the walk-level warning.
        let docs = documents(&[
            (
                "Left",
                name_table_product_translations("Left", &["Widget"], &[[12.5, 0.0, 14.4]]),
            ),
            (
                "Right",
                name_table_product_translations("Right", &["Bracket"], &[[12.5, 0.0, 14.4]]),
            ),
        ]);

        let tree = resolve_owned_assembly("Left", &docs);

        assert_eq!(tree.total_instances, 1);
        assert_eq!(tree.placed_instances, 0);
        assert_eq!(tree.identity_instances, 1);
        assert_eq!(tree.undecodable_instances, 0);
        let row = &tree.instances[0];
        assert_eq!(row.placement_status, PlacementStatus::Identity);
        assert_eq!(row.transform, Some(IDENTITY_TRANSFORM));
        assert!(row.has_position_attr);
        let detail = row.classification_detail.as_deref().unwrap();
        assert!(
            detail.contains("connector-frame records: all 1"),
            "{detail}"
        );
        assert!(detail.contains("(W5 law C)"), "{detail}");
        assert!(
            tree.warnings
                .iter()
                .any(|w| w.class == "connector-frame-records-v5r26")
        );
    }

    #[test]
    fn shared_body_blocks_the_placed_refinement() {
        // #R == #own(D) == 2 with byte-identical matrices would fire S7 —
        // but the same body also sits in an unrelated document, so the
        // records are connector frames and the set refuses to identity.
        let docs = documents(&[
            (
                "Solo",
                name_table_product_translations(
                    "Solo",
                    &["Widget", "Bracket"],
                    &[[12.5, 0.0, 14.4], [12.5, 0.0, 14.4]],
                ),
            ),
            (
                "Elsewhere",
                name_table_product_translations("Elsewhere", &["Nut"], &[[12.5, 0.0, 14.4]]),
            ),
        ]);

        let tree = resolve_owned_assembly("Solo", &docs);

        assert_eq!(tree.placed_instances, 0);
        assert_eq!(tree.identity_instances, 2);
        assert_eq!(tree.undecodable_instances, 0);
        for row in &tree.instances {
            assert_eq!(row.placement_status, PlacementStatus::Identity);
            let detail = row.classification_detail.as_deref().unwrap();
            assert!(
                detail.contains("connector-frame records: all 2"),
                "{detail}"
            );
        }
    }

    #[test]
    fn mixed_refusal_stays_fail_closed() {
        // A shared body next to a unique body: the shared record refuses,
        // the unique one cannot be attributed either -> undecodable.
        let docs = documents(&[
            (
                "Mixed",
                name_table_product_translations(
                    "Mixed",
                    &["Widget", "Bracket"],
                    &[[12.5, 0.0, 14.4], [9.0, 0.0, 0.0]],
                ),
            ),
            (
                "Elsewhere",
                name_table_product_translations("Elsewhere", &["Nut"], &[[12.5, 0.0, 14.4]]),
            ),
        ]);

        let tree = resolve_owned_assembly("Mixed", &docs);

        assert_eq!(tree.placed_instances, 0);
        assert_eq!(tree.undecodable_instances, 2);
        for row in &tree.instances {
            assert_eq!(row.placement_status, PlacementStatus::Undecodable);
            assert!(row.transform.is_none());
            let detail = row.classification_detail.as_deref().unwrap();
            assert!(
                detail.contains("connector-frame refusal blocks binding"),
                "{detail}"
            );
        }
    }

    #[test]
    fn unique_body_keeps_the_s7_placement() {
        // The S7 shape still places when the body appears in exactly one
        // document of the walked set (the swbd nut-bt family).
        let docs = documents(&[
            (
                "Solo",
                name_table_product_translations(
                    "Solo",
                    &["Widget", "Bracket"],
                    &[[12.5, 0.0, 14.4], [12.5, 0.0, 14.4]],
                ),
            ),
            (
                "Elsewhere",
                name_table_product_translations("Elsewhere", &["Nut"], &[[1.0, 2.0, 3.0]]),
            ),
        ]);

        let tree = resolve_owned_assembly("Solo", &docs);

        assert_eq!(tree.placed_instances, 2);
        for row in &tree.instances {
            assert_eq!(row.placement_status, PlacementStatus::Placed);
            assert_eq!(row.transform, Some([12.5, 0.0, 14.4, 1.0, 0.0, 0.0, 0.0]));
        }
    }
}
