# NAS Assistant

Your family cloud, at home. Every Home Assistant user gets a private space for photos and files,
plus a **Family** folder shared with everyone, on a dedicated disk of your choice.

The interface follows the language of your Home Assistant profile
(English, Italiano, Español, Français, Deutsch), then your browser's, then English.

## Before you start

You need a dedicated USB or SATA disk, any size. Home Assistant backups stay on the main disk and never include NAS files.

## Choosing the disk

Leave **Protection mode** on: it is never needed to turn it off.

1. Plug in the disk and open **NAS Assistant** from the sidebar (as an administrator).
2. Your disks are listed (never the Home Assistant system disk): press **Use as the NAS disk** on the partition you
   want. Your existing files stay where they are: nothing is formatted. NAS Assistant restarts to apply it
   (Home Assistant grants the add-on access to that disk only).
3. A brand new disk with no filesystem shows **Initialize…** instead: it runs only when you press it and type the
   confirmation word.

You can also pick the partition yourself in **Configuration → NAS disk device**. With protection mode off, the
classic list with **Use as is** / **Erase everything and format** is offered under **Other options** too.

Supported filesystems: ext4, exFAT, NTFS. The disk is mounted again at every restart.
If it is missing, NAS Assistant writes nothing to the main disk.

## Disks

Administrators find **Disks** in the sidebar: the disks connected to Home Assistant (never its own system disk),
what each one is used for and how full it is. A free disk can be given a role, and you can change it later:

- **Use for backups**: every night the NAS is copied onto it, on its own (see below).
- **Use as extra storage**: more room, joined to the NAS disk. Its files appear in the same *Files*,
  *Shared files* and *Photos* as the others, with the same per-user privacy, and its free space adds up. New files go
  to the NAS disk while it has more than 20 GB free (usually the faster disk: an extra disk may be an old USB 2
  drive), then to the disk with the most free space; files can be moved anywhere. Each disk keeps
  its own trash. It is included in the nightly backup. A disk that was used by NAS Assistant before (also as the NAS
  disk) brings its files back as they were.
- **Eject safely**, next to each disk's name: finishes writes and unmounts the disk so you can unplug it.
  For the backup and extra-storage disks, plug it back in and **Put back as …** restores its role in one tap.
  Ejecting the NAS disk asks twice and pauses the NAS for everyone; plug it back in and press **Reactivate**.
- **Use … instead** switches a disk between the two roles, **Stop using it** frees it. Changing roles never erases
  anything: NAS Assistant only ever writes inside its own folder on these disks ("NAS Assistant" or
  "NAS Assistant Backup"), then restarts to apply the change. This works with protection mode on.
- If the NAS can't use a disk's filesystem (a brand new disk, or one formatted for a Mac), **Initialize…** appears.
  It runs only when you press it and type the confirmation word; it erases that disk and makes it ext4.
- The NAS disk, any other partition of the same physical disk, and the Home Assistant system disk are never
  initialized or given a role.
- A disk that doesn't appear is not visible to Home Assistant itself: check its power supply, cable and USB port.

## Uploading

Drag files onto the page or press **Upload**. A panel shows the whole upload: how much is sent out of the total,
what is left, speed and time left, and how many files are uploaded, already there or not uploaded.

- Uploads go straight to the add-on, not through Home Assistant's Ingress (which is very slow for uploads): on the
  home network to its port 8456 when Home Assistant was opened with its local `http://` address (tens of MB/s),
  otherwise to the **Public address** (e.g. Cloudflare), with a pass that only allows uploads and lasts 12 hours.
  Without either, uploads use Ingress as before.
- Files travel in pieces. When the connection drops, the piece is sent again from what really reached the disk,
  with smaller pieces while the network is bad, for up to 10 minutes per file. A locked phone or a background tab
  doesn't stop it.
- A file already on the NAS (same name and size) is skipped. A different file with the same name is kept as
  "name (2)": nothing is ever overwritten.
- If the page is closed mid-way, the panel remembers it: choose the same files again (all of them is fine) and the
  upload goes on from where it stopped. Files that didn't make it can be retried in one tap.

## Watch on the TV

Photos and videos can be shown on any TV or player Home Assistant knows (Chromecast / Google TV, Samsung, LG,
Apple TV, …: add its integration in Home Assistant first):

- In the viewer, the **TV** button plays the photo or video on the TV you pick (the last one is remembered).
- In *Photos*, *Family photos* and in an album, **On the TV** starts a slideshow: photos for a few seconds each,
  videos to the end. A bar at the bottom shows what is playing, with **Stop**.
