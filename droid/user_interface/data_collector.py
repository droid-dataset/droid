import os
import time
from copy import deepcopy
from datetime import date

import cv2
import h5py

import droid.trajectory_utils.misc as tu
from droid.calibration.calibration_utils import check_calibration_info
from droid.misc.parameters import hand_camera_id, droid_version, robot_serial_number, robot_type

# Prepare Data Folder #
dir_path = os.path.dirname(os.path.realpath(__file__))
data_dir = os.path.join(dir_path, "../../data")


class DataCollecter:
    def __init__(self, env, controller, policy=None, save_data=True, save_traj_dir=None):
        self.env = env
        self.controller = controller
        self.policy = policy

        self.last_traj_path = None
        self.traj_running = False
        self.traj_saved = False
        self.obs_pointer = {}

        # Get Camera Info #
        self.cam_ids = list(env.camera_reader.camera_dict.keys())
        self.cam_ids.sort()

        _, full_cam_ids = self.get_camera_feed()
        self.num_cameras = len(full_cam_ids)
        self.full_cam_ids = full_cam_ids
        self.advanced_calibration = False

        # Make Sure Log Directorys Exist #
        if save_traj_dir is None:
            save_traj_dir = data_dir
        self.success_logdir = os.path.join(save_traj_dir, "success", str(date.today()))
        self.failure_logdir = os.path.join(save_traj_dir, "failure", str(date.today()))
        if not os.path.isdir(self.success_logdir):
            os.makedirs(self.success_logdir)
        if not os.path.isdir(self.failure_logdir):
            os.makedirs(self.failure_logdir)
        self.save_data = save_data

    def reset_robot(self, randomize=False):
        self.env._robot.establish_connection()
        self.controller.reset_state()
        self.env.reset(randomize=randomize)

    def get_user_feedback(self):
        info = self.controller.get_info()
        return deepcopy(info)

    def enable_advanced_calibration(self):
        self.advanced_calibration = True
        self.env.camera_reader.enable_advanced_calibration()

    def disable_advanced_calibration(self):
        self.advanced_calibration = False
        self.env.camera_reader.disable_advanced_calibration()

    def set_calibration_mode(self, cam_id):
        self.env.camera_reader.set_calibration_mode(cam_id)

    def set_trajectory_mode(self):
        self.env.camera_reader.set_trajectory_mode()

    def collect_trajectory(self, info=None, practice=False, reset_robot=True):
        self.last_traj_name = time.asctime().replace(" ", "_")

        if info is None:
            info = {}
        info["time"] = self.last_traj_name
        info["robot_serial_number"] = "{0}-{1}".format(robot_type, robot_serial_number)
        info["version_number"] = droid_version

        if practice or (not self.save_data):
            save_filepath = None
            recording_folderpath = None
        else:
            if len(self.full_cam_ids) != 6:
                raise ValueError("WARNING: User is trying to collect data without all three cameras running!")
            save_filepath = os.path.join(self.failure_logdir, info["time"], "trajectory.h5")
            recording_folderpath = os.path.join(self.failure_logdir, info["time"], "recordings")
            if not os.path.isdir(recording_folderpath):
                os.makedirs(recording_folderpath)

        # Collect Trajectory #
        self.traj_running = True
        self.env._robot.establish_connection()
        controller_info = tu.collect_trajectory(
            self.env,
            controller=self.controller,
            metadata=info,
            policy=self.policy,
            obs_pointer=self.obs_pointer,
            reset_robot=reset_robot,
            recording_folderpath=recording_folderpath,
            save_filepath=save_filepath,
            wait_for_controller=True,
        )
        self.traj_running = False
        self.obs_pointer = {}

        # Sort Trajectory #
        self.traj_saved = controller_info["success"] and (save_filepath is not None)

        if self.traj_saved:
            self.last_traj_path = os.path.join(self.success_logdir, info["time"])
            os.rename(os.path.join(self.failure_logdir, info["time"]), self.last_traj_path)

    def calibrate_camera(self, cam_id, reset_robot=True):
        self.traj_running = True
        self.env._robot.establish_connection()
        success = tu.calibrate_camera(
            self.env,
            cam_id,
            controller=self.controller,
            obs_pointer=self.obs_pointer,
            wait_for_controller=True,
            reset_robot=reset_robot,
        )
        self.traj_running = False
        self.obs_pointer = {}
        return success

    def check_calibration_info(self, remove_hand_camera=False):
        info_dict = check_calibration_info(self.full_cam_ids)
        if remove_hand_camera:
            info_dict["old"] = [cam_id for cam_id in info_dict["old"] if (hand_camera_id not in cam_id)]
        return info_dict

    def get_gui_imgs(self, obs):
        all_cam_ids = list(obs["image"].keys())
        all_cam_ids.sort()

        gui_images = []
        for cam_id in all_cam_ids:
            img = cv2.cvtColor(obs["image"][cam_id], cv2.COLOR_BGRA2RGB)
            gui_images.append(img)

        return gui_images, all_cam_ids

    def get_camera_feed(self):
        if self.traj_running:
            if "image" not in self.obs_pointer:
                raise ValueError
            obs = deepcopy(self.obs_pointer)
        else:
            obs = self.env.read_cameras()[0]
        gui_images, cam_ids = self.get_gui_imgs(obs)
        return gui_images, cam_ids

    def change_trajectory_status(self, success=False):
        if (self.last_traj_path is None) or (success == self.traj_saved):
            return

        save_filepath = os.path.join(self.last_traj_path, "trajectory.h5")
        traj_file = h5py.File(save_filepath, "r+")
        traj_file.attrs["success"] = success
        traj_file.attrs["failure"] = not success
        traj_file.close()

        if success:
            new_traj_path = os.path.join(self.success_logdir, self.last_traj_name)
            os.rename(self.last_traj_path, new_traj_path)
            self.last_traj_path = new_traj_path
            self.traj_saved = True
        else:
            new_traj_path = os.path.join(self.failure_logdir, self.last_traj_name)
            os.rename(self.last_traj_path, new_traj_path)
            self.last_traj_path = new_traj_path
            self.traj_saved = False
