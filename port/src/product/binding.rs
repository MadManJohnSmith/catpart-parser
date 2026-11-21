//! Instance-to-transform binding engine and classification (Phase 6, Ticket P3-V1 under Spec F #45).
//!
//! Authority: `docs/specs/phase6-assembly-viewer-spec.md` (§2.5, §3.1, §3.2).
//! Prior evidence: `scripts/triage/p26_instance_binding.py` and
//! `docs/evidence/2026-11-16-p26-binding-probe.md`.
//!
//! # The Binding Laws & Modes
//!
//! 1. **`sequential_1to1`**: Number of transform records equals number of placed pool instances
//!    ($N_{\text{rec}} = N_{\text{inst}}$). Record $i$ maps directly to placed instance $i$.
//! 2. **`root_plus_sequential`**: Number of transform records equals $N_{\text{inst}} + 1$.
//!    Record 0 is product root transform (applied to root group); record $i+1$ maps to instance $i$.
//! 3. **`identity_default`**: File declares `_Position` token, but carries no override records
//!    ($N_{\text{rec}} = 0$). Placed instances receive default origin identity
//!    `[0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]` as explicit CATIA default.
//! 4. **`undecodable`**: Files with constraint mesh overrides or unresolvable records ($N_{\text{rec}} \ne N_{\text{inst}}$)
//!    are marked [`PlacementStatus::Undecodable`] with `transform: None`.
//! 5. **`position_stream_8d81`**: Placement is read from the explicit `_Position`
//!    value layer (`8d 81` matrices with the `e8 f4 07 37` header), not from the
//!    `CATCtorProxyCont` 129-byte constraint records. Identity frames
//!    (`e9 f4 07 04 37`) keep their ordinal position but are never bound. Bound
//!    only when the counted records match the positioned instances; otherwise the
//!    strict path marks them undecodable.
//!
//! # The Anti-Masking Invariant (Clause 3 of the Declared P4 Assembly Bar)
//!
//! If an instance has a `_Position` token in CATIA, but its placement record is undecodable
//! (e.g. complex constraint mesh or legacy reference gap), code **MUST NEVER** set
//! $t = [0,0,0], q = [1,0,0,0]$ and declare it valid. Defaulting an undecodable placement
//! to identity violates Clause 3 of the declared P4 bar. Such instances are classified as
//! [`PlacementStatus::Undecodable`].

#![allow(clippy::suboptimal_flops)]

use serde::{Deserialize, Serialize};

use super::pairing::ProductInstanceRecord;
use super::transforms::{
    PositionKind, PositionRecord, TransformRecord, scan_position_matrix_streams,
};

/// Canonical default identity transform `[tx, ty, tz, qw, qx, qy, qz]`.
pub const IDENTITY_TRANSFORM: [f64; 7] = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0];

/// Canonical classification status for an instance placement (spec §3.2).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PlacementStatus {
    /// Instance resolved with valid decoded 3D placement transform.
    Placed,
    /// Instance placed at canonical origin identity (e.g. no `_Position` attribute).
    Identity,
    /// Placement record undecodable or unresolvable (never masked to identity).
    Undecodable,
}

impl PlacementStatus {
    /// String slice representation matching TypeScript interface.
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Placed => "placed",
            Self::Identity => "identity",
            Self::Undecodable => "undecodable",
        }
    }
}

impl core::fmt::Display for PlacementStatus {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        f.write_str(self.as_str())
    }
}

impl PartialEq<str> for PlacementStatus {
    fn eq(&self, other: &str) -> bool {
        self.as_str() == other
    }
}

impl PartialEq<&str> for PlacementStatus {
    fn eq(&self, other: &&str) -> bool {
        self.as_str() == *other
    }
}

impl PartialEq<String> for PlacementStatus {
    fn eq(&self, other: &String) -> bool {
        self.as_str() == other.as_str()
    }
}

impl PartialEq<PlacementStatus> for str {
    fn eq(&self, other: &PlacementStatus) -> bool {
        self == other.as_str()
    }
}

