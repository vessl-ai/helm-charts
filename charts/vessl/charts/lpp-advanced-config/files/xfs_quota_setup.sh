#!/bin/sh
set -eu

PROJ_NAME=$(basename "$VOL_DIR")
PROJ_ID=$(od -An -N4 -t u4 < /dev/urandom | tr -d ' ')
XFS_NAME=$(dirname "$VOL_DIR")

_install_xfsprogs() {
    /bin/echo -e "\033[1;32mInstalling xfsprogs...\033[0m"
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y xfsprogs
}

_create_dir() {
    /bin/echo -e "\033[1;32mCreating directory\033[0m: ${VOL_DIR}"
    mkdir -m 0777 -p "$VOL_DIR"
}

_setup_xfs_quota() {
    /bin/echo -e "\033[1;32mCreating project...\033[0m (ID: ${PROJ_ID}, name: ${PROJ_NAME})"
    /bin/echo "${PROJ_ID}:${VOL_DIR}" >> /etc/projects
    /bin/echo "${PROJ_NAME}:${PROJ_ID}" >> /etc/projid

    if ! [[ -v "XFS_QUOTA_SIZE" ]]
    then
        /bin/echo -e "\033[1;31mThe shell variable 'XFS_QUOTA_SIZE' is not set!\033[0m"
        /bin/echo -e "It is likely that something is wrong with the chart configuration."
        /bin/echo -e "Defaulting to 10 GB."
        XFS_QUOTA_SIZE=10g
    fi

    /bin/echo -e "\033[1;32mRunning xfs_quota commands...\033[0m"
    xfs_quota -x -c "project -s ${PROJ_NAME}"
    xfs_quota -x -c "limit -p bhard=${XFS_QUOTA_SIZE} ${PROJ_NAME}" "${XFS_NAME}"
    xfs_quota -x -c "report -pbih" "${XFS_NAME}"
}

##################
# MAIN STARTS HERE
##################

_install_xfsprogs
_create_dir
_setup_xfs_quota

/bin/echo -e "\033[1;32mSetup complete!\033[0m"
sleep 10 # TODO: remove me