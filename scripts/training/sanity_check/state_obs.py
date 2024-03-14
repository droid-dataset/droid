from droid.training.model_trainer import exp_launcher

variant = dict(
    exp_name="sanity_check_state_obs",
    use_gpu=True,
    seed=0,
    training_kwargs=dict(
        num_epochs=100,
        grad_steps_per_epoch=1000,
        weight_decay=0.0,
        lr=1e-4,
    ),
    camera_kwargs=dict(
        hand_camera=dict(image=False, depth=False, pointcloud=False, concatenate_images=False, resolution=(256, 256)),
        fixed_camera=dict(image=False, depth=False, pointcloud=False, concatenate_images=False, resolution=(256, 256)),
        varied_camera=dict(image=False, depth=False, pointcloud=False, concatenate_images=False, resolution=(256, 256)),
    ),
    data_processing_kwargs=dict(
        timestep_filtering_kwargs=dict(
            action_space="cartesian_velocity",
            robot_state_keys=["cartesian_position", "gripper_position"],
            camera_extrinsics=[],
        ),
        image_transform_kwargs=dict(
            remove_alpha=True,
            bgr_to_rgb=True,
            to_tensor=True,
            augment=True,
        ),
    ),
    data_loader_kwargs=dict(
        batch_size=4,
        prefetch_factor=1,
        buffer_size=200,
        num_workers=2,
        data_filtering_kwargs=dict(
            train_p=0.9,
            remove_failures=True,
            filter_func=None,
        ),
        traj_loading_kwargs=dict(
            remove_skipped_steps=True,
            num_samples_per_traj=20,
            num_samples_per_traj_coeff=1.5,
            read_cameras=False,
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
        num_policy_layers=2,
        num_policy_hidden=200,
    ),
)

if __name__ == "__main__":
    exp_launcher(variant, run_id=1, exp_id=0)
