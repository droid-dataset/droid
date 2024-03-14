# Postprocessing Instructions

Running `scripts/postprocess.py` will iterate through all folders/files dumped as part of data collection, verify
that each trajectory contains the relevant information, convert all SVO files to MP4s, and then uploads all
trajectory data to Amazon S3.

This README only applies to `scripts/postprocess.py`; to get started, see the Quickstart section below. The remaining
sections provide more context about what this script is doing, as well as helpful tips for debugging common errors.

**Note:** This script tries to be smart and efficient by caching intermediate states/errors as it runs. You can trust
that script will never delete or overwrite existing files, nor will it overwrite anything in S3. However,
cache invalidation is hard -- if the script logs an error, and you fix it, it may/may not update the "errored_paths"
entry of the cache file properly. It's on you to manually fix those entries in `<lab>-cache.json` for now (or message
Sidd if you have a better solution)!

## Quickstart

To get started, make sure you're on the data collection laptop! Pull the latest version of the DROID repository;
there should be a folder `cache/postprocessing` at the repository root. If your lab has uploaded data to Google
Drive prior to August 1st, 2023, you should see a file `<lab>-cache.json` in this folder!

To upload new demonstrations:

1. Install new Python dependencies for post-processing (`pip install -e .`); should install `boto3` and `pyrallis`.

2. Read and familiarize yourself with the script `scripts/postprocess.py`, especially the arguments in the
   dataclass `DROIDUploadConfig`. Note the labs and members defined in `REGISTERED_MEMBERS`.
   + If your lab is not in the dictionary, add it (along with your first member's name + associated 8-character ID).
   + The comments above the dictionary definition walk through how to add new members (and generate IDs)!

3. Create a file `droid-credentials.json` (or whatever, just make sure **it is not tracked by git**) with the AWS
   Access Key and Secret Key that was sent to your lab leads by email.
   + The JSON file should be formatted as ```{"AccessKeyID": <ACCESS KEY>, "SecretAccessKey": <SECRET KEY>}```
   + Update `DROIDUploadConfig.credentials_json` with the path to this JSON file.
   + **If you don't have AWS Credentials:** Check the section "AWS S3 Access" below!

4. Update `DROIDUploadConfig.lab` with your unique lab identifier from `REGISTERED_MEMBERS`. Update
   `DROIDUploadConfig.data_dir` with the path to the folder containing your demonstrations. This folder is
   automatically created by the data collection GUI, and should be formatted following the
   "Expected Data Directory Structure" section below.

5. Run the script from the root of the repository `python scripts/postprocess.py`.
   + If you run into errors, or the script outputs "Errors in... [FIX IMMEDIATELY]" or "Errors in... [VERIFY]",
     consult the "Debugging Common Failures" section below.

**Note:** This script will occasionally exit with a message "EXITING TO PREVENT SVO SEGFAULT" due to a known issue with
bulk converting SVO files to MP4s. If you see this, just rerun the script (because of caching, it'll just pick up where
it left off).

---

### AWS S3 Access

One member per lab should email Sidd to get credentials to upload demonstrations to the S3 bucket. Each lab will only
get one set of credentials, to be stored on the data collection laptop; the credentials only allow for uploading to
the DROID S3 bucket (no other AWS permissions).

Make sure to check that your lab doesn't already have a set of valid credentials (the following users should already
have credentials):

```
- Sasha Khazatsky (Lab(s): IRIS, TRI)
- Joey Hejna (Lab: ILIAD)
- Marion Lepert (Lab: IPRL)
- Mohan Kumar (Lab: GuptaLab)
- Sungjae Park (Lab: CLVR)
```

If your name is on the above list, your credentials should've been sent to you (search your inbox for an email from
LastPass -- subject line should be something like `sravya.reddy@tri.global shared secure information with you`).

### Expected Data Directory Structure

This script expects that the `data_dir` containing demonstrations has the following structure. This structure is strict,
and follows the format dumped by the Data Collection script. If your data is not in this format, please reformat
prior to running the script!

```
- <data_dir>
    - success/ (Contains the user-labelled "success" trajectories)
        - <YYYY>-<MM>-<DD>/ (Corresponds to the day the trajectory was collected on)
            - <Day>_<Mon>_<DD>_<HH>:<MM>:<SS>_<YYYY>/ (Path to an individual trajectory directory)
                - trajectory.h5 (HDF5 file containing states, actions, camera data as time series)
                - recordings/
                    - SVO/ (Directory containing ZED SVO files -- one for each of the three cameras)
                        - <wrist_serial.svo>
                        - <ext1_serial.svo>
                        - <ext2_serial.svo>

    - [Optional] failure/ (Contains the user-labelled "failure" or otherwise unsuccessful trajectories)
        - .../ (Same format as above)
```

The script will complain/log any deviations from the above format... but try to keep things organized!

### Debugging Common Failures