- Photos are sent as Full HD JPEG, so iPhone HEIC photos show on every TV. Videos are sent as they are: a TV that
  can't play a format (e.g. HEVC on an older Chromecast) shows nothing for it.
- The TV gets a secret link that works for a few hours and **only on the home network**: links coming through a
  tunnel such as Cloudflare are refused. The TV fetches the file from port 8456 of Home Assistant.

## TVs of the house (DLNA)

On the Disks page, **TVs of the house → Turn on** shares the **Family** space with the smart TVs of the home
network (Samsung, LG, Sony, Philips… anything with a DLNA / "Media server" source). The TV finds
**NAS Assistant** among its sources and shows photos, videos and music with the remote, by folder or (photos) by
date. It is read only, and private spaces are never shared: DLNA has no password, so anyone on the home Wi-Fi can
see Family. Off by default.

To be found by the TVs the add-on uses the host network (SSDP on UDP 1900, the media server on port 8200). The web
UI and the API stay on port 8456, and other add-ons still reach it by its hostname (e.g. a Cloudflare Tunnel
pointing to `http://<add-on hostname>:8456`).

## Other files on the disk

A disk often holds more than NAS Assistant's folders: music, old photos, documents copied there over the years.
Administrators find them in **Other files on the disk** (sidebar, under System), for the NAS disk and the
extra-storage disk, also from outside home:

- Browse folders, preview photos and videos, open and download files.
- **Copy to…** puts a file or a whole folder into *My space* or *Family*, where it gets the usual privacy, the
  gallery and the nightly backup. Big folders copy in the background; a message says when it's done.
- It is **read only**: nothing on the disk is renamed, moved or deleted from here. NAS Assistant's own folders and
  system folders (`$RECYCLE.BIN`, `System Volume Information`, `.Trashes`, …) are not shown.

## Plug and play

NAS Assistant watches disks being plugged in and out:

- **A disk it already knows comes back** (the backup or extra-storage disk, or the NAS disk): it takes its role back
  on its own. NAS Assistant restarts for a few seconds, which Home Assistant needs to grant access to a disk.
  An old NAS disk plugged in while another NAS disk is working joins it as extra storage, so its files show again.
  A Home Assistant notification says it is back. While it is unplugged, the Disks page keeps listing it as
  **Not connected**, so its files are never "lost": plugging it in is all there is to do.
- A disk connected at USB 2 speed works normally; the Disks page only mentions that a faster port exists.
- **A disk in use is unplugged without Eject**: it is unmounted and its role remembered for when it comes back. For
  the NAS disk the NAS pauses. Unplugging while files are being written can damage them: use **Eject** when you can.
- **A new disk is plugged in**: nothing is decided for you. A Home Assistant notification and a banner in NAS Assistant
  ask what to use it for (backup or extra storage, from the Disks page).
- **Changing the NAS disk**: while no NAS disk is connected, the start page lists the other disks with
  **Use as the NAS disk**, used as they are. The old disk's files come back when you switch back to it.

Nothing is ever formatted automatically.

## Backup to a second disk

Pick a free disk with **Use for backups** on the Disks page (or choose its partition in **Backup disk** in the
Configuration tab, then save and restart). The Backup card on the Home page unlocks:

- Every night at **Backup time** (default 03:00) the NAS disk is copied to the backup disk. Only what changed is copied.
  If Home Assistant was off at that time, the backup runs a few minutes after the add-on starts.
- Nothing is lost between backups: when a file is changed or deleted, its previous copy is kept for
  **Keep old versions** days (default 30) in `NAS Assistant Backup/versions/<date>/`.
- The latest copy of everything is in `NAS Assistant Backup/current/`, readable on any computer.
- The backup disk is used as is and never formatted: nothing outside its `NAS Assistant Backup` folder is touched.
- Administrators can start a backup at any time with **Back up now**.

Not copied: thumbnails (rebuilt automatically), Recently deleted, uploads still in progress.
Use two different physical disks: two partitions of the same disk don't protect from a disk failure.

## Phones: backup in the background

Web pages can't upload in the background on phones: the browser pauses them as soon as the screen locks.

**With the Home Assistant app only**: open NAS Assistant from its sidebar and upload as usual. The screen stays on
while uploading (where the phone allows it); if you leave the app, the upload pauses and continues by itself from
where it stopped when you come back. Automatic camera-roll backup needs the NAS Assistant app.