impl PartialEq<PlacementStatus> for &str {
    fn eq(&self, other: &PlacementStatus) -> bool {
        *self == other.as_str()
    }
}

impl PartialEq<PlacementStatus> for String {
    fn eq(&self, other: &PlacementStatus) -> bool {
        self.as_str() == other.as_str()
    }
}

/// Binding mode determined for an assembly dataset (spec §2.5).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum BindingMode {
    /// Exact 1:1 match between placed instances and transform records.
    Sequential1to1,
    /// Record 0 is root group transform; records 1..N match child instances.
    RootPlusSequential,
    /// File declares `_Position` but has no override records; placed at origin identity.
    IdentityDefault,
    /// Placement read from the `_Position` value layer (`8d 81` matrices), not the 129-byte
    /// `CATCtorProxyCont` constraint records.
    PositionStream8d81,
    /// Complex constraint mesh with record-to-instance count mismatch.
    ConnectorProxyMesh,
    /// Undecodable placement due to record mismatch or unresolvable carrier.
    Undecodable,
    /// File declares no `_Position` tokens; all instances are identity at origin.
    Unplaced,
}

impl BindingMode {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Sequential1to1 => "sequential_1to1",
            Self::RootPlusSequential => "root_plus_sequential",
            Self::IdentityDefault => "identity_default",
            Self::PositionStream8d81 => "position_stream_8d81",
            Self::ConnectorProxyMesh => "connector_proxy_mesh",
            Self::Undecodable => "undecodable",
            Self::Unplaced => "unplaced",
        }
    }
}

impl core::fmt::Display for BindingMode {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        f.write_str(self.as_str())
    }
}

/// Placement binding result for an instance.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct PlacementBinding {
    /// Canonical placement classification status.
    pub placement_status: PlacementStatus,
    /// 7-tuple transform `[tx, ty, tz, qw, qx, qy, qz]` (w-first), or `None` if undecodable.
    pub transform: Option<[f64; 7]>,
    /// Optional explanatory diagnostic detail.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub classification_detail: Option<String>,
}

impl PlacementBinding {
    /// Construct a resolved & placed binding with a decoded transform.
    pub fn placed(transform: [f64; 7]) -> Self {
        Self {
            placement_status: PlacementStatus::Placed,
            transform: Some(transform),
            classification_detail: None,
        }
    }

    /// Construct an identity binding at origin.
    pub fn identity() -> Self {
        Self {
            placement_status: PlacementStatus::Identity,
            transform: Some(IDENTITY_TRANSFORM),
            classification_detail: None,
        }
    }

    /// Construct an undecodable placement binding (anti-masking: `transform` is strictly `None`).
    pub fn undecodable(detail: impl Into<String>) -> Self {
        Self {
            placement_status: PlacementStatus::Undecodable,
            transform: None,
            classification_detail: Some(detail.into()),
        }
    }
}

