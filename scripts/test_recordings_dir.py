#!/usr/bin/env python3
"""
Test script to verify that the recordings directory is working correctly.
"""
import os
import pathlib
import datetime

# Get the home directory
home_dir = str(pathlib.Path.home())
recordings_dir = os.path.join(home_dir, "recordings")

print(f"Checking if recordings directory exists: {recordings_dir}")
if not os.path.exists(recordings_dir):
    print("Creating recordings directory...")
    os.makedirs(recordings_dir, exist_ok=True)
    print("Created successfully.")
else:
    print("Recordings directory already exists.")

# Create test directories for success and failure
today = datetime.date.today()
success_dir = os.path.join(recordings_dir, "success", str(today))
failure_dir = os.path.join(recordings_dir, "failure", str(today))

print(f"Creating test directories for today ({today}):")
print(f"  - Success directory: {success_dir}")
print(f"  - Failure directory: {failure_dir}")

os.makedirs(success_dir, exist_ok=True)
os.makedirs(failure_dir, exist_ok=True)

# Create a test file
test_file_path = os.path.join(success_dir, "test_file.txt")
with open(test_file_path, "w") as f:
    f.write(f"Test file created at {datetime.datetime.now()}")

print(f"Created test file: {test_file_path}")
print("Test completed successfully.") 