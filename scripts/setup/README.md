# Overview

The scripts in this directory can be run to setup the NUC and laptop for the DROID project. Before running these scripts the following steps need to be accomplished:

* Install Ubuntu 22.04
* Setup Free Ubuntu Pro Account 
* Complete system parameters file 

# Install latest Ubuntu 

The following [tutorial](https://ubuntu.com/tutorials/install-ubuntu-desktop#1-overview) demonstrates how to install Ubuntu 22.04 on your machine.

# Setup Ubuntu Pro Account

Register an Ubuntu Pro account [here](https://ubuntu.com/pro). Note your Ubuntu Pro token from your Ubuntu Pro dashboard which will be viewable once you have created an account and logged in.

# Complete parameters
You will need to add the IP parameters, sudo password, robot type, robot serial number, Ubuntu Pro token and Charuco board paramerers in the [parameters.py](https://github.com/AlexanderKhazatsky/DROID/blob/main/droid/misc/parameters.py) file.

You will need to add your the IP address of your Franka Emika control server to the `robot_ip` parameter in `config/<your robot type>/franka_hardware.yaml`.

# NUC Setup

Run `sudo ./nuc_setup.sh`. This script accomplishes the following steps:

* Ensure all dependent submodules are pulled locally
* Installs Docker
* Installs realtime kernel and sets to default
* Disables CPU frequency scaling and sets CPU governor to performance
* Builds docker container for control server
* Sets a static IP
* Runs control server docker container with restart policy that ensure it starts on system boot


# Laptop Setup  

Run `sudo ./laptop_setup.sh`. This script accomplishes the following steps:

* Ensure all dependent submodules are pulled locally
* Installs Docker
* Installs and configures nvidia container toolkit
* Installs APK on Oculus device
* Builds docker container for user client
* Sets a static IP
* Runs user client docker container
