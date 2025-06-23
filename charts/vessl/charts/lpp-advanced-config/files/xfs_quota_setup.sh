#!/bin/sh
set -e

PROJ_NAME=$(basename "$VOL_DIR")
PROJ_ID=$(od -An -N4 -t u4 < /dev/urandom | tr -d ' ')
XFS_NAME=$(dirname "$VOL_DIR")

_create_dir() {
    /bin/echo -e "\033[1;32mCreating directory\033[0m: ${VOL_DIR}"
    mkdir -m 0777 -p "$VOL_DIR"
}

_check_variables() {
    /bin/echo -e "\033[1;32mChecking env vars...\033[0m"
    if [ -z "${XFS_QUOTA_SIZE}" ]
    then
        /bin/echo -e "\033[1;31mThe shell variable 'XFS_QUOTA_SIZE' is not set!\033[0m"
        /bin/echo -e "It is likely that something is wrong with the chart configuration."
        /bin/echo -e "Defaulting to 10 GB."
        XFS_QUOTA_SIZE=10g
    fi

    if ! echo "${XFS_QUOTA_SIZE}" | grep -q -E '^[1-9][0-9]*[kmg]?$'
    then
        /bin/echo -e "\033[1;31mThe shell variable 'XFS_QUOTA_SIZE' is invalid!\033[0m"
        /bin/echo -e "It should contain an integer, optionally followed by suffixes: k, m, g."
        /bin/echo -e "Ignoring its current value '${XFS_QUOTA_SIZE}', and defaulting to 10 GB."
        XFS_QUOTA_SIZE=10g
    fi
}

_setup_quota() {
    VOL_SIZE_MB=$((VOL_SIZE / 1024 / 1024))
    dd if=/dev/zero of=/opt/local-path-provisioner/mydisk.img bs=1M count="${VOL_SIZE_MB}"
    
    LOOPDEV=$(losetup --find --show /opt/local-path-provisioner/mydisk.img)
    losetup $LOOPDEV /opt/local-path-provisioner/mydisk.img
    mkfs.ext4 $LOOPDEV
    mount $LOOPDEV $VOL_DIR
}

##################
# MAIN STARTS HERE
##################

_create_dir
_check_variables
_setup_quota

/bin/echo -e "\033[1;32mSetup complete!\033[0m"