import os
from collections import defaultdict

import h5py
import numpy as np

from droid.plotting.misc import *
from droid.plotting.text import *

# Create Empty Objects #
user_progress_dict = defaultdict(lambda: 0)
weekly_progress_dict = defaultdict(lambda: 0)
traj_progress_dict = defaultdict(lambda: np.array([0 for i in range(NUM_DAYS)]))
task_distribution_dict = defaultdict(lambda: 0)
scene_progress_dict = defaultdict(lambda: np.array([0 for i in range(NUM_DAYS)]))
all_camera_poses = []
all_traj_lengths = []
all_traj_ids = set()
all_scene_ids = set()


# Define Analysis Function #
def analysis_func(hdf5_filepath, hdf5_file=None):
    if hdf5_file is None:
        hdf5_file = h5py.File(hdf5_filepath, "r")

    traj_horizon = hdf5_file["action"]["joint_position"].shape[0]
    file_timestamp = os.path.getmtime(hdf5_filepath)
    day_index = get_bucket_index(file_timestamp)
    orig_user = hdf5_file.attrs["user"]
    user = clean_user.get(orig_user, orig_user)
    scene_id = hdf5_file.attrs.get("scene_id", 0)
    is_new_scene = hdf5_file.attrs.get("scene_id", 0) not in all_scene_ids
    traj_id = user + hdf5_file.attrs["time"]
    is_old_traj = traj_id in all_traj_ids
    curr_task = hdf5_file.attrs["current_task"]
    camera_poses = grab_3rd_person_extrinsics(
        hdf5_file["observation"]["camera_extrinsics"], hdf5_file["observation"]["camera_type"]
    )

    if is_old_traj:
        return
    else:
        all_traj_ids.add(traj_id)
    if user not in user_to_lab:
        print("Relevant Filepath: " + hdf5_filepath)
        print("WARNING: {0} not assigned to lab! To fix this permenantly, update the user dictionary.".format(user))
        user_to_lab[user] = input("Enter the lab for {0}:\n".format(user))

    # Update Total Progress #
    lab = user_to_lab.get(user, user)
    traj_progress_dict[lab][day_index] += 1

    # Update User Progress #
    user_progress_dict[user] += traj_horizon

    # Update Scene Progress #
    if is_new_scene:
        scene_progress_dict[lab][day_index] += 1
        all_scene_ids.add(scene_id)

    # Update Weekly Progress #
    if (file_timestamp >= WEEK_START) and (file_timestamp <= WEEK_END):
        weekly_progress_dict[lab] += traj_horizon

    # Update Task Distribution #
    task_label = task_mapper(curr_task)
    task_distribution_dict[task_label] += 1

    # Update Trajectory Length Distribution #
    all_traj_lengths.append(traj_horizon)

    # Update Camera Distribution #
    all_camera_poses.extend(camera_poses)
