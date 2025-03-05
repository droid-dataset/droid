import h5py
import tyro
import numpy as np
import matplotlib.pyplot as plt
from dataclasses import dataclass
from rich.console import Console

from droid.robot_env import RobotEnv
from droid.trajectory_utils.misc import  replay_trajectory
from droid.trajectory_utils.trajectory_reader import TrajectoryReader

@dataclass
class Args:
    trajectory: str
    action_space: str = "joint_velocity"

def main(args: Args):
    console = Console()

    # Load traj
    console.print(f"Loading trajectory from: {args.trajectory}")

    # create robot environment
    action_space = args.action_space
    env = RobotEnv(action_space=action_space)
    console.print(f"[bold green]DROID Environment Ready![/bold green] with action space: [bold purple] {action_space} [/bold purple]")

    # replay
    recorded_traj_path = replay_trajectory(
                        env=env,
                        filepath=args.trajectory
                    )
    console.print(f"Replay trajectory dumped to: {recorded_traj_path}")
    env.close()

    # Compare results of joint error over time
    gt_traj = TrajectoryReader(args.trajectory, read_images=False)
    recorded_traj = TrajectoryReader(recorded_traj_path, read_images=False)

    assert gt_traj.length() == recorded_traj.length(), "Trajectory lengths do not match"
    horizon = gt_traj.length()
    errors = []
    for i in range(horizon):
        gt_timestep = gt_traj.read_timestep()
        recorded_timestep = recorded_traj.read_timestep()

        gt_joint_pos = gt_timestep["observations"]["robot_state"]["joint_positions"]
        recorded_joint_pos = recorded_timestep["observations"]["robot_state"]["joint_positions"]

        joint_error = gt_joint_pos - recorded_joint_pos
        errors.append(joint_error)

    # plot errors
    errors = np.array(errors)
    for i in range(errors.shape[1]):
        plt.plot(errors[:, i], label=f"joint_{i}")
    plt.legend()
    plt.xlabel("Time")
    plt.ylabel("Joint Error")
    plt.title("Joint Error Over Time")
    plt.show()

if __name__ == "__main__":
    args = tyro.cli(Args)
    main(args)