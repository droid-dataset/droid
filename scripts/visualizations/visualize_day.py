import random

from droid.data_loading.trajectory_sampler import crawler
from droid.trajectory_utils.misc import visualize_trajectory

logdir = "/home/sasha/DROID/data/success/2023-04-20"

all_folderpaths = crawler(logdir)
random.shuffle(all_folderpaths)

camera_kwargs = dict(
    hand_camera=dict(image=True, resolution=(0, 0)),
    varied_camera=dict(image=True, resolution=(0, 0)),
)

for folderpath in all_folderpaths:
    h5_filepath = folderpath + "/trajectory.h5"
    recording_folderpath = folderpath + "/recordings/SVO"
    try:
        visualize_trajectory(
            filepath=h5_filepath, recording_folderpath=recording_folderpath, camera_kwargs=camera_kwargs
        )
    except:
        pass
