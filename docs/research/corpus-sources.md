# Research: public corpus routes for CATPart files (2026-11-06)

Question: which public sources yield ≥ 100 `.CATPart` files across multiple
CATIA V5 release lines and domains, with no paid account, and what are the
exact fetch routes?

Verdict: **the ≥ 100-file bar is met anonymously by GitHub alone** — 383
`.CATPart`/`.CATProduct` files verified in 4 public repos, with a validated
end-to-end anonymous download route (Git LFS). Per-file version coverage
cannot be confirmed before byte triage; one repo is explicitly documented as
built with CATIA V5R21. Account-gated libraries (GrabCAD and similar) are
**not load-bearing** for volume; they remain a diversity option.

## Route A (primary, validated): GitHub public repositories

### Discovery

Legacy code search indexes default branches only:

```
gh api 'search/code?q=extension:CATPart&per_page=100&page=N'    # 354 hits, 13 repos (checked 2026-11-06)
gh api 'search/code?q=extension:CATProduct&per_page=100&page=N' # 23 hits
```

Exact per-repo inventory (also detects Git LFS by blob size):

```
gh api 'repos/<owner>/<repo>/git/trees/<branch>?recursive=1' \
  --jq '[.tree[] | select((.path|endswith(".CATPart")) or (.path|endswith(".CATProduct")))]'
```

### Verified repositories (checked 2026-11-06)

| Repo | Files | Domain | License | Version evidence |
|---|---|---|---|---|
| hssnadr/HTBX_01Ressources | 125 | electronics enclosure (controller, boards, case) | MIT | README states CATIA V5R21 32-bit |
| Apoloo13/ASE_III | 111 | animatronic head (servos, molds, mechanisms) | NOASSERTION | — |
| dolganin/SO_SPIDAR300 | 74 | robot arm (gimbal, gripper, fasteners) | none | — |
| Guilherme115/Motor-V6 | 73 | V6 engine assembly (block, valves, belts) | none | — |

Nine further repos contribute 1-7 files each. Domain spread is good
(electronics, mechanisms, automotive, robotics); author spread is 4 major
contexts plus singles. Standard parts (ISO fasteners, connectors) recur
across repos — dedupe by SHA-256 before counting corpus entries.

### Download route (anonymous, validated on all 4 repos)

1. Read the LFS pointer at `https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<url-encoded-path>`
   → gives `oid sha256:...` and `size` **without downloading the binary**.
2. Download via `https://media.githubusercontent.com/media/<owner>/<repo>/<branch>/<url-encoded-path>`
   → validated HTTP 200, `application/octet-stream`, bytes match the pointer.
3. Regular (non-LFS) blobs download from `raw.githubusercontent.com` directly.

All 383 files in the 4 main repos are LFS-backed. URL-encode paths (spaces,
accents: `jq -Rr @uri`). Example pointer: `oid sha256:ef61cfc2…`, size
5002500.

### Quality signal

First 8 bytes of every file checked (parts and products, 4 independent
repos) are `56 35 5F 43 46 56 32 00` — ASCII `V5_CFV2\0`. Bytes 8-11 vary
per file (uninterpreted dword). Corpus candidates are genuine CATIA V5
containers, not renamed junk. This observation belongs to Phase 1 triage;
recorded here as route-validation evidence.

### Licensing

Manifest records digests + source URLs only; binaries are never committed,
so unlicensed (all-rights-reserved) repos are compatible with the project's
legal posture. hssnadr/HTBX_01Ressources is MIT, which would additionally
permit redistributing its files if ever needed.

## Route B (secondary, unverified): Dassault EDU course materials

The official-style student guide `EDU_CAT_EN_V5F_FB_V5R19.pdf` is publicly
hosted at `yvonet.florent.free.fr/SERVEUR/COURS CATIA/` (confirmed URL,
2026-11-06). EDU guides exist for several releases, so this route could add
multi-release coverage, but the server does not expose directory listings
(empty response to listing requests) and exercise binaries were not
reachable without manual URL discovery. Revisit only if Phase 1 shows
version gaps.

## Route C (account-gated): GrabCAD, TraceParts, 3D ContentCentral

Massive libraries tagged `catpart` (e.g.
https://grabcad.com/library/tag/catpart) but all require a free account to
download. Not needed for the 100-file bar; decision recorded in the GrabCAD
wayfinder ticket (closed 2026-11-06 with a reopen trigger).

## Dead ends (negative results, checked 2026-11-06)

- **GitLab.com** anonymous blob search: `401 Unauthorized` (API requires auth).
- **Codeberg** repo search for "catpart": 0 results.
- **TransMagic** free-sample page and format-support post: no direct
  CATPart download links found.
- **CAD Exchanger** (`cadexchanger.com/catpart`): format documentation and an
  online converter only; no anonymous sample downloads.
- **archive.org**: books and tutorials about CATIA (borrow-only scans), no
  model files.
- **Academic CAD datasets** (SldprtNet, ABC, Fusion 360 Gallery): distribute
  SLDPRT or STEP/B-rep, not native CATPart.
- **University sites** (.edu): syllabi reference `.CATPart` files but no
  public course-file repositories surfaced via search.

## Bottom line and recommended download order

1. The 4 verified GitHub repos (383 candidates, dedupe by SHA-256) — exceeds
   the 100-file bar alone.
2. The 9 smaller GitHub repos for author diversity.
3. Only if Phase 1 triage shows version monoculture or diversity deficits:
   reopen the GrabCAD decision or work the EDU route (Route B).

## Mapping to the manifest

`manifests/corpus-manifest.csv` columns per `docs/ROADMAP.md`: SHA-256 (from
the LFS pointer, verify after download), source URL (the exact raw/media
URL), reported CATIA version (repo context when stated, otherwise blank —
Phase 1 triage detects it), size (from the pointer).
