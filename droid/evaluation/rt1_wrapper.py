from pathlib import Path
from PIL import Image
import tensorflow as tf
import numpy as np
from tf_agents.policies import py_tf_eager_policy
import tf_agents
from tf_agents.trajectories import time_step as ts
import tensorflow_hub as hub

from droid.user_interface.eval_gui import GoalCondPolicy, DEFAULT_LANG_TEXT


def resize(image):
    image = tf.image.resize_with_pad(image, target_width=320, target_height=256)
    image = tf.cast(image, tf.uint8)
    return image


class RT1Policy(GoalCondPolicy):
    def __init__(self, checkpoint_path, goal_images=None, language_instruction=None, camera_obs_keys=[]):
        """goal_images is a tuple of two goal images."""
        self._policy = py_tf_eager_policy.SavedModelPyTFEagerPolicy(
            model_path=checkpoint_path, load_specs_from_pbtxt=True, use_tf_function=True
        )
        self.obs = self._run_dummy_inference()
        self._goal_images = goal_images
        self._policy_state = self._policy.get_initial_state(batch_size=1)
        self._camera_obs_keys = camera_obs_keys
        if language_instruction is not None:
            self._language_embedding = self.compute_embedding(language_instruction)
        else:
            self._language_embedding = None

    def _run_dummy_inference(self):
        observation = tf_agents.specs.zero_spec_nest(tf_agents.specs.from_spec(self._policy.time_step_spec.observation))
        tfa_time_step = ts.transition(observation, reward=np.zeros((), dtype=np.float32))
        policy_state = self._policy.get_initial_state(batch_size=1)
        action = self._policy.action(tfa_time_step, policy_state)
        return observation

    def _normalize_task_name(self, task_name):

        replaced = (
            task_name.replace("_", " ")
            .replace("1f", " ")
            .replace("4f", " ")
            .replace("-", " ")
            .replace("50", " ")
            .replace("55", " ")
            .replace("56", " ")
        )
        return replaced.lstrip(" ").rstrip(" ")

    def compute_embedding(self, task_name):
        print("Computing embedding ...")
        # Load language model and embed the task string
        embed = hub.load("https://tfhub.dev/google/universal-sentence-encoder-large/5")
        print("Finished loading language model.")
        return embed([self._normalize_task_name(task_name)])[0]

    def forward(self, observation):
        # construct observation
        if not self._goal_images:
            # throw exception saying no goal images were provided
            raise Exception("No goal images were provided")

        for i, key in enumerate(self._camera_obs_keys):
            if i == 0:
                self.obs["image"] = resize(tf.convert_to_tensor(observation["image"][key][:, :, :3].copy()[..., ::-1]))
                self.obs["goal_image"] = self._goal_images[0]
            elif i >= 1:
                self.obs[f"image{i}"] = resize(
                    tf.convert_to_tensor(observation["image"][key][:, :, :3].copy()[..., ::-1])
                )
                self.obs[f"goal_image{i}"] = self._goal_images[1]

        if self._language_embedding is not None:
            self.obs["natural_language_embedding"] = self._language_embedding

        tfa_time_step = ts.transition(self.obs, reward=np.zeros((), dtype=np.float32))

        policy_step = self._policy.action(tfa_time_step, self._policy_state)
        self._policy_state = policy_step.state
        action = np.concatenate(
            [
                policy_step.action["world_vector"],
                policy_step.action["rotation_delta"],
                policy_step.action["gripper_closedness_action"],
            ]
        )
        print(f"returning action: {action}")
        return action

    def load_goal_imgs(self, img_dict):
        goal_images = []
        for key in self._camera_obs_keys:
            goal_images.append(resize(tf.convert_to_tensor(img_dict[key])))
        self._goal_images = goal_images

    def load_lang(self, text):
        if text != DEFAULT_LANG_TEXT:
            self._language_embedding = self.compute_embedding(text)
