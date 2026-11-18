"""Tessellation-level quadric surface recognition (BR4, ticket #56, Spec G #47).

Recognizes cylindrical, conical and spherical strip loops in the
facet-record tessellation of the nested ``CATStdCont`` store body, on
the two scopes where the references resolve to coordinates:

- **pool-only stores** (G3/F2 semantics): the facet references are
  lexicographic ranks of the vertex pool (``catpart.geometry.facets``).
- **composite identity-decoded stores** (stage-3d identity law, shipped
  ``catpart.geometry.composite``): the references are element indices
  of the decoded list-node region (``decode_region`` +
  ``parse_strip_records``); this scope is candidate on stores that
  identity reading covers and is reported separately.

The recognition unit is one ``ty`` strip loop of an accepted strip
record — NOT a record: one accepted record is one face patch per G3,
and its ``ty`` loops are that patch's strip segments (G3 phase reset),
so a record with ``ty`` > 1 contributes that many recognized units.
The laws, in test order (all residuals relative to the patch bbox
diagonal ``scale``):

1. **planar** — the patch's triangle normals are parallel (max chord
   ``||n - mean||`` below :data:`SPREAD_MIN`): no curved reading.
2. **pencil branch: cylinder (SRF-02) or pencil-noncyl (SRF-07)** —
   the normals share a null direction ``a`` (``|n.a| <= K_CYL`` for
   every triangle normal, ``a`` = smallest eigenvector of
   ``sum n n^T``), and this branch RETURNS: a least-squares cylinder
   with axis ``a`` fitting with max residual ``<= TOL_PATCH`` is a
   cylinder, anything else under the pencil is ``pencil-noncyl`` (the
   negative-space signature of a non-cylindrical extrusion).  The cone
   and sphere laws are never reached from a pencil patch.  The radius
   law separates a cylinder from a planar-extruded patch (the pencil
   alone does not: plane strips are removed by the spread test, but any
   ruled surface along ``a`` passes it).
3. **cone (SRF-03)** — the normals make a CONSTANT angle with a common
   axis ``a`` (``|mean(n).a|`` in ``(K_CYL, K_PLANE)``; ``a`` =
   smallest eigenvector of the normal deviations' scatter) AND the
   radial distances are affine in the axial heights: the affine fit's
   max residual ``<= TOL_PATCH`` and the fitted quadratic term
   explains ``<= TOL_PATCH`` over the height span (the quadratic gate
   — a torus-fillet band's tube profile is quadratic in ``h`` and is
   rejected by it).  The cone law is tested BEFORE the sphere law:
   over a short axial/meridional span the two laws are mutually
   satisfiable — a true sphere band over a short meridional span
   (R 12.0 at lats 1.30/1.25/1.20 rad → cone: residual 8.7e-3 <= tol
   6.5e-2, quadratic term 6.3e-2 <= tol) satisfies the cone gates, and
   a short cone band satisfies the Kasa sphere fit (both
   fixture-pinned) — so precedence assigns such bands to SRF-03, and
   the sphere count is a floor.
4. **sphere (SRF-04)** — a Kasa algebraic sphere fit (points only; the
   tessellation vertices lie ON the surface, so the fit is exact-form)
   with max residual ``<= TOL_SPHERE`` and ``R <= R_SCALE_MAX x scale``.
5. **curved-unclassified** — curved patch, no law: the shared
   unclassified population of SRF-05 torus, SRF-06 non-quadric
   revolution, SRF-07 extrusion (when the pencil fails, e.g. revolved
   profiles) and SRF-08 NURBS tessellation patches.  It is NOT a torus
   population: a torus band also satisfies richer laws (see the SRF-05
   honesty line), so SRF-05 has no class-shaped bound.

Detector honesty (one line per class, echoed in the evidence note):

- The patch classifier does NOT discriminate construction history:
  a tessellated cylinder cannot be told from a tabulated cylinder
  (SRF-07) or from the cylindrical special case of a revolution
  (SRF-06) — the surface geometry is identical; only CGM-side
  construction records (BR5's slice) could.
- The pencil test does NOT discriminate the extrusion direction
  convention and does not establish which face binds the patch.
- The cone law does NOT discriminate the apex side (slope sign is
  reported, not interpreted), a torus-fillet band over a short height
  span (its quadratic term can sit under the gate — the named
  residual-margin limitation), or a sphere band over a short
  meridional span, which lands in SRF-03 by precedence (so cone counts
  absorb sphere-shaped short spans; fixture-pinned).
- The sphere law does NOT discriminate a spherical cap's side and
  cannot separate a small torus region from a sphere at local-patch
  scale (any smooth patch is locally spherical; the tight
  :data:`TOL_SPHERE` and the ``R <= 10 x scale`` sanity are the only
  guards).  A short torus band satisfies it (fixture-pinned), so
  sphere counts are floors too.
- **No law isolates a torus (SRF-05), so no class is a torus
  population.**  A torus band is consistent with two or more laws,
  one fixture per measured escape: **cylinder** at either equator (a
  0.05 rad band fits R 33.998 outer / 26.002 inner within
  :data:`TOL_PATCH` — the tube is locally a cylinder there),
  **planar** near the pole (a 0.05 rad band straddling the pole
  spreads 0.0255, well under :data:`SPREAD_MIN`; the planar gate
  returns first, so the `pencil-noncyl` reading this band would also
  earn — its radius law fails — is never measured, and that class
  stays inside the bound anyway), **cone** and **sphere** over short
  spans, **curved-unclassified** at a wide span.  SRF-05's measured
  upper bound is therefore the FULL classified loop total, not a
  union of classes — every recognized loop, of any class, could be a
  torus band, so nothing may be subtracted.  That bound covers the
  classified population only; the loops the recognizer never saw are
  unclassified loops above it.
- Per-loop granularity: a writer splitting one cylinder across
  several ``ty`` loops with per-loop arcs under :data:`SPREAD_MIN`
  lands them planar — the recognized counts are FLOORS, never
  ceilings.

Provenance: laws calibrated on synthetic tessellations and measured
corpus-wide by ``scripts/triage/decode_brep_quadrics.py``; rates and
scope caveats in ``docs/evidence/2026-11-17-br4-quadrics.md`` (BR4).
"""

