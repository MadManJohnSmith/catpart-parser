#!/usr/bin/env python3
"""Download a subset of the corpus named by a probe CSV / evidence note.

The w4 marathon evidence is measured on a small, named population (the
bag-rep carriers, the BLANK parts); downloading the full 3.4 GB corpus
is unnecessary to reproduce it. This reads ``manifests/corpus-manifest.csv``
and fetches only the rows whose ``path`` matches one of the given
substring patterns (or every missing row with ``--all-missing``),
verifying each download against the manifest sha256 (the same rule
``redownload_corpus.py`` applies corpus-wide).

Usage (from a clone of MadManJohnSmith/catpart-parser):

    python3 -I scripts/triage/download_corpus_subset.py [pattern ...]

No pattern: downloads every manifest row that is missing locally (the
redownload script's behavior, sequential and polite). With patterns:
a row is fetched when any pattern is a case-sensitive substring of its
``path``. ``--list`` prints what matched and what is already present
without downloading.
"""
import csv
import hashlib
import pathlib
import sys
import time
import urllib.request


def main(repo_root: pathlib.Path, patterns: list[str], list_only: bool) -> int:
    manifest = repo_root / "manifests" / "corpus-manifest.csv"
    rows = list(csv.DictReader(manifest.open(newline="")))
    if patterns:
        rows = [r for r in rows if any(p in r["path"] for p in patterns)]
        missing = [
            f"[{i}/{len(rows)}] {r['path']}"
            for i, r in enumerate(rows, 1)
            if not (repo_root / r["local_path"]).is_file()
        ]
        present = len(rows) - len(missing)
        if list_only:
            print(f"matched {len(rows)} rows, present {present}, missing {len(missing)}")
            for line in missing:
                print("  MISSING", line)
            return 0
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
    print(
        f"done: downloaded={ok} already-present={skipped} "
        f"failed={failed} hash-mismatch={hash_bad}"
    )
    return 1 if failed or hash_bad else 0


if __name__ == "__main__":
    args = sys.argv[1:]
    list_only = "--list" in args
    args = [a for a in args if a != "--list"]
    root = pathlib.Path(__file__).resolve().parents[2]
    raise SystemExit(main(root, args, list_only))
