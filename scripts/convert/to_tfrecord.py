import os

import numpy as np
import tensorflow as tf
import tqdm
from absl import app, flags, logging
from tqdm_multiprocess import TqdmMultiProcessPool

from droid.data_loading.trajectory_sampler import crawler
from droid.trajectory_utils.misc import load_trajectory

"""
AVAILABLE KEYS:

action/cartesian_position
action/cartesian_velocity
action/gripper_position
action/gripper_velocity
action/joint_position
action/joint_velocity
action/robot_state/cartesian_position
action/robot_state/gripper_position
action/robot_state/joint_positions
action/robot_state/joint_torques_computed
action/robot_state/joint_velocities
action/robot_state/motor_torques_measured
action/robot_state/prev_command_successful
action/robot_state/prev_controller_latency_ms
action/robot_state/prev_joint_torques_computed
action/robot_state/prev_joint_torques_computed_safened
action/target_cartesian_position
action/target_gripper_position
observation/camera_extrinsics/13062452_left
observation/camera_extrinsics/13062452_left_gripper_offset
observation/camera_extrinsics/13062452_right
observation/camera_extrinsics/13062452_right_gripper_offset
observation/camera_extrinsics/19824535_left
observation/camera_extrinsics/19824535_right
observation/camera_extrinsics/20521388_left
observation/camera_extrinsics/20521388_right
observation/camera_extrinsics/23404442_left
observation/camera_extrinsics/23404442_right
observation/camera_extrinsics/24259877_left
observation/camera_extrinsics/24259877_right
observation/camera_extrinsics/26405488_left
observation/camera_extrinsics/26405488_right
observation/camera_extrinsics/29838012_left
observation/camera_extrinsics/29838012_right
observation/camera_type/13062452
observation/camera_type/20521388
observation/camera_type/24259877
observation/controller_info/controller_on
observation/controller_info/failure
observation/controller_info/movement_enabled
observation/controller_info/success
observation/robot_state/cartesian_position
observation/robot_state/gripper_position
observation/robot_state/joint_positions
observation/robot_state/joint_torques_computed
observation/robot_state/joint_velocities
observation/robot_state/motor_torques_measured
observation/robot_state/prev_command_successful
observation/robot_state/prev_controller_latency_ms
observation/robot_state/prev_joint_torques_computed
observation/robot_state/prev_joint_torques_computed_safened
observation/timestamp/cameras/13062452_estimated_capture
observation/timestamp/cameras/13062452_frame_received
observation/timestamp/cameras/13062452_read_end
observation/timestamp/cameras/13062452_read_start
observation/timestamp/cameras/20521388_estimated_capture
observation/timestamp/cameras/20521388_frame_received
observation/timestamp/cameras/20521388_read_end
observation/timestamp/cameras/20521388_read_start
observation/timestamp/cameras/24259877_estimated_capture
observation/timestamp/cameras/24259877_frame_received
observation/timestamp/cameras/24259877_read_end
observation/timestamp/cameras/24259877_read_start
observation/timestamp/control/control_start
observation/timestamp/control/policy_start
observation/timestamp/control/sleep_start
observation/timestamp/control/step_end
observation/timestamp/control/step_start
observation/timestamp/robot_state/read_end
observation/timestamp/robot_state/read_start
observation/timestamp/robot_state/robot_timestamp_nanos
observation/timestamp/robot_state/robot_timestamp_seconds
observation/timestamp/skip_action
observation/image/24259877_left
observation/image/24259877_right
observation/image/13062452_left
observation/image/13062452_right
observation/image/20521388_left
observation/image/20521388_right
"""


def flatten(x):
    d = {}
    for k, v in x.items():
        if isinstance(v, dict):
            for k2, v2 in flatten(v).items():
                d[k + "/" + k2] = v2
        else:
            d[k] = v
    return d


def tensor_feature(value):
    return tf.train.Feature(bytes_list=tf.train.BytesList(value=[tf.io.serialize_tensor(value).numpy()]))


def resize_and_encode(image, size):
    return tf.io.encode_jpeg(tf.cast(tf.round(tf.image.resize(image, size, method="bicubic")), tf.uint8))


