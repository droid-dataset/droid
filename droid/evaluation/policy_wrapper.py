import numpy as np
import torch
from collections import deque

from droid.data_processing.timestep_processing import TimestepProcesser
import robomimic.utils.torch_utils as TorchUtils
import robomimic.utils.tensor_utils as TensorUtils


def converter_helper(data, batchify=True):
    if torch.is_tensor(data):
        pass
    elif isinstance(data, np.ndarray):
        data = torch.from_numpy(data)
    else:
        raise ValueError

    if batchify:
        data = data.unsqueeze(0)
    return data


def np_dict_to_torch_dict(np_dict, batchify=True):
    torch_dict = {}

    for key in np_dict:
        curr_data = np_dict[key]
        if isinstance(curr_data, dict):
            torch_dict[key] = np_dict_to_torch_dict(curr_data)
        elif isinstance(curr_data, np.ndarray) or torch.is_tensor(curr_data):
            torch_dict[key] = converter_helper(curr_data, batchify=batchify)
        elif isinstance(curr_data, list):
            torch_dict[key] = [converter_helper(d, batchify=batchify) for d in curr_data]
        else:
            raise ValueError

    return torch_dict


class PolicyWrapper:
    def __init__(self, policy, timestep_filtering_kwargs, image_transform_kwargs, eval_mode=True):
        self.policy = policy

        if eval_mode:
            self.policy.eval()
        else:
            self.policy.train()

        self.timestep_processor = TimestepProcesser(
            ignore_action=True, **timestep_filtering_kwargs, image_transform_kwargs=image_transform_kwargs
        )

    def forward(self, observation):
        timestep = {"observation": observation}
        processed_timestep = self.timestep_processor.forward(timestep)
        torch_timestep = np_dict_to_torch_dict(processed_timestep)
        action = self.policy(torch_timestep)[0]
        np_action = action.detach().numpy()

        # a_star = np.cumsum(processed_timestep['observation']['state']) / 7
        # print('Policy Action: ', np_action)
        # print('Expert Action: ', a_star)
        # print('Error: ', np.abs(a_star - np_action).mean())

        # import pdb; pdb.set_trace()
        return np_action


