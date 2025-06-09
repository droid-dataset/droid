import multiprocessing
import subprocess
import threading


def run_terminal_command(command):
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stdin=subprocess.PIPE, shell=True, executable="/bin/bash", encoding="utf8"
    )

    return process


def run_threaded_command(command, args=(), daemon=True):
    thread = threading.Thread(target=command, args=args, daemon=daemon)
    thread.start()

    return thread


def run_multiprocessed_command(command, args=()):
    process = multiprocessing.Process(target=command, args=args)
    process.start()

    return process
