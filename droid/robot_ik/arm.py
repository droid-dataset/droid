import os

import numpy as np
from dm_control import mjcf
from dm_robotics.moma.models import types
from dm_robotics.moma.models.robots.robot_arms import robot_arm

from droid.misc.parameters import robot_type


class RobotArm(robot_arm.RobotArm):
    def _build(self, model_file):
        self._mjcf_root = mjcf.from_path(self._model_file)

    def _create_body(self):
        # Find MJCF elements that will be exposed as attributes.
        self._joints = self._mjcf_root.find_all("joint")
        self._bodies = self.mjcf_model.find_all("body")
        self._actuators = self.mjcf_model.find_all("actuator")
        self._wrist_site = self.mjcf_model.find("site", "wrist_site")
        self._base_site = self.mjcf_model.find("site", "base_site")

    def name(self) -> str:
        return self._name

    @property
    def joints(self):
        """List of joint elements belonging to the arm."""
        return self._joints

    @property
    def actuators(self):
        """List of actuator elements belonging to the arm."""
        return self._actuators

    @property
    def mjcf_model(self):
        """Returns the `mjcf.RootElement` object corresponding to this robot."""
        return self._mjcf_root

    def update_state(self, physics: mjcf.Physics, qpos: np.ndarray, qvel: np.ndarray) -> None:
        physics.bind(self._joints).qpos[:] = qpos
        physics.bind(self._joints).qvel[:] = qvel

    def set_joint_angles(self, physics: mjcf.Physics, qpos: np.ndarray) -> None:
        physics.bind(self._joints).qpos[:] = qpos

    @property
    def base_site(self) -> types.MjcfElement:
        return self._base_site

    @property
    def wrist_site(self) -> types.MjcfElement:
        return self._wrist_site

    def initialize_episode(self, physics: mjcf.Physics, random_state: np.random.RandomState):
        """Function called at the beginning of every episode."""
        del random_state  # Unused.
        return


class FrankaArm(RobotArm):
    def _build(self):
        self._name = "franka"
        dir_path = os.path.dirname(os.path.realpath(__file__))
        self._model_file = os.path.join(dir_path, "franka", "{0}.xml".format(robot_type))
        self._mjcf_root = mjcf.from_path(self._model_file)
        self._create_body()
