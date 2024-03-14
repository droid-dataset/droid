---
layout: default
title: Teleoperating the Robot
parent: Example Workflows
nav_order: 1
---

# Prerequisites

This guide assumes you have already setup DROID application software to run on your host machine or through Docker. Proceed with this guide having launched the control server on the NUC and the GUI application on the laptop.

# Teleoperating the Robot

* To teleoperate the robot, your oculus controller should be plugged into your laptop, and the permissions prompt should be accepted (done by putting the headset on and clicking “Accept”. Also, the controller has to be in view of the headset cameras. It detects the pose of the handle via infrared stickers on the handle.
* To control the robot, we will use only the right controller. If you would like to use the left controller for teleoperation instead, change [this](https://github.com/droid-dataset/droid/blob/5f2f96b5cf9d95dde67fda21a8ab776683aeeae7/droid/controllers/oculus_controller.py#L16) parameter.
* Teleoperation works by applying the changes to the oculus handle’s pose to the robot gripper’s pose. The trigger on the front of the controller is used to control the gripper. Actions are only applied when the trigger on the side of the controller is being held.
* It is important for intuitive control that the controller’s definition of forward is aligned with the direction of the robot. The controller defines “forward” on the first step where the side button of the controller is held. At any point, you can redefine the forward direction by pressing down on the joystick until you hear a click. At some point, try changing the definition of forward to get a better feel for its purpose.
* To practice, select `Practice` from the GUI application.

<iframe src="https://drive.google.com/file/d/1Rg10T5rVaK9m_0BYXq2EkVdNgLpZnj3P/preview" width="640" height="480" allow="autoplay"></iframe>

