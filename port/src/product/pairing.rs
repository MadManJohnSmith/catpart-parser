//! The CATProduct structure pool pairing laws and assembly constraint separation.
//!
//! Authority: `docs/specs/phase6-assembly-viewer-spec.md` (§2.3) and
//! `docs/evidence/2026-11-14-p2-pool-pairing.md` (§4).
//! Constraint resolution: `scripts/triage/p26_instance_binding.py`.
//!
//! # The Three Pairing Laws
//!
//! 1. **Identity Triple** (P2-identity-triple, 216/253 framed files, FACT):
//!    `<PartNumber> _InstanceName <InstanceName>`
//!    The instance's component part number strictly precedes the `_InstanceName` token;
//!    the instance name strictly follows it.
//! 2. **Description Block** (P2-desc-instance-block, 17 files, FACT):
//!    `<PN> _DescriptionInst <PN:1> _InstanceName <PN_1> _Position`
//!    Serializes colon-form (`PN:1`) and underscore-form (`PN_1`) instance aliases
//!    alongside the `_Position` attribute token.
//! 3. **Bare Pair Adjacency** (P2-bare-pair, 9 files, INFERENCE):
//!    `<PartNumber> <InstanceName>`
//!    Adjacent strings matching `<stem>` and `<stem>.<N>` without an intervening `_InstanceName` token.
//!
//! # Assembly Constraint Separation Rule
//!
//! In CATIA V5, assembly constraints (e.g. `Coincidence.1`, `Surface contact.2`, `Offset.1`, `Fix.1`)
//! use the same dot-shape `<name>.<N>` naming convention. A dot-shaped name is classified as an
//! assembly constraint if its case-insensitive prefix matches any canonical constraint token in
//! [`CONSTRAINT_PREFIXES`]. Instances whose prefix matches this vocabulary are classified as
//! assembly constraints and excluded from the physical part instance tree.

#![allow(clippy::suboptimal_flops)]

use serde::{Deserialize, Serialize};

use super::binding::PlacementStatus;
use super::pool::{
    BINARY_SENTINEL, is_class_token, is_colon_shape, is_dot_shape, is_token, is_uscore_shape,
};

/// Comprehensive English and French assembly constraint prefixes in CATIA V5 pools.
pub const CONSTRAINT_PREFIXES: &[&str] = &[
    "coincidence",
    "coïncidence",
    "cx_coincidence",
    "surface contact",
    "contact surfacique",
    "cx_surface contact",
    "offset",
    "décalage",
    "fix",
    "fixe",
    "angle",
    "contact linéique",
    "line contact",
    "contact ponctuel",
    "point contact",
    "parallelism",
    "parallélisme",
    "perpendicularity",
    "perpendicularité",
];

/// Check whether a name represents an assembly constraint rather than a part instance.
pub fn is_constraint_name(name: &str) -> bool {
    let prefix = name.split('.').next().unwrap_or("").trim().to_lowercase();
    CONSTRAINT_PREFIXES
        .iter()
        .any(|&cst| prefix.starts_with(cst))
}

/// Separate true component/part instance names from assembly constraints
/// across a pool's string items (mirrors `p26.classify_pool_names`).
pub fn separate_instances_and_constraints(texts: &[String]) -> (Vec<String>, Vec<String>) {
    let mut instances = Vec::new();
    let mut constraints = Vec::new();
    for t in texts {
        if is_dot_shape(t) {
            if is_constraint_name(t) {
                constraints.push(t.clone());
            } else {
                instances.push(t.clone());
            }
        } else if is_colon_shape(t) {
            instances.push(t.clone());
        }
    }
    (instances, constraints)
}

/// Pairing rule by which a product instance was bound to its part number.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PairingRule {
    /// Identity Triple: `<PartNumber> _InstanceName <InstanceName>`
    Triple,
    /// Description Block: `<PN> _DescriptionInst <PN:1> _InstanceName <PN_1> _Position`
    DescBlock,
    /// Bare Pair: `<PartNumber> <InstanceName>`
    BarePair,
    /// V5R26 name table: an interned name item, with no per-instance marker.
    NameTable,
}

