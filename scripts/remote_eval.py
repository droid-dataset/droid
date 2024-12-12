import datetime
import faulthandler
import os
import pickle

import numpy as np
import pandas as pd
import requests
import tqdm
from moviepy.editor import ImageSequenceClip
from PIL import Image
from r2d2.robot_env import RobotEnv

from scripts import websocket_policy_client

faulthandler.enable()


def _resize_with_pad_pil(image: Image.Image, height: int, width: int, method: int) -> Image.Image:
    """Replicates tf.image.resize_with_pad for one image using PIL. Resizes an image to a target height and
    width without distortion by padding with zeros.

    Unlike the jax version, note that PIL uses [width, height, channel] ordering instead of [batch, h, w, c].
    """
    cur_width, cur_height = image.size
    if cur_width == width and cur_height == height:
        return image  # No need to resize if the image is already the correct size.

    ratio = max(cur_width / width, cur_height / height)
    resized_height = int(cur_height / ratio)
    resized_width = int(cur_width / ratio)
    resized_image = image.resize((resized_width, resized_height), resample=method)

    zero_image = Image.new(resized_image.mode, (width, height), 0)
    pad_height = max(0, int((height - resized_height) / 2))
    pad_width = max(0, int((width - resized_width) / 2))
    zero_image.paste(resized_image, (pad_width, pad_height))
    assert zero_image.size == (width, height)
    return zero_image


def resize_with_pad(images: np.ndarray, height: int, width: int, method=Image.BILINEAR) -> np.ndarray:
    """Replicates tf.image.resize_with_pad for multiple images using PIL. Resizes a batch of images to a target height.

    Args:
        images: A batch of images in [..., height, width, channel] format.
        height: The target height of the image.
        width: The target width of the image.
        method: The interpolation method to use. Default is bilinear.

    Returns:
        The resized images in [..., height, width, channel].
    """
    # If the images are already the correct size, return them as is.
    if images.shape[-3:-1] == (height, width):
        return images

    original_shape = images.shape

    images = images.reshape(-1, *original_shape[-3:])
    resized = np.stack([_resize_with_pad_pil(Image.fromarray(im), height, width, method=method) for im in images])
    return resized.reshape(*original_shape[:-3], *resized.shape[-3:])


def _make_request(uri: str, element):
    response = requests.post(uri, data=pickle.dumps(element))
    if response.status_code != 200:
        raise Exception(response.text)

    action = pickle.loads(response.content)
    # print(action.keys())
    return action["actions"]  # remove batch dim


def extract_observation(obs_dict, save_to_disk=False):
    image_observations = obs_dict["image"]
    left_image, right_image, wrist_image = None, None, None
    for key in image_observations.keys():
        if "24259877" in key and "left" in key:
            left_image = image_observations[key]
        elif "24514023" in key and "left" in key:
            right_image = image_observations[key]
        elif "13062452" in key and "left" in key:
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


def main(base_image, policy_name):
    policy_client = websocket_policy_client.WebsocketClientPolicy("localhost", 8000)

    # Initialize the Panda environment.
    env = RobotEnv(action_space="joint_velocity", gripper_action_space="position")
    print("created the droid env!")

    df = pd.DataFrame(columns=["policy_name", "command", "success", "duration", "video_filename"])

    while True:
        # Rollout parameters
        max_timesteps = 400
        open_loop_horizon = (
            8  # how many actions to execute from a predicted action chunk before querying policy server again
        )
        actions_from_chunk_completed = 0
        pred_action_chunk = None

        lang_command = input("Enter language command: ")

        # Prepare to save video of rollout
        timestamp = datetime.datetime.now().strftime("%Y_%m_%d_%H:%M:%S")
        save_filename = policy_name + "_" + lang_command.replace(" ", "_") + "_" + timestamp
        video = []
        bar = tqdm.tqdm(range(max_timesteps))
        for t_step in bar:
            try:
                # Get the current observation
                curr_obs = extract_observation(
                    env.get_observation(), save_to_disk=t_step == 0
                )  # If its the first obs save to disk

                video.append(curr_obs["right_image"])

                # Send HTTP request to policy server if it's time to predict a new chunk
                if actions_from_chunk_completed == 0 or actions_from_chunk_completed >= open_loop_horizon:
                    actions_from_chunk_completed = 0

                    request_data = {
                        "observation/exterior_image_1_left": np.array(curr_obs[base_image]),
                        "observation/exterior_image_1_left_mask": np.array(True),
                        "observation/wrist_image_left": np.array(curr_obs["wrist_image"]),
                        "observation/wrist_image_left_mask": np.array(True),
                        "observation/joint_position": curr_obs["joint_position"],
                        "observation/gripper_position": curr_obs["gripper_position"],
                        "raw_text": lang_command,
                    }
                    bar.set_description(f"Language: {lang_command}")

                    # this returns action chunk [16, 8] of 16 joint velocity actions (7) + gripper position (1)
                    pred_action_chunk = _make_request("http://10.103.116.247:8000/infer", request_data)
                    pred_action_chunk = pred_action_chunk
                    assert pred_action_chunk.shape == (15, 8)

                # Select current action to execute from chunk
                action = pred_action_chunk[actions_from_chunk_completed]
                actions_from_chunk_completed += 1

                # binarize gripper action
                if action[-1].item() > 0.5:
                    action[-1] = 1.0
                elif action[-1].item() < 0.5:
                    action[-1] = 0.0

                # clip gripper action
                if action[-1].item() > 1.0:
                    action[-1] = 1.0
                elif action[-1].item() < 0.0:
                    action[-1] = 0.0

                # clip all dimensions of action to [-1, 1]
                action = np.clip(action, -1, 1)

                env.step(action)
            except KeyboardInterrupt:
                break

        video = np.stack(video)
        # np.save(os.path.join("videos", save_filename), video)
        ImageSequenceClip(list(video), fps=10).write_videofile(save_filename + ".mp4", codec="libx264")

        success = None
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
                "policy_name": policy_name,
                "success": success,
                "command": lang_command,
                "duration": t_step,
                "video_filename": save_filename,
            },
            ignore_index=True,
        )

        r = input("Do one more eval? (enter y or n) ")
        if r != "y":
            break
        env.reset()

    os.makedirs("results", exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%I:%M%p_%B_%d_%Y")
    csv_filename = os.path.join("results", f"eval_{timestamp}.csv")
    df.to_csv(csv_filename)
    print(f"Results saved to {csv_filename}")


if __name__ == "__main__":
    import sys

    assert sys.argv[1] in ["left_image", "right_image"]
    assert sys.argv[2] in ["droid_dct", "droid_rt2", "droid_dct_universal", "droid_fsq"]
    main(sys.argv[1], sys.argv[2])
