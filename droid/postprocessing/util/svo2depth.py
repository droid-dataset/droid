"""
svo2mp4.py

Utility scripts for using the ZED Python SDK and FFMPEG to convert raw `.svo` files to `.mp4` files (including "fused"
MP4s with multiple camera feeds).
"""
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import pyzed.sl as sl
from tqdm import tqdm
import imageio

def export_depth(
    svo_file: Path,
    depth_dir: Path,
    stereo_view: str = "left",
    resolution: tuple = (0,0),
    frequency: int = 1,
    show_progress: bool = False
) -> bool:
    """Reads an SVO file, dumping the export depth to the desired path; supports ZED SDK 3.8.* and 4.0.* ONLY."""
    
    # Create Depth Folder
    depth_out = depth_dir / f"{svo_file.stem}"
    os.makedirs(depth_out, exist_ok=True)
    sdk_version, use_sdk_4 = sl.Camera().get_sdk_version(), None
    if not (sdk_version.startswith("4.0") or sdk_version.startswith("3.8")):
        raise ValueError("Function `export_mp4` only supports ZED SDK 3.8 OR 4.0; if you see this, contact Sidd!")
    else:
        use_sdk_4 = sdk_version.startswith("4.0")

    # Configure PyZED --> set mostly from SVO Path, don't convert in realtime!
    initial_parameters = sl.InitParameters()
    initial_parameters.set_from_svo_file(str(svo_file))
    initial_parameters.svo_real_time_mode = False
    initial_parameters.coordinate_units = sl.UNIT.MILLIMETER
    initial_parameters.camera_image_flip = sl.FLIP_MODE.OFF
    if stereo_view == "right":
        initial_parameters.enable_right_side_measure = True
        depth_measure = sl.MEASURE.DEPTH_RIGHT
    else:
        depth_measure = sl.MEASURE.DEPTH

    # Create ZED Camera Object & Open SVO File
    zed = sl.Camera()
    err = zed.open(initial_parameters)
    if err != sl.ERROR_CODE.SUCCESS:
        zed.close()
        return False

    # Set Reading Resolution #
    depth_resolution = sl.Resolution(*resolution)

    # Create ZED Image Containers
    assert stereo_view in {"left", "right"}, f"Invalid View to Export `{stereo_view}`!"
    img_container = sl.Mat()

    # SVO Export
    n_frames, rt_parameters = zed.get_svo_number_of_frames(), sl.RuntimeParameters()
    if show_progress:
        pbar = tqdm(total=n_frames, desc="     => Exporting SVO Frames", leave=False)

    # Read & Transcode all Frames
    while True:
        grabbed = zed.grab(rt_parameters)

        # [NOTE SDK SEMANTICS] --> ZED SDK 4.0 introduces `sl.ERROR_CODE.END_OF_SVOFILE_REACHED`
        if (grabbed == sl.ERROR_CODE.SUCCESS) or (use_sdk_4 and (grabbed == sl.ERROR_CODE.END_OF_SVOFILE_REACHED)):
            svo_position = zed.get_svo_position()
            should_extract = svo_position % frequency == 0
            if should_extract:
                zed.retrieve_measure(img_container, depth_measure, resolution=depth_resolution)
                processed_depth = (img_container.get_data() * 1000).astype(np.uint16)
                imageio.imwrite(depth_out / '{0}.png'.format(svo_position), processed_depth)

            # Update Progress
            if show_progress:
                pbar.update()

            # [NOTE SDK SEMANTICS] --> Check if we've reached the end of the video
            if (svo_position >= (n_frames - 1)) or (use_sdk_4 and (grabbed == sl.ERROR_CODE.END_OF_SVOFILE_REACHED)):
                break

    # Cleanup & Return
    zed.close()
    if show_progress:
        pbar.close()

    return True


def convert_depths(
    data_dir: Path,
    demo_dir: Path,
    wrist_serial: str,
    ext1_serial: str,
    ext2_serial: str,
    ext1_extrinsics: List[float],
    ext2_extrinsics: List[float],
    resolution: tuple,
    frequency: int,
    do_fuse: bool = False,
) -> Tuple[bool, Optional[Dict[str, str]]]:
    """Convert each `serial.svo` to a valid MP4 file, updating the `data_record` path entries in-place."""
    svo_path, depth_path = demo_dir / "recordings" / "SVO", demo_dir / "recordings" / "Depth"
    os.makedirs(depth_path, exist_ok=True)
    for svo_file in svo_path.iterdir():
        successful_convert = export_depth(svo_file, depth_path, resolution=resolution, frequency=frequency, show_progress=True)
        if not successful_convert:
            return False, None

    # Associate Ext1 / Ext2 with left/right positions relative to the robot base; use computed extrinsics.
    #   => Extrinsics are saved as a 6-dim vector of [pos; rot] where:
    #       - `pos` is (x, y, z) offset --> moving left of robot is +y, moving right is -y
    #       - `rot` is rotation offset as Euler (`R.from_matrix(rmat).as_euler("xyz")`)
    #   => Therefore we can compute `left = ext1_serial if ext1_extrinsics[1] > ext2_extrinsics[1]`
    ext1_y, ext2_y = ext1_extrinsics[1], ext2_extrinsics[1]
    left_serial = ext1_serial if ext1_y > ext2_y else ext2_serial
    right_serial = ext2_serial if left_serial == ext1_serial else ext1_serial

    # Create Dictionary of SVO/MP4 Paths
    rel_svo_path, rel_depth_path = svo_path.relative_to(data_dir), depth_path.relative_to(data_dir)
    record_paths = {
        "wrist_svo_path": str(rel_svo_path / f"{wrist_serial}.svo"),
        "wrist_depth_path": str(rel_depth_path / f"{wrist_serial}"),
        "ext1_svo_path": str(rel_svo_path / f"{ext1_serial}.svo"),
        "ext1_depth_path": str(rel_depth_path / f"{ext1_serial}"),
        "ext2_svo_path": str(rel_svo_path / f"{ext2_serial}.svo"),
        "ext2_depth_path": str(rel_depth_path / f"{ext2_serial}"),
        "left_depth_path": str(rel_depth_path / f"{left_serial}"),
        "right_depth_path": str(rel_depth_path / f"{right_serial}"),
    }

    return True, record_paths
