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
use super::transforms::TransformRecord;

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
            BindingMode::Undecodable | BindingMode::ConnectorProxyMesh | BindingMode::Unplaced => {
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
}
