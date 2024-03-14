import zerorpc

from droid.franka.robot import FrankaRobot

if __name__ == "__main__":
    robot_client = FrankaRobot()
    s = zerorpc.Server(robot_client)
    s.bind("tcp://0.0.0.0:4242")
    s.run()
