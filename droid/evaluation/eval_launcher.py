import json
import os

import numpy as np
import torch

from droid.controllers.oculus_controller import VRPolicy
from droid.evaluation.policy_wrapper import PolicyWrapper
from droid.robot_env import RobotEnv
from droid.user_interface.data_collector import DataCollecter
from droid.user_interface.gui import RobotGUI


def eval_launcher(variant, run_id, exp_id):
    # Get Directory #
    dir_path = os.path.dirname(os.path.realpath(__file__))

    # Prepare Log Directory #
    variant["exp_name"] = os.path.join(variant["exp_name"], "run{0}/id{1}/".format(run_id, exp_id))
    log_dir = os.path.join(dir_path, "../../evaluation_logs", variant["exp_name"])

    # Set Random Seeds #
    torch.manual_seed(variant["seed"])
    np.random.seed(variant["seed"])

    # Set Compute Mode #
    use_gpu = variant.get("use_gpu", False)
    torch.device("cuda:0" if use_gpu else "cpu")

    # Load Model + Variant #
    policy_logdir = os.path.join(dir_path, "../../training_logs", variant["policy_logdir"])
    policy_filepath = os.path.join(policy_logdir, "models", "{0}.pt".format(variant["model_id"]))
    policy = torch.load(policy_filepath)

    variant_filepath = os.path.join(policy_logdir, "variant.json")
    with open(variant_filepath, "r") as jsonFile:
        policy_variant = json.load(jsonFile)

    # Prepare Policy Wrapper #
    data_processing_kwargs = variant.get("data_processing_kwargs", {})
    timestep_filtering_kwargs = data_processing_kwargs.get("timestep_filtering_kwargs", {})
    image_transform_kwargs = data_processing_kwargs.get("image_transform_kwargs", {})

    policy_data_processing_kwargs = policy_variant.get("data_processing_kwargs", {})
    policy_timestep_filtering_kwargs = policy_data_processing_kwargs.get("timestep_filtering_kwargs", {})
    policy_image_transform_kwargs = policy_data_processing_kwargs.get("image_transform_kwargs", {})

    policy_timestep_filtering_kwargs.update(timestep_filtering_kwargs)
    policy_image_transform_kwargs.update(image_transform_kwargs)

    wrapped_policy = PolicyWrapper(
        policy=policy,
        timestep_filtering_kwargs=policy_timestep_filtering_kwargs,
        image_transform_kwargs=policy_image_transform_kwargs,
        eval_mode=True,
    )

    # Prepare Environment #
    policy_action_space = policy_timestep_filtering_kwargs["action_space"]

    camera_kwargs = variant.get("camera_kwargs", {})
    policy_camera_kwargs = policy_variant.get("camera_kwargs", {})
    policy_camera_kwargs.update(camera_kwargs)

    env = RobotEnv(action_space=policy_action_space, camera_kwargs=policy_camera_kwargs)
    controller = VRPolicy()

    # Launch GUI #
    data_collector = DataCollecter(
        env=env,
        controller=controller,
        policy=wrapped_policy,
        save_traj_dir=log_dir,
        save_data=variant.get("save_data", True),
    )
    RobotGUI(robot=data_collector)
