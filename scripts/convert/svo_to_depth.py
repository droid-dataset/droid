"""
Script for extracting MP4 data from SVO files.

Performs the following:
    - Checks for "cached" uploads in `DROID/cache/<lab>-cache.json; avoids repetitive work.
    - Parses out relevant metadata from each trajectory --> *errors* on "unexpected format" (fail-fast).
    - Converts all SVO files to the relevant Depth --> logs "corrupt" data (silent).
    - Runs validation logic on all *new* demonstrations --> errors on "corrupt" data (fail-fast).
    - Writes JSON metadata for all *new* demonstrations for easy data querying.
    - Uploads each demonstration "day" data to Amazon S3 bucket and updates `DROID/cache/<lab>-cache.json`.

IMPORTANT INFORMATION:
    - Resizing is done through the ZED SDK. Make sure you keep this consistent during policy evaluation.
    - Depth is given in millimeters, but before saving it we multiple the values by 1000 and convert to uint16
    - Upon decoding the depth, you should divide the values by 1000 to return to millimeters

Note :: Must run on hardware with the ZED SDK; highly recommended to run this on the data collection laptop directly!

Run from DROID directory root with: `python scripts/convert/svo_to_depth.py'


"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

import pyrallis

from droid.postprocessing.parse import parse_datetime
from droid.postprocessing.stages import run_indexing, run_processing
from droid.postprocessing.util.validate import validate_user2id

# Registry of known labs and associated users. Note that we canonicalize names as "<F>irst <L>ast".
#   => We map each "name" to a unique ID (8 characters); when adding new users, make sure to pick a unique ID!
#         + Simple ID generator --> python -c "import uuid; print(str(uuid.uuid4())[:8])"
# fmt: off
REGISTERED_MEMBERS: Dict[str, Dict[str, str]] = {
    "Lab Name": {
        "First Last": "4b1a56cc",
    },
}
validate_user2id(REGISTERED_MEMBERS)

# Try to be as consistent as possible using the "canonical" names in the dictionary above; however, for unavoidable
# cases (e.g., unfortunate typos, using names/nicknames interchangeably), update the dictionary below!
REGISTERED_ALIASES: Dict[str, Tuple[str, str]] = {
    **{user: (lab, user) for lab, users in REGISTERED_MEMBERS.items() for user in users},

    # Note: Add duplicates/typos below (follow format)!
    **{
        "First Last": ("Lab Name", "First Last"),
    }
}
# fmt: on

@dataclass
class DROIDConversionConfig:
    # fmt: off
    lab: str                                        # Lab ID (all uppercase) -- e.g., "CLVR", "ILIAD", "REAL"
    data_dir: Path = Path("data")                   # Path to top-level directory, if lab_agnostic=False it should contain "success"/"failure" directories
    lab_agnostic: bool = True                       # Determines whether to only convert your lab's data or all data

    # Stage Handling
    do_index: bool = True                           # Whether to run an initial indexing pass prior to processing stage
    do_process: bool = True                         # Whether to run processing (can skip if just want to upload)

    # Processing Details
    process_failures: bool = False                  # Whether to include failures in the processing stage
    extract_MP4_data: bool = False                  # Whether to extract MP4 data from the SVO files
    extract_depth_data: bool = True                 # Whether to extract depth data from the SVO files
    depth_resolution: tuple = (0,0)                 # Resolution to extract depth data at, use a value of (0,0) to avoid resizing
    depth_frequency: int = 1                        # The timestep frequency at which we extract depth data

    # Important :: Only update once you're sure *all* demonstrations prior to this date have been processed!
    #   > If not running low on disk, leave alone!
    start_date: str = "2023-01-01"                  # Start indexing/processing/uploading demos starting from this date

    # Cache Parameters
    cache_dir: Path = Path("cache/postprocessing")  # Relative path to `cache` directory; defaults to repository root
    # fmt: on


@pyrallis.wrap()
def postprocess(cfg: DROIDConversionConfig) -> None:
    print(f"[*] Starting Data Processing & Upload for Lab `{cfg.lab}`")

    # Initialize Cache Data Structure --> Load Uploaded/Processed List from `cache_dir` (if exists)
    #   => Note that in calls to each stage, cache is updated *in-place* (allows for the try/finally to work)
    cache = {
        "lab": cfg.lab,
        "start_date": cfg.start_date,
        "totals": {k: {"success": 0, "failure": 0} for k in ["scanned", "indexed", "processed", "uploaded", "errored"]},
        "scanned_paths": {"success": {}, "failure": {}},
        "indexed_uuids": {"success": {}, "failure": {}},
        "processed_uuids": {"success": {}, "failure": {}},
        "uploaded_uuids": {"success": {}, "failure": {}},
        "errored_paths": {"success": {}, "failure": {}},
    }
    os.makedirs(cfg.cache_dir, exist_ok=True)
    if (cfg.cache_dir / f"{cfg.lab}-cache.json").exists():
        with open(cfg.cache_dir / f"{cfg.lab}-cache.json", "r") as f:
            loaded_cache = json.load(f)

            # Only replace cache on matched `start_date` --> not an ideal solution (cache invalidation is hard!)
            if loaded_cache["start_date"] == cache["start_date"]:
                cache = loaded_cache

    # === Run Post-Processing Stages ===
    try:
        start_datetime = parse_datetime(cfg.start_date, mode="day")

        # Stage 1 --> "Indexing"
        if cfg.do_index:
            run_indexing(
                cfg.data_dir,
                cfg.lab,
                start_datetime,
                aliases=REGISTERED_ALIASES,
                members=REGISTERED_MEMBERS,
                totals=cache["totals"],
                scanned_paths=cache["scanned_paths"],
                indexed_uuids=cache["indexed_uuids"],
                errored_paths=cache["errored_paths"],
                process_failures=cfg.process_failures,
                lab_agnostic=cfg.lab_agnostic,
                search_existing_metadata=True,
            )
        else:
            print("[*] Stage 1 =>> Skipping Indexing!")

        # Stage 2 --> "Processing"
        if cfg.do_process:
            run_processing(
                cfg.data_dir,
                cfg.lab,
                aliases=REGISTERED_ALIASES,
                members=REGISTERED_MEMBERS,
                totals=cache["totals"],
                indexed_uuids=cache["indexed_uuids"],
                processed_uuids=cache["processed_uuids"],
                errored_paths=cache["errored_paths"],
                extract_MP4_data=cfg.extract_MP4_data,
                extract_depth_data=cfg.extract_depth_data,
                depth_resolution=cfg.depth_resolution,
                depth_frequency=cfg.depth_frequency,
                search_existing_metadata=True,
            )
        else:
            print("[*] Stage 2 =>> Skipping Processing!")


    finally:
        # Dump `cache` on any interruption!
        with open(cfg.cache_dir / f"{cfg.lab}-cache.json", "w") as f:
            json.dump(cache, f, indent=2)

        # Print Statistics
        print(
            "[*] Terminated Post-Processing Script --> Summary:\n"
            f"\t- Scanned:      {sum(cache['totals']['scanned'].values())}\n"
            f"\t- Indexed:      {sum(cache['totals']['indexed'].values())}\n"
            f"\t- Processed:    {sum(cache['totals']['processed'].values())}\n"
            f"\t- Uploaded:     {sum(cache['totals']['uploaded'].values())}\n"
            f"\t- Total Errors: {sum(cache['totals']['errored'].values())}\n"
            f"\t  -> Errors in `success/` [FIX IMMEDIATELY]: {cache['totals']['errored']['success']}\n"
            f"\t  -> Errors in `failure/` [VERIFY]: {cache['totals']['errored']['failure']}\n\n"
            f"[*] See `{cfg.lab}-cache.json` in {cfg.cache_dir} for more information!\n"
        )


if __name__ == "__main__":
    postprocess()
