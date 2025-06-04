from functools import partial
from typing import Dict

import tensorflow as tf


def get_type_spec(path: str) -> Dict[str, tf.TensorSpec]:
    """Get a type spec from a tfrecord file.

    Args:
        path (str): Path to a single tfrecord file.

    Returns:
        dict: A dictionary mapping feature names to tf.TensorSpecs.
    """
    data = next(iter(tf.data.TFRecordDataset(path))).numpy()
    example = tf.train.Example()
    example.ParseFromString(data)

    out = {}
    for key, value in example.features.feature.items():
        data = value.bytes_list.value[0]
        tensor_proto = tf.make_tensor_proto([])
        tensor_proto.ParseFromString(data)
        dtype = tf.dtypes.as_dtype(tensor_proto.dtype)
        shape = [d.size for d in tensor_proto.tensor_shape.dim]
        shape[0] = None  # first dimension is trajectory length, which is variable
        out[key] = tf.TensorSpec(shape=shape, dtype=dtype)

    return out


def get_tf_dataloader(
    path: str,
    *,
    batch_size: int,
    shuffle_buffer_size: int = 25000,
    cache: bool = False,
) -> tf.data.Dataset:
    # get the tfrecord files
    paths = tf.io.gfile.glob(tf.io.gfile.join(path, "*.tfrecord"))

    # extract the type spec
    type_spec = get_type_spec(paths[0])

    # read the tfrecords (yields raw serialized examples)
    dataset = tf.data.TFRecordDataset(paths, num_parallel_reads=tf.data.AUTOTUNE)

    # decode the examples (yields trajectories)
    dataset = dataset.map(partial(_decode_example, type_spec=type_spec), num_parallel_calls=tf.data.AUTOTUNE)

    # cache all the dataloading (uses a lot of memory)
    if cache:
        dataset = dataset.cache()

    # do any trajectory-level transforms here (e.g. filtering, goal relabeling)

    # unbatch to get individual transitions
    dataset = dataset.unbatch()

    # process each transition
    dataset = dataset.map(_process_transition, num_parallel_calls=tf.data.AUTOTUNE)

    # do any transition-level transformations here (e.g. augmentations)

    # shuffle the dataset
    dataset = dataset.shuffle(shuffle_buffer_size)

    dataset = dataset.repeat()

    # batch the dataset
    dataset = dataset.batch(batch_size, num_parallel_calls=tf.data.AUTOTUNE)

    # always prefetch last
    dataset = dataset.prefetch(tf.data.AUTOTUNE)

    return dataset


def _decode_example(example_proto: tf.Tensor, type_spec: Dict[str, tf.TensorSpec]) -> Dict[str, tf.Tensor]:
    features = {key: tf.io.FixedLenFeature([], tf.string) for key in type_spec.keys()}
    parsed_features = tf.io.parse_single_example(example_proto, features)
    parsed_tensors = {key: tf.io.parse_tensor(parsed_features[key], spec.dtype) for key, spec in type_spec.items()}

    for key in parsed_tensors:
        parsed_tensors[key] = tf.ensure_shape(parsed_tensors[key], type_spec[key].shape)

    return parsed_tensors


def _process_transition(transition: Dict[str, tf.Tensor]) -> Dict[str, tf.Tensor]:
    for key in transition:
        if "image" in key:
            transition[key] = tf.io.decode_jpeg(transition[key])

            # convert to float and normalize to [-1, 1]
            transition[key] = tf.cast(transition[key], tf.float32) / 127.5 - 1.0
    return transition


if __name__ == "__main__":
    ### EXAMPLE USAGE ###
    import tqdm

    dataset = get_tf_dataloader(
        "/tmp/franka_tfrecord_test/train",
        batch_size=8,
        shuffle_buffer_size=1,
    )
    with tqdm.tqdm() as pbar:
        for batch in dataset.as_numpy_iterator():
            for key, value in batch.items():
                pbar.write(f"{key}: {value.shape}")
            images = batch["observation/image/20521388_right"]
            pbar.update(len(images))
            # for image in images:
            #     plt.imshow(image / 2 + 0.5)
            #     plt.savefig("test.png")