from __future__ import annotations

import dataclasses
import math

TOL_PATCH = 2e-3  # cylinder/cone residual tol, relative to bbox diagonal
TOL_SPHERE = 5e-4  # Kasa sphere tol: vertices lie exactly on the sphere
K_CYL = 0.05  # max |n.a| for the pencil law (normals perpendicular to a)
K_PLANE = 0.995  # |mean(n).a| above which the normals are ~parallel to a
SPREAD_MIN = 0.10  # min max-chord ||n - mean|| for a curved patch
R_SCALE_MAX = 10.0  # sphere radius sanity cap, x scale
MIN_TRIANGLES = 2  # below this a patch carries no usable normal spread


@dataclasses.dataclass(frozen=True)
class PatchFit:
    """One strip patch's recognition result."""

    label: str  # planar/degenerate/cylinder/sphere/cone/pencil-noncyl/curved-unclassified
    spread: float  # max chord ||n - mean|| over the patch's triangle normals
    kmax: float  # max |n.a| under the pencil axis (0 = perfect pencil)
    axis: tuple[float, float, float] | None  # pencil/cone axis (unit) or None
    radius: float | None  # cylinder radius / Kasa R (sphere) / rho0 (cone)
    residual: float  # max law residual of the accepted fit attempt
    tol: float  # the residual tolerance of that attempt
    slope: float | None  # cone drho/dh (cone only)
    quad: float | None  # fitted quadratic term over the h span (cone gate)
    center: tuple[float, float, float] | None  # sphere center (sphere only)


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _norm(a):
    return math.sqrt(_dot(a, a))


def _unit(a):
    n = _norm(a)
    return (a[0] / n, a[1] / n, a[2] / n) if n > 0 else (0.0, 0.0, 0.0)