Running `python scripts/postprocess.py` will iterate through all demonstrations in `data_dir` throwing either "hard"
or "silent" errors. Hard errors stop execution of the script until they are fixed, while "silent" errors are logged
and reported to you at the end of execution (and are stored in the `<lab>-cache.json` file).

#### Debugging "Hard" Failures

- `Unexpected Directory <PATH> -- did you accidentally nest directories?`
  + This error indicates finding a directory "<YYYY>-<MM>-<DD>/" nested in another "<YYYY>-<MM>-<DD>/" directory.
    This usually only happens if a user has accidentally moved / copied directories. Fix by moving the nested directory
    up the file tree (merging directories if necessary), or deleting the nested directory (if duplicate).

- `Invalid Directory <PATH> -- check timestamp format!`
  + This error indicates that a directory was found under `success/` or `failure/` that **does not** follow the above
    format ("<YYYY>-<MM>-<DD>"). Fix by removing the offending directory (or moving it to the appropriate place).

- `User alias <NAME> not in REGISTERED_LAB_MEMBERS or REGISTERED_ALIASES`
  + This error indicates that the given name (should be "<F>irst <Last>", case-sensitive) is not in the top-level
    `REGISTERED_LAB_MEMBERS` dictionary. If this is a new user, add them to the dictionary, following the comment
    above the dictionary definition.
  + **However:** If this is a typo or alias of an existing user (e.g., "Sasha -> Alexander", "Sdid" --> "Sidd), add this
    alias to the `REGISTERED_ALIASES` dictionary instead. **In general, avoid using multiple names for the same user!**

- `Lab <LAB> not in REGISTERED_LAB_MEMBERS`
  + This error means that `<LAB>` is not recognized. If you're a lab joining the project, add an entry to
  + `REGISTERED_LAB_MEMBERS`. Otherwise, check the `lab` parameter you set in `DROIDUploadConfig` or message Sidd.

- `Problem connection to S3 bucket; verify credentials JSON file!`
  + There's an issue connection to AWS S3; verify the credentials in the JSON file were copied correctly, otherwise
    message Sidd.

If there is any other error thrown during script execution, message Sidd to debug!

#### Debugging "Silent" Failures

These failures are logged during execution, and only reported in aggregate in the final message printed by the script.
To get individual errors, look at your lab's cache file `cache/postprocessing/<lab>-cache.json`. Under the `totals`
key, you'll see a JSON dictionary with the following:

```
{
    "totals": {
      ...

      // You want to look at this entry!
      "errored": {
        "success": <Ns> (# of trajectories from success/ subdirectory>),
        "failure": <Nf> (# of trajectories from failure/ subdirectory)
      },
    },
    ...

    // Actual error messages!
    "errored_paths": {
      "success": {
        "<Relative Path from `data_dir`>": "<ERROR MSG",
      },
      "failure": {
        "<Relative Path from `data_dir`>": "<ERROR MSG",
      }
    }
}
```

**Note that `success` and `failure` here refer to the type of demonstration (successful/unsuccesful), and NOT return
values from the postprocessing script!**

Based on the type of demonstration (`success/` or `failure/`), you might want to handle the following errors
differently. Where possible, we've outlined how each case should be handled:

- `[Indexing Error] Missing/Invalid HDF5! If the HDF5 is missing/corrupt, you can delete this trajectory!`
  + [Case: `success` OR `failure`] Make sure the `trajectory.h5` is actually missing from the directory (or is
    unreadable/corrupt). If it's unreparable, this demonstration has no useful data, so remove this directory.

- `[Indexing Error] Missing SVO Files! Ensure all 3 SVO files are in <timestamp>/recordings/SVO/<serial>.svo!`
  + [Case: `success/`] Successful trajectories should have *all 3 SVO* files present! If this is not the case, relabel
    this trajectory as a `failure/`.
  + [Case: `failure/`] Failure trajectories might not have all 3 SVO files; in this case, just keep the directory on
    disk (it will not be uploaded at this time). We'll figure out what to do about these soon!

- `[Processing Error] JSON Metadata Parse Error`
  + [Case: `success/`] This error only happens if the `trajectory.h5` file is corrupt or otherwise missing information.
    Fix the H5 file if possible, otherwise relabel this trajectory as a `failure/`.
  + [Case: `failure/`] If `trajectory.h5` is corrupt/unreadable, keep this directory on disk (it will not be uploaded).
    Similar to above, we'll figure out what to do about these soon!

- `[Processing Error] Corrupted SVO / Failed Conversion`
  + [Case: `success/`] This error happens if there's an issue with SVO conversion -- check that the SVO files are
    actually unreadable, and if so, mark as a `failure/`.
  + [Case: `failure/`] Same as above; keep on disk, but it will not be uploaded!

When you've handled *all errors* the value of `"totals" --> "success/"` in `<lab>-cache.json` should be 0!
