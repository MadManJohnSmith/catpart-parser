# ADR-0003: Fitness is measured locally and published via gh-pages

The corpus (≈2,500 binaries, ~3.4 GB) is gitignored by design and never
transferred to GitHub, so CI cannot measure real fitness. Decision: real
fitness is always measured on the machine holding `corpus/`, by a local
scheduled or on-demand job that publishes the results; GitHub Actions is
kept light — unit tests over script-generated synthetic fixtures (never
real binaries) and lint on every PR. Publication goes to the `gh-pages`
branch as dynamic JSON (fitness history plus the latest Dev scalar) with a
shields.io badge pointing at that endpoint, linked from the README.

## Considered Options

- Self-hosted Actions runner: rejected — daemon and security surface to
  maintain for one machine.
- Actions downloading the corpus at runtime (with cache): rejected —
  15-20 minutes per run, LFS/raw rate limits, and breakage if a source
  dies.
- History only in the repo, no badge: rejected by the maintainer — trend
  visibility in the README was wanted, accepting one external service
  (shields.io) in the loop.

## Consequences

- `gh-pages` is the fitness visibility surface; the local job updates it.
- shields.io is an accepted external dependency of the grind loop.
