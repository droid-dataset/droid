# The DROID Robot Platform

This repository contains the code for setting up your DROID robot platform and using it to collect teleoperated demonstration data. This platform was used to collect the [DROID dataset](https://droid-dataset.github.io), a large, in-the-wild dataset of robot manipulations.

If you are interested in using the DROID dataset for training robot policies, please check out our [policy learning repo](https://github.com/droid-dataset/droid_policy_learning).
For more information about DROID, please see the following links:

[**[Homepage]**](https://droid-dataset.github.io) &ensp; [**[Documentation]**](https://droid-dataset.github.io/droid) &ensp; [**[Paper]**](https://arxiv.org/abs/2403.12945) &ensp; [**[Dataset Visualizer]**](https://droid-dataset.github.io/dataset.html).

![](https://droid-dataset.github.io/droid/assets/index/droid_teaser.jpg)

---

## Setup Guide

We assembled a step-by-step guide for setting up the DROID robot platform in our [developer documentation](https://droid-dataset.github.io/droid).
This guide has been used to set up 18 DROID robot platforms over the course of the DROID dataset collection. Please refer to the steps in this guide for setting up your own robot. Specifically, you can follow these key steps:

1. [Hardware Assembly and Setup](https://droid-dataset.github.io/droid/docs/hardware-setup)
2. [Software Installation and Setup](https://droid-dataset.github.io/droid/docs/software-setup)
3. [Example Workflows to collect data or calibrate cameras](https://droid-dataset.github.io/droid/docs/example-workflows)

### Installation Methods

There are two methods of installation for the DROID software:

#### Docker Installation (Recommended)

Running DROID software through Docker requires less installation steps and allows for machines to easily be repurposed for other sets of software as the application software is containerized. This method decouples most of the DROID application config from your host machine configuration.

To run the application using Docker:

1. Make sure Docker is installed on your system
2. Clone this repository
3. Navigate to the `.docker` directory
4. Build and run the Docker containers:
   ```bash
   docker-compose up -d
   ```
5. Connect to the running container:
   ```bash
   docker exec -it droid_container bash
   ```
6. Inside the container, run the application:
   ```bash
   python scripts/main.py
   ```

For more detailed Docker setup instructions, see the [Software Setup documentation](https://droid-dataset.github.io/droid/docs/software-setup).

#### Host Installation

Running DROID software directly on the host machine requires more installation steps but is worthwhile in the case where machines are dedicated to the DROID setup as it forgoes the need to launch and manage Docker containers.

If you encounter issues during setup, please raise them as issues in this github repo.

## Recording Trajectory Data

Once your DROID robot platform is set up, you can start collecting teleoperated demonstration data. The system uses VR controllers (Meta Quest/Oculus) to control the robot and manage recording.

### Starting the System

1. **Using Docker (recommended):**

   ```bash
   cd .docker
   docker-compose up -d
   docker exec -it droid_container bash
   python scripts/main.py
   ```

2. **Direct host execution:**

   ```bash
   python scripts/main.py
   ```

3. **For left controller users:**
   ```bash
   python scripts/main.py --left_controller
   ```

### VR Controller Recording Controls

The trajectory recording is controlled through VR controller buttons:

#### **Right Controller (default):**

- **Button A**: Mark trajectory as **success** and stop recording
- **Button B**: Mark trajectory as **failure** and stop recording
- **Right Grip (RG)**: Hold to enable robot movement during recording
- **Right Joystick (RJ)**: Reset controller orientation

#### **Left Controller:**

- **Button X**: Mark trajectory as **success** and stop recording
- **Button Y**: Mark trajectory as **failure** and stop recording
- **Left Grip (LG)**: Hold to enable robot movement during recording
- **Left Joystick (LJ)**: Reset controller orientation

### Recording Workflow

1. **Start Recording**: Launch the GUI application, which automatically begins recording when you start a trajectory collection session

2. **Control the Robot**:

   - Hold the **grip button** (RG for right controller, LG for left controller) to enable robot movement
   - Move the VR controller to teleoperate the robot arm
   - Release grip to pause movement while keeping recording active

3. **Stop Recording**:
   - **Success**: Press **A** (right controller) or **X** (left controller) to save as successful demonstration
   - **Failure**: Press **B** (right controller) or **Y** (left controller) to save as failed attempt
   - **Emergency Stop**: Press **Ctrl+C** to interrupt (marks as failure)

### Data Output

All recordings are automatically saved to `~/recordings/` with this structure:

```
~/recordings/
├── success/YYYY-MM-DD/        # Successful demonstrations by date
├── failure/YYYY-MM-DD/        # Failed attempts by date
└── evaluation_logs/           # Policy evaluation logs
```

Each trajectory creates a timestamped folder containing:

- `trajectory.mcap` - Main trajectory data (robot states, actions, VR controller data)
- `recordings/SVO/` - Camera recordings from all 3 ZED cameras

### Programmatic Interface

You can also control recording programmatically:

```python
from droid.controllers.oculus_controller import VRPolicy
from droid.robot_env import RobotEnv
from droid.trajectory_utils.misc import collect_trajectory

# Initialize environment and controller
env = RobotEnv()
controller = VRPolicy()

# Collect trajectory (blocks until success/failure button press)
controller_info = collect_trajectory(env, controller=controller)
print(f"Recording completed. Success: {controller_info['success']}")
```

## Data Storage Format

The Droid Franka Robots framework supports two data storage formats:

1. **MCAP Format (Default)** - A standardized container format for robotics data that offers better interoperability, self-contained schemas, and efficient reading/writing. See [docs/mcap_format.md](docs/mcap_format.md) for details.

2. **HDF5 Format (Legacy)** - The original format used for storing trajectory data.

### MCAP Sensor Data Coverage

The MCAP implementation captures comprehensive sensor data from all modalities used in the DROID system:

#### **Robot Data**

- **Joint State**: 7-DOF joint positions, velocities, and efforts
- **Cartesian State**: 6-DOF end-effector position and velocity (x,y,z,rx,ry,rz)
- **Gripper State**: Position and velocity
- **Control Actions**: 7-DOF robot control commands

#### **Camera Data**

- **3 ZED Cameras**: Complete stereo vision setup
  - Hand camera (attached to robot gripper)
  - Two third-person cameras for scene observation
  - Left and right stereo images from each camera (6 images total)
- **Image Format**: JPEG compressed for efficient storage
- **Camera Calibration**: Intrinsics and extrinsics data included

#### **Audio Data**

- **Microphone**: Single channel audio recording
- **Format**: PCM 16-bit encoding at 44.1 kHz sample rate
- **Encoding**: Base64 encoded for MCAP storage

#### **VR Controller Data**

- **Meta Quest/Oculus Controllers**: Complete teleoperation state capture
- **Poses**: 4x4 transformation matrices for left and right controllers
- **Buttons**: All button states (A, B, X, Y, triggers, grip, joystick)
- **Control State**: Movement enabled/disabled, controller connectivity, success/failure flags

### MCAP Data Schema

#### **Topic Structure**

```
/robot_state               - Robot joint and cartesian state
/action                    - Control actions sent to robot
/camera/{id}/compressed    - Compressed images from each camera
/audio/microphone          - Audio data from microphone
/vr_controller             - VR controller poses, buttons, and state
```

#### **Message Schemas**

**Robot State** (`droid.RobotState`)

```json
{
  "timestamp": {"sec": int, "nsec": int},
  "joint_positions": [float],     // 7 elements
  "joint_velocities": [float],    // 7 elements
  "joint_efforts": [float],       // 7 elements
  "cartesian_position": [float],  // 6 elements (x,y,z,rx,ry,rz)
  "cartesian_velocity": [float],  // 6 elements
  "gripper_position": float,
  "gripper_velocity": float
}
```

**Camera Images** (`foxglove.CompressedImage`)

```json
{
  "timestamp": {"sec": int, "nsec": int},
  "frame_id": string,           // Camera identifier (e.g. "12345_left")
  "data": string,               // Base64 encoded JPEG data
  "format": "jpeg"
}
```

**Actions** (`droid.Action`)

```json
{
  "timestamp": {"sec": int, "nsec": int},
  "data": [float]               // 7-DOF action vector
}
```

**Audio** (`foxglove.RawAudio`)

```json
{
  "timestamp": {"sec": int, "nsec": int},
  "frame_id": "microphone",
  "encoding": "pcm_16le",       // PCM 16-bit little endian
  "sample_rate": 44100,
  "data": string                // Base64 encoded audio data
}
```

**VR Controller** (`droid.VRController`)

```json
{
  "timestamp": {"sec": int, "nsec": int},
  "poses": {
    "r": [float],               // Right controller 4x4 matrix (16 elements)
    "l": [float]                // Left controller 4x4 matrix (16 elements)
  },
  "buttons": {
    "A": bool, "B": bool, "X": bool, "Y": bool,
    "RG": bool, "LG": bool,     // Right/Left grip
    "RJ": bool, "LJ": bool,     // Right/Left joystick
    "rightTrig": [float],       // Right trigger value
    "leftTrig": [float]         // Left trigger value
  },
  "movement_enabled": bool,
  "controller_on": bool,
  "success": bool,
  "failure": bool
}
```

### Storage Location

All recordings are stored in `~/recordings/` with the following structure:

```
~/recordings/
├── success/           # Successful demonstrations
├── failure/           # Failed attempts
└── evaluation_logs/   # Policy evaluation logs
```

To convert existing HDF5 files to MCAP format:

```bash
python scripts/convert/h5_to_mcap.py input_file.h5 output_file.mcap
```
