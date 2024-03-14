import os

import h5py
import numpy as np

from droid.data_processing.timestep_processing import TimestepProcesser
from droid.trajectory_utils.misc import load_trajectory


def crawler(dirname, filter_func=None):
    subfolders = [f.path for f in os.scandir(dirname) if f.is_dir()]
    traj_files = [f.path for f in os.scandir(dirname) if (f.is_file() and "trajectory.h5" in f.path)]

    if len(traj_files):
        # Only Save Desired Data #
        if filter_func is None:
            use_data = True
        else:
            hdf5_file = h5py.File(traj_files[0], "r")
            use_data = filter_func(hdf5_file.attrs)
            hdf5_file.close()

        if use_data:
            return [dirname]

    all_folderpaths = []
    for child_dirname in subfolders:
        child_paths = crawler(child_dirname, filter_func=filter_func)
        all_folderpaths.extend(child_paths)

    return all_folderpaths


def generate_train_test_split(filter_func=None, remove_failures=True, train_p=0.9):
    # Collect And Split #
    all_folderpaths = collect_data_folderpaths(filter_func=filter_func, remove_failures=remove_failures)

    # Split Into Train / Test #
    num_train_traj = int(train_p * len(all_folderpaths))
    all_ind = np.random.permutation(len(all_folderpaths))
    training_ind, test_ind = all_ind[:num_train_traj], all_ind[num_train_traj:]
    train_folderpaths, test_folderpaths = [], []

    for i in range(len(all_folderpaths)):
        folderpath = all_folderpaths[i]
        if i in training_ind:
            train_folderpaths.append(folderpath)
        if i in test_ind:
            test_folderpaths.append(folderpath)

    return train_folderpaths, test_folderpaths


def collect_data_folderpaths(filter_func=None, remove_failures=True):
    # Prepare Data Folder #
    dir_path = os.path.dirname(os.path.realpath(__file__))
    data_dir = os.path.join(dir_path, "../../data")
    if remove_failures:
        data_dir = os.path.join(data_dir, "success")

    # Collect #
    all_folderpaths = crawler(data_dir, filter_func=filter_func)

    # Return Paths #
    return all_folderpaths


class TrajectorySampler:
    def __init__(
        self,
        all_folderpaths,
        recording_prefix="",
        traj_loading_kwargs={},
        timestep_filtering_kwargs={},
        image_transform_kwargs={},
        camera_kwargs={},
    ):
        self._all_folderpaths = all_folderpaths
        self.recording_prefix = recording_prefix
        self.traj_loading_kwargs = traj_loading_kwargs
        self.timestep_processer = TimestepProcesser(
            **timestep_filtering_kwargs, image_transform_kwargs=image_transform_kwargs
        )
        self.camera_kwargs = camera_kwargs

    def fetch_samples(self, worker_info=None):
        if worker_info is None:
            range_low, range_high = 0, len(self._all_folderpaths)
        else:
            slice_size = len(self._all_folderpaths) // worker_info.num_workers
            range_low = slice_size * worker_info.id
            range_high = slice_size * (worker_info.id + 1)

        traj_ind = np.random.randint(low=range_low, high=range_high)
        folderpath = self._all_folderpaths[traj_ind]

        filepath = os.path.join(folderpath, "trajectory.h5")
        recording_folderpath = os.path.join(folderpath, "recordings", self.recording_prefix)
        if not os.path.exists(recording_folderpath):
            recording_folderpath = None

        traj_samples = load_trajectory(
            filepath,
            recording_folderpath=recording_folderpath,
            camera_kwargs=self.camera_kwargs,
            **self.traj_loading_kwargs,
        )

        processed_traj_samples = [self.timestep_processer.forward(t) for t in traj_samples]

        return processed_traj_samples
