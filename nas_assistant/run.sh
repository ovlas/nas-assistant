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
        bashio::log.error "Disco '${DISK}' non trovato. Collegalo e riavvia l'add-on."
        export NAS_DISK_STATE=missing
    else
        bashio::log.info "Monto ${DEVICE} in ${NAS_ROOT}"
        mount "${DEVICE}" "${NAS_ROOT}"
        export NAS_DISK_STATE=mounted
    fi
else
    bashio::log.warning "Nessun disco NAS configurato: aprilo dalla barra laterale per sceglierne uno."
    export NAS_DISK_STATE=unconfigured
fi

cd /opt/nas_assistant
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8456 --log-level "${NAS_LOG_LEVEL}"