def _smallest_evec(m):
    """Smallest-eigenvalue eigenvector of a symmetric 3x3 (Jacobi)."""
    a = [list(row) for row in m]
    v = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    for _ in range(64):
        if abs(a[0][1]) + abs(a[0][2]) + abs(a[1][2]) < 1e-14:
            break
        for p, q in ((0, 1), (0, 2), (1, 2)):
            if abs(a[p][q]) < 1e-18:
                continue
            theta = (a[q][q] - a[p][p]) / (2 * a[p][q])
            t = (1 if theta >= 0 else -1) / (abs(theta) + math.sqrt(theta * theta + 1))
            c = 1 / math.sqrt(t * t + 1)
            s = t * c
            for k in range(3):
                akp, akq = a[k][p], a[k][q]
                a[k][p] = c * akp - s * akq
                a[k][q] = s * akp + c * akq
            for k in range(3):
                apk, aqk = a[p][k], a[q][k]
                a[p][k] = c * apk - s * aqk
                a[q][k] = s * apk + c * aqk
            for k in range(3):
                vkp, vkq = v[k][p], v[k][q]
                v[k][p] = c * vkp - s * vkq
                v[k][q] = s * vkp + c * vkq
    evals = [a[0][0], a[1][1], a[2][2]]
    i = min(range(3), key=lambda j: evals[j])
    return _unit((v[0][i], v[1][i], v[2][i]))


