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
import pyzed.sl as sl
from tqdm import tqdm


def export_mp4(svo_file: Path, mp4_dir: Path, stereo_view: str = "left", show_progress: bool = False) -> bool:
    """Reads an SVO file, dumping the export MP4 to the desired path; supports ZED SDK 3.8.* and 4.0.* ONLY."""
    mp4_out = mp4_dir / f"{svo_file.stem}.mp4"
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

    # Create ZED Camera Object & Open SVO File
    zed = sl.Camera()
    err = zed.open(initial_parameters)
    if err != sl.ERROR_CODE.SUCCESS:
        zed.close()
        return False

    # [NOTE SDK SEMANTICS] --> Get Image Size & FPS
    if use_sdk_4:
        fps = zed.get_camera_information().camera_configuration.fps
        resolution = zed.get_camera_information().camera_configuration.resolution
        width, height = resolution.width, resolution.height
    else:
        fps = zed.get_camera_information().camera_fps
        resolution = zed.get_camera_information().camera_resolution
        width, height = resolution.width, resolution.height

    # Create ZED Image Containers
    assert stereo_view in {"left", "right"}, f"Invalid View to Export `{stereo_view}`!"
    img_container = sl.Mat()

    # Create a VideoWriter with the MP4V Codec
    video_writer = cv2.VideoWriter(
        str(mp4_out),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not video_writer.isOpened():
        print(f"Error Opening CV2 Video Writer; check the MP4 path `{mp4_out}` and permissions!")
        zed.close()
        return False

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
            zed.retrieve_image(img_container, {"left": sl.VIEW.LEFT, "right": sl.VIEW.RIGHT}[stereo_view])

            # Copy image data into VideoWrite after converting to RGB
            rgb = cv2.cvtColor(img_container.get_data(), cv2.COLOR_RGBA2RGB)
            video_writer.write(rgb)

            # Update Progress
            if show_progress:
                pbar.update()

            # [NOTE SDK SEMANTICS] --> Check if we've reached the end of the video
            if (svo_position >= (n_frames - 1)) or (use_sdk_4 and (grabbed == sl.ERROR_CODE.END_OF_SVOFILE_REACHED)):
                break

    # Cleanup & Return
    video_writer.release()
    zed.close()
    if show_progress:
        pbar.close()

    return True


def convert_mp4s(
    data_dir: Path,
    demo_dir: Path,
    wrist_serial: str,
    ext1_serial: str,
    ext2_serial: str,
    ext1_extrinsics: List[float],
    ext2_extrinsics: List[float],
    do_fuse: bool = False,
) -> Tuple[bool, Optional[Dict[str, str]]]:
    """Convert each `serial.svo` to a valid MP4 file, updating the `data_record` path entries in-place."""
    svo_path, mp4_path = demo_dir / "recordings" / "SVO", demo_dir / "recordings" / "MP4"
    os.makedirs(mp4_path, exist_ok=True)
    for svo_file in svo_path.iterdir():
        successful_convert = export_mp4(svo_file, mp4_path, show_progress=True)
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
    rel_svo_path, rel_mp4_path = svo_path.relative_to(data_dir), mp4_path.relative_to(data_dir)
    record_paths = {
        "wrist_svo_path": str(rel_svo_path / f"{wrist_serial}.svo"),
        "wrist_mp4_path": str(rel_mp4_path / f"{wrist_serial}.mp4"),
        "ext1_svo_path": str(rel_svo_path / f"{ext1_serial}.svo"),
        "ext1_mp4_path": str(rel_mp4_path / f"{ext1_serial}.mp4"),
        "ext2_svo_path": str(rel_svo_path / f"{ext2_serial}.svo"),
        "ext2_mp4_path": str(rel_mp4_path / f"{ext2_serial}.mp4"),
        "left_mp4_path": str(rel_mp4_path / f"{left_serial}.mp4"),
        "right_mp4_path": str(rel_mp4_path / f"{right_serial}.mp4"),
    }

    if do_fuse:
        # Build Fused Left/Right MP4 Files via FFMPEG
        left, right = str(mp4_path / f"{left_serial}.mp4"), str(mp4_path / f"{right_serial}.mp4")
        subprocess.run(
            f"ffmpeg -y -i {left} -i {right} -vsync 2 -filter_complex hstack {mp4_path / 'fused.mp4'!s}",
            shell=True,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    return True, record_paths
