import torch
from torch.utils.data import IterableDataset


class TrajectoryDataset(IterableDataset):
    def __init__(self, trajectory_sampler):
        self._trajectory_sampler = trajectory_sampler

    def _refresh_generator(self):
        worker_info = torch.utils.data.get_worker_info()
        new_samples = self._trajectory_sampler.fetch_samples(worker_info=worker_info)
        self._sample_generator = iter(new_samples)

    def __iter__(self):
        self._refresh_generator()
        while True:
            try:
                yield next(self._sample_generator)
            except StopIteration:
                self._refresh_generator()
