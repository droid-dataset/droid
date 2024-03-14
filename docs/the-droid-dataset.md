---
layout: default
title: The DROID Dataset
nav_order: 4
---

## 🔍 Exploring the Dataset

It is possible to interactively explore the DROID via the following [interactive dataset visualizer](https://www.cs.princeton.edu/~jw60/droid-dataset-visualizer/). This is a great way to start understanding the DROID dataset and is a highly recommended starting point.

<a href="https://www.cs.princeton.edu/~jw60/droid-dataset-visualizer/"><img src="./assets/the-droid-dataset/droid_data_visualizer.png" alt="image" width="90%" height="auto"></a>

## 📈 Using the Dataset

The DROID dataset is hosted within a Google Cloud Bucket and is offered in two formats:

1. [RLDS](https://github.com/google-research/rlds): ideal for dataloading for the purpose of training policies
2. Raw Data: ideal for those who wish to manipulate the raw data

To browse the bucket storing the data visit the following [link](https://console.cloud.google.com/storage/browser/xembodiment_data/r2d2).

### Accessing RLDS Dataset

To load the RLDS dataset directly as a tensorflow datast one can run the below snippet. It is worth noting that there are a variety of tools that exist for interacting with RLDS formatted datasets, for the below example we demonstrate how to load a small subset of the dataset and view an image.

```python
import tensorflow_datasets as tfds
from PIL import Image

# get the dataset
data_directory = 'gs://xembodiment_data/r2d2/tfds/2024_01_23/1.0.0'
dataset_builder = tfds.builder_from_directory(data_directory)

# inspect episode data
dataset_sample = dataset_builder.as_dataset(split='train[:10]').shuffle(10) # 10 episode from train split
episode = next(iter(dataset_sample))

# lets look at the exterior left image
images = [step['observation']['exterior_image_1_left'] for step in episode['steps']]
images = [Image.fromarray(image.numpy()) for image in images]
images[0].show()
```

For more complex examples of loading the RLDS format of the DROID and for training policies please consult examples provided in [robomimic](https://github.com/ARISE-Initiative/robomimic).

### Accessing Raw Data

The easiest way to download the raw dataset is via `gsutil`, to get started please install the gcloud CLI tools at the following [link](https://cloud.google.com/sdk/docs/install).

With `gsutil` installed it is now possible to copy the raw data with the below command:

```bash
gsutil cp -r gs://xembodiment_data/r2d2/r2d2-data-full <path_on_local>
```

## 📝 Dataset Schema

```python
DROID = {
        "episode_metadata": {
                "recording_folderpath": tf.Text, # path to the folder of recordings
                "file_path": tf.Text, # path to the original data file
                },
	"steps": {
		"is_first": tf.Scalar(dtype=bool), # true on first step of the episode
                "is_last": tf.Scalar(dtype=bool), # true on last step of the episode
        	"is_terminal": tf.Scalar(dtype=bool), # true on last step of the episode if it is a terminal step, True for demos
                                
                "language_instruction": tf.Text, # language instruction
                "language_instruction_2": tf.Text, # alternative language instruction
                "language_instruction_3": tf.Text, # alternative language instruction
                "language_embedding": tf.Tensor(512, dtype=float32), # Kona language embedding. See https://tfhub.dev/google/universal-sentence-encoder-large/5
                "language_embedding_2": tf.Tensor(512, dtype=float32), # alternative Kona language embedding
                "language_embedding_3": tf.Tensor(512, dtype=float32), # alternative Kona language embedding
                "observation": {
                                "gripper_position": tf.Tensor(1, dtype=float64), # gripper position state
                                "cartesian_position": tf.Tensor(6, dtype=float64), # robot Cartesian state
                                "joint_position": tf.Tensor(7, dtype=float64), # joint position state
                                "wrist_image_left": tf.Image(180, 320, 3, dtype=uint8), # wrist camera RGB left viewpoint        
                                "exterior_image_1_left": tf.Image(180, 320, 3, dtype=uint8), # exterior camera 1 left viewpoint
                                "exterior_image_2_left": tf.Image(180, 320, 3, dtype=uint8), # exterior camera 2 left viewpoint
                		},                            
                "action_dict": {
                                "gripper_position": tf.Tensor(1, dtype=float64), # commanded gripper position
                                "gripper_velocity": tf.Tensor(1, dtype=float64), # commanded gripper velocity
                                "cartesian_position": tf.Tensor(6, dtype=float64), # commanded Cartesian position
                                "cartesian_velocity": tf.Tensor(6, dtype=float64), # commanded Cartesian velocity
                                "joint_position": tf.Tensor(7, dtype=float64),  # commanded joint position
                        	"joint_velocity": tf.Tensor(7, dtype=float64), # commanded joint velocity
                		},
		"discount": tf.Scalar(dtype=float32), # discount if provided, default to 1
                "reward": tf.Scalar(dtype=float32), # reward if provided, 1 on final step for demos
                "action": tf.Tensor(7, dtype=float64), # robot action, consists of [6x joint velocities, 1x gripper position]
	},
}
```

## 📄 Data Analysis and Further Information
Please consult the [paper](https://openreview.net/pdf?id=gG0QQsoaCp) for detailed data analysis and further information about the dataset.