impl PairingRule {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Triple => "triple",
            Self::DescBlock => "desc_block",
            Self::BarePair => "bare_pair",
            Self::NameTable => "name_table",
        }
    }
}

/// Depth of the V5R26 schema head (items `0..22`, ending at `_Reps`).
pub const NAME_TABLE_HEAD_DEPTH: usize = 22;

/// Fixed V5R26 schema items that are never instance names.
pub const NAME_TABLE_SCHEMA_TOKENS: &[&str] = &[
    "ASMProduct",
    "_BagRepsList",
    "_PrdVersion",
    "_PubConnectors",
    "_AttrForLiterals",
    "_RefProduct",
    "_Disciplines",
    "PRDBAGREP",
    "3DIC",
    "_Reps",
    "_Version",
    "IsRoot",
    "PRDREP",
    "TEMP",
];

/// Container whose presence marks the older COSO/SERVO pool generation.
pub const CATMECH_PROD_CONTAINER: &str = "CATMechProdCont";

/// A decoded V5R26 name table.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NameTable {
    /// Value of the first `_PartNumber` item (the document's own product name).
    pub self_name: Option<String>,
    /// Interned value items after the schema head, in table order.
    pub names: Vec<String>,
}

/// Structural signature of a V5R26 name-table pool.
///
/// The caller must also require that the marker passes extracted zero
/// instances (`read_name_table` is only the signature) so a document the
/// existing pairing laws decode is never re-decided.
pub fn has_name_table_signature(texts: &[String]) -> bool {
    if texts.iter().take(24).any(|t| t == CATMECH_PROD_CONTAINER) {
        return false;
    }
    let head = &texts[..texts.len().min(NAME_TABLE_HEAD_DEPTH)];
    head.windows(2)
        .any(|pair| pair[0] == "PRDBAGREP" && pair[1] == "3DIC")
}

/// Recognise the name-table signature and enumerate its interned names.
///
/// The body is a bag: it lists the document's own children and the leaves of
/// the sub-products it references. Attribution is the walker's job
/// (`ownership::own_children`); enumeration must not sort or reorder, because
/// the table order is not an instance order (alphabetized in A1/A3, logical in
/// B4/B2).
pub fn read_name_table(texts: &[String]) -> Option<NameTable> {
    if !has_name_table_signature(texts) {
        return None;
    }

    let self_name = texts
        .iter()
        .position(|t| t == "_PartNumber")
        .and_then(|i| texts.get(i + 1))
        .filter(|t| !is_token(t) && !is_class_token(t) && *t != BINARY_SENTINEL)
        .cloned();

    let mut head_end = 0;
    for (i, text) in texts.iter().take(NAME_TABLE_HEAD_DEPTH).enumerate() {
        if is_token(text)
            || is_class_token(text)
            || NAME_TABLE_SCHEMA_TOKENS.contains(&text.as_str())
        {
            head_end = i + 1;
        }
    }

    let mut names = Vec::new();
    let mut seen = std::collections::HashSet::new();
    for text in texts.iter().skip(head_end) {
        if text.is_empty()
            || text == BINARY_SENTINEL
            || is_token(text)
            || is_class_token(text)
            || NAME_TABLE_SCHEMA_TOKENS.contains(&text.as_str())
            || self_name.as_ref() == Some(text)
        {
            continue;
        }
        if seen.insert(text.as_str()) {
            names.push(text.clone());
        }
    }
    Some(NameTable { self_name, names })
}

/// Enumerate one unplaced instance record per interned name.
///
/// Placement is filled by `binding::bind_name_table` (zero records -> identity,
/// any record -> undecodable).
pub fn extract_name_table_instances(texts: &[String]) -> Option<Vec<InstanceRecord>> {
    let table = read_name_table(texts)?;
    Some(
        table
            .names
            .into_iter()
            .map(|name| InstanceRecord {
                instance_name: name.clone(),
                part_number: name,
                pairing_rule: PairingRule::NameTable,
                has_position_attr: false,
                placement_status: PlacementStatus::Identity,
                transform: None,
                object_tag: None,
                classification_detail: None,
            })
            .collect(),
    )
}

