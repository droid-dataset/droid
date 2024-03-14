import os
import tempfile
from collections import defaultdict
from copy import deepcopy
from queue import Empty, Queue

import h5py
import imageio
import numpy as np

from droid.misc.subprocess_utils import run_threaded_command


def write_dict_to_hdf5(hdf5_file, data_dict, keys_to_ignore=["image", "depth", "pointcloud"]):
    for key in data_dict.keys():
        # Pass Over Specified Keys #
        if key in keys_to_ignore:
            continue

        # Examine Data #
        curr_data = data_dict[key]
        if type(curr_data) == list:
            curr_data = np.array(curr_data)
        dtype = type(curr_data)

        # Unwrap If Dictionary #
        if dtype == dict:
            if key not in hdf5_file:
                hdf5_file.create_group(key)
            write_dict_to_hdf5(hdf5_file[key], curr_data)
            continue

        # Make Room For Data #
        if key not in hdf5_file:
            if dtype != np.ndarray:
                dshape = ()
            else:
                dtype, dshape = curr_data.dtype, curr_data.shape
            hdf5_file.create_dataset(key, (1, *dshape), maxshape=(None, *dshape), dtype=dtype)
        else:
            hdf5_file[key].resize(hdf5_file[key].shape[0] + 1, axis=0)

        # Save Data #
        hdf5_file[key][-1] = curr_data


class TrajectoryWriter:
    def __init__(self, filepath, metadata=None, exists_ok=False, save_images=True):
        assert (not os.path.isfile(filepath)) or exists_ok
        self._filepath = filepath
        self._save_images = save_images
        self._hdf5_file = h5py.File(filepath, "w")
        self._queue_dict = defaultdict(Queue)
        self._video_writers = {}
        self._video_files = {}
        self._open = True

        # Add Metadata #
        if metadata is not None:
            self._update_metadata(metadata)

        # Start HDF5 Writer Thread #
        def hdf5_writer(data):
            return write_dict_to_hdf5(self._hdf5_file, data)

        run_threaded_command(self._write_from_queue, args=(hdf5_writer, self._queue_dict["hdf5"]))

    def write_timestep(self, timestep):
        if self._save_images:
            self._update_video_files(timestep)
        self._queue_dict["hdf5"].put(timestep)

    def _update_metadata(self, metadata):
        for key in metadata:
            self._hdf5_file.attrs[key] = deepcopy(metadata[key])

    def _write_from_queue(self, writer, queue):
        while self._open:
            try:
                data = queue.get(timeout=1)
            except Empty:
                continue
            writer(data)
            queue.task_done()

    def _update_video_files(self, timestep):
        image_dict = timestep["observations"]["image"]

        for video_id in image_dict:
            # Get Frame #
            img = image_dict[video_id]
            del image_dict[video_id]

            # Create Writer And Buffer #
            if video_id not in self._video_buffers:
                filename = self.create_video_file(video_id, ".mp4")
                self._video_writers[video_id] = imageio.get_writer(filename, macro_block_size=1)
                run_threaded_command(
                    self._write_from_queue, args=(self._video_writers[video_id].append_data, self._queue_dict[video_id])
                )

            # Add Image To Queue #
            self._queue_dict[video_id].put(img)

        del timestep["observations"]["image"]

    def create_video_file(self, video_id, suffix):
        temp_file = tempfile.NamedTemporaryFile(suffix=suffix)
        self._video_files[video_id] = temp_file
        return temp_file.name

    def close(self, metadata=None):
        # Add Metadata #
        if metadata is not None:
            self._update_metadata(metadata)

        # Finish Remaining Jobs #
        [queue.join() for queue in self._queue_dict.values()]

        # Close Video Writers #
        for video_id in self._video_writers:
            self._video_writers[video_id].close()

        # Save Serialized Videos #
        for video_id in self._video_files:
            # Create Folder #
            if "videos" not in self._hdf5_file["observations"]:
                self._hdf5_file["observations"].create_group("videos")

            # Get Serialized Video #
            self._video_files[video_id].seek(0)
            serialized_video = np.asarray(self._video_files[video_id].read())

            # Save Data #
            self._hdf5_file["observations"]["videos"].create_dataset(video_id, data=serialized_video)
            self._video_files[video_id].close()

        # Close File #
        self._hdf5_file.close()
        self._open = False