def _ls_solve(rows, rhs):
    """Least squares via normal equations + Gauss-Jordan (small systems)."""
    ncol = len(rows[0])
    ata = [[sum(r[i] * r[j] for r in rows) for j in range(ncol)] for i in range(ncol)]
    atb = [sum(r[i] * b for r, b in zip(rows, rhs)) for i in range(ncol)]
    m = [ata[i][:] + [atb[i]] for i in range(ncol)]
    for col in range(ncol):
        piv = max(range(col, ncol), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-12:
            return None
        m[col], m[piv] = m[piv], m[col]
        pv = m[col][col]
        m[col] = [x / pv for x in m[col]]
        for r in range(ncol):
            if r != col and abs(m[r][col]) > 0:
                f = m[r][col]
                m[r] = [x - f * y for x, y in zip(m[r], m[col])]
    return [m[i][ncol] for i in range(ncol)]


def _bbox_scale(pts):
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    return _norm(_sub(hi, lo)) or 1.0


def fit_cylinder(pts, axis):
    """LS cylinder with a known axis direction.

    The axis point is parametrized in the plane perpendicular to
    ``axis`` (its axial component is unconstrained by the residuals, so
    the full 4-unknown system would be singular).  Returns
    ``(axis_point, radius, max_residual, scale)`` or ``None``.
    """
    a = axis
    proj = lambda p: (  # noqa: E731 - local helper, matches sibling scripts
        p[0] - _dot(p, a) * a[0],
        p[1] - _dot(p, a) * a[1],
        p[2] - _dot(p, a) * a[2],
    )
    e1 = _unit(_cross(a, (1.0, 0.0, 0.0))) or _unit(_cross(a, (0.0, 1.0, 0.0)))
    e2 = _cross(a, e1)
    rows, rhs = [], []
    for p in pts:
        ap = proj(p)
        rows.append([2 * _dot(ap, e1), 2 * _dot(ap, e2), -1.0])
        rhs.append(_dot(p, ap))
    sol = _ls_solve(rows, rhs)
    if sol is None:
        return None
    u = (
        sol[0] * e1[0] + sol[1] * e2[0],
        sol[0] * e1[1] + sol[1] * e2[1],
        sol[0] * e1[2] + sol[1] * e2[2],
    )
    r2 = _dot(u, proj(u)) - sol[2]
    if r2 <= 0:
        return None
    r = math.sqrt(r2)
    res = 0.0
    for p in pts:
        d = _sub(p, u)
        dh = _dot(d, a)
        rho = _norm(_sub(d, (dh * a[0], dh * a[1], dh * a[2])))
        res = max(res, abs(rho - r))
    return u, r, res, _bbox_scale(pts)


def fit_cone(pts, axis):
    """Affine radial law ``rho(h)`` with the axis point from the cylinder fit.

    Returns ``(rho0, slope, max_residual, scale, quad_term)`` or
    ``None``; ``quad_term`` is the fitted ``h^2`` coefficient's
    explanation over the height span (the torus gate).
    """
    cyl = fit_cylinder(pts, axis)
    if cyl is None:
        return None
    u = cyl[0]
    a = axis
    hs, rhos = [], []
    for p in pts:
        d = _sub(p, u)
        dh = _dot(d, a)
        hs.append(dh)
        dperp = _sub(d, (dh * a[0], dh * a[1], dh * a[2]))
        rhos.append(_norm(dperp))
    hlo, hhi = min(hs), max(hs)
    hspan = hhi - hlo
    sol = _ls_solve([[h, 1.0] for h in hs], rhos)
    if sol is None:
        return None
    slope, rho0 = sol
    res = max(abs(rho0 + slope * h - rho) for h, rho in zip(hs, rhos))
    quad = None
    sol_q = _ls_solve([[h * h, h, 1.0] for h in hs], rhos)
    if sol_q is not None and hspan > 1e-9:
        quad = abs(sol_q[0]) * hspan * hspan
    return rho0, slope, res, _bbox_scale(pts), quad


def fit_sphere(pts):
    """Kasa algebraic sphere fit (points only).

    Returns ``(center, radius, max_residual, scale)`` or ``None``.
    """
    rows, rhs = [], []
    for p in pts:
        rows.append([2 * p[0], 2 * p[1], 2 * p[2], 1.0])
        rhs.append(_dot(p, p))
    sol = _ls_solve(rows, rhs)
    if sol is None:
        return None
    c = (sol[0], sol[1], sol[2])
    r2 = sol[3] + _dot(c, c)
    if r2 <= 0:
        return None
    r = math.sqrt(r2)
    res = max(abs(_norm(_sub(p, c)) - r) for p in pts)
    return c, r, res, _bbox_scale(pts)


def strip_triangles(refs):
    """Strip-segment triangles ``(r_t, r_{t+1}, r_{t+2})``, flip on odd t.

    ``refs`` are already-resolved positions into the caller's point
    list (pool positions under the lex-rank law, element indices under
    the identity law).
    """
    tris = []
    for t in range(len(refs) - 2):
        tri = (refs[t], refs[t + 1], refs[t + 2])
        if t % 2 == 1:
            tri = (tri[2], tri[1], tri[0])
        tris.append(tri)
    return tris


def classify_strip_patch(refs, points):
    """Recognize one ``ty`` strip loop from its resolved references.

    ``refs`` are positions into ``points`` (the caller resolves them
    through the scope's index law); one call = one strip loop, so a
    record with several ``ty`` loops is classified loop by loop.
    Returns a :class:`PatchFit`.
    """
    tris = []
    for tri in strip_triangles(refs):
        a, b, c = points[tri[0]], points[tri[1]], points[tri[2]]
        n = _cross(_sub(b, a), _sub(c, a))
        ln = _norm(n)
        if ln <= 0:
            continue
        tris.append((a, b, c, (n[0] / ln, n[1] / ln, n[2] / ln)))
    if len(tris) < MIN_TRIANGLES:
        return PatchFit("degenerate", 0.0, 0.0, None, None, 0.0, 0.0, None, None, None)
    normals = [t[3] for t in tris]
    mean = (
        sum(n[0] for n in normals) / len(normals),
        sum(n[1] for n in normals) / len(normals),
        sum(n[2] for n in normals) / len(normals),
    )
    spread = max(_norm(_sub(n, mean)) for n in normals)
    if spread < SPREAD_MIN:
        return PatchFit("planar", spread, 0.0, None, None, 0.0, 0.0, None, None, None)
    pts = [p for t in tris for p in t[:3]]

    # Pencil (cylinder / extrusion): normals share a null direction.
    gram = [[sum(n[i] * n[j] for n in normals) for j in range(3)] for i in range(3)]
    axis = _smallest_evec(gram)
    kmax = max(abs(_dot(n, axis)) for n in normals)
    if kmax <= K_CYL:
        fitc = fit_cylinder(pts, axis)
        tol = TOL_PATCH * (fitc[3] if fitc else 1.0)
        if fitc and fitc[1] > 1e-6 and fitc[2] <= tol:
            _, r, res, scale = fitc
            return PatchFit(
                "cylinder", spread, kmax, axis, r, res, TOL_PATCH * scale,
                None, None, None,
            )
        return PatchFit(
            "pencil-noncyl", spread, kmax, axis,
            fitc[1] if fitc else None, fitc[2] if fitc else 0.0, tol,
            None, None, None,
        )
    # Cone BEFORE the sphere: over a short span the two laws are mutually
    # satisfiable (a sphere band satisfies these gates; a short cone band
    # satisfies the Kasa fit), so precedence — not constraint — decides
    # and short sphere-shaped spans are labeled cone.
    mean_n = mean
    scatter = [
        [
            sum((n[i] - mean_n[i]) * (n[j] - mean_n[j]) for n in normals)
            for j in range(3)
        ]
        for i in range(3)
    ]
    caxis = _smallest_evec(scatter)
    kmean = _dot(mean_n, caxis)
    if K_CYL < abs(kmean) < K_PLANE:
        fc = fit_cone(pts, caxis)
        if fc:
            rho0, slope, res, scale, quad = fc
            tol = TOL_PATCH * scale
            if (
                res <= tol
                and quad is not None
                and quad <= tol
                and abs(slope) > 1e-9
            ):
                return PatchFit(
                    "cone", spread, kmax, caxis, rho0, res, tol,
                    slope, quad, None,
                )
    # Sphere (Kasa, points only).
    fs = fit_sphere(pts)
    stol = TOL_SPHERE * (fs[3] if fs else 1.0)
    if fs and fs[1] > 1e-6 and fs[2] <= stol and fs[1] <= R_SCALE_MAX * fs[3]:
        c, r, res, scale = fs
        return PatchFit(
            "sphere", spread, kmax, None, r, res, TOL_SPHERE * scale,
            None, None, c,
        )
    return PatchFit(
        "curved-unclassified", spread, kmax, None, None, 0.0, 0.0,
        None, None, None,
    )


def _selftest_cases():
    """The synthetic fixture set as ``(name, callable)`` pairs.

    Each callable returns ``None`` (case passed) or a failure string.
    The list is the single source of the case count: :func:`selftest`
    runs it, :func:`selftest_count` sizes the ``BR4_selftest`` claims
    row, and ``tests/test_brep_quadrics.py`` pins the same edges.

    Positives: cylinder / cone / sphere tessellations decode under
    their laws with the exact construction parameters.  Negatives: the
    discriminating edges (cone rejects the cylinder pencil;
    torus-fillet band rejected by the quadratic gate and the sphere
    tolerance; extruded ellipse stays pencil-noncyl; plane stays
    planar; cone rejects when the radial law is broken).  Span edges:
    a sphere band with a ~0.1 rad meridional span lands in ``cone`` and
    a short cone band satisfies the Kasa sphere fit (why cone precedence
    exists).  Torus escapes (the SRF-05 upper-bound fixtures): one
    fixture per class a torus band was measured to land in — cylinder
    at either equator, planar at the pole, cone / sphere over short
    spans, curved-unclassified at a wide span.
    """
    import struct

    def check(name, got, want):
        return None if got == want else f"{name}: label {got!r} != {want!r}"

    def ring(cx, cy, cz, r, n, r2=None):
        pts = []
        for i in range(n):
            t = 2 * math.pi * i / n
            x, y = r * math.cos(t), r * math.sin(t)
            if r2 is not None:
                y = r2 * math.sin(t)
            pts.append((cx + x, cy + y, cz))
        return pts

    def zig(a_ring, b_ring):
        out = []
        for i in range(len(a_ring)):
            out.append(a_ring[i])
            out.append(b_ring[i])
        return out

    def classify_bands(bands):
        pool = sum(bands, [])
        refs = [
            pool.index(p)
            for p in zig(bands[0], bands[1]) + zig(bands[1], bands[2])
        ]
        return pool, refs, classify_strip_patch(refs, pool)

    def sphere_bands(lats, r=12.0, n=24):
        return [ring(0, 0, r * math.cos(t), r * math.sin(t), n) for t in lats]

    def torus_bands(phis, n=16):
        thetas = [2 * math.pi * i / n for i in range(n)]
        bands = []
        for phi in phis:
            rho = 30 + 4 * math.cos(phi)
            bands.append(
                [
                    (rho * math.cos(th), rho * math.sin(th), 4 * math.sin(phi))
                    for th in thetas
                ]
            )
        return bands

    def case_cylinder():
        r0, r1, r2 = ring(0, 0, 0, 8, 24), ring(0, 0, 10, 8, 24), ring(0, 0, 20, 8, 24)
        pool = r0 + r1 + r2
        refs = [pool.index(p) for p in zig(r0, r1) + zig(r1, r2)]
        f = classify_strip_patch(refs, pool)
        if f.label != "cylinder":
            return f"label {f.label!r} != 'cylinder'"
        if abs(f.radius - 8.0) > 1e-3:
            return f"radius {f.radius} != 8.0"
        return None

    def case_cylinder_f32():
        def f32(v):
            return struct.unpack("<f", struct.pack("<f", v))[0]

        r0, r1, r2 = ring(0, 0, 0, 8, 24), ring(0, 0, 10, 8, 24), ring(0, 0, 20, 8, 24)
        pool = [(f32(x), f32(y), f32(z)) for x, y, z in r0 + r1 + r2]
        refs = [
            pool.index((f32(p[0]), f32(p[1]), f32(p[2])))
            for p in zig(r0, r1) + zig(r1, r2)
        ]
        return check("cylinder f32", classify_strip_patch(refs, pool).label, "cylinder")

    def case_cone():
        a0, a1, a2 = ring(0, 0, 0, 10, 24), ring(0, 0, 10, 7.5, 24), ring(0, 0, 20, 5, 24)
        pool = a0 + a1 + a2
        refs = [pool.index(p) for p in zig(a0, a1) + zig(a1, a2)]
        f = classify_strip_patch(refs, pool)
        if f.label != "cone":
            return f"label {f.label!r} != 'cone'"
        if abs(f.slope + 0.25) > 1e-3:
            return f"slope {f.slope} != -0.25"
        return None

    def case_sphere_cap():
        bands = sphere_bands((0.2, 0.6, 1.0))
        pool, refs, f = classify_bands(bands)
        if f.label != "sphere":
            return f"label {f.label!r} != 'sphere'"
        if abs(f.radius - 12.0) > 1e-3:
            return f"radius {f.radius} != 12.0"
        return None

    def case_sphere_short_span_cone():
        # B8 edge: a TRUE sphere band (R 12.0, lats 1.30/1.25/1.20 rad)
        # satisfies the cone gates and is labeled cone by precedence.
        bands = sphere_bands((1.3, 1.25, 1.2))
        _pool, _refs, f = classify_bands(bands)
        if f.label != "cone":
            return f"label {f.label!r} != 'cone' (precedence edge unpinned)"
        if f.quad is None or f.quad > f.tol:
            return f"quad {f.quad} > tol {f.tol}"
        return None

    def case_cone_short_span_spherelike():
        # Why the cone law is tested first: a short cone band also
        # satisfies the Kasa sphere fit (the laws are mutually
        # satisfiable over short spans).
        bands = [ring(0, 0, 0, 10, 24), ring(0, 0, 0.5, 9.75, 24), ring(0, 0, 1, 9.5, 24)]
        pool, refs, _f = classify_bands(bands)
        pts = [pool[i] for tri in strip_triangles(refs) for i in tri]
        fs = fit_sphere(pts)
        if fs is None:
            return "Kasa sphere fit declined"
        _c, _r, res, scale = fs
        if res > TOL_SPHERE * scale:
            return f"sphere residual {res} > tol {TOL_SPHERE * scale}"
        return None

    def case_torus_fillet():
        bands = torus_bands([math.pi - t for t in (0.9, 0.6, 0.3)])
        _pool, _refs, f = classify_bands(bands)
        return check("torus fillet (not cone/sphere)", f.label, "curved-unclassified")

    def case_torus_equator_cylinder():
        # SRF-05 upper-bound escape: the tube is locally cylindrical at
        # either equator, so a 0.05 rad band lands in cylinder with the
        # ring radius (34 = R + r outer, 26 = R - r inner).
        for name, phis, want_r in (
            ("outer", (0.05, 0.025, 0.0), 34.0),
            ("inner", (math.pi, math.pi - 0.025, math.pi - 0.05), 26.0),
        ):
            _pool, _refs, f = classify_bands(torus_bands(phis))
            if f.label != "cylinder":
                return f"{name} equator: label {f.label!r} != 'cylinder'"
            if abs(f.radius - want_r) > 1e-2:
                return f"{name} equator: radius {f.radius} != {want_r}"
            if f.residual > f.tol:
                return f"{name} equator: residual {f.residual} > tol {f.tol}"
        return None

    def case_torus_pole_planar():
        # SRF-05 upper-bound escape: a band straddling the pole is
        # nearly flat, so its normals are parallel and it reads planar
        # — no curved reading at all.  The planar gate returns before
        # the pencil branch, so the pencil-noncyl reading this band
        # would also earn (kmax 0.0255 <= K_CYL, radius law fails) is
        # never measured; that class stays inside the bound regardless.
        bands = torus_bands((math.pi / 2 + 0.05, math.pi / 2, math.pi / 2 - 0.05))
        _pool, _refs, f = classify_bands(bands)
        if f.label != "planar":
            return f"label {f.label!r} != 'planar'"
        if f.spread >= SPREAD_MIN:
            return f"spread {f.spread} >= {SPREAD_MIN}"
        return None

    def case_torus_short_span_cone():
        # SRF-05 upper-bound escape: a short torus band lands in cone.
        bands = torus_bands([math.pi - 0.2 * i / 2 for i in (0, 1, 2)])
        _pool, _refs, f = classify_bands(bands)
        return check("torus short span (cone)", f.label, "cone")

    def case_torus_short_span_sphere():
        # SRF-05 upper-bound escape: a slightly longer short band lands
        # in sphere.
        bands = torus_bands([math.pi - 0.3 * i / 2 for i in (0, 1, 2)])
        _pool, _refs, f = classify_bands(bands)
        return check("torus short span (sphere)", f.label, "sphere")

    def case_extruded_ellipse():
        e0 = ring(0, 0, 0, 10, 24, r2=5)
        e1 = ring(0, 0, 10, 10, 24, r2=5)
        e2 = ring(0, 0, 20, 10, 24, r2=5)
        pool = e0 + e1 + e2
        refs = [pool.index(p) for p in zig(e0, e1) + zig(e1, e2)]
        return check(
            "extruded ellipse", classify_strip_patch(refs, pool).label, "pencil-noncyl"
        )

    def case_plane_strip():
        pl0 = [(0, 0, 0), (4, 0, 0), (8, 0, 0), (12, 0, 0), (16, 0, 0)]
        pl1 = [(0, 3, 0), (4, 3, 0), (8, 3, 0), (12, 3, 0), (16, 3, 0)]
        pool = pl0 + pl1
        refs = [pool.index(p) for p in zig(pl0, pl1)]
        return check("plane strip", classify_strip_patch(refs, pool).label, "planar")

    def case_cone_jitter():
        cj0, cj1, cj2 = ring(0, 0, 0, 10, 24), ring(0, 0, 10, 7.0, 24), ring(0, 0, 20, 5, 24)
        pool = cj0 + cj1 + cj2
        refs = [pool.index(p) for p in zig(cj0, cj1) + zig(cj1, cj2)]
        f = classify_strip_patch(refs, pool)
        if f.label == "cone":
            return f"jittered radii accepted as cone (slope {f.slope})"
        return None

    def case_sphere_negative_ellipsoid():
        def ell_ring(z, rx, ry, n):
            pts = []
            for i in range(n):
                t = 2 * math.pi * i / n
                pts.append((rx * math.cos(t), ry * math.sin(t), z))
            return pts

        s0 = ell_ring(0, 12, 12, 24)
        s1 = ell_ring(4, 11, 5.5, 24)
        pool = s0 + s1
        refs = [pool.index(p) for p in zig(s0, s1)]
        f = classify_strip_patch(refs, pool)
        if f.label == "sphere":
            return f"ellipsoid accepted (R {f.radius})"
        return None

    def case_degenerate():
        pts = [(i * 1.0, 0.0, 0.0) for i in range(6)]
        return check(
            "collinear strip",
            classify_strip_patch(list(range(6)), pts).label,
            "degenerate",
        )

    return [
        ("cylinder", case_cylinder),
        ("cylinder_f32", case_cylinder_f32),
        ("cone", case_cone),
        ("sphere_cap", case_sphere_cap),
        ("sphere_short_span_cone", case_sphere_short_span_cone),
        ("cone_short_span_spherelike", case_cone_short_span_spherelike),
        ("torus_fillet", case_torus_fillet),
        ("torus_equator_cylinder", case_torus_equator_cylinder),
        ("torus_pole_planar", case_torus_pole_planar),
        ("torus_short_span_cone", case_torus_short_span_cone),
        ("torus_short_span_sphere", case_torus_short_span_sphere),
        ("extruded_ellipse", case_extruded_ellipse),
        ("plane_strip", case_plane_strip),
        ("cone_jitter_negative", case_cone_jitter),
        ("sphere_ellipsoid_negative", case_sphere_negative_ellipsoid),
        ("degenerate", case_degenerate),
    ]


def selftest():
    """Run the synthetic fixture set; returns a list of failure strings."""
    failures = []
    for name, case in _selftest_cases():
        message = case()
        if message:
            failures.append(f"{name}: {message}")
    return failures


def selftest_count():
    """Number of fixture cases :func:`selftest` runs (the claims row's size)."""
    return len(_selftest_cases())
