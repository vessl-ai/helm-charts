#!/bin/sh
set -eu

PROJ_NAME=$(basename "$VOL_DIR")
XFS_NAME=$(dirname "$VOL_DIR")

_remove_xfs_quota() {
    {
        flock -w 30 9

        /bin/echo -e "\033[1;32mRunning xfs_quota commands...\033[0m"
        xfs_quota -x -c "limit -p bhard=0 ${PROJ_NAME}" "${XFS_NAME}"
        xfs_quota -x -c "report -pbih" "${XFS_NAME}"

        /bin/echo -e "\033[1;32mRemoving project...\033[0m (name: ${PROJ_NAME})"
        /bin/echo "$(sed "/${PROJ_NAME}/d" /etc/projects)" > /etc/projects
        /bin/echo "$(sed "/${PROJ_NAME}/d" /etc/projid)" > /etc/projid
    } 9>/opt/vessl/xfs-quota-lock
}

_remove_quota() {
    /bin/echo -e "\033[1;32mRemoving quota...\033[0m"
    LOOPDEV=$(findmnt -n -o SOURCE --target "$VOL_DIR")
    umount "$VOL_DIR"
    losetup -d "$LOOPDEV"
    rm -f /opt/local-path-provisioner/mydisk.img
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