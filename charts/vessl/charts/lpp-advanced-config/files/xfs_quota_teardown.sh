#!/bin/sh
set -eu

PROJ_NAME=$(basename "$VOL_DIR")
XFS_NAME=$(dirname "$VOL_DIR")

_remove_quota() {
    /bin/echo -e "\033[1;32mRemoving quota...\033[0m"
    LOOPDEV=$(findmnt -n -o SOURCE --target "$VOL_DIR")
    umount "$VOL_DIR"
    losetup -d "$LOOPDEV"
    rm -f /opt/local-path-provisioner/${PROJ_NAME}.img

    sed -i "\|${LOOPDEV}|d" /etc/fstab
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