# The DROID Robot Platform

This repository contains the code for setting up your DROID robot platform and using it to collect teleoperated demonstration data. This platform was used to collect the [DROID dataset](https://droid-dataset.github.io), a large, in-the-wild dataset of robot manipulations.

If you are interested in using the DROID dataset for training robot policies, please check out our [policy learning repo](https://github.com/droid-dataset/droid_policy_learning).
For more information about DROID, please see the following links:

[**[Homepage]**](https://droid-dataset.github.io) &ensp; [**[Documentation]**](https://droid-dataset.github.io/droid) &ensp; [**[Paper]**](https://arxiv.org/abs/2403.12945) &ensp; [**[Dataset Visualizer]**](https://droid-dataset.github.io/dataset.html).

![](https://droid-dataset.github.io/droid/assets/index/droid_teaser.jpg)

---

## Setup Guide

We assembled a step-by-step guide for setting up the DROID robot platform in our [developer documentation](https://droid-dataset.github.io/droid).
This guide has been used to set up 18 DROID robot platforms over the course of the DROID dataset collection. Please refer to the steps in this guide for setting up your own robot. Specifically, you can follow these key steps:

1. [Hardware Assembly and Setup](https://droid-dataset.github.io/droid/docs/hardware-setup)
2. [Software Installation and Setup](https://droid-dataset.github.io/droid/docs/software-setup)
3. [Example Workflows to collect data or calibrate cameras](https://droid-dataset.github.io/droid/docs/example-workflows)

### Installation Methods

There are two methods of installation for the DROID software:

#### Docker Installation (Recommended)

Running DROID software through Docker requires less installation steps and allows for machines to easily be repurposed for other sets of software as the application software is containerized. This method decouples most of the DROID application config from your host machine configuration.

To run the application using Docker:

1. Make sure Docker is installed on your system
2. Clone this repository
3. Navigate to the `.docker` directory
4. Build and run the Docker containers:
   ```bash
   docker-compose up -d
   ```
5. Connect to the running container:
   ```bash
   docker exec -it droid_container bash
   ```
6. Inside the container, run the application:
   ```bash
   python scripts/main.py
   ```

For more detailed Docker setup instructions, see the [Software Setup documentation](https://droid-dataset.github.io/droid/docs/software-setup).

#### Host Installation

Running DROID software directly on the host machine requires more installation steps but is worthwhile in the case where machines are dedicated to the DROID setup as it forgoes the need to launch and manage Docker containers.

If you encounter issues during setup, please raise them as issues in this github repo.

## Data Storage Format

The Droid Franka Robots framework supports two data storage formats:

1. **MCAP Format (Default)** - A standardized container format for robotics data that offers better interoperability, self-contained schemas, and efficient reading/writing. See [docs/mcap_format.md](docs/mcap_format.md) for details.

2. **HDF5 Format (Legacy)** - The original format used for storing trajectory data.

To convert existing HDF5 files to MCAP format, use the provided conversion tool:

```bash
python scripts/convert/h5_to_mcap.py path/to/file.h5
```

### Data Storage Location

By default, all recordings are stored in the `~/recordings` directory in your home folder. The directory will be created automatically if it doesn't exist, with the following structure:

- `~/recordings/success/` - Contains successful trajectories
- `~/recordings/failure/` - Contains failed trajectories

Each trajectory is stored in a date-based folder structure for easy organization.
