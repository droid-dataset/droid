# MCAP Data Storage Format

## Overview

DROID Franka Robots now supports storing data in the Foxglove MCAP format, which is a standardized container format for robotics data. This document explains the MCAP implementation, data schema, and how to convert existing H5 files to MCAP.

## What is MCAP?

MCAP (Multi-Channel Container Format for Arbitrary Pub/sub data) is an open source file format designed specifically for robotics data storage. It offers several advantages:

- **Serialization-agnostic**: Supports multiple message serialization formats
- **Self-contained**: Message schemas are stored alongside data
- **Efficient seeking**: Supports fast, indexed reading of data
- **Optional compression**: Supports LZ4 or Zstandard compression
- **Broad language support**: Libraries available for Python, C++, JavaScript, and more
- **Foxglove Studio compatibility**: Can be opened directly in Foxglove Studio for visualization

## Supported Sensors

The DROID MCAP implementation supports comprehensive sensor data collection:

### Robot Data

- **Joint state**: Joint positions, velocities, and efforts (7-DOF)
- **Cartesian state**: End-effector position and velocity (6-DOF)
- **Gripper state**: Position and velocity
- **Actions**: Control commands sent to the robot

### Camera Data

- **3 ZED Cameras**: Each providing left and right stereo images
  - Hand camera (attached to robot gripper)
  - Two third-person cameras for scene observation
- **Image format**: JPEG compressed for efficient storage
- **Camera intrinsics and extrinsics**: Calibration data included

### Audio Data

- **Microphone**: Single channel audio recording
- **Format**: PCM 16-bit or 32-bit encoding
- **Sample rate**: Configurable (default 44.1 kHz)

### VR Controller Data

- **Meta Quest/Oculus Controllers**: Complete VR controller state capture
- **Poses**: 4x4 transformation matrices for left and right controllers
- **Buttons**: All button states (A, B, X, Y, triggers, grip, joystick)
- **State**: Movement enabled/disabled, controller connectivity, success/failure flags

## Data Schema

### Topics Structure

The MCAP files contain the following topics:

```
/robot_state          - Robot joint and cartesian state
/action               - Control actions sent to robot
/camera/{id}/compressed - Compressed images from each camera
/audio/microphone     - Audio data from microphone
/vr_controller        - VR controller poses, buttons, and state
```

### Message Schemas

#### Robot State (`droid.RobotState`)

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

#### Camera Images (`foxglove.CompressedImage`)

```json
{
  "timestamp": {"sec": int, "nsec": int},
  "frame_id": string,           // Camera identifier
  "data": string,               // Base64 encoded JPEG data
  "format": "jpeg"
}
```

#### Actions (`droid.Action`)

```json
{
  "timestamp": {"sec": int, "nsec": int},
  "data": [float]               // 7-DOF action vector
}
```

#### Audio (`foxglove.RawAudio`)

```json
{
  "timestamp": {"sec": int, "nsec": int},
  "frame_id": "microphone",
  "encoding": string,           // "pcm_16le" or "pcm_32le"
  "sample_rate": int,           // Usually 44100
  "data": string                // Base64 encoded audio data
}
```

#### VR Controller (`droid.VRController`)

```json
{
  "timestamp": {"sec": int, "nsec": int},
  "pose": [float],              // 4x4 transformation matrix (16 elements)
  "button_states": [bool],       // 7 elements (A, B, X, Y, triggers, grip, joystick)
  "movement_enabled": bool,
  "controller_connected": bool,
  "success": bool
}
```

## Usage

### Recording Data in MCAP Format

The MCAP format is now the default for new recordings:

```python
from droid.robot_env import RobotEnv
from droid.user_interface.data_collector import DataCollecter

# Create robot environment with microphone enabled
env = RobotEnv(enable_microphone=True)

# Create data collector (uses MCAP by default)
collector = DataCollecter(env, controller, use_mcap=True)

# Collect trajectory - will be saved as .mcap file
collector.collect_trajectory()
```

