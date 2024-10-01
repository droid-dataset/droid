import time

import numpy as np
import zerorpc


def attempt_n_times(function_list, max_attempts, sleep_time=0.1):
    if type(function_list) is not list:
        function_list = list(function_list)

    for i in range(max_attempts):
        try:
            [f() for f in function_list]
            return
        except zerorpc.exceptions.RemoteError as err:
            last_attempt = i == (max_attempts - 1)
            if last_attempt:
                raise err
            else:
                time.sleep(sleep_time)


class ServerInterface:
    def __init__(self, ip_address="127.0.0.1", launch=True):
        self.ip_address = ip_address
        self.establish_connection()

        if launch:
            func_list = [self.launch_controller, self.launch_robot]
            attempt_n_times(func_list, max_attempts=2)

    def establish_connection(self):
        self.server = zerorpc.Client(heartbeat=20)
        self.server.connect("tcp://" + self.ip_address + ":4242")

    def launch_controller(self):
        self.server.launch_controller()

    def launch_robot(self):
        self.server.launch_robot()

    def kill_controller(self):
        self.server.kill_controller()

    def update_command(self, command, action_space="cartesian_velocity", gripper_action_space="velocity", blocking=False):
        action_dict = self.server.update_command(command.tolist(), action_space, gripper_action_space, blocking)
        return action_dict

    def create_action_dict(self, command, action_space="cartesian_velocity"):
        action_dict = self.server.create_action_dict(command.tolist(), action_space)
        return action_dict

    def update_pose(self, command, velocity=True, blocking=False):
        self.server.update_pose(command.tolist(), velocity, blocking)

    def update_joints(self, command, velocity=True, blocking=False, cartesian_noise=None):
        if cartesian_noise is not None:
            cartesian_noise = cartesian_noise.tolist()
        self.server.update_joints(command.tolist(), velocity, blocking, cartesian_noise)

    def update_gripper(self, command, velocity=True, blocking=False):
        self.server.update_gripper(command, velocity, blocking)

    def get_ee_pose(self):
        return np.array(self.server.get_ee_pose())

    def get_joint_positions(self):
        return np.array(self.server.get_joint_positions())

    def get_joint_velocities(self):
        return np.array(self.server.get_joint_velocities())

    def get_gripper_state(self):
        return self.server.get_gripper_state()

    def get_robot_state(self):
        return self.server.get_robot_state()
