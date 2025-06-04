import json
import os

# Prepare Filepath #
dir_path = os.path.dirname(os.path.realpath(__file__))


def load_version_info(version_number):
    version_number = version_number.replace(".", "_")
    version_string = "{0}.json".format(version_number)
    version_info_filepath = os.path.join(dir_path, version_string)
    if not os.path.isfile(version_info_filepath):
        return {}
    with open(version_info_filepath, "r") as jsonFile:
        version_info = json.load(jsonFile)
    return version_info
