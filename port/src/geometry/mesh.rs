//! Mesh invariants over the decoded triangle soup (G3 F6/F8 measures)
//! — the port of the Python reference module
//! ``catpart.geometry.mesh`` (``src/catpart/geometry/mesh.py``), per
//! spec §2.1 of ``docs/specs/phase5-viewer-spec.md`` (invariants).
//!
//! Adapted from ``scripts/triage/decode_facet_semantics.py``'s
//! ``soup_stats`` with the semantics unchanged: undirected edge usage,
//! manifold (no edge used more than twice), closure (every edge
//! exactly twice), orientation consistency (each edge used once per
//! direction) and the boundary-edge count — the numbers G3 validated
//! the acceptance-seed soup with (140 triangles, 210 edges, closed
//! manifold, oriented).
//!
//! A non-closed result is legitimate geometry (the sheet-like open
//! shells of F6: 10/76 clean-store soups), reported as the
//! ``open-shell`` warning class, never an error.
//!
//! Evidence: the twin's docstring cites no dedicated evidence note —
//! it is adapted from ``scripts/triage/decode_facet_semantics.py``'s
//! ``soup_stats`` with the semantics unchanged (ticket #32), its
//! numbers are the G3 acceptance-seed soup measures (140 triangles,
//! 210 edges, closed manifold, oriented) and its claim home is the
//! G3 note's F6/F8: ``docs/evidence/2026-11-09-facet-semantics.md``.
//! Those are the citations this port carries.
//!
//! Numeric contract (spec §2.2): decode module — the
//! ``clippy::suboptimal_flops`` allow below is the pinned carve-out
//! (mul_add changes rounding and flips exact-equality decisions); see
//! the crate docs in ``../lib.rs`` for the full policy.
#![allow(clippy::suboptimal_flops)]

use std::collections::HashMap;

/// Invariants of one decoded triangle mesh — the twin's
/// :class:`catpart.geometry.mesh.MeshStats` dataclass (frozen). Field
/// declaration order = the twin's construction order.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MeshStats {
    /// Distinct undirected edges.
    pub edge_count: usize,
    /// Every edge used at most twice.
    pub manifold: bool,
    /// Every edge used exactly twice.
    pub closed: bool,
    /// Each edge used once per direction.
    pub oriented: bool,
    /// Edges used exactly once.
    pub boundary_edges: usize,
}

/// Edge histogram and closure/orientation invariants (G3 soup_stats) —
/// the twin's :func:`catpart.geometry.mesh.mesh_stats`.
pub fn mesh_stats(triangles: &[(u32, u32, u32)]) -> MeshStats {
    let mut edge: HashMap<[u32; 2], u32> = HashMap::new();
    let mut directed: HashMap<(u32, u32), u32> = HashMap::new();
    for tri in triangles {
        for e in [(tri.0, tri.1), (tri.1, tri.2), (tri.2, tri.0)] {
            let key = if e.0 <= e.1 { [e.0, e.1] } else { [e.1, e.0] };
            *edge.entry(key).or_insert(0) += 1;
            *directed.entry(e).or_insert(0) += 1;
        }
    }
    MeshStats {
        edge_count: edge.len(),
        manifold: edge.values().all(|&v| v <= 2),
        closed: edge.values().all(|&v| v == 2),
        oriented: directed
            .iter()
            .all(|(&(a, b), &v)| directed.get(&(b, a)).copied().unwrap_or(0) == v),
        boundary_edges: edge.values().filter(|&&v| v == 1).count(),
    }
}

/// How many of the ``n_vertices`` pool positions any triangle uses —
/// the twin's :func:`catpart.geometry.mesh.used_vertex_count`.
pub fn used_vertex_count(triangles: &[(u32, u32, u32)], n_vertices: usize) -> usize {
    let used: std::collections::HashSet<u32> = triangles
        .iter()
        .flat_map(|tri| [tri.0, tri.1, tri.2])
        .collect();
    (0..n_vertices)
        .filter(|i| used.contains(&(*i as u32)))
        .count()
}

