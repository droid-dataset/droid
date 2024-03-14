from torch.utils.data.datapipes.iter import Shuffler

from droid.data_loading.dataset import TrajectoryDataset
from droid.data_loading.trajectory_sampler import *
from droid.trajectory_utils.misc import visualize_timestep

all_folderpaths = collect_data_folderpaths()
traj_sampler = TrajectorySampler(all_folderpaths, recording_prefix="SVO")
traj_dataset = TrajectoryDataset(traj_sampler)
shuffled_dataset = Shuffler(traj_dataset, buffer_size=100)
data_iterator = iter(shuffled_dataset)

while True:
    timestep = next(data_iterator)
    visualize_timestep(timestep, pause_time=500)
