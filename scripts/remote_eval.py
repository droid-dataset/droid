import dataclasses
import datetime
import faulthandler
import os

import numpy as np
import pandas as pd
import tqdm
import tyro
from moviepy.editor import ImageSequenceClip
from PIL import Image

from droid.robot_env import RobotEnv
from scripts import websocket_policy_client

faulthandler.enable()


@dataclasses.dataclass
class Args:
    # Required arguments
    policy_name: str

    # Hardware parameters
    left_camera_id: str = "24259877"
    right_camera_id: str = "24514023"
    wrist_camera_id: str = "13062452"

    # Rollout parameters
    max_timesteps: int = 400
    # How many actions to execute from a predicted action chunk before querying policy server again
    open_loop_horizon: int = 8

    # Remote server parameters
    remote_host: str = "localhost"
    remote_port: int = 8000


def main(args: Args):
    # Initialize the Panda environment.
    env = RobotEnv(action_space="joint_velocity", gripper_action_space="position")
    print("created the droid env!")

    policy_client = websocket_policy_client.WebsocketClientPolicy(args.remote_host, args.remote_port)

    df = pd.DataFrame(columns=["policy_name", "success", "duration", "video_filename"])

    while True:
        # Rollout parameters
        actions_from_chunk_completed = 0
        pred_action_chunk = None

        # Prepare to save video of rollout
        timestamp = datetime.datetime.now().strftime("%Y_%m_%d_%H:%M:%S")
        video = []
        bar = tqdm.tqdm(range(args.max_timesteps))
        for t_step in bar:
            try:
                # Get the current observation
                curr_obs = _extract_observation(
                    args,
                    env.get_observation(),
                    # Save the first observation to disk
                    save_to_disk=t_step == 0,
                )

                video.append(curr_obs["right_image"])

                # Send websocket request to policy server if it's time to predict a new chunk
                if actions_from_chunk_completed == 0 or actions_from_chunk_completed >= args.open_loop_horizon:
                    actions_from_chunk_completed = 0

                    request_data = {
                        "observation/exterior_image_1_left": np.array(curr_obs["left_image"]),
                        "observation/exterior_image_2_left": np.array(curr_obs["right_image"]),
                        "observation/wrist_image_left": np.array(curr_obs["wrist_image"]),
                        "observation/joint_position": curr_obs["joint_position"],
                        "observation/gripper_position": curr_obs["gripper_position"],
                    }

                    # this returns action chunk [16, 8] of 16 joint velocity actions (7) + gripper position (1)
                    pred_action_chunk = policy_client.infer(request_data)
                    pred_action_chunk = pred_action_chunk
                    assert pred_action_chunk.shape == (15, 8)

                # Select current action to execute from chunk
                action = pred_action_chunk[actions_from_chunk_completed]
                actions_from_chunk_completed += 1

                # binarize gripper action
                if action[-1].item() > 0.5:
                    action[-1] = 1.0
                else:
                    action[-1] = 0.0

                # clip all dimensions of action to [-1, 1]
                action = np.clip(action, -1, 1)

                env.step(action)
            except KeyboardInterrupt:
                break

        video = np.stack(video)
        save_filename = args.policy_name + "_" + timestamp
        # np.save(os.path.join("videos", save_filename), video)
        ImageSequenceClip(list(video), fps=10).write_videofile(save_filename + ".mp4", codec="libx264")

        success: str | float | None = None
        while not isinstance(success, float):
            success = input(
                "Did the rollout succeed? (enter y for 100%, n for 0%), or a numeric value 0-100 based on the evaluation spec"
            )
            if success == "y":
                success = 1.0
            elif success == "n":
                success = 0.0

            try:
                success = float(success) / 100
                assert 0 <= success <= 1
            except:
                print(f"Success must be a number in [0, 100] but got: {success}")

        df = df.append(
            {
                "policy_name": args.policy_name,
                "success": success,
                "duration": t_step,
                "video_filename": save_filename,
            },
            ignore_index=True,
        )

        if input("Do one more eval? (enter y or n) ").lower() != "y":
            break
        env.reset()

    os.makedirs("results", exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%I:%M%p_%B_%d_%Y")
    csv_filename = os.path.join("results", f"eval_{timestamp}.csv")
    df.to_csv(csv_filename)
    print(f"Results saved to {csv_filename}")


def _extract_observation(args: Args, obs_dict, save_to_disk=False):
    image_observations = obs_dict["image"]
    left_image, right_image, wrist_image = None, None, None
    for key in image_observations.keys():
        if args.left_camera_id in key and "left" in key:
            left_image = image_observations[key]
        elif args.right_camera_id in key and "left" in key:
            right_image = image_observations[key]
        elif args.wrist_camera_id in key and "left" in key:
            wrist_image = image_observations[key]

    # Drop the alpha dimension
    left_image = left_image[..., :3]
    right_image = right_image[..., :3]
    wrist_image = wrist_image[..., :3]

    # Convert to RGB
    left_image = np.concatenate([left_image[..., 2:], left_image[..., 1:2], left_image[..., :1]], axis=-1)
    right_image = np.concatenate([right_image[..., 2:], right_image[..., 1:2], right_image[..., :1]], axis=-1)
    wrist_image = np.concatenate([wrist_image[..., 2:], wrist_image[..., 1:2], wrist_image[..., :1]], axis=-1)

    # In addition to image observations, also capture the proprioceptive state
    robot_state = obs_dict["robot_state"]
    cartesian_position = np.array(robot_state["cartesian_position"])
    joint_position = np.array(robot_state["joint_positions"])
    gripper_position = np.array([robot_state["gripper_position"]])

    # Save the images to disk so that they can be viewed live while the robot is running
    # Create one combined image to make live viewing easy
    if save_to_disk:
        combined_image = np.concatenate([left_image, wrist_image, right_image], axis=1)
        combined_image = Image.fromarray(combined_image)
        combined_image.save("robot_camera_views.png")

    return {
        "left_image": left_image,
        "right_image": right_image,
        "wrist_image": wrist_image,
        "cartesian_position": cartesian_position,
        "joint_position": joint_position,
        "gripper_position": gripper_position,
    }


if __name__ == "__main__":
    args: Args = tyro.cli(Args)
    assert args.policy_name in ["droid_dct", "droid_rt2", "droid_dct_universal", "droid_fsq"]
    main(args)