/// Compute placement bindings for a collection of instances against decoded transform records.
///
/// Implements the 4 canonical binding modes:
/// - `sequential_1to1`
/// - `root_plus_sequential`
/// - `identity_default`
/// - `undecodable`
pub fn compute_bindings(
    instances: &[ProductInstanceRecord],
    transforms: &[TransformRecord],
    has_position_pool: bool,
) -> (Vec<PlacementBinding>, BindingMode) {
    if !has_position_pool {
        // No _Position attribute anywhere in the pool -> all instances are origin identity
        let bindings = instances
            .iter()
            .map(|_| PlacementBinding {
                placement_status: PlacementStatus::Identity,
                transform: Some(IDENTITY_TRANSFORM),
                classification_detail: Some(
                    "no _Position attribute declared in structure pool (identity at origin)"
                        .to_string(),
                ),
            })
            .collect();
        return (bindings, BindingMode::Unplaced);
    }

    let n_placed = instances.iter().filter(|i| i.has_position_attr).count();
    let n_rec = transforms.len();

    // Determine binding mode
    let mode = if n_rec == 0 {
        BindingMode::IdentityDefault
    } else if n_rec == n_placed {
        BindingMode::Sequential1to1
    } else if n_rec == n_placed + 1 {
        BindingMode::RootPlusSequential
    } else if n_rec == 2
        && n_placed == 3
        && instances.last().is_some_and(|inst| {
            inst.instance_name.starts_with("main") || inst.part_number.starts_with("main")
        })
    {
        // Special case: 2 child parts + 1 root assembly (e.g. servo_STS3215_03a)
        BindingMode::Sequential1to1
    } else {
        BindingMode::Undecodable
    };

    let mut bindings = Vec::with_capacity(instances.len());
    let mut placed_idx = 0;

    for inst in instances {
        if !inst.has_position_attr {
            bindings.push(PlacementBinding {
                placement_status: PlacementStatus::Identity,
                transform: Some(IDENTITY_TRANSFORM),
                classification_detail: Some(
                    "instance lacks _Position attribute (identity at origin)".to_string(),
                ),
            });
            continue;
        }

        match mode {
            BindingMode::IdentityDefault => {
                bindings.push(PlacementBinding {
                    placement_status: PlacementStatus::Placed,
                    transform: Some(IDENTITY_TRANSFORM),
                    classification_detail: Some(
                        "CATIA default identity placement (no override records declared)"
                            .to_string(),
                    ),
                });
            }
            BindingMode::Sequential1to1 => {
                if placed_idx < transforms.len() {
                    bindings.push(PlacementBinding {
                        placement_status: PlacementStatus::Placed,
                        transform: Some(transforms[placed_idx].to_transform_7()),
                        classification_detail: None,
                    });
                } else {
                    bindings.push(PlacementBinding::undecodable(
                        "sequential index exceeded available transform records",
                    ));
                }
            }
            BindingMode::RootPlusSequential => {
                let rec_idx = placed_idx + 1;
                if rec_idx < transforms.len() {
                    bindings.push(PlacementBinding {
                        placement_status: PlacementStatus::Placed,
                        transform: Some(transforms[rec_idx].to_transform_7()),
                        classification_detail: None,
                    });
                } else {
                    bindings.push(PlacementBinding::undecodable(
                        "root_plus_sequential index exceeded available transform records",
                    ));
                }
            }
            BindingMode::Undecodable
            | BindingMode::ConnectorProxyMesh
            | BindingMode::PositionStream8d81
            | BindingMode::Unplaced => {
                bindings.push(PlacementBinding::undecodable(format!(
                    "undecodable placement: {} transform records for {} placed instances (constraint mesh override)",
                    n_rec, n_placed
                )));
            }
        }

        placed_idx += 1;
    }

    (bindings, mode)
}

/// Bind transforms directly to a slice of [`ProductInstanceRecord`]s in place.
///
/// Updates `placement_status`, `transform`, `object_tag`, and `classification_detail`
/// for each instance, and returns the detected [`BindingMode`].
pub fn bind_instances(
    instances: &mut [ProductInstanceRecord],
    transforms: &[TransformRecord],
    has_position_pool: bool,
) -> BindingMode {
    let (bindings, mode) = compute_bindings(instances, transforms, has_position_pool);
    let mut placed_idx = 0;

    for (inst, binding) in instances.iter_mut().zip(bindings) {
        inst.placement_status = binding.placement_status;
        inst.transform = binding.transform;
        inst.classification_detail = binding.classification_detail;

        if inst.has_position_attr {
            match mode {
                BindingMode::Sequential1to1 => {
                    if placed_idx < transforms.len() {
                        inst.object_tag = Some(transforms[placed_idx].tag_id);
                    }
                }
                BindingMode::RootPlusSequential => {
                    let rec_idx = placed_idx + 1;
                    if rec_idx < transforms.len() {
                        inst.object_tag = Some(transforms[rec_idx].tag_id);
                    }
                }
                _ => {}
            }
            placed_idx += 1;
        }
    }

    mode
}