/// The pool coordinate extents as ``(min, max)`` triples — the twin's
/// :func:`catpart.geometry.mesh.bounding_box`. ``None`` mirrors the
/// twin's ``zip(*pool)`` unpacking ``ValueError`` on an empty pool —
/// unreachable on the clean decode path (the no-pool store raises
/// ``undecoded-variant`` before this line), surfaced by the caller as
/// the twin's unclassified crash (never a Fidelity match, §3.2).
pub fn bounding_box(pool: &[(f64, f64, f64)]) -> Option<([f64; 3], [f64; 3])> {
    if pool.is_empty() {
        return None;
    }
    let mut min = pool[0];
    let mut max = pool[0];
    for &(x, y, z) in &pool[1..] {
        if x < min.0 {
            min.0 = x;
        }
        if y < min.1 {
            min.1 = y;
        }
        if z < min.2 {
            min.2 = z;
        }
        if x > max.0 {
            max.0 = x;
        }
        if y > max.1 {
            max.1 = y;
        }
        if z > max.2 {
            max.2 = z;
        }
    }
    Some(([min.0, min.1, min.2], [max.0, max.1, max.2]))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_acceptance_seed_soup_is_a_closed_oriented_manifold() {
        // The G3 acceptance-seed measures (140 triangles, 210 edges,
        // closed manifold, oriented) reduce here to the closed
        // tetrahedron: 4 triangles, 6 edges, each used twice, every
        // edge once per direction, no boundary.
        let tetrahedron = vec![(0, 1, 2), (0, 3, 1), (1, 3, 2), (2, 3, 0)];
        let stats = mesh_stats(&tetrahedron);
        assert_eq!(stats.edge_count, 6);
        assert!(stats.manifold);
        assert!(stats.closed);
        assert!(stats.oriented);
        assert_eq!(stats.boundary_edges, 0);
    }

    #[test]
    fn open_shell_and_orientation_laws() {
        // One triangle: 3 boundary edges, not closed, manifold, and
        // NOT oriented (the twin's law: every directed edge needs its
        // reverse — boundary edges have none, Counter-missing = 0).
        let stats = mesh_stats(&[(0, 1, 2)]);
        assert_eq!(stats.edge_count, 3);
        assert!(stats.manifold);
        assert!(!stats.closed);
        assert!(!stats.oriented);
        assert_eq!(stats.boundary_edges, 3);
        // An edge used 3x: not manifold (the F8 measure).
        let overused = vec![(0, 1, 2), (1, 2, 3), (2, 1, 3)];
        let stats = mesh_stats(&overused);
        assert!(!stats.manifold);
        // The twin's oriented law: every directed edge needs its
        // reverse. Two identical triangles (an edge used twice in the
        // same direction) are NOT oriented; the two-sided sheet (both
        // windings once) IS — both are the twin's own semantics.
        let stats = mesh_stats(&vec![(0, 1, 2), (0, 1, 2)]);
        assert!(!stats.oriented);
        let stats = mesh_stats(&vec![(0, 1, 2), (0, 2, 1)]);
        assert!(stats.oriented);
    }

    #[test]
    fn empty_soup_is_vacuously_closed() {
        // Python's all() over an empty Counter: True on both laws.
        let stats = mesh_stats(&[]);
        assert!(stats.manifold);
        assert!(stats.closed);
        assert!(stats.oriented);
        assert_eq!(stats.edge_count, 0);
        assert_eq!(stats.boundary_edges, 0);
    }

    #[test]
    fn used_vertex_count_counts_referenced_positions() {
        // Positions 0..8; the triangles reference 0, 1, 2, 4: 4 used.
        assert_eq!(used_vertex_count(&[(0, 1, 2), (2, 1, 4)], 9), 4);
        assert_eq!(used_vertex_count(&[], 5), 0);
    }

    #[test]
    fn bounding_box_extremes_and_the_empty_pool_arm() {
        let pool = vec![(0.0, 10.0, -5.0), (20.0, 0.0, 60.0), (5.0, 100.0, 30.0)];
        let (min, max) = bounding_box(&pool).unwrap();
        assert_eq!(min, [0.0, 0.0, -5.0]);
        assert_eq!(max, [20.0, 100.0, 60.0]);
        // The twin's zip(*[]) ValueError arm.
        assert!(bounding_box(&[]).is_none());
    }
}
