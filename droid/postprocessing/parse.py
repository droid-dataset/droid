"""
parse.py

Core parsing logic -- takes a path to a raw demonstration directory (comprised of `trajectory.h5` and the SVO
recordings), parses out the relevant structured information following the schema in `droid.postprocessing.schema`,
returning a JSON-serializable data record.
"""
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple
import os

import h5py
import json

from droid.postprocessing.schema import TRAJECTORY_SCHEMA


def parse_datetime(date_str: str, mode="day") -> datetime:
    if mode == "day":
        return datetime.strptime(date_str, "%Y-%m-%d")
    else:
        raise ValueError(f"Function `parse_datetime` mode `{mode}` not supported!")


def parse_user(
    trajectory_dir: Path, aliases: Dict[str, Tuple[str, str]], members: Dict[str, Dict[str, str]]
) -> Tuple[Optional[str], Optional[str]]:
    try:
        with h5py.File(trajectory_dir / "trajectory.h5", "r") as h5:
            user_alias = h5.attrs["user"].title()
            lab, user = aliases.get(user_alias, (None, None))

        assert user_alias in aliases, f"User alias `{user_alias}` not in REGISTERED_LAB_MEMBERS or REGISTERED_ALIASES!"
        assert lab in members, f"Lab `{lab}` not in REGISTERED_LAB_MEMBERS!"
        assert user in members[lab], f"Canonical user `{user}` not in REGISTERED_LAB_MEMBERS['{lab}']"

        return user, members[lab][user]

    except AssertionError as e:
        raise e

    except (KeyError, OSError, RuntimeError):
        # Invalid/Incomplete HDF5 File --> return invalid :: (None, None)
        return None, None

def parse_existing_metadata(trajectory_dir: str):
    dir_path = os.path.abspath(trajectory_dir)
    all_filepaths = [entry.path for entry in os.scandir(dir_path) if entry.is_file()]
    for filepath in all_filepaths:
        if 'metadata' in filepath:
            with open(filepath) as json_file:
                metadata = json.load(json_file)
            return metadata
    return None

def parse_data_directory(data_dir: str, lab_agnostic: bool = False, process_failures: bool = False):
    if lab_agnostic:
        data_dirs = [p for p in data_dir.iterdir() if p.is_dir()]
    else:
        data_dirs = [data_dir]

    paths_to_index = []
    for curr_dir in data_dirs:
        paths_to_index += [(p, p.name) for p in [curr_dir / "success"]]
        if process_failures:
            paths_to_index += [(p, p.name) for p in [curr_dir / "failure"]]

    return paths_to_index


def parse_timestamp(trajectory_dir: Path) -> str:
    for pattern in [
        "%a_%b__%d_%H:%M:%S_%Y",
        "%a_%b_%d_%H:%M:%S_%Y",  # Colon
        "%a_%b__%d_%H_%M_%S_%Y",
        "%a_%b_%d_%H_%M_%S_%Y",  # Underscore
        "%a_%b__%d_%H:%M:%S_%Y",
        "%a_%b_%d_%H:%M:%S_%Y",  # Slash
    ]:
        try:
            return datetime.strptime(trajectory_dir.name, pattern).strftime("%Y-%m-%d-%Hh-%Mm-%Ss")
        except ValueError as e:
            assert ("time data" in str(e)) and ("does not match format" in str(e))
            continue

    # Invalid Trajectory Directory Path --> wonky timestamp! Check for common failure cases, then error.
    try:
        _ = datetime.strptime(trajectory_dir.name, "%Y-%m-%d")
        raise AssertionError(f"Unexpected Directory `{trajectory_dir}` -- did you accidentally nest directories?")
    except ValueError as e:
        raise AssertionError(f"Invalid Directory `{trajectory_dir}` -- check timestamp format!") from e


def parse_trajectory(
    data_dir: Path, trajectory_dir: Path, uuid: str, lab: str, user: str, user_id: str, timestamp: str
) -> Tuple[bool, Optional[Dict]]:
    """Attempt to parse `<trajectory>/trajectory.h5` and extract relevant elements into a JSON-valid record."""
    try:
        with h5py.File(trajectory_dir / "trajectory.h5", "r") as h5:
            assert "action" in h5.keys(), "Incomplete HDF5 file; no actual trajectory data logged!"
            trajectory_record, attrs, trajectory_length = {}, h5.attrs, int(h5["action"]["joint_position"].shape[0])
            exts = ["ext1", "ext2"]

            # Extract Camera Information
            camera_types, camera_extrinsics = h5["observation"]["camera_type"], h5["observation"]["camera_extrinsics"]
            ctype2extrinsics = {
                "wrist" if camera_types[serial][0] == 0 else exts.pop(0): {
                    "serial": serial,
                    "extrinsics": camera_extrinsics[f"{serial}_left"][0],
                }
                for serial in sorted(camera_types.keys())
            }

            # Compute Relative Path to `trajectory.h5`
            hdf5_path = str(trajectory_dir.relative_to(data_dir) / "trajectory.h5")

            # Populate Record
            for cname, etl_fn in TRAJECTORY_SCHEMA.items():
                trajectory_record[cname] = etl_fn(
                    uuid=uuid,
                    lab=lab,
                    user=user,
                    user_id=user_id,
                    timestamp=timestamp,
                    hdf5_path=hdf5_path,
                    attrs=attrs,
                    trajectory_length=trajectory_length,
                    ctype2extrinsics=ctype2extrinsics,
                )

            return True, trajectory_record

    except (AssertionError, KeyError, OSError, RuntimeError):
        # Invalid/Incomplete HDF5 File --> return invalid!
        return False, None