FLAGS = flags.FLAGS
flags.DEFINE_string("input_path", "franka_data/success", "Path to input directory")
flags.DEFINE_string("output_path", "franka_data/tfrecords", "Path to output directory")
flags.DEFINE_bool("overwrite", False, "Overwrite existing tfrecords")
flags.DEFINE_float("train_fraction", 0.8, "Fraction of data to use for training")
flags.DEFINE_integer("shard_size", 200, "Maximum number of trajectories per tfrecord")
flags.DEFINE_integer("num_workers", 8, "Number of workers to use for parallel processing")


KEEP_KEYS = [
    "action/cartesian_position",
    "action/cartesian_velocity",
    "action/gripper_position",
    "action/gripper_velocity",
    "action/target_cartesian_position",
    "action/target_gripper_position",
    "observation/image/24259877_left",
    "observation/image/24259877_right",
    "observation/image/13062452_left",
    "observation/image/13062452_right",
    "observation/image/20521388_left",
    "observation/image/20521388_right",
]

FRAMESKIP = 1
IMAGE_SIZE = (180, 320)


def create_tfrecord(paths, output_path, tqdm_func, global_tqdm):
    writer = tf.io.TFRecordWriter(output_path)

    for path in paths:
        h5_filepath = os.path.join(path, "trajectory.h5")
        recording_folderpath = os.path.join(path, "recordings", "MP4")

        # this is really inefficient, should really do frame skipping inside `load_trajectory` but I didn't want to mess
        # with it for now
        traj = load_trajectory(h5_filepath, recording_folderpath=recording_folderpath)
        traj = traj[::FRAMESKIP]

        # each element of `traj` is a possibly nested dict; flatten them and make sure they all have the same keys
        traj_flat = [flatten(t) for t in traj]
        assert all(t.keys() == traj_flat[0].keys() for t in traj_flat)

        # convert to a single dict of lists, processing images and discarding unwanted keys along the way
        out = {}
        for key in traj_flat[0].keys():
            if key not in KEEP_KEYS:
                continue
            if "image" in key:
                out[key] = [resize_and_encode(t[key], IMAGE_SIZE) for t in traj_flat]
            else:
                out[key] = [t[key] for t in traj_flat]
        example = tf.train.Example(features=tf.train.Features(feature={k: tensor_feature(v) for k, v in out.items()}))

        writer.write(example.SerializeToString())

        global_tqdm.update(1)

    writer.close()


def main(_):
    if tf.io.gfile.exists(FLAGS.output_path):
        if FLAGS.overwrite:
            logging.info(f"Deleting {FLAGS.output_path}")
            tf.io.gfile.rmtree(FLAGS.output_path)
        else:
            logging.info(f"{FLAGS.output_path} exists, exiting")
            return

    all_paths = crawler(FLAGS.input_path)
    all_paths = [p for p in all_paths if os.path.exists(p + "/trajectory.h5") and os.path.exists(p + "/recordings/MP4")]

    # train/test split
    # might be a good idea to do a stratified split, but that would require significant changes in `crawler`
    np.random.shuffle(all_paths)
    train_paths = all_paths[: int(len(all_paths) * FLAGS.train_fraction)]
    test_paths = all_paths[int(len(all_paths) * FLAGS.train_fraction) :]

    # shard paths
    train_shards = np.array_split(train_paths, np.ceil(len(train_paths) / FLAGS.shard_size))
    test_shards = np.array_split(test_paths, np.ceil(len(test_paths) / FLAGS.shard_size))

    # create output paths
    tf.io.gfile.makedirs(os.path.join(FLAGS.output_path, "train"))
    tf.io.gfile.makedirs(os.path.join(FLAGS.output_path, "test"))
    train_output_paths = [os.path.join(FLAGS.output_path, "train", f"{i}.tfrecord") for i in range(len(train_shards))]
    test_output_paths = [os.path.join(FLAGS.output_path, "test", f"{i}.tfrecord") for i in range(len(test_shards))]

    # create tasks (see tqdm_multiprocess documenation)
    tasks = [(create_tfrecord, (train_shards[i], train_output_paths[i])) for i in range(len(train_shards))] + [
        (create_tfrecord, (test_shards[i], test_output_paths[i])) for i in range(len(test_shards))
    ]

    # run tasks
    pool = TqdmMultiProcessPool(FLAGS.num_workers)
    with tqdm.tqdm(total=len(all_paths), dynamic_ncols=True) as pbar:
        pool.map(pbar, tasks, lambda _: None, lambda _: None)


if __name__ == "__main__":
    app.run(main)
