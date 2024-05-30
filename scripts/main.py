from droid.controllers.oculus_controller import VRPolicy
from droid.robot_env import RobotEnv
from droid.user_interface.data_collector import DataCollecter
from droid.user_interface.gui import RobotGUI
import argparse

parser = argparse.ArgumentParser(description='Process a boolean argument for right_controller.')

# Adding the right_controller argument
parser.add_argument('--left_controller', action='store_true', help='Use left oculus controller')
parser.add_argument('--right_controller', action='store_true', help='Use right oculus controller')


args = parser.parse_args()

# Make the robot env
env = RobotEnv()

if args.left_controller:
    controller = VRPolicy(right_controller=False)
    # Make the data collector
    data_collector = DataCollecter(env=env, controller=controller)
    # Make the GUI
    user_interface = RobotGUI(robot=data_collector, right_controller=False)
else:
    controller = VRPolicy(right_controller=True)
    # Make the data collector
    data_collector = DataCollecter(env=env, controller=controller)
    # Make the GUI
    user_interface = RobotGUI(robot=data_collector, right_controller=True)




