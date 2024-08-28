#!/bin/sh
set -eu

PROJ_NAME=$(basename "$VOL_DIR")
XFS_NAME=$(dirname "$VOL_DIR")

_remove_xfs_quota() {
    {
        flock -w 30 200

        /bin/echo -e "\033[1;32mRunning xfs_quota commands...\033[0m"
        xfs_quota -x -c "limit -p bhard=0 ${PROJ_NAME}" "${XFS_NAME}"
        xfs_quota -x -c "report -pbih" "${XFS_NAME}"

        /bin/echo -e "\033[1;32mRemoving project...\033[0m (name: ${PROJ_NAME})"
        /bin/echo "$(sed "/${PROJ_NAME}/d" /etc/projects)" > /etc/projects
        /bin/echo "$(sed "/${PROJ_NAME}/d" /etc/projid)" > /etc/projid
    } 200>/opt/vessl/xfs-quota-lock/flock.lock
}

_remove_dir() {
    /bin/echo -e "\033[1;32mRemoving directory:\033[0m ${VOL_DIR}"
    rm -rf "$VOL_DIR"
}

##################
# MAIN STARTS HERE
##################

_remove_xfs_quota
_remove_dir

/bin/echo -e "\033[1;32mTeardown complete!\033[0m"
sleep 10 # TODO: remove me