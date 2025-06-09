"""
schema.py

Schema & processing functions for extracting and formatting metadata from an individual DROID trajectory as a
JSON-serializable record. Converting to JSON provides a more friendly human-readable format, and facilitates downstream
tools for standing up a database/query engine.
"""
from typing import Callable, Dict, List, Optional


# === ETL Function Definitions ===
def get_uuid(*, uuid: str, **_) -> str:
    return uuid


def get_lab(*, lab: str, **_) -> str:
    return lab


def get_user(*, user: str, **_) -> str:
    return user


def get_user_id(*, user_id: str, **_) -> str:
    return user_id


def get_date(*, timestamp: str, **_) -> str:
    return timestamp[:10]  # YYYY-MM-DD


def get_timestamp(*, timestamp: str, **_) -> str:
    return timestamp


def get_hdf5_path(*, hdf5_path: str, **_) -> str:
    return hdf5_path


def get_building(*, attrs: Dict, **_) -> str:
    return attrs.get("building", "N/A")


def get_scene_id(*, attrs: Dict, **_) -> str:
    return int(attrs.get("scene_id", -1))


def get_success(*, attrs: Dict, **_) -> Optional[bool]:
    return bool(attrs["success"]) if "success" in attrs else None


def get_robot_serial(*, attrs: Dict, **_) -> str:
    return attrs.get("robot_serial_number", "unknown")


def get_droid_version(*, attrs: Dict, **_) -> str:
    return str(attrs.get("version_number", "-1.0"))


def get_current_task(*, attrs: Dict, **_) -> str:
    return attrs["current_task"]


def get_trajectory_length(*, trajectory_length: int, **_) -> int:
    return trajectory_length


def get_wrist_cam_serial(*, ctype2extrinsics: Dict, **_) -> str:
    return ctype2extrinsics["wrist"]["serial"]


def get_ext1_cam_serial(*, ctype2extrinsics: Dict, **_) -> str:
    return ctype2extrinsics["ext1"]["serial"]


def get_ext2_cam_serial(*, ctype2extrinsics: Dict, **_) -> str:
    return ctype2extrinsics["ext2"]["serial"]


def get_wrist_cam_extrinsics(*, ctype2extrinsics: Dict, **_) -> List[float]:
    return ctype2extrinsics["wrist"]["extrinsics"].tolist()


def get_ext1_cam_extrinsics(*, ctype2extrinsics: Dict, **_) -> List[float]:
    return ctype2extrinsics["ext1"]["extrinsics"].tolist()


def get_ext2_cam_extrinsics(*, ctype2extrinsics: Dict, **_) -> List[float]:
    return ctype2extrinsics["ext2"]["extrinsics"].tolist()


def get_path_placeholder(**_) -> None:
    return None


# fmt: off
TRAJECTORY_SCHEMA: Dict[str, Callable] = {
    "uuid": get_uuid,
    "lab": get_lab,
    "user": get_user,
    "user_id": get_user_id,
    "date": get_date,
    "timestamp": get_timestamp,

    # === HDF5 Parameters ===
    "hdf5_path": get_hdf5_path,
    "building": get_building,
    "scene_id": get_scene_id,
    "success": get_success,
    "robot_serial": get_robot_serial,
    "droid_version": get_droid_version,

    # === Task Parameters ===
    "current_task": get_current_task,

    # === Trajectory Parameters ===
    "trajectory_length": get_trajectory_length,

    # === ZED Camera Parameters ===
    "wrist_cam_serial": get_wrist_cam_serial,
    "ext1_cam_serial": get_ext1_cam_serial,
    "ext2_cam_serial": get_ext2_cam_serial,

    # Camera Extrinsics for Third-Person Cameras (always assumes *left* stereo camera, ext1/ext2 sorted by serial #)
    #   => Extrinsics are saved as a 6-dim vector of [pos; rot] where:
    #       - `pos` is (x, y, z) offset --> moving left of robot is +y, moving right is -y
    #       - `rot` is rotation offset as Euler (`R.from_matrix(rmat).as_euler("xyz")`)
    "wrist_cam_extrinsics": get_wrist_cam_extrinsics,
    "ext1_cam_extrinsics": get_ext1_cam_extrinsics,
    "ext2_cam_extrinsics": get_ext2_cam_extrinsics,

    # Save SVO and MP4 Paths --> Paths are always "relative" to <LAB> directory!
    "wrist_svo_path": get_path_placeholder,
    "wrist_mp4_path": get_path_placeholder,
    "ext1_svo_path": get_path_placeholder,
    "ext1_mp4_path": get_path_placeholder,
    "ext2_svo_path": get_path_placeholder,
    "ext2_mp4_path": get_path_placeholder,

    # Mapping to "left" and "right" external MP4s --> computed heuristically...
    "left_mp4_path": get_path_placeholder,
    "right_mp4_path": get_path_placeholder,
}
# fmt: off