class PolicyWrapperRobomimic:
    def __init__(self, policy, timestep_filtering_kwargs, image_transform_kwargs, frame_stack, eval_mode=True):
        self.policy = policy

        assert eval_mode is True

        self.fs_wrapper = FrameStackWrapper(num_frames=frame_stack)
        self.fs_wrapper.reset()
        self.policy.start_episode()

        self.timestep_processor = TimestepProcesser(
            ignore_action=True, **timestep_filtering_kwargs, image_transform_kwargs=image_transform_kwargs
        )

    def convert_raw_extrinsics_to_Twc(self, raw_data):
        """
        helper function that convert raw extrinsics (6d pose) to transformation matrix (Twc)
        """
        raw_data = torch.from_numpy(np.array(raw_data))
        pos = raw_data[0:3]
        rot_mat = TorchUtils.euler_angles_to_matrix(raw_data[3:6], convention="XYZ")
        extrinsics = np.zeros((4, 4))
        extrinsics[:3,:3] = TensorUtils.to_numpy(rot_mat)
        extrinsics[:3,3] = TensorUtils.to_numpy(pos)
        extrinsics[3,3] = 1.0
        # invert the matrix to represent standard definition of extrinsics: from world to cam
        extrinsics = np.linalg.inv(extrinsics)
        return extrinsics

    def forward(self, observation):
        timestep = {"observation": observation}
        processed_timestep = self.timestep_processor.forward(timestep)

        extrinsics_dict = processed_timestep["extrinsics_dict"]
        intrinsics_dict = processed_timestep["intrinsics_dict"]
        # import pdb; pdb.set_trace()

        obs = {
            "robot_state/cartesian_position": observation["robot_state"]["cartesian_position"],
            "robot_state/gripper_position": [observation["robot_state"]["gripper_position"]], # wrap as array, raw data is single float
            "camera/image/hand_camera_left_image": processed_timestep["observation"]["camera"]["image"]["hand_camera"][0],
            "camera/image/hand_camera_right_image": processed_timestep["observation"]["camera"]["image"]["hand_camera"][1],
            "camera/image/varied_camera_1_left_image": processed_timestep["observation"]["camera"]["image"]["varied_camera"][0],
            "camera/image/varied_camera_1_right_image": processed_timestep["observation"]["camera"]["image"]["varied_camera"][1],
            "camera/image/varied_camera_2_left_image": processed_timestep["observation"]["camera"]["image"]["varied_camera"][2],
            "camera/image/varied_camera_2_right_image": processed_timestep["observation"]["camera"]["image"]["varied_camera"][3],

            "camera/extrinsics/hand_camera_left": self.convert_raw_extrinsics_to_Twc(extrinsics_dict["hand_camera"][0]),
            "camera/extrinsics/hand_camera_right": self.convert_raw_extrinsics_to_Twc(extrinsics_dict["hand_camera"][2]),
            "camera/extrinsics/varied_camera_1_left": self.convert_raw_extrinsics_to_Twc(extrinsics_dict["varied_camera"][0]),
            "camera/extrinsics/varied_camera_1_right": self.convert_raw_extrinsics_to_Twc(extrinsics_dict["varied_camera"][1]),
            "camera/extrinsics/varied_camera_2_left": self.convert_raw_extrinsics_to_Twc(extrinsics_dict["varied_camera"][2]),
            "camera/extrinsics/varied_camera_2_right": self.convert_raw_extrinsics_to_Twc(extrinsics_dict["varied_camera"][3]),

            "camera/intrinsics/hand_camera_left": intrinsics_dict["hand_camera"][0],
            "camera/intrinsics/hand_camera_right": intrinsics_dict["hand_camera"][1],
            "camera/intrinsics/varied_camera_1_left": intrinsics_dict["varied_camera"][0],
            "camera/intrinsics/varied_camera_1_right": intrinsics_dict["varied_camera"][1],
            "camera/intrinsics/varied_camera_2_left": intrinsics_dict["varied_camera"][2],
            "camera/intrinsics/varied_camera_2_right": intrinsics_dict["varied_camera"][3],
        }

        # set item of obs as np.array
        for k in obs:
            obs[k] = np.array(obs[k])
        
        self.fs_wrapper.add_obs(obs)
        obs_history = self.fs_wrapper.get_obs_history()
        action = self.policy(obs_history)

        return action

    def reset(self):
        self.fs_wrapper.reset()
        self.policy.start_episode()
    

class FrameStackWrapper:
    """
    Wrapper for frame stacking observations during rollouts. The agent
    receives a sequence of past observations instead of a single observation
    when it calls @env.reset, @env.reset_to, or @env.step in the rollout loop.
    """
    def __init__(self, num_frames):
        """
        Args:
            env (EnvBase instance): The environment to wrap.
            num_frames (int): number of past observations (including current observation)
                to stack together. Must be greater than 1 (otherwise this wrapper would
                be a no-op).
        """
        self.num_frames = num_frames

        ### TODO: add action padding option + adding action to obs to include action history in obs ###

        # keep track of last @num_frames observations for each obs key
        self.obs_history = None

    def _set_initial_obs_history(self, init_obs):
        """
        Helper method to get observation history from the initial observation, by
        repeating it.

        Returns:
            obs_history (dict): a deque for each observation key, with an extra
                leading dimension of 1 for each key (for easy concatenation later)
        """
        self.obs_history = {}
        for k in init_obs:
            self.obs_history[k] = deque(
                [init_obs[k][None] for _ in range(self.num_frames)], 
                maxlen=self.num_frames,
            )

    def reset(self):
        self.obs_history = None

    def get_obs_history(self):
        """
        Helper method to convert internal variable @self.obs_history to a 
        stacked observation where each key is a numpy array with leading dimension
        @self.num_frames.
        """
        # concatenate all frames per key so we return a numpy array per key
        if self.num_frames == 1:
            return { k : np.concatenate(self.obs_history[k], axis=0)[0] for k in self.obs_history }
        else:
            return { k : np.concatenate(self.obs_history[k], axis=0) for k in self.obs_history }

    def add_obs(self, obs):
        if self.obs_history is None:
            self._set_initial_obs_history(obs)

        # update frame history
        for k in obs:
            # make sure to have leading dim of 1 for easy concatenation
            self.obs_history[k].append(obs[k][None])
