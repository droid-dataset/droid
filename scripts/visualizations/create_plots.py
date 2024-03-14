import os

import matplotlib.pyplot as plt

from droid.plotting.analysis_func import *
from droid.plotting.misc import *
from droid.plotting.text import *

# Gather Graphical Data #
data_path = None  # "/Volumes/DROID_Drive/MyDrive/DROID: Weekly Lab Data/IPRL"
dir_path = os.path.dirname(os.path.realpath(__file__))
data_directory = os.path.join(dir_path, "../../", "data") if data_path is None else data_path
PLOT_FOLDERPATH = os.path.join(dir_path, "../../", "plots")
if not os.path.exists(PLOT_FOLDERPATH):
    os.makedirs(PLOT_FOLDERPATH)

# Run Data Crawler #
data_crawler(data_directory, func_list=[analysis_func])

# Prepare Cumulative Values #
cumulative_dicts = [traj_progress_dict, scene_progress_dict]
for curr_dict in cumulative_dicts:
    all_dict_keys = list(curr_dict.keys())
    for key in all_dict_keys:
        curr_dict[key] = np.cumsum(curr_dict[key])
        curr_dict["DROID"] += curr_dict[key]

# Make Figure #
fig = plt.figure()

# Plot Trajectory Progress #
plt.xticks(all_month_timestamps, labels=all_month_names)
for key in traj_progress_dict:
    lab_progress = traj_progress_dict[key]
    plt.plot(DAY_TIMESTAMPS, lab_progress, label=key)

plt.legend(loc="center left", bbox_to_anchor=(1, 0.5))
plt.title("Trajectories Collected", fontweight="bold")
plt.savefig(PLOT_FOLDERPATH + "/trajectory_progress.png", bbox_inches="tight")

# Plot Scene Progress #
plt.clf()
plt.xticks(all_month_timestamps, labels=all_month_names)
for key in scene_progress_dict:
    lab_progress = scene_progress_dict[key]
    plt.plot(DAY_TIMESTAMPS, lab_progress, label=key)

plt.legend(loc="center left", bbox_to_anchor=(1, 0.5))
plt.title("Scenes Collected", fontweight="bold")
plt.savefig(PLOT_FOLDERPATH + "/scene_progress.png", bbox_inches="tight")

# Plot Week Summary #
plt.clf()
weekly_threshold = 150000
lab_names = list(weekly_progress_dict.keys())
lab_quantities = [weekly_progress_dict[key] for key in lab_names]
plt.bar(lab_names, lab_quantities)
plt.axhline(weekly_threshold, color="black", ls="dotted")
plt.title("Week Summary: Samples Collected", fontweight="bold")
plt.savefig(PLOT_FOLDERPATH + "/week_progress.png", bbox_inches="tight")

# Plot User Progress #
plt.clf()
user_threshold = 500000
user_names = list(user_progress_dict.keys())
user_quantities = [user_progress_dict[key] for key in user_names]
tick_names = ["{0}K".format(100 * i) if i < 10 else "1M" for i in range(6)]
tick_values = [1e5 * i for i in range(len(tick_names))]
plt.xticks(tick_values, labels=tick_names)
plt.barh(user_names, user_quantities)
plt.axvline(user_threshold, color="blue", ls="dotted", label="Standard Requirement")
plt.axvline(user_threshold // 2, color="green", ls="dotted", label="Lab Lead Requirement")
plt.title("Per Person Progress", fontweight="bold")
plt.xlabel("Data Points Collected")
plt.legend(loc="center left", bbox_to_anchor=(1, 0.5))
plt.savefig(PLOT_FOLDERPATH + "/personal_progress.png", bbox_inches="tight")

# Plot Task Distribution #
plt.clf()
task_names = list(task_distribution_dict.keys())
task_quantities = [task_distribution_dict[key] for key in task_names]
sections, texts = plt.pie(task_quantities)
plt.legend(sections, task_names, loc="center left", bbox_to_anchor=(1, 0.5))
plt.title("Task Distribution", fontweight="bold")
plt.savefig(PLOT_FOLDERPATH + "/task_distribution.png", bbox_inches="tight")

# Plot Trajectory Length Distribution #
plt.clf()
plt.hist(all_traj_lengths, bins=100)
plt.xlim([0, 1000])
plt.title("Horizon Distribution", fontweight="bold")
plt.savefig(PLOT_FOLDERPATH + "/horizon_distribution.png", bbox_inches="tight")

# Plot Camera Pose Distribution #
plt.clf()
ax_pos = fig.add_subplot(1, 2, 1, projection="3d")
ax_ang = fig.add_subplot(1, 2, 2, projection="3d")
pos_values, pos_density, ang_values, ang_density = estimate_pos_angle_density(all_camera_poses)
ax_pos.scatter(pos_values[0], pos_values[1], pos_values[2], c=pos_density, cmap="viridis", linewidth=0.5)
ax_ang.scatter(ang_values[0], ang_values[1], ang_values[2], c=ang_density, cmap="viridis", linewidth=0.5)
ax_pos.set_title("Camera Positions", fontweight="bold")
ax_ang.set_title("Camera Angles", fontweight="bold")
ax_pos.view_init(elev=20, azim=-23)
ax_ang.view_init(elev=14, azim=-143)
plt.savefig(PLOT_FOLDERPATH + "/camera_poses.png", bbox_inches="tight")
plt.show()
