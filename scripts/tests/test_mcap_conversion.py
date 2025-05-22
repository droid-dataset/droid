#!/usr/bin/env python3
"""
Test script for MCAP conversion functionality.
"""
import os
import sys
import tempfile
import numpy as np
import h5py

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from droid.trajectory_utils.trajectory_reader import TrajectoryReader
from droid.trajectory_utils.trajectory_reader_mcap import TrajectoryReaderMCAP
from droid.trajectory_utils.trajectory_writer import TrajectoryWriter
from droid.trajectory_utils.trajectory_writer_mcap import TrajectoryWriterMCAP

def create_test_h5_file(filepath):
    """Create a simple test HDF5 file with dummy data."""
    print(f"Creating test HDF5 file: {filepath}")
    
    # Create a trajectory writer
    writer = TrajectoryWriter(filepath, metadata={"test": "metadata"})
    
    # Create dummy timestep data
    for i in range(5):
        # Create observation data
        obs = {
            "timestamp": {
                "robot_state": {
                    "read_start": 1000000 + i * 1000,
                    "read_end": 1000100 + i * 1000
                },
                "cameras": {
                    "camera1_read_start": 1000000 + i * 1000,
                    "camera1_read_end": 1000100 + i * 1000
                }
            },
            "robot_state": {
                "joint_positions": np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]),
                "joint_velocities": np.array([0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07]),
                "cartesian_position": np.array([0.1, 0.2, 0.3, 0.0, 0.0, 0.0]),
                "gripper_position": 0.5
            },
            "camera_extrinsics": {
                "camera1": np.array([1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0])
            },
            "camera_intrinsics": {
                "camera1": np.array([[500.0, 0.0, 320.0], [0.0, 500.0, 240.0], [0.0, 0.0, 1.0]])
            },
            "camera_type": {
                "camera1": 1
            },
            "image": {
                "camera1": np.zeros((480, 640, 3), dtype=np.uint8)
            },
            "controller_info": {
                "movement_enabled": True
            }
        }
        
        # Create action data
        action = {
            "cartesian_position": np.array([0.1, 0.2, 0.3, 0.0, 0.0, 0.0]),
            "gripper_position": 0.5
        }
        
        # Write timestep
        timestep = {"observation": obs, "action": action}
        writer.write_timestep(timestep)
    
    # Close writer
    writer.close(metadata={"success": True})
    print(f"Created test HDF5 file with 5 timesteps")
    return filepath

def test_mcap_writer():
    """Test creating an MCAP file directly with TrajectoryWriterMCAP."""
    print("\n=== Testing MCAP Writer ===")
    
    # Create a temporary file
    with tempfile.NamedTemporaryFile(suffix=".mcap", delete=False) as tmp:
        filepath = tmp.name
    
    # Create an MCAP writer
    writer = TrajectoryWriterMCAP(filepath, metadata={"test": "metadata"})
    
    # Create dummy timestep data
    for i in range(5):
        # Create observation data
        obs = {
            "timestamp": {
                "robot_state": {
                    "read_start": 1000000 + i * 1000,
                    "read_end": 1000100 + i * 1000
                },
                "cameras": {
                    "camera1_read_start": 1000000 + i * 1000,
                    "camera1_read_end": 1000100 + i * 1000
                }
            },
            "robot_state": {
                "joint_positions": np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]),
                "joint_velocities": np.array([0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07]),
                "cartesian_position": np.array([0.1, 0.2, 0.3, 0.0, 0.0, 0.0]),
                "gripper_position": 0.5
            },
            "camera_extrinsics": {
                "camera1": np.array([1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0])
            },
            "camera_intrinsics": {
                "camera1": np.array([[500.0, 0.0, 320.0], [0.0, 500.0, 240.0], [0.0, 0.0, 1.0]])
            },
            "camera_type": {
                "camera1": 1
            },
            "image": {
                "camera1": np.zeros((480, 640, 3), dtype=np.uint8)
            },
            "controller_info": {
                "movement_enabled": True
            }
        }
        
        # Create action data
        action = {
            "cartesian_position": np.array([0.1, 0.2, 0.3, 0.0, 0.0, 0.0]),
            "gripper_position": 0.5
        }
        
        # Write timestep
        timestep = {"observation": obs, "action": action}
        writer.write_timestep(timestep)
    
    # Close writer
    writer.close(metadata={"success": True})
    
    print(f"Created MCAP file: {filepath}")
    file_size = os.path.getsize(filepath)
    print(f"File size: {file_size} bytes")
    
    # Now try to read the file
    reader = TrajectoryReaderMCAP(filepath, read_images=True)
    length = reader.length()
    print(f"MCAP file contains {length} timesteps")
    
    # Read first timestep
    timestep = reader.read_timestep()
    
    # Verify basic content
    assert "observation" in timestep, "Missing observation key"
    assert "robot_state" in timestep["observation"], "Missing robot_state key"
    assert "action" in timestep, "Missing action key"
    
    if "image" in timestep["observation"]:
        print("Successfully read images from MCAP file")
    else:
        print("No images found in MCAP file")
    
    reader.close()
    print("MCAP writer test successful")
    
    # Clean up
    os.unlink(filepath)
    return True

def test_h5_to_mcap_conversion():
    """Test converting an H5 file to MCAP format using the conversion script."""
    print("\n=== Testing H5 to MCAP Conversion ===")
    
    # Create test H5 file
    with tempfile.NamedTemporaryFile(suffix=".h5", delete=False) as tmp:
        h5_filepath = tmp.name
    
    create_test_h5_file(h5_filepath)
    
    # Convert to MCAP
    mcap_filepath = h5_filepath.replace(".h5", ".mcap")
    
    # Import the conversion utility
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../convert")))
    from h5_to_mcap import convert_h5_to_mcap
    
    # Convert the file
    convert_h5_to_mcap(h5_filepath, mcap_filepath)
    
    # Verify MCAP file exists and has non-zero size
    assert os.path.exists(mcap_filepath), f"MCAP file {mcap_filepath} not created"
    assert os.path.getsize(mcap_filepath) > 0, f"MCAP file {mcap_filepath} is empty"
    
    # Try reading the MCAP file
    reader = TrajectoryReaderMCAP(mcap_filepath)
    length = reader.length()
    print(f"Converted MCAP file contains {length} timesteps")
    
    # Read first timestep
    timestep = reader.read_timestep()
    
    # Verify basic content
    assert "observation" in timestep, "Missing observation key"
    assert "robot_state" in timestep["observation"], "Missing robot_state key"
    assert "action" in timestep, "Missing action key"
    
    reader.close()
    print("H5 to MCAP conversion test successful")
    
    # Clean up
    os.unlink(h5_filepath)
    os.unlink(mcap_filepath)
    return True

def main():
    """Run all tests."""
    try:
        test_mcap_writer()
        test_h5_to_mcap_conversion()
        print("\nAll tests passed!")
        return 0
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main()) 