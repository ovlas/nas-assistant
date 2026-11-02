# NAS Assistant — Architecture

> Your family cloud, at home, inside Home Assistant.

## Principles

1. **Plug & play**: install the add-on, pick a disk, done. No new accounts.
2. **Users are the Home Assistant users**: every HA user gets a private space.
3. **Dedicated disk**: NAS data lives on a secondary disk chosen by the user
   (USB/SATA, any capacity). The main disk stays Home Assistant's.
4. **Separate backups**: HA backups never include the NAS files and stay on the main disk.
5. **Everything local**: no cloud service required.
6. **Never lose data**: an existing disk is used as is; formatting only happens when explicitly asked and confirmed.

## Components

```
┌──────────────────────────── Home Assistant OS ────────────────────────────┐
│                                                                           │
│  Main disk (SD/eMMC/SSD)               Dedicated NAS disk (USB/SATA)      │
│  ├─ Home Assistant Core                └─ mounted on /nas by the add-on   │
│  ├─ HA backups  ◄── stay here             ├─ users/<HA user id>/          │
│  └─ NAS Assistant add-on (/data =         ├─ family/                      │
│       configuration only, small)          ├─ .trash/                      │
│                                           └─ .nas_assistant/ (db, thumbs) │
│                                                                           │
│  NAS Assistant add-on                                                     │
│  ├─ API (FastAPI)  ── port 8456 (mobile apps, LAN/VPN)                    │
│  ├─ Web UI         ── via Ingress (HA sidebar)                            │
│  └─ integration    ── sensors: used space, users, disk state              │
└───────────────────────────────────────────────────────────────────────────┘
        ▲                       ▲                          ▲
   Browser (Ingress)     iOS / Android app            HA automations
```

- **Add-on** (this repository): backend and web UI.
- **Mobile app** ([ovlas/nas-assistant-app](https://github.com/ovlas/nas-assistant-app)): **Flutter**, one codebase for the App Store and Play Store.
  Immich made the same choice and showed that background photo backup works well this way.
- **HA integration** (later): sensors and events (`nas_assistant_file_uploaded`, …).

## Languages

The web UI follows the language of the Home Assistant user profile, then the browser language,
then falls back to English. Translations live in [`nas_assistant/web/i18n.js`](../nas_assistant/web/i18n.js);
add-on options are translated in [`nas_assistant/translations/`](../nas_assistant/translations).
Server messages are in English and translated by the UI.

## Identity and permissions

| Where the request comes from | How the user is identified |
|---|---|
| Web UI inside HA (Ingress) | `X-Remote-User-Id` header added by the Supervisor. Trusted **only** when the request comes from the Ingress IP `172.30.32.2`. |
| Mobile app | Home Assistant OAuth login (same flow as the Companion app). The app sends `Authorization: Bearer <HA token>`, the add-on asks HA who the user is (`auth/current_user`) and caches the answer. |

Result: **one login, Home Assistant's**. A user disabled in HA also loses access to the NAS.

Spaces:
- `personal` → `/nas/users/<user_id>/`, visible only to its owner
- `family` → `/nas/family/`, shared with every user
- HA admins **cannot** see private files from the UI. (Privacy against physical access to the disk: per-user encryption, phase 3.)

## Remote access

The app picks the best route by itself, in this order:

1. **Direct LAN** — `http://<ha-ip>:8456`. Full speed at home (found via mDNS).
2. **Tailscale** (recommended away from home) — the community Tailscale add-on: no open ports,
   encrypted, full speed. NAS Assistant detects it and guides the setup.
3. **Own domain / Cloudflare Tunnel** — for people who already run a reverse proxy.
4. **Fallback through Home Assistant (Nabu Casa / HA external URL)** — the app opens an Ingress session with the HA token.
   Works anywhere with no setup but is slower: fine for browsing and downloading;
   large backups wait for home Wi-Fi or Tailscale.

Uploads are **resumable** and sent in 16 MB pieces: if the connection drops or switches from Wi-Fi to 4G,
the upload continues where it stopped, and no request goes over the 100 MB limit of tunnels such as Cloudflare.
App options: "Wi-Fi only", "only while charging", "only at home".

## Disk

- The add-on mounts the chosen disk inside its own container on `/nas`.
- Recommended: the partition is picked in the add-on `device` option (`device(subsystem=block)`). The Supervisor then
  grants access to that one device and refuses the system disk, so protection mode stays on.
  With protection mode off, `full_access` lets the web wizard list and read every disk instead.
- Supported filesystems: ext4 (recommended), exFAT, NTFS (read-write via ntfs3, ntfs-3g as fallback).
- Guided setup in the web UI: lists the disks, shows capacity, lets you **use a disk as is** (nothing is deleted)
  or format it (double confirmation).
- The Home Assistant system disk is never listed.
- If the disk is missing, the add-on writes **nothing** to the main disk: it shows a warning and waits.
- The add-on `/data` only holds configuration → HA backups stay small.

## Roadmap

**Phase 1 — MVP (add-on)**
- [x] HA user recognition via Ingress
- [x] Personal space and Family folder
- [x] File list, folders, upload, download, trash
- [x] Dedicated disk mount + guided setup (use as is, or format as ext4)
- [x] Photo/video thumbnails (Pillow + HEIC, ffmpeg) and timeline gallery
- [x] Resumable chunked uploads
- [x] Catalogue by file type, rename, move (also between My space and Family)
- [x] Background uploads from phones: one-time QR pairing, per-device upload-only keys, resumable device uploads; iOS Shortcut as fallback
- [ ] Mobile app (Flutter, iOS + Android): QR pairing and camera-roll backup in the background
- [x] Backup to a second disk: nightly incremental copy with versions
- [x] Files as list, icons or grid; Home Assistant profile picture
- [x] iCloud-style welcome page
- [x] Favorites for files, folders, photos and videos
- [x] Recently deleted with restore, delete forever and undo; inline rename
- [x] Multilingual UI (English, Italiano, Español, Français, Deutsch)
- [ ] Per-user quotas
- [ ] Sensors in HA

**Phase 2 — Mobile app**
- [ ] Login with HA, automatic route choice (LAN/Tailscale/HA)
- [ ] Automatic camera roll backup in the background (iOS and Android)
- [ ] Family shared albums, share links

**Phase 3 — Better than iCloud**
- [ ] Search, deduplication
- [ ] Local face and object recognition
- [ ] Per-user encryption
- [ ] SMB/WebDAV access for Mac/PC
- [ ] Backup to a remote site; browse and restore backups from the web UI
