import json
import os
import time

import numpy as np

dir_path = os.path.dirname(os.path.realpath(__file__))
gui_info_filepath = os.path.join(dir_path, "gui_info.json")


def load_gui_info():
    if not os.path.isfile(gui_info_filepath):
        return {}
    with open(gui_info_filepath, "r") as jsonFile:
        gui_info = json.load(jsonFile)
    return gui_info


def update_gui_info(user=None, building=None, scene_id=None):
    gui_info = load_gui_info()
    if user is not None:
        gui_info["user"] = user
    if building is not None:
        gui_info["building"] = building
    if scene_id is not None:
        existing_id = gui_info.get("scene_id", None)
        if existing_id != scene_id:
            gui_info["scene_id_timestamp"] = time.time()
        gui_info["scene_id"] = scene_id

    with open(gui_info_filepath, "w") as jsonFile:
        json.dump(gui_info, jsonFile)


def generate_scene_id():
    return np.random.randint(0, 1e10)
