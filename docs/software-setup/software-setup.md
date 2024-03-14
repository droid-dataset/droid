---
layout: default
title: Software Setup
has_children: true
has_toc: false
nav_order: 3
permalink: /docs/software-setup
---

## 🖥️  Welcome to the DROID software guides.

The goal of the software guides are to:

1. Configure the Franka robot for DROID application software
2. Configure the Oculus Quest 2 for DROID application software
3. Set up a Polymetis control server on the NUC 
4. Set up a user client and GUI on the laptop/workstation
5. Validate the entire platform setup

There are two methods of installation for the software used in DROID; one can run the application software directly on the host machine or through Docker. Below we provide a brief description of each, importantly it is only necessary to perform one of the two installations, please choose one based on the outlined considerations. We strongly recommend using the Docker installation as it requires less manual configuration and it decouples most of the DROID application config from your host machine configuration.

### Installation Method 1: Docker Installation
Running DROID software through Docker requires less installation steps and allows for machines to easily be repurposed for other sets of software as the application software is containerised. Running the application software through Docker does however require an understanding of Docker the management of Docker containers. 

### Installation Method 2: Host Installation
Running DROID software directly on the host machine requires more installation steps but is worthwhile in the case where machines are dedicated to the DROID setup as it forgoes the need to launch and manage Docker containers. 
