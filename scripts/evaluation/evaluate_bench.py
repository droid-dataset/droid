# ruff: noqa
"""PolaRiS Bench eval entry point.

Runs a policy on a task config defined by an institution, records full HDF5
trajectories (with per-camera MP4 streams) via TrajectoryWriter, and prompts
the operator for the task-specific rubric after every rollout.
"""

import contextlib
import dataclasses
import datetime
import faulthandler
import json
import signal
import subprocess
import time
from pathlib import Path

import numpy as np
import tqdm
import tyro
from moviepy import ImageSequenceClip
from openpi_client import image_tools
from openpi_client import websocket_client_policy
from PIL import Image

import droid.misc.parameters as params
from droid.evaluation.scoring import prompt_rubric
from droid.evaluation.task_config import TaskConfig, load_task
from droid.robot_env import RobotEnv
from droid.trajectory_utils.trajectory_writer import TrajectoryWriter

faulthandler.enable()

DROID_CONTROL_FREQUENCY = 15
DEFAULT_MAX_TIMESTEPS = 450


@dataclasses.dataclass
class Args:
    task_config: Path
    policy_name: str
    operator: str

    output_dir: Path = Path("runs")
    n_episodes: int = 1

    left_camera_id: str = params.varied_camera_1_id
    right_camera_id: str = "<>"
    wrist_camera_id: str = params.hand_camera_id
    external_camera: str = "left"

    open_loop_horizon: int = 8
    remote_host: str = "0.0.0.0"
    remote_port: int = 8000


@contextlib.contextmanager
def prevent_keyboard_interrupt():
    interrupted = False
    original_handler = signal.getsignal(signal.SIGINT)

    def handler(signum, frame):
        nonlocal interrupted
        interrupted = True

    signal.signal(signal.SIGINT, handler)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, original_handler)
        if interrupted:
            raise KeyboardInterrupt


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parent, stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return "unknown"


def _extract_observation(args: Args, obs_dict, *, save_to_disk=False):
    image_observations = obs_dict["image"]
    left_image, right_image, wrist_image = None, None, None
    for key in image_observations:
        if args.left_camera_id in key and "left" in key:
            left_image = image_observations[key]
        elif args.right_camera_id in key and "left" in key:
            right_image = image_observations[key]
        elif args.wrist_camera_id in key and "left" in key:
            wrist_image = image_observations[key]

    left_image = left_image[..., :3] if left_image is not None else None
    right_image = right_image[..., :3] if right_image is not None else None
    wrist_image = wrist_image[..., :3]

    left_image = left_image[..., ::-1] if left_image is not None else None
    right_image = right_image[..., ::-1] if right_image is not None else None
    wrist_image = wrist_image[..., ::-1]

    robot_state = obs_dict["robot_state"]
    cartesian_position = np.array(robot_state["cartesian_position"])
    joint_position = np.array(robot_state["joint_positions"])
    gripper_position = np.array([robot_state["gripper_position"]])

    if save_to_disk:
        combined_image = np.concatenate([left_image, wrist_image, right_image], axis=1)
        Image.fromarray(combined_image).save("robot_camera_views.png")

    return {
        "left_image": left_image,
        "right_image": right_image,
        "wrist_image": wrist_image,
        "cartesian_position": cartesian_position,
        "joint_position": joint_position,
        "gripper_position": gripper_position,
    }


def _build_timestep(curr_obs: dict, action: np.ndarray, args: Args) -> dict:
    images = {}
    if curr_obs.get("left_image") is not None:
        images[f"{args.left_camera_id}_left"] = np.ascontiguousarray(curr_obs["left_image"])
    if curr_obs.get("right_image") is not None:
        images[f"{args.right_camera_id}_left"] = np.ascontiguousarray(curr_obs["right_image"])
    if curr_obs.get("wrist_image") is not None:
        images[f"{args.wrist_camera_id}_left"] = np.ascontiguousarray(curr_obs["wrist_image"])
    return {
        "observation": {
            "image": images,
            "robot_state": {
                "cartesian_position": curr_obs["cartesian_position"],
                "joint_position": curr_obs["joint_position"],
                "gripper_position": curr_obs["gripper_position"],
            },
            "timestamp": {"step_time": time.time()},
        },
        "action": {
            "joint_position": np.asarray(action[:-1]),
            "gripper_position": np.asarray(action[-1:]),
        },
    }


