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
        self._writer.start("droid", library="droid-franka-robots")
        self._queue_dict = defaultdict(Queue)
        self._video_writers = {}
        self._video_files = {}
        self._open = True
        self._channels = {}
        self._schemas = {}
        self._register_schemas()

        # Add Metadata #
        if metadata is not None:
            self._update_metadata(metadata)

        # Start MCAP Writer Thread #
        run_threaded_command(self._write_from_queue, args=(self._write_to_mcap, self._queue_dict["mcap"]))

    def _register_schemas(self):
        """Register all the schemas we'll need for DROID data"""
        
        # Foxglove CompressedImage schema for camera data
        self._schemas["compressed_image"] = self._writer.register_schema(
            name="foxglove.CompressedImage",
            encoding="jsonschema",
            data=b"""
            {
              "type": "object",
              "properties": {
                "timestamp": {
                  "type": "object",
                  "properties": {
                    "sec":  {"type": "integer"},
                    "nsec": {"type": "integer"}
                  }
                },
                "frame_id": {"type": "string"},
                "data": {"type": "string", "contentEncoding": "base64"},
                "format": {"type": "string"}
              }
            }
            """
        )
        
        # Foxglove PoseInFrame schema for camera poses/robot poses
        self._schemas["pose"] = self._writer.register_schema(
            name="foxglove.PoseInFrame",
            encoding="jsonschema",
            data=b"""
            {
              "type": "object",
              "properties": {
                "timestamp": {
                  "type": "object",
                  "properties": {
                    "sec":  {"type": "integer"},
                    "nsec": {"type": "integer"}
                  }
                },
                "frame_id": {"type": "string"},
                "pose": {
                  "type": "object",
                  "properties": {
                    "position": {
                      "type": "object",
                      "properties": {
                        "x": {"type": "number"},
                        "y": {"type": "number"},
                        "z": {"type": "number"}
                      }
                    },
                    "orientation": {
                      "type": "object",
                      "properties": {
                        "x": {"type": "number"},
                        "y": {"type": "number"},
                        "z": {"type": "number"},
                        "w": {"type": "number"}
                      }
                    }
                  }
                }
              }
            }
            """
        )
        
        # Robot state schema for joint positions, velocities, etc.
        self._schemas["robot_state"] = self._writer.register_schema(
            name="droid.RobotState",
            encoding="jsonschema",
            data=b"""
            {
              "type": "object",
              "properties": {
                "timestamp": {
                  "type": "object",
                  "properties": {
                    "sec": {"type": "integer"},
                    "nsec": {"type": "integer"}
                  }
                },
                "joint_positions": {
                  "type": "array",
                  "items": {"type": "number"}
                },
                "joint_velocities": {
                  "type": "array", 
                  "items": {"type": "number"}
                },
                "joint_efforts": {
                  "type": "array",
                  "items": {"type": "number"}
                },
                "cartesian_position": {
                  "type": "array",
                  "items": {"type": "number"}
                },
                "cartesian_velocity": {
                  "type": "array",
                  "items": {"type": "number"}
                },
                "gripper_position": {"type": "number"},
                "gripper_velocity": {"type": "number"}
              }
            }
            """
        )
        
        # Action schema for robot actions
        self._schemas["action"] = self._writer.register_schema(
            name="droid.Action",
            encoding="jsonschema", 
            data=b"""
            {
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
                  "type": "array",
                  "items": {"type": "number"}
                }
              }
            }
            """
        )
        
        # Audio data schema for microphone
        self._schemas["audio"] = self._writer.register_schema(
            name="foxglove.RawAudio",
            encoding="jsonschema",
            data=b"""
            {
              "type": "object", 
              "properties": {
                "timestamp": {
                  "type": "object",
                  "properties": {
                    "sec": {"type": "integer"},
                    "nsec": {"type": "integer"}
                  }
                },
                "frame_id": {"type": "string"},
                "encoding": {"type": "string"},
                "sample_rate": {"type": "integer"},
                "data": {"type": "string", "contentEncoding": "base64"}
              }
            }
            """
        )
        
        # VR Controller schema for Quest/Oculus data
        self._schemas["vr_controller"] = self._writer.register_schema(
            name="droid.VRController",
            encoding="jsonschema",
            data=b"""
            {
              "type": "object",
              "properties": {
                "timestamp": {
                  "type": "object", 
                  "properties": {
                    "sec": {"type": "integer"},
                    "nsec": {"type": "integer"}
                  }
                },
                "poses": {
                  "type": "object",
                  "additionalProperties": {
                    "type": "array",
                    "items": {"type": "number"}
                  }
                },
                "buttons": {
                  "type": "object",
                  "properties": {
                    "A": {"type": "boolean"},
                    "B": {"type": "boolean"},
                    "X": {"type": "boolean"},
                    "Y": {"type": "boolean"},
                    "RG": {"type": "boolean"},
                    "LG": {"type": "boolean"},
                    "RJ": {"type": "boolean"},
                    "LJ": {"type": "boolean"},
                    "rightTrig": {"type": "array", "items": {"type": "number"}},
                    "leftTrig": {"type": "array", "items": {"type": "number"}}
                  }
                },
                "movement_enabled": {"type": "boolean"},
                "controller_on": {"type": "boolean"},
                "success": {"type": "boolean"},
                "failure": {"type": "boolean"}
              }
            }
            """
        )

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

    def _get_timestamp_ns(self, timestep):
        """Extract timestamp in nanoseconds from timestep"""
        try:
            robot_timestamp = timestep["observation"]["timestamp"]["robot_state"]
            time_ns = robot_timestamp.get("read_start", time.time_ns())
            if isinstance(time_ns, float):
                time_ns = int(time_ns * 1e6)  # Convert from ms to ns if needed
            return time_ns
        except (KeyError, TypeError):
            return time.time_ns()

    def _write_to_mcap(self, timestep):
        """Write a complete timestep to MCAP"""
        time_ns = self._get_timestamp_ns(timestep)
        ts_sec = int(time_ns // 1_000_000_000)
        ts_nsec = int(time_ns % 1_000_000_000)
        
        # Write robot state
        self._write_robot_state(timestep["observation"]["robot_state"], time_ns, ts_sec, ts_nsec)
        
        # Write action
        if "action" in timestep:
            self._write_action(timestep["action"], time_ns, ts_sec, ts_nsec)
        
        # Write camera images
        if "image" in timestep["observation"]:
            self._write_camera_images(timestep["observation"]["image"], time_ns, ts_sec, ts_nsec)
        
        # Write audio data if present
        if "audio" in timestep["observation"]:
            self._write_audio(timestep["observation"]["audio"], time_ns, ts_sec, ts_nsec)
            
        # Write VR controller data if present
        if "controller_info" in timestep["observation"]:
            self._write_vr_controller(timestep["observation"]["controller_info"], time_ns, ts_sec, ts_nsec)

    def _write_robot_state(self, robot_state, time_ns, ts_sec, ts_nsec):
        """Write robot state data to MCAP"""
        if "robot_state" not in self._channels:
            self._channels["robot_state"] = self._writer.register_channel(
                topic="/robot_state",
                message_encoding="json",
                schema_id=self._schemas["robot_state"]
            )
        
        # Convert robot state to the expected format
        robot_msg = {
            "timestamp": {"sec": ts_sec, "nsec": ts_nsec},
            "joint_positions": robot_state.get("joint_positions", []),
            "joint_velocities": robot_state.get("joint_velocities", []),
            "joint_efforts": robot_state.get("joint_efforts", []),
            "cartesian_position": robot_state.get("cartesian_position", []),
            "cartesian_velocity": robot_state.get("cartesian_velocity", []),
            "gripper_position": robot_state.get("gripper_position", 0.0),
            "gripper_velocity": robot_state.get("gripper_velocity", 0.0)
        }
        
        self._writer.add_message(
            channel_id=self._channels["robot_state"],
            sequence=0,
            log_time=time_ns,
            publish_time=time_ns,
            data=json.dumps(robot_msg).encode("utf-8")
        )

    def _write_action(self, action, time_ns, ts_sec, ts_nsec):
        """Write action data to MCAP"""
        if "action" not in self._channels:
            self._channels["action"] = self._writer.register_channel(
                topic="/action",
                message_encoding="json",
                schema_id=self._schemas["action"]
            )
        
        action_msg = {
            "timestamp": {"sec": ts_sec, "nsec": ts_nsec},
            "data": action.tolist() if hasattr(action, 'tolist') else action
        }
        
        self._writer.add_message(
            channel_id=self._channels["action"],
            sequence=0,
            log_time=time_ns,
            publish_time=time_ns,
            data=json.dumps(action_msg).encode("utf-8")
        )

    def _write_camera_images(self, image_dict, time_ns, ts_sec, ts_nsec):
        """Write camera images to MCAP"""
        import cv2
        
        for camera_id, image in image_dict.items():
            # Create unique channel per camera
            channel_name = f"camera_{camera_id}"
            if channel_name not in self._channels:
                self._channels[channel_name] = self._writer.register_channel(
                    topic=f"/camera/{camera_id}/compressed",
                    message_encoding="json",
                    schema_id=self._schemas["compressed_image"]
                )
            
            # Convert image to JPEG and encode as base64
            if image is not None:
                # Handle different image formats
                if len(image.shape) == 3 and image.shape[2] == 4:  # BGRA
                    image_bgr = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
                elif len(image.shape) == 3 and image.shape[2] == 3:  # BGR or RGB
                    image_bgr = image
                else:
                    continue  # Skip unsupported formats
                
                success, jpeg_data = cv2.imencode(".jpg", image_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
                if not success:
                    continue
                
                image_msg = {
                    "timestamp": {"sec": ts_sec, "nsec": ts_nsec},
                    "frame_id": camera_id,
                    "data": base64.b64encode(jpeg_data.tobytes()).decode("ascii"),
                    "format": "jpeg"
                }
                
                self._writer.add_message(
                    channel_id=self._channels[channel_name],
                    sequence=0,
                    log_time=time_ns,
                    publish_time=time_ns,
                    data=json.dumps(image_msg).encode("utf-8")
                )

    def _write_audio(self, audio_data, time_ns, ts_sec, ts_nsec):
        """Write audio data to MCAP"""
        if "audio" not in self._channels:
            self._channels["audio"] = self._writer.register_channel(
                topic="/audio/microphone",
                message_encoding="json",
                schema_id=self._schemas["audio"]
            )
        
        # Assume audio_data is a dict with 'data', 'sample_rate', 'encoding'
        audio_msg = {
            "timestamp": {"sec": ts_sec, "nsec": ts_nsec},
            "frame_id": "microphone",
            "encoding": audio_data.get("encoding", "pcm_f32le"),
            "sample_rate": audio_data.get("sample_rate", 44100),
            "data": base64.b64encode(audio_data["data"]).decode("ascii") if isinstance(audio_data["data"], bytes) else audio_data["data"]
        }
        
        self._writer.add_message(
            channel_id=self._channels["audio"],
            sequence=0,
            log_time=time_ns,
            publish_time=time_ns,
            data=json.dumps(audio_msg).encode("utf-8")
        )

    def _write_vr_controller(self, controller_info, time_ns, ts_sec, ts_nsec):
        """Write VR controller data to MCAP"""
        if "vr_controller" not in self._channels:
            self._channels["vr_controller"] = self._writer.register_channel(
                topic="/vr_controller",
                message_encoding="json",
                schema_id=self._schemas["vr_controller"]
            )
        
        # Structure VR controller message
        vr_msg = {
            "timestamp": {"sec": ts_sec, "nsec": ts_nsec},
            "poses": controller_info.get("poses", {}),
            "buttons": controller_info.get("buttons", {}),
            "movement_enabled": controller_info.get("movement_enabled", False),
            "controller_on": controller_info.get("controller_on", True),
            "success": controller_info.get("success", False),
            "failure": controller_info.get("failure", False)
        }
        
        # Convert numpy arrays in poses to lists for JSON serialization
        if "poses" in vr_msg and vr_msg["poses"]:
            for pose_key, pose_matrix in vr_msg["poses"].items():
                if hasattr(pose_matrix, 'tolist'):
                    vr_msg["poses"][pose_key] = pose_matrix.tolist()
                elif isinstance(pose_matrix, np.ndarray):
                    vr_msg["poses"][pose_key] = pose_matrix.flatten().tolist()
        
        self._writer.add_message(
            channel_id=self._channels["vr_controller"],
            sequence=0,
            log_time=time_ns,
            publish_time=time_ns,
            data=json.dumps(vr_msg).encode("utf-8")
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
        # Add final metadata
        if metadata is not None:
            self._update_metadata(metadata)

        # Finish remaining jobs
        [queue.join() for queue in self._queue_dict.values()]

        # Close MCAP writer
        self._writer.finish()
        self._mcap_file.close()
        self._open = False 