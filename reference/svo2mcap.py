#!/usr/bin/env python3
"""svo2mcap.py

Convert a ZED SVO recording into an MCAP file that Foxglove can open.

Outputs two topics:
  • /zed/left/compressed  – foxglove.CompressedImage (JPEG)
  • /zed/pose            – foxglove.PoseInFrame      (camera/world pose)

Requirements
------------
• ZED SDK + Python API (pyzed-sl).  Install from:
    https://www.stereolabs.com/docs/installation/  (Ubuntu or Windows)
• mcap-python           `pip install mcap-python`
• opencv-python         (for JPEG encoding)

Usage
-----
    python scripts/svo2mcap.py  input.svo  output.mcap  [--absolute-time]
"""
from __future__ import annotations
import os, sys, json, base64, argparse, time, pathlib
from typing import Optional

import cv2
import numpy as np
from mcap.writer import Writer
from pyzed import sl

DEFAULT_CHANNEL_LEFT = "/zed/left/compressed"
DEFAULT_CHANNEL_POSE = "/zed/pose"


def register_schemas(writer: Writer):
    """Return (image_schema_id, pose_schema_id)."""
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
                "sec":  {"type": "integer"},
                "nsec": {"type": "integer"}
              }
            },
            "frame_id": {"type": "string"},
            "data": {"type": "string", "contentEncoding": "base64"},
            "format": {"type": "string"}
          }
        }
        """
    )

    pose_schema_id = writer.register_schema(
        name="foxglove.PoseInFrame",
        encoding="jsonschema",
        data=b"""
        {
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
    return image_schema_id, pose_schema_id


def ns_from_ts(ts: int, origin_ns: int = 0) -> tuple[int, int, int]:
    """Return (timestamp_ns, sec, nsec) shifted by origin_ns."""
    t_ns = ts + origin_ns
    return t_ns, t_ns // 1_000_000_000, t_ns % 1_000_000_000


def convert_svo_to_mcap(svo_path: str, out_path: str, absolute_time: bool = False):
    if not os.path.exists(svo_path):
        sys.exit(f"SVO file not found: {svo_path}")

    # --------------------------- ZED initialisation ---------------------------
    cam = sl.Camera()
    init_params = sl.InitParameters(input_t=sl.InputType(svo_path))
    init_params.coordinate_units = sl.UNIT.METER
    init_params.depth_mode = sl.DEPTH_MODE.NONE  # we only need images + pose

    if cam.open(init_params) != sl.ERROR_CODE.SUCCESS:
        sys.exit(f"Failed to open SVO: {cam.get_last_error()}")

    # Enable tracking so we get poses
    tracking_params = sl.PositionalTrackingParameters()
    if cam.enable_positional_tracking(tracking_params) != sl.ERROR_CODE.SUCCESS:
        sys.exit("Failed to enable positional tracking")

    # Prepare containers
    left_mat = sl.Mat()
    pose = sl.Pose()

    # Determine origin shift
    origin_ns = 0
    if absolute_time:
        origin_ns = int(time.time() * 1_000_000_000)

    with open(out_path, "wb") as f:
        writer = Writer(f)
        writer.start()

        img_schema_id, pose_schema_id = register_schemas(writer)
        img_channel_id = writer.register_channel(
            schema_id=img_schema_id,
            topic=DEFAULT_CHANNEL_LEFT,
            message_encoding="json",
        )
        pose_channel_id = writer.register_channel(
            schema_id=pose_schema_id,
            topic=DEFAULT_CHANNEL_POSE,
            message_encoding="json",
        )

        img_seq = 0
        pose_seq = 0

        runtime = sl.RuntimeParameters()

        while True:
            if cam.grab(runtime) != sl.ERROR_CODE.SUCCESS:
                break  # end of SVO

            # ----------------------- timestamp -----------------------
            ts_cam = cam.get_timestamp(sl.TIME_REFERENCE.IMAGE).get_nanoseconds()
            t_ns, sec, nsec = ns_from_ts(ts_cam, origin_ns)

            # ----------------------- image ---------------------------
            cam.retrieve_image(left_mat, sl.VIEW.LEFT)
            img_rgba = left_mat.get_data()  # numpy HxWx4 uint8
            img_rgb = cv2.cvtColor(img_rgba, cv2.COLOR_BGRA2BGR)
            ok, jpeg_buf = cv2.imencode(".jpg", img_rgb, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            if not ok:
                continue

            img_msg = {
                "timestamp": {"sec": sec, "nsec": nsec},
                "frame_id": "zed_left",
                "data": base64.b64encode(jpeg_buf.tobytes()).decode("ascii"),
                "format": "jpeg",
            }
            writer.add_message(
                channel_id=img_channel_id,
                sequence=img_seq,
                log_time=t_ns,
                publish_time=t_ns,
                data=json.dumps(img_msg).encode("utf-8"),
            )
            img_seq += 1

            # ----------------------- pose ---------------------------
            if cam.get_position(pose, sl.REFERENCE_FRAME.WORLD) == sl.POSITIONAL_TRACKING_STATE.OK:
                trans = pose.get_translation().get()
                orient = pose.get_orientation().get()
                pose_msg = {
                    "timestamp": {"sec": sec, "nsec": nsec},
                    "frame_id": "world",
                    "pose": {
                        "position": {"x": trans[0], "y": trans[1], "z": trans[2]},
                        "orientation": {"x": orient[0], "y": orient[1], "z": orient[2], "w": orient[3]},
                    },
                }
                writer.add_message(
                    channel_id=pose_channel_id,
                    sequence=pose_seq,
                    log_time=t_ns,
                    publish_time=t_ns,
                    data=json.dumps(pose_msg).encode("utf-8"),
                )
                pose_seq += 1

        writer.finish()
    cam.disable_positional_tracking()
    cam.close()
    print(f"✅ Wrote {img_seq} images and {pose_seq} poses to {out_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Convert ZED .svo to MCAP")
    ap.add_argument("svo", help="Input SVO filename")
    ap.add_argument("out", help="Output .mcap filename")
    ap.add_argument("--absolute-time", action="store_true",
                    help="Shift timestamps to wall-clock epoch")
    args = ap.parse_args()

    convert_svo_to_mcap(args.svo, args.out, args.absolute_time) 