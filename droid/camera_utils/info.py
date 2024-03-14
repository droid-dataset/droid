from droid.misc.parameters import *

camera_type_dict = {
    hand_camera_id: 0,
    varied_camera_1_id: 1,
    varied_camera_2_id: 1,
}

camera_type_to_string_dict = {
    0: "hand_camera",
    1: "varied_camera",
    2: "fixed_camera",
}

camera_name_dict = {
    hand_camera_id: "Hand Camera",
    varied_camera_1_id: "Varied Camera #1",
    varied_camera_2_id: "Varied Camera #2",
}


def get_camera_name(cam_id):
    if cam_id in camera_name_dict:
        return camera_name_dict[cam_id]
    return cam_id


def get_camera_type(cam_id):
    if cam_id not in camera_type_dict:
        return None
    type_int = camera_type_dict[cam_id]
    type_str = camera_type_to_string_dict[type_int]
    return type_str
