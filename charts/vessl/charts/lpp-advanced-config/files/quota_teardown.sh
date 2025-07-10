#!/bin/sh
set -eu

PROJ_NAME=$(basename "$VOL_DIR")
IMAGE_FILE="${VOL_DIR_PARENT}/${PROJ_NAME}.img"

_remove_quota() {
    /bin/echo -e "\033[1;32mRemoving quota...\033[0m"
    umount -d "$VOL_DIR" 2>/dev/null || true
    rm -f "$IMAGE_FILE"

    flock -w 10 -e 200 -c "
        /bin/echo \"\$(sed \"/${PROJ_NAME}/d\" /etc/fstab)\" > /etc/fstab
    "
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
