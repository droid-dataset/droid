import glob
import json
import os

import cv2
from tqdm import tqdm

from droid.camera_utils.recording_readers.svo_reader import SVOReader
from droid.data_loading.trajectory_sampler import collect_data_folderpaths


def convert_svo_to_mp4(filepath, recording_folderpath):
    # Open SVO Reader #
    serial_number = filepath.split("/")[-1][:-4]
    camera = SVOReader(filepath, serial_number=serial_number)
    camera.set_reading_parameters(image=True, depth=False, pointcloud=False, concatenate_images=True)
    width, height = camera.get_frame_resolution()

    # Create MP4 Writer #
    video_output_path = os.path.join(recording_folderpath, "MP4", serial_number + ".mp4")
    timestamp_output_path = video_output_path[:-4] + "_timestamps.json"
    video_codec = cv2.VideoWriter_fourcc(*"mp4v")
    video_writer = cv2.VideoWriter(video_output_path, fourcc=video_codec, fps=15, frameSize=(width * 2, height))

    # Convert To MP4 #
    frame_count = camera.get_frame_count()
    received_timestamps = []

    for _i in range(frame_count):
        output = camera.read_camera(return_timestamp=True)
        if output is None:
            break
        else:
            data_dict, timestamp = output

        sbs_frame = data_dict["image"][serial_number]
        received_timestamps.append(timestamp)
        sbs_frame = cv2.cvtColor(sbs_frame, cv2.COLOR_BGRA2BGR)
        video_writer.write(sbs_frame)

    # Close Everything #
    camera.disable_camera()
    video_writer.release()

    with open(timestamp_output_path, "w") as jsonFile:
        json.dump(received_timestamps, jsonFile)


corrupted_traj = []
all_folderpaths = collect_data_folderpaths()
for folderpath in tqdm(all_folderpaths):
    recording_folderpath = os.path.join(folderpath, "recordings")
    mp4_folderpath = os.path.join(recording_folderpath, "MP4")
    svo_folderpath = os.path.join(recording_folderpath, "SVO")
    if not os.path.exists(mp4_folderpath):
        os.makedirs(mp4_folderpath)
    if not os.path.exists(svo_folderpath):
        os.makedirs(svo_folderpath)

    # Move Files To New Location #
    svo_files_to_move = glob.glob(recording_folderpath + "/*.svo")
    for f in svo_files_to_move:
        path_list = f.split("/")
        path_list.insert(len(path_list) - 1, "SVO")
        new_f = "/".join(path_list)
        os.rename(f, new_f)

    # Gather Files To Convert #
    svo_filepaths = glob.glob(svo_folderpath + "/*.svo")
    mp4_filepaths = glob.glob(mp4_folderpath + "/*.mp4")
    files_to_convert = []
    for f in svo_filepaths:
        serial_number = f.split("/")[-1][:-4]
        if not any([serial_number in f for f in mp4_filepaths]):
            files_to_convert.append(f)

    for f in mp4_filepaths:
        timestamp_filepath = f[:-4] + "_timestamps.json"
        if not os.path.exists(timestamp_filepath):
            files_to_convert.append(f)

        reader = cv2.VideoCapture(f)
        if reader.isOpened():
            reader.release()
        else:
            files_to_convert.append(f)

    # Convert Files #
    for f in files_to_convert:
        convert_svo_to_mp4(f, recording_folderpath)

    # Check Success #
    num_mp4 = len(glob.glob(mp4_folderpath + "/*.mp4"))
    num_svo = len(svo_filepaths)

    if num_svo > num_mp4:
        corrupted_traj.append(folderpath)

print("The following trajectories are corrupted: ")
for folderpath in corrupted_traj:
    print(folderpath)
