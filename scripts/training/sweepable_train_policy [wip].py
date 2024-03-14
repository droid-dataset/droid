from droid.training.model_trainer import exp_launcher

# import rlkit.util.hyperparameter as hyp

"""
THIS IS A WORK IN PROGRESS
"""


variant = dict(
    exp_name="simple_bc",
    use_gpu=True,
    seed=0,
    training_kwargs=dict(
        grad_steps_per_epoch=10,
        num_epochs=100,
        weight_decay=0.0,
        lr=1e-3,
    ),
    camera_kwargs=dict(
        image=True,
        depth=False,
        pointcloud=False,
        resolution_kwargs=dict(
            hand_camera=(256, 256),
            fixed_camera=(256, 256),
            varied_camera=(256, 256),
        ),
    ),
    data_processing_kwars=dict(
        timestep_filtering_kwargs=dict(
            # Eventually need to enable sweeper to take lists #
            action_space="cartesian_delta",
            robot_state_keys=["cartesian_pose", "gripper_position", "joint_positions", "joint_velocities"],
            camera_extrinsics=["hand_camera", "varied_camera", "fixed_camera"],
            image_views=["hand_camera", "varied_camera", "fixed_camera"],
            depth_views=[],
            pointcloud_views=[],
        ),
        image_transform_kwargs=dict(remove_alpha=True, to_tensor=True, augment=True),
    ),
    data_loader_kwargs=dict(
        buffer_size=500,
        batch_size=32,
        num_workers=1,
        train_p=0.9,
        remove_failures=True,
        filter_func=None,
        traj_loading_kwargs=dict(
            remove_skipped_steps=True,
            num_samples_per_traj=100,
            num_samples_per_traj_coeff=2,
        ),
    ),
    model_kwargs=dict(
        embedding_dim=1,
        num_encoder_hiddens=128,
        num_residual_layers=3,
        num_residual_hiddens=64,
        representation_size=100,
        num_img_layers=4,
        num_img_hidden=400,
        num_state_layers=4,
        num_state_hidden=400,
        num_policy_layers=4,
        num_policy_hidden=400,
    ),
)

if __name__ == "__main__":
    exp_launcher(variant, run_id=1, exp_id=0)

    # search_space = {
    #     "seed": range(1),
    # }
    # sweeper = hyp.DeterministicHyperparameterSweeper(
    #     search_space, default_parameters=variant,
    # )

    # exp_id = 0
    # for variant in sweeper.iterate_hyperparameters():
    #     exp_launcher(variant, run_id=1, exp_id=exp_id)
    #     exp_id += 1
