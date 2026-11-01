# NAS Assistant

Your family cloud, at home. Every Home Assistant user gets a private space for photos and files,
plus a **Family** folder shared with everyone, on a dedicated disk of your choice.

The interface follows the language of your Home Assistant profile
(English, Italiano, Español, Français, Deutsch), then your browser's, then English.

## Before you start

- A dedicated USB or SATA disk, any size. Home Assistant backups stay on the main disk and never include NAS files.
- **Protection mode must be off.** NAS Assistant needs to mount the disk:
  on this add-on's page, turn off **Protection mode** and restart the add-on.

## Choosing the disk

1. Open **NAS** from the sidebar (as a Home Assistant administrator).
2. Your disks are listed; the Home Assistant system disk is never shown.
3. Pick a partition and press **Use as is**: your existing files stay where they are.
   Supported filesystems: ext4, exFAT, NTFS.
4. Only if you want a blank disk, use **Erase everything and format**. You will be asked to type a confirmation word.

The disk is remembered and mounted again at every restart. If it is unplugged, NAS Assistant
waits and writes nothing to the main disk.

## Using it

- **Photos**: a timeline by month. Uploads from the gallery go to `Photos/<year>/<month>`.
- **Files**: folders and files of your private space.
- **Family photos / Shared files**: the same, shared with every Home Assistant user.
- Drag and drop files anywhere, or press **Upload**. Large files are sent in pieces and resume by themselves
  if the connection drops.
- **Filter by type** in Files: Photos, Videos, Music, Documents, Archives, Other. Each filter lists the files of that
  type from the whole space, with the folder they are in.
- **Rename and move** from the ⋯ menu of each file or folder (or right-click). You can also drag a file onto a folder
  or onto the path at the top. Moving works between My space and Family too, and is instant: nothing is copied.
- Deleted items go to a trash folder on the disk (`.trash/`), they are not erased right away.

Each family member just needs a Home Assistant user: there are no other accounts.
Home Assistant admins cannot browse other users' private files from the interface.

## Where files are on the disk

```
users/<Home Assistant user id>/   private spaces
family/                           shared with everyone
.trash/                           deleted items
.nas_assistant/                   thumbnails and photo index (can be deleted, they are rebuilt)
```

## Options

| Option | Description |
|---|---|
| `disk` | UUID or label of the NAS disk. Leave empty and choose it from the interface. |
| `family_folder_name` | Name of the shared folder. |
| `log_level` | Log detail. |

Port `8456` is used by the mobile apps (coming soon) on your home network or through Tailscale.

## Help

Questions and bug reports: <https://github.com/ovlas/nas-assistant/issues>
