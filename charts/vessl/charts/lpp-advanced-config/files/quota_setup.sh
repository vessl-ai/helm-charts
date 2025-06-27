#!/bin/sh
set -e

PROJ_NAME=$(basename "$VOL_DIR")
VOL_SIZE_MB=$((VOL_SIZE_BYTES / 1024 / 1024))
IMAGE_FILE="${VOL_DIR_PARENT}/${PROJ_NAME}.img"

# Track what has been created for rollback
DIR_CREATED=false
IMAGE_CREATED=false
MOUNTED=false
FSTAB_UPDATED=false

_cleanup() {
    /bin/echo -e "\033[1;33mRolling back changes...\033[0m"
    
    # Unmount if mounted
    if [ "$MOUNTED" = true ]; then
        /bin/echo "Unmounting ${VOL_DIR}"
        umount -d "$VOL_DIR" 2>/dev/null || true
    fi
    
    # Remove from fstab if added
    if [ "$FSTAB_UPDATED" = true ]; then
        /bin/echo "Removing entry from /etc/fstab"
        sed -i "\|${IMAGE_FILE}|d" /etc/fstab 2>/dev/null || true
    fi
    
    # Remove image file if created
    if [ "$IMAGE_CREATED" = true ]; then
        /bin/echo "Removing image file ${IMAGE_FILE}"
        rm -f "$IMAGE_FILE" 2>/dev/null || true
    fi
    
    # Remove directory if created
    if [ "$DIR_CREATED" = true ]; then
        /bin/echo "Removing directory ${VOL_DIR}"
        rm -rf "$VOL_DIR" 2>/dev/null || true
    fi
    
    /bin/echo -e "\033[1;33mRollback complete\033[0m"
    exit 1
}

# Set up trap to call cleanup on any error
trap _cleanup ERR

_create_dir() {
    /bin/echo -e "\033[1;32mCreating directory\033[0m: ${VOL_DIR}"
    mkdir -m 0777 -p "$VOL_DIR"
    DIR_CREATED=true
}

_check_disk_space() {
    # Get total and available disk space in MiB
    OUTPUT=$(df --output=size,avail --block-size=1M "$VOL_DIR" | tail -n1)
    TOTAL_MB=$(echo "$OUTPUT" | awk '{print $1}')
    AVAIL_MB=$(echo "$OUTPUT" | awk '{print $2}')
    /bin/echo "Disk Total: ${TOTAL_MB}MiB, Available: ${AVAIL_MB}MiB"

    # Calculate max allocation as 70% of total disk space
    MAX_ALLOC_MB=$(( TOTAL_MB * 70 / 100 ))
    /bin/echo "Max allocation: ${MAX_ALLOC_MB}MiB, At least 30% of the disk must be free"

    # Get total reserved space in MiB
    ALLOC_MB=$(du --apparent-size -BM ${VOL_DIR_PARENT}/*.img 2>/dev/null \
      | awk '{gsub(/M/, "", $1); sum += $1} END {print sum}')
    [ -z "$ALLOC_MB" ] && ALLOC_MB=0
    /bin/echo "Already reserved: ${ALLOC_MB}MiB"

    # Calculate total requested space after allocation
    TOTAL_REQUESTED_MB=$(expr "$ALLOC_MB" + "$VOL_SIZE_MB")
    /bin/echo "Total after allocation: ${TOTAL_REQUESTED_MB}MiB"

    # Check if total requested space exceeds max allocation
    if [ "$TOTAL_REQUESTED_MB" -gt "$MAX_ALLOC_MB" ]; then
        /bin/echo -e "\033[1;31mError: Total reservation (${TOTAL_REQUESTED_MB}MiB) exceeds disk (${MAX_ALLOC_MB}MiB)\033[0m"
        exit 1
    fi
}

_setup_quota() {
    /bin/echo -e "\033[1;32mSetting up quota...\033[0m"
    
    # Create image file
    fallocate -l ${VOL_SIZE_MB}M ${IMAGE_FILE}
    IMAGE_CREATED=true
    
    # Format the image
    mkfs.ext4 ${IMAGE_FILE}
    
    # Mount the image
    /bin/echo -e "\033[1;32mMounting image file to ${VOL_DIR}\033[0m"
    mount -o loop ${IMAGE_FILE} ${VOL_DIR}
    MOUNTED=true
    
    # Add to fstab
    /bin/echo "${IMAGE_FILE}    ${VOL_DIR}    ext4    defaults,loop,nofail    0 0" >> /etc/fstab
    FSTAB_UPDATED=true
}

##################
# MAIN STARTS HERE
##################

_create_dir
_check_disk_space
_setup_quota

# Remove trap since we succeeded
trap - ERR

/bin/echo -e "\033[1;32mSetup complete!\033[0m"
