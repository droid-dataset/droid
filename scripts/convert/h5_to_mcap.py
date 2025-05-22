#!/usr/bin/env python3
"""
Convert existing HDF5 trajectory files to MCAP format.
Usage: python h5_to_mcap.py input_h5_file output_mcap_file
"""

import os
import sys
import argparse
import h5py
import json
import numpy as np
from pathlib import Path
import time
import cv2
import base64

from mcap.writer import Writer
from mcap.well_known import SchemaEncoding, MessageEncoding

def convert_h5_to_mcap(input_file, output_file):
    print(f"Converting {input_file} to {output_file}")
    
    # Open the HDF5 file
    h5_file = h5py.File(input_file, "r")
    
    # Open the output MCAP file
    mcap_file = open(output_file, "wb")
    writer = Writer(mcap_file)
    writer.start("ros2", library="droid-franka-robots")
    
    # Register schemas for different message types
    schemas = {}
    channels = {}
    
    # Register basic schema for all data types
    def register_schema(name):
        schema = {
            "type": "object",
            "properties": {
                "timestamp": {
                    "type": "object",
                    "properties": {
                        "sec": {"type": "integer"},
                        "nsec": {"type": "integer"}
                    }
                },
                "data": {
                    "type": "object",
                    "additionalProperties": True
                }
            }
        }
        
        schema_id = writer.register_schema(
            name=f"droid.{name}",
            encoding=SchemaEncoding.JSONSchema,
            data=json.dumps(schema).encode("utf-8"),
        )
        schemas[name] = schema_id
        return schema_id
    
    # Register image schema
    image_schema = {
        "type": "object",
        "properties": {
            "timestamp": {
                "type": "object",
                "properties": {
                    "sec": {"type": "integer"},
                    "nsec": {"type": "integer"}
                }
            },
            "format": {"type": "string"},
            "data": {"type": "string"}
        }
    }
    
    schemas["image"] = writer.register_schema(
        name="foxglove.CompressedImage",
        encoding=SchemaEncoding.JSONSchema,
        data=json.dumps(image_schema).encode("utf-8"),
    )
    
    # Register schema for common types
    register_schema("RobotState")
    register_schema("Action")
    register_schema("CameraExtrinsics")
    register_schema("CameraIntrinsics")
    register_schema("CameraType")
    
    # Add file metadata
    for key, value in h5_file.attrs.items():
        if isinstance(value, (str, int, float, bool)):
            writer.add_metadata(key, str(value).encode('utf-8'))
        elif isinstance(value, (np.ndarray, list)):
            writer.add_metadata(key, json.dumps(value.tolist() if isinstance(value, np.ndarray) else value).encode('utf-8'))
        else:
            print(f"Skipping metadata {key} with unsupported type {type(value)}")
    
    # Determine trajectory length
    def get_hdf5_length(group, keys_to_ignore=[]):
        length = None

        for key in group.keys():
            if key in keys_to_ignore:
                continue

            curr_data = group[key]
            if isinstance(curr_data, h5py.Group):
                curr_length = get_hdf5_length(curr_data, keys_to_ignore=keys_to_ignore)
            elif isinstance(curr_data, h5py.Dataset):
                curr_length = len(curr_data)
            else:
                raise ValueError

            if length is None:
                length = curr_length
            assert curr_length == length

        return length
    
    # Get trajectory length
    traj_length = get_hdf5_length(h5_file)
    print(f"Trajectory length: {traj_length}")
    
    # Helper function to extract data from HDF5
    def load_hdf5_to_dict(group, index, keys_to_ignore=[]):
        data_dict = {}

        for key in group.keys():
            if key in keys_to_ignore:
                continue

            curr_data = group[key]
            if isinstance(curr_data, h5py.Group):
                data_dict[key] = load_hdf5_to_dict(curr_data, index, keys_to_ignore=keys_to_ignore)
            elif isinstance(curr_data, h5py.Dataset):
                data_dict[key] = curr_data[index]
            else:
                raise ValueError

        return data_dict
    
    # Process each timestep
    for i in range(traj_length):
        print(f"Processing timestep {i+1}/{traj_length}")
        
        # Load low dimensional data, excluding videos
        keys_to_ignore = ["videos"]
        timestep = load_hdf5_to_dict(h5_file, i, keys_to_ignore=keys_to_ignore)
        
        # Use timestamp from the observation
        timestamp_ns = int(timestep.get("observation", {}).get("timestamp", {}).get("robot_state", {}).get("read_start", time.time_ns()))
        
        # Process robot state
        if "robot_state" in timestep.get("observation", {}):
            if "robot_state" not in channels:
                channels["robot_state"] = writer.register_channel(
                    topic="/robot_state",
                    message_encoding=MessageEncoding.JSON,
                    schema_id=schemas["RobotState"],
                )
            
            robot_state = timestep["observation"]["robot_state"]
            robot_state_msg = {
                "timestamp": {
                    "sec": int(timestamp_ns / 1e9),
                    "nsec": int(timestamp_ns % 1e9)
                },
                "data": robot_state
            }
            
            writer.add_message(
                channel_id=channels["robot_state"],
                log_time=timestamp_ns,
                data=json.dumps(robot_state_msg).encode("utf-8"),
                publish_time=timestamp_ns
            )
        
        # Process action data
        if "action" in timestep:
            if "action" not in channels:
                channels["action"] = writer.register_channel(
                    topic="/action",
                    message_encoding=MessageEncoding.JSON,
                    schema_id=schemas["Action"],
                )
            
            action_msg = {
                "timestamp": {
                    "sec": int(timestamp_ns / 1e9),
                    "nsec": int(timestamp_ns % 1e9)
                },
                "data": timestep["action"]
            }
            
            writer.add_message(
                channel_id=channels["action"],
                log_time=timestamp_ns,
                data=json.dumps(action_msg).encode("utf-8"),
                publish_time=timestamp_ns
            )
        
        # Process camera extrinsics
        if "camera_extrinsics" in timestep.get("observation", {}):
            if "camera_extrinsics" not in channels:
                channels["camera_extrinsics"] = writer.register_channel(
                    topic="/camera_extrinsics",
                    message_encoding=MessageEncoding.JSON,
                    schema_id=schemas["CameraExtrinsics"],
                )
            
            extrinsics_msg = {
                "timestamp": {
                    "sec": int(timestamp_ns / 1e9),
                    "nsec": int(timestamp_ns % 1e9)
                },
                "data": timestep["observation"]["camera_extrinsics"]
            }
            
            writer.add_message(
                channel_id=channels["camera_extrinsics"],
                log_time=timestamp_ns,
                data=json.dumps(extrinsics_msg).encode("utf-8"),
                publish_time=timestamp_ns
            )
        
        # Process camera intrinsics
        if "camera_intrinsics" in timestep.get("observation", {}):
            if "camera_intrinsics" not in channels:
                channels["camera_intrinsics"] = writer.register_channel(
                    topic="/camera_intrinsics",
                    message_encoding=MessageEncoding.JSON,
                    schema_id=schemas["CameraIntrinsics"],
                )
            
            intrinsics_msg = {
                "timestamp": {
                    "sec": int(timestamp_ns / 1e9),
                    "nsec": int(timestamp_ns % 1e9)
                },
                "data": timestep["observation"]["camera_intrinsics"]
            }
            
            writer.add_message(
                channel_id=channels["camera_intrinsics"],
                log_time=timestamp_ns,
                data=json.dumps(intrinsics_msg).encode("utf-8"),
                publish_time=timestamp_ns
            )
        
        # Process camera types
        if "camera_type" in timestep.get("observation", {}):
            if "camera_type" not in channels:
                channels["camera_type"] = writer.register_channel(
                    topic="/camera_type",
                    message_encoding=MessageEncoding.JSON,
                    schema_id=schemas["CameraType"],
                )
            
            camera_type_msg = {
                "timestamp": {
                    "sec": int(timestamp_ns / 1e9),
                    "nsec": int(timestamp_ns % 1e9)
                },
                "data": timestep["observation"]["camera_type"]
            }
            
            writer.add_message(
                channel_id=channels["camera_type"],
                log_time=timestamp_ns,
                data=json.dumps(camera_type_msg).encode("utf-8"),
                publish_time=timestamp_ns
            )
        
        # Process video data if available
        if "videos" in h5_file["observation"] and i == 0:
            # For videos, we need to extract and convert them only once, not per timestamp
            # This approach is slightly different from TrajectoryWriterMCAP which writes images per frame
            # But this is a conversion utility, so we extract the video and sample frames
            
            videos_group = h5_file["observation"]["videos"]
            for video_id in videos_group:
                # Create a temporary video file
                video_data = videos_group[video_id][()]
                temp_video_path = f"/tmp/{video_id}_{int(time.time())}.mp4"
                
                with open(temp_video_path, "wb") as f:
                    f.write(video_data.tobytes())
                
                # Open the video and extract frames
                try:
                    video_capture = cv2.VideoCapture(temp_video_path)
                    frame_count = int(video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
                    fps = video_capture.get(cv2.CAP_PROP_FPS)
                    
                    if frame_count > 0:
                        # Register channel for this camera if needed
                        if f"image_{video_id}" not in channels:
                            channels[f"image_{video_id}"] = writer.register_channel(
                                topic=f"/camera/{video_id}/compressed",
                                message_encoding=MessageEncoding.JSON,
                                schema_id=schemas["image"],
                            )
                        
                        # Sample frames at equal intervals based on trajectory length
                        frame_indices = np.linspace(0, frame_count-1, traj_length, dtype=int)
                        
                        for j, frame_idx in enumerate(frame_indices):
                            # Set the frame position
                            video_capture.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                            ret, frame = video_capture.read()
                            
                            if ret:
                                # Calculate timestamp for this frame
                                frame_timestamp = timestamp_ns + int((j / fps) * 1e9)
                                
                                # Convert frame to JPEG and encode as base64
                                _, jpeg_data = cv2.imencode(".jpg", frame)
                                base64_data = base64.b64encode(jpeg_data).decode("utf-8")
                                
                                # Create message
                                image_msg = {
                                    "timestamp": {
                                        "sec": int(frame_timestamp / 1e9),
                                        "nsec": int(frame_timestamp % 1e9)
                                    },
                                    "format": "jpeg",
                                    "data": base64_data
                                }
                                
                                # Write to MCAP
                                writer.add_message(
                                    channel_id=channels[f"image_{video_id}"],
                                    log_time=frame_timestamp,
                                    data=json.dumps(image_msg).encode("utf-8"),
                                    publish_time=frame_timestamp
                                )
                    
                    # Clean up
                    video_capture.release()
                    os.remove(temp_video_path)
                    
                except Exception as e:
                    print(f"Error processing video {video_id}: {e}")
                    if os.path.exists(temp_video_path):
                        os.remove(temp_video_path)
    
    # Finish writing
    writer.finish()
    mcap_file.close()
    h5_file.close()
    
    print(f"Conversion complete: {input_file} -> {output_file}")
    return True

def main():
    parser = argparse.ArgumentParser(description='Convert HDF5 trajectory files to MCAP format')
    parser.add_argument('input', help='Input HDF5 file or directory')
    parser.add_argument('--output', help='Output MCAP file or directory (default: replace .h5 with .mcap)')
    parser.add_argument('--recursive', action='store_true', help='Recursively process directories')
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    
    if input_path.is_file():
        # Single file conversion
        if not args.output:
            output_file = str(input_path).replace('.h5', '.mcap')
        else:
            output_file = args.output
            
        if input_path.suffix.lower() != '.h5':
            print(f"Warning: Input file {input_path} doesn't have .h5 extension")
            
        convert_h5_to_mcap(str(input_path), output_file)
    
    elif input_path.is_dir():
        # Directory conversion
        if args.output:
            output_dir = Path(args.output)
            if not output_dir.exists():
                output_dir.mkdir(parents=True)
        else:
            output_dir = input_path
            
        # Find all .h5 files
        if args.recursive:
            h5_files = list(input_path.glob('**/*.h5'))
        else:
            h5_files = list(input_path.glob('*.h5'))
            
        print(f"Found {len(h5_files)} HDF5 files to convert")
        
        for h5_file in h5_files:
            # Create output path matching the input directory structure
            rel_path = h5_file.relative_to(input_path)
            output_file = output_dir / rel_path.with_suffix('.mcap')
            
            # Ensure output directory exists
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert the file
            convert_h5_to_mcap(str(h5_file), str(output_file))
    
    else:
        print(f"Error: Input path {input_path} does not exist")
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main()) 