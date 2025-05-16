import time
from collections import defaultdict
from copy import deepcopy
import tempfile


import cv2
import numpy as np
from PIL import Image

from droid.camera_utils.camera_readers.zed_camera import gather_zed_cameras, ZedCamera
from droid.calibration.calibration_utils import ThirdPersonCameraCalibrator
import pyzed.sl as sl
import tyro
from dataclasses import dataclass


@dataclass
class Args:
    file: str
    camera_id: str = "23404442"

if __name__ == "__main__":
    args = tyro.cli(Args)
    camera_id = args.camera_id
    file = args.file

    # initialize camera of interest
    cameras = sl.Camera.get_device_list()
    camera = None
    for cam in cameras:
        if cam.serial_number == int(camera_id):
            print(f"Found camera {camera_id}")
            camera = ZedCamera(cam)
            break
    camera.set_calibration_mode()
    intrinsics = camera.get_intrinsics()
    calibrator = ThirdPersonCameraCalibrator(intrinsics_dict=intrinsics)
    calibrator._curr_cam_id = camera_id + "_left"


    if file:
        frames = np.load(file, allow_pickle=True)
        for frame in frames:
            calibrator.add_sample(camera_id + "_left", frame, pose=None)

        data = {
            "image": frames,
            "intrinsics": intrinsics,
        }
        np.save("charuco_frames.npy", data)
    else:
        # Sample at 5 Hz
        sample_rate = 0.2
        prev_time = time.time()
        fps = 0
        frames = []
        prev_frame_time = time.time()
        while True:
            # Calculate FPS
            curr_time = time.time()
            fps = 1/(curr_time - prev_time)
            prev_time = curr_time

            img_dict, _ = camera.read_camera()
            left_img_og = img_dict["image"][camera_id + "_left"]

            left_img = calibrator.augment_image(camera_id + "_left", left_img_og)

            # Add FPS text to image
            fps_text = f"FPS: {fps:.1f}"
            cv2.putText(left_img, fps_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            cv2.imshow("image", left_img)
            key = cv2.waitKey(1)

            if time.time() - prev_frame_time > sample_rate:
                frames.append(left_img)
                calibrator.add_sample(camera_id + "_left", left_img_og, pose=None)
                prev_frame_time = time.time()

            if key == ord("q"):
                break
        camera.disable_camera()
        cv2.destroyAllWindows()

        # Save frames to numpy

        frames_np = np.array(
            {
                "image": frames,
                "intrinsics": intrinsics,
            }
            )
        np.save("charuco_frames.npy", frames_np)

    rmats, tvecs, successes = calibrator.calculate_target_to_cam(calibrator._readings_dict[camera_id + "_left"])
    rmats, tvecs, successes = np.array(rmats), np.array(tvecs), np.array(successes)
    print(f"Detected {len(successes)} / {len(frames)} charuco boards")

