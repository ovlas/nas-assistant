#!/usr/bin/with-contenv bashio
set -e

DISK="$(bashio::config 'disk')"
# Disk chosen from the setup wizard, used when the option is left empty.
if ! bashio::var.has_value "${DISK}" && [ -f /data/disk.json ]; then
    DISK="$(jq -r '.uuid // empty' /data/disk.json)"
fi
export NAS_ROOT=/nas
export NAS_FAMILY_NAME="$(bashio::config 'family_folder_name')"
export NAS_LOG_LEVEL="$(bashio::config 'log_level')"
mkdir -p "${NAS_ROOT}"

if bashio::var.has_value "${DISK}"; then
    # DISK can be a UUID or a filesystem label.
    DEVICE="$(blkid -U "${DISK}" 2>/dev/null || blkid -L "${DISK}" 2>/dev/null || true)"
    if [ -z "${DEVICE}" ]; then
        bashio::log.error "Disk '${DISK}' not found. Plug it in and restart the add-on."
        export NAS_DISK_STATE=missing
    else
        bashio::log.info "Mounting ${DEVICE} on ${NAS_ROOT}"
        nas-mount "${DEVICE}" "${NAS_ROOT}"
        export NAS_DISK_STATE=mounted
    fi
else
    bashio::log.warning "No NAS disk configured: open NAS Assistant from the sidebar to choose one."
    export NAS_DISK_STATE=unconfigured
fi

cd /opt/nas_assistant
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8456 --log-level "${NAS_LOG_LEVEL}"
