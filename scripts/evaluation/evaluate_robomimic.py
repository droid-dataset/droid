import tyro
import json
import numpy as np
import cv2
from dataclasses import dataclass
from rich.console import Console
from collections import deque
from pathlib import Path

from droid.robot_env import RobotEnv
from droid.trajectory_utils.misc import collect_trajectory
import robomimic.utils.file_utils as FileUtils


@dataclass
class Args:
    checkpoint: str 

class RobomimicPolicyWrapper:
    def __init__(self, policy, cfg):
        self.policy = policy
        self.cfg = cfg
        self.policy.start_episode()

        self.buffer = deque(maxlen=cfg["algo"]["horizon"]["observation_horizon"])

    def forward(self, obs):
        simple_obs = {}
        valid_state_keys = ["joint_positions", "joint_velocities", "cartesian_position", "gripper_position"]
        for k,v in obs["robot_state"].items():
            if k in valid_state_keys:
                simple_obs[k] = np.array(v).reshape(-1)
        # get ims
        for k,v in obs["image"].items():
            simple_obs[k] = cv2.resize(np.array(v)[..., :3], (224,224))

        action = self.policy(ob=simple_obs)
        print(action)

        # padd gripper action
        action = np.concatenate([action, np.array([0.0])])
        return action

         

def main(args: Args):
    console = Console()

    # load policy
    console.print(f"Loading policy from checkpoint: {args.checkpoint}")
    policy, ckpt_dict = FileUtils.policy_from_checkpoint(ckpt_path=args.checkpoint, device="cuda", verbose=True)
    policy_config = json.loads(ckpt_dict["config"])
    policy = RobomimicPolicyWrapper(policy, policy_config)

    # create robot environment
    action_space = policy_config["train"]["action_key"]
    env = RobotEnv(action_space=action_space)
    console.print(f"[bold green]DROID Environment Ready![/bold green] with action space: [bold purple] {action_space} [/bold purple]")

    # rolling out
    collect_trajectory(
        env,
        policy=policy,
        reset_robot=True,
        horizon=200,
        save_filepath=f"{Path(__file__).parent / 'diffusion_replay.h5'}"
    )

    # evaluate policy
    env.close()
    

if __name__ == "__main__":
    args = tyro.cli(Args)
    main(args)