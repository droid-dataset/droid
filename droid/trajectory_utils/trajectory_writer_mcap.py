import os
import tempfile
from collections import defaultdict
from copy import deepcopy
from queue import Empty, Queue
import json
import base64
import struct
import numpy as np
import time
from pathlib import Path

import mcap
from mcap.writer import Writer
from mcap.well_known import SchemaEncoding, MessageEncoding

from droid.misc.subprocess_utils import run_threaded_command


class TrajectoryWriterMCAP:
    def __init__(self, filepath, metadata=None, exists_ok=False, save_images=True):
        assert (not os.path.isfile(filepath)) or exists_ok
        self._filepath = filepath
        self._save_images = save_images
        self._mcap_file = open(filepath, "wb")
        self._writer = Writer(self._mcap_file)
        self._writer.start("ros2", library="droid-franka-robots")
        self._queue_dict = defaultdict(Queue)
        self._video_writers = {}
        self._video_files = {}
        self._open = True
        self._channels = {}
        self._message_schemas = {}
        self._register_schemas()

        # Add Metadata #
        if metadata is not None:
            self._update_metadata(metadata)

        # Start MCAP Writer Thread #
        run_threaded_command(self._write_from_queue, args=(self._write_to_mcap, self._queue_dict["mcap"]))

    def _register_schemas(self):
        # Register robot state schema
        robot_state_schema = {
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
        
        robot_state_schema_id = self._writer.register_schema(
            name="droid.RobotState",
            encoding=SchemaEncoding.JSONSchema,
            data=json.dumps(robot_state_schema).encode("utf-8"),
        )
        
        # Register image schema (using Foxglove CompressedImage schema)
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
        
        image_schema_id = self._writer.register_schema(
            name="foxglove.CompressedImage",
            encoding=SchemaEncoding.JSONSchema,
            data=json.dumps(image_schema).encode("utf-8"),
        )
        
        # Register action schema
        action_schema = {
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
        
        action_schema_id = self._writer.register_schema(
            name="droid.Action",
            encoding=SchemaEncoding.JSONSchema,
            data=json.dumps(action_schema).encode("utf-8"),
        )
        
        # Store schema IDs for later use
        self._message_schemas = {
            "robot_state": robot_state_schema_id,
            "image": image_schema_id,
            "action": action_schema_id
        }

    def write_timestep(self, timestep):
        if self._save_images:
            self._update_video_files(timestep)
        self._queue_dict["mcap"].put(timestep)

    def _update_metadata(self, metadata):
        # Create a metadata record in MCAP
        metadata_json = json.dumps(metadata)
        self._writer.add_metadata("droid_metadata", metadata_json.encode("utf-8"))

    def _write_from_queue(self, writer, queue):
        while self._open:
            try:
                data = queue.get(timeout=1)
            except Empty:
                continue
            writer(data)
            queue.task_done()

    def _write_to_mcap(self, timestep):
        # Get timestamp for this message
        robot_state_timestamp = timestep["observation"]["timestamp"]["robot_state"]
        time_ns = robot_state_timestamp.get("read_start", time.time_ns())
        
        # Register or get channel for robot state
        if "robot_state" not in self._channels:
            self._channels["robot_state"] = self._writer.register_channel(
                topic="/robot_state",
                message_encoding=MessageEncoding.JSON,
                schema_id=self._message_schemas["robot_state"],
            )
        
        # Write robot state
        robot_state = timestep["observation"]["robot_state"]
        robot_state_msg = {
            "timestamp": {
                "sec": int(time_ns / 1e9),
                "nsec": int(time_ns % 1e9)
            },
            "data": robot_state
        }
        
        self._writer.add_message(
            channel_id=self._channels["robot_state"],
            log_time=time_ns,
            data=json.dumps(robot_state_msg).encode("utf-8"),
            publish_time=time_ns
        )
        
        # Process and write image data if present
        if "image" in timestep["observation"]:
            self._write_images(timestep["observation"]["image"], time_ns)
            
        # Write action data
        if "action" not in self._channels:
            self._channels["action"] = self._writer.register_channel(
                topic="/action",
                message_encoding=MessageEncoding.JSON,
                schema_id=self._message_schemas["action"],
            )
            
        action_msg = {
            "timestamp": {
                "sec": int(time_ns / 1e9),
                "nsec": int(time_ns % 1e9)
            },
            "data": timestep["action"]
        }
        
        self._writer.add_message(
            channel_id=self._channels["action"],
            log_time=time_ns,
            data=json.dumps(action_msg).encode("utf-8"),
            publish_time=time_ns
        )
        
        # Write other observation data (extrinsics, intrinsics, etc.)
        self._write_additional_observation_data(timestep["observation"], time_ns)

    def _write_images(self, image_dict, time_ns):
        import cv2
        
        for camera_id, image in image_dict.items():
            # Register channel for this camera if not already done
            if f"image_{camera_id}" not in self._channels:
                self._channels[f"image_{camera_id}"] = self._writer.register_channel(
                    topic=f"/camera/{camera_id}/compressed",
                    message_encoding=MessageEncoding.JSON,
                    schema_id=self._message_schemas["image"],
                )
            
            # Convert image to JPEG and encode as base64
            _, jpeg_data = cv2.imencode(".jpg", image)
            base64_data = base64.b64encode(jpeg_data).decode("utf-8")
            
            # Create message
            image_msg = {
                "timestamp": {
                    "sec": int(time_ns / 1e9),
                    "nsec": int(time_ns % 1e9)
                },
                "format": "jpeg",
                "data": base64_data
            }
            
            # Write to MCAP
            self._writer.add_message(
                channel_id=self._channels[f"image_{camera_id}"],
                log_time=time_ns,
                data=json.dumps(image_msg).encode("utf-8"),
                publish_time=time_ns
            )

    def _write_additional_observation_data(self, observation, time_ns):
        # Handle camera extrinsics
        if "camera_extrinsics" in observation:
            if "camera_extrinsics" not in self._channels:
                # Register channel for camera extrinsics
                extrinsics_schema_id = self._writer.register_schema(
                    name="droid.CameraExtrinsics",
                    encoding=SchemaEncoding.JSONSchema,
                    data=json.dumps({
                        "type": "object",
                        "properties": {
                            "timestamp": {
                                "type": "object",
                                "properties": {
                                    "sec": {"type": "integer"},
                                    "nsec": {"type": "integer"}
                                }
                            },
                            "data": {"type": "object", "additionalProperties": True}
                        }
                    }).encode("utf-8"),
                )
                
                self._channels["camera_extrinsics"] = self._writer.register_channel(
                    topic="/camera_extrinsics",
                    message_encoding=MessageEncoding.JSON,
                    schema_id=extrinsics_schema_id,
                )
            
            extrinsics_msg = {
                "timestamp": {
                    "sec": int(time_ns / 1e9),
                    "nsec": int(time_ns % 1e9)
                },
                "data": observation["camera_extrinsics"]
            }
            
            self._writer.add_message(
                channel_id=self._channels["camera_extrinsics"],
                log_time=time_ns,
                data=json.dumps(extrinsics_msg).encode("utf-8"),
                publish_time=time_ns
            )
        
        # Handle camera intrinsics
        if "camera_intrinsics" in observation:
            if "camera_intrinsics" not in self._channels:
                # Register channel for camera intrinsics
                intrinsics_schema_id = self._writer.register_schema(
                    name="droid.CameraIntrinsics",
                    encoding=SchemaEncoding.JSONSchema,
                    data=json.dumps({
                        "type": "object",
                        "properties": {
                            "timestamp": {
                                "type": "object",
                                "properties": {
                                    "sec": {"type": "integer"},
                                    "nsec": {"type": "integer"}
                                }
                            },
                            "data": {"type": "object", "additionalProperties": True}
                        }
                    }).encode("utf-8"),
                )
                
                self._channels["camera_intrinsics"] = self._writer.register_channel(
                    topic="/camera_intrinsics",
                    message_encoding=MessageEncoding.JSON,
                    schema_id=intrinsics_schema_id,
                )
            
            intrinsics_msg = {
                "timestamp": {
                    "sec": int(time_ns / 1e9),
                    "nsec": int(time_ns % 1e9)
                },
                "data": observation["camera_intrinsics"]
            }
            
            self._writer.add_message(
                channel_id=self._channels["camera_intrinsics"],
                log_time=time_ns,
                data=json.dumps(intrinsics_msg).encode("utf-8"),
                publish_time=time_ns
            )
            
        # Handle camera types
        if "camera_type" in observation:
            if "camera_type" not in self._channels:
                # Register channel for camera types
                camera_type_schema_id = self._writer.register_schema(
                    name="droid.CameraType",
                    encoding=SchemaEncoding.JSONSchema,
                    data=json.dumps({
                        "type": "object",
                        "properties": {
                            "timestamp": {
                                "type": "object",
                                "properties": {
                                    "sec": {"type": "integer"},
                                    "nsec": {"type": "integer"}
                                }
                            },
                            "data": {"type": "object", "additionalProperties": True}
                        }
                    }).encode("utf-8"),
                )
                
                self._channels["camera_type"] = self._writer.register_channel(
                    topic="/camera_type",
                    message_encoding=MessageEncoding.JSON,
                    schema_id=camera_type_schema_id,
                )
            
            camera_type_msg = {
                "timestamp": {
                    "sec": int(time_ns / 1e9),
                    "nsec": int(time_ns % 1e9)
                },
                "data": observation["camera_type"]
            }
            
            self._writer.add_message(
                channel_id=self._channels["camera_type"],
                log_time=time_ns,
                data=json.dumps(camera_type_msg).encode("utf-8"),
                publish_time=time_ns
            )

    def _update_video_files(self, timestep):
        # For MCAP format, we handle images directly in _write_to_mcap
        # This method is kept for compatibility with the original interface
        pass

    def create_video_file(self, video_id, suffix):
        # For MCAP format, we handle images differently
        # This method is kept for compatibility with the original interface
        pass

    def close(self, metadata=None):
        # Add Metadata #
        if metadata is not None:
            self._update_metadata(metadata)

        # Finish Remaining Jobs #
        [queue.join() for queue in self._queue_dict.values()]

        # Close MCAP writer #
        self._writer.finish()
        self._mcap_file.close()
        self._open = False 