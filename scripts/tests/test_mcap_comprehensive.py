#!/usr/bin/env python3
"""
Comprehensive test script for MCAP functionality.
Tests data storage and retrieval for:
- 3 ZED cameras (simulated)
- 1 microphone (simulated)
- Franka robot data (simulated)
"""
import os
import sys
import tempfile
import numpy as np
import time
import json

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from droid.trajectory_utils.trajectory_writer_mcap import TrajectoryWriterMCAP
from droid.trajectory_utils.trajectory_reader_mcap import TrajectoryReaderMCAP


def create_test_timestep(frame_idx=0):
    """Create a simulated timestep with all sensor data"""
    
    # Simulate robot state data
    robot_state = {
        "joint_positions": np.random.rand(7).tolist(),
        "joint_velocities": np.random.rand(7).tolist(), 
        "joint_efforts": np.random.rand(7).tolist(),
        "cartesian_position": np.random.rand(6).tolist(),
        "cartesian_velocity": np.random.rand(6).tolist(),
        "gripper_position": np.random.rand(),
        "gripper_velocity": np.random.rand()
    }
    
    # Simulate 3 ZED cameras (each with left and right images) 
    camera_serials = ["12345", "23456", "34567"]  # 3 camera serial numbers
    images = {}
    
    for serial in camera_serials:
        # Create simulated images (480x640x3 BGR)
        left_img = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        right_img = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        
        images[f"{serial}_left"] = left_img
        images[f"{serial}_right"] = right_img
    
    # Simulate microphone data
    audio_data = {
        "data": np.random.randint(-32768, 32767, 1024, dtype=np.int16).tobytes(),
        "sample_rate": 44100,
        "encoding": "pcm_16le"
    }
    
    # Simulate VR controller data (Quest/Oculus)
    controller_info = {
        "poses": {
            "r": np.random.rand(4, 4).astype(np.float32),  # Right controller 4x4 transformation matrix
            "l": np.random.rand(4, 4).astype(np.float32),  # Left controller 4x4 transformation matrix
        },
        "buttons": {
            "A": np.random.choice([True, False]),
            "B": np.random.choice([True, False]),
            "X": np.random.choice([True, False]), 
            "Y": np.random.choice([True, False]),
            "RG": np.random.choice([True, False]),  # Right grip
            "LG": np.random.choice([True, False]),  # Left grip
            "RJ": np.random.choice([True, False]),  # Right joystick
            "LJ": np.random.choice([True, False]),  # Left joystick
            "rightTrig": [np.random.rand()],        # Right trigger value
            "leftTrig": [np.random.rand()],         # Left trigger value
        },
        "movement_enabled": np.random.choice([True, False]),
        "controller_on": True,
        "success": False,
        "failure": False
    }
    
    # Create observation dict
    observation = {
        "robot_state": robot_state,
        "image": images,
        "audio": audio_data,
        "controller_info": controller_info,
        "timestamp": {
            "robot_state": {
                "read_start": time.time_ns()
            }
        }
    }
    
    # Simulate action data
    action = np.random.rand(7).tolist()  # 7-DOF action
    
    return {
        "observation": observation,
        "action": action
    }


