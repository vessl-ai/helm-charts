#!/bin/sh
set -eu

PROJ_NAME=$(basename "$VOL_DIR")
IMAGE_FILE="${VOL_DIR_PARENT}/${PROJ_NAME}.img"

_remove_quota() {
    set +e

    /bin/echo -e "\033[1;32mRemoving quota...\033[0m"
    umount -d "$VOL_DIR"
    rm -f "$IMAGE_FILE"
    sed -i "\|${IMAGE_FILE}|d" /etc/fstab

    set -e
}

_remove_dir() {
    /bin/echo -e "\033[1;32mRemoving directory:\033[0m ${VOL_DIR}"
    rm -rf "$VOL_DIR"
}

##################
# MAIN STARTS HERE
##################

_remove_quota
_remove_dir

/bin/echo -e "\033[1;32mTeardown complete!\033[0m"
