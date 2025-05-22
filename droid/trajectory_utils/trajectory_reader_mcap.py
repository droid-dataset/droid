import json
import base64
import numpy as np
import cv2
from collections import defaultdict

from mcap.reader import make_reader

class TrajectoryReaderMCAP:
    def __init__(self, filepath, read_images=True):
        self._filepath = filepath
        self._read_images = read_images
        
        # Open the MCAP file
        self._mcap_file = open(filepath, "rb")
        self._reader = make_reader(self._mcap_file)
        
        # Pre-process the file to determine length and structure
        self._channels = {}
        self._timestamps = []
        self._schemas = {}
        self._messages_by_timestamp = defaultdict(dict)
        
        # Scan all messages to build an index by timestamp
        for schema in self._reader.get_summary().schemas.values():
            self._schemas[schema.id] = schema
            
        for channel in self._reader.get_summary().channels.values():
            self._channels[channel.id] = channel
            
        # Collect all messages and organize by timestamp
        for msg in self._reader.iter_messages():
            channel = self._channels[msg.channel_id]
            topic = channel.topic
            
            # Parse the message to get timestamp
            try:
                msg_data = json.loads(msg.data.decode("utf-8"))
                if "timestamp" in msg_data:
                    ts_data = msg_data["timestamp"]
                    time_ns = ts_data["sec"] * 1_000_000_000 + ts_data["nsec"]
                else:
                    time_ns = msg.log_time
            except:
                time_ns = msg.log_time
            
            # Store this message keyed by topic
            self._messages_by_timestamp[time_ns][topic] = msg_data
        
        # Sort timestamps to ensure sequential access
        self._timestamps = sorted(self._messages_by_timestamp.keys())
        self._length = len(self._timestamps)
        self._index = 0

    def length(self):
        return self._length

    def read_timestep(self, index=None, keys_to_ignore=[]):
        # Make sure we read within range
        if index is None:
            index = self._index
        else:
            self._index = index
        
        if index >= self._length:
            return None
            
        self._index += 1

        # Get timestamp for this index
        time_ns = self._timestamps[index]
        messages = self._messages_by_timestamp[time_ns]
        
        # Construct the timestep dictionary with all messages at this timestamp
        timestep = {
            "observation": {
                "timestamp": {
                    "robot_state": {
                        "read_start": time_ns
                    }
                }
            }
        }
        
        # Process robot state
        if "/robot_state" in messages:
            robot_data = messages["/robot_state"]
            timestep["observation"]["robot_state"] = {
                "joint_positions": np.array(robot_data.get("joint_positions", [])),
                "joint_velocities": np.array(robot_data.get("joint_velocities", [])),
                "joint_efforts": np.array(robot_data.get("joint_efforts", [])),
                "cartesian_position": np.array(robot_data.get("cartesian_position", [])),
                "cartesian_velocity": np.array(robot_data.get("cartesian_velocity", [])),
                "gripper_position": robot_data.get("gripper_position", 0.0),
                "gripper_velocity": robot_data.get("gripper_velocity", 0.0)
            }
        
        # Process action data
        if "/action" in messages:
            action_data = messages["/action"]
            timestep["action"] = np.array(action_data.get("data", []))
        
        # Process camera images
        if self._read_images:
            image_dict = {}
            for topic, msg_data in messages.items():
                if topic.startswith("/camera/") and topic.endswith("/compressed"):
                    # Extract camera ID from topic like "/camera/12345_left/compressed"
                    camera_id = topic.split("/camera/")[1].split("/compressed")[0]
                    
                    # Decode base64 image data
                    if "data" in msg_data:
                        try:
                            img_bytes = base64.b64decode(msg_data["data"])
                            img_array = np.frombuffer(img_bytes, dtype=np.uint8)
                            image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                            if image is not None:
                                image_dict[camera_id] = image
                        except Exception as e:
                            print(f"Failed to decode image for camera {camera_id}: {e}")
                            continue
            
            if image_dict:
                timestep["observation"]["image"] = image_dict
        
        # Process audio data
        if "/audio/microphone" in messages:
            audio_data = messages["/audio/microphone"]
            try:
                audio_bytes = base64.b64decode(audio_data["data"])
                timestep["observation"]["audio"] = {
                    "data": audio_bytes,
                    "sample_rate": audio_data.get("sample_rate", 44100),
                    "encoding": audio_data.get("encoding", "pcm_f32le")
                }
            except Exception as e:
                print(f"Failed to decode audio data: {e}")
        
        # Process VR controller data
        if "/vr_controller" in messages:
            vr_data = messages["/vr_controller"]
            controller_info = {
                "poses": vr_data.get("poses", {}),
                "buttons": vr_data.get("buttons", {}),
                "movement_enabled": vr_data.get("movement_enabled", False),
                "controller_on": vr_data.get("controller_on", True),
                "success": vr_data.get("success", False),
                "failure": vr_data.get("failure", False)
            }
            
            # Convert pose lists back to numpy arrays
            if "poses" in controller_info and controller_info["poses"]:
                for pose_key, pose_list in controller_info["poses"].items():
                    if isinstance(pose_list, list) and len(pose_list) == 16:
                        # Reshape flat list back to 4x4 matrix
                        controller_info["poses"][pose_key] = np.array(pose_list).reshape(4, 4)
                    elif isinstance(pose_list, list):
                        controller_info["poses"][pose_key] = np.array(pose_list)
            
            timestep["observation"]["controller_info"] = controller_info
        
        return timestep

    def get_trajectory(self, keys_to_ignore=[]):
        """Read the entire trajectory as a list of timesteps"""
        trajectory = []
        for i in range(self._length):
            timestep = self.read_timestep(i, keys_to_ignore)
            if timestep is not None:
                trajectory.append(timestep)
        return trajectory

    def close(self):
        """Close the MCAP file"""
        if hasattr(self, '_mcap_file'):
            self._mcap_file.close() 