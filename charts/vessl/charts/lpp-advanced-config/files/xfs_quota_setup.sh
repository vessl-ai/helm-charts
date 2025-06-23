#!/bin/sh
set -e

PROJ_NAME=$(basename "$VOL_DIR")
PROJ_ID=$(od -An -N4 -t u4 < /dev/urandom | tr -d ' ')
XFS_NAME=$(dirname "$VOL_DIR")

_create_dir() {
    /bin/echo -e "\033[1;32mCreating directory\033[0m: ${VOL_DIR}"
    mkdir -m 0777 -p "$VOL_DIR"
}

_setup_quota() {
    /bin/echo -e "\033[1;32mSetting up quota...\033[0m"
    VOL_SIZE_MB=$((VOL_SIZE_BYTES / 1024 / 1024))

    read TOTAL_MB AVAIL_MB < <(
      df --output=size,avail --block-size=1M "$VOL_DIR" \
        | tail -n1
    )
    /bin/echo "Partition Total: ${TOTAL_MB}MiB, Avail: ${AVAIL_MB}MiB"
    MIN_FREE_MB=$(( TOTAL_MB * 25 / 100 ))
    /bin/echo "Require at least 25% free: ${MIN_FREE_MB}MiB"

    if (( VOL_SIZE_MB > AVAIL_MB )); then
        /bin/echo -e "\033[1;31mError: Not enough space (${AVAIL_MB}MiB available, ${VOL_SIZE_MB}MiB needed)\033[0m"
        exit 1
    fi

    if (( AVAIL_MB - VOL_SIZE_MB < MIN_FREE_MB )); then
        /bin/echo -e "\033[1;31mError: Would leave only $(( AVAIL_MB - VOL_SIZE_MB ))MiB free (<25% of ${TOTAL_MB}MiB)\033[0m"
        exit 1
    fi

    /bin/echo -e "\033[1;32mCreating image file\033[0m: /opt/local-path-provisioner/${PROJ_NAME}.img"
    fallocate -l ${VOL_SIZE_MB}M /opt/local-path-provisioner/${PROJ_NAME}.img
    sync
    /bin/echo -e "\033[1;32mAttaching image file to loopback device\033[0m"
    LOOPDEV=$(losetup --find --show /opt/local-path-provisioner/${PROJ_NAME}.img)
    /bin/echo -e "\033[1;32mFormatting loopback device\033[0m"
    mkfs.ext4 $LOOPDEV
    /bin/echo -e "\033[1;32mMounting loopback device to ${VOL_DIR}\033[0m"
    mount $LOOPDEV $VOL_DIR
}

##################
# MAIN STARTS HERE
##################

_create_dir
_setup_quota

/bin/echo -e "\033[1;32mSetup complete!\033[0m"