**With the NAS Assistant app (iPhone and Android, coming soon)**: on the Home page open
**iPhone and devices → Connect a phone** and scan the QR code with the app. The code works once and for
10 minutes only; the key it is exchanged for goes straight into the phone's secure storage and never appears on
screen. Each phone can be disconnected from the same card.

**Without the app (iPhone, advanced)**: an **iOS Shortcut** keeps going in the background:

1. On the Home page open **iPhone and devices → iOS Shortcut (advanced)**. You get an address and a key
   for that device (the key only allows uploads into your space; disconnect the device any time).
2. Build the Shortcut following the steps shown there: *Repeat with Each* → *Get Contents of URL*
   (POST, header `Authorization`, Form body with a File field named `file`).
3. Use it from the Share menu of Photos or Files, or from an Automation (e.g. "when the charger is connected",
   with *Find Photos* added in the last day) for a nightly camera-roll backup.

Photos and videos go to `Photos/<year>/<month>` of the day they were taken; other files to `Uploads`
(folder names follow the phone's language). A file that is already there is skipped, so sending the same photos
twice costs nothing.

**Which address the phone uses**

| Your setup | Address | Notes |
|---|---|---|
| Any (at home) | `http://homeassistant.local:8456` | Works with no setup on the home Wi-Fi. Best for the overnight automation and large videos. |
| Cloudflared add-on | your own host, e.g. `https://nas.example.com` | In the Cloudflared add-on add an *additional host* with service `http://<NAS Assistant hostname>:8456` (shown on this add-on's Info page), then set **Public address** here. Cloudflare limits each request to 100 MB: send larger videos at home. |
| Tailscale add-on | `http://<Tailscale name of Home Assistant>:8456` | Private, encrypted, no size limit; needs the Tailscale app on the phone. |
| Home Assistant Cloud (Nabu Casa) only | home address | Nabu Casa forwards Home Assistant itself, not add-on ports, so Shortcuts can't reach NAS Assistant through it. The overnight automation at home still backs up everything; the upcoming mobile app will log in through Home Assistant and also work via Nabu Casa. |

## Using it

- **Home**: an iCloud-style welcome page with your storage, latest photos, recent files, what the family
  shared lately, your favorites and Recently deleted. Tap any card to open it.
- **Photos**: a timeline by month. Uploads from the gallery go to `Photos/<year>/<month>`.
- **Files**: folders and files of your private space, as a list, icons or a grid (buttons at the top right).
- **Sort** (button at the top) by name, size, date added (when the file arrived on the NAS) or date created (for
  photos and videos, when they were shot), either way round. It applies to every list (files, types, favorites,
  albums and dossiers, other files on the disk) and is remembered on each device.
- **Family photos / Shared files**: the same, shared with every Home Assistant user.
- Drag and drop files anywhere, or press **Upload**. Large files are sent in pieces and resume by themselves
  if the connection drops.
- **Filter by type** in Files: Photos, Videos, Music, Documents, Archives, Other. Each filter lists the files of that
  type from the whole space, with the folder they are in.
- **Rename** from the ⋯ menu (right-click on a computer, long press on a phone), or with the pencil in the photo viewer:
  the name becomes editable in place with the extension left out of the selection. Enter saves, Esc cancels.
- **Move** from the same menu, or drag a file onto a folder or onto the path at the top. Moving works between
  My space and Family too, and is instant: nothing is copied.
- **Collections**: albums for photos and dossiers for documents (a trip, a house purchase, a project). A collection
  only groups files: they stay where they are, can be in several collections, and follow renames and moves.
  Add files from the ⋯ menu (*Add to collection…*) or from the photo viewer; removing one from a collection never
  deletes it. A collection is personal, or shared with the family (shared ones only take files from Family, so
  nobody sees someone else's private files).
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
| `backup_device` | Optional disk for nightly backups (set it from the Disks page). |
| `storage_device` | Optional disk used as extra storage (set it from the Disks page). |
| `backup_time` | When the nightly backup runs (HH:MM). |
| `backup_keep_days` | Days previous versions of changed or deleted files are kept. |
| `public_url` | Address of NAS Assistant from outside home (e.g. a Cloudflare Tunnel host), shown when you connect a phone. |
| `trash_days` | Days an item stays in Recently deleted before it is erased for good (0 = never). |
| `log_level` | Log detail. |
| `dlna` | Share the Family space with the TVs of the house (also from the Disks page). |

Port `8456` is used by the mobile apps (coming soon) on your home network or through Tailscale.

## Help

Questions and bug reports: <https://github.com/ovlas/nas-assistant/issues>
