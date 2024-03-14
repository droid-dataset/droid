from droid.controllers.oculus_controller import VRPolicy
from droid.robot_env import RobotEnv
from droid.trajectory_utils.misc import collect_trajectory

# Make the robot env
env = RobotEnv()
controller = VRPolicy()

print("Ready")
collect_trajectory(env, controller=controller)
