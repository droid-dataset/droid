"""
validate.py

Helper functions for validating almost every part of the postprocessing pipeline; the general principle is to
*fail-fast*; if there is any data in a format we don't recognize, we raise an informative error, and stop the
post-processing loop.

It is up to the individual users to correct these errors/manually override them.
"""
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict


# === Indexing / Formatting Validators ===
def validate_user2id(registered_lab_members: Dict[str, Dict[str, str]]) -> bool:
    unique_users, unique_ids = {}, {}
    for lab in sorted(registered_lab_members):
        for user, uuid in sorted(registered_lab_members[lab].items()):
            dup_user, dup_uuid = f"Duplicate User `{user}` in Lab `{lab}", f"Duplicate UUID `{uuid}` for User `{user}`"
            assert user not in unique_users, f"{dup_user}; already exists in Lab: {unique_users[user]}!"
            assert uuid not in unique_ids, f"{dup_uuid}; already exists for (Lab, User): {unique_ids[uuid]}!"
            unique_users[user], unique_ids[uuid] = lab, user

    # Global Uniqueness Assertion
    assert len(unique_users) == len(unique_ids), "Mismatch between number of unique Users and UUIDs!"
    return True


def validate_day_dir(day_dir: Path) -> bool:
    format_err_msg = f"Invalid directory `{day_dir}`; should match YYYY-MM-DD!"
    date_err_msg = f"Invalid directory `{day_dir}`; date is in the future!"
    assert re.match(r"^\d{4}-\d{2}-\d{2}", day_dir.name) is not None, format_err_msg
    assert datetime.strptime(day_dir.name, "%Y-%m-%d") <= datetime.now(), date_err_msg
    return True


def validate_svo_existence(trajectory_dir: Path) -> bool:
    svo_path = trajectory_dir / "recordings" / "SVO"
    if svo_path.exists() and (len([p for p in svo_path.iterdir() if p.name.endswith(".svo")]) == 3):
        return True

    # Check Common Failure Mode --> files at `trajectory_dir / recordings / *.svo`
    fallback_svo_path = trajectory_dir / "recordings"
    if fallback_svo_path.exists() and (len([p for p in fallback_svo_path.iterdir() if p.name.endswith(".svo")]) == 3):
        os.makedirs(svo_path, exist_ok=False)
        svo_files = list([p for p in fallback_svo_path.iterdir() if p.name.endswith(".svo")])
        for file in svo_files:
            shutil.move(file, svo_path / file.name)
        return len([p for p in svo_path.iterdir() if p.name.endswith(".svo")]) == 3

    return False


# === Metadata Record Validator ===
def validate_metadata_record(metadata_record: Dict) -> bool:
    for key in metadata_record:
        if metadata_record[key] is None:
            return False

    return True