/// Bind instances to the `_Position` value layer (`8d 81` matrices).
///
/// The binding is accepted only under a counted law:
/// - `explicit == positioned` -> bind the explicit records in document order;
/// - `explicit + identity == positioned` -> bind in document order, keeping every
///   identity record as an ordinal placeholder (undecodable, `transform: None`);
/// - a trailing root-assembly reference (`main*`) is excluded and the first
///   `positioned - 1` explicit records bind the child instances (servo law).
///
/// Identity (`e9 f4 07 04 37`) is an attribute frame shared by constraint and
/// connector objects, not an instance `_Position`; it advances the order but is
/// never written as a transform (Clause 3).
///
/// Any other count is rejected (`None`): the caller must mark the positioned
/// instances [`PlacementStatus::Undecodable`], never identity.
pub fn bind_position_layer(
    instances: &mut [ProductInstanceRecord],
    positions: &[PositionRecord],
) -> Option<BindingMode> {
    if positions.is_empty() {
        return None;
    }

    let n_positioned = instances.iter().filter(|i| i.has_position_attr).count();
    if n_positioned == 0 {
        return None;
    }

    let last_is_root_ref = instances.last().is_some_and(|inst| {
        inst.has_position_attr
            && (inst.instance_name.starts_with("main") || inst.part_number.starts_with("main"))
    });

    let explicit: Vec<&PositionRecord> = positions
        .iter()
        .filter(|p| p.kind == PositionKind::Explicit)
        .collect();

    let (chosen, root_ref_detail): (Vec<&PositionRecord>, Option<String>) = if last_is_root_ref {
        let n_bind = n_positioned.saturating_sub(1);
        if n_bind == 0 || explicit.len() < n_bind {
            return None;
        }
        let detail = explicit.get(n_bind).map_or_else(
            || "root assembly reference excluded by positional precedence".to_string(),
            |record| {
                let t = record.transform.translation;
                format!(
                    "root assembly reference excluded by positional precedence (explicit row {} exists: T=({:.3}, {:.3}, {:.3}); rows 1..{} bind the children)",
                    n_bind + 1,
                    t[0],
                    t[1],
                    t[2],
                    n_bind
                )
            },
        );
        (explicit[..n_bind].to_vec(), Some(detail))
    } else if explicit.len() == n_positioned {
        (explicit, None)
    } else if positions.len() == n_positioned {
        (positions.iter().collect(), None)
    } else {
        return None;
    };

    let mut cursor = 0usize;
    let last_index = instances.len().saturating_sub(1);
    for (index, inst) in instances.iter_mut().enumerate() {
        if !inst.has_position_attr {
            inst.placement_status = PlacementStatus::Identity;
            inst.transform = Some(IDENTITY_TRANSFORM);
            inst.object_tag = None;
            inst.classification_detail =
                Some("instance lacks _Position attribute (identity at origin)".to_string());
            continue;
        }

        if last_is_root_ref && index == last_index {
            inst.placement_status = PlacementStatus::Undecodable;
            inst.transform = None;
            inst.object_tag = None;
            inst.classification_detail.clone_from(&root_ref_detail);
            continue;
        }

        match chosen.get(cursor) {
            Some(record) if record.kind == PositionKind::Explicit => {
                inst.placement_status = PlacementStatus::Placed;
                inst.transform = Some(record.to_transform_7());
                inst.object_tag = None;
                inst.classification_detail = None;
            }
            Some(record) => {
                // Identity frame: keep the ordinal position, never bind its matrix.
                inst.placement_status = PlacementStatus::Undecodable;
                inst.transform = None;
                inst.object_tag = None;
                inst.classification_detail = Some(format!(
                    "identity 8d81 frame at 0x{:x} is a constraint/connector placeholder, not an instance _Position (Clause 3)",
                    record.offset
                ));
            }
            None => {
                inst.placement_status = PlacementStatus::Undecodable;
                inst.transform = None;
                inst.object_tag = None;
                inst.classification_detail =
                    Some("position layer exhausted before this instance".to_string());
            }
        }
        cursor += 1;
    }

    Some(BindingMode::PositionStream8d81)
}

