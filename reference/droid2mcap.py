import os, json, base64
import pandas as pd
import numpy as np
from mcap.writer import Writer
import time

DEFAULT_FRAME_PERIOD_NS = 33_333_333  # 30 fps

# -----------------------------------------------------------------------------
# CLI helpers will set this after argument parsing; keep at module level so the
# to_nanoseconds() helper doesn't need to know about CLI flags.
# -----------------------------------------------------------------------------

_GLOBAL_ORIGIN_NS = 0  # added to every log/publish timestamp

# -----------------------------------------------------------------------------
# Helper
# -----------------------------------------------------------------------------

def to_nanoseconds(raw_ts: int, idx: int, period_ns: int = DEFAULT_FRAME_PERIOD_NS) -> int:
    """Return *monotonically increasing* nanosecond stamp.

    The Droid CSV sometimes stores:

    • real nanoseconds since epoch (≥ 1 e15)
    • microseconds since epoch  (≥ 1 e12 but < 1 e15)
    • simple frame indices starting at 0 (< 1 e9)

    This helper normalises each variant to nanoseconds.
    """

    if raw_ts >= 1_000_000_000_000_000:  # ≥ 1 e15 → already ns
        return raw_ts

    if raw_ts >= 1_000_000_000_000:      # 1 e12-1 e15 → μs
        return raw_ts * 1_000

    # Otherwise treat as sequential frame counter
    return idx * period_ns

def convert_droid_to_mcap(droid_path: str, out_path: str):
    image_dir = os.path.join(droid_path, "cam0", "data")
    image_csv = os.path.join(droid_path, "cam0", "data.csv")
    pose_csv = os.path.join(droid_path, "state_groundtruth_estimate0", "data.csv")

    image_df = pd.read_csv(image_csv)

    pose_available = os.path.exists(pose_csv)
    if pose_available:
        pose_df = pd.read_csv(pose_csv)
        pose_dict = {}
        for idx, r in enumerate(pose_df.values):
            ts_ns = to_nanoseconds(int(r[0]), idx)
            pose_dict[ts_ns] = r[1:]
    else:
        pose_dict = {}

    with open(out_path, "wb") as f:
        writer = Writer(f)
        writer.start()

        # Define schemas
        image_schema_id = writer.register_schema(
            name="foxglove.CompressedImage",
            encoding="jsonschema",
            data=b"""
            {
                "type": "object",
                "properties": {
                    "timestamp": {
                        "type": "object",
                        "properties": {
                            "sec": { "type": "integer" },
                            "nsec": { "type": "integer" }
                        }
                    },
                    "frame_id": { "type": "string" },
                    "data": { "type": "string", "contentEncoding": "base64" },
                    "format": { "type": "string" }
                }
            }
            """
        )

        if pose_available:
            pose_schema_id = writer.register_schema(
                name="foxglove.PoseInFrame",
                encoding="jsonschema",
                data=b"""
                {
                  "$schema": "http://json-schema.org/draft-07/schema#",
                  "type": "object",
                  "properties": {
                    "timestamp": {
                      "type": "object",
                      "properties": {
                        "sec":  {"type": "integer"},
                        "nsec": {"type": "integer"}
                      }
                    },
                    "frame_id": {"type": "string"},
                    "pose": {
                      "type": "object",
                      "properties": {
                        "position": {
                          "type": "object",
                          "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "z": {"type": "number"}
                          }
                        },
                        "orientation": {
                          "type": "object",
                          "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "z": {"type": "number"},
                            "w": {"type": "number"}
                          }
                        }
                      }
                    }
                  }
                }
                """
            )

        image_channel_id = writer.register_channel(
            schema_id=image_schema_id,
            topic="/cam0/image",
            message_encoding="json"
        )

        if pose_available:
            pose_channel_id = writer.register_channel(
                schema_id=pose_schema_id,
                topic="/cam0/pose",
                message_encoding="json"
            )

        img_seq = 0
        pose_seq = 0

        # ------------------------------------------------------------------
        # Emit *all* poses so motion can be visualised in the 3-D panel.
        # ------------------------------------------------------------------
        if pose_available:
            for idx, (rel_ts_ns, pose) in enumerate(sorted(pose_dict.items())):
                timestamp_ns = rel_ts_ns + _GLOBAL_ORIGIN_NS

                ts_sec = timestamp_ns // 1_000_000_000
                ts_nsec = timestamp_ns % 1_000_000_000

                pos = {"x": pose[0], "y": pose[1], "z": pose[2]}
                orient = {"x": pose[3], "y": pose[4], "z": pose[5], "w": pose[6]}

                pose_msg = {
                    "timestamp": {"sec": ts_sec, "nsec": ts_nsec},
                    "frame_id": "world",
                    "pose": {
                        "position": pos,
                        "orientation": orient
                    }
                }

                writer.add_message(
                    channel_id=pose_channel_id,
                    sequence=pose_seq,
                    log_time=timestamp_ns,
                    publish_time=timestamp_ns,
                    data=json.dumps(pose_msg).encode("utf-8")
                )
                pose_seq += 1

        for idx, row in image_df.iterrows():
            raw_ts = int(row.iloc[0])
            timestamp_ns = to_nanoseconds(raw_ts, idx) + _GLOBAL_ORIGIN_NS

            filename = row.iloc[1]
            image_path = os.path.join(image_dir, filename)
            if not os.path.exists(image_path):
                continue

            # Read raw JPEG bytes and base64-encode them
            try:
                with open(image_path, "rb") as img_file:
                    jpeg_bytes = img_file.read()
            except OSError:
                continue  # skip unreadable file

            ts_sec = timestamp_ns // 1_000_000_000
            ts_nsec = timestamp_ns % 1_000_000_000

            img_msg = {
                "timestamp": {"sec": ts_sec, "nsec": ts_nsec},
                "frame_id": "cam0",
                "data": base64.b64encode(jpeg_bytes).decode("ascii"),
                "format": "jpeg"
            }

            writer.add_message(
                channel_id=image_channel_id,
                sequence=img_seq,
                log_time=timestamp_ns,
                publish_time=timestamp_ns,
                data=json.dumps(img_msg).encode("utf-8")
            )
            img_seq += 1

        writer.finish()
    print(f"✅ MCAP file written to {out_path}")

