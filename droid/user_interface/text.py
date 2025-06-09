all_tasks = {
    "Articulated Tasks": [
        "Press button (ex: light switch, elevators, microwave button)",
        "Open or close hinged object (ex: hinged door, microwave, oven, book, dryer, toilet, box)",
        "Open or close slidable objects (ex: toaster, drawers, sliding doors, dressers)",
        "Turn twistable object (ex: faucets, lamps, stove knobs)",
    ],
    "Free Object Tasks": [
        "Move object into or out of container (ex: drawer, clothes hamper, plate, trashcan, washer)",
        "Move lid on or off of container (ex: pot, cup, pill bottle)",
        "Move object to a new position and orientation (ex: grasping, relocating, flipping)",
    ],
    "Tool Usage Tasks": [
        "Use cup to pour something granular (ex: nuts, rice, dried pasta, coffee beans)",
        "Use object to pick up something (ex: spoon + almonds, spatula + bread, fork + banana)",
        "Use cloth to clean something (ex: table, window, mirror, plate)",
        "Use object to stir something (ex: almonds in a bowl, dried pasta in a pot)",
    ],
    "Deformable Object Tasks": [
        "Open or close curtain (ex: blanket on bed, shower curtain, shades)",
        "Hang or unhang object (ex: towel on hook, clothes over chair)",
        "Fold, spread out, or clump object (ex: cloth, charging cord, clothes)",
    ],
}

preferred_tasks = {
    "Articulated Tasks": [
        "Flip a lightswitch",
        "Open or close a hinged cabinet",
        "Open or close a sliding drawer",
        "Push down the lever on a toaster",
    ],
    "Free Object Tasks": [
        "Move a lid onto or off of a pot",
        "Put an object in or take an object out of a [pot, cabinet, drawer, clothes hamper]",
        "Move an object to a new position and orientation",
    ],
    "Tool Usage Tasks": [
        "Use cup to pour something granular",
        "Use a spatula to pick up an object",
        "Use a cloth to wipe a table",
        "Use a big spoon to stir a pot",
    ],
    "Deformable Object Tasks": [
        "Pull a blanket on a bed forward or backward",
        "Hang or unhang fabric (towel, clothes, etc) on a hook",
        "Fold or unfold fabric (towel, clothes, etc)",
    ],
}

compositional_tasks = [
    lambda: "Do anything you like that takes multiple steps to complete.",
    lambda t: "Do any task, and then reset the scene.\n\nSuggested task:\n* {0}".format(t),
    lambda t1, t2: "Do any two tasks consecutively.\n\nSuggested tasks:\n* {0}\n* {1}".format(t1, t2),
    lambda t1, t2, t3: "Do any three tasks consecutively.\n\nSuggested tasks:\n* {0}\n* {1}\n* {2}".format(t1, t2, t3),
]

how_to_text = (
    "1. Move the robot to a desired location (remember to unlock + relock wheels) \n\n2. Confirm that robot can reach"
    " everything of interest \n\n3. Confirm that ALL interaction objects are within ALL camera views \n\n4. Check the"
    " task categories that are doable from the CURRENT scene \n\n5. Try to come up with roughly three tasks of your own"
)

how_to_calibrate_text = (
    "Follow these steps EVERYTIME you move a camera:\n\n1. Attach the ChArUco board to the gripper when calibrating 3rd"
    " person cameras, or place it on a table when calibrating the hand camera\n\n2. Once the trajectory starts, move the"
    " gripper such that the board is clearly visible by the camera (1-2 feet away)\n\n3. Press 'A' to begin the"
    " calibration trajectory, the GUI will inform you if calibration fails\n\nTip: You can name cameras in the"
    " parameters file\n\nWarning: 'Advanced Mode' has higher calibration success, but is slow and buggy!"
)

data_collection_text = (
    "* Use as much action noise as possible, such that you can still perform the tasks\n\n* Make sure that you"
    " prioritize data collection for everything in 'Preferred Tasks'\n\n* Create tasks like those in 'Task Ideas'. Keep"
    " things simple and realistic :)\n\n* Finish trajectories in such a way that the robot can be reset (ex: nothing in"
    " gripper)\n\n* Although we want you to stick to the requested tasks, use your best judgement\n\n* Avoid setting up"
    " scenes that cover repetitive task categories\n\n* At any time, hold 'Return' for 5 seconds to reset the robot"
)

warnings_text = (
    "* DO NOT use the robot to grasp fragile items (ex: glass, eggs) \n\n* NEVER get the robot or any of its equipment"
    " wet \n\n* ALWAYS keep the mobile base on all four wheels \n\n* STAY out of camera view and refrain from talking"
    " during data collection"
)

scene_changes = [
    "Change the table height slightly (1-6 inches)",
    "Change the table height significantly (6+ inches)",
    "Move the table position and angle slightly (1-6 square inches, 1-15 degrees)",
    "Move the table position and angle significantly (6+ square inches, 15+ degrees)",
    "Move a varied camera's pose significantly and recalibrate",
    "Add an object to the scene",
    "Remove (if applicable) an object from the scene",
    "If possible, change the lighting in the room (ex: dim a light, close a window)",
]

noise_text = "Use the slider to adjust the action noise"
task_suggestions_text = "Suggestions are organized below by room"
use_checkboxes_text = "Use the checkboxes to keep track of your progress"
missing_name_text = "Enter your first AND last name"
missing_building_text = "Enter a building name"
move_robot_text = "MANDATORY: Move the robot setup to an entirely new location"
preferred_task_text = "Use the checkboxes below to keep track of your progress"
no_tasks_text = "There are no tasks to sample. Please click or enter some :)"
freewrite_text = "Enter Your Own Tasks Here (Seperate Entries With Semicolons)"
shift_text = "Press 'Shift' to toggle camera feed"
controller_off_msg = "Place it on your head to wake it up. When ready, press space to continue :)"
missing_calibration_text = "You must finish calibrating all cameras in order to proceed"
old_calibration_text = (
    "You have cameras that haven't been calibrated in over an hour. Are you sure you want to continue?"
)
old_scene_text = "You haven't marked a scene change in over an hour. Are you sure you want to continue?"
color_spectrum_explantion = (
    "Blue: Camera has not been calibrated in over an hour\n\nRed: Camera has never been calibrated"
)

camera_page_title = {
    "live": "Camera Feed",
    "traj": "*Live Trajectory*",
    "replay": "<Replaying Last Trajectory>",
    "practice_traj": "*Practice Run*",
}

camera_page_instr = {
    "live": "Click two images to swap them, or double click one image to enlarge it (click again to return)",
    "traj": "Press 'A' to mark a success, or 'B' to mark a failure",
    "replay": "Would you like to save or delete this trajectory?",
    "practice_traj": "Press 'A' or 'B' to end the trial run",
}
