#!/usr/bin/with-contenv bashio
set -e

# Disk picked from the device list in the Configuration tab. The Supervisor grants
# the add-on access to that one disk, so it works with protection mode on.
# Unset optional options come back as "null": read them only when they have a value.
DEVICE_OPTION=""
if bashio::config.has_value 'device'; then DEVICE_OPTION="$(bashio::config 'device')"; fi
DISK="$(bashio::config 'disk')"
# Disk chosen from the setup wizard, used when the option is left empty.
if ! bashio::var.has_value "${DISK}" && [ -f /data/disk.json ]; then
    DISK="$(jq -r '.uuid // empty' /data/disk.json)"
fi
export NAS_ROOT=/nas
export NAS_FAMILY_NAME="$(bashio::config 'family_folder_name')"
export NAS_LOG_LEVEL="$(bashio::config 'log_level')"
export NAS_TRASH_DAYS="$(bashio::config 'trash_days')"
export NAS_PUBLIC_URL=""
if bashio::config.has_value 'public_url'; then export NAS_PUBLIC_URL="$(bashio::config 'public_url')"; fi
mkdir -p "${NAS_ROOT}"

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
        else
            bashio::log.error "Can't mount ${DEVICE}. With protection mode on, choose the disk partition in the 'NAS disk device' option of the Configuration tab."
            export NAS_DISK_STATE=missing
        fi
    fi
else
    bashio::log.warning "No NAS disk configured: open NAS Assistant from the sidebar to choose one."
    export NAS_DISK_STATE=unconfigured
fi

# Optional second disk for backups, mounted on /backup. It is used as is:
# backups only ever write inside its "NAS Assistant Backup" folder.
BACKUP_OPTION=""
if bashio::config.has_value 'backup_device'; then BACKUP_OPTION="$(bashio::config 'backup_device')"; fi
export NAS_BACKUP_ROOT=/backup
export NAS_BACKUP_TIME="$(bashio::config 'backup_time')"
export NAS_BACKUP_KEEP_DAYS="$(bashio::config 'backup_keep_days')"
export NAS_BACKUP_STATE=none
if bashio::var.has_value "${BACKUP_OPTION}"; then
    BACKUP_DEVICE="$(readlink -f "${BACKUP_OPTION}" || true)"
    if [ -z "${BACKUP_DEVICE}" ] || [ ! -b "${BACKUP_DEVICE}" ]; then
        bashio::log.error "Backup disk not found."
        export NAS_BACKUP_STATE=missing
    elif [ "${BACKUP_DEVICE}" = "${DEVICE:-}" ]; then
        bashio::log.error "The backup disk is the NAS disk itself: choose another disk for backups."
        export NAS_BACKUP_STATE=same
    else
        mkdir -p "${NAS_BACKUP_ROOT}"
        bashio::log.info "Mounting backup disk ${BACKUP_DEVICE} on ${NAS_BACKUP_ROOT}"
        if nas-mount "${BACKUP_DEVICE}" "${NAS_BACKUP_ROOT}"; then
            export NAS_BACKUP_STATE=mounted
            # Two partitions of the same physical disk don't protect from a disk failure.
            NAS_PARENT="$(lsblk -no PKNAME "${DEVICE:-/nonexistent}" 2>/dev/null || true)"
            BACKUP_PARENT="$(lsblk -no PKNAME "${BACKUP_DEVICE}" 2>/dev/null || true)"
            if [ -n "${NAS_PARENT}" ] && [ "${NAS_PARENT}" = "${BACKUP_PARENT}" ]; then
                export NAS_BACKUP_SAME_DISK=1
                bashio::log.warning "NAS and backup are partitions of the same physical disk."
            fi
        else
            # A disk the NAS can't use as is (new, or e.g. formatted for a Mac): offer to initialize it.
            BACKUP_FSTYPE="$(blkid -p -s TYPE -o value "${BACKUP_DEVICE}" 2>/dev/null || true)"
            case "${BACKUP_FSTYPE}" in
                ext4|exfat|ntfs)
                    bashio::log.error "Can't mount the backup disk ${BACKUP_DEVICE}."
                    export NAS_BACKUP_STATE=missing ;;
                *)
                    bashio::log.warning "The backup disk has no usable filesystem (${BACKUP_FSTYPE:-none}): initialize it from the Disks page."
                    export NAS_BACKUP_STATE=uninitialized
                    export NAS_BACKUP_FSTYPE="${BACKUP_FSTYPE}" ;;
            esac
        fi
    fi
fi
export NAS_DEVICE="${DEVICE:-}"
export NAS_BACKUP_DEVICE="${BACKUP_DEVICE:-}"

cd /opt/nas_assistant
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8456 --log-level "${NAS_LOG_LEVEL}"
