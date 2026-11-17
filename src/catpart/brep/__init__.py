"""B-rep construct decoders and the topological boundary graph (Phase 7, Spec G #47).

Scaffold for the Wave-1 dispatch of Spec G #47: each decode ticket lands
its own module here (``planar``, ``curves``, ``quadrics``,
``cgm_nurbs``) without touching this file; the orchestrator populates
the public surface at the BR6 integration step, per
docs/agents/handoff-2026-11-17.md. The L3 construct denominator is the
frozen vocabulary (docs/evidence/data/brep-construct-vocabulary.csv,
ticket #48 / BR1).
"""
