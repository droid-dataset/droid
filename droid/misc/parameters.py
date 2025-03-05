import os
from cv2 import aruco

# Robot Params #
nuc_ip = "172.16.0.4"
robot_ip = "172.16.0.2"
laptop_ip = "172.16.0.1"
sudo_password = "robot"
robot_type = "panda"  # 'panda' or 'fr3'
robot_serial_number = "2953411325132"

# Camera ID's #
hand_camera_id = "16744838"
varied_camera_1_id = "28834630"
varied_camera_2_id = "23677903"

# Charuco Board Params #
CHARUCOBOARD_ROWCOUNT = 9
CHARUCOBOARD_COLCOUNT = 14
CHARUCOBOARD_CHECKER_SIZE = 0.020
CHARUCOBOARD_MARKER_SIZE = 0.015
ARUCO_DICT = aruco.getPredefinedDictionary(aruco.DICT_5X5_100)

# Ubuntu Pro Token (RT PATCH) #
ubuntu_pro_token = ""

# Code Version [DONT CHANGE] #
droid_version = "1.3"

