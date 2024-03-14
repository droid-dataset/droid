import json
import os
from collections import defaultdict

from droid.camera_utils.wrappers.recorded_multi_camera_wrapper import RecordedMultiCameraWrapper
from droid.training.data_loading.trajectory_sampler import collect_data_folderpaths
from droid.trajectory_utils.misc import visualize_timestep
from droid.trajectory_utils.trajectory_reader import TrajectoryReader

# Prepare Calibration Info #
dir_path = os.path.dirname(os.path.realpath(__file__))
task_label_filepath = os.path.join(dir_path, "task_label_filepath.json")


def load_task_info():
    if not os.path.isfile(task_label_filepath):
        return {}
    with open(task_label_filepath, "r") as jsonFile:
        task_labels = json.load(jsonFile)
    return task_labels


def update_task_label(folderpath, traj_id):
    task_labels = load_task_info()
    task_labels[folderpath] = traj_id

    with open(task_label_filepath, "w") as jsonFile:
        json.dump(task_labels, jsonFile)


# Classify Traj #
def label_trajectory(
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

    while True:
        for i in range(horizon):
            # Get HDF5 Data #
            timestep = traj_reader.read_timestep()

            # If Applicable, Get Recorded Data #
            if recording_folderpath:
                timestamp_dict = timestep["observation"]["timestamp"]["cameras"]
                camera_obs = camera_reader.read_cameras(timestamp_dict=timestamp_dict)
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

            # Skip #
            if (i % 10) != 0:
                continue

            # Visualize Timestep #
            visualize_timestep(
                timestep, max_width=max_width, max_height=max_height, aspect_ratio=aspect_ratio, pause_time=15
            )

            # Check Termination #
            key_pressed = input("Enter Label (Putting In: A, Taking Out: S):\n")

            if key_pressed in ["a", "s", "b"]:
                # Close Readers #
                traj_reader.close()
                if recording_folderpath:
                    camera_reader.disable_cameras()

                if key_pressed == "b":
                    return -1
                return key_pressed == "a"


# Check Traj #
def check_trajectory(
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

    while True:
        for i in range(horizon):
            # Get HDF5 Data #
            timestep = traj_reader.read_timestep()

            # If Applicable, Get Recorded Data #
            if recording_folderpath:
                timestamp_dict = timestep["observation"]["timestamp"]["cameras"]
                camera_obs = camera_reader.read_cameras(timestamp_dict=timestamp_dict)
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

            # Skip #
            if (i % 10) != 0:
                continue

            # Visualize Timestep #
            visualize_timestep(
                timestep, max_width=max_width, max_height=max_height, aspect_ratio=aspect_ratio, pause_time=15
            )

            # Check Termination #
            key_pressed = input("Enter Label (Putting In: A, Taking Out: S):\n")

            if key_pressed in ["a", "s", "b", " "]:
                # Close Readers #
                traj_reader.close()
                if recording_folderpath:
                    camera_reader.disable_cameras()

                if key_pressed == " ":
                    return None
                elif key_pressed == "b":
                    return -1
                return key_pressed == "a"


def filter_func(h5_metadata):
    curr_task = h5_metadata["current_task"]
    desired_task = "Move object into or out of container"
    keep = desired_task in curr_task
    return keep


traj_folders = collect_data_folderpaths(filter_func=filter_func, remove_failures=True)
labeled_trajectories = list(load_task_info().keys())
labeled_traj_dict = load_task_info()

i = 0
label = 0

# while i < len(traj_folders):
# 	folderpath = traj_folders[i]
# 	name = folderpath.split('/')[-1]

# 	filepath = os.path.join(folderpath, 'trajectory.h5')
# 	recording_folderpath = os.path.join(folderpath, 'recordings')
# 	if name in labeled_trajectories and labeled_traj_dict[name] == 1:
# 		label = check_trajectory(filepath, recording_folderpath=recording_folderpath, remove_skipped_steps=True)

# 		if label != None:
# 			print('relabling')
# 			update_task_label(name, label)

# 	i += 1


while i < len(traj_folders):
    folderpath = traj_folders[i]
    name = folderpath.split("/")[-1]
    if (label != -1) and (name in labeled_trajectories):
        i += 1
        continue

    filepath = os.path.join(folderpath, "trajectory.h5")
    recording_folderpath = os.path.join(folderpath, "recordings", "SVO")
    try:
        label = label_trajectory(filepath, recording_folderpath=recording_folderpath, remove_skipped_steps=True)
    except:
        i += 1
        continue

    if label == -1:
        i -= 1
    else:
        update_task_label(name, label)
        i += 1
