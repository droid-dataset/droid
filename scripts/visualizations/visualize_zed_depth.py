import cv2
import matplotlib.pyplot as plt
import numpy as np
import os
import fnmatch

from r2d2.trajectory_utils.misc import load_trajectory
from r2d2.camera_utils.recording_readers.svo_reader import SVOReader

def make_cv_disparity_image(disparity, max_disparity):
    vis_disparity = disparity / max_disparity
    vis_disparity[vis_disparity < 0.0] = 0.0
    vis_disparity[vis_disparity > 1.0] = 1.0
    vis_disparity = vis_disparity
    np_img = (vis_disparity * 255.0).astype(np.uint8)
    mapped = cv2.applyColorMap(np_img, cv2.COLORMAP_JET)
    mapped[vis_disparity < 1e-3, :] = 0
    mapped[vis_disparity > 1.0 - 1e-3, :] = 0
    return mapped

filepath = "INSERT PATH TO DATA FOLDER HERE (eg. /path/to/folder/Fri_Jul__7_14:57:48_2023)"
traj_filepath = os.path.join(filepath, "trajectory.h5")
recording_folderpath = os.path.join(filepath, "recordings/SVO")
traj = load_trajectory(traj_filepath, recording_folderpath=recording_folderpath, camera_kwargs={})

svo_files = []
for root, _, files in os.walk(recording_folderpath):
    for filename in files:
        if fnmatch.fnmatch(filename, "*.svo"):
            svo_files.append(os.path.join(root, filename))

cameras = []
frame_counts = []
serial_numbers = []
cam_matrices = []
cam_baselines = []

for svo_file in svo_files:
    # Open SVO Reader
    serial_number = svo_file.split("/")[-1][:-4]
    camera = SVOReader(svo_file, serial_number=serial_number)
    camera.set_reading_parameters(image=True, depth=True, pointcloud=False, concatenate_images=False)
    im_key = '%s_left' % serial_number
    # Intrinsics are the same for the left and the right camera
    cam_matrices.append(camera.get_camera_intrinsics()[im_key]['cameraMatrix'])
    cam_baselines.append(camera.get_camera_baseline())
    frame_count = camera.get_frame_count()
    cameras.append(camera)
    frame_counts.append(frame_count)
    serial_numbers.append(serial_number)

# return serial_numbers
cameras = [x for y, x in sorted(zip(serial_numbers, cameras))]
cam_matrices = [x for y, x in sorted(zip(serial_numbers, cam_matrices))]
cam_baselines = [x for y, x in sorted(zip(serial_numbers, cam_baselines))]
serial_numbers = sorted(serial_numbers)

assert frame_counts.count(frame_counts[0]) == len(frame_counts)

timestep = np.random.randint(frame_counts[0])
frame = traj[timestep]
obs = frame["observation"]
image_obs = obs["image"]
depth_obs = obs["depth"]

zed_depths = []
left_rgbs = []
right_rgbs = []

for i, cam_id in enumerate(serial_numbers):
    left_key, right_key = f"{cam_id}_left", f"{cam_id}_right"
    left_rgb, right_rgb = image_obs[left_key], image_obs[right_key] 
    left_rgbs.append(left_rgb)
    right_rgbs.append(right_rgb)
    # Note (Ashwin): depth from the left and right stereo pairs are the same
    # so I'm just arbitrarily picking one
    zed_depths.append(depth_obs[left_key])

images = []
for serial_num, zed_depth, left_rgb, right_rgb in zip(serial_numbers, zed_depths, left_rgbs, right_rgbs):
    zed_depth[np.isnan(zed_depth)] = 0
    zed_depth[np.isinf(zed_depth)] = 1_000
    zed_depth = zed_depth / 1_000
    zed_depth_vis = make_cv_disparity_image(np.array(zed_depth), 9.0)
    images.append(left_rgb)
    images.append(right_rgb)
    images.append(zed_depth_vis)

# Create a 3x3 subplot grid
fig, axes = plt.subplots(3, 3, figsize=(12, 5))
titles = ["Left RGB", "Right RGB", "ZED Depth"] * 3

# Iterate through the images and display them on the subplots
for i, ax in enumerate(axes.ravel()):
    if i < len(images):
        ax.imshow(cv2.cvtColor(images[i], cv2.COLOR_BGR2RGB))
        if i < 3:
            ax.set_title(titles[i])
        ax.axis('off')

plt.savefig('depth_image_grid.png', bbox_inches='tight')