### Loading MCAP Data

```python
from droid.trajectory_utils.misc import load_trajectory

# Load MCAP file (automatically detected by extension)
trajectory = load_trajectory("path/to/recording.mcap")

# Access data
for timestep in trajectory:
    robot_state = timestep["observation"]["robot_state"]
    images = timestep["observation"]["image"]
    audio = timestep["observation"]["audio"]
    action = timestep["action"]
```

### Reading MCAP Files Directly

```python
from droid.trajectory_utils.trajectory_reader_mcap import TrajectoryReaderMCAP

reader = TrajectoryReaderMCAP("recording.mcap", read_images=True)

# Read individual timesteps
for i in range(reader.length()):
    timestep = reader.read_timestep(i)
    # Process timestep data

# Or read entire trajectory
trajectory = reader.get_trajectory()
reader.close()
```

## Converting H5 to MCAP

To convert existing HDF5 files to MCAP format:

```bash
python scripts/convert/h5_to_mcap.py input_file.h5 output_file.mcap
```

The conversion script will:

- Extract robot state data
- Convert camera images to JPEG format
- Preserve timestamps and metadata
- Create appropriate MCAP schemas

## Visualization

MCAP files can be opened directly in:

- **Foxglove Studio**: Drag and drop the .mcap file for immediate visualization
- **Custom scripts**: Use the `TrajectoryReaderMCAP` class

## Configuration

### Microphone Settings

The microphone recording can be configured:

```python
from droid.camera_utils.recording_readers.microphone_reader import MicrophoneReader

microphone = MicrophoneReader(
    sample_rate=44100,    # Audio sample rate
    chunk_size=1024,      # Samples per chunk
    channels=1,           # Mono audio
    format_bits=16        # 16-bit PCM
)
```

### Camera Configuration

Camera settings are configured through the existing camera system:

```python
camera_kwargs = {
    "hand_camera": {"image": True, "concatenate_images": False},
    "third_person_camera": {"image": True, "concatenate_images": False}
}

env = RobotEnv(camera_kwargs=camera_kwargs)
```

## Performance Considerations

- **Image compression**: JPEG compression reduces file sizes significantly
- **Audio compression**: Raw PCM audio can be large; consider lower sample rates for longer recordings
- **Memory usage**: MCAP files are memory-mapped for efficient reading
- **File sizes**: Expect ~50-100MB per minute of recording with 3 cameras and audio

## Troubleshooting

### Common Issues

1. **Missing pyaudio**: Install with `pip install pyaudio`
2. **Camera permission**: Ensure microphone permissions are granted
3. **Memory errors**: Use `read_images=False` for large files when images aren't needed
4. **Corrupted files**: Check disk space during recording

### Testing

Run the comprehensive test suite:

```bash
python scripts/tests/test_mcap_comprehensive.py
```

This will validate:

- Data writing and reading
- All sensor data types
- Schema compatibility
- Integration with existing code

## Benefits of MCAP Format

1. **Standardization**: Industry-standard format used by many robotics teams
2. **Tooling**: Rich ecosystem of tools for analysis and visualization
3. **Performance**: Efficient storage and fast seeking
4. **Future-proof**: Extensible schema system for new sensor types
5. **Interoperability**: Easy sharing between different software stacks

## Migration Guide

### From H5 to MCAP

1. **Update existing code**: Change `use_mcap=False` to `use_mcap=True` (or remove parameter)
2. **Convert existing data**: Use the conversion script for old recordings
3. **Update analysis scripts**: Replace `TrajectoryReader` with `TrajectoryReaderMCAP` for .mcap files
4. **Verify compatibility**: Run tests to ensure your pipeline works with MCAP

### Backwards Compatibility

The system maintains backwards compatibility:

- H5 files continue to work with existing readers
- The `load_trajectory` function automatically detects file format
- Both formats can be used simultaneously
