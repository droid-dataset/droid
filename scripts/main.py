from droid.controllers.oculus_controller import VRPolicy
from droid.robot_env import RobotEnv
from droid.user_interface.data_collector import DataCollecter
from droid.user_interface.gui import RobotGUI

# Make the robot env
env = RobotEnv()
controller = VRPolicy()

# Make the data collector
data_collector = DataCollecter(env=env, controller=controller)

# Make the GUI
user_interface = RobotGUI(robot=data_collector)
