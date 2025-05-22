#!/usr/bin/env python3
# unpack_droid_episode.py
#
# Usage:
#   python unpack_droid_episode.py /path/to/episode_dir  /path/to/out_dir
#
# Creates:
#   out_dir/
#     cam0/
#       data/
#         000000000.jpg  ...
#       data.csv
#     state_groundtruth_estimate0/
#       data.csv   (simply symlinked if it already exists)

import argparse, os, subprocess, csv, glob, shutil, json
from pathlib import Path

def extract_frames(video_path: Path, dst_dir: Path):
    """
    Uses ffmpeg to dump every frame in <video_path> into <dst_dir> as
    zero-padded JPEGs named after the frame's presentation timestamp.
    """
    dst_dir.mkdir(parents=True, exist_ok=True)
    # %013d keeps ns timestamps sorted lexicographically
    cmd = [
        "ffmpeg",
        "-loglevel", "error",          # be quiet unless something goes wrong
        "-i", str(video_path),
        "-vsync", "0",                 # keep original frame timing
        "-q:v", "2",                   # good JPEG quality
        str(dst_dir / "%013d.jpg")
    ]
    subprocess.run(cmd, check=True)

def main(ep_dir: str, out_dir: str):
    ep = Path(ep_dir).expanduser().resolve()
    out = Path(out_dir).expanduser().resolve()

    # 1. Find the camera video(s)
    #    – first look for non-stereo .mp4 files in the episode root
    mp4s = sorted([
        p for p in ep.iterdir()
        if p.is_file() and p.suffix.lower() == ".mp4" and not p.stem.endswith("-stereo")
    ])

    #    – if nothing found, accept the stereo stream(s) instead
    if not mp4s:
        mp4s = sorted([
            p for p in ep.iterdir()
            if p.is_file() and p.suffix.lower() == ".mp4" and p.stem.endswith("-stereo")
        ])

    #    – still nothing?  search recursively (some episodes tuck video under ./camera/ or similar)
    if not mp4s:
        mp4s = sorted(ep.rglob("*.mp4"))

    if not mp4s:
        raise RuntimeError(f"No .mp4 video found inside {ep}")

    cam_video = mp4s[0]        # each episode normally has one camera; grab the first
    print(f"Using video: {cam_video.name}")

    # 2. Extract frames
    frame_dir = out / "cam0" / "data"
    extract_frames(cam_video, frame_dir)

    # 3. Build cam0/data.csv  (timestamp,filename)
    csv_path = frame_dir.parent / "data.csv"
    with csv_path.open("w", newline="") as f:
        writer = csv.writer(f)
        for jpg in sorted(frame_dir.glob("*.jpg")):
            ts_ns = jpg.stem           # file stem = 13-digit ns timestamp
            writer.writerow([ts_ns, jpg.name])

    # 4. If the episode already came with GT poses, surface them verbatim
    gt_csv_src = ep / "state_groundtruth_estimate0" / "data.csv"
    if gt_csv_src.exists():
        gt_dst_dir = out / "state_groundtruth_estimate0"
        gt_dst_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(gt_csv_src, gt_dst_dir / "data.csv")

    print(f"Done. Images → {frame_dir}, index → {csv_path}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Unpack a Droid-raw episode into the cam0/ pose/ layout"
    )
    ap.add_argument("episode_dir", help="Path to raw episode folder")
    ap.add_argument("out_dir",     help="Where to create cam0/ etc.")
    args = ap.parse_args()
    main(args.episode_dir, args.out_dir)