from torch.utils.data import DataLoader
from torch.utils.data.datapipes.iter import Shuffler

from droid.data_loading.dataset import TrajectoryDataset
from droid.data_loading.trajectory_sampler import *


def create_dataloader(
    data_folderpaths,
    recording_prefix="MP4",
    batch_size=32,
    num_workers=6,
    buffer_size=1000,
    prefetch_factor=2,
    traj_loading_kwargs={},
    timestep_filtering_kwargs={},
    camera_kwargs={},
    image_transform_kwargs={},
):
    traj_sampler = TrajectorySampler(
        data_folderpaths,
        recording_prefix=recording_prefix,
        traj_loading_kwargs=traj_loading_kwargs,
        timestep_filtering_kwargs=timestep_filtering_kwargs,
        image_transform_kwargs=image_transform_kwargs,
        camera_kwargs=camera_kwargs,
    )
    dataset = TrajectoryDataset(traj_sampler)
    shuffled_dataset = Shuffler(dataset, buffer_size=buffer_size)
    dataloader = DataLoader(
        shuffled_dataset, batch_size=batch_size, num_workers=num_workers, prefetch_factor=prefetch_factor
    )

    return dataloader


def create_train_test_data_loader(data_loader_kwargs={}, data_processing_kwargs={}, camera_kwargs={}):
    # Generate Train / Test Split #
    data_filtering_kwargs = data_loader_kwargs.pop("data_filtering_kwargs", {})
    train_folderpaths, test_folderpaths = generate_train_test_split(**data_filtering_kwargs)

    # Create Train / Test Dataloaders #
    train_dataloader = create_dataloader(
        train_folderpaths, **data_loader_kwargs, **data_processing_kwargs, camera_kwargs=camera_kwargs
    )
    test_dataloader = create_dataloader(
        test_folderpaths, **data_loader_kwargs, **data_processing_kwargs, camera_kwargs=camera_kwargs
    )

    return train_dataloader, test_dataloader


# This is nice bc we only have one buffer at a time, but isn't working
class TrainTestDataloader:
    def __init__(self, data_loader_kwargs={}, data_processing_kwargs={}, camera_kwargs={}):
        # Generate Train / Test Split #
        data_filtering_kwargs = data_loader_kwargs.pop("data_filtering_kwargs", {})
        self.train_folderpaths, self.test_folderpaths = generate_train_test_split(**data_filtering_kwargs)

        # Create Dataloader Generator #
        self.generate_dataloader = lambda folderpaths: create_dataloader(
            folderpaths, **data_loader_kwargs, **data_processing_kwargs, camera_kwargs=camera_kwargs
        )

    def set_train_mode(self):
        self.dataloader = self.generate_dataloader(self.train_folderpaths)

    def set_test_mode(self):
        self.dataloader = self.generate_dataloader(self.test_folderpaths)

    def __iter__(self):
        return iter(self.dataloader)