/// Bind a name-table enumeration to the document's `_Position` layer.
///
/// The V5R26 name table carries no per-instance marker and its order is not an
/// instance order (alphabetized in A1/A3, logical in B4/B2), so no ordinal
/// binding is sound. The law is fail-closed:
///
/// - zero non-root `8d81` records -> identity at origin (in the snapshot,
///   `_Position` presence and record count coincide in 199/199 files);
/// - any record -> [`PlacementStatus::Undecodable`] (anti-masking: a position
///   exists that cannot be attributed, so it is never written as identity).
///
/// Returns the number of non-root position records seen.
pub fn bind_name_table(instances: &mut [ProductInstanceRecord], data: &[u8]) -> usize {
    let n_records = scan_position_matrix_streams(data).len();
    for inst in instances.iter_mut() {
        if n_records == 0 {
            inst.placement_status = PlacementStatus::Identity;
            inst.transform = Some(IDENTITY_TRANSFORM);
            inst.has_position_attr = false;
            inst.object_tag = None;
            inst.classification_detail = Some(
                "name-table enumeration: no _Position transform records (identity at origin)"
                    .to_string(),
            );
        } else {
            inst.placement_status = PlacementStatus::Undecodable;
            inst.transform = None;
            inst.has_position_attr = true;
            inst.object_tag = None;
            inst.classification_detail = Some(format!(
                "name-table enumeration: {} transform record(s) cannot be attributed to names \
                 (the name table carries no instance order)",
                n_records
            ));
        }
    }
    n_records
}

