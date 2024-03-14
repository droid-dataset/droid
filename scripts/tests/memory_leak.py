import glob
import random

import matplotlib.pyplot as plt
import psutil
import pyzed.sl as sl
from tqdm import tqdm

from droid.camera_utils.wrappers.recorded_multi_camera_wrapper import RecordedMultiCameraWrapper
from droid.data_loading.trajectory_sampler import *


def example_script():
    path = "/home/sasha/DROID/data/success/2023-02-15/Wed_Feb_15_19:08:33_2023/recordings/23404442.svo"

    init = sl.InitParameters()
    init.set_from_svo_file(path)

    # init = sl.InitParameters(svo_input_filename=path, svo_real_time_mode=False)
    cam = sl.Camera()
    status = cam.open(init)
    if status != sl.ERROR_CODE.SUCCESS:
        print(repr(status))
        return

    runtime = sl.RuntimeParameters()
    mat = sl.Mat()
    while True:  # for 'q' key
        err = cam.grab(runtime)
        if err == sl.ERROR_CODE.SUCCESS:
            cam.retrieve_image(mat)
        else:
            break
    cam.close()


data_filtering_kwargs = dict(
    train_p=0.5,
    remove_failures=True,
    filter_func=None,
)

traj_loading_kwargs = dict(
    remove_skipped_steps=True,
    num_samples_per_traj=None,
    num_samples_per_traj_coeff=1.5,
)

timestep_filtering_kwargs = dict(
    # Eventually need to enable sweeper to take lists #
    action_space="cartesian_velocity",
    robot_state_keys=[],
    camera_extrinsics=[],
)

image_transform_kwargs = dict(
    remove_alpha=True,
    bgr_to_rgb=True,
    to_tensor=True,
    augment=True,
)

camera_kwargs = dict(
    hand_camera=dict(image=True, depth=False, pointcloud=False, concatenate_images=False, resolution=(128, 128)),
    fixed_camera=dict(image=True, depth=False, pointcloud=False, concatenate_images=False, resolution=(128, 128)),
    varied_camera=dict(image=True, depth=False, pointcloud=False, concatenate_images=False, resolution=(128, 128)),
)

train_folderpaths, test_folderpaths = generate_train_test_split(**data_filtering_kwargs)

traj_sampler = TrajectorySampler(
    train_folderpaths,
    traj_loading_kwargs=traj_loading_kwargs,
    timestep_filtering_kwargs=timestep_filtering_kwargs,
    image_transform_kwargs=image_transform_kwargs,
    camera_kwargs=camera_kwargs,
)


def traj_sampling_script():
    traj_sampler.fetch_samples()


def load_random_traj_script():
    folderpath = random.choice(train_folderpaths)
    filepath = os.path.join(folderpath, "trajectory.h5")
    recording_folderpath = os.path.join(folderpath, "recordings/MP4")

    load_trajectory(
        filepath,
        recording_folderpath=recording_folderpath,
        read_cameras=True,
        camera_kwargs=camera_kwargs,
        **traj_loading_kwargs,
    )


def camera_wrapper_script():
    folderpath = random.choice(train_folderpaths)
    recording_folderpath = os.path.join(folderpath, "recordings")

    camera_reader = RecordedMultiCameraWrapper(recording_folderpath, **camera_kwargs)

    while True:
        camera_obs = camera_reader.read_cameras()
        camera_failed = camera_obs is None
        if camera_failed:
            break

    camera_reader.disable_cameras()


def single_reader_script():
    folderpath = random.choice(train_folderpaths)
    recording_folderpath = os.path.join(folderpath, "recordings")
    all_filepaths = glob.glob(recording_folderpath + "/*.svo")

    path = random.choice(all_filepaths)

    camera = RecordedZedCamera(path, serial_number="")
    camera.set_reading_parameters(resolution=(256, 256))

    frame_count = camera.get_frame_count()
    for _i in range(frame_count):
        camera.read_camera()

    camera.disable_camera()


# from droid.training.data_loading.data_loader import create_train_test_data_loader
# data_processing_kwargs=dict(
#     timestep_filtering_kwargs=dict(
#         # Eventually need to enable sweeper to take lists #
#         action_space='cartesian_velocity',
#         robot_state_keys=[],
#         camera_extrinsics=[],
#         image_views=['hand_camera'],
#         depth_views=[],
#         pointcloud_views=[],
#     ),

#     image_transform_kwargs=dict(
#         remove_alpha=True,
#         bgr_to_rgb=True,
#         to_tensor=True,
#         augment=True,
#     ),
# )

# camera_kwargs=dict(
#     image=True,
#     depth=False,
#     pointcloud=False,

#     resolution_kwargs=dict(
#         hand_camera=(256, 256),
#         fixed_camera=(256, 256),
#         varied_camera=(256, 256),
#     ),
# )

# data_loader_kwargs=dict(
#     batch_size=2,
#     prefetch_factor=1,
#     buffer_size=200,
#     num_workers=4,

#     data_filtering_kwargs=dict(
#         train_p=0.5,
#         remove_failures=True,
#         filter_func=None,
#     ),

#     traj_loading_kwargs=dict(
#         remove_skipped_steps=True,
#         num_samples_per_traj=20,
#         num_samples_per_traj_coeff=1.5,
#     ),
# )

# train_dataloader, test_dataloader = create_train_test_data_loader(
#     data_loader_kwargs=data_loader_kwargs, data_processing_kwargs=data_processing_kwargs,
#     camera_kwargs=camera_kwargs)
# iterator = iter(train_dataloader)

# def training_script():
#     next(iterator)


if __name__ == "__main__":
    memory_usage = []
    for _ in tqdm(range(100)):
        curr_mem_usage = psutil.virtual_memory()[3]
        memory_usage.append(curr_mem_usage)

        # single_reader_script()
        load_random_traj_script()

    try:
        plt.plot(memory_usage)
        plt.ylabel("RAM Used")
        plt.xlabel("SVO Files Read")
        plt.show()
    except:
        pass
