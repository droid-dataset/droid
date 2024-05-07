#!/bin/bash

# Function to display devices and ask for confirmation
function confirm_devices {
    devices=$(adb devices)
    
    echo "List of devices:"
    echo "$devices"
    
    read -p "Is your oculus device connected? (y/n): " confirmation
    
    if [ "$confirmation" != "y" ] && [ "$confirmation" != "Y" ]; then
	return 1
    fi
}

# print out nice ascii art
ascii=$(cat ./intro.txt)
echo "$ascii"

echo "Welcome to the DROID setup process."


read -p "Is this your first time setting up the machine? (yes/no): " first_time

# path variables
ROOT_DIR="$(git rev-parse --show-toplevel)"
DOCKER_COMPOSE_DIR="$ROOT_DIR/.docker/laptop"
DOCKER_COMPOSE_FILE="$DOCKER_COMPOSE_DIR/docker-compose-laptop.yaml"


if [ "$first_time" = "yes" ]; then
	# ensure local files are up to date and git lfs is configured
	echo -e "Ensure all submodules are cloned and oculus_reader APK file pulled locally \n"

	eval "$(ssh-agent -s)"
	ssh-add /home/robot/.ssh/id_ed25519
	curl -s https://packagecloud.io/install/repositories/github/git-lfs/script.deb.sh | bash
	apt update && apt install -y git-lfs
	git lfs install # has to be run only once on a single user account
	cd $ROOT_DIR && git rm ./src/droid/fairo && git submodule update --recursive --init
	
	# install docker
	echo -e "Install docker \n"

	apt-get update
	apt-get install ca-certificates curl gnupg
	install -m 0755 -d /etc/apt/keyrings
	curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
	chmod a+r /etc/apt/keyrings/docker.gpg
	echo \
	  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
	  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
	  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
	apt-get update
	apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

	# install and configure nvidia container toolkit
	echo -e "Install Nvidia container toolkit \n"

	distribution=$(. /etc/os-release;echo $ID$VERSION_ID) \
	      && curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
	      && curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
		    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
		    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
	apt-get update
	apt-get install -y nvidia-container-toolkit
	nvidia-ctk runtime configure --runtime=docker
	systemctl restart docker

else
	echo -e "\nWelcome back!\n"
fi

read -p "Have you installed the oculus_reader APK file on your Oculus Quest 2? (yes/no): " first_time

if [ "$first_time" = "no" ]; then

	# install APK on Oculus device
	echo -e "Install APK on oculus device \n"

	#usermod -aG plugdev $LOGNAME
	#newgrp plugdev
	apt install -y android-tools-adb android-sdk-platform-tools-common
	adb start-server

	read -p "Connect your Oculus Quest 2 via USB-C, and approve USB debugging within device. Confirm with y when complete? (y/n): " confirmation
	    
	if [ "$confirmation" != "y" ] && [ "$confirmation" != "Y" ]; then
		return 1
	else
		return exit 1
	fi


	# Retry loop
	max_retries=3
	retry_count=0

	while ! confirm_devices; do
	    ((retry_count++))
	    if [ "$retry_count" -ge "$max_retries" ]; then
		echo "Max retry attempts reached. Aborting installation."
		exit 1
	    fi
	    echo "Retrying..."
	done

	echo $ROOT_DIR
	pip3 install -e $ROOT_DIR/droid/oculus_reader
	python3 $ROOT_DIR/droid/oculus_reader/oculus_reader/reader.py
	echo cleaning up threads ...
	sleep 5
	adb kill-server
fi

# expose parameters as environment variables
echo -e "Set environment variables from parameters file \n"

PARAMETERS_FILE="$(git rev-parse --show-toplevel)/droid/misc/parameters.py"
awk -F'[[:space:]]*=[[:space:]]*' '/^[[:space:]]*([[:alnum:]_]+)[[:space:]]*=/ && $1 != "ARUCO_DICT" { gsub("\"", "", $2); print "export " $1 "=" $2 }' "$PARAMETERS_FILE" > temp_env_vars.sh
source temp_env_vars.sh
export ROOT_DIR=$ROOT_DIR
export NUC_IP=$nuc_ip
export LAPTOP_IP=$laptop_ip
export ROBOT_IP=$robot_ip
export SUDO_PASSWORD=$sudo_password
export ROBOT_TYPE=$robot_type
export ROBOT_SERIAL_NUMBER=$robot_serial_number
export HAND_CAMERA_ID=$hand_camera_id
export VARIED_CAMERA_1_ID=$varied_camera_1_id
export VARIED_CAMERA_2_ID=$varied_camera_2_id
export LIBFRANKA_VERSION=$libfranka_version
export ROOT_DIR=$ROOT_DIR
rm temp_env_vars.sh

if [ "$ROBOT_TYPE" == "panda" ]; then
        export LIBFRANKA_VERSION=0.9.0
else
        export LIBFRANKA_VERSION=0.10.0
fi


# ensure GUI window is accessible from container
echo -e "Set Docker Xauth for x11 forwarding \n"

export DOCKER_XAUTH=/tmp/.docker.xauth
rm $DOCKER_XAUTH
touch $DOCKER_XAUTH
xauth nlist $DISPLAY | sed -e 's/^..../ffff/' | xauth -f $DOCKER_XAUTH nmerge -

# build client server container

read -p "Do you want to rebuild the container image? (yes/no): " first_time

if [ "$first_time" = "yes" ]; then
	echo -e "build control server container \n"
	cd $DOCKER_COMPOSE_DIR && docker compose -f $DOCKER_COMPOSE_FILE build
fi

# find ethernet interface on device
echo -e "\n set static ip \n"

echo "Select an Ethernet interface to set a static IP for:"

interfaces=$(ip -o link show | grep -Eo '^[0-9]+: (en|eth|ens|eno|enp)[a-z0-9]*' | awk -F' ' '{print $2}')

# Display available interfaces for the user to choose from
select interface_name in $interfaces; do
    if [ -n "$interface_name" ]; then
        break
    else
        echo "Invalid selection. Please choose a valid interface."
    fi
done

echo "You've selected: $interface_name"

# Add and configure the static IP connection
nmcli connection delete "laptop_static"
nmcli connection add con-name "laptop_static" ifname "$interface_name" type ethernet
nmcli connection modify "laptop_static" ipv4.method manual ipv4.address $LAPTOP_IP/24
nmcli connection up "laptop_static"

echo "Static IP configuration complete for interface $interface_name."

# run docker container
read -p "Please plug in and out each camera connected via usb and press enter once done?: " _

echo "Starting ADB server on host machine"
adb kill-server
adb -a nodaemon server start &> /dev/null &

# Retry loop
max_retries=3
retry_count=0

while ! confirm_devices; do
    ((retry_count++))
    if [ "$retry_count" -ge "$max_retries" ]; then
	echo "Max retry attempts reached. Aborting installation."
	exit 1
    fi
    echo "Retrying..."
done

echo -e "run client application \n"
docker compose -f $DOCKER_COMPOSE_FILE up