if __name__ == "__main__":
    import argparse, sys, pathlib, json

    ap = argparse.ArgumentParser(
        description="Convert a Droid episode (after unpack) into an MCAP file"
    )
    ap.add_argument("episode_dir", help="Path to directory that contains cam0/ etc.")
    ap.add_argument("out_mcap", help="Output .mcap filename")
    ap.add_argument("--absolute-time", action="store_true",
                    help="Shift timestamps so the bag starts at file-modification Unix time")
    args = ap.parse_args()

    # Expand ~ and make absolute so the user can supply relative paths.
    ep_dir = pathlib.Path(args.episode_dir).expanduser().resolve()
    out_path = pathlib.Path(args.out_mcap).expanduser().resolve()

    if not ep_dir.exists():
        sys.exit(f"Episode directory not found: {ep_dir}")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Determine origin shift if requested
    if args.absolute_time:
        # Use modification time of the first image as anchor
        first_row = pd.read_csv(ep_dir / "cam0" / "data.csv", nrows=1).iloc[0]
        first_img_path = ep_dir / "cam0" / "data" / first_row[1]
        if first_img_path.exists():
            _GLOBAL_ORIGIN_NS = int(os.path.getmtime(first_img_path) * 1_000_000_000)
        else:
            _GLOBAL_ORIGIN_NS = int(time.time() * 1_000_000_000)

    convert_droid_to_mcap(str(ep_dir), str(out_path))
