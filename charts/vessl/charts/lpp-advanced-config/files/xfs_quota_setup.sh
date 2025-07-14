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

_setup_xfs_quota() {
    /bin/echo -e "\033[1;32mCreating project...\033[0m (ID: ${PROJ_ID}, name: ${PROJ_NAME})"

    {
        flock -w 30 9
        /bin/echo "${PROJ_ID}:${VOL_DIR}" >> /etc/projects
        /bin/echo "${PROJ_NAME}:${PROJ_ID}" >> /etc/projid

        /bin/echo -e "\033[1;32mRunning xfs_quota commands...\033[0m"
        xfs_quota -x -c "project -s ${PROJ_NAME}"
        xfs_quota -x -c "limit -p bhard=${XFS_QUOTA_SIZE} ${PROJ_NAME}" "${XFS_NAME}"
        xfs_quota -x -c "report -pbih" "${XFS_NAME}"
    } 9>/opt/vessl/xfs-quota-lock
}

##################
# MAIN STARTS HERE
##################

_create_dir
_check_variables
_setup_xfs_quota

/bin/echo -e "\033[1;32mSetup complete!\033[0m"