def test_mcap_write_read():
    """Test writing and reading MCAP files"""
    print("Testing MCAP write and read functionality...")
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(suffix=".mcap", delete=False) as tmp_file:
        mcap_path = tmp_file.name
    
    try:
        # Test writing
        print("Writing test data to MCAP...")
        metadata = {
            "test": "comprehensive_mcap_test",
            "cameras": 3,
            "microphone": True,
            "description": "Test with 3 ZED cameras, microphone, and robot data"
        }
        
        writer = TrajectoryWriterMCAP(mcap_path, metadata=metadata, save_images=True)
        
        # Write 10 timesteps
        num_timesteps = 10
        for i in range(num_timesteps):
            timestep = create_test_timestep(i)
            writer.write_timestep(timestep)
            print(f"  Written timestep {i+1}/{num_timesteps}")
        
        writer.close()
        print(f"Successfully wrote {num_timesteps} timesteps to {mcap_path}")
        
        # Test reading
        print("Reading test data from MCAP...")
        reader = TrajectoryReaderMCAP(mcap_path, read_images=True)
        
        print(f"MCAP file contains {reader.length()} timesteps")
        
        # Read all timesteps
        for i in range(reader.length()):
            timestep = reader.read_timestep(i)
            
            # Validate data structure
            assert "observation" in timestep
            assert "action" in timestep
            assert "robot_state" in timestep["observation"]
            assert "image" in timestep["observation"] 
            assert "audio" in timestep["observation"]
            assert "controller_info" in timestep["observation"]
            
            # Validate robot state
            robot_state = timestep["observation"]["robot_state"]
            assert "joint_positions" in robot_state
            assert "joint_velocities" in robot_state
            assert "joint_efforts" in robot_state
            assert "cartesian_position" in robot_state
            assert "cartesian_velocity" in robot_state
            assert "gripper_position" in robot_state
            assert "gripper_velocity" in robot_state
            
            # Validate images (should have 6 images: 3 cameras x 2 sides)
            images = timestep["observation"]["image"]
            expected_cameras = ["12345_left", "12345_right", "23456_left", "23456_right", "34567_left", "34567_right"]
            for cam_id in expected_cameras:
                assert cam_id in images, f"Missing camera {cam_id}"
                assert images[cam_id].shape == (480, 640, 3), f"Wrong image shape for {cam_id}"
            
            # Validate audio
            audio = timestep["observation"]["audio"]
            assert "data" in audio
            assert "sample_rate" in audio 
            assert "encoding" in audio
            assert audio["sample_rate"] == 44100
            assert audio["encoding"] == "pcm_16le"
            
            # Validate VR controller data
            controller_info = timestep["observation"]["controller_info"]
            assert "poses" in controller_info
            assert "buttons" in controller_info
            assert "movement_enabled" in controller_info
            assert "controller_on" in controller_info
            assert "success" in controller_info
            assert "failure" in controller_info
            
            # Validate VR poses
            poses = controller_info["poses"]
            if poses:  # Only check if poses exist
                for pose_key, pose_matrix in poses.items():
                    assert isinstance(pose_matrix, np.ndarray), f"Pose {pose_key} should be numpy array"
                    assert pose_matrix.shape == (4, 4), f"Pose {pose_key} should be 4x4 matrix"
            
            # Validate VR buttons
            buttons = controller_info["buttons"]
            if buttons:  # Only check if buttons exist
                expected_buttons = ["A", "B", "X", "Y", "RG", "LG", "RJ", "LJ"]
                for btn in expected_buttons:
                    if btn in buttons:
                        assert isinstance(buttons[btn], (bool, np.bool_)), f"Button {btn} should be boolean"
                
                # Validate trigger values
                for trigger in ["rightTrig", "leftTrig"]:
                    if trigger in buttons:
                        assert isinstance(buttons[trigger], list), f"{trigger} should be a list"
            
            # Validate action
            action = timestep["action"]
            assert len(action) == 7, f"Expected 7-DOF action, got {len(action)}"
            
            print(f"  Validated timestep {i+1}/{reader.length()}")
        
        reader.close()
        print("Successfully read and validated all timesteps")
        
        # Test trajectory reading
        print("Testing get_trajectory method...")
        reader2 = TrajectoryReaderMCAP(mcap_path, read_images=True)
        trajectory = reader2.get_trajectory()
        assert len(trajectory) == num_timesteps
        reader2.close()
        print("get_trajectory method works correctly")
        
        print("✅ All MCAP tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ MCAP test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up
        if os.path.exists(mcap_path):
            os.unlink(mcap_path)


def test_mcap_compatibility():
    """Test MCAP compatibility with existing workflow"""
    print("Testing MCAP compatibility with existing trajectory loading...")
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(suffix=".mcap", delete=False) as tmp_file:
        mcap_path = tmp_file.name
    
    try:
        # Write MCAP file
        writer = TrajectoryWriterMCAP(mcap_path, save_images=True)
        for i in range(5):
            timestep = create_test_timestep(i)
            writer.write_timestep(timestep)
        writer.close()
        
        # Test load_trajectory function
        from droid.trajectory_utils.misc import load_trajectory
        
        trajectory = load_trajectory(
            filepath=mcap_path,
            read_cameras=True,
            use_mcap=True
        )
        
        assert len(trajectory) == 5
        print("✅ load_trajectory works with MCAP files")
        return True
        
    except Exception as e:
        print(f"❌ MCAP compatibility test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        if os.path.exists(mcap_path):
            os.unlink(mcap_path)


def test_mcap_metadata():
    """Test MCAP metadata functionality"""
    print("Testing MCAP metadata...")
    
    with tempfile.NamedTemporaryFile(suffix=".mcap", delete=False) as tmp_file:
        mcap_path = tmp_file.name
    
    try:
        # Write with initial metadata
        initial_metadata = {"version": "1.0", "robot": "franka_panda"}
        writer = TrajectoryWriterMCAP(mcap_path, metadata=initial_metadata)
        
        timestep = create_test_timestep()
        writer.write_timestep(timestep)
        
        # Close with final metadata
        final_metadata = {"success": True, "duration": 10.5}
        writer.close(metadata=final_metadata)
        
        print("✅ MCAP metadata test passed")
        return True
        
    except Exception as e:
        print(f"❌ MCAP metadata test failed: {e}")
        return False
        
    finally:
        if os.path.exists(mcap_path):
            os.unlink(mcap_path)


def main():
    """Run all MCAP tests"""
    print("Running comprehensive MCAP tests...\n")
    
    tests = [
        test_mcap_write_read,
        test_mcap_compatibility, 
        test_mcap_metadata
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        print(f"\n{'='*50}")
        if test():
            passed += 1
        else:
            failed += 1
    
    print(f"\n{'='*50}")
    print(f"Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! MCAP implementation is working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 