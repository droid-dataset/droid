source ~/miniconda3/etc/profile.d/conda.sh
conda activate polymetis-local
pkill -9 run_server
pkill -9 franka_panda_cl
launch_robot.py robot_client=franka_hardware
