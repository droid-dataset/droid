from collections import defaultdict
from copy import deepcopy
from itertools import chain

import numpy as np

from droid.camera_utils.info import camera_type_to_string_dict
from droid.data_processing.data_transforms import ImageTransformer


class TimestepProcesser:
    def __init__(
        self,
        ignore_action=False,
        action_space="cartesian_velocity",
        gripper_action_space=None,
        robot_state_keys=["cartesian_position", "gripper_position", "joint_positions", "joint_velocities"],
        camera_extrinsics=["hand_camera", "varied_camera", "fixed_camera"],
        state_dtype=np.float32,
        action_dtype=np.float32,
        image_transform_kwargs={},
    ):
        assert action_space in ["cartesian_position", "joint_position", "cartesian_velocity", "joint_velocity"]

        self.action_space = action_space
        self.gripper_key = "gripper_velocity" if "velocity" in gripper_action_space else "gripper_position"
        self.ignore_action = ignore_action

        self.robot_state_keys = robot_state_keys
        self.camera_extrinsics = camera_extrinsics

        self.state_dtype = state_dtype
        self.action_dtype = action_dtype

        self.image_transformer = ImageTransformer(**image_transform_kwargs)

    def forward(self, timestep):
        # Make Deep Copy #
        timestep = deepcopy(timestep)

        # Get Relevant Camera Info #
        camera_type_dict = {k: camera_type_to_string_dict[v] for k, v in timestep["observation"]["camera_type"].items()}
        sorted_camera_ids = sorted(camera_type_dict.keys())

        ### Get Robot State Info ###
        sorted_state_keys = sorted(self.robot_state_keys)
        full_robot_state = timestep["observation"]["robot_state"]
        robot_state = [np.array(full_robot_state[key]).flatten() for key in sorted_state_keys]
        if len(robot_state):
            robot_state = np.concatenate(robot_state)

        ### Get Extrinsics ###
        calibration_dict = timestep["observation"]["camera_extrinsics"]
        sorted_calibrated_ids = sorted(calibration_dict.keys())
        extrinsics_dict = defaultdict(list)

        for serial_number in sorted_camera_ids:
            cam_type = camera_type_dict[serial_number]
            if cam_type not in self.camera_extrinsics:
                continue

            for full_cam_id in sorted_calibrated_ids:
                if serial_number in full_cam_id:
                    cam2base = calibration_dict[full_cam_id]
                    extrinsics_dict[cam_type].append(cam2base)

        sorted_extrinsics_keys = sorted(extrinsics_dict.keys())
        extrinsics_state = list(chain(*[extrinsics_dict[cam_type] for cam_type in sorted_extrinsics_keys]))
        if len(extrinsics_state):
            extrinsics_state = np.concatenate(extrinsics_state)

        ### Get Intrinsics ###
        cam_intrinsics_obs = timestep["observation"]["camera_intrinsics"]
        sorted_calibrated_ids = sorted(calibration_dict.keys())
        intrinsics_dict = defaultdict(list)

        for serial_number in sorted_camera_ids:
            cam_type = camera_type_dict[serial_number]
            if cam_type not in self.camera_extrinsics:
                continue

            full_cam_ids = sorted(cam_intrinsics_obs.keys())
            for full_cam_id in full_cam_ids:
                if serial_number in full_cam_id:
                    intr = cam_intrinsics_obs[full_cam_id]
                    intrinsics_dict[cam_type].append(intr)

        sorted_intrinsics_keys = sorted(intrinsics_dict.keys())
        intrinsics_state = list([np.array(intrinsics_dict[cam_type]).flatten() for cam_type in sorted_intrinsics_keys])
        if len(intrinsics_state):
            intrinsics_state = np.concatenate(intrinsics_state)

        ### Get High Dimensional State Info ###
        high_dim_state_dict = defaultdict(lambda: defaultdict(list))

        for obs_type in ["image", "depth", "pointcloud"]:
            obs_type_dict = timestep["observation"].get(obs_type, {})
            sorted_obs_ids = sorted(obs_type_dict.keys())

            for serial_number in sorted_camera_ids:
                cam_type = camera_type_dict[serial_number]

                for full_obs_id in sorted_obs_ids:
                    if serial_number in full_obs_id:
                        data = obs_type_dict[full_obs_id]
                        high_dim_state_dict[obs_type][cam_type].append(data)

        ### Finish Observation Portion ###
        low_level_state = np.concatenate([robot_state, extrinsics_state, intrinsics_state], dtype=self.state_dtype)
        processed_timestep = {"observation": {"state": low_level_state, "camera": high_dim_state_dict}}
        self.image_transformer.forward(processed_timestep)

        ### Add Proper Action ###
        if not self.ignore_action:
            arm_action = timestep["action"][self.action_space]
            gripper_action = timestep["action"][self.gripper_key]
            action = np.concatenate([arm_action, [gripper_action]], dtype=self.action_dtype)
            processed_timestep["action"] = action

        # return raw information + meta data
        processed_timestep["extrinsics_dict"] = extrinsics_dict
        processed_timestep["intrinsics_dict"] = intrinsics_dict

        return processed_timestep
