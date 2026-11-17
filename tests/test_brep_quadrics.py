"""Unit tests for the BR4 quadric-surface recognizers (ticket #56).

Synthetic fixtures only (corpus binaries stay out of the test suite);
every discriminating edge of the recognition laws carries a negative
fixture — the detector-honesty fixtures of the evidence note
(docs/evidence/2026-11-17-br4-quadrics.md).
"""

from __future__ import annotations

import math
import struct

from catpart.brep import quadrics

# ---------------------------------------------------------------- helpers


def f32(v: float) -> float:
    """Round through f32 (the corpus coordinate storage)."""
    return struct.unpack("<f", struct.pack("<f", v))[0]


def ring(cx, cy, cz, r, n, r2=None):
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x, y = r * math.cos(t), r * math.sin(t)
        if r2 is not None:
            y = r2 * math.sin(t)
        pts.append((cx + x, cy + y, cz))
    return pts


def zig(ring_a, ring_b):
    """Strip refs alternating between two rings (the B4 worked-example shape)."""
    out = []
    for i in range(len(ring_a)):
        out.append(ring_a[i])
        out.append(ring_b[i])
    return out


def classify(seq_points, pool):
    refs = [pool.index(p) for p in seq_points]
    return quadrics.classify_strip_patch(refs, pool)


# ---------------------------------------------------------------- positives


def test_cylinder_positive_exact_radius():
    r0, r1, r2 = ring(0, 0, 0, 8, 24), ring(0, 0, 10, 8, 24), ring(0, 0, 20, 8, 24)
    pool = r0 + r1 + r2
    fit = classify(zig(r0, r1) + zig(r1, r2), pool)
    assert fit.label == "cylinder"
    assert abs(fit.radius - 8.0) <= 1e-3
    assert fit.kmax <= quadrics.K_CYL
    assert fit.residual <= fit.tol


def test_cylinder_positive_f32_coordinates():
    # The corpus stores f32 coordinates; the laws must hold there.
    r0, r1, r2 = ring(0, 0, 0, 8, 24), ring(0, 0, 10, 8, 24), ring(0, 0, 20, 8, 24)
    pool = [(f32(x), f32(y), f32(z)) for x, y, z in r0 + r1 + r2]
    seq = [(f32(x), f32(y), f32(z)) for x, y, z in zig(r0, r1) + zig(r1, r2)]
    fit = classify(seq, pool)
    assert fit.label == "cylinder"
    assert abs(fit.radius - 8.0) <= 1e-3


def test_cone_positive_exact_slope():
    a0, a1, a2 = ring(0, 0, 0, 10, 24), ring(0, 0, 10, 7.5, 24), ring(0, 0, 20, 5, 24)
    pool = a0 + a1 + a2
    fit = classify(zig(a0, a1) + zig(a1, a2), pool)
    assert fit.label == "cone"
    assert abs(fit.slope + 0.25) <= 1e-3  # 10 -> 5 over h 0..20
    assert fit.residual <= fit.tol
    assert fit.quad <= fit.tol  # the quadratic gate accepts a true cone


def test_sphere_positive_exact_radius():
    lats = [(12 * math.cos(t), 12 * math.sin(t)) for t in (0.2, 0.6, 1.0)]
    bands = [ring(0, 0, z, rl, 24) for rl, z in lats]
    pool = sum(bands, [])
    fit = classify(zig(bands[0], bands[1]) + zig(bands[1], bands[2]), pool)
    assert fit.label == "sphere"
    assert abs(fit.radius - 12.0) <= 1e-3
    assert fit.residual <= fit.tol


# ---------------------------------------------------------------- negatives


def test_plane_strip_negative_planar():
    # Detector honesty: a planar strip is not a curved patch (spread gate).
    pl0 = [(0, 0, 0), (4, 0, 0), (8, 0, 0), (12, 0, 0), (16, 0, 0)]
    pl1 = [(0, 3, 0), (4, 3, 0), (8, 3, 0), (12, 3, 0), (16, 3, 0)]
    pool = pl0 + pl1
    fit = classify(zig(pl0, pl1), pool)
    assert fit.label == "planar"
    assert fit.spread < quadrics.SPREAD_MIN


