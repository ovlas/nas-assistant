# NAS Assistant

Your family cloud, at home. Every Home Assistant user gets a private space for photos and files,
plus a **Family** folder shared with everyone, on a dedicated disk of your choice.

The interface follows the language of your Home Assistant profile
(English, Italiano, Español, Français, Deutsch), then your browser's, then English.

## Before you start

You need a dedicated USB or SATA disk, any size. Home Assistant backups stay on the main disk and never include NAS files.

## Choosing the disk

**Recommended — protection mode on**

1. Plug in the disk, then on this add-on's page open **Configuration**.
2. In **NAS disk device** pick the partition of your disk (the entry ending in `-part1`, `-part2`, …).
   The Home Assistant system disk is refused by the Supervisor.
3. Save and restart the add-on. Your existing files stay where they are: nothing is formatted.

With protection mode on, the add-on can only touch the disk you picked.
If that disk is unplugged, the add-on will not start until you plug it back in.

**Alternative — protection mode off**

Turn off **Protection mode**, restart the add-on and open **NAS Assistant** from the sidebar (as an administrator).
Your disks are listed (never the Home Assistant system disk): pick a partition and press **Use as is**.
Only if you want a blank disk, use **Erase everything and format** and type the confirmation word.

Supported filesystems: ext4, exFAT, NTFS. The disk is mounted again at every restart.
If it is missing, NAS Assistant writes nothing to the main disk.

## Backup to a second disk

Plug in a second disk and pick its partition in **Backup disk** (Configuration tab), then save and restart.
The Backup card on the Home page unlocks:

- Every night at **Backup time** (default 03:00) the NAS disk is copied to the backup disk. Only what changed is copied.
  If Home Assistant was off at that time, the backup runs a few minutes after the add-on starts.
- Nothing is lost between backups: when a file is changed or deleted, its previous copy is kept for
  **Keep old versions** days (default 30) in `NAS Assistant Backup/versions/<date>/`.
- The latest copy of everything is in `NAS Assistant Backup/current/`, readable on any computer.
- The backup disk is used as is and never formatted: nothing outside its `NAS Assistant Backup` folder is touched.
- Administrators can start a backup at any time with **Back up now**.

Not copied: thumbnails (rebuilt automatically), Recently deleted, uploads still in progress.
Use two different physical disks: two partitions of the same disk don't protect from a disk failure.

## Using it

- **Home**: an iCloud-style welcome page with your storage, latest photos, recent files, what the family
  shared lately, your favorites and Recently deleted. Tap any card to open it.
- **Photos**: a timeline by month. Uploads from the gallery go to `Photos/<year>/<month>`.
- **Files**: folders and files of your private space, as a list, icons or a grid (buttons at the top right).
- **Family photos / Shared files**: the same, shared with every Home Assistant user.
- Drag and drop files anywhere, or press **Upload**. Large files are sent in pieces and resume by themselves
  if the connection drops.
- **Filter by type** in Files: Photos, Videos, Music, Documents, Archives, Other. Each filter lists the files of that
  type from the whole space, with the folder they are in.
- **Rename** from the ⋯ menu (right-click on a computer, long press on a phone), or with the pencil in the photo viewer:
  the name becomes editable in place with the extension left out of the selection. Enter saves, Esc cancels.
- **Move** from the same menu, or drag a file onto a folder or onto the path at the top. Moving works between
  My space and Family too, and is instant: nothing is copied.
- **Favorites**: tap the heart in the photo viewer (or press `.`), or choose **Add to Favorites** from the ⋯ menu
  of any file or folder. The **Favorites** filter in Photos and in Files lists them. Favorites are personal, also in
  Family, and follow items when they are renamed or moved.
- **Recently deleted**: deleted items go here, with **Undo** right after deleting. From there you can **Restore** an item
  to where it was (its folders are recreated if needed) or **Delete forever**, one item or the whole trash.
  Items are erased for good after 30 days; change it with the `trash_days` option (0 = never).
  Each person has their own Recently deleted, also for items deleted from Family.

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
| `device` | Partition of the NAS disk. Recommended, works with protection mode on. |
| `disk` | UUID or label of the NAS disk (advanced). |
| `family_folder_name` | Name of the shared folder. |
| `backup_device` | Optional second disk for nightly backups. |
| `backup_time` | When the nightly backup runs (HH:MM). |
| `backup_keep_days` | Days previous versions of changed or deleted files are kept. |
| `trash_days` | Days an item stays in Recently deleted before it is erased for good (0 = never). |
| `log_level` | Log detail. |

Port `8456` is used by the mobile apps (coming soon) on your home network or through Tailscale.

## Help

Questions and bug reports: <https://github.com/ovlas/nas-assistant/issues>