def _run_episode(args: Args, task: TaskConfig, env: RobotEnv, policy_client, episode_idx: int) -> None:
    assert args.external_camera in ("left", "right"), f"Invalid external_camera: {args.external_camera}"

    timestamp = datetime.datetime.now().strftime("%Y_%m_%d_%H:%M:%S")
    episode_dir = (
        args.output_dir
        / task.institution
        / task.task_id
        / args.policy_name
        / timestamp
    )
    episode_dir.mkdir(parents=True, exist_ok=True)
    trajectory_path = episode_dir / "trajectory.h5"
    preview_path = episode_dir / "video_preview.mp4"
    scores_path = episode_dir / "scores.json"

    max_timesteps = task.max_timesteps or DEFAULT_MAX_TIMESTEPS

    metadata = {
        "institution": task.institution,
        "task_id": task.task_id,
        "language_instruction": task.language_instruction,
        "success_criteria": task.success_criteria,
        "policy_name": args.policy_name,
        "operator": args.operator,
        "timestamp": timestamp,
        "episode_idx": episode_idx,
        "max_timesteps": max_timesteps,
        "open_loop_horizon": args.open_loop_horizon,
        "external_camera": args.external_camera,
        "droid_git_sha": _git_sha(),
    }

    writer = TrajectoryWriter(str(trajectory_path), metadata=metadata, save_images=True, save_depth=False)

    actions_from_chunk_completed = 0
    pred_action_chunk = None
    preview_frames = []
    early_terminated = False
    completed_steps = 0

    print(f"\n[ep {episode_idx + 1}/{args.n_episodes}] task={task.task_id} policy={args.policy_name}")
    print(f"  instruction: {task.language_instruction}")
    print(f"  output: {episode_dir}")
    print("  rollout running — Ctrl+C to stop early")

    for t_step in tqdm.tqdm(range(max_timesteps)):
        start_time = time.time()
        try:
            curr_obs = _extract_observation(args, env.get_observation(), save_to_disk=False)

            external = image_tools.resize_with_pad(curr_obs[f"{args.external_camera}_image"], 224, 224)
            wrist = image_tools.resize_with_pad(curr_obs["wrist_image"], 224, 224)
            preview_frames.append(np.concatenate([external, wrist], axis=1))

            if actions_from_chunk_completed == 0 or actions_from_chunk_completed >= args.open_loop_horizon:
                actions_from_chunk_completed = 0
                request_data = {
                    "observation/exterior_image_1_left": image_tools.resize_with_pad(
                        curr_obs[f"{args.external_camera}_image"], 224, 224
                    ),
                    "observation/wrist_image_left": image_tools.resize_with_pad(curr_obs["wrist_image"], 224, 224),
                    "observation/joint_position": curr_obs["joint_position"],
                    "observation/gripper_position": curr_obs["gripper_position"],
                    "prompt": task.language_instruction,
                }
                with prevent_keyboard_interrupt():
                    pred_action_chunk = policy_client.infer(request_data)["actions"]

            action = pred_action_chunk[actions_from_chunk_completed]
            actions_from_chunk_completed += 1

            if action[-1].item() > 0.5:
                action = np.concatenate([action[:-1], np.ones((1,))])
            else:
                action = np.concatenate([action[:-1], np.zeros((1,))])

            writer.write_timestep(_build_timestep(curr_obs, action, args))
            env.step(action)
            completed_steps = t_step + 1

            elapsed_time = time.time() - start_time
            if elapsed_time < 1 / DROID_CONTROL_FREQUENCY:
                time.sleep(1 / DROID_CONTROL_FREQUENCY - elapsed_time)
        except KeyboardInterrupt:
            early_terminated = True
            break

    if preview_frames:
        ImageSequenceClip(list(np.stack(preview_frames)), fps=30).write_videofile(str(preview_path), codec="libx264")

    print("\n  scoring rubric (operator input)")
    scores = prompt_rubric(task)

    flat_score_attrs = {
        "scores/highest_milestone": scores["highest_milestone"],
        "scores/task_complete": scores["task_complete"],
        "scores/notes": scores["notes"],
        **{f"scores/milestone/{name}": reached for name, reached in scores["milestone_reached"].items()},
    }
    writer.close(
        metadata={
            **flat_score_attrs,
            "completed_steps": completed_steps,
            "early_terminated": early_terminated,
        }
    )

    sidecar = {
        "task": {
            "institution": task.institution,
            "task_id": task.task_id,
            "language_instruction": task.language_instruction,
            "success_criteria": task.success_criteria,
        },
        "policy": {"name": args.policy_name},
        "operator": args.operator,
        "timestamp": timestamp,
        "episode_idx": episode_idx,
        "completed_steps": completed_steps,
        "early_terminated": early_terminated,
        "scores": scores,
        "paths": {
            "trajectory_h5": str(trajectory_path.relative_to(args.output_dir)),
            "video_preview": str(preview_path.relative_to(args.output_dir)),
        },
    }
    with scores_path.open("w") as f:
        json.dump(sidecar, f, indent=2)
    print(f"  saved scores -> {scores_path}")


def main(args: Args):
    task = load_task(args.task_config)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    env = RobotEnv(action_space="joint_position", gripper_action_space="position")
    print("Created the droid env!")
    policy_client = websocket_client_policy.WebsocketClientPolicy(args.remote_host, args.remote_port)

    for ep in range(args.n_episodes):
        _run_episode(args, task, env, policy_client, episode_idx=ep)
        env.reset()


if __name__ == "__main__":
    main(tyro.cli(Args))
