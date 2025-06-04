import time

import cv2
import numpy as np
import pyrealsense2 as rs


def gather_realsense_cameras(hardware_reset=False):
    context = rs.context()
    all_devices = list(context.devices)
    all_rs_cameras = []

    for device in all_devices:
        if hardware_reset:
            device.hardware_reset()
            time.sleep(1)
        rs_camera = RealSenseCamera(device)
        all_rs_cameras.append(rs_camera)

    return all_rs_cameras


class RealSenseCamera:
    def __init__(self, device):
        self._pipeline = rs.pipeline()
        self._serial_number = str(device.get_info(rs.camera_info.serial_number))
        self._config = rs.config()

        self._config.enable_device(self._serial_number)

        self._config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
        # self._config.enable_stream(rs.stream.depth, 320, 180, rs.format.z16, 30)
        device_product_line = str(device.get_info(rs.camera_info.product_line))

        if device_product_line == "L500":
            self._config.enable_stream(rs.stream.color, 960, 540, rs.format.bgr8, 30)
        else:
            self._config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)

        cfg = self._pipeline.start(self._config)
        self._align = rs.align(rs.stream.color)

        profile = cfg.get_stream(rs.stream.color)
        intr = profile.as_video_stream_profile().get_intrinsics()
        self._intrinsics = {
            self._serial_number: self._process_intrinsics(intr),
        }

        color_sensor = device.query_sensors()[1]
        color_sensor.set_option(rs.option.enable_auto_exposure, False)
        color_sensor.set_option(rs.option.exposure, 500)
        depth_sensor = device.query_sensors()[0]
        depth_sensor.set_option(rs.option.enable_auto_exposure, False)

        # https://support.stereolabs.com/hc/en-us/articles/360007395634-What-is-the-camera-focal-length-and-field-of-view
        # vertical FOV for a D455 and 1280x800 RGB
        self._fovy = 65
    
    def get_intrinsics(self):
        return self._intrinsics
    
    @property
    def serial_number(self):
        return self._serial_number

    def _process_intrinsics(self, params):
        intrinsics = {}
        intrinsics["cameraMatrix"] = np.array(
            [[params.fx, 0, params.ppx], [0, params.fy, params.ppy], [0, 0, 1]]
        )
        intrinsics["distCoeffs"] = np.array(list(params.coeffs))
        return intrinsics

    def read_camera(self):
        timestamp_dict = {}
        data_dict = {}

        # Wait for a coherent pair of frames: depth and color
        frames = self._pipeline.wait_for_frames()
        frames = self._align.process(frames)

        depth_frame = frames.get_depth_frame()
        color_frame = frames.get_color_frame()

        read_time = time.time()

        # Convert images to numpy arrays
        depth_image = np.asanyarray(depth_frame.get_data())[...,None]
        color_image = np.asanyarray(color_frame.get_data())
        color_image = cv2.cvtColor(color_image, cv2.COLOR_BGR2RGB)

        data_dict["image"] = {
            self._serial_number: color_image,
        }
        data_dict["depth"] = {
            self._serial_number: depth_image,
        }

        return data_dict, timestamp_dict
        # dict_1 = {
        #     "array": color_image,
        #     "shape": color_image.shape,
        #     "type": "rgb",
        #     "read_time": read_time,
        #     "serial_number": self._serial_number,
        # }
        # dict_2 = {
        #     "array": depth_image,
        #     "shape": depth_image.shape,
        #     "type": "depth",
        #     "read_time": read_time,
        #     "serial_number": self._serial_number,
        # }

        # return [dict_1, dict_2]

    def disable_camera(self):
        self._pipeline.stop()
        self._config.disable_all_streams()

    def set_reading_parameters(self, **kwargs):
        pass

    def __del__(self):
        self.disable_camera()
