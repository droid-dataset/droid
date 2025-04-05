from droid.controllers.oculus_controller import VRPolicy
from droid.robot_env import RobotEnv
from droid.trajectory_utils.misc import collect_trajectory


from rich.live import Live
from rich.table import Table
from rich.prompt import Prompt
from rich.console import Console
import time
import random
from pathlib import Path


class RobotDataCollector:
    def __init__(self, task):
        self.task = task
        self.total_trajectories = 0
        self.is_collecting = False
        

    def add_successful_trajectory(self):
        self.total_trajectories += 1

    def start_collecting(self):
        self.is_collecting = True

    def stop_collecting(self):
        self.is_collecting = False

    def generate_table(self):
        """Creates a live-updating table for display."""
        table = Table(title=f"Data Collection for Task: {self.task}")
        table.add_column("Successful Trajectories", justify="center")
        table.add_column("Collecting Status", justify="center")

        table.add_row(str(self.total_trajectories), "🟢 Collecting" if self.is_collecting else "🔴 Idle")

        return table

def wait_until_ready(controller, console):
    '''
    If user is ready, returns true, but false if user wants to stop the data collection
    '''
    # controller.reset_state()
    # last_state = False
    # while True:
    #     controller_info = controller.get_info()
    #     if not (controller_info["success"] == last_state):
    #         last_state = controller_info["success"]
    #         time.sleep(0.2)
    #     if not (controller_info["success"]):
    #         return True
    #     elif controller_info["failure"]:
    #         console.print("Data collection stopped.")
    #         return False
    #     else:
    #         time.sleep(0.1)
    #     time.sl

    controller.reset_state()
    last_state = None
    while True:
        controller_info = controller.get_info()
        if not last_state is None:
            if last_state =="success" and not controller_info["success"]:
                return True
            elif last_state == "failure" and not controller_info["failure"]:
                return False

        if controller_info["success"]:
            last_state = "success"
        elif controller_info["failure"]:
            last_state = "failure"
        else:
            last_state = None

# Initialize data collector
console = Console()
task = Prompt.ask("What task are you collecting data for?")
# make data folder
data_folder = Path("data") / f"{task.lower().replace(' ', '_')}-{time.strftime('%Y-%m-%d-%H-%M-%S')}"
data_folder.mkdir(parents=True, exist_ok=True)
console.print(f"Data will be saved in [bold green]{data_folder}[/bold green]")

collector = RobotDataCollector(task=task)


env = RobotEnv(action_space="cartesian_velocity", gripper_action_space="position")
controller = VRPolicy(
        pos_action_gain = 10,
        rot_action_gain= 6,
)


# Simulate data collection in real-time
with Live(collector.generate_table(), refresh_per_second=5) as live:
# while True:
    # get all trajs
    trajs = list(data_folder.glob("*.h5"))
    traj_idx = len(trajs) + 1   

    while True:
        proceed = wait_until_ready(controller, console)
        if not proceed:
            break

        collector.start_collecting()
        live.update(collector.generate_table())
        controller.reset_state()

        controller_info = collect_trajectory(env, 
                                            controller=controller,
                                            save_filepath=str(data_folder / f"traj_{traj_idx}.h5"),
                                            save_images=True,
                                            reset_robot=False,
                                            )

        collector.stop_collecting()
        if controller_info["success"]:
            collector.add_successful_trajectory()
            traj_idx += 1
        else:
            # rename the failed trajectory
            (data_folder / f"traj_{traj_idx}.h5").rename(data_folder / f"traj_{traj_idx}.fail") 
                        
        live.update(collector.generate_table())  # Update the UI
        env.reset()


    


