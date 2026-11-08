#!/usr/bin/env python3
"""Re-download the catpart-parser corpus from its documented sources.

Usage (from a clone of MadManJohnSmith/catpart-parser):
    python3 -I <path-to>/redownload_corpus.py <repo-root>

Reads manifests/corpus-manifest.csv (columns include local_path, source_url,
sha256), downloads every missing file into <repo-root>/<local_path> and
verifies each download against the manifest sha256. Existing files are kept.

Caveat: source URLs point at third-party GitHub repos that may have been
deleted or renamed since 2026-11-07; failures are reported, not fatal.
Sequential and polite (0.2 s between requests); no parallelism.
"""
import csv
import hashlib
import pathlib
import sys
import time
import urllib.request

def main(repo_root: pathlib.Path) -> int:
    manifest = repo_root / "manifests" / "corpus-manifest.csv"
    rows = list(csv.DictReader(manifest.open(newline="")))
    ok = skipped = failed = hash_bad = 0
    for i, r in enumerate(rows, 1):
        dest = repo_root / r["local_path"]
        if dest.is_file():
            skipped += 1
            continue
        try:
            with urllib.request.urlopen(r["source_url"], timeout=60) as resp:
                data = resp.read()
        except Exception as exc:  # noqa: BLE001 - report and continue
            print(f"[{i}/{len(rows)}] FAIL {r['local_path']}: {exc}")
            failed += 1
            time.sleep(0.2)
            continue
        digest = hashlib.sha256(data).hexdigest()
        if digest != r["sha256"]:
            print(f"[{i}/{len(rows)}] HASH-MISMATCH {r['local_path']}")
            hash_bad += 1
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        ok += 1
        if i % 100 == 0:
            print(f"[{i}/{len(rows)}] ok={ok} skipped={skipped} failed={failed}")
        time.sleep(0.2)
    print(f"done: downloaded={ok} already-present={skipped} failed={failed} hash-mismatch={hash_bad}")
    return 1 if (failed or hash_bad) else 0

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1])))
