"""
stages.py

Functions capturing logic for the various postprocessing stages:
    - Stage 1 :: "Indexing"  -->  Quickly iterate through all data, identifying formatting errors & naively counting
                                  total number of demonstrations to process/convert/upload.

                                  Note :: Raises hard exceptions on any unexpected directory/file formatting!

    - Stage 2 :: "Processing" --> Walk through data, extract & validate metadata (writing a JSON record for each unique
                                  demonstration). Additionally, runs conversion from SVO --> MP4.

                                  Note :: Logs corrupt HDF5/SVO files & raises warning at end of stage.

    - Stage 3 :: "Uploading" -->  Iterates through individual processed demonstration directories, and uploads them
                                  sequentially to the AWS S3 Bucket (via `boto`).

The outputs/failures of each stage are logged to a special cache data structure that prevents redundant work where
possible. Note that to emphasize readability, some of the following code is intentionally redundant.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple

import boto3
from tqdm import tqdm

from droid.postprocessing.parse import parse_datetime, parse_timestamp, parse_trajectory, parse_user, parse_existing_metadata, parse_data_directory
from droid.postprocessing.util.svo2mp4 import convert_mp4s
from droid.postprocessing.util.svo2depth import convert_depths
from droid.postprocessing.util.validate import validate_day_dir, validate_metadata_record, validate_svo_existence


# === Stage 1 :: Indexing ===
def run_indexing(
    data_dir: Path,
    lab: str,
    start_datetime: datetime,
    aliases: Dict[str, Tuple[str, str]],
    members: Dict[str, Dict[str, str]],
    totals: Dict[str, Dict[str, int]],
    scanned_paths: Dict[str, Dict[str, str]],
    indexed_uuids: Dict[str, Dict[str, str]],
    errored_paths: Dict[str, Dict[str, str]],
    search_existing_metadata: bool = False,
    lab_agnostic: bool = False,
    process_failures: bool = True,
) -> None:
    """Index data by iterating through each "success/ | failure/" --> <DAY>/ --> <TIMESTAMP>/ (specified trajectory)."""
    progress = tqdm(desc="[*] Stage 1 =>> Indexing")

    paths_to_index = parse_data_directory(data_dir, lab_agnostic=lab_agnostic, process_failures=process_failures)

    for outcome_dir, outcome in paths_to_index:
        if outcome == "failure" and not outcome_dir.exists():
            # Note: Some labs don't have failure trajectories...
            continue

        day_dirs = sorted([p for p in outcome_dir.iterdir() if p.is_dir() and validate_day_dir(p)])
        for day_dir, day in [(p, p.name) for p in day_dirs]:
            if parse_datetime(day) < start_datetime:
                continue

            for trajectory_dir in [p for p in day_dir.iterdir() if p.is_dir()]:
                rel_trajectory_dir = str(trajectory_dir.relative_to(data_dir))

                # Extract Timestamp (from `trajectory_dir`) and User, User ID (from `trajectory.h5`)
                existing_metadata_found = False
                if search_existing_metadata:
                    metadata = parse_existing_metadata(trajectory_dir)
                    if metadata is not None:
                        timestamp = metadata['timestamp']
                        user = metadata['user']
                        user_id = metadata['user_id']
                        uuid = metadata['uuid']
                        existing_metadata_found = True
                if not (search_existing_metadata and existing_metadata_found):
                    timestamp = parse_timestamp(trajectory_dir)
                    user, user_id = parse_user(trajectory_dir, aliases, members)

                    # Create Trajectory UUID --> <LAB>+<USER_ID>+YYYY-MM-DD-{24 Hour}h-{Min}m-{Sec}s
                    uuid = f"{lab}+{user_id}+{timestamp}"

                if user is None or user_id is None:
                    scanned_paths[outcome][rel_trajectory_dir] = True
                    errored_paths[outcome][rel_trajectory_dir] = (
                        "[Indexing Error] Missing/Invalid HDF5! "
                        "If the HDF5 is missing/corrupt, you can delete this trajectory!"
                    )
                    totals["scanned"][outcome] = len(scanned_paths[outcome])
                    totals["errored"][outcome] = len(errored_paths[outcome])
                    progress.update()
                    continue

                # Verify SVO Files
                if not validate_svo_existence(trajectory_dir):
                    scanned_paths[outcome][rel_trajectory_dir] = True
                    errored_paths[outcome][rel_trajectory_dir] = (
                        "[Indexing Error] Missing SVO Files! "
                        "Ensure all 3 SVO files are in `<timestamp>/recordings/SVO/<serial>.svo!"
                    )
                    totals["scanned"][outcome] = len(scanned_paths[outcome])
                    totals["errored"][outcome] = len(errored_paths[outcome])
                    progress.update()
                    continue

                # Otherwise -- we're good for indexing!
                indexed_uuids[outcome][uuid] = rel_trajectory_dir
                scanned_paths[outcome][rel_trajectory_dir] = True
                errored_paths[outcome].pop(rel_trajectory_dir, None)
                totals["scanned"][outcome] = len(scanned_paths[outcome])
                totals["indexed"][outcome] = len(indexed_uuids[outcome])
                totals["errored"][outcome] = len(errored_paths[outcome])
                progress.update()


# === Stage 2 :: Processing ===
def run_processing(
    data_dir: Path,
    lab: str,
    aliases: Dict[str, Tuple[str, str]],
    members: Dict[str, Dict[str, str]],
    totals: Dict[str, Dict[str, int]],
    indexed_uuids: Dict[str, Dict[str, str]],
    processed_uuids: Dict[str, Dict[str, str]],
    errored_paths: Dict[str, Dict[str, str]],
    process_batch_limit: int = 250,
    search_existing_metadata: bool = False,
    extract_MP4_data: bool = True,
    extract_depth_data: bool = False,
    depth_resolution: tuple = (0,0),
    depth_frequency: int = 1,
) -> None:
    """Iterate through each trajectory in `indexed_uuids` and 1) extract JSON metadata and 2) convert SVO -> MP4."""
    for outcome in indexed_uuids:
        uuid2trajectory_generator, counter = indexed_uuids[outcome].items(), 0
        for uuid, rel_trajectory_dir in tqdm(uuid2trajectory_generator, desc=f"[*] Stage 2 =>> `{outcome}` Processing"):
            if uuid in processed_uuids[outcome]:
                continue

            trajectory_dir = data_dir / rel_trajectory_dir
            
            existing_metadata_found = False
            if search_existing_metadata:
                metadata = parse_existing_metadata(trajectory_dir)
                if metadata is not None:
                    metadata_record = metadata
                    timestamp = metadata['timestamp']
                    user = metadata['user']
                    user_id = metadata['user_id']
                    uuid = metadata['uuid']
                    existing_metadata_found = True
                    valid_parse = True
            if not (search_existing_metadata and existing_metadata_found):
                timestamp = parse_timestamp(trajectory_dir)
                user, user_id = parse_user(trajectory_dir, aliases, members)

                # Run Metadata Extraction --> JSON-serializable Data Record + Validation
                valid_parse, metadata_record = parse_trajectory(
                    data_dir, trajectory_dir, uuid, lab, user, user_id, timestamp
                )
            if not valid_parse:
                errored_paths[outcome][rel_trajectory_dir] = "[Processing Error] JSON Metadata Parse Error"
                totals["errored"][outcome] = len(errored_paths[outcome])
                continue

            # Convert SVOs --> MP4s
            if extract_MP4_data:
                valid_convert, vid_paths = convert_mp4s(
                    data_dir,
                    trajectory_dir,
                    metadata_record["wrist_cam_serial"],
                    metadata_record["ext1_cam_serial"],
                    metadata_record["ext2_cam_serial"],
                    metadata_record["ext1_cam_extrinsics"],
                    metadata_record["ext2_cam_extrinsics"],
                )
                if not valid_convert:
                    errored_paths[outcome][rel_trajectory_dir] = "[Processing Error] Corrupted SVO / Failed Conversion"
                    totals["errored"][outcome] = len(errored_paths[outcome])
                    continue

                # Extend Metadata Record
                for key, vid_path in vid_paths.items():
                    metadata_record[key] = vid_path

            # Convert SVOs --> Depth
            if extract_depth_data:
                valid_convert, vid_paths = convert_depths(
                    data_dir,
                    trajectory_dir,
                    metadata_record["wrist_cam_serial"],
                    metadata_record["ext1_cam_serial"],
                    metadata_record["ext2_cam_serial"],
                    metadata_record["ext1_cam_extrinsics"],
                    metadata_record["ext2_cam_extrinsics"],
                    resolution=depth_resolution,
                    frequency=depth_frequency,
                )
                if not valid_convert:
                    errored_paths[outcome][rel_trajectory_dir] = "[Processing Error] Corrupted SVO / Failed Conversion"
                    totals["errored"][outcome] = len(errored_paths[outcome])
                    continue

                # Extend Metadata Record
                for key, vid_path in vid_paths.items():
                    metadata_record[key] = vid_path

            # Validate
            if not validate_metadata_record(metadata_record):
                errored_paths[outcome][rel_trajectory_dir] = "[Processing Error] Incomplete Metadata Record!"
                totals["errored"][outcome] = len(errored_paths[outcome])
                continue

            # Write JSON
            with open(trajectory_dir / f"metadata_{uuid}.json", "w") as f:
                json.dump(metadata_record, f)

            # Otherwise --> we're good for processing!
            processed_uuids[outcome][uuid] = rel_trajectory_dir
            errored_paths[outcome].pop(rel_trajectory_dir, None)
            totals["processed"][outcome] = len(processed_uuids[outcome])
            totals["errored"][outcome] = len(errored_paths[outcome])
            counter += 1

            # Note :: ZED SDK has an unfortunate problem with segmentation faults after processing > 2000 videos.
            #         Unfortunately, no good way to catch/handle a segfault from Python --> instead we just set
            #         a max limit `process_batch_limit` and trust that caching works.
            if counter > process_batch_limit:
                print("[*] EXITING TO PREVENT SVO SEGFAULT!")
                return


# === Stage 3 :: Uploading ===
def run_upload(
    data_dir: Path,
    lab: str,
    credentials_json: Path,
    totals: Dict[str, Dict[str, int]],
    processed_uuids: Dict[str, Dict[str, str]],
    uploaded_uuids: Dict[str, Dict[str, str]],
    bucket_name: str = "droid-data",
    prefix: str = "lab-uploads/",
) -> None:
    """Iterate through each successfully processed trajectory in `processed_uuids` and upload to S3."""
    with open(credentials_json, "r") as f:
        credentials = json.load(f)

    # Initialize S3 Client from Credentials & Validate
    client = boto3.client(
        "s3", aws_access_key_id=credentials["AccessKeyID"], aws_secret_access_key=credentials["SecretAccessKey"]
    )
    response = client.head_bucket(Bucket=bucket_name)
    assert (
        response["ResponseMetadata"]["HTTPStatusCode"] == 200
    ), "Problem connecting to S3 bucket; verify credentials JSON file!"

    # Start Uploading
    for outcome in processed_uuids:
        uuid2trajectory_generator = processed_uuids[outcome].items()
        for uuid, rel_trajectory_dir in tqdm(uuid2trajectory_generator, desc=f"[*] Stage 3 =>> `{outcome}` Uploading"):
            if uuid in uploaded_uuids[outcome]:
                continue

            # Recursively walk through each file in the `trajectory_dir` and upload one at a time!
            trajectory_dir = data_dir / rel_trajectory_dir
            for child in tqdm(
                list(trajectory_dir.rglob("*")), desc=f"     => Uploading `{rel_trajectory_dir}`", leave=False
            ):
                if child.is_file():
                    s3_path = str(Path(prefix) / lab / child.relative_to(data_dir))
                    client.upload_file(str(child), Bucket=bucket_name, Key=s3_path)

            # If we've managed to upload all files without error, then we're good for uploading!
            uploaded_uuids[outcome][uuid] = rel_trajectory_dir
            totals["uploaded"][outcome] = len(uploaded_uuids[outcome])
