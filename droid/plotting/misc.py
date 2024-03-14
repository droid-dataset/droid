import datetime
import os
import time

import h5py
import numpy as np
from dateutil.relativedelta import relativedelta
from scipy import stats

from droid.plotting.misc import *
from droid.plotting.text import *

# Define Data Crawler #
num_demos = 0


def data_crawler(dirname, func_list=None, ignore_failure=True):
    global num_demos
    subfolders = [f.path for f in os.scandir(dirname) if f.is_dir()]
    traj_files = [f.path for f in os.scandir(dirname) if (f.is_file() and "trajectory.h5" in f.path)]
    h5_file_exists = len(traj_files) == 1

    # Obey Success / Failure Requirements #
    if ignore_failure and "failure" in dirname:
        return

    # Process Data #
    if h5_file_exists:
        num_demos += 1
        print("Num Demos:", num_demos)

        for func in func_list:
            hdf5_file = h5py.File(traj_files[0], "r")
            func(traj_files[0], hdf5_file=hdf5_file)

    for child_dirname in subfolders:
        data_crawler(child_dirname, func_list=func_list, ignore_failure=ignore_failure)


def task_mapper(task_description):
    for curr_task in all_tasks:
        if curr_task in task_description:
            return curr_task
    return "Arbitrary user defined task"


def grab_3rd_person_extrinsics(camera_extrinsics, camera_type_dict):
    varied_extrinsics = []
    for cam_id in camera_type_dict:
        # Ignore Hand Camera #
        if camera_type_dict[cam_id][0] == 0:
            continue

        # Gather Relevant Poses #
        for full_id in camera_extrinsics:
            if cam_id in full_id:
                cam_pose = camera_extrinsics[full_id][0]
                varied_extrinsics.append(cam_pose)

    return varied_extrinsics


def estimate_pos_angle_density(pose_list):
    cleaned_poses = {tuple(pose) for pose in pose_list}
    stacked_values = np.vstack(list(cleaned_poses))
    pos_values = stacked_values[:, :3].T
    ang_values = stacked_values[:, 3:].T
    pos_density_func = stats.gaussian_kde(pos_values)
    ang_density_func = stats.gaussian_kde(ang_values)
    pos_density = pos_density_func(pos_values)
    ang_density = ang_density_func(ang_values)
    return pos_values, pos_density, ang_values, ang_density


# Useful Values #
START_TIME = 1677500000
min_dt = datetime.datetime.min.time()

# Discretize Time #
start_date = datetime.datetime.fromtimestamp(START_TIME)
end_date = datetime.datetime.fromtimestamp(time.time())
NUM_DAYS = (end_date - start_date).days + 1
DAY_TIMESTAMPS = [
    datetime.datetime.timestamp(
        datetime.datetime.combine(start_date + datetime.timedelta(days=i), datetime.datetime.min.time())
    )
    for i in range(NUM_DAYS)
]


def get_bucket_index(timestamp):
    date = datetime.datetime.fromtimestamp(timestamp)
    index = (date - start_date).days
    return index


# Get Week Bracket #
today = datetime.date.today()
week_start_date = today - datetime.timedelta(days=today.weekday(), weeks=1)
week_end_date = week_start_date + datetime.timedelta(weeks=1)
week_start_dt = datetime.datetime.combine(week_start_date, min_dt)
week_end_dt = datetime.datetime.combine(week_end_date, min_dt)
WEEK_START = datetime.datetime.timestamp(week_start_dt)
WEEK_END = datetime.datetime.timestamp(week_end_dt)

# Get Per Month Info #
all_month_names, all_month_timestamps = [], []
curr_dt = start_date.replace(day=1)
while curr_dt <= end_date:
    # Get Info #
    month_name = curr_dt.strftime("%b")
    month_dt = datetime.datetime.combine(curr_dt, min_dt)
    month_ts = datetime.datetime.timestamp(month_dt)
    all_month_names.append(month_name)
    all_month_timestamps.append(month_ts)

    # Increment #
    curr_dt += relativedelta(months=+1)
