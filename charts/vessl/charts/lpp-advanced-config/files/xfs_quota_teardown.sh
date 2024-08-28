#!/bin/bash
set -eu

PROJ_NAME=$(basename "$VOL_DIR")
XFS_NAME=$(dirname "$VOL_DIR")

_install_xfsprogs() {
    echo -e "\033[1;32mInstalling xfsprogs...\033[0m"
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y xfsprogs
}

_remove_xfs_quota() {
    echo -e "\033[1;32mRunning xfs_quota commands...\033[0m"
    xfs_quota -x -c "limit -p bhard=0 ${PROJ_NAME}" ${XFS_NAME}
    xfs_quota -x -c "report -pbih" ${XFS_NAME}

    echo -e "\033[1;32mRemoving project...\033[0m (name: ${PROJ_NAME})"
    echo "$(sed "/${PROJ_NAME}/d" /etc/projects)" > /etc/projects
    echo "$(sed "/${PROJ_NAME}/d" /etc/projid)" > /etc/projid
}

_remove_dir() {
    echo -e "\033[1;32mRemoving directory:\033[0m ${VOL_DIR}"
    rm -rf "$VOL_DIR"
}

##################
# MAIN STARTS HERE
##################

_install_xfsprogs
_remove_xfs_quota
_remove_dir

echo -e "\033[1;32mTeardown complete!\033[0m"
sleep 10 # TODO: remove me