def test_extruded_ellipse_negative_pencil_noncyl():
    # The SRF-02/SRF-07 edge: an extruded (tab-cyl) non-circular profile
    # passes the pencil but fails the cylinder radius law.
    e0 = ring(0, 0, 0, 10, 24, r2=5)
    e1 = ring(0, 0, 10, 10, 24, r2=5)
    e2 = ring(0, 0, 20, 10, 24, r2=5)
    pool = e0 + e1 + e2
    fit = classify(zig(e0, e1) + zig(e1, e2), pool)
    assert fit.label == "pencil-noncyl"
    assert fit.kmax <= quadrics.K_CYL
    assert fit.residual > fit.tol


def test_torus_fillet_negative_not_cone_not_sphere():
    # The SRF-03/SRF-05 edge: a torus-fillet band's tube profile is
    # quadratic in h (quad gate) and its best-fit sphere misses the
    # tight Kasa tolerance -> curved-unclassified, never cone/sphere.
    phis = [math.pi - t for t in (0.9, 0.6, 0.3)]
    thetas = [2 * math.pi * i / 16 for i in range(16)]
    bands = []
    for phi in phis:
        band = []
        for th in thetas:
            rho = 30 + 4 * math.cos(phi)
            band.append((rho * math.cos(th), rho * math.sin(th), 4 * math.sin(phi)))
        bands.append(band)
    pool = sum(bands, [])
    fit = classify(zig(bands[0], bands[1]) + zig(bands[1], bands[2]), pool)
    assert fit.label == "curved-unclassified"


def test_cone_negative_jittered_radii():
    # The affine radial law rejects non-affine rho(h) (a "cone" whose
    # radius does not vary linearly with height).
    c0 = ring(0, 0, 0, 10, 24)
    c1 = ring(0, 0, 10, 7.0, 24)  # affine would predict 7.5
    c2 = ring(0, 0, 20, 5, 24)
    pool = c0 + c1 + c2
    fit = classify(zig(c0, c1) + zig(c1, c2), pool)
    assert fit.label != "cone"


def test_sphere_negative_ellipsoid():
    # The Kasa distance law rejects an ellipsoid shell.
    def ell_ring(z, rx, ry, n):
        pts = []
        for i in range(n):
            t = 2 * math.pi * i / n
            pts.append((rx * math.cos(t), ry * math.sin(t), z))
        return pts

    s0 = ell_ring(0, 12, 12, 24)
    s1 = ell_ring(4, 11, 5.5, 24)
    pool = s0 + s1
    fit = classify(zig(s0, s1), pool)
    assert fit.label != "sphere"


def test_degenerate_collinear_patch():
    # A collinear strip carries no usable normals -> degenerate, not a
    # surface reading.
    pts = [(i * 1.0, 0.0, 0.0) for i in range(6)]
    fit = quadrics.classify_strip_patch(list(range(6)), pts)
    assert fit.label == "degenerate"


# ---------------------------------------------------------------- unit laws


def test_strip_triangles_winding_flip():
    # G3 F3: the odd strip triangle flips so the winding stays consistent.
    refs = [0, 1, 2, 3]
    tris = quadrics.strip_triangles(refs)
    assert tris[0] == (0, 1, 2)
    assert tris[1] == (3, 2, 1)  # flipped odd triangle


def test_fit_cylinder_recovers_axis_point():
    r0, r1 = ring(0, 0, 0, 8, 24), ring(0, 0, 10, 8, 24)
    pool = r0 + r1
    refs = [pool.index(p) for p in zig(r0, r1)]
    pts = []
    for tri in quadrics.strip_triangles(refs):
        pts.extend(pool[i] for i in tri)
    u, r, res, scale = quadrics.fit_cylinder(pts, (0.0, 0.0, 1.0))
    assert abs(r - 8.0) <= 1e-3
    assert res <= 1e-6
    assert abs(u[0]) <= 1e-6 and abs(u[1]) <= 1e-6


def test_fit_sphere_exact_on_surface_points():
    pts = ring(0, 0, 0, 5, 32) + ring(0, 0, 3, 4, 32)
    c, r, res, scale = quadrics.fit_sphere(pts)
    # Both rings lie on the sphere through them centered on the axis.
    assert res <= 1e-4
    assert r > 4.0


def test_selftest_has_no_failures():
    assert quadrics.selftest() == []
