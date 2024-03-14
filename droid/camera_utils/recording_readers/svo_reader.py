from copy import deepcopy

import cv2

try:
    import pyzed.sl as sl
except ModuleNotFoundError:
    print("WARNING: You have not setup the ZED cameras, and currently cannot use them")

resize_func_map = {"cv2": cv2.resize, None: None}


class SVOReader:
    def __init__(self, filepath, serial_number):
        # Save Parameters #
        self.serial_number = serial_number
        self._index = 0

        # Initialize Readers #
        self._sbs_img = sl.Mat()
        self._left_img = sl.Mat()
        self._right_img = sl.Mat()
        self._left_depth = sl.Mat()
        self._right_depth = sl.Mat()
        self._left_pointcloud = sl.Mat()
        self._right_pointcloud = sl.Mat()

        # Set SVO path for playback
        init_parameters = sl.InitParameters()
        init_parameters.camera_image_flip = sl.FLIP_MODE.OFF
        init_parameters.set_from_svo_file(filepath)

        # Open the ZED
        self._cam = sl.Camera()
        status = self._cam.open(init_parameters)
        if status != sl.ERROR_CODE.SUCCESS:
            print("Zed Error: " + repr(status))

    def set_reading_parameters(
        self,
        image=True,
        depth=False,
        pointcloud=False,
        concatenate_images=False,
        resolution=(0, 0),
        resize_func=None,
    ):
        # Save Parameters #
        self.image = image
        self.depth = depth
        self.pointcloud = pointcloud
        self.concatenate_images = concatenate_images
        self.resize_func = resize_func_map[resize_func]

        if self.resize_func is None:
            self.zed_resolution = sl.Resolution(*resolution)
            self.resizer_resolution = (0, 0)
        else:
            self.zed_resolution = sl.Resolution(0, 0)
            self.resizer_resolution = resolution

        self.skip_reading = not any([image, depth, pointcloud])
        if self.skip_reading:
            return

    def get_frame_resolution(self):
        camera_info = self._cam.get_camera_information().camera_configuration
        width = camera_info.resolution.width
        height = camera_info.resolution.height
        return (width, height)

    def get_frame_count(self):
        if self.skip_reading:
            return 0
        return self._cam.get_svo_number_of_frames()

    def set_frame_index(self, index):
        if self.skip_reading:
            return

        if index < self._index:
            self._cam.set_svo_position(index)
            self._index = index

        while self._index < index:
            self.read_camera(ignore_data=True)

    def _process_frame(self, frame):
        frame = deepcopy(frame.get_data())
        if self.resizer_resolution == (0, 0):
            return frame
        return self.resize_func(frame, self.resizer_resolution)

    def read_camera(self, ignore_data=False, correct_timestamp=None, return_timestamp=False):
        # Skip if Read Unnecesary #
        if self.skip_reading:
            return {}

        # Read Camera #
        self._index += 1
        err = self._cam.grab()
        if err != sl.ERROR_CODE.SUCCESS:
            return None
        if ignore_data:
            return None

        # Check Image Timestamp #
        received_time = self._cam.get_timestamp(sl.TIME_REFERENCE.IMAGE).get_milliseconds()
        timestamp_error = (correct_timestamp is not None) and (correct_timestamp != received_time)

        if timestamp_error:
            print("Timestamps did not match...")
            return None

        # Return Data #
        data_dict = {}

        if self.image:
            if self.concatenate_images:
                self._cam.retrieve_image(self._sbs_img, sl.VIEW.SIDE_BY_SIDE, resolution=self.zed_resolution)
                data_dict["image"] = {self.serial_number: self._process_frame(self._sbs_img)}
            else:
                self._cam.retrieve_image(self._left_img, sl.VIEW.LEFT, resolution=self.zed_resolution)
                self._cam.retrieve_image(self._right_img, sl.VIEW.RIGHT, resolution=self.zed_resolution)
                data_dict["image"] = {
                    self.serial_number + "_left": self._process_frame(self._left_img),
                    self.serial_number + "_right": self._process_frame(self._right_img),
                }
        # if self.depth:
        # 	self._cam.retrieve_measure(self._left_depth, sl.MEASURE.DEPTH, resolution=self.resolution)
        # 	self._cam.retrieve_measure(self._right_depth, sl.MEASURE.DEPTH_RIGHT, resolution=self.resolution)
        # 	data_dict['depth'] = {
        # 		self.serial_number + '_left': self._left_depth.get_data().copy(),
        # 		self.serial_number + '_right': self._right_depth.get_data().copy()}
        # if self.pointcloud:
        # 	self._cam.retrieve_measure(self._left_pointcloud, sl.MEASURE.XYZRGBA, resolution=self.resolution)
        # 	self._cam.retrieve_measure(self._right_pointcloud, sl.MEASURE.XYZRGBA_RIGHT, resolution=self.resolution)
        # 	data_dict['pointcloud'] = {
        # 		self.serial_number + '_left': self._left_pointcloud.get_data().copy(),
        # 		self.serial_number + '_right': self._right_pointcloud.get_data().copy()}

        if return_timestamp:
            return data_dict, received_time
        return data_dict

    def disable_camera(self):
        if hasattr(self, "_cam"):
            self._cam.close()
