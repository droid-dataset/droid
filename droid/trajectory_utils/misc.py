import time
from collections import defaultdict
from copy import deepcopy
import os

import cv2
import numpy as np
from PIL import Image

from droid.calibration.calibration_utils import *
from droid.camera_utils.info import camera_type_to_string_dict
from droid.camera_utils.wrappers.recorded_multi_camera_wrapper import RecordedMultiCameraWrapper
from droid.misc.parameters import *
from droid.misc.time import time_ms
from droid.misc.transformations import change_pose_frame
from droid.trajectory_utils.trajectory_reader import TrajectoryReader
from droid.trajectory_utils.trajectory_writer import TrajectoryWriter
from droid.trajectory_utils.trajectory_reader_mcap import TrajectoryReaderMCAP
from droid.trajectory_utils.trajectory_writer_mcap import TrajectoryWriterMCAP


def collect_trajectory(
    env,
    controller,
    save_filepath=None,
    recording_folderpath=None,
    metadata=None,
    reset_robot=True,
    policy=None,
    controller_type="ControllerInterface",
    obs_pointer=None,
    wait_for_controller=False,
    step_wait_time=None,
    use_mcap=True,
):
    """Collect a trajectory and store the data"""

    if obs_pointer is not None:
        assert isinstance(obs_pointer, dict)

    # Reset Robot #
    if reset_robot:
        env.reset()
    controller.reset_state()

    # Open TrajectorWriter #
    assert save_filepath is not None
    if use_mcap:
        from droid.trajectory_utils.trajectory_writer_mcap import TrajectoryWriterMCAP
        writer = TrajectoryWriterMCAP(save_filepath, metadata=metadata, save_images=True)
    else:
        writer = TrajectoryWriter(save_filepath, metadata=metadata, save_images=True)

    # Start camera and microphone recording
    if recording_folderpath is not None:
        env.camera_reader.start_recording(recording_folderpath)
    
    # Start microphone recording if available
    if hasattr(env, 'start_microphone_recording'):
        env.start_microphone_recording()

    # Save Metadata #
    metadata = metadata or {}
    metadata["controller_type"] = controller_type

    timestep = 0
    try:
        while True:
            start_time = time.time()

            # Get Observation #
            obs = env.get_observation()
            if obs_pointer is not None:
                obs_pointer.update(obs)

            # Get Action From Controller#
            controller_info = controller.get_info()
            action = controller.forward(obs)
            
            # Add VR controller data to observation
            obs["controller_info"] = controller_info

            # Check For Early Termination #
            if controller_info["success"] or controller_info["failure"]:
                break

            # Save Trajectory #
            timestep_data = {"observation": obs, "action": action}
            writer.write_timestep(timestep_data)

            # Take Environment Action #
            skip_step = wait_for_controller and (not controller_info["movement_enabled"])
            if not skip_step:
                env.step(action)

            # Regulate Control Rate #
            if step_wait_time is not None:
                time.sleep(step_wait_time)
            else:
                comp_time = time.time() - start_time
                sleep_left = (1 / env.control_hz) - comp_time
                if sleep_left > 0:
                    time.sleep(sleep_left)

            timestep += 1

    except KeyboardInterrupt:
        controller_info = {"success": False, "failure": True}

    # Stop recording
    if recording_folderpath is not None:
        env.camera_reader.stop_recording()
    
    # Stop microphone recording if available
    if hasattr(env, 'stop_microphone_recording'):
        env.stop_microphone_recording()

    # Save To HDF5 File #
    metadata.update(controller_info)
    metadata["timesteps"] = timestep
    metadata["success"] = controller_info["success"]
    writer.close(metadata=metadata)

    return controller_info


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
        update_calibration_info(full_cam_id, transformation)

    return True


def replay_trajectory(
    env, filepath=None, assert_replayable_keys=["cartesian_position", "gripper_position", "joint_positions"]
):
    print("WARNING: STATE 'CLOSENESS' FOR REPLAYABILITY HAS NOT BEEN CALIBRATED")
    gripper_key = "gripper_velocity" if "velocity" in env.action_space else "gripper_position"

    # Prepare Trajectory Reader #
    traj_reader = TrajectoryReader(filepath, read_images=False)
    horizon = traj_reader.length()

    for i in range(horizon):
        # Get HDF5 Data #
        timestep = traj_reader.read_timestep()

        # Move To Initial Position #
        if i == 0:
            init_joint_position = timestep["observation"]["robot_state"]["joint_positions"]
            init_gripper_position = timestep["observation"]["robot_state"]["gripper_position"]
            action = np.concatenate([init_joint_position, [init_gripper_position]])
            env.update_robot(action, action_space="joint_position", blocking=True)

        # TODO: Assert Replayability #
        # robot_state = env.get_state()[0]
        # for key in assert_replayable_keys:
        # 	desired = timestep['observation']['robot_state'][key]
        # 	current = robot_state[key]
        # 	assert np.allclose(desired, current)

        # Regularize Control Frequency #
        time.sleep(1 / env.control_hz)

        # Get Action In Desired Action Space #
        arm_action = timestep["action"][env.action_space]
        gripper_action = timestep["action"][gripper_key]
        action = np.concatenate([arm_action, [gripper_action]])
        controller_info = timestep["observation"]["controller_info"]
        movement_enabled = controller_info.get("movement_enabled", True)

        # Follow Trajectory #
        if movement_enabled:
            env.step(action)


def load_trajectory(
    filepath=None,
    read_cameras=True,
    recording_folderpath=None,
    camera_kwargs={},
    remove_skipped_steps=False,
    num_samples_per_traj=None,
    num_samples_per_traj_coeff=1.5,
    use_mcap=True,
):
    read_hdf5_images = read_cameras and (recording_folderpath is None)
    read_recording_folderpath = read_cameras and (recording_folderpath is not None)

    # Check file extension to determine format
    _, ext = os.path.splitext(filepath)
    is_mcap = ext.lower() == '.mcap'
    
    # Use the appropriate reader based on format
    if is_mcap and use_mcap:
        traj_reader = TrajectoryReaderMCAP(filepath, read_images=read_hdf5_images)
    else:
        traj_reader = TrajectoryReader(filepath, read_images=read_hdf5_images)
        
    if read_recording_folderpath:
        camera_reader = RecordedMultiCameraWrapper(recording_folderpath, camera_kwargs)

    horizon = traj_reader.length()
    timestep_list = []

    # Choose Timesteps To Save #
    if num_samples_per_traj:
        num_to_save = num_samples_per_traj
        if remove_skipped_steps:
            num_to_save = int(num_to_save * num_samples_per_traj_coeff)
        max_size = min(num_to_save, horizon)
        indices_to_save = np.sort(np.random.choice(horizon, size=max_size, replace=False))
    else:
        indices_to_save = np.arange(horizon)

    # Iterate Over Trajectory #
    for i in indices_to_save:
        # Get Data #
        timestep = traj_reader.read_timestep(index=i)

        # If Applicable, Get Recorded Data #
        if read_recording_folderpath:
            timestamp_dict = timestep["observation"]["timestamp"]["cameras"]
            camera_type_dict = {
                k: camera_type_to_string_dict[v] for k, v in timestep["observation"]["camera_type"].items()
            }
            camera_obs = camera_reader.read_cameras(
                index=i, camera_type_dict=camera_type_dict, timestamp_dict=timestamp_dict
            )
            camera_failed = camera_obs is None

            # Add Data To Timestep If Successful #
            if camera_failed:
                break
            else:
                timestep["observation"].update(camera_obs)

        # Filter Steps #
        step_skipped = not timestep["observation"]["controller_info"].get("movement_enabled", True)
        delete_skipped_step = step_skipped and remove_skipped_steps

        # Save Filtered Timesteps #
        if delete_skipped_step:
            del timestep
        else:
            timestep_list.append(timestep)

    # Remove Extra Transitions #
    timestep_list = np.array(timestep_list)
    if (num_samples_per_traj is not None) and (len(timestep_list) > num_samples_per_traj):
        ind_to_keep = np.random.choice(len(timestep_list), size=num_samples_per_traj, replace=False)
        timestep_list = timestep_list[ind_to_keep]

    # Close Readers #
    traj_reader.close()
    if read_recording_folderpath:
        camera_reader.disable_cameras()

    # Return Data #
    return timestep_list


