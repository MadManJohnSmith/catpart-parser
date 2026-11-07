# Research: the CATPart tooling landscape (2026-11-06)

Question: is there any existing open-source effort to read CATIA V5
`.CATPart`/`.CATProduct` binaries directly? Verdict: **no** — the field is
open. What exists today:

## What exists

- **COM automation, requires a running CATIA license.** Everything mainstream
  drives a CATIA instance instead of parsing files:
  [pycatia](https://github.com/evereux/pycatia) (Python, pywin32),
  [STARIONGROUP/DEH-CATIA](https://github.com/STARIONGROUP/DEH-CATIA) (C#),
  [TUMFTM/MATLAB2CAD](https://github.com/TUMFTM/MATLAB2CAD) (MATLAB).
- **Closest thing to file-level tooling:** [cadmpeg/cadmpeg](https://github.com/cadmpeg/cadmpeg)
  (CLI CAD format conversion; references a "L3 profile" for CATPart). Not a
  documented, reusable parser library.
- **Neutral-format escape hatch:** OpenCascade and similar kernels read STEP/
  IGES — but those require CATIA (or a paid converter) to produce them in the
  first place.
- The format is repeatedly described as **undocumented** in third-party
  discussions (e.g. MATLAB community threads asking how to read CATPart
  programmatically without CATIA).

## What this means

- Reading `.CATPart` binaries without a CATIA seat is a genuine gap; paid
  converters (CAD Exchanger and similar) are the only practical interop
  route today.
- A reproducible corpus of public files is achievable via model-sharing
  platforms (GrabCAD and similar) and university course archives.
- Effort split: "parse the structure" (containers, compression, object
  tables) is the tractable core; "interpret geometry" (B-rep semantics) is
  the deep end.

## Sources

- https://github.com/cadmpeg/cadmpeg
- https://github.com/TUMFTM/MATLAB2CAD
- https://github.com/STARIONGROUP/DEH-CATIA
- MATLAB community discussions on reading CATPart without CATIA (multiple threads)

*Caveat: absence of evidence from search is not proof of absence; a deeper
survey (papers, patent literature) is planned during Phase 1.*