/// An instance record extracted from a CATProduct structure pool.
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ProductInstanceRecord {
    pub instance_name: String,
    pub part_number: String,
    pub pairing_rule: PairingRule,
    pub has_position_attr: bool,
    pub placement_status: PlacementStatus,
    pub transform: Option<[f64; 7]>,
    pub object_tag: Option<u32>,
    pub classification_detail: Option<String>,
}

pub type InstanceRecord = ProductInstanceRecord;

/// Extract all physical part instances from a decoded pool text sequence.
///
/// Applies the three pairing rules in order of precedence:
/// 1. Description blocks: `<PN> _DescriptionInst <PN:1> _InstanceName <PN_1> _Position`
/// 2. Identity triples: `<PartNumber> _InstanceName <InstanceName>` (or empty marker)
/// 3. Bare pairs: `<PartNumber> <InstanceName>` matching `<stem>` and `<stem>.<N>`
///
/// Filters out all assembly constraints (`Offset`, `Coincidence`, `Fix`, etc.).
pub fn extract_instances(texts: &[String], pool_has_position: bool) -> Vec<InstanceRecord> {
    let mut records = Vec::new();
    let mut consumed_indices = std::collections::HashSet::new();
    let n = texts.len();

    // Pass 1: Explicit markers (_InstanceName and Description Blocks)
    for i in 0..n {
        let is_marker = texts[i] == "_InstanceName"
            || (texts[i].is_empty() && i > 0 && i + 1 < n && is_dot_shape(&texts[i + 1]));

        if is_marker {
            // Check for Description Block: <PN> _DescriptionInst <PN:1> _InstanceName <PN_1> _Position
            if i >= 2 && texts[i - 2] == "_DescriptionInst" {
                let pn = if i >= 3
                    && !is_token(&texts[i - 3])
                    && !is_class_token(&texts[i - 3])
                    && texts[i - 3] != BINARY_SENTINEL
                {
                    texts[i - 3].clone()
                } else if let Some((stem, _)) = texts[i - 1].split_once(':') {
                    stem.to_string()
                } else {
                    texts[i - 1].clone()
                };

                let instance_name = if is_colon_shape(&texts[i - 1]) || is_dot_shape(&texts[i - 1])
                {
                    texts[i - 1].clone()
                } else if i + 1 < n
                    && !is_token(&texts[i + 1])
                    && !texts[i + 1].trim().is_empty()
                    && texts[i + 1] != BINARY_SENTINEL
                {
                    texts[i + 1].clone()
                } else {
                    texts[i - 1].clone()
                };

                if !is_constraint_name(&instance_name) {
                    let has_position =
                        (i + 2 < n && texts[i + 2] == "_Position") || pool_has_position;
                    let placement_status = if has_position {
                        PlacementStatus::Placed
                    } else {
                        PlacementStatus::Identity
                    };
                    records.push(InstanceRecord {
                        instance_name,
                        part_number: pn,
                        pairing_rule: PairingRule::DescBlock,
                        has_position_attr: has_position,
                        placement_status,
                        transform: None,
                        object_tag: None,
                        classification_detail: None,
                    });
                }
                consumed_indices.insert(i - 1);
                consumed_indices.insert(i + 1);
            } else if i > 0 && i + 1 < n {
                // Identity Triple: <PartNumber> _InstanceName <InstanceName>
                let prev = &texts[i - 1];
                let next = &texts[i + 1];
                if !is_token(prev)
                    && !is_token(next)
                    && prev != BINARY_SENTINEL
                    && next != BINARY_SENTINEL
                    && !is_class_token(prev)
                {
                    if !is_constraint_name(next) {
                        let has_position =
                            (i + 2 < n && texts[i + 2] == "_Position") || pool_has_position;
                        let placement_status = if has_position {
                            PlacementStatus::Placed
                        } else {
                            PlacementStatus::Identity
                        };
                        records.push(InstanceRecord {
                            instance_name: next.clone(),
                            part_number: prev.clone(),
                            pairing_rule: PairingRule::Triple,
                            has_position_attr: has_position,
                            placement_status,
                            transform: None,
                            object_tag: None,
                            classification_detail: None,
                        });
                    }
                    consumed_indices.insert(i - 1);
                    consumed_indices.insert(i + 1);
                }
            }
        }
    }

    // Pass 2: Bare pairs and remaining dot- or colon-shaped instances
    for i in 0..n {
        if consumed_indices.contains(&i) {
            continue;
        }
        let curr = &texts[i];
        let is_dot = is_dot_shape(curr);
        let is_colon = is_colon_shape(curr);
        if (!is_dot && !is_colon) || is_constraint_name(curr) || curr == BINARY_SENTINEL {
            continue;
        }
        // If immediately preceded by ASMPRODUCT, this is the root product name
        if i > 0 && texts[i - 1] == "ASMPRODUCT" {
            continue;
        }

        let stem = if is_dot {
            curr.rsplit_once('.').unwrap().0
        } else {
            curr.rsplit_once(':').unwrap().0
        };
        let (pn, rule) = if i > 0
            && !is_token(&texts[i - 1])
            && !is_class_token(&texts[i - 1])
            && texts[i - 1] == stem
        {
            (texts[i - 1].clone(), PairingRule::BarePair)
        } else {
            (stem.to_string(), PairingRule::BarePair)
        };

        let has_position = (i + 1 < n && texts[i + 1] == "_Position") || pool_has_position;
        let placement_status = if has_position {
            PlacementStatus::Placed
        } else {
            PlacementStatus::Identity
        };

        records.push(InstanceRecord {
            instance_name: curr.clone(),
            part_number: pn,
            pairing_rule: rule,
            has_position_attr: has_position,
            placement_status,
            transform: None,
            object_tag: None,
            classification_detail: None,
        });
        consumed_indices.insert(i);
        if is_colon && i + 1 < n && is_uscore_shape(&texts[i + 1]) {
            consumed_indices.insert(i + 1);
        }
    }

    records
}

/// Statistical measurement summary over a pool's string items
/// (mirrors `p2_pool_pairing.py:classify_pairings`).
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct PairingClassificationSummary {
    pub inst_marker: usize,
    pub inst_triple: usize,
    pub inst_triple_dotnext: usize,
    pub desc_block: usize,
    pub desc_colon_form: usize,
    pub desc_uscore_form: usize,
    pub bare_pair: usize,
    pub bare_pair_stem: usize,
    pub position_tokens: usize,
    pub position_succ_token: usize,
    pub position_succ_value: usize,
    pub position_succ_numeric: usize,
    pub asmp_count: usize,
    pub asmp_succ_value: usize,
    pub prdrep_count: usize,
    pub prdrep_succ_value: usize,
    pub isroot_present: usize,
    pub isroot_last: bool,
}

/// Compute pairing classification measurements over one decoded chain.
pub fn classify_pairings(texts: &[String]) -> PairingClassificationSummary {
    let mut out = PairingClassificationSummary::default();
    let n = texts.len();

    for (i, t) in texts.iter().enumerate() {
        let prev_t = if i > 0 { Some(&texts[i - 1]) } else { None };
        let next_t = if i + 1 < n { Some(&texts[i + 1]) } else { None };

        if t == "_InstanceName" {
            out.inst_marker += 1;
            if let (Some(prev), Some(next)) = (prev_t, next_t)
                && !is_token(prev)
                && !is_token(next)
                && prev != BINARY_SENTINEL
                && next != BINARY_SENTINEL
            {
                out.inst_triple += 1;
                if is_dot_shape(next) {
                    out.inst_triple_dotnext += 1;
                }
            }
            if i >= 2
                && texts[i - 2] == "_DescriptionInst"
                && let Some(prev) = prev_t
                && !is_token(prev)
            {
                out.desc_block += 1;
                if is_colon_shape(prev) {
                    out.desc_colon_form += 1;
                }
                if let Some(next) = next_t
                    && is_uscore_shape(next)
                {
                    out.desc_uscore_form += 1;
                }
            }
        } else if t == "_Position" {
            out.position_tokens += 1;
            match next_t {
                None => {
                    out.position_succ_token += 1;
                }
                Some(next) => {
                    if is_token(next) || is_class_token(next) {
                        out.position_succ_token += 1;
                    } else {
                        out.position_succ_value += 1;
                        if next.parse::<f64>().is_ok() {
                            out.position_succ_numeric += 1;
                        }
                    }
                }
            }
        } else if t == "ASMPRODUCT" {
            out.asmp_count += 1;
            if let Some(next) = next_t
                && !is_token(next)
                && !is_class_token(next)
            {
                out.asmp_succ_value += 1;
            }
        } else if t == "PRDREP" {
            out.prdrep_count += 1;
            if let Some(next) = next_t
                && !is_token(next)
                && !is_class_token(next)
            {
                out.prdrep_succ_value += 1;
            }
        } else if t == "IsRoot" {
            out.isroot_present += 1;
            if i == n - 1 {
                out.isroot_last = true;
            }
        }

        // Bare pair check: a non-token followed by a dot-shaped non-token
        if let Some(prev) = prev_t
            && !is_token(t)
            && !prev.starts_with('!')
            && !is_token(prev)
            && !is_class_token(prev)
            && prev != BINARY_SENTINEL
            && is_dot_shape(t)
        {
            out.bare_pair += 1;
            let stem = t.rsplit_once('.').unwrap().0;
            if prev == stem {
                out.bare_pair_stem += 1;
            }
        }
    }

    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn constraint_filtering() {
        assert!(is_constraint_name("Fix.1"));
        assert!(is_constraint_name("Fixe.75"));
        assert!(is_constraint_name("Coincidence.2"));
        assert!(is_constraint_name("coïncidence.3"));
        assert!(is_constraint_name("Surface contact.1"));
        assert!(is_constraint_name("contact surfacique.4"));
        assert!(is_constraint_name("Offset.103"));
        assert!(is_constraint_name("décalage.5"));
        assert!(is_constraint_name("Angle.1"));
        assert!(is_constraint_name("Parallelism.1"));
        assert!(is_constraint_name("Perpendicularity.1"));

        assert!(!is_constraint_name("Part11.1"));
        assert!(!is_constraint_name("Bolt_M8.2"));
        assert!(!is_constraint_name("Product1.1"));
        assert!(!is_constraint_name("ac2:1"));
    }

    #[test]
    fn separate_instances_and_constraints_test() {
        let texts = vec![
            "Part11.1".to_string(),
            "Fix.75".to_string(),
            "Offset.103".to_string(),
            "Part11.2".to_string(),
            "Surface contact.5".to_string(),
            "ac2:1".to_string(),
        ];
        let (insts, csts) = separate_instances_and_constraints(&texts);
        assert_eq!(insts, vec!["Part11.1", "Part11.2", "ac2:1"]);
        assert_eq!(csts, vec!["Fix.75", "Offset.103", "Surface contact.5"]);
    }

    #[test]
    fn identity_triple_extraction() {
        let texts = vec![
            "ASMPRODUCT".to_string(),
            "Product1".to_string(),
            "Part001".to_string(),
            "_InstanceName".to_string(),
            "Part001.1".to_string(),
            "_Position".to_string(),
            "PRDREP".to_string(),
        ];
        let records = extract_instances(&texts, true);
        assert_eq!(records.len(), 1);
        let rec = &records[0];
        assert_eq!(rec.part_number, "Part001");
        assert_eq!(rec.instance_name, "Part001.1");
        assert_eq!(rec.pairing_rule, PairingRule::Triple);
        assert!(rec.has_position_attr);
        assert_eq!(rec.placement_status, "placed");
    }

    #[test]
    fn description_block_extraction() {
        let texts = vec![
            "ac2".to_string(),
            "_DescriptionInst".to_string(),
            "ac2:1".to_string(),
            "_InstanceName".to_string(),
            "ac2_1".to_string(),
            "_Position".to_string(),
        ];
        let records = extract_instances(&texts, true);
        assert_eq!(records.len(), 1);
        let rec = &records[0];
        assert_eq!(rec.part_number, "ac2");
        assert_eq!(rec.instance_name, "ac2:1");
        assert_eq!(rec.pairing_rule, PairingRule::DescBlock);
        assert!(rec.has_position_attr);
        assert_eq!(rec.placement_status, "placed");
    }

    #[test]
    fn bare_pair_extraction() {
        let texts = vec![
            "Part11".to_string(),
            "Part11.1".to_string(),
            "Part11.2".to_string(),
        ];
        let records = extract_instances(&texts, false);
        assert_eq!(records.len(), 2);
        assert_eq!(records[0].part_number, "Part11");
        assert_eq!(records[0].instance_name, "Part11.1");
        assert_eq!(records[0].pairing_rule, PairingRule::BarePair);
        assert!(!records[0].has_position_attr);
        assert_eq!(records[0].placement_status, "identity");

        assert_eq!(records[1].part_number, "Part11");
        assert_eq!(records[1].instance_name, "Part11.2");
        assert_eq!(records[1].pairing_rule, PairingRule::BarePair);
    }

    #[test]
    fn constraint_is_excluded_from_instances() {
        let texts = vec![
            "Part1".to_string(),
            "_InstanceName".to_string(),
            "Fix.1".to_string(),
            "Offset.2".to_string(),
            "Part2".to_string(),
            "_InstanceName".to_string(),
            "Part2.1".to_string(),
        ];
        let records = extract_instances(&texts, false);
        assert_eq!(records.len(), 1);
        assert_eq!(records[0].instance_name, "Part2.1");
        assert_eq!(records[0].part_number, "Part2");
    }

    fn name_table_texts(names: &[&str]) -> Vec<String> {
        let mut texts: Vec<String> = [
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
        ]
        .iter()
        .map(|s| (*s).to_string())
        .collect();
        texts.push("TableAssembly".to_string());
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
            texts.push(text.to_string());
        }
        texts.extend(names.iter().map(|s| (*s).to_string()));
        texts.push("IsRoot".to_string());
        texts
    }

    #[test]
    fn name_table_signature_and_extraction() {
        let texts = name_table_texts(&["Widget", "Bracket"]);
        assert!(has_name_table_signature(&texts));

        let table = read_name_table(&texts).expect("name table");
        assert_eq!(table.self_name.as_deref(), Some("TableAssembly"));
        assert_eq!(table.names, vec!["Widget", "Bracket"]);

        let records = extract_name_table_instances(&texts).expect("instances");
        assert_eq!(records.len(), 2);
        assert_eq!(records[0].instance_name, "Widget");
        assert_eq!(records[0].part_number, "Widget");
        assert_eq!(records[0].pairing_rule, PairingRule::NameTable);
        assert!(!records[0].has_position_attr);
    }

    #[test]
    fn name_table_keeps_table_order_and_drops_self_name() {
        // A1/A3 shape: alphabetized pool, document order not recoverable from it.
        let texts = name_table_texts(&["aardvark", "mike", "zulu", "TableAssembly"]);
        let table = read_name_table(&texts).expect("name table");
        assert_eq!(table.names, vec!["aardvark", "mike", "zulu"]);
    }

    #[test]
    fn name_table_signature_rejects_other_generations() {
        let mut with_mechprod = name_table_texts(&["Widget"]);
        with_mechprod[6] = CATMECH_PROD_CONTAINER.to_string();
        assert!(!has_name_table_signature(&with_mechprod));
        assert!(read_name_table(&with_mechprod).is_none());

        let mut without_bag = name_table_texts(&["Widget"]);
        without_bag.retain(|t| t != "PRDBAGREP" && t != "3DIC");
        assert!(!has_name_table_signature(&without_bag));
        assert!(read_name_table(&without_bag).is_none());
    }

    #[test]
    fn classify_pairings_selftest_vectors() {
        let texts = vec![
            "CATCatalogManager".to_string(),
            "catalogManager".to_string(),
            "catalogLinks".to_string(),
            "".to_string(),
            "ASMPRODUCT".to_string(),
            "Product1".to_string(),
            "_PartNumber".to_string(),
            "Part001".to_string(),
            "_InstanceName".to_string(),
            "Part001.1".to_string(),
            "_Position".to_string(),
            "PRDREP".to_string(),
            "Shape 1".to_string(),
            "IsRoot".to_string(),
        ];
        let summary = classify_pairings(&texts);
        assert_eq!(summary.inst_triple, 1);
        assert_eq!(summary.inst_triple_dotnext, 1);
        assert_eq!(summary.position_succ_token, 1);
        assert_eq!(summary.position_succ_numeric, 0);
        assert_eq!(summary.asmp_succ_value, 1);
        assert_eq!(summary.prdrep_succ_value, 1);
        assert!(summary.isroot_last);
    }
}
