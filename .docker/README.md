# Overview

In order to simplify the setup and deployment of DROID across different machines we supply Dockerfiles for both the control server (nuc) and the client machine (laptop). The directory structure is broken down as follows: 

    ├── nuc                                      # directory for nuc docker setup files
    ├──── Dockerfile.nuc                         # nuc image definition
    ├──── docker-compose-nuc.yaml                # nuc container deployment settings
    ├── laptop                                   # directory for laptop docker setup files
    ├──── Dockerfile.laptop                      # laptop image definition
    ├──── docker-compose-laptop.yaml             # laptop container deployment settings
    ├──── entrypoint.sh                          # script that is run on entrypoint of Docker container

We recognise that some users may not already be familiar with Docker, the syntax of Dockerfiles and the syntax of docker compose configuration files. We point the user towards the following resources on these topics:

* [Docker Overview](https://docs.docker.com/get-started/overview/)
* [Dockerfile Reference](https://docs.docker.com/engine/reference/builder/)
* [Docker Compose Overview](https://docs.docker.com/compose/)

# NUC Setup
In order to set up the control server on your NUC run `sudo ./nuc_setup.sh` from this [directory](https://github.com/AlexanderKhazatsky/DROID/tree/main/scripts/setup). Running through all the steps in this script will install host system dependencies and ensure the control server runs automatically in a docker container each time your machine is booted.

Further details on the steps in README.md in the `scripts/setup` directory.

# Laptop Setup  
In order to set up the user client on your laptop run `sudo ./laptop_setup.sh` from this [directory](https://github.com/AlexanderKhazatsky/DROID/tree/main/scripts/setup). Running through all the steps in this script will install host system dependencies and ensure the user client can be run in a docker container.

Further details can be found [README.md](https://github.com/AlexanderKhazatsky/DROID/tree/main/scripts/setup/README.md).

