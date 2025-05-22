#!/usr/bin/env python3
"""batch_svo2mcap.py

Walk a directory tree, find every *.svo file, and convert it to an
adjacent *.mcap (same basename) using `svo2mcap.py`.

Example
-------
    python scripts/batch_svo2mcap.py  /data/zed_logs  --out-dir /data/mcap   \
            --absolute-time  --workers 4

If --out-dir is omitted the .mcap is written next to the .svo.
"""
from __future__ import annotations
import argparse, subprocess, os, sys, concurrent.futures, pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parent
SINGLE_CONVERTER = REPO_ROOT / "svo2mcap.py"


def convert_one(svo_path: pathlib.Path, out_path: pathlib.Path, abs_time: bool):
    cmd = [sys.executable, str(SINGLE_CONVERTER), str(svo_path), str(out_path)]
    if abs_time:
        cmd.append("--absolute-time")
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as e:
        print(f"❌ Conversion failed for {svo_path}: {e}")


def main():
    ap = argparse.ArgumentParser(description="Batch convert SVO recordings to MCAP")
    ap.add_argument("input_dir", help="Root directory to search for .svo files")
    ap.add_argument("--out-dir", help="Root directory to mirror outputs under")
    ap.add_argument("--absolute-time", action="store_true",
                    help="Stamp bags with wall-clock time")
    ap.add_argument("--workers", type=int, default=os.cpu_count(),
                    help="Concurrent workers (default: #CPU cores)")
    args = ap.parse_args()

    in_root = pathlib.Path(args.input_dir).expanduser().resolve()
    if args.out_dir:
        out_root = pathlib.Path(args.out_dir).expanduser().resolve()
        out_root.mkdir(parents=True, exist_ok=True)
    else:
        out_root = None

    jobs: list[tuple[pathlib.Path, pathlib.Path]] = []
    for svo_file in in_root.rglob("*.svo"):
        if out_root:
            rel = svo_file.relative_to(in_root)
            target = out_root / rel.with_suffix(".mcap")
            target.parent.mkdir(parents=True, exist_ok=True)
        else:
            target = svo_file.with_suffix(".mcap")
        jobs.append((svo_file, target))

    print(f"Found {len(jobs)} SVO recordings → converting with {args.workers} workers")

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        fts = [pool.submit(convert_one, s, t, args.absolute_time) for s, t in jobs]
        for ft in concurrent.futures.as_completed(fts):
            pass  # progress printed by convert_one

    print("✅ Batch conversion finished")


if __name__ == "__main__":
    main() 