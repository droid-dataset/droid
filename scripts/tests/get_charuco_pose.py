import time
from collections import defaultdict
from copy import deepcopy
import tempfile


import cv2
import numpy as np
from PIL import Image

from droid.robot_env import RobotEnv
from droid.controllers.oculus_controller import VRPolicy
from droid.calibration.calibration_utils import *
from droid.camera_utils.info import camera_type_to_string_dict
from droid.camera_utils.wrappers.recorded_multi_camera_wrapper import RecordedMultiCameraWrapper
from droid.misc.parameters import *
from droid.misc.time import time_ms
from droid.misc.transformations import change_pose_frame
from droid.trajectory_utils.trajectory_reader import TrajectoryReader
from droid.trajectory_utils.trajectory_writer import TrajectoryWriter



def calibrate_camera(
    env,
    camera_id,
    controller,
    step_size=0.01,
    pause_time=0.5,
    image_freq=10,
    obs_pointer=None,
    wait_for_controller=False,
    reset_robot=True,
):
    """Returns true if calibration was successful, otherwise returns False
    3rd Person Calibration Instructions: Press A when board in aligned with the camera from 1 foot away.
    Hand Calibration Instructions: Press A when the hand camera is aligned with the board from 1 foot away."""

    if obs_pointer is not None:
        assert isinstance(obs_pointer, dict)

    # Get Camera + Set Calibration Mode #
    camera = env.camera_reader.get_camera(camera_id)
    env.camera_reader.set_calibration_mode(camera_id)
    assert pause_time > (camera.latency / 1000)

    # Select Proper Calibration Procedure #
    hand_camera = camera.serial_number == hand_camera_id
    intrinsics_dict = camera.get_intrinsics()
    if hand_camera:
        calibrator = HandCameraCalibrator(intrinsics_dict)
    else:
        calibrator = ThirdPersonCameraCalibrator(intrinsics_dict)

    if reset_robot:
        env.reset()
    controller.reset_state()

    while True:
        # Collect Controller Info #
        controller_info = controller.get_info()
        start_time = time.time()

        # Get Observation #
        state, _ = env.get_state()
        cam_obs, _ = env.read_cameras()

        for full_cam_id in cam_obs["image"]:
            if camera_id not in full_cam_id:
                continue
            cam_obs["image"][full_cam_id] = calibrator.augment_image(full_cam_id, cam_obs["image"][full_cam_id])
            if full_cam_id == f"{camera_id}_left":
                cv2.imshow("image", cam_obs["image"][f"{full_cam_id}"])
                cv2.waitKey(1)
        if obs_pointer is not None:
            obs_pointer.update(cam_obs)

        # Get Action #
        action = controller.forward({"robot_state": state})
        action[-1] = 0  # Keep gripper open

        # Regularize Control Frequency #
        comp_time = time.time() - start_time
        sleep_left = (1 / env.control_hz) - comp_time
        if sleep_left > 0:
            time.sleep(sleep_left)

        # Step Environment #
        skip_step = wait_for_controller and (not controller_info["movement_enabled"])
        if not skip_step:
            env.step(action)

        # Check Termination #
        start_calibration = controller_info["success"]
        end_calibration = controller_info["failure"]

        # Close Files And Return #
        if start_calibration:
            break
        if end_calibration:
            return False

    # Collect Data #
    time.time()
    pose_origin = state["cartesian_position"]
    i = 0

    while True:
        # Check For Termination #
        controller_info = controller.get_info()
        if controller_info["failure"]:
            return False

        # Start #
        start_time = time.time()
        take_picture = (i % image_freq) == 0

        # Collect Observations #
        if take_picture:
            time.sleep(pause_time)
        state, _ = env.get_state()
        cam_obs, _ = env.read_cameras()

        # Add Sample + Augment Images #
        for full_cam_id in cam_obs["image"]:
            if camera_id not in full_cam_id:
                continue
            if take_picture:
                img = deepcopy(cam_obs["image"][full_cam_id])
                pose = state["cartesian_position"].copy()
                calibrator.add_sample(full_cam_id, img, pose)
            cam_obs["image"][full_cam_id] = calibrator.augment_image(full_cam_id, cam_obs["image"][full_cam_id])
            if full_cam_id == f"{camera_id}_left":
                cv2.imshow("image", cam_obs["image"][full_cam_id])
                cv2.waitKey(1)
        

        # Update Obs Pointer #
        if obs_pointer is not None:
            obs_pointer.update(cam_obs)

        # Move To Desired Next Pose #
        calib_pose = calibration_traj(i * step_size, hand_camera=hand_camera)
        desired_pose = change_pose_frame(calib_pose, pose_origin)
        action = np.concatenate([desired_pose, [0]])
        env.update_robot(action, action_space="cartesian_position", blocking=False)

        # Regularize Control Frequency #
        comp_time = time.time() - start_time
        sleep_left = (1 / env.control_hz) - comp_time
        if sleep_left > 0:
            time.sleep(sleep_left)

        # Check If Cycle Complete #
        cycle_complete = (i * step_size) >= (2 * np.pi)
        if cycle_complete:
            break
        i += 1

    # SAVE INTO A JSON
    for full_cam_id in cam_obs["image"]:
        if camera_id not in full_cam_id:
            continue
        success = calibrator.is_calibration_accurate(full_cam_id)
        if not success:
            return False
        transformation = calibrator.calibrate(full_cam_id)
        # update_calibration_info(full_cam_id, transformation)
        print("Successfully calibrated camera: ", full_cam_id)

    return calibrator




if __name__ == "__main__":
    env = RobotEnv()
    controller = VRPolicy()
    camera_id = "18650758"

    calibrator = calibrate_camera(env, camera_id, controller)

    # get readings and poses
    camera_id = f"{camera_id}_left"
    readings = calibrator._readings_dict[camera_id]
    assert len(readings) != 0
    poses = np.array(calibrator._pose_dict[camera_id])

    # Get Target2Cam Transformations
    target2cam_results = calibrator.calculate_target_to_cam(readings, train=False)
    if target2cam_results is None:
        print("No target2cam results found")
        exit()
    eval_R_target2cam, eval_t_target2cam, eval_successes = target2cam_results

    # Base 2 Target
    base2target = calibrator._calibrate_base_to_target(gripper_poses=poses, target2cam_results=target2cam_results)
    R_base2target = R.from_euler("xyz", base2target[3:]).as_matrix()
    t_base2target = np.array(base2target[:3])

    print(f"R_base2target: {R_base2target}")
    print(f"t_base2target: {t_base2target}")

    transform = {
        "R": R_base2target,
        "t": t_base2target
    }
    np.save("base2target.npy", transform)


    


    