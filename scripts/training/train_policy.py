import json

from droid.training.model_trainer import exp_launcher

task_label_filepath = "/home/sasha/DROID/scripts/labeling/task_label_filepath.json"
with open(task_label_filepath, "r") as jsonFile:
    task_labels = json.load(jsonFile)


def filter_func(h5_metadata, put_in_only=False):
    put_in = task_labels.get(h5_metadata["time"], not put_in_only)
    return put_in == put_in_only


variant = dict(
    exp_name="pen_cup_task",
    use_gpu=True,
    seed=0,
    training_kwargs=dict(
        num_epochs=100,
        grad_steps_per_epoch=1000,
        weight_decay=1e-4,
        lr=1e-4,
    ),
    camera_kwargs=dict(
        hand_camera=dict(image=True, concatenate_images=False, resolution=(128, 128), resize_func="cv2"),
        varied_camera=dict(image=False, concatenate_images=False, resolution=(128, 128), resize_func="cv2"),
    ),
    data_processing_kwargs=dict(
        timestep_filtering_kwargs=dict(
            action_space="cartesian_velocity",
            robot_state_keys=["cartesian_position", "gripper_position", "joint_positions"],
            camera_extrinsics=[],
        ),
        image_transform_kwargs=dict(
            remove_alpha=True,
            bgr_to_rgb=True,
            to_tensor=True,
            augment=False,
        ),
    ),
    data_loader_kwargs=dict(
        recording_prefix="MP4",
        batch_size=4,
        prefetch_factor=1,
        buffer_size=1000,
        num_workers=4,
        data_filtering_kwargs=dict(
            train_p=0.9,
            remove_failures=True,
            filter_func=filter_func,
        ),
        traj_loading_kwargs=dict(
            remove_skipped_steps=True,
            num_samples_per_traj=50,
            num_samples_per_traj_coeff=1.5,
            read_cameras=True,
        ),
    ),
    model_kwargs=dict(
        representation_size=50,
        embedding_dim=1,
        num_encoder_hiddens=128,
        num_residual_layers=3,
        num_residual_hiddens=64,
        num_camera_layers=1,
        num_camera_hidden=200,
        num_state_layers=1,
        num_state_hidden=200,
        num_policy_layers=3,
        num_policy_hidden=300,
    ),
)

if __name__ == "__main__":
    exp_launcher(variant, run_id=3, exp_id=0)
