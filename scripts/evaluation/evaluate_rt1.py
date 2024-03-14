import argparse
from droid.user_interface.eval_gui import EvalGUI
from droid.evaluation.rt1_wrapper import RT1Policy


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint_path", type=str, required=True)
    args = parser.parse_args()

    policy = RT1Policy(
        args.checkpoint_path,
        camera_obs_keys=[
            "26638268_left",
            "26638268_right",
            "22246076_left",
            "22246076_right",
            "16291792_left",
            "16291792_right",
        ],
    )
    EvalGUI(policy=policy)


if __name__ == "__main__":
    main()
