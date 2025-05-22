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
        for schema in self._reader.get_schemas():
            self._schemas[schema.id] = schema
            
        for channel in self._reader.get_channels():
            self._channels[channel.id] = channel
            
        # Group messages by timestamp
        for msg in self._reader.iter_messages():
            # Use log_time as our primary key for timesteps
            time_ns = msg.log_time
            
            # Add to our timestamps list if this is a new timestamp
            if time_ns not in self._messages_by_timestamp:
                self._timestamps.append(time_ns)
                
            # Get channel info
            channel = self._channels[msg.channel_id]
            topic = channel.topic
            
            # Store this message keyed by topic
            self._messages_by_timestamp[time_ns][topic] = msg
        
        # Sort timestamps to ensure sequential access
        self._timestamps.sort()
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
        assert index < self._length

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
        
        # Add robot state data if available
        if "/robot_state" in messages:
            robot_state_msg = messages["/robot_state"]
            robot_state_data = json.loads(robot_state_msg.data)
            timestep["observation"]["robot_state"] = robot_state_data["data"]
        
        # Add action data if available
        if "/action" in messages:
            action_msg = messages["/action"]
            action_data = json.loads(action_msg.data)
            timestep["action"] = action_data["data"]
            
        # Add camera extrinsics data if available
        if "/camera_extrinsics" in messages:
            extrinsics_msg = messages["/camera_extrinsics"]
            extrinsics_data = json.loads(extrinsics_msg.data)
            timestep["observation"]["camera_extrinsics"] = extrinsics_data["data"]
            
        # Add camera intrinsics data if available
        if "/camera_intrinsics" in messages:
            intrinsics_msg = messages["/camera_intrinsics"]
            intrinsics_data = json.loads(intrinsics_msg.data)
            timestep["observation"]["camera_intrinsics"] = intrinsics_data["data"]
            
        # Add camera type data if available
        if "/camera_type" in messages:
            camera_type_msg = messages["/camera_type"]
            camera_type_data = json.loads(camera_type_msg.data)
            timestep["observation"]["camera_type"] = camera_type_data["data"]
            
        # Add image data if requested and available
        if self._read_images:
            timestep["observation"]["image"] = {}
            
            # Process all camera topics
            for topic, msg in messages.items():
                if topic.startswith("/camera/") and topic.endswith("/compressed"):
                    # Extract camera ID from topic
                    camera_id = topic.split('/')[2]
                    
                    # Parse image data
                    image_data = json.loads(msg.data)
                    image_bytes = base64.b64decode(image_data["data"])
                    
                    # Convert to numpy array
                    img_np = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
                    
                    # Add to timestep
                    timestep["observation"]["image"][camera_id] = img_np
        
        # Increment read index
        self._index += 1
        
        # Return timestep
        return timestep

    def close(self):
        self._mcap_file.close() 