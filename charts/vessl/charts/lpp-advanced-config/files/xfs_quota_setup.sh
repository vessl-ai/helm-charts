#!/bin/bash
set -e

PROJ_NAME=$(basename "$VOL_DIR")
PROJ_ID=$(od -An -N4 -t u4 < /dev/urandom | tr -d ' ')
XFS_NAME=$(dirname "$VOL_DIR")
VOL_SIZE_MB=$((VOL_SIZE_BYTES / 1024 / 1024))

_create_dir() {
    /bin/echo -e "\033[1;32mCreating directory\033[0m: ${VOL_DIR}"
    mkdir -m 0777 -p "$VOL_DIR"
}

_check_disk_space() {
    OUTPUT=$(df --output=size,avail --block-size=1M "$VOL_DIR" | tail -n1)
    TOTAL_MB=$(echo "$OUTPUT" | awk '{print $1}')
    AVAIL_MB=$(echo "$OUTPUT" | awk '{print $2}')

    /bin/echo "Disk Total: ${TOTAL_MB}MiB, Available: ${AVAIL_MB}MiB"

    MIN_FREE_MB=$(expr "$TOTAL_MB" * 30 / 100)
    ALLOC_MB=$(du --apparent-size -BM /opt/local-path-provisioner/*.img 2>/dev/null \
      | awk '{gsub(/M/, "", $1); sum += $1} END {print sum}')
    [ -z "$ALLOC_MB" ] && ALLOC_MB=0
    /bin/echo "Already reserved: ${ALLOC_MB}MiB"

    TOTAL_REQUESTED_MB=$(expr "$ALLOC_MB" + "$VOL_SIZE_MB")
    /bin/echo "Total after allocation: ${TOTAL_REQUESTED_MB}MiB"

    if [ "$TOTAL_REQUESTED_MB" -gt "$TOTAL_MB" ]; then
        /bin/echo -e "\033[1;31mError: Total reservation (${TOTAL_REQUESTED_MB}MiB) exceeds disk (${TOTAL_MB}MiB)\033[0m"
        exit 1
    fi

    REMAIN_MB=$(expr "$TOTAL_MB" - "$TOTAL_REQUESTED_MB")
    if [ "$REMAIN_MB" -lt "$MIN_FREE_MB" ]; then
        /bin/echo -e "\033[1;31mError: Only ${REMAIN_MB}MiB free would remain (<25%)\033[0m"
        exit 1
    fi
}

_setup_quota() {
    /bin/echo -e "\033[1;32mSetting up quota...\033[0m"
    
    /bin/echo -e "\033[1;32mCreating image file\033[0m: /opt/local-path-provisioner/${PROJ_NAME}.img"
    fallocate -l ${VOL_SIZE_MB}M /opt/local-path-provisioner/${PROJ_NAME}.img
    sync
    /bin/echo -e "\033[1;32mAttaching image file to loopback device\033[0m"
    LOOPDEV=$(losetup --find --show /opt/local-path-provisioner/${PROJ_NAME}.img)
    /bin/echo -e "\033[1;32mFormatting loopback device\033[0m"
    mkfs.ext4 $LOOPDEV
    /bin/echo -e "\033[1;32mMounting loopback device to ${VOL_DIR}\033[0m"
    mount $LOOPDEV $VOL_DIR

    /bin/echo "${LOOPDEV}    ${VOL_DIR}    ext4    loop    0 0" >> /etc/fstab
}

##################
# MAIN STARTS HERE
##################

_create_dir
_check_disk_space
_setup_quota

/bin/echo -e "\033[1;32mSetup complete!\033[0m"