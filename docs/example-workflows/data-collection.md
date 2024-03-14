---
layout: default
title: Collecting Data
parent: Example Workflows
nav_order: 3
---

# Prerequisites

**Important:** Before proceeding please ensure you have followed the camera calibration guide and calibrated your cameras. 

This guide assumes you have already setup DROID application software to run on your host machine or through Docker. Proceed with this guide having launched the control server on the NUC and the GUI application on the laptop.

# Collecting Data

## Using the GUI

* The GUI will start by prompting you to enter your name.
	* Note 1: Your trajectories will be associated with the name you type in. So, make sure to be consistent, and type in your full name! The login page will not let you pass until you have done so.
	* Note 2: Press shift to see the camera feed. Anytime you see a camera feed, confirm that there are exactly 6 images on screen. If there is anything different, halt data collection, unplug and replug the 3 camera wires, and restart the GUI.

* After this, you will be presented with the task configuration page. This is where you enter all the tasks that are currently doable from the scene you have created for your robot. You may select from the predefined tasks using the checkboxes, or enter your own tasks in the text box. For your convenience, use the shift button to toggle between this page and the camera feed. This can be useful for checking what is in view of your cameras.
	* In the upper left corner are 3 tabs:
	* Task Ideas: A google doc of task ideas for inspiration split by room type (ex: bedroom, kitchen, etc)
	* Preferred Tasks: We will be collecting demonstrations for 20 abstract tasks, and 20 specific tasks as a backup. These latter 20 tasks are specific instances of the 20 abstract tasks. We ask that you make sure that around once every couple xdays, you collect some trajectories for as many of these tasks as possible. Clicking this tab will bring you to a page that lists all of the specific tasks and allows you to keep track of which ones you have collected data for.
	* Franka Website: This will bring you to your Franka’s website, where you can lock / unlock robot joints, as well as activate FCI mode.

* In the lower right corner are another 3 tabs:
	* Collect Trajectory: This will bring you to the requested task page, where you will be prompted with your task for the next trajectory. You may press A to begin the trajectory, or B to sample a new task if it’s necessary.
	* Calibrate: This will bring you to the camera calibration page. Click the camera that you would like to calibrate. Note that because we need to turn the cameras on in high resolution, button clicks may take a while here. See the section below for more information on camera calibration.
	* Practice: This will allow you to collect a trajectory without the data being saved. You can use this tool however you see fit.

* Periodically, the GUI will prompt you with desired scene changes. Proceed with them as instructed. When the scene changes involve altering a camera position, make sure to recalibrate the associated camera!

* Miscellaneous Notes:
	* Finish trajectories in such a way that the robot can be reset (ex: nothing in gripper, as it will be dropped.
	* Try to create scenes with as many available tasks as possible.
	* Although we want you to stick to the requested tasks, use your best judgment.
	* At any time, hold 'Return' for 5 seconds to reset the robot

# Uploading Data

Instructions for uploading data can be found in [this](https://github.com/droid-dataset/droid/tree/main/scripts) readme.

