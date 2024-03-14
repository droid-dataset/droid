---
layout: default
title: Calibrating Cameras
parent: Example Workflows
nav_order: 2
---

# Prerequisites

This guide assumes you have already setup DROID application software to run on your host machine or through Docker. Proceed with this guide having launched the control server on the NUC and the GUI application on the laptop.

# Calibrating Cameras

The GUI will let you know if any of your camera’s have yet to be calibrated, or if any of your camera’s haven’t been calibrated in a while (this is to make sure you don’t accidentally move them and forget). Since the hand camera is relatively fixed, it is okay to calibrate significantly less frequently than the other cameras, but it is still good practice to calibrate it every now and then.

Useful Information:
* If calibration is successful, you will be brought back to the calibration hub. If it is unsuccessful, the GUI will inform you as such.
* During calibration, you will see a visualization of the pose estimation of the charuco board. Stable, green boxes along with stable axes lines are good! When these are not present, a calibration is likely to fail. If things start to significantly jumble during the automated calibration procedure, feel free to press B and try again.
* Because the board is heavy, the robot may move differently when the board is attached to the gripper.
* **WARNING:** If A button click is taking a really long time. The camera might have failed. You can confirm this by looking in the terminal for a line that resembles “can’t claim interface…”. The solution is to simply close the GUI, and load it up again. Your previous calibration info will not be lost.

## Mounting Calibration Board

Please follow the instructions in the assembly guide for mounting the calibration board.

## Calibrating a 3rd-Person Camera

<iframe src="https://drive.google.com/file/d/1kcE4YzeJYJLbKanY2N8R66tiCqWjk6ij/preview" width="640" height="480" allow="autoplay"></iframe>

## Calibration a Hand-Mounted Camera

<iframe src="https://drive.google.com/file/d/1Raqb35VDrr4YvSBaola5kSR-QFNKZ32w/preview" width="640" height="480" allow="autoplay"></iframe>
