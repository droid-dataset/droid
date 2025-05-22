# MCAP Data Storage Format

## Overview

Droid Franka Robots now supports storing data in the Foxglove MCAP format, which is a standardized container format for robotics data. This document explains the MCAP implementation, data schema, and how to convert existing H5 files to MCAP.

## What is MCAP?

MCAP (Multi-Channel Container Format for Arbitrary Pub/sub data) is an open source file format designed specifically for robotics data storage. It offers several advantages:

- **Serialization-agnostic**: Supports multiple message serialization formats
- **Self-contained**: Message schemas are stored alongside data
- **Efficient seeking**: Supports fast, indexed reading of data
- **Optional compression**: Supports LZ4 or Zstandard compression
- **Broad language support**: Libraries available in C++, Go, Python, Rust, Swift, and TypeScript

Learn more at [mcap.dev](https://mcap.dev).

## Data Schema

The Droid implementation uses the following schema for MCAP:

| Channel           | Topic                            | Schema                     | Description                                                         |
| ----------------- | -------------------------------- | -------------------------- | ------------------------------------------------------------------- |
| Robot State       | `/robot_state`                   | `droid.RobotState`         | Robot state information (joint positions, cartesian position, etc.) |
| Action            | `/action`                        | `droid.Action`             | Robot action data                                                   |
| Camera Images     | `/camera/{camera_id}/compressed` | `foxglove.CompressedImage` | Camera images in JPEG format                                        |
| Camera Extrinsics | `/camera_extrinsics`             | `droid.CameraExtrinsics`   | Camera extrinsic parameters                                         |
| Camera Intrinsics | `/camera_intrinsics`             | `droid.CameraIntrinsics`   | Camera intrinsic parameters                                         |
| Camera Types      | `/camera_type`                   | `droid.CameraType`         | Camera type information                                             |

## Using MCAP Format

MCAP is now the default format for storing trajectories. The `DataCollecter` class has a new parameter `use_mcap` which defaults to `True`:

```python
# To use with MCAP (default)
data_collector = DataCollecter(env, controller, use_mcap=True)

# To use with HDF5 (legacy format)
data_collector = DataCollecter(env, controller, use_mcap=False)
```

You can also specify the format when using the trajectory utility functions directly:

```python
# Using MCAP format
tu.collect_trajectory(env, controller, save_filepath="trajectory.mcap", use_mcap=True)

# Using HDF5 format
tu.collect_trajectory(env, controller, save_filepath="trajectory.h5", use_mcap=False)
```

## Reading MCAP Files

The `TrajectoryReaderMCAP` class provides a consistent interface with the original `TrajectoryReader`:

```python
from droid.trajectory_utils.trajectory_reader_mcap import TrajectoryReaderMCAP

# Read a trajectory file
reader = TrajectoryReaderMCAP("path/to/trajectory.mcap", read_images=True)

# Read the first timestep
timestep = reader.read_timestep()

# Access observation data
robot_state = timestep["observation"]["robot_state"]
camera_images = timestep["observation"]["image"]

# Access action data
action = timestep["action"]

# Close the reader when done
reader.close()
```

## Converting Existing HDF5 Files to MCAP

A conversion utility is provided to convert existing HDF5 trajectory files to MCAP format:

```bash
# Convert a single file
python scripts/convert/h5_to_mcap.py path/to/trajectory.h5 --output path/to/output.mcap

# Convert all files in a directory
python scripts/convert/h5_to_mcap.py path/to/directory --recursive
```

The converter preserves all data from the original H5 files, including:

- Robot state information
- Action data
- Camera images (extracted from embedded videos)
- Camera parameters
- Metadata

## Benefits of Using MCAP

1. **Better interoperability**: MCAP files can be viewed in tools like [Foxglove Studio](https://foxglove.dev)
2. **Self-contained**: No need for separate schema definitions
3. **Future-proof**: Well-defined standard with broad industry support
4. **Performance**: Efficient for both writing and reading
5. **Flexible**: Supports various compression options and serialization formats

## Implementation Details

The MCAP implementation includes:

1. `TrajectoryWriterMCAP`: A replacement for `TrajectoryWriter` that stores data in MCAP format
2. `TrajectoryReaderMCAP`: A replacement for `TrajectoryReader` that reads MCAP files
3. Updated `collect_trajectory` function in `misc.py` that supports both formats
4. `h5_to_mcap.py` conversion utility for existing data
5. Updated `DataCollecter` class with MCAP support

Each timestep in a trajectory recording is stored as separate messages in the MCAP file, all sharing the same timestamp. The schema definitions are stored once at the beginning of the file, making the format self-contained.
