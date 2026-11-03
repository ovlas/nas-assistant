#!/usr/bin/with-contenv bashio
set -e

# Disks picked in the Configuration tab or in NAS Assistant. The Supervisor grants the
# add-on access to them, so it works with protection mode on. NAS Assistant takes them out
# of the options when it stops (a disk unplugged meanwhile would stop Home Assistant from
# starting it) and remembers them in /data/disks.json: an option left empty reads it there.
# Unset optional options come back as "null": read them only when they have a value.
chosen_disk() {
    if bashio::config.has_value "$1"; then
        bashio::config "$1"
    elif [ -f /data/disks.json ]; then
        jq -r --arg o "$1" '.[$o] // empty' /data/disks.json 2>/dev/null || true
    fi
}
DEVICE_OPTION="$(chosen_disk device)"
DISK="$(bashio::config 'disk')"
# Disk chosen from the setup wizard, used when the option is left empty.
if ! bashio::var.has_value "${DISK}" && [ -f /data/disk.json ]; then
    DISK="$(jq -r '.uuid // empty' /data/disk.json)"
fi
export NAS_ROOT=/nas
export NAS_FAMILY_NAME="$(bashio::config 'family_folder_name')"
export NAS_LOG_LEVEL="$(bashio::config 'log_level')"
export NAS_TRASH_DAYS="$(bashio::config 'trash_days')"
export NAS_DLNA=false
if bashio::config.true 'dlna'; then export NAS_DLNA=true; fi
export NAS_PUBLIC_URL=""
if bashio::config.has_value 'public_url'; then export NAS_PUBLIC_URL="$(bashio::config 'public_url')"; fi
mkdir -p "${NAS_ROOT}"

# A disk Home Assistant hasn't given access to yet can't even be read: it must never look
# like a disk with no filesystem (that would offer to initialize, i.e. erase, it).
readable() { dd if="$1" of=/dev/null bs=4096 count=1 2>/dev/null; }

if bashio::var.has_value "${DEVICE_OPTION}" || bashio::var.has_value "${DISK}"; then
    if bashio::var.has_value "${DEVICE_OPTION}"; then
        DEVICE="$(readlink -f "${DEVICE_OPTION}" || true)"
    else
        # DISK can be a UUID or a filesystem label.
        DEVICE="$(blkid -U "${DISK}" 2>/dev/null || blkid -L "${DISK}" 2>/dev/null || true)"
    fi
    if [ -z "${DEVICE}" ] || [ ! -b "${DEVICE}" ]; then
        bashio::log.error "NAS disk not found. Plug it in and restart the add-on."
        export NAS_DISK_STATE=missing
    else
        bashio::log.info "Mounting ${DEVICE} on ${NAS_ROOT}"
        if nas-mount "${DEVICE}" "${NAS_ROOT}"; then
            export NAS_DISK_STATE=mounted
        elif ! readable "${DEVICE}"; then
            bashio::log.error "Can't open ${DEVICE} yet: NAS Assistant gets access to it and restarts."
            export NAS_DISK_STATE=missing
        else
            # A new disk with no filesystem at all: offer to initialize it (only on the user's request).
            NAS_FSTYPE="$(blkid -p -s TYPE -o value "${DEVICE}" 2>/dev/null || true)"
            if [ -z "${NAS_FSTYPE}" ]; then
                bashio::log.warning "${DEVICE} has no filesystem: initialize it from NAS Assistant."
                export NAS_DISK_STATE=uninitialized
            else
                bashio::log.error "Can't mount ${DEVICE} (${NAS_FSTYPE})."
                export NAS_DISK_STATE=missing
            fi
        fi
    fi
else
    bashio::log.warning "No NAS disk configured: open NAS Assistant from the sidebar to choose one."
    export NAS_DISK_STATE=unconfigured
fi

# Optional extra disks, each used as is: a backup disk (/backup) and an extra-storage
# disk (/storage). They only ever get written inside their "NAS Assistant…" folder.
# mount_extra <option> <mountpoint> <ENV prefix>: sets <prefix>_STATE (none, mounted,
# missing, same, uninitialized), <prefix>_DEVICE and <prefix>_FSTYPE.
mount_extra() {
    local option="$1" target="$2" prefix="$3" device="" fstype="" state=none
    local chosen
    chosen="$(chosen_disk "${option}")"
    if [ -n "${chosen}" ]; then
        device="$(readlink -f "${chosen}" || true)"
        if [ -z "${device}" ] || [ ! -b "${device}" ]; then
            bashio::log.error "Disk for ${option} not found."
            state=missing
        elif [ "${device}" = "${DEVICE:-}" ]; then
            bashio::log.error "The disk for ${option} is the NAS disk itself: choose another disk."
            state=same
        else
            mkdir -p "${target}"
            bashio::log.info "Mounting ${device} on ${target}"
            if nas-mount "${device}" "${target}"; then
                state=mounted
            elif ! readable "${device}"; then
                bashio::log.error "Can't open ${device} yet: NAS Assistant gets access to it and restarts."
                state=missing
            else
                # A disk the NAS can't use as is (new, or e.g. formatted for a Mac): offer to initialize it.
                fstype="$(blkid -p -s TYPE -o value "${device}" 2>/dev/null || true)"
                case "${fstype}" in
                    ext4|exfat|ntfs)
                        bashio::log.error "Can't mount ${device}."
                        state=missing ;;
                    *)
                        bashio::log.warning "${device} has no usable filesystem (${fstype:-none}): initialize it from the Disks page."
                        state=uninitialized ;;
                esac
            fi
        fi
    fi
    export "${prefix}_STATE=${state}" "${prefix}_DEVICE=${device}" "${prefix}_FSTYPE=${fstype}"
}

export NAS_BACKUP_ROOT=/backup
export NAS_BACKUP_TIME="$(bashio::config 'backup_time')"
export NAS_BACKUP_KEEP_DAYS="$(bashio::config 'backup_keep_days')"
mount_extra backup_device "${NAS_BACKUP_ROOT}" NAS_BACKUP
if [ "${NAS_BACKUP_STATE}" = mounted ]; then
    # Two partitions of the same physical disk don't protect from a disk failure.
    NAS_PARENT="$(lsblk -no PKNAME "${DEVICE:-/nonexistent}" 2>/dev/null || true)"
    BACKUP_PARENT="$(lsblk -no PKNAME "${NAS_BACKUP_DEVICE}" 2>/dev/null || true)"
    if [ -n "${NAS_PARENT}" ] && [ "${NAS_PARENT}" = "${BACKUP_PARENT}" ]; then
        export NAS_BACKUP_SAME_DISK=1
        bashio::log.warning "NAS and backup are partitions of the same physical disk."
    fi
fi

export NAS_STORAGE_ROOT=/storage
mount_extra storage_device "${NAS_STORAGE_ROOT}" NAS_STORAGE
if [ "${NAS_STORAGE_STATE}" = mounted ]; then
    # Shown as a folder in every space: the disk's label, or its model.
    NAME="$(blkid -s LABEL -o value "${NAS_STORAGE_DEVICE}" 2>/dev/null || true)"
    [ -n "${NAME}" ] || NAME="$(lsblk -dno MODEL "$(lsblk -no PKNAME "${NAS_STORAGE_DEVICE}" | sed 's|^|/dev/|')" 2>/dev/null | xargs || true)"
    export NAS_STORAGE_NAME="$(echo "${NAME:-Extra disk}" | tr -d '/\\' | sed 's/^\.*//')"
fi
export NAS_DEVICE="${DEVICE:-}"

cd /opt/nas_assistant
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8456 --log-level "${NAS_LOG_LEVEL}"