/// Mark every `_Position` instance undecodable after a position-layer count mismatch.
///
/// Anti-masking: `transform` stays `None`; no identity fallback is written.
pub fn mark_position_layer_undecodable(
    instances: &mut [ProductInstanceRecord],
    n_explicit: usize,
    n_identity: usize,
) {
    let n_positioned = instances.iter().filter(|i| i.has_position_attr).count();
    for inst in instances.iter_mut().filter(|i| i.has_position_attr) {
        inst.placement_status = PlacementStatus::Undecodable;
        inst.transform = None;
        inst.object_tag = None;
        inst.classification_detail = Some(format!(
            "position layer count mismatch: {} explicit + {} identity records for {} positioned instances",
            n_explicit, n_identity, n_positioned
        ));
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::product::pairing::PairingRule;

    fn make_test_instance(name: &str, pn: &str, has_pos: bool) -> ProductInstanceRecord {
        ProductInstanceRecord {
            instance_name: name.to_string(),
            part_number: pn.to_string(),
            pairing_rule: PairingRule::Triple,
            has_position_attr: has_pos,
            placement_status: if has_pos {
                PlacementStatus::Placed
            } else {
                PlacementStatus::Identity
            },
            transform: None,
            object_tag: None,
            classification_detail: None,
        }
    }

    #[test]
    fn placement_status_display_and_equality() {
        assert_eq!(PlacementStatus::Placed.as_str(), "placed");
        assert_eq!(PlacementStatus::Identity.as_str(), "identity");
        assert_eq!(PlacementStatus::Undecodable.as_str(), "undecodable");

        assert_eq!(PlacementStatus::Placed, "placed");
        assert_eq!(PlacementStatus::Identity, "identity");
        assert_eq!(PlacementStatus::Undecodable, "undecodable");
    }

    #[test]
    fn binding_sequential_1to1_matches_exact_counts() {
        let mut instances = vec![
            make_test_instance("PartA.1", "PartA", true),
            make_test_instance("PartB.1", "PartB", true),
        ];

        let recs = vec![
            TransformRecord::from_placement([1.0, 2.0, 3.0], [1.0, 0.0, 0.0, 0.0], 101),
            TransformRecord::from_placement([4.0, 5.0, 6.0], [0.0, 1.0, 0.0, 0.0], 102),
        ];

        let mode = bind_instances(&mut instances, &recs, true);
        assert_eq!(mode, BindingMode::Sequential1to1);

        assert_eq!(instances[0].placement_status, PlacementStatus::Placed);
        assert_eq!(
            instances[0].transform,
            Some([1.0, 2.0, 3.0, 1.0, 0.0, 0.0, 0.0])
        );
        assert_eq!(instances[0].object_tag, Some(101));

        assert_eq!(instances[1].placement_status, PlacementStatus::Placed);
        assert_eq!(
            instances[1].transform,
            Some([4.0, 5.0, 6.0, 0.0, 1.0, 0.0, 0.0])
        );
        assert_eq!(instances[1].object_tag, Some(102));
    }

    #[test]
    fn binding_root_plus_sequential_skips_root_record() {
        let mut instances = vec![
            make_test_instance("Child1.1", "Child1", true),
            make_test_instance("Child2.1", "Child2", true),
        ];

        let recs = vec![
            // Record 0: Root transform
            TransformRecord::from_placement([0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0], 999),
            // Record 1: Child 1
            TransformRecord::from_placement([10.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0], 1001),
            // Record 2: Child 2
            TransformRecord::from_placement([20.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0], 1002),
        ];

        let mode = bind_instances(&mut instances, &recs, true);
        assert_eq!(mode, BindingMode::RootPlusSequential);

        assert_eq!(instances[0].placement_status, PlacementStatus::Placed);
        assert_eq!(
            instances[0].transform,
            Some([10.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0])
        );
        assert_eq!(instances[0].object_tag, Some(1001));

        assert_eq!(instances[1].placement_status, PlacementStatus::Placed);
        assert_eq!(
            instances[1].transform,
            Some([20.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0])
        );
        assert_eq!(instances[1].object_tag, Some(1002));
    }

    #[test]
    fn binding_identity_default_places_at_origin_when_no_records() {
        let mut instances = vec![
            make_test_instance("PartA.1", "PartA", true),
            make_test_instance("PartB.1", "PartB", true),
        ];

        let recs = Vec::new();
        let mode = bind_instances(&mut instances, &recs, true);
        assert_eq!(mode, BindingMode::IdentityDefault);

        for inst in &instances {
            assert_eq!(inst.placement_status, PlacementStatus::Placed);
            assert_eq!(inst.transform, Some(IDENTITY_TRANSFORM));
        }
    }

    #[test]
    fn binding_unplaced_when_no_position_in_pool() {
        let mut instances = vec![
            make_test_instance("PartA.1", "PartA", false),
            make_test_instance("PartB.1", "PartB", false),
        ];

        let recs = Vec::new();
        let mode = bind_instances(&mut instances, &recs, false);
        assert_eq!(mode, BindingMode::Unplaced);

        for inst in &instances {
            assert_eq!(inst.placement_status, PlacementStatus::Identity);
            assert_eq!(inst.transform, Some(IDENTITY_TRANSFORM));
        }
    }

    #[test]
    fn anti_masking_invariant_undecodable_mesh_never_masked_to_identity() {
        // 2 placed instances, but 5 transform records (constraint mesh mismatch)
        let mut instances = vec![
            make_test_instance("Bolt.1", "Bolt", true),
            make_test_instance("Nut.1", "Nut", true),
        ];

        let recs = vec![
            TransformRecord::from_placement([1.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0], 1),
            TransformRecord::from_placement([2.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0], 2),
            TransformRecord::from_placement([3.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0], 3),
            TransformRecord::from_placement([4.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0], 4),
            TransformRecord::from_placement([5.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0], 5),
        ];

        let mode = bind_instances(&mut instances, &recs, true);
        assert_eq!(mode, BindingMode::Undecodable);

        for inst in &instances {
            assert_eq!(inst.placement_status, PlacementStatus::Undecodable);
            // Strict Anti-Masking: transform MUST be None, NEVER origin identity!
            assert!(
                inst.transform.is_none(),
                "anti-masking violation: undecodable transform masked to Some!"
            );
            assert!(inst.classification_detail.is_some());
        }
    }

    fn make_position(kind: PositionKind, t: [f64; 3]) -> PositionRecord {
        PositionRecord {
            kind,
            transform: TransformRecord::from_placement(t, [1.0, 0.0, 0.0, 0.0], 0),
            offset: 0,
        }
    }

    #[test]
    fn position_layer_keeps_identity_record_as_undecodable_placeholder() {
        // Coso shape: 7 instanced parts, 6 explicit + 1 identity frame.
        let mut instances: Vec<ProductInstanceRecord> = [
            "Part4.1",
            "Part5.1",
            "Part5.1.2",
            "Part7.1",
            "Part7.2",
            "Part5.1.1",
            "Part5.1.1.1",
        ]
        .iter()
        .map(|n| make_test_instance(n, n.split('.').next().unwrap(), true))
        .collect();

        let positions = vec![
            make_position(PositionKind::Explicit, [-10.0, 11.0, 2.0]),
            make_position(PositionKind::Identity, [0.0, 0.0, 0.0]),
            make_position(PositionKind::Explicit, [9.0, 11.0, 6.0]),
            make_position(PositionKind::Explicit, [-9.0, 46.0, 11.0]),
            make_position(PositionKind::Explicit, [-16.0, -18.0, 2.0]),
            make_position(PositionKind::Explicit, [-5.0, -6.0, 6.0]),
            make_position(PositionKind::Explicit, [-1.0, 32.0, 6.0]),
        ];

        let mode = bind_position_layer(&mut instances, &positions).expect("bound");
        assert_eq!(mode, BindingMode::PositionStream8d81);
        assert_eq!(
            instances[0].transform,
            Some([-10.0, 11.0, 2.0, 1.0, 0.0, 0.0, 0.0])
        );
        // The identity frame keeps ordinal position 1 -> Part5.1, but is never bound.
        assert_eq!(instances[1].placement_status, PlacementStatus::Undecodable);
        assert!(instances[1].transform.is_none());
        // The following explicit record still binds Part5.1.2: the order did not shift.
        assert_eq!(
            instances[2].transform,
            Some([9.0, 11.0, 6.0, 1.0, 0.0, 0.0, 0.0])
        );
        assert_eq!(
            instances
                .iter()
                .filter(|i| i.placement_status == PlacementStatus::Placed)
                .count(),
            6
        );
    }

    #[test]
    fn position_layer_root_ref_keeps_root_undecodable() {
        // Servo shape: ac2:1, ac1:1, main:1; 3 explicit + 1 identity record.
        let mut instances = vec![
            make_test_instance("ac2:1", "ac2", true),
            make_test_instance("ac1:1", "ac1", true),
            make_test_instance("main:1", "main", true),
        ];
        let positions = vec![
            make_position(PositionKind::Explicit, [0.0, 0.0, -22.9]),
            make_position(PositionKind::Explicit, [43.2, 51.3, 0.0]),
            make_position(PositionKind::Explicit, [43.2, 51.3, -1.7]),
            make_position(PositionKind::Identity, [0.0, 0.0, 0.0]),
        ];

        let mode = bind_position_layer(&mut instances, &positions).expect("bound");
        assert_eq!(mode, BindingMode::PositionStream8d81);
        assert_eq!(
            instances[0].transform,
            Some([0.0, 0.0, -22.9, 1.0, 0.0, 0.0, 0.0])
        );
        assert_eq!(
            instances[1].transform,
            Some([43.2, 51.3, 0.0, 1.0, 0.0, 0.0, 0.0])
        );
        assert_eq!(instances[2].placement_status, PlacementStatus::Undecodable);
        assert!(instances[2].transform.is_none());
        let detail = instances[2]
            .classification_detail
            .as_deref()
            .expect("detail");
        assert!(detail.contains("positional precedence"));
        assert!(detail.contains("43.200"));
    }

    #[test]
    fn position_layer_count_mismatch_fails_closed() {
        // 3 positioned instances, but only 2 explicit + 0 identity records.
        let mut instances = vec![
            make_test_instance("A.1", "A", true),
            make_test_instance("B.1", "B", true),
            make_test_instance("C.1", "C", true),
        ];
        let positions = vec![
            make_position(PositionKind::Explicit, [1.0, 0.0, 0.0]),
            make_position(PositionKind::Explicit, [2.0, 0.0, 0.0]),
        ];

        assert!(bind_position_layer(&mut instances, &positions).is_none());
        mark_position_layer_undecodable(&mut instances, 2, 0);
        for inst in &instances {
            assert_eq!(inst.placement_status, PlacementStatus::Undecodable);
            assert!(inst.transform.is_none());
            assert!(inst.classification_detail.is_some());
        }
    }

    fn name_table_position_bytes(records: usize) -> Vec<u8> {
        let mut data = Vec::new();
        for _ in 0..records {
            data.extend_from_slice(&crate::product::transforms::POSITION_EXPLICIT_HEADER);
            data.extend_from_slice(&crate::product::transforms::R15_MATRIX_MARKER);
            data.extend_from_slice(&[0xE7, 0xE8, 0xE8, 0xE8]);
            data.extend_from_slice(&[0xE7, 0xE8, 0xE8, 0xE8]);
            data.push(0xE7);
            for v in [12.5f64, 0.0, 14.4] {
                data.push(0xE6);
                data.extend_from_slice(&v.to_le_bytes());
            }
            data.push(0xFE);
        }
        data
    }

    #[test]
    fn name_table_zero_records_binds_identity() {
        let mut instances = vec![
            make_test_instance("Widget", "Widget", false),
            make_test_instance("Bracket", "Bracket", false),
        ];

        let n = bind_name_table(&mut instances, &[]);

        assert_eq!(n, 0);
        for inst in &instances {
            assert_eq!(inst.placement_status, PlacementStatus::Identity);
            assert_eq!(inst.transform, Some(IDENTITY_TRANSFORM));
            assert!(!inst.has_position_attr);
            assert!(inst.object_tag.is_none());
        }
    }

    #[test]
    fn name_table_position_records_never_bind_identity() {
        let mut instances = vec![
            make_test_instance("Widget", "Widget", false),
            make_test_instance("Bracket", "Bracket", false),
        ];
        let data = name_table_position_bytes(2);

        let n = bind_name_table(&mut instances, &data);

        assert_eq!(n, 2);
        for inst in &instances {
            assert_eq!(inst.placement_status, PlacementStatus::Undecodable);
            assert!(inst.transform.is_none());
            assert!(inst.has_position_attr);
            assert!(inst.classification_detail.is_some());
        }
    }

    #[test]
    fn name_table_root_frame_is_not_a_position_record() {
        let mut data = Vec::new();
        data.extend_from_slice(&crate::product::transforms::POSITION_ROOT_HEADER);
        data.extend_from_slice(&crate::product::transforms::R15_MATRIX_MARKER);
        data.extend_from_slice(&[0xE7, 0xE8, 0xE8, 0xE8]);
        data.extend_from_slice(&[0xE7, 0xE8, 0xE8, 0xE8]);
        data.push(0xE7);
        for v in [0.0f64, 0.0, 0.0] {
            data.push(0xE6);
            data.extend_from_slice(&v.to_le_bytes());
        }
        data.push(0xFE);

        let mut instances = vec![make_test_instance("Widget", "Widget", false)];
        let n = bind_name_table(&mut instances, &data);
        assert_eq!(n, 0);
        assert_eq!(instances[0].placement_status, PlacementStatus::Identity);
    }
}
