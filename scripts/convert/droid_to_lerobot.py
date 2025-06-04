import h5py
import imageio
import numpy as np
import tempfile
import types
import torch
import tyro

from tqdm import tqdm
from pathlib import Path
from dataclasses import dataclass
from droid.trajectory_utils.trajectory_reader import TrajectoryReader
# from store_features_greencube import storage
from lerobot.common.datasets.lerobot_dataset import LeRobotDataset

@dataclass
class Args:
    data_path:str


def create_features_from_timestep(t, key_prefix="", features={}, structure_only=False):
    '''Recursively create feature structure from timestep data.'''
    if not isinstance(t, dict):
        t = torch.tensor(t) 
        if len(t.shape) == 0:
            t = t[None]
        if structure_only:
            dtype = type(t)
            names = None
            shape = (1,)
            if "image" in key_prefix:
                dtype = "video"
                names = ["height", "width", "channels"]
                shape = t.shape

            elif hasattr(t, "dtype"):
                dtype = str(t.dtype).replace("torch.", "")
                shape = t.shape 

            features[key_prefix[1:]] = {
                "dtype": dtype,
                "shape": shape,
                "names": names,
            }
        else:
            features[key_prefix[1:]] = t

        return

    for key, value in t.items():
        create_features_from_timestep(value, ".".join([key_prefix, key]), structure_only=structure_only, features=features)
    return features

if __name__ == "__main__":
    args = tyro.cli(Args)

    data_path = Path(args.data_path)

    # define dataset
    first_traj = next(data_path.glob("*.h5"))
    traj_reader = TrajectoryReader(first_traj, read_images=True)
    step = traj_reader.read_timestep()
    features = create_features_from_timestep(step, structure_only=True)
    lerobot_dataset = LeRobotDataset.create(
            repo_id=data_path.stem,
            fps=15,
            robot_type="fr3",
            features=features,
            use_videos= True,
            image_writer_processes=10,
            image_writer_threads=5,
            )
    print(lerobot_dataset)

    # populate dataset
    for file in data_path.glob("*.h5"):
        traj_reader = TrajectoryReader(file, read_images=True)
        traj_len = traj_reader.length()
        for i in tqdm(range(traj_len)):
            step = traj_reader.read_timestep()
            # Process each step as needed
            features = create_features_from_timestep(step)
            features["task"] = data_path.stem
            lerobot_dataset.add_frame(features)
        lerobot_dataset.save_episode()

    print("Finished converting Droid dataset to LeRobot format.")
