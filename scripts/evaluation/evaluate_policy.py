from droid.evaluation.eval_launcher_robomimic import eval_launcher, get_goal_im
import matplotlib.pyplot as plt
import os
import argparse
import cv2


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-g', '--capture_goal', action='store_true')
    parser.add_argument('-l', '--lang_cond', action='store_true')
    parser.add_argument('-c', '--ckpt_path', type=str, default=None, 
        help='Path to Pytorch checkpoint (.pth) corresponding to the policy you want to evaluate.')
    args = parser.parse_args()

    variant = dict(
        exp_name="policy_test",
        save_data=False,
        use_gpu=True,
        seed=0,
        policy_logdir="test",
        task="",
        layout_id=None,
        model_id=50,
        camera_kwargs=dict(),
        data_processing_kwargs=dict(
            timestep_filtering_kwargs=dict(),
            image_transform_kwargs=dict(),
        ),
        ckpt_path=args.ckpt_path,
    )

    if args.capture_goal:
        valid_values = ["yes", "no"]
        goal_im_ok = False

        while goal_im_ok is not True:
            program_mode = input("Move the robot into programming mode, adjust the scene as needed, and then press Enter to acknowledge: ")
            exec_mode = input("Now move the robot into execution mode, press Enter to acknowledge: ")
            print("Capturing Goal Image")
            goal_ims = get_goal_im(variant, run_id=1, exp_id=0)
            # Sort the goal_ims by key and display in a 3 x 2 grid
            sort_goal_ims = [cv2.cvtColor(image[1][:, :, :3], cv2.COLOR_BGR2RGB) for image in sorted(goal_ims.items(), key=lambda x: x[0])]
            fig, axes = plt.subplots(3, 2, figsize=(8,10))
            axes = axes.flatten()
            for i in range(len(sort_goal_ims)):
                axes[i].imshow(sort_goal_ims[i])
                axes[i].axis('off')
            plt.tight_layout()
            plt.show()

            user_input = input("Do these goal images look reasonable? Enter Yes or No: ").lower()
            while user_input not in valid_values:
                print("Invalid input, Please enter Yes or No")
            goal_im_ok = user_input == "yes"
        input("Now reset the scene for the policy to execute, press Enter to acknowledge: ")
    if args.lang_cond:
        user_input = input("Provide a language command for the robot to complete: ").lower()
        if not os.path.exists('eval_params'):
            os.makedirs('eval_params')
        with open('eval_params/lang_command.txt', 'w') as file:
            file.write(user_input)
    
    print("Evaluating Policy")
    eval_launcher(variant, run_id=1, exp_id=0)