def visualize_timestep(timestep, max_width=1000, max_height=500, aspect_ratio=1.5, pause_time=15):
    # Process Image Data #
    obs = timestep["observation"]
    if "image" in obs:
        img_obs = obs["image"]
    elif "image" in obs["camera"]:
        img_obs = obs["camera"]["image"]
    else:
        raise ValueError

    camera_ids = sorted(img_obs.keys())
    sorted_image_list = []
    for cam_id in camera_ids:
        data = img_obs[cam_id]
        if type(data) == list:
            sorted_image_list.extend(data)
        else:
            sorted_image_list.append(data)

    # Get Ideal Number Of Rows #
    num_images = len(sorted_image_list)
    max_num_rows = int(num_images**0.5)
    for num_rows in range(max_num_rows, 0, -1):
        num_cols = num_images // num_rows
        if num_images % num_rows == 0:
            break

    # Get Per Image Shape #
    max_img_width, max_img_height = max_width // num_cols, max_height // num_rows
    if max_img_width > aspect_ratio * max_img_height:
        img_width, img_height = max_img_width, int(max_img_width / aspect_ratio)
    else:
        img_width, img_height = int(max_img_height * aspect_ratio), max_img_height

    # Fill Out Image Grid #
    img_grid = [[] for i in range(num_rows)]

    for i in range(len(sorted_image_list)):
        img = Image.fromarray(sorted_image_list[i])
        resized_img = img.resize((img_width, img_height), Image.Resampling.LANCZOS)
        img_grid[i % num_rows].append(np.array(resized_img))

    # Combine Images #
    for i in range(num_rows):
        img_grid[i] = np.hstack(img_grid[i])
    img_grid = np.vstack(img_grid)

    # Visualize Frame #
    cv2.imshow("Image Feed", img_grid)
    cv2.waitKey(pause_time)


def visualize_trajectory(
    filepath,
    recording_folderpath=None,
    remove_skipped_steps=False,
    camera_kwargs={},
    max_width=1000,
    max_height=500,
    aspect_ratio=1.5,
):
    traj_reader = TrajectoryReader(filepath, read_images=True)
    if recording_folderpath:
        if camera_kwargs is {}:
            camera_kwargs = defaultdict(lambda: {"image": True})
        camera_reader = RecordedMultiCameraWrapper(recording_folderpath, camera_kwargs)

    horizon = traj_reader.length()
    camera_failed = False

    for i in range(horizon):
        # Get HDF5 Data #
        timestep = traj_reader.read_timestep()

        # If Applicable, Get Recorded Data #
        if recording_folderpath:
            timestamp_dict = timestep["observation"]["timestamp"]["cameras"]
            camera_type_dict = {
                k: camera_type_to_string_dict[v] for k, v in timestep["observation"]["camera_type"].items()
            }
            camera_obs = camera_reader.read_cameras(
                index=i, camera_type_dict=camera_type_dict, timestamp_dict=timestamp_dict
            )
            camera_failed = camera_obs is None

            # Add Data To Timestep #
            if not camera_failed:
                timestep["observation"].update(camera_obs)

        # Filter Steps #
        step_skipped = not timestep["observation"]["controller_info"].get("movement_enabled", True)
        delete_skipped_step = step_skipped and remove_skipped_steps
        delete_step = delete_skipped_step or camera_failed
        if delete_step:
            continue

        # Get Image Info #
        assert "image" in timestep["observation"]
        img_obs = timestep["observation"]["image"]
        camera_ids = list(img_obs.keys())
        len(camera_ids)
        camera_ids.sort()

        # Visualize Timestep #
        visualize_timestep(
            timestep, max_width=max_width, max_height=max_height, aspect_ratio=aspect_ratio, pause_time=15
        )

    # Close Readers #
    traj_reader.close()
    if recording_folderpath:
        camera_reader.disable_cameras()
