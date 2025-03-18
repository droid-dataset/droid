import h5py
import tyro
import imageio
import numpy as np
from pathlib import Path
import json
from dataclasses import dataclass
from typing import Tuple
import cv2

def process_traj(traj_path, image_res):
    '''
    Takes a single h5 trajectory in droid format and parses it into a single demo entry for robomimic
    '''
    traj = h5py.File(traj_path, 'r')
    observations = traj['observations']
    actions = traj['action']
    demo_data= {}

    # traj len
    traj_len = len(observations["robot_state"]["joint_positions"])

    # action_ds = actions[action_key][()]
    actions_ds = {}
    observation_ds = {}

    ## Actions
    for k,v in actions.items():
        if not isinstance(v, h5py.Group):
            try:
                actions_ds[k] = v[()].reshape(traj_len, -1)
            except:
                print(f"Could not reshape {k} with shape {v.shape} to {(traj_len, -1)}")


    ## Obs
    # capture states
    valid_state_keys = ["joint_positions", "joint_velocities", "cartesian_position", "gripper_position"]
    for k,v in observations["robot_state"].items():
        if k in valid_state_keys:
            observation_ds[k] = v[()].reshape(traj_len, -1)
    # get videos
    for k,v in observations["videos"].items():
        # observation_ds[k] = v[()]
        serialized_video = v[()]
        vid_reader = imageio.get_reader(serialized_video,  'mp4')
        frames = []
        for frame in vid_reader:
            frame = cv2.resize(frame, image_res)
            frames.append(frame)
        observation_ds[k] = np.array(frames)

    demo_data = {
        "num_samples": traj_len,
        "states": np.array([]),
        "actions": actions_ds,
        "rewards": np.zeros(traj_len),
        "dones": np.zeros(traj_len),
        "obs": observation_ds
    }
    return demo_data

@dataclass
class Args:
    droid_data_dir: str = "/home/r2d2/projects/real2simeval/droid_arhan/scripts/data/training1-2025-03-03-22-00-23" # directory containing h5 files
    action_key: str = "joint_position"
    image_res: Tuple[int, int] = (224,224)

if __name__ == "__main__":
    args = tyro.cli(Args)

    traj_folder = Path(args.droid_data_dir)
    if not traj_folder.exists():
        raise ValueError(f"Trajectory folder {traj_folder} does not exist")
    traj_files = list(traj_folder.glob("*.h5"))
    if len(traj_files) == 0:
        raise ValueError(f"No h5 files found in {traj_folder}")

    robomimic_dataset = h5py.File(traj_folder / f"droid_dataset.robomimic_ds", "w")
    data_group = robomimic_dataset.create_group("data")

    total_state_action_pairs = 0
    for i, traj_file in enumerate(traj_files):
        print(f"Processing {traj_file}")
        # traj_data = process_traj(traj_file, action_key=args.action_key)
        traj_data = process_traj(traj_file, image_res=args.image_res)

        total_state_action_pairs += traj_data["num_samples"]

        demo_group = data_group.create_group(f"demo_{i}")

        demo_group.attrs["num_samples"] = traj_data["num_samples"]
        demo_group.create_dataset("states", data=traj_data["states"])
        demo_group.create_dataset("rewards", data=traj_data["rewards"])
        demo_group.create_dataset("dones", data=traj_data["dones"])
        obs_group = demo_group.create_group("obs")
        for k,v in traj_data["obs"].items():
            obs_group.create_dataset(k, data=v)

        # demo_group.create_dataset("actions", data=traj_data["actions"])
        action_group = demo_group.create_group("actions")
        for k,v in traj_data["actions"].items():
            action_group.create_dataset(k, data=v)

    env_args = {
        "env_name": "DROID",
        "env_kwargs": {},
        "type": 2
    }
    data_group.attrs["total"] = total_state_action_pairs
    data_group.attrs["env_args"] = json.dumps(env_args)


    robomimic_dataset.close()
