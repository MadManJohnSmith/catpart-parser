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
}

impl PairingRule {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Triple => "triple",
            Self::DescBlock => "desc_block",
            Self::BarePair => "bare_pair",
        }
    }
}

/// An instance record extracted from a CATProduct structure pool.
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ProductInstanceRecord {
    pub instance_name: String,
    pub part_number: String,
    pub pairing_rule: PairingRule,
    pub has_position_attr: bool,
    pub placement_status: String,
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
                        "placed".to_string()
                    } else {
                        "identity".to_string()
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
                            "placed".to_string()
                        } else {
                            "identity".to_string()
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

    // Pass 2: Bare pairs and remaining dot-shaped instances
    for i in 0..n {
        if consumed_indices.contains(&i) {
            continue;
        }
        let curr = &texts[i];
        if !is_dot_shape(curr) || is_constraint_name(curr) || curr == BINARY_SENTINEL {
            continue;
        }
        // If immediately preceded by ASMPRODUCT, this is the root product name
        if i > 0 && texts[i - 1] == "ASMPRODUCT" {
            continue;
        }

        let stem = curr.rsplit_once('.').unwrap().0;
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
            "placed".to_string()
        } else {
            "identity".to_string()
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
