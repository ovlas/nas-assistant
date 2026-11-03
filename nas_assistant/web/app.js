// All URLs are relative so the UI works behind Ingress (/api/hassio_ingress/<token>/).
const state = { space: "personal", view: "home", path: "", kind: "all", layout: savedLayout(), user: null, items: [], viewerIndex: -1 };
const $ = (id) => document.getElementById(id);

// Files layout (list, icons, grid): a per-browser preference.
function savedLayout() {
  try { return ["list", "icons", "grid"].includes(localStorage.getItem("nas-layout")) ? localStorage.getItem("nas-layout") : "list"; }
  catch { return "list"; }
}

// --- Icons (outline, SF Symbols-like) -----------------------------------------

const ICON_PATHS = {
  photos: '<rect x="3" y="5" width="18" height="14" rx="3"/><circle cx="15.5" cy="9.5" r="1.6"/><path d="M3.5 17l5-5.5 4 4 2.5-2.5 5.5 5"/>',
  folder: '<path d="M3 7.5A2.5 2.5 0 0 1 5.5 5H9l2 2.2h7.5A2.5 2.5 0 0 1 21 9.7v7.8a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 17.5z"/>',
  family: '<circle cx="9" cy="8" r="3"/><circle cx="17" cy="9.5" r="2.3"/><path d="M3.5 19c.6-3.2 2.8-5 5.5-5s4.9 1.8 5.5 5M14.5 14.6c.7-.4 1.6-.6 2.5-.6 2.3 0 3.9 1.5 4.4 4"/>',
  share: '<path d="M8 12h-1.5A2.5 2.5 0 0 0 4 14.5v3A2.5 2.5 0 0 0 6.5 20h11a2.5 2.5 0 0 0 2.5-2.5v-3a2.5 2.5 0 0 0-2.5-2.5H16M12 15V3.5M8.5 7 12 3.5 15.5 7"/>',
  disk: '<rect x="5" y="3" width="14" height="18" rx="3"/><circle cx="12" cy="10" r="3.5"/><path d="M14.5 17.5 12.8 13"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  upload: '<path d="M12 16V4M7.5 8.5 12 4l4.5 4.5M4.5 15v2.5A2.5 2.5 0 0 0 7 20h10a2.5 2.5 0 0 0 2.5-2.5V15"/>',
  download: '<path d="M12 4v12M7.5 11.5 12 16l4.5-4.5M4.5 15v2.5A2.5 2.5 0 0 0 7 20h10a2.5 2.5 0 0 0 2.5-2.5V15"/>',
  trash: '<path d="M4.5 6.5h15M9.5 6.5V4.8c0-.7.5-1.3 1.2-1.3h2.6c.7 0 1.2.6 1.2 1.3v1.7M6.5 6.5l.8 12.2c.1 1 .9 1.8 1.9 1.8h5.6c1 0 1.8-.8 1.9-1.8l.8-12.2"/>',
  close: '<path d="M6 6l12 12M18 6 6 18"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  up: '<path d="M6 15l6-6 6 6"/>',
  down: '<path d="M6 9l6 6 6-6"/>',
  left: '<path d="M15 5l-7 7 7 7"/>',
  right: '<path d="M9 5l7 7-7 7"/>',
  play: '<path d="M8 5.5v13l10.5-6.5z" fill="currentColor"/>',
  file: '<path d="M7 3h6.5L19 8.5V19a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/><path d="M13 3v6h6"/>',
  video: '<rect x="3" y="6" width="13" height="12" rx="2.5"/><path d="M16 10.5l5-3v9l-5-3"/>',
  audio: '<path d="M9 18V6l11-2v12"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="17.5" cy="16" r="2.5"/>',
  document: '<path d="M7 3h6.5L19 8.5V19a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/><path d="M13 3v6h6M8.5 13h7M8.5 16.5h5"/>',
  archive: '<rect x="3.5" y="4" width="17" height="5" rx="1.5"/><path d="M5 9v9.5A1.5 1.5 0 0 0 6.5 20h11a1.5 1.5 0 0 0 1.5-1.5V9M10 13h4"/>',
  more: '<circle cx="5.5" cy="12" r="1.3" fill="currentColor"/><circle cx="12" cy="12" r="1.3" fill="currentColor"/><circle cx="18.5" cy="12" r="1.3" fill="currentColor"/>',
  rename: '<path d="M14.5 5.5l4 4M4 20l1-4.5L15.8 4.7a1.8 1.8 0 0 1 2.5 0l1 1a1.8 1.8 0 0 1 0 2.5L8.5 19z"/>',
  homeAssistant: '<path fill="currentColor" stroke="none" d="M21.8,13H20V21H13V17.67L15.79,14.88L16.5,15C17.66,15 18.6,14.06 18.6,12.9C18.6,11.74 17.66,10.8 16.5,10.8A2.1,2.1 0 0,0 14.4,12.9L14.5,13.61L13,15.13V9.65C13.66,9.29 14.1,8.6 14.1,7.8A2.1,2.1 0 0,0 12,5.7A2.1,2.1 0 0,0 9.9,7.8C9.9,8.6 10.34,9.29 11,9.65V15.13L9.5,13.61L9.6,12.9A2.1,2.1 0 0,0 7.5,10.8A2.1,2.1 0 0,0 5.4,12.9A2.1,2.1 0 0,0 7.5,15L8.21,14.88L11,17.67V21H4V13H2.25C1.83,13 1.42,13 1.42,12.79C1.43,12.57 1.85,12.15 2.28,11.72L11,3C11.33,2.67 11.67,2.33 12,2.33C12.33,2.33 12.67,2.67 13,3L17,7V6H19V9L21.78,11.78C22.18,12.18 22.59,12.59 22.6,12.8C22.6,13 22.2,13 21.8,13M7.5,12A0.9,0.9 0 0,1 8.4,12.9A0.9,0.9 0 0,1 7.5,13.8A0.9,0.9 0 0,1 6.6,12.9A0.9,0.9 0 0,1 7.5,12M16.5,12C17,12 17.4,12.4 17.4,12.9C17.4,13.4 17,13.8 16.5,13.8A0.9,0.9 0 0,1 15.6,12.9A0.9,0.9 0 0,1 16.5,12M12,6.9C12.5,6.9 12.9,7.3 12.9,7.8C12.9,8.3 12.5,8.7 12,8.7C11.5,8.7 11.1,8.3 11.1,7.8C11.1,7.3 11.5,6.9 12,6.9Z"/>',
  // The current Home Assistant logo: blue house with the white circuit "tree".
  haLogo: '<path d="M12 2.6 21 10.3V20a1.6 1.6 0 0 1-1.6 1.6H4.6A1.6 1.6 0 0 1 3 20v-9.7z" fill="#18BCF2" stroke="#18BCF2" stroke-width="1.6" stroke-linejoin="round"/><g stroke="#fff" stroke-width="1.35" fill="none" stroke-linecap="round"><path d="M12 21.6V10.6M12 17.2 8.9 14.1M12 14.9l3.1-3.1"/></g><g fill="#fff" stroke="none"><circle cx="12" cy="9.4" r="1.45"/><circle cx="8.1" cy="13.3" r="1.3"/><circle cx="15.9" cy="11" r="1.3"/></g>',
  tv: '<rect x="3" y="4.5" width="18" height="12.5" rx="2.5"/><path d="M8.5 20.5h7M12 17v3.5"/>',
  eject: '<path d="M12 4.5 4.5 13h15z"/><path d="M5 17.5h14"/>',
  album: '<rect x="3" y="7" width="14" height="13" rx="2.5"/><path d="M7 4h11.5A2.5 2.5 0 0 1 21 6.5V16"/><path d="M3.5 17l4-4 3 3 2-2 4 4"/>',
  dossier: '<path d="M3 8a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M8 13h8M8 16.5h5"/>',
  sidebar: '<rect x="3.5" y="4.5" width="17" height="15" rx="3"/><path d="M9.5 4.5v15"/>',
  layoutList: '<path d="M8.5 6.5h11M8.5 12h11M8.5 17.5h11"/><circle cx="4.8" cy="6.5" r=".9" fill="currentColor"/><circle cx="4.8" cy="12" r=".9" fill="currentColor"/><circle cx="4.8" cy="17.5" r=".9" fill="currentColor"/>',
  layoutIcons: '<rect x="4" y="4" width="6.5" height="6.5" rx="1.6"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="1.6"/><rect x="4" y="13.5" width="6.5" height="6.5" rx="1.6"/><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1.6"/>',
  layoutGrid: '<rect x="3.5" y="4" width="17" height="10" rx="2"/><path d="M3.5 18h7M13.5 18h7"/>',
  phone: '<rect x="6.5" y="2.5" width="11" height="19" rx="2.6"/><path d="M10.5 18.5h3"/>',
  copy: '<rect x="8" y="8" width="12" height="12" rx="2.4"/><path d="M16 8V6.4A2.4 2.4 0 0 0 13.6 4H6.4A2.4 2.4 0 0 0 4 6.4v7.2A2.4 2.4 0 0 0 6.4 16H8"/>',
  lock: '<rect x="5" y="10.5" width="14" height="10" rx="2.5"/><path d="M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5"/>',
  backup: '<path d="M7 18.5h-.5a4 4 0 0 1-.6-7.96A5.5 5.5 0 0 1 16.6 9a3.8 3.8 0 0 1 .9 7.5"/><path d="M12 20.5v-8M9 15.5l3-3 3 3"/>',
  home: '<path d="M4 10.5 12 4l8 6.5V19a1.5 1.5 0 0 1-1.5 1.5H15v-6H9v6H5.5A1.5 1.5 0 0 1 4 19z"/>',
  heart: '<path d="M12 20s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7.2a4.3 4.3 0 0 1 7.5 2.6C19.5 15.4 12 20 12 20z"/>',
  heartFill: '<path fill="currentColor" d="M12 20s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7.2a4.3 4.3 0 0 1 7.5 2.6C19.5 15.4 12 20 12 20z"/>',
  restore: '<path d="M4 12a8 8 0 1 0 2.4-5.7M4 4.5v3.8h3.8"/><path d="M12 8v4.2l2.8 1.8"/>',
  move: '<path d="M3 7.5A2.5 2.5 0 0 1 5.5 5H9l2 2.2h7.5A2.5 2.5 0 0 1 21 9.7v7.8a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 17.5z"/><path d="M9 13.5h6M12.5 11l2.5 2.5-2.5 2.5"/>',
};

// File types, as catalogued by the server (app/kinds.py).
const KIND_ICONS = {
  favorite: "heart", image: "photos", video: "video", audio: "audio", document: "document", archive: "archive", other: "file",
};
const KIND_FILTERS = ["all", "favorite", "image", "video", "audio", "document", "archive", "other"];
const GALLERY_FILTERS = ["all", "favorite"];

function icon(name) {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${ICON_PATHS[name] || ""}</svg>`;
}

function paintIcons(root = document) {
  root.querySelectorAll("i[data-icon]").forEach((i) => { if (!i.innerHTML) i.innerHTML = icon(i.dataset.icon); });
}

// --- Helpers ------------------------------------------------------------------

async function api(url, opts) {
  const res = await fetch(url, opts);
  if (!res.ok) {
    const message = tError((await res.json().catch(() => ({}))).detail || res.statusText);
    throw Object.assign(new Error(message), { status: res.status });
  }
  return res.json();
}

const qs = (params) => new URLSearchParams(params).toString();
const join = (...parts) => parts.filter(Boolean).join("/");
const IMAGE = /\.(jpe?g|png|gif|webp|heic|heif|bmp|tiff?)$/i;
const VIDEO = /\.(mp4|mov|m4v|webm|mkv|avi|3gp)$/i;
const kindOf = (name) => (IMAGE.test(name) ? "image" : VIDEO.test(name) ? "video" : null);

// "Other files on the disk": space "disk" lists the disks, "disk:nas" / "disk:storage" browse one (read only).
const isDisk = (space) => typeof space === "string" && space.startsWith("disk");
const thumbUrl = (path, v, size = "s", space = state.space) => `api/thumb?${qs({ space, path, size, v })}`;
const fileUrl = (path, inline = false, space = state.space) =>
  `api/download?${qs({ space, path, ...(inline ? { inline: 1 } : {}) })}`;

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function iconEl(name) {
  const i = el("i");
  i.dataset.icon = name;
  i.innerHTML = icon(name);
  return i;
}

function formatSize(bytes) {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  while (bytes >= 1024 && i < units.length - 1) { bytes /= 1024; i++; }
  return `${bytes.toFixed(i ? 1 : 0)} ${units[i]}`;
}

const capitalize = (s) => s.charAt(0).toUpperCase() + s.slice(1);
const monthFmt = new Intl.DateTimeFormat(LOCALE, { month: "long", year: "numeric" });
const dayFmt = new Intl.DateTimeFormat(LOCALE, { day: "numeric", month: "long", year: "numeric" });
const timeFmt = new Intl.DateTimeFormat(LOCALE, { hour: "2-digit", minute: "2-digit" });
const shortFmt = new Intl.DateTimeFormat(LOCALE, { day: "numeric", month: "short", year: "numeric" });

function fadeIn(img) {
  img.onload = () => img.classList.add("loaded");
  img.onerror = () => img.classList.add("loaded");
}

// --- Navigation ---------------------------------------------------------------

function go(space, view, path = "", kind = "all") {
  Object.assign(state, { space, view, path, kind });
  closeMenu();
  const navView = view === "collection" ? "collections" : view;
  document.querySelectorAll(".nav-item").forEach((b) =>
    b.classList.toggle("active", b.dataset.space === (view === "collection" ? "personal" : isDisk(space) ? "disk" : space)
      && b.dataset.view === navView));
  render();
}

function setHeader(title, subtitle) {
  $("title").textContent = title;
  $("subtitle").textContent = subtitle;
  $("new-folder").hidden = state.view !== "files";
  $("layout-switch").hidden = state.view !== "files";
  document.querySelectorAll("#layout-switch button").forEach((b) => b.classList.toggle("active", b.dataset.layout === state.layout));
  $("upload-btn").hidden = ["trash", "disks", "collections", "collection"].includes(state.view) || isDisk(state.space);
  $("empty-trash").hidden = true;
  $("tv-btn").hidden = true;  // shown by the photo views once they have items
}

function showEmpty(title, text) {
  $("empty").hidden = !title;
  if (title) { $("empty-title").textContent = title; $("empty-text").textContent = text; }
}

// Each render gets a number; a slower, older render that finishes later must not
// draw over the newer one (e.g. switching folder while the previous one loads).
let renderSeq = 0;
const stale = (seq) => seq !== renderSeq;

function render() {
  renderSeq++;
  $("gallery").innerHTML = "";
  $("files").innerHTML = "";
  $("crumbs").innerHTML = "";
  $("chips").innerHTML = "";
  $("home").replaceChildren();
  $("disks").replaceChildren();
  $("disks").hidden = state.view !== "disks";
  $("collections").replaceChildren();
  $("collections").hidden = state.view !== "collections";
  showEmpty(null);
  document.body.classList.toggle("on-home", state.view === "home");
  $("home").hidden = state.view !== "home";
  if (state.view === "home") return renderHome();
  if (state.view === "disks") return renderDisks();
  if (state.view === "collections") return renderCollections();
  if (state.view === "collection") return renderCollection();
  if (state.view === "trash") return renderTrash();
  return state.view === "photos" ? renderGallery() : renderFiles();
}

// --- Gallery ------------------------------------------------------------------

async function renderGallery() {
  const where = t(state.space === "personal" ? "mySpace" : "family");
  setHeader(t(state.space === "personal" ? "photos" : "familyPhotos"), where);
  const seq = renderSeq;
  let items;
  try {
    ({ items } = await api(`api/photos?${qs({ space: state.space })}`));
  } catch (err) {
    return stale(seq) || showEmpty(t("photosLoadError"), err.message);
  }
  if (stale(seq)) return;
  renderChips(GALLERY_FILTERS);
  if (state.openPath) {
    const index = items.findIndex((i) => i.path === state.openPath);
    state.openPath = null;
    if (index >= 0) setTimeout(() => openViewer(index));
  }
  if (state.kind === "favorite") items = items.filter((i) => i.fav);
  state.items = items;
  $("tv-btn").hidden = !items.length;
  const photos = items.filter((i) => i.kind === "image").length;
  const videos = items.length - photos;
  setHeader($("title").textContent,
    [where, t("photoCount", { n: photos }), videos ? t("videoCount", { n: videos }) : ""].filter(Boolean).join(" · "));
  if (!items.length) {
    return state.kind === "favorite"
      ? showEmpty(t("noFavTitle"), t("noFavText"))
      : showEmpty(t("noPhotosTitle"), t("noPhotosText"));
  }

  const gallery = $("gallery");
  let section, tiles, currentMonth;
  items.forEach((item, index) => {
    const month = capitalize(monthFmt.format(item.taken * 1000));
    if (month !== currentMonth) {
      currentMonth = month;
      section = el("section", "month");
      const h2 = el("h2", "", month);
      h2.append(el("span"));
      tiles = el("div", "tiles");
      section.append(h2, tiles);
      gallery.append(section);
    }
    section.querySelector("h2 span").textContent = `${tiles.children.length + 1}`;
    tiles.append(tile(item, index));
  });
}

function tile(item, index) {
  const node = el("div", "tile");
  const img = el("img");
  img.loading = "lazy";
  img.alt = item.name;
  fadeIn(img);
  img.src = thumbUrl(item.path, item.v, "s", item.space || state.space);
  node.append(img);
  if (item.kind === "video") {
    const badge = el("span", "badge");
    badge.append(iconEl("play"));
    node.append(badge);
  }
  if (item.fav) {
    const heart = el("span", "fav-badge");
    heart.append(iconEl("heartFill"));
    node.append(heart);
  }
  node.onclick = () => openViewer(index);
  return node;
}

// --- Files --------------------------------------------------------------------

async function renderFiles() {
  if (isDisk(state.space)) return renderDiskFiles();
  const root = t(state.space === "personal" ? "files" : "sharedFiles");
  setHeader(root, t(state.space === "personal" ? "mySpace" : "family"));
  renderChips();
  if (state.kind === "all") renderCrumbs(root);
  $("new-folder").hidden = state.kind !== "all";
  const seq = renderSeq;
  let entries;
  try {
    ({ entries } = state.kind === "all"
      ? await api(`api/files?${qs({ space: state.space, path: state.path })}`)
      : state.kind === "favorite"
        ? await api(`api/favorites?${qs({ space: state.space })}`)
        : await api(`api/files/by-kind?${qs({ space: state.space, kind: state.kind })}`));
  } catch (err) {
    return stale(seq) || showEmpty(t("folderOpenError"), err.message);
  }
  if (stale(seq)) return;
  for (const e of entries) e.path = e.path || join(state.path, e.name);
  // The viewer browses the photos and videos of this list.
  state.items = entries.filter((e) => !e.is_dir && kindOf(e.name))
    .map((e) => ({ path: e.path, name: e.name, kind: kindOf(e.name), taken: e.modified, v: e.v, fav: e.fav }));
  if (!entries.length) {
    return state.kind === "all"
      ? showEmpty(t("emptyFolderTitle"), t("emptyFolderText"))
      : state.kind === "favorite"
        ? showEmpty(t("noFavTitle"), t("noFavText"))
        : showEmpty(t("noKindTitle"), t("noKindText"));
  }
  const list = $("files");
  list.className = `file-list layout-${state.layout}`;
  for (const entry of entries) list.append(fileRow(entry));
}

const DISK_NAMES = { nas: "roleNas", storage: "roleStorage" };
const diskName = (space) => t(DISK_NAMES[space.slice(5)] || "diskFiles");

async function renderDiskFiles() {
  setHeader(t("diskFiles"), state.space === "disk" ? t("diskFilesSub") : diskName(state.space));
  $("new-folder").hidden = true;
  const seq = renderSeq;
  let entries;
  try {
    if (state.space === "disk") {
      const { disks: found } = await api("api/disk/roots");
      if (stale(seq)) return;
      if (found.length === 1) return go(found[0].space, "files");
      entries = found.map((d) => ({ name: t(DISK_NAMES[d.role]), is_dir: true, volume: true, open: d.space, modified: 0, size: 0 }));
    } else {
      ({ entries } = await api(`api/files?${qs({ space: state.space, path: state.path })}`));
    }
  } catch (err) {
    return stale(seq) || showEmpty(t("folderOpenError"), err.message);
  }
  if (stale(seq)) return;
  if (state.space !== "disk") renderCrumbs(diskName(state.space));
  for (const e of entries) e.path = e.path || join(state.path, e.name);
  state.items = entries.filter((e) => !e.is_dir && kindOf(e.name))
    .map((e) => ({ path: e.path, name: e.name, kind: kindOf(e.name), taken: e.modified, v: e.v }));
  if (!entries.length) return showEmpty(t(state.space === "disk" ? "noDiskFilesTitle" : "emptyFolderTitle"), t(state.space === "disk" ? "noDiskFilesText" : "diskFilesEmpty"));
  const list = $("files");
  list.className = `file-list layout-${state.layout}`;
  for (const entry of entries) list.append(fileRow(entry));
}

function renderChips(filters = KIND_FILTERS) {
  const chips = $("chips");
  for (const kind of filters) {
    const chip = el("button", kind === state.kind ? "chip active" : "chip");
    if (kind !== "all") chip.append(iconEl(KIND_ICONS[kind]));
    // In the gallery "All" means all photos and videos.
    chip.append(el("span", "", t(kind === "all" && state.view === "photos" ? "allMedia" : `kind_${kind}`)));
    chip.onclick = () => go(state.space, state.view, kind === "all" ? state.path : "", kind);
    chips.append(chip);
  }
}

async function toggleFavorite(item) {
  await post("api/favorites", { space: item.space || state.space, path: item.path, favorite: item.fav ? "0" : "1" });
  item.fav = !item.fav;
}

function renderCrumbs(root) {
  if (!state.path) return;
  const parts = state.path.split("/");
  const crumbs = $("crumbs");
  [root, ...parts].forEach((label, i) => {
    if (i) crumbs.append(iconEl("right"));
    const a = el("a", "", label);
    a.onclick = () => go(state.space, "files", parts.slice(0, i).join("/"));
    if (i < parts.length && !isDisk(state.space)) dropTarget(a, parts.slice(0, i).join("/"));
    crumbs.append(a);
  });
  crumbs.querySelectorAll("i").forEach((i) => { i.style.width = i.style.height = "14px"; });
}

function fileRow(entry) {
  const path = entry.path;
  const kind = entry.is_dir ? null : kindOf(entry.name);
  const listLayout = state.layout === "list";
  const row = el("div", listLayout ? "row" : "cell");

  const thumb = el("div", entry.is_dir ? "thumb folder" : "thumb");
  if (kind) {
    const img = el("img");
    img.loading = "lazy";
    img.src = thumbUrl(path, entry.v, "s", entry.space || state.space);
    img.onerror = () => { thumb.innerHTML = ""; thumb.append(iconEl(KIND_ICONS[kind])); };
    thumb.append(img);
  } else {
    thumb.append(iconEl(entry.volume ? "disk" : entry.is_dir ? "folder" : KIND_ICONS[entry.kind] || "file"));
  }

  const actions = el("div", "row-actions");
  const more = el("button", "icon-btn");
  more.title = t("more");
  more.append(iconEl("more"));
  more.onclick = (e) => { e.stopPropagation(); openMenu(entry, more.getBoundingClientRect()); };
  // The extra disk's folder can't be renamed, moved or deleted.
  if (!entry.volume) actions.append(more);
  row.oncontextmenu = (e) => {
    if (entry.volume) return;
    e.preventDefault();
    openMenu(entry, { left: e.clientX, right: e.clientX, top: e.clientY, bottom: e.clientY });
  };
  onLongPress(row, (x, y) => openMenu(entry, { left: x, right: x, top: y, bottom: y }));

  const name = el("div", "name");
  const title = el("div", "", entry.name);
  if (entry.fav) title.prepend(Object.assign(iconEl("heartFill"), { className: "fav-mark" }));
  name.append(title);
  entry.nameEl = name;
  if (state.kind !== "all") {
    // Catalogue view: say which folder the file is in.
    const folder = path.includes("/") ? path.slice(0, path.lastIndexOf("/")) : t(state.space === "personal" ? "files" : "sharedFiles");
    name.append(el("div", "where", folder));
  } else if (!listLayout) {
    name.append(el("div", "where", entry.is_dir ? t("folder") : formatSize(entry.size)));
  }
  if (listLayout) {
    row.append(
      thumb,
      name,
      el("div", "meta", entry.modified ? shortFmt.format(entry.modified * 1000) : "—"),
      el("div", "meta", entry.is_dir ? "—" : formatSize(entry.size)),
      actions,
    );
  } else {
    row.append(thumb, name, actions);
  }

  if (entry.open) {
    row.onclick = () => go(entry.open, "files");
    return row;
  }
  // Drag a row onto a folder (or a breadcrumb) to move it. The disk's own files stay put.
  row.draggable = !isDisk(state.space);
  row.ondragstart = (e) => {
    e.dataTransfer.setData(DRAG_TYPE, JSON.stringify({ space: state.space, path }));
    e.dataTransfer.effectAllowed = "move";
  };
  if (entry.is_dir && !isDisk(state.space)) dropTarget(row, path);
  row.onclick = () => {
    if (entry.is_dir) return go(state.space, "files", path);
    if (kind) return openViewer(state.items.findIndex((i) => i.path === path));
    window.open(fileUrl(path, true, entry.space || state.space), "_blank");
  };
  return row;
}

// Deleting is safe: items go to Recently deleted, and the snack bar offers Undo.
async function removeItem(path) {
  const { id } = await api(`api/files?${qs({ space: state.space, path })}`, { method: "DELETE" });
  loadStatus();
  snack(t("movedToTrash", { name: path.split("/").pop() }), t("undo"), async () => {
    await post("api/trash/restore", { id });
    if ($("viewer").hidden) render();
    loadStatus();
  });
}

let snackTimer;
function snack(text, actionLabel, action) {
  clearTimeout(snackTimer);
  $("snack-text").textContent = text;
  const button = $("snack-action");
  button.hidden = !action;
  button.textContent = actionLabel || "";
  button.onclick = async () => {
    $("snack").hidden = true;
    try { await action(); } catch (err) { alert(err.message); }
  };
  $("snack").hidden = false;
  snackTimer = setTimeout(() => { $("snack").hidden = true; }, 6000);
}

// Touch screens have no right click: a long press opens the same menu.
function onLongPress(node, callback) {
  let timer = null;
  let fired = false;
  node.addEventListener("touchstart", (e) => {
    fired = false;
    const { clientX, clientY } = e.touches[0];
    timer = setTimeout(() => { fired = true; callback(clientX, clientY); }, 550);
  }, { passive: true });
  const cancel = () => clearTimeout(timer);
  node.addEventListener("touchmove", cancel, { passive: true });
  node.addEventListener("touchend", (e) => {
    cancel();
    if (fired) e.preventDefault();  // no click after a long press
  });
}

// --- Welcome page (iCloud-style) ------------------------------------------------

const APP_COLORS = {
  photos: "linear-gradient(135deg, #ffb340, #ff375f 50%, #af52de)",
  files: "linear-gradient(135deg, #64d2ff, #0a84ff)",
  family: "linear-gradient(135deg, #30d158, #30b0c7)",
  favorite: "linear-gradient(135deg, #ff6482, #ff2d55)",
  trash: "linear-gradient(135deg, #aeaeb2, #636366)",
  backup: "linear-gradient(135deg, #5e5ce6, #0a84ff)",
  devices: "linear-gradient(135deg, #64d2ff, #30d158)",
  collections: "linear-gradient(135deg, #ffd60a, #ff9f0a)",
};

async function renderHome() {
  const seq = renderSeq;
  let data, status;
  try {
    [data, status, state.backup, state.devices, state.collections] = await Promise.all(
      [api("api/home"), api("api/status"), api("api/backup"), api("api/devices"), api("api/collections")]);
  } catch (err) {
    return stale(seq) || showEmpty(t("homeLoadError"), err.message);
  }
  if (stale(seq)) return;  // the user moved on while loading
  $("home").replaceChildren(
    profileCard(status.usage),
    photosCard(data.photos),
    filesCard(data.recent),
    familyCard(data.family),
    backupCard(state.backup),
    trashCard(data.trash),
    collectionsCard(state.collections.collections),
    devicesCard(state.devices),
    favoritesCard(data.favorites),
  );
}

// --- Phones: background uploads with an iOS Shortcut ---------------------------

function devicesCard(info) {
  const node = card("devices-card", "phone", APP_COLORS.devices, t("devicesTitle"),
    info.devices.length ? t("deviceCount", { n: info.devices.length }) : t("devicesSub"));
  const body = el("div", "card-body");
  if (info.devices.length) {
    const list = el("div", "device-list");
    for (const device of info.devices) {
      const row = el("div", "device-row");
      const text = el("div", "home-text");
      text.append(el("div", "home-name", device.name),
        el("div", "card-sub", device.last_used ? t("lastUsed", { when: when(device.last_used) }) : t("neverUsed")));
      const revoke = el("button", "icon-btn danger-icon");
      revoke.title = t("revoke");
      revoke.append(iconEl("close"));
      revoke.onclick = async () => {
        if (!confirm(t("confirmRevoke", { name: device.name }))) return;
        await api(`api/devices?${qs({ id: device.id })}`, { method: "DELETE" });
        render();
      };
      row.append(iconEl("phone"), text, revoke);
      list.append(row);
    }
    body.append(list);
  } else {
    body.append(el("p", "card-sub wrap", t("devicesHow")));
  }
  const add = el("button", "btn primary", t("connectPhone"));
  add.onclick = pairPhone;
  const shortcut = el("button", "btn link subtle", t("shortcutAdvanced"));
  shortcut.onclick = connectPhone;
  body.append(add, shortcut);
  node.append(body);
  return node;
}

// Pair the mobile app: a one-time QR code (10 minutes). The key it is exchanged
// for goes straight to the phone and never appears here.
let pairTimer;

async function pairPhone() {
  const dialog = $("device-dialog");
  let pairing;
  try {
    pairing = await post("api/devices/pairing", {});
  } catch (err) {
    return alert(err.message);
  }
  clearInterval(pairTimer);
  const qr = el("div", "qr");
  qr.innerHTML = pairing.qr_svg;  // SVG made by the server from the code
  const status = el("p", "pair-status");
  const close = el("button", "btn", t("cancel"));
  close.onclick = () => dialog.close();
  const steps = el("ol", "steps");
  steps.append(el("li", "", t("pairStep1")), el("li", "", t("pairStep2")));
  dialog.replaceChildren(el("h2", "", t("pairTitle")), qr, steps, status, close);
  dialog.onclose = () => { clearInterval(pairTimer); render(); };
  if (!dialog.open) dialog.showModal();

  const tick = async () => {
    const left = pairing.expires - Math.floor(Date.now() / 1000);
    if (left <= 0) {
      clearInterval(pairTimer);
      qr.classList.add("expired");
      const again = el("button", "btn primary", t("newCode"));
      again.onclick = pairPhone;
      status.replaceChildren(el("span", "", t("pairExpired") + " "), again);
      return;
    }
    status.textContent = t("pairValid", { time: `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}` });
    try {
      const { paired } = await api(`api/devices/paired?${qs({ since: pairing.started })}`);
      if (paired) {
        clearInterval(pairTimer);
        qr.classList.add("done");
        status.textContent = t("pairDone");
        close.textContent = t("done");
      }
    } catch { /* keep waiting */ }
  };
  tick();
  pairTimer = setInterval(tick, 2000);
}

async function connectPhone() {
  const name = prompt(t("deviceNamePrompt"), "iPhone");
  if (!name) return;
  let info;
  try {
    info = await post("api/devices", { name });
  } catch (err) {
    return alert(err.message);
  }
  const dialog = $("device-dialog");
  const field = (label, value) => {
    const wrap = el("div", "copy-field");
    const input = el("input");
    input.readOnly = true;
    input.value = value;
    input.onclick = () => input.select();
    const copy = el("button", "icon-btn");
    copy.title = t("copy");
    copy.append(iconEl("copy"));
    copy.onclick = async () => {
      input.select();
      try { await navigator.clipboard.writeText(value); copy.classList.add("done"); }
      catch { document.execCommand("copy"); }
    };
    wrap.append(input, copy);
    const box = el("label", "copy-label");
    box.append(el("span", "", label), wrap);
    return box;
  };
  const url = `${info.public_url || info.lan_url}/api/device/upload`;
  const steps = el("ol", "steps");
  for (const key of ["step1", "step2", "step3", "step4", "step5"]) steps.append(el("li", "", t(key)));
  const done = el("button", "btn primary", t("done"));
  done.onclick = () => { dialog.close(); render(); };
  dialog.replaceChildren(
    el("h2", "", t("connectTitle", { name })),
    el("p", "card-sub wrap", t("keyOnce")),
    field(t("fieldUrl"), url),
    field(t("fieldHeader"), `Bearer ${info.key}`),
    steps,
    el("p", "card-sub wrap", info.public_url ? t("homeUrlTip", { url: `${info.lan_url}/api/device/upload` }) : t("noPublicUrl")),
    done,
  );
  dialog.showModal();
}

// The user's Home Assistant picture, or their initial when they have none.
function avatarEl(className, name) {
  const node = el("div", className, (name || "?").charAt(0).toUpperCase());
  const img = new Image();
  img.alt = "";
  img.onload = () => node.replaceChildren(img);
  img.src = "api/avatar";
  return node;
}

const timeOnly = new Intl.DateTimeFormat(LOCALE, { hour: "2-digit", minute: "2-digit" });

function when(seconds) {
  const date = new Date(seconds * 1000);
  const days = Math.round((new Date(date).setHours(0, 0, 0, 0) - new Date().setHours(0, 0, 0, 0)) / 86400000);
  const day = days === 0 ? t("today") : days === -1 ? t("yesterday") : days === 1 ? t("tomorrow") : shortFmt.format(date);
  return t("dayAtTime", { day, time: timeOnly.format(date) });
}

let backupPoll;

function backupCard(info) {
  const admin = state.user && state.user.is_admin;
  const ready = info.state === "mounted";
  let subtitle;
  if (!ready) subtitle = t(info.state === "none" ? "backupLocked" : info.state === "same" ? "backupSame" : "backupMissing");
  else if (info.running) subtitle = t("backupRunning", { n: info.percent });
  else if (info.last && !info.last.ok) subtitle = t("backupFailed");
  else subtitle = info.last_ok ? t("backupLast", { when: when(info.last_ok) }) : t("backupNever");
  const node = card("backup-card" + (ready ? "" : " locked"), ready ? "backup" : "lock",
    ready ? APP_COLORS.backup : APP_COLORS.trash, t("backup"), subtitle);
  const body = el("div", "card-body");

  if (!ready) {
    body.append(el("p", "", t(info.state === "none" ? "backupHow" : "backupFix")));
    if (admin) {
      const link = el("a", "btn primary", t("openConfig"));
      link.href = `https://my.home-assistant.io/redirect/supervisor_addon/?addon=${encodeURIComponent(info.addon)}`;
      link.target = "_blank";
      link.rel = "noopener";
      body.append(link);
    } else {
      body.append(el("p", "card-sub", t("askAdmin")));
    }
    node.append(body);
    return node;
  }

  if (info.running) {
    const bar = el("div", "bar");
    const fill = el("div", "bar-fill");
    fill.style.width = `${info.percent}%`;
    bar.append(fill);
    body.append(bar);
  }
  const facts = el("ul", "facts");
  facts.append(
    el("li", "", t("backupNext", { when: when(info.next) })),
    el("li", "", t("backupDisk", { free: formatSize(info.usage.free), total: formatSize(info.usage.total) })),
    el("li", "", t("backupKeep", { n: info.keep_days })),
  );
  body.append(facts);
  if (info.last && !info.last.ok && info.last.message) body.append(el("p", "notice", info.last.message));
  if (info.same_disk) body.append(el("p", "notice", t("backupSameDisk")));
  if (admin) {
    const now = el("button", "btn primary", t(info.running ? "backupRunningShort" : "backupNow"));
    now.disabled = info.running;
    now.onclick = async () => {
      now.disabled = true;
      try { await post("api/backup/run", {}); } catch (err) { alert(err.message); }
      setTimeout(refreshBackup, 800);
    };
    body.append(now);
  }
  node.append(body);
  clearTimeout(backupPoll);
  if (info.running) backupPoll = setTimeout(refreshBackup, 3000);
  return node;
}

async function refreshBackup() {
  if (state.view !== "home") return;
  try {
    const info = await api("api/backup");
    const old = document.querySelector(".backup-card");
    if (old && state.view === "home") old.replaceWith(backupCard(info));
  } catch { /* try again on the next visit */ }
}

function card(className, iconName, color, title, subtitle, open) {
  const node = el("section", `card ${className}`);
  const head = el("header", "card-head");
  const appIcon = el("div", "app-icon");
  appIcon.style.background = color;
  appIcon.append(iconEl(iconName));
  const titles = el("div", "card-titles");
  titles.append(el("h2", "", title), el("div", "card-sub", subtitle));
  head.append(appIcon, titles);
  if (open) {
    head.classList.add("link");
    head.onclick = open;
  }
  node.append(head);
  return node;
}

function profileCard(usage) {
  const node = el("section", "card profile");
  const name = (state.user && state.user.display_name) || "";
  const cloud = el("div", "cloud");
  cloud.append(avatarEl("big-avatar", name));
  const info = el("div", "profile-info");
  info.append(el("h1", "", name), el("div", "profile-plan", "NAS Assistant"));
  if (usage) {
    const bar = el("div", "bar");
    const fill = el("div", "bar-fill");
    fill.style.width = `${(usage.used / usage.total) * 100}%`;
    bar.append(fill);
    info.append(bar, el("div", "card-sub", t("diskFree", { free: formatSize(usage.free), total: formatSize(usage.total) })));
  }
  node.append(cloud, info);
  return node;
}

// Open a photo or video in the gallery viewer, or any other file in a new tab.
function openFrom(space, entry) {
  if (entry.is_dir) {
    return go(space, "files", entry.path);
  }
  if (kindOf(entry.name)) {
    state.openPath = entry.path;
    return go(space, "photos");
  }
  window.open(fileUrl(entry.path, true, space), "_blank");
}

function photosCard(photos) {
  const subtitle = [t("library"), t("photoCount", { n: photos.images }),
    photos.videos ? t("videoCount", { n: photos.videos }) : ""].filter(Boolean).join(" · ");
  const node = card("photos-card", "photos", APP_COLORS.photos, t("photos"), subtitle, () => go("personal", "photos"));
  if (!photos.recent.length) {
    node.append(el("p", "card-empty", t("noPhotosText")));
    return node;
  }
  const grid = el("div", "mosaic");
  for (const item of photos.recent) {
    const cell = el("button", "mosaic-cell");
    const img = el("img");
    img.loading = "lazy";
    img.alt = item.name;
    fadeIn(img);
    img.src = thumbUrl(item.path, item.v, "s", "personal");
    cell.append(img);
    if (item.kind === "video") {
      const badge = el("span", "badge");
      badge.append(iconEl("play"));
      cell.append(badge);
    }
    cell.onclick = () => openFrom("personal", item);
    grid.append(cell);
  }
  node.append(grid);
  return node;
}

const typeLabel = (entry) => {
  if (entry.is_dir) return t("folder");
  const dot = entry.name.lastIndexOf(".");
  return dot > 0 ? entry.name.slice(dot + 1).toUpperCase() : t(`kind_${entry.kind || "other"}`);
};

function itemRow(space, entry, detail) {
  const row = el("button", "home-row");
  const thumb = el("div", "home-thumb");
  if (!entry.is_dir && kindOf(entry.name)) {
    const img = el("img");
    img.loading = "lazy";
    img.src = thumbUrl(entry.path, entry.v, "s", space);
    img.onerror = () => thumb.replaceChildren(iconEl(KIND_ICONS[entry.kind] || "file"));
    thumb.append(img);
  } else {
    thumb.append(iconEl(entry.is_dir ? "folder" : KIND_ICONS[entry.kind] || "file"));
  }
  const text = el("div", "home-text");
  text.append(el("div", "home-name", entry.name), el("div", "card-sub", detail || typeLabel(entry)));
  row.append(thumb, text);
  row.onclick = () => openFrom(space, entry);
  return row;
}

function listCard(className, iconName, color, title, subtitle, open, space, entries, detail) {
  const node = card(className, iconName, color, title, subtitle, open);
  if (!entries.length) {
    node.append(el("p", "card-empty", t("nothingYet")));
    return node;
  }
  const list = el("div", "home-list");
  for (const entry of entries) list.append(itemRow(space, entry, detail && detail(entry)));
  node.append(list);
  return node;
}

function filesCard(recent) {
  return listCard("files-card", "folder", APP_COLORS.files, t("files"), t("recent"),
    () => go("personal", "files"), "personal", recent);
}

function familyCard(recent) {
  return listCard("family-card", "family", APP_COLORS.family, t("family"), t("recentShared"),
    () => go("family", "photos"), "family", recent,
    (e) => `${shortFmt.format(e.modified * 1000)} · ${typeLabel(e)}`);
}

function favoritesCard(favs) {
  return listCard("fav-card", "heartFill", APP_COLORS.favorite, t("kind_favorite"), t("mySpace"),
    () => go("personal", "files", "", "favorite"), "personal", favs);
}

function trashCard(count) {
  const node = card("trash-card", "trash", APP_COLORS.trash, t("recentlyDeleted"),
    count ? t("itemCount", { n: count }) : t("trashEmptyTitle"), () => go("personal", "trash"));
  return node;
}

// --- Collections: albums and dossiers --------------------------------------------

async function renderCollections() {
  setHeader(t("collections"), t("collectionsSub"));
  const seq = renderSeq;
  let list;
  try {
    ({ collections: list } = await api("api/collections"));
  } catch (err) {
    return stale(seq) || showEmpty(t("collectionsLoadError"), err.message);
  }
  if (stale(seq)) return;
  const page = $("collections");
  const bar = el("div", "collection-bar");
  for (const kind of ["album", "dossier"]) {
    const b = el("button", "btn" + (kind === "album" ? " primary" : ""));
    b.append(iconEl(kind), el("span", "", t(kind === "album" ? "newAlbum" : "newDossier")));
    b.onclick = () => newCollection(kind);
    bar.append(b);
  }
  page.append(bar);
  if (!list.length) {
    page.append(el("p", "notice hint", t("collectionsHow")));
    return;
  }
  const grid = el("div", "collection-grid");
  for (const col of list) grid.append(collectionCard(col));
  page.append(grid);
}

function collectionCard(col) {
  const node = el("button", "collection-card");
  const cover = el("div", "collection-cover" + (col.covers.length ? "" : " empty"));
  if (col.covers.length) {
    for (const c of col.covers.slice(0, col.covers.length >= 4 ? 4 : 1)) {
      const img = el("img");
      img.loading = "lazy";
      fadeIn(img);
      img.src = thumbUrl(c.path, c.v, "s", c.space);
      cover.append(img);
    }
    cover.classList.toggle("quad", col.covers.length >= 4);
  } else {
    cover.append(iconEl(col.kind));
  }
  const meta = [t("itemCount", { n: col.count }), col.shared ? t("sharedBadge") : ""].filter(Boolean).join(" · ");
  node.append(cover, el("div", "collection-name", col.name), el("div", "card-sub", meta));
  node.onclick = () => openCollection(col.id);
  return node;
}

function openCollection(id) {
  state.collection = id;
  go("personal", "collection");
}

async function renderCollection() {
  const seq = renderSeq;
  let col;
  try {
    col = await api(`api/collections/items?${qs({ id: state.collection })}`);
  } catch (err) {
    return stale(seq) || showEmpty(t("collectionsLoadError"), err.message);
  }
  if (stale(seq)) return;
  setHeader(col.name, [t(col.kind === "album" ? "albumKind" : "dossierKind"), t("itemCount", { n: col.items.length }),
    col.shared ? t("sharedBadge") : ""].filter(Boolean).join(" · "));
  const crumbs = $("crumbs");
  const back = el("a", "", t("collections"));
  back.onclick = () => go("personal", "collections");
  const rename = el("a", "", t("rename"));
  rename.onclick = async () => {
    const name = prompt(t("collectionName"), col.name);
    if (!name || name === col.name) return;
    try { await post("api/collections/rename", { id: col.id, name }); } catch (err) { alert(err.message); }
    render();
  };
  crumbs.append(back, iconEl("right"), el("a", "", col.name), el("span", "crumb-gap"), rename);
  if (col.mine || (state.user && state.user.is_admin)) {
    const del = el("a", "danger-link", t("deleteCollection"));
    del.onclick = async () => {
      if (!confirm(t("confirmDeleteCollection", { name: col.name }))) return;
      await api(`api/collections?${qs({ id: col.id })}`, { method: "DELETE" });
      go("personal", "collections");
    };
    crumbs.append(del);
  }
  crumbs.querySelectorAll("i").forEach((i) => { i.style.width = i.style.height = "14px"; });
  state.items = col.items.filter((i) => kindOf(i.name))
    .map((i) => ({ ...i, taken: i.modified }));
  $("tv-btn").hidden = !state.items.length;
  if (!col.items.length) return showEmpty(t("collectionEmptyTitle"), t(col.kind === "album" ? "albumEmptyText" : "dossierEmptyText"));
  if (col.kind === "album") {
    const tiles = el("div", "tiles");
    col.items.forEach((item) => {
      const index = state.items.findIndex((i) => i.space === item.space && i.path === item.path);
      if (index >= 0) tiles.append(tile(state.items[index], index));
    });
    const others = col.items.filter((i) => !kindOf(i.name));
    $("gallery").append(tiles);
    if (others.length) {
      $("files").className = "file-list layout-list";
      for (const entry of others) $("files").append(fileRow(entry));
    }
  } else {
    $("files").className = `file-list layout-${state.layout}`;
    for (const entry of col.items) $("files").append(fileRow(entry));
  }
}

async function removeFromCollection(entry) {
  await api(`api/collections/items?${qs({ id: state.collection, space: entry.space, path: entry.path })}`,
    { method: "DELETE" });
}

// New collection: a name, and whether the whole family sees it.
function collectionForm(kind, onDone) {
  const dialog = $("collection-dialog");
  const name = el("input");
  name.placeholder = t("collectionName");
  const shared = el("input");
  shared.type = "checkbox";
  const label = el("label", "check-row");
  label.append(shared, el("span", "", t("shareWithFamily")));
  const ok = el("button", "btn primary", t("create"));
  const cancel = el("button", "btn", t("cancel"));
  cancel.onclick = () => dialog.close();
  ok.onclick = async () => {
    if (!name.value.trim()) return name.focus();
    try {
      const { id } = await post("api/collections", { name: name.value, kind, shared: shared.checked ? "1" : "0" });
      dialog.close();
      onDone(id, name.value.trim());
    } catch (err) {
      alert(err.message);
    }
  };
  const actions = el("div", "dialog-actions");
  actions.append(cancel, ok);
  dialog.replaceChildren(el("h2", "", t(kind === "album" ? "newAlbum" : "newDossier")), name, label,
    el("p", "card-sub wrap", t("shareHint")), actions);
  dialog.showModal();
  name.focus();
}

function newCollection(kind) {
  collectionForm(kind, (id) => openCollection(id));
}

// "Add to collection…": pick one, or make a new one on the spot.
async function addToCollection(entry) {
  const space = entry.space || state.space;
  let list;
  try {
    ({ collections: list } = await api("api/collections"));
  } catch (err) {
    return alert(err.message);
  }
  // Private files can't go into a shared collection.
  const fits = list.filter((c) => space === "family" || !c.shared);
  const dialog = $("collection-dialog");
  const picks = el("div", "pick-list");
  const add = async (id) => {
    try {
      await post("api/collections/items", { id, space, path: entry.path });
      dialog.close();
      snack(t("addedToCollection", { name: (list.find((c) => c.id === id) || { name: "" }).name }));
    } catch (err) {
      alert(err.message);
    }
  };
  if (!fits.length) picks.append(el("p", "muted", t("noCollections")));
  for (const col of fits) {
    const b = el("button", "pick");
    b.append(iconEl(col.kind), el("span", "", col.name), el("span", "card-sub", col.shared ? t("sharedBadge") : ""));
    b.onclick = () => add(col.id);
    picks.append(b);
  }
  const create = el("button", "btn", t("newCollection"));
  create.onclick = () => collectionForm(kindOf(entry.name) ? "album" : "dossier", (id, name) => {
    list.push({ id, name });
    add(id);
  });
  const cancel = el("button", "btn", t("cancel"));
  cancel.onclick = () => dialog.close();
  const actions = el("div", "dialog-actions");
  actions.append(create, cancel);
  dialog.replaceChildren(el("h2", "", t("addToCollectionTitle", { name: entry.name })), picks, actions);
  dialog.showModal();
}

function collectionsCard(list) {
  const node = card("collections-card", "album", APP_COLORS.collections, t("collections"),
    list.length ? t("collectionCount", { n: list.length }) : t("collectionsSub"), () => go("personal", "collections"));
  const grid = el("div", "collection-grid mini");
  for (const col of list.slice(0, 4)) grid.append(collectionCard(col));
  if (!list.length) node.append(el("p", "card-empty", t("collectionsHow")));
  else node.append(grid);
  return node;
}

// --- Disks (administrators) -----------------------------------------------------

const ROLE_LABELS = { nas: "roleNas", backup: "roleBackup", storage: "roleStorage", system: "roleSystem", free: "roleFree" };

async function renderDisks() {
  setHeader(t("disksTitle"), t("disksSub"));
  const seq = renderSeq;
  let info;
  try {
    info = await api("api/disks/overview");
  } catch (err) {
    return stale(seq) || showEmpty(t("disksLoadError"), err.message);
  }
  if (stale(seq)) return;
  const page = $("disks");
  const taken = (role) => info.disks.some((d) => d.partitions.some((p) => p.role === role));
  for (const disk of info.disks) page.append(diskCard(disk, info, { backup: taken("backup"), storage: taken("storage") }));
  for (const disk of info.away || []) page.append(awayCard(disk));
  page.append(el("p", "notice hint", t("diskNotListed")));
}

// A disk that had a role and is unplugged: it stays listed, and comes back by itself.
function awayCard(disk) {
  const node = el("section", "card disk-card-big away");
  const head = el("header", "card-head");
  const appIcon = el("div", "app-icon");
  appIcon.style.background = APP_COLORS.trash;
  appIcon.append(iconEl("disk"));
  const titles = el("div", "card-titles");
  titles.append(el("h2", "", disk.name), el("div", "card-sub", t("notConnected")));
  head.append(appIcon, titles);
  const body = el("div", "card-body");
  const row = el("div", "part");
  const top = el("div", "part-top");
  top.append(el("span", `role role-${disk.role}`, t(ROLE_LABELS[disk.role])));
  row.append(top, el("div", "card-sub", t("awayText")));
  body.append(row);
  node.append(head, body);
  return node;
}

const setRole = (id, role) => post("api/disks/role", { id, role });

function diskCard(disk, info, taken) {
  const node = el("section", "card disk-card-big" + (disk.system ? " system" : ""));
  const head = el("header", "card-head");
  const appIcon = el("div", "app-icon");
  appIcon.style.background = disk.system ? APP_COLORS.trash : APP_COLORS.files;
  appIcon.append(iconEl("disk"));
  const titles = el("div", "card-titles");
  titles.append(el("h2", "", disk.model),
    el("div", "card-sub", [formatSize(disk.size), disk.transport, disk.path].filter(Boolean).join(" · ")));
  head.append(appIcon, titles);
  // A USB 2 link works, just slower: say so gently, once.
  if (disk.usb_speed && disk.usb_speed <= 480) titles.append(el("div", "card-sub", t("slowUsb")));
  // Eject sits next to the disk's name, so it is clear which disk gets unplugged.
  const used = disk.partitions.find((p) => ["nas", "backup", "storage"].includes(p.role) && p.state === "mounted");
  if (used) {
    const eject = el("button", "btn eject-btn");
    eject.append(iconEl("eject"), el("span", "", t("eject")));
    eject.onclick = () => ejectDisk(disk, used.role);
    head.append(eject);
  }
  node.append(head);

  const body = el("div", "card-body");
  for (const part of disk.partitions) {
    const row = el("div", "part");
    const top = el("div", "part-top");
    top.append(el("span", `role role-${part.role}`, t(ROLE_LABELS[part.role])),
      el("span", "part-name", [part.label || part.path.split("/").pop(),
        FS_NAMES[part.fstype] || part.fstype || t("fsUnknown"), formatSize(part.size)].join(" · ")));
    row.append(top);
    if (part.usage) {
      const bar = el("div", "bar");
      const fill = el("div", "bar-fill");
      fill.style.width = `${(part.usage.used / part.usage.total) * 100}%`;
      bar.append(fill);
      row.append(bar, el("div", "card-sub", t("diskFree", { free: formatSize(part.usage.free), total: formatSize(part.usage.total) })));
      if (part.files != null) row.append(el("div", "card-sub", t("nasFiles", { n: part.files })));
    }
    const actions = el("div", "part-actions");
    if (part.role === "nas") {
      row.append(el("div", "card-sub", t("nasProtected")));
    } else if (part.role === "backup" || part.role === "storage") {
      row.append(el("div", "card-sub", t(part.role === "backup" ? "backupRoleText" : "storageRoleText", { name: info.storage_name })));
      if (part.state === "uninitialized") {
        row.append(el("p", "notice", t("needsInit", { fs: FS_NAMES[part.fstype] || part.fstype || t("fsNone") })));
        const init = el("button", "btn danger", t("initialize"));
        init.onclick = () => askInitialize(disk, part);
        actions.append(init);
      }
      // Change your mind later: switch role, or stop using the disk. Nothing is erased.
      const other = part.role === "backup" ? "storage" : "backup";
      if (!taken[other]) {
        const swap = el("button", "btn", t(other === "backup" ? "switchToBackup" : "switchToStorage"));
        swap.onclick = () => diskAction(t("confirmSwitch"), () => setRole(part.id, other));
        actions.append(swap);
      }
      const stop = el("button", "btn", t("stopUsing"));
      stop.onclick = () => diskAction(t(part.role === "backup" ? "confirmStopBackup" : "confirmStopStorage"),
        () => setRole(part.id, "none"));
      actions.append(stop);
    } else if (part.same_disk_as_nas) {
      row.append(el("div", "card-sub", t("sameDiskAsNas")));
    } else if (part.id && part.was && !taken[part.was]) {
      // Ejected earlier: one tap puts it back where it was.
      row.append(el("div", "card-sub", t("wasRole", { role: t(ROLE_LABELS[part.was]) })));
      const back = el("button", "btn primary", t("reattach", { role: t(ROLE_LABELS[part.was]) }));
      back.onclick = () => diskAction(t("confirmSwitch"), () => setRole(part.id, part.was));
      actions.append(back);
    } else if (part.id) {
      if (!taken.backup) {
        const use = el("button", "btn primary", t("useForBackup"));
        use.onclick = () => diskAction(t("confirmUseBackup", { name: disk.model }), () => setRole(part.id, "backup"));
        actions.append(use);
      }
      if (!taken.storage) {
        const more = el("button", "btn" + (taken.backup ? " primary" : ""), t("useForStorage"));
        more.onclick = () => diskAction(t("confirmUseStorage", { name: disk.model }), () => setRole(part.id, "storage"));
        actions.append(more);
      }
      if (!taken.backup && !taken.storage) row.append(el("div", "card-sub", t("chooseRole")));
    }
    if (actions.children.length) row.append(actions);
    body.append(row);
  }
  node.append(body);
  return node;
}

async function ejectDisk(disk, role) {
  if (!confirm(t(role === "nas" ? "confirmEjectNas" : "confirmEject", { name: disk.model }))) return;
  // The NAS disk holds everything: ask twice.
  if (role === "nas" && !confirm(t("confirmEjectNas2"))) return;
  try {
    await post("api/disks/eject", { role });
  } catch (err) {
    return alert(err.message);
  }
  snack(t("ejected", { name: disk.model }));
  if (role === "nas") return loadStatus();
  render();
}

// Changing disks restarts the add-on: wait for it to come back, then reload the page.
async function diskAction(question, action) {
  if (!confirm(question)) return;
  try {
    await action();
  } catch (err) {
    return alert(err.message);
  }
  showEmpty(t("restarting"), t("restartingText"));
  $("disks").hidden = true;
  await sleep(6000);
  for (let i = 0; i < 60; i++) {
    try { await api("api/status"); return location.reload(); } catch { await sleep(2000); }
  }
}

function askInitialize(disk, part) {
  const dialog = $("format-dialog");
  const name = el("span", "", part.size ? `${disk.model} (${formatSize(part.size)})` : disk.model).innerHTML;
  $("format-text").innerHTML = t("initText", { name });
  $("format-word").innerHTML = t("formatConfirm", { word: t("formatWord") });
  $("format-confirm").value = "";
  dialog.onclose = () => {
    const typed = $("format-confirm").value.trim().toUpperCase();
    if (dialog.returnValue !== "ok") return;
    if (typed !== t("formatWord")) return alert(tError("Formatting not confirmed"));
    diskAction(t("confirmInitialize"), () => post("api/disks/initialize", { role: part.role, confirm: "FORMAT" }));
  };
  dialog.showModal();
}

// --- Home Assistant sidebar and our own collapsible sidebar ---------------------

// Inside Home Assistant (Ingress) ask it to hide its own sidebar and header, like
// Music Assistant does; the Home Assistant button brings its menu back.
if (window.parent !== window) {
  window.parent.postMessage({ type: "home-assistant/subscribe-properties", kioskMode: true }, "*");
  for (const id of ["ha-menu", "ha-menu-fab"]) {
    $(id).hidden = false;
    $(id).onclick = () => window.parent.postMessage({ type: "home-assistant/toggle-menu" }, "*");
  }
}

function setCollapsed(collapsed) {
  document.body.classList.toggle("nav-collapsed", collapsed);
  try { localStorage.setItem("nas-sidebar", collapsed ? "collapsed" : "open"); } catch { /* not remembered */ }
}
try { setCollapsed(localStorage.getItem("nas-sidebar") === "collapsed"); } catch { /* default: open */ }
$("collapse").onclick = () => setCollapsed(!document.body.classList.contains("nav-collapsed"));

// --- Recently deleted ---------------------------------------------------------

async function renderTrash() {
  setHeader(t("recentlyDeleted"), "");
  const seq = renderSeq;
  let items, days;
  try {
    ({ items, days } = await api("api/trash"));
  } catch (err) {
    return stale(seq) || showEmpty(t("trashLoadError"), err.message);
  }
  if (stale(seq)) return;
  $("subtitle").textContent = days ? t("trashNote", { n: days }) : t("trashNoteForever");
  $("empty-trash").hidden = !items.length;
  $("empty-trash").onclick = async () => {
    if (!confirm(t("confirmEmptyTrash", { n: items.length }))) return;
    await api("api/trash?all=1", { method: "DELETE" });
    render();
    loadStatus();
  };
  if (!items.length) return showEmpty(t("trashEmptyTitle"), t("trashEmptyText"));
  const list = $("files");
  for (const item of items) list.append(trashRow(item));
}

function trashRow(item) {
  const row = el("div", "row trash-row");
  const thumb = el("div", item.is_dir ? "thumb folder" : "thumb");
  const fallback = iconEl(item.is_dir ? "folder" : KIND_ICONS[item.kind] || "file");
  if (item.kind === "image" || item.kind === "video") {
    const img = el("img");
    img.loading = "lazy";
    img.src = `api/trash/thumb?${qs({ id: item.id, v: item.v })}`;
    img.onerror = () => thumb.replaceChildren(fallback);
    thumb.append(img);
  } else {
    thumb.append(fallback);
  }

  const folder = item.path.includes("/") ? item.path.slice(0, item.path.lastIndexOf("/")) : "";
  const origin = [t(item.space === "family" ? "sharedFiles" : "files"), ...(folder ? folder.split("/") : [])].join(" › ");
  const name = el("div", "name");
  name.append(el("div", "", item.name), el("div", "where", t("deletedFrom", { place: origin })));

  const left = item.expires ? Math.max(1, Math.ceil((item.expires * 1000 - Date.now()) / 86400000)) : null;
  const actions = el("div", "row-actions");
  const back = el("button", "btn small");
  back.append(iconEl("restore"), el("span", "", t("restore")));
  back.onclick = async (e) => {
    e.stopPropagation();
    try {
      const where = await post("api/trash/restore", { id: item.id });
      snack(t("restored", { name: item.name }), t("show"), async () => {
        const parent = where.path.includes("/") ? where.path.slice(0, where.path.lastIndexOf("/")) : "";
        go(where.space, "files", parent);
      });
    } catch (err) {
      alert(err.message);
    }
    render();
    loadStatus();
  };
  const del = el("button", "icon-btn danger-icon");
  del.title = t("deleteForever");
  del.append(iconEl("trash"));
  del.onclick = async (e) => {
    e.stopPropagation();
    if (!confirm(t("confirmDeleteForever", { name: item.name }))) return;
    await api(`api/trash?${qs({ id: item.id })}`, { method: "DELETE" });
    render();
    loadStatus();
  };
  actions.append(back, del);

  row.append(
    thumb,
    name,
    el("div", "meta", shortFmt.format(item.deleted * 1000)),
    el("div", "meta", left ? t("daysLeft", { n: left }) : item.is_dir ? "—" : formatSize(item.size)),
    actions,
  );
  return row;
}

const post = (url, fields) => {
  const form = new FormData();
  for (const [key, value] of Object.entries(fields)) form.append(key, value);
  return api(url, { method: "POST", body: form });
};

// --- Rename, move, context menu ----------------------------------------------

const DRAG_TYPE = "application/x-nas-item";

function dropTarget(node, folder) {
  const ours = (e) => e.dataTransfer.types.includes(DRAG_TYPE);
  node.addEventListener("dragover", (e) => {
    if (!ours(e)) return;
    e.preventDefault();
    e.stopPropagation();
    node.classList.add("drop");
  });
  node.addEventListener("dragleave", () => node.classList.remove("drop"));
  node.addEventListener("drop", (e) => {
    if (!ours(e)) return;
    e.preventDefault();
    e.stopPropagation();
    node.classList.remove("drop");
    const item = JSON.parse(e.dataTransfer.getData(DRAG_TYPE));
    if (item.path === folder) return;
    moveItem(item.space, item.path, state.space, folder);
  });
}

async function moveItem(space, path, toSpace, toPath) {
  try {
    await post("api/move", { space, path, to_space: toSpace, to_path: toPath });
  } catch (err) {
    alert(err.message);
  }
  render();
}

function renameItem(entry) {
  inlineRename(entry.nameEl, entry, async (name) => {
    await post("api/rename", { space: state.space, path: entry.path, name });
    render();
  });
}

const extOf = (name) => {
  const dot = name.lastIndexOf(".");
  return dot > 0 ? name.slice(dot) : "";
};

// Rename in place, like the Finder: the name turns into a text field with the
// name selected (not the extension). Enter or clicking away saves, Esc cancels.
function inlineRename(host, entry, save) {
  const before = [...host.childNodes];
  const input = el("input", "rename-input");
  const error = el("div", "rename-error");
  input.value = entry.name;
  input.spellcheck = false;
  input.autocapitalize = "off";
  host.replaceChildren(input, error);
  for (const type of ["click", "dblclick", "mousedown", "touchstart", "contextmenu"]) {
    input.addEventListener(type, (e) => e.stopPropagation());
  }
  const row = host.closest(".row, .cell");
  if (row) { row.draggable = false; row.classList.add("editing"); }
  input.focus();
  const ext = entry.is_dir ? "" : extOf(entry.name);
  input.setSelectionRange(0, entry.name.length - ext.length);

  let busy = false;
  let finished = false;
  let failedValue = null;
  const finish = () => {
    finished = true;
    if (row) { row.draggable = true; row.classList.remove("editing"); }
    host.replaceChildren(...before);
  };
  const fail = (message) => {
    busy = false;
    failedValue = input.value;
    error.textContent = message;
    input.classList.add("invalid");
    input.focus();
  };

  async function commit() {
    if (busy || finished) return;
    let name = input.value.trim();
    if (!name || name === entry.name) return finish();
    if (/[\/\\]/.test(name) || name.startsWith(".")) return fail(t("badName"));
    busy = true;
    const newExt = extOf(name);
    if (ext && newExt.toLowerCase() !== ext.toLowerCase()
        && !confirm(t("changeExt", { old: ext, ext: newExt || t("noExt") }))) {
      name = name.slice(0, name.length - newExt.length) + ext;  // keep the old extension
      input.value = name;
    }
    try {
      await save(name);
      finished = true;
    } catch (err) {
      fail(err.message);
    }
  }

  input.addEventListener("keydown", (e) => {
    e.stopPropagation();
    if (e.key === "Enter") { e.preventDefault(); commit(); }
    if (e.key === "Escape") { e.preventDefault(); finish(); }
  });
  input.addEventListener("input", () => { error.textContent = ""; input.classList.remove("invalid"); });
  // Clicking away saves; if that name was already refused, clicking away cancels.
  input.addEventListener("blur", () => (input.value === failedValue ? finish() : commit()));
}

function closeMenu() {
  $("menu").hidden = true;
}

function openMenu(entry, rect) {
  const menu = $("menu");
  menu.innerHTML = "";
  const item = (iconName, label, action, danger) => {
    const b = el("button", danger ? "danger" : "");
    b.append(iconEl(iconName), el("span", "", label));
    b.onclick = () => { closeMenu(); action(); };
    menu.append(b);
  };
  if (isDisk(state.space)) {
    // Other files on the disk: read only, they can be copied into a space.
    item("move", t("copyTo"), () => openCopyDialog(entry));
    if (!entry.is_dir) item("download", t("download"), () => { location.href = fileUrl(entry.path); });
    return placeMenu(menu, rect);
  }
  if (state.view === "collection") {
    // Inside a collection: the file stays where it is, only the grouping changes.
    const folder = entry.path.includes("/") ? entry.path.slice(0, entry.path.lastIndexOf("/")) : "";
    item("folder", t("showInFolder"), () => go(entry.space, "files", folder));
    item("download", t("download"), () => { location.href = fileUrl(entry.path, false, entry.space); });
    item("close", t("removeFromCollection"), async () => { await removeFromCollection(entry); render(); }, true);
    return placeMenu(menu, rect);
  }
  if (!entry.is_dir) item("album", t("addToCollection"), () => addToCollection(entry));
  item(entry.fav ? "heartFill" : "heart", t(entry.fav ? "unfavorite" : "favorite"), async () => {
    await toggleFavorite(entry);
    render();
  });
  item("rename", t("rename"), () => renameItem(entry));
  item("move", t("moveTo"), () => openMoveDialog(entry));
  if (!entry.is_dir) item("download", t("download"), () => { location.href = fileUrl(entry.path); });
  item("trash", t("moveToTrash"), async () => {
    await removeItem(entry.path);
    render();
  }, true);
  placeMenu(menu, rect);
}

function placeMenu(menu, rect) {
  menu.hidden = false;
  // Open below the button, or above it near the bottom of the screen.
  const { offsetWidth: w, offsetHeight: h } = menu;
  menu.style.left = `${Math.max(8, Math.min(rect.right - w, innerWidth - w - 8))}px`;
  menu.style.top = `${rect.bottom + h + 8 > innerHeight ? Math.max(8, rect.top - h - 4) : rect.bottom + 4}px`;
}

document.addEventListener("click", (e) => { if (!$("menu").contains(e.target)) closeMenu(); });
document.addEventListener("scroll", closeMenu, true);
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeMenu(); });

// Folder picker: browse My space and Family, then "Move here".
const picker = { space: "personal", path: "", entry: null, from: null };

function openMoveDialog(entry) {
  Object.assign(picker, { space: state.space, path: state.kind === "all" ? state.path : "", entry, from: state.space, copy: false });
  $("move-title").textContent = t("moveTitle", { name: entry.name });
  $("move-ok").textContent = t("moveHere");
  $("move-dialog").showModal();
  renderPicker();
}

async function renderPicker() {
  document.querySelectorAll("#move-spaces button").forEach((b) => b.classList.toggle("active", b.dataset.space === picker.space));
  const crumbs = $("move-crumbs");
  crumbs.innerHTML = "";
  const parts = picker.path ? picker.path.split("/") : [];
  [t(picker.space === "personal" ? "files" : "sharedFiles"), ...parts].forEach((label, i) => {
    if (i) crumbs.append(iconEl("right"));
    const a = el("a", "", label);
    a.onclick = () => { picker.path = parts.slice(0, i).join("/"); renderPicker(); };
    crumbs.append(a);
  });
  const list = $("move-list");
  list.replaceChildren(el("p", "muted", "…"));
  let entries = [];
  try {
    ({ entries } = await api(`api/files?${qs({ space: picker.space, path: picker.path })}`));
  } catch (err) {
    return list.replaceChildren(el("p", "muted", err.message));
  }
  // A folder can't go inside itself.
  const moving = picker.space === picker.from && picker.entry.is_dir ? picker.entry.path : null;
  const folders = entries.filter((e) => e.is_dir && join(picker.path, e.name) !== moving);
  list.innerHTML = "";
  if (!folders.length) list.append(el("p", "muted", t("noSubfolders")));
  for (const folder of folders) {
    const b = el("button", "pick");
    b.append(iconEl("folder"), el("span", "", folder.name), iconEl("right"));
    b.onclick = () => { picker.path = join(picker.path, folder.name); renderPicker(); };
    list.append(b);
  }
  const current = picker.entry.path.includes("/") ? picker.entry.path.slice(0, picker.entry.path.lastIndexOf("/")) : "";
  $("move-ok").disabled = picker.space === picker.from && picker.path === current;
}

document.querySelectorAll("#move-spaces button").forEach((b) => {
  b.onclick = () => { picker.space = b.dataset.space; picker.path = ""; renderPicker(); };
});
$("move-ok").onclick = () => {
  $("move-dialog").close();
  if (picker.copy) return startCopy(picker.from, picker.entry, picker.space, picker.path);
  moveItem(picker.from, picker.entry.path, picker.space, picker.path);
};

// "Copy to…" for the other files on the disk: pick a folder of My space or Family.
function openCopyDialog(entry) {
  Object.assign(picker, { space: "personal", path: "", entry, from: state.space, copy: true });
  $("move-title").textContent = t("copyTitle", { name: entry.name });
  $("move-ok").textContent = t("copyHere");
  $("move-dialog").showModal();
  renderPicker();
}

async function startCopy(from, entry, space, path) {
  try {
    await post("api/disk/copy", { space: from, path: entry.path, to_space: space, to_path: path });
  } catch (err) {
    return alert(err.message);
  }
  snack(t("copyStarted", { name: entry.name }));
  watchCopies();
}

// Copies run on the NAS: follow them, and say when each one is done.
let copyWatch = null;
const copiesSeen = new Set();
function watchCopies() {
  if (copyWatch) return;
  copyWatch = setInterval(async () => {
    let jobs = [];
    try { ({ jobs } = await api("api/disk/jobs")); } catch { return; }
    const running = jobs.filter((j) => j.state === "copying");
    for (const job of jobs.filter((j) => j.state !== "copying" && !copiesSeen.has(j.id))) {
      copiesSeen.add(job.id);
      if (job.state === "error") alert(t("copyFailed", { name: job.name, error: job.error }));
      else snack(t("copyDone", { name: job.name, where: t(job.space === "personal" ? "mySpace" : "family") }),
        t("open"), () => go(job.space, "files", job.path));
      loadStatus();
    }
    if (running.length) {
      const done = running.reduce((n, j) => n + j.done, 0);
      const total = running.reduce((n, j) => n + j.total, 0) || 1;
      snack(t("copying", { name: running[0].name, pct: Math.floor((done / total) * 100) }));
    } else {
      clearInterval(copyWatch);
      copyWatch = null;
    }
  }, 2000);
}
$("move-cancel").onclick = () => $("move-dialog").close();

// --- Viewer -------------------------------------------------------------------

function openViewer(index) {
  if (index < 0) return;
  state.viewerIndex = index;
  $("viewer").hidden = false;
  document.body.style.overflow = "hidden";
  showViewerItem();
}

let viewerChanged = false;  // favorites toggled in the viewer: refresh the list on close

function closeViewer() {
  if (viewerChanged) { viewerChanged = false; render(); }
  $("viewer").hidden = true;
  $("v-stage").innerHTML = "";
  document.body.style.overflow = "";
}

function showViewerItem() {
  const item = state.items[state.viewerIndex];
  if (!item) return closeViewer();
  const stage = $("v-stage");
  stage.innerHTML = "";
  if (item.kind === "video") {
    const video = el("video");
    video.src = fileUrl(item.path, true, item.space || state.space);
    video.controls = true;
    video.autoplay = true;
    video.playsInline = true;
    video.poster = thumbUrl(item.path, item.v, "l", item.space || state.space);
    stage.append(video);
  } else {
    const img = el("img");
    img.src = thumbUrl(item.path, item.v, "l", item.space || state.space);
    img.alt = item.name;
    stage.append(img);
    // Preload the neighbours so swiping feels instant.
    for (const n of [state.items[state.viewerIndex + 1], state.items[state.viewerIndex - 1]]) {
      if (n && n.kind === "image") new Image().src = thumbUrl(n.path, n.v, "l", n.space || state.space);
    }
  }
  const date = new Date(item.taken * 1000);
  $("v-date").textContent = `${dayFmt.format(date)} · ${timeFmt.format(date)}`;
  $("v-name").textContent = item.name;
  $("v-download").href = fileUrl(item.path, false, item.space || state.space);
  $("v-delete").title = t(state.view === "collection" ? "removeFromCollection" : "moveToTrash");
  for (const id of ["v-fav", "v-rename", "v-album", "v-delete"]) $(id).hidden = viewerReadOnly();
  paintFavButton(item);
  $("v-prev").hidden = state.viewerIndex === 0;
  $("v-next").hidden = state.viewerIndex === state.items.length - 1;
}

function step(delta) {
  const next = state.viewerIndex + delta;
  if (next < 0 || next >= state.items.length) return;
  state.viewerIndex = next;
  showViewerItem();
}

$("v-close").onclick = closeViewer;
$("v-prev").onclick = () => step(-1);
$("v-next").onclick = () => step(1);
const viewerReadOnly = () => isDisk((state.items[state.viewerIndex] || {}).space || state.space);

function paintFavButton(item) {
  const button = $("v-fav");
  button.replaceChildren(iconEl(item.fav ? "heartFill" : "heart"));
  button.title = t(item.fav ? "unfavorite" : "favorite");
  button.classList.toggle("on", !!item.fav);
}

$("v-fav").onclick = async () => {
  if (viewerReadOnly()) return;
  const item = state.items[state.viewerIndex];
  try {
    await toggleFavorite(item);
    viewerChanged = true;
    paintFavButton(item);
  } catch (err) {
    alert(err.message);
  }
};

$("v-rename").onclick = () => {
  if (viewerReadOnly()) return;
  const item = state.items[state.viewerIndex];
  inlineRename($("v-name"), { name: item.name, is_dir: false }, async (name) => {
    const { name: saved } = await post("api/rename", { space: item.space || state.space, path: item.path, name });
    const folder = item.path.includes("/") ? item.path.slice(0, item.path.lastIndexOf("/") + 1) : "";
    Object.assign(item, { name: saved, path: folder + saved });
    showViewerItem();
    render();
  });
};
$("v-name").onclick = () => $("v-rename").click();
$("v-album").onclick = () => addToCollection(state.items[state.viewerIndex]);
$("v-tv").onclick = () => {
  const item = state.items[state.viewerIndex];
  const video = $("v-stage").querySelector("video");
  if (video) video.pause();  // it plays on the TV now
  playOnTv([{ space: item.space || state.space, path: item.path }], item.name);
};
// "On the TV" at the top: a slideshow of what the page shows, in order.
$("tv-btn").onclick = () => playOnTv((state.items || []).map((i) => ({ space: i.space || state.space, path: i.path })),
  $("title").textContent);

// --- Watch on the TV ------------------------------------------------------------

function remembered(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}

async function chooseTv() {
  let info;
  try {
    info = await api("api/tv/players");
  } catch (err) {
    alert(err.message);
    return null;
  }
  const dialog = $("tv-dialog");
  const picks = el("div", "pick-list");
  return new Promise((resolve) => {
    let chosen = null;
    dialog.onclose = () => resolve(chosen);
    if (!info.players.length) picks.append(el("p", "muted", t("noTvs")));
    const last = remembered("nas-tv");
    const players = [...info.players].sort((a, b) => (b.id === last) - (a.id === last));
    for (const player of players) {
      const b = el("button", "pick");
      const name = el("span", "", player.name);
      if (player.detail) name.append(el("div", "card-sub", player.detail));
      b.append(iconEl("tv"), name, el("span", "card-sub", t(player.state === "off" ? "tvOff" : player.id === last ? "tvLast" : "tvReady")));
      b.onclick = () => {
        chosen = player;
        try { localStorage.setItem("nas-tv", player.id); } catch { /* not remembered */ }
        dialog.close();
      };
      picks.append(b);
    }
    const cancel = el("button", "btn", t("cancel"));
    cancel.onclick = () => dialog.close();
    const actions = el("div", "dialog-actions");
    actions.append(cancel);
    dialog.replaceChildren(el("h2", "", t("chooseTv")), el("p", "muted", t("chooseTvText")), picks, actions);
    dialog.showModal();
  });
}

let tvPlaying = null;
async function playOnTv(items, label) {
  if (!items.length) return;
  const player = await chooseTv();
  if (!player) return;
  try {
    await api("api/tv/play", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ entity_id: player.id, items }),
    });
  } catch (err) {
    return alert(err.message);
  }
  tvPlaying = player;
  $("tv-bar-text").textContent = t(items.length > 1 ? "tvSlideshow" : "tvPlaying", { name: label, tv: player.name });
  $("tv-bar").hidden = false;
}

$("tv-stop").onclick = async () => {
  $("tv-bar").hidden = true;
  if (tvPlaying) await post("api/tv/stop", { entity_id: tvPlaying.id }).catch(() => {});
  tvPlaying = null;
};
$("v-delete").onclick = async () => {
  if (viewerReadOnly()) return;
  const item = state.items[state.viewerIndex];
  // In an album the bin icon takes the photo out of the album; the file stays.
  if (state.view === "collection") {
    await removeFromCollection(item);
    state.items.splice(state.viewerIndex, 1);
    if (state.viewerIndex >= state.items.length) state.viewerIndex--;
    viewerChanged = true;
    return state.items.length ? showViewerItem() : closeViewer();
  }
  await removeItem(item.path);
  state.items.splice(state.viewerIndex, 1);
  if (state.viewerIndex >= state.items.length) state.viewerIndex--;
  state.items.length ? showViewerItem() : closeViewer();
  render();
};
document.addEventListener("keydown", (e) => {
  if ($("viewer").hidden) return;
  if (e.key === "Escape") closeViewer();
  if (e.key === "ArrowLeft") step(-1);
  if (e.key === ".") $("v-fav").click();  // same shortcut as Apple Photos
  if (e.key === "ArrowRight") step(1);
});
let touchX = null;
$("v-stage").addEventListener("touchstart", (e) => { touchX = e.touches[0].clientX; }, { passive: true });
$("v-stage").addEventListener("touchend", (e) => {
  if (touchX === null) return;
  const dx = e.changedTouches[0].clientX - touchX;
  if (Math.abs(dx) > 50) step(dx < 0 ? 1 : -1);
  touchX = null;
});

// --- Upload -------------------------------------------------------------------
//
// Uploads must survive a flaky Wi-Fi, a locked phone and a closed page:
// - files travel in pieces (1-16 MB, smaller while the network is bad); no request goes
//   over the 100 MB limit of tunnels such as Cloudflare;
// - a lost piece is sent again, for minutes if needed, from what really reached the disk;
// - before a file starts, the NAS says if it is already there (skipped), half sent
//   (resumed) or if another file has its name (the new one gets "name (2)");
// - the queue is remembered: after a reload, choosing the same files again goes on from
//   where it stopped.

const CHUNK_MIN = 1024 * 1024;
const CHUNK_MAX = 16 * 1024 * 1024;
const STALL_MS = 20 * 1000;
const GIVE_UP_MS = 10 * 60 * 1000;  // a file waits this long for the network before "not uploaded"
const QUEUE_KEY = "nas-upload-queue";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const uploads = { jobs: [], running: false, started: 0, wakeLock: null, status: "", open: true, base: "", pass: "" };

// Through Home Assistant's Ingress uploads crawl: send them straight to the add-on when it can
// be reached — its home address (60 MB/s at home; only from a page opened with http://, browsers
// block http calls from https pages), else its public address — with a pass that only uploads.
async function pickUploadRoute() {
  uploads.base = "";
  uploads.pass = "";
  let session;
  try { session = await api("api/upload/session", { method: "POST" }); } catch { return; }
  const routes = [];
  if (location.protocol === "http:" && session.lan) routes.push(session.lan);
  if (session.public && session.public !== location.origin) routes.push(session.public);
  for (const base of routes) {
    try {
      const res = await fetch(`${base}/api/upload/ping`, { signal: AbortSignal.timeout(2500) });
      if (res.ok) { uploads.base = base; uploads.pass = session.token; return; }
    } catch { /* not reachable from here: try the next */ }
  }
}

// The upload pass expired (12 hours) or the add-on restarted: go on through Ingress.
function passRefused(err) {
  if (err.status !== 401 || !uploads.pass) return false;
  uploads.base = uploads.pass = "";
  return true;
}

// After a few failures in a row on the direct route, go back to Ingress.
function directFailed() {
  if (!uploads.base) return;
  uploads.directFailures = (uploads.directFailures || 0) + 1;
  if (uploads.directFailures >= 3) { uploads.base = ""; uploads.pass = ""; }
}

const uploadHeaders = () => (uploads.pass ? { Authorization: `Bearer ${uploads.pass}` } : {});

function putChunk(url, blob, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    let last = Date.now();
    const watchdog = setInterval(() => {
      if (Date.now() - last > STALL_MS) xhr.abort();
    }, 5000);
    const fail = (message, extra = {}) => { clearInterval(watchdog); reject(Object.assign(new Error(message), extra)); };
    xhr.open("PUT", url);
    for (const [key, value] of Object.entries(uploadHeaders())) xhr.setRequestHeader(key, value);
    xhr.upload.onprogress = (e) => { last = Date.now(); onProgress(e.loaded); };
    xhr.onload = () => {
      clearInterval(watchdog);
      let body = {};
      try { body = JSON.parse(xhr.responseText || "{}"); } catch { /* not JSON */ }
      if (xhr.status < 300) return resolve(body);
      const detail = body.detail || {};
      if (xhr.status === 409 && typeof detail.offset === "number") return fail("resume", { offset: detail.offset });
      // 4xx: the NAS refused this file (name, space, disk full…): trying again won't help.
      const permanent = xhr.status >= 400 && xhr.status < 500 && ![408, 429].includes(xhr.status) || xhr.status === 507;
      fail(typeof detail === "string" ? tError(detail) : t("httpError", { status: xhr.status }), { permanent, status: xhr.status });
    };
    xhr.onerror = () => fail(t("connectionLost"));
    xhr.onabort = () => fail(t("connectionStalled"));
    xhr.send(blob);
  });
}

const uploadUrl = (job, extra) =>
  `${uploads.base ? uploads.base + "/" : ""}api/upload?${qs({ space: job.space, path: job.path, name: job.name, ...extra })}`;
const uploadApi = (url) => api(url, { headers: uploadHeaders() });

async function serverOffset(job) {
  const { offset } = await uploadApi(uploadUrl(job));
  return offset;
}

// Waits out a bad network before trying again: a few seconds first, then up to 30.
async function waitToRetry(attempt) {
  if (!navigator.onLine) {
    setUploadStatus(t("uploadPaused"));
    return untilOnline();
  }
  for (let s = Math.min(30, 2 ** Math.min(attempt, 5)); s > 0; s--) {
    setUploadStatus(t("retryingIn", { s, i: attempt }));
    await sleep(1000);
  }
}

// Already there, half sent, or another file with this name? Asked again until the NAS answers.
async function uploadPlan(job) {
  const since = Date.now();
  for (let attempt = 1; ; attempt++) {
    try {
      return await uploadApi(uploadUrl(job, { size: job.size }));
    } catch (err) {
      if (passRefused(err)) continue;
      if (!err.status) directFailed();
      if (err.status && err.status < 500 && ![408, 429].includes(err.status)) throw err;  // refused: name, space…
      if (Date.now() - since > GIVE_UP_MS) throw err;
      await waitToRetry(attempt);
    }
  }
}

async function uploadJob(job) {
  const plan = await uploadPlan(job);
  setUploadStatus("");
  job.name = plan.name;
  if (plan.complete) { job.sent = job.size; job.state = "skipped"; return; }
  let offset = plan.offset;
  let chunk = 8 * 1024 * 1024;
  let failingSince = 0;
  let attempt = 0;
  let good = 0;
  job.state = "uploading";
  for (;;) {
    const end = Math.min(offset + chunk, job.size);
    const final = end >= job.size;
    try {
      await putChunk(uploadUrl(job, { offset, ...(final ? { final: 1 } : {}) }), job.file.slice(offset, end),
        (loaded) => { job.sent = offset + loaded; paintUploads(); });
      job.sent = offset = end;
      failingSince = attempt = 0;
      uploads.directFailures = 0;
      setUploadStatus("");
      if (++good >= 3 && chunk < CHUNK_MAX) { chunk *= 2; good = 0; }  // the network is fine again
      if (final) { job.state = "done"; return; }
    } catch (err) {
      if (err.offset !== undefined) { offset = err.offset; continue; }  // the NAS says where to go on
      if (passRefused(err)) continue;
      if (err.permanent) throw err;
      directFailed();
      good = 0;
      // Phone locked, app in the background or offline: waiting doesn't count as failing.
      if (document.hidden || !navigator.onLine) {
        failingSince = attempt = 0;
      } else {
        failingSince = failingSince || Date.now();
        if (Date.now() - failingSince > GIVE_UP_MS) throw err;
        chunk = Math.max(CHUNK_MIN, chunk / 2);  // smaller pieces get through a bad network
      }
      await waitToRetry(++attempt);
      // Go on from what actually reached the disk, not from the start of the piece.
      try { offset = await serverOffset(job); } catch { /* still offline: the same piece again */ }
      job.sent = offset;
    }
  }
}

// Resolves when the device is online again. (A locked phone just freezes the page: it goes
// on by itself when unlocked; a background tab on a computer keeps uploading.)
function untilOnline() {
  return new Promise((resolve) => {
    const check = () => {
      if (!navigator.onLine) return;
      window.removeEventListener("online", check);
      setTimeout(resolve, 1000);  // let the network come back up
    };
    window.addEventListener("online", check);
    check();
  });
}

// Keep the screen on while uploading, where the browser allows it, so the phone doesn't lock mid-way.
async function keepAwake() {
  try { return await navigator.wakeLock.request("screen"); } catch { return null; }
}
document.addEventListener("visibilitychange", async () => {
  if (!document.hidden && uploads.running && (!uploads.wakeLock || uploads.wakeLock.released)) uploads.wakeLock = await keepAwake();
});
window.addEventListener("beforeunload", (e) => {
  if (uploads.running) { e.preventDefault(); e.returnValue = ""; }
});

// --- The queue, remembered across reloads ---------------------------------------

const fileKey = (f) => `${f.name}|${f.size}|${f.lastModified}`;

function saveQueue() {
  const left = uploads.jobs.filter((j) => !["done", "skipped"].includes(j.state))
    .map((j) => ({ key: j.key, name: j.original, size: j.size, space: j.space, path: j.path }));
  try {
    if (left.length) localStorage.setItem(QUEUE_KEY, JSON.stringify(left));
    else localStorage.removeItem(QUEUE_KEY);
  } catch { /* not remembered */ }
}

function savedQueue() {
  try { return JSON.parse(localStorage.getItem(QUEUE_KEY) || "[]"); } catch { return []; }
}

function upload(files) {
  if (!files.length) return;
  // Files of an unfinished upload go back where they were going; new ones to this folder.
  const saved = new Map(savedQueue().map((s) => [s.key, s]));
  const now = new Date();
  const here = state.view === "photos"
    ? join(t("photosFolder"), String(now.getFullYear()), String(now.getMonth() + 1).padStart(2, "0"))
    : state.path;
  const space = isDisk(state.space) ? "personal" : state.space;
  const queued = new Set(uploads.jobs.filter((j) => !["done", "skipped", "failed"].includes(j.state)).map((j) => j.key));
  for (const file of files) {
    const key = fileKey(file);
    if (queued.has(key)) continue;
    const before = saved.get(key);
    uploads.jobs = uploads.jobs.filter((j) => j.key !== key);  // choosing a failed file again retries it
    uploads.jobs.push({ key, file, original: file.name, name: file.name, size: file.size, sent: 0, state: "waiting", error: "",
      space: before ? before.space : space, path: before ? before.path : here });
  }
  uploads.open = true;
  saveQueue();
  runUploads();
}

async function runUploads() {
  paintUploads();
  if (uploads.running) return;
  uploads.running = true;
  uploads.started = Date.now();
  uploads.startBytes = sum(uploads.jobs, "sent");
  uploads.wakeLock = await keepAwake();
  await pickUploadRoute();
  let job;
  while ((job = uploads.jobs.find((j) => j.state === "waiting"))) {
    // Back on Ingress after a hiccup (e.g. NAS Assistant restarting): try the direct way again.
    if (!uploads.base) { uploads.directFailures = 0; await pickUploadRoute(); }
    job.state = "uploading";
    paintUploads();
    try {
      await uploadJob(job);
    } catch (err) {
      job.state = "failed";
      job.error = err.message;
    }
    setUploadStatus("");
    saveQueue();
    paintUploads();
  }
  uploads.running = false;
  if (uploads.wakeLock) uploads.wakeLock.release().catch(() => {});
  paintUploads();
  render();
  loadStatus();
}

const sum = (jobs, field) => jobs.reduce((n, j) => n + j[field], 0);

function setUploadStatus(text) {
  uploads.status = text;
  paintUploads();
}

// --- The upload panel: how much, how much is left, what didn't make it -----------

const UPLOAD_ICONS = { waiting: "clock", uploading: "upload", done: "check", skipped: "check", failed: "close" };
let paintQueued = false;

function paintUploads() {
  if (paintQueued) return;
  paintQueued = true;
  // A timer, not requestAnimationFrame: the panel must be right when coming back to the tab.
  setTimeout(() => { paintQueued = false; drawUploads(); }, 100);
}

function drawUploads() {
  const panel = $("upload-panel");
  const jobs = uploads.jobs;
  const saved = uploads.running ? [] : savedQueue().filter((s) => !jobs.some((j) => j.key === s.key));
  panel.hidden = !jobs.length && !saved.length;
  if (panel.hidden) return;
  const total = sum(jobs, "size") || 1;
  const sent = sum(jobs, "sent");
  const count = (state) => jobs.filter((j) => j.state === state).length;
  const failed = jobs.filter((j) => j.state === "failed");
  const finished = count("done") + count("skipped");
  const seconds = (Date.now() - uploads.started) / 1000;
  const speed = uploads.running && seconds > 3 ? (sent - uploads.startBytes) / seconds : 0;
  const left = total - sent - sum(failed, "size") + sum(failed, "sent");

  const head = el("div", "up-head");
  const title = jobs.length
    ? t(uploads.running ? "upTitle" : failed.length ? "upTitleFailed" : "upTitleDone", { i: finished, n: jobs.length })
    : t("upResumeTitle", { n: saved.length });
  head.append(el("strong", "", title));
  const toggle = el("button", "icon-btn");
  toggle.append(iconEl(uploads.open ? "down" : "up"));
  toggle.title = t(uploads.open ? "upHide" : "upShow");
  toggle.onclick = () => { uploads.open = !uploads.open; drawUploads(); };
  head.append(toggle);
  if (!uploads.running) {
    const close = el("button", "icon-btn");
    close.append(iconEl("close"));
    close.title = t("close");
    // Files not uploaded stay remembered: the panel then offers to choose them again.
    close.onclick = () => {
      if (!jobs.length) try { localStorage.removeItem(QUEUE_KEY); } catch { /* nothing to forget */ }
      uploads.jobs = [];
      drawUploads();
    };
    head.append(close);
  }
  const nodes = [head];

  if (jobs.length) {
    const bar = el("div", "bar");
    const fill = el("div", "bar-fill");
    fill.style.width = `${Math.min(100, (sent / total) * 100)}%`;
    bar.append(fill);
    const figures = [t("upSent", { sent: formatSize(sent), total: formatSize(total) })];
    if (uploads.running && left > 0) figures.push(t("upLeft", { left: formatSize(left) }));
    if (speed > 0) {
      figures.push(`${formatSize(speed)}/s`);
      figures.push(t("upEta", { time: duration(left / speed) }));
    }
    const chips = el("div", "up-chips");
    if (count("done")) chips.append(el("span", "up-chip ok", t("upDone", { n: count("done") })));
    if (count("skipped")) chips.append(el("span", "up-chip ok", t("upSkipped", { n: count("skipped") })));
    if (count("waiting") + count("uploading")) chips.append(el("span", "up-chip", t("upWaiting", { n: count("waiting") + count("uploading") })));
    if (failed.length) chips.append(el("span", "up-chip bad", t("upFailed", { n: failed.length })));
    nodes.push(bar, el("div", "up-figures", figures.join(" · ")), chips);
    if (uploads.status) nodes.push(el("div", "up-status", uploads.status));
  }

  if (uploads.open) {
    const list = el("div", "up-list");
    // Failed files first, then the one going up, then the rest (the last 150).
    const order = { failed: 0, uploading: 1, waiting: 2, done: 3, skipped: 3 };
    const rows = [...jobs].sort((a, b) => order[a.state] - order[b.state]).slice(0, 150);
    for (const job of rows) {
      const row = el("div", `up-row ${job.state}`);
      row.append(iconEl(UPLOAD_ICONS[job.state]));
      const text = el("div", "up-name");
      text.append(el("div", "", job.name));
      const sub = job.state === "failed" ? job.error
        : job.state === "skipped" ? t("upAlready")
          : job.state === "uploading" ? `${Math.floor((job.sent / (job.size || 1)) * 100)}% · ${formatSize(job.size)}`
            : formatSize(job.size);
      text.append(el("div", "card-sub", sub));
      row.append(text);
      list.append(row);
    }
    if (rows.length) nodes.push(list);
    if (saved.length) {
      nodes.push(el("p", "up-hint", t("upResumeText", { n: saved.length,
        size: formatSize(saved.reduce((n, s) => n + s.size, 0)) })));
    }
  }

  const actions = el("div", "up-actions");
  if (!uploads.running && failed.length) {
    const retry = el("button", "btn primary", t("upRetry"));
    retry.onclick = () => {
      for (const job of failed) Object.assign(job, { state: "waiting", error: "" });
      runUploads();
    };
    actions.append(retry);
  }
  if (!uploads.running && saved.length) {
    const pick = el("button", "btn primary", t("upPickAgain"));
    pick.onclick = () => $("file-input").click();
    const forget = el("button", "btn", t("upForget"));
    forget.onclick = () => { try { localStorage.removeItem(QUEUE_KEY); } catch { /* nothing */ } drawUploads(); };
    actions.append(pick, forget);
  }
  if (actions.children.length) nodes.push(actions);
  panel.classList.toggle("collapsed", !uploads.open);
  panel.replaceChildren(...nodes);
}

function duration(seconds) {
  if (!isFinite(seconds)) return "…";
  if (seconds < 60) return t("secondsShort", { n: Math.max(1, Math.round(seconds)) });
  if (seconds < 3600) return t("minutesShort", { n: Math.round(seconds / 60) });
  return t("hoursShort", { h: Math.floor(seconds / 3600), m: Math.round((seconds % 3600) / 60) });
}

drawUploads();  // an upload left unfinished last time

$("file-input").onchange = (e) => { upload([...e.target.files]); e.target.value = ""; };
const main = $("main");
const draggingFiles = (e) => e.dataTransfer.types.includes("Files") && state.view !== "trash";
main.ondragover = (e) => {
  if (!draggingFiles(e)) return;
  e.preventDefault();
  if ($("setup").hidden) main.classList.add("dragging");
};
main.ondragleave = (e) => { if (!main.contains(e.relatedTarget)) main.classList.remove("dragging"); };
main.ondrop = (e) => {
  if (!draggingFiles(e)) return;
  e.preventDefault();
  main.classList.remove("dragging");
  if ($("setup").hidden) upload([...e.dataTransfer.files]);
};

$("new-folder").onclick = async () => {
  const name = prompt(t("newFolderPrompt"));
  if (!name) return;
  try { await post("api/folders", { space: state.space, path: state.path, name }); render(); }
  catch (err) { alert(err.message); }
};

// --- Disk status and setup wizard --------------------------------------------

let lastDiskState = null;

async function loadStatus() {
  try {
    const { disk, usage, new_disks: newDisks } = await api("api/status");
    lastDiskState = disk;
    showDiskBanner(newDisks || []);
    showSetup(disk !== "mounted", disk);
    if (disk !== "mounted") {
      $("disk-label").textContent = t(disk === "missing" ? "diskMissing" : disk === "ejected" ? "diskEjectedShort" : "diskNone");
      $("disk-bar").style.width = "0";
      return false;
    }
    $("disk-label").textContent = t("diskFree", { free: formatSize(usage.free), total: formatSize(usage.total) });
    $("disk-bar").style.width = `${(usage.used / usage.total) * 100}%`;
    return true;
  } catch {
    return false;
  }
}

const FS_NAMES = { ext4: "ext4", exfat: "exFAT", ntfs: "NTFS", vfat: "FAT32" };

function showSetup(visible, disk) {
  $("setup").hidden = !visible;
  for (const id of ["gallery", "files", "crumbs", "topbar", "home", "disks", "collections", "chips"]) $(id).hidden = visible;
  if (visible) showEmpty(null);
  if (!visible) return;
  if (disk === "ejected") {
    // The NAS disk was ejected on purpose: everything pauses until it is reactivated.
    $("disk-list").innerHTML = "";
    $("disk-refresh").hidden = true;
    $("setup").querySelector("h1").textContent = t("nasEjectedTitle");
    const admin = state.user && state.user.is_admin;
    $("setup-lead").textContent = t(admin ? "nasEjected" : "nasEjectedUser");
    if (admin) {
      const again = el("button", "btn primary", t("reactivate"));
      again.onclick = () => diskAction(t("confirmReactivate"), () => post("api/disks/reactivate", {}));
      $("disk-list").append(again);
    }
    return;
  }
  $("setup").querySelector("h1").textContent = t("setupTitle");
  $("disk-refresh").hidden = false;
  if (!state.user || !state.user.is_admin) {
    $("setup-lead").textContent = t("setupNoAdmin");
    $("disk-list").innerHTML = "";
    $("disk-refresh").hidden = true;
    return;
  }
  if (disk === "uninitialized") {
    // The chosen NAS disk is brand new (no filesystem): preparing it is the user's call.
    $("setup-lead").textContent = t("nasNeedsInit");
    const init = el("button", "btn danger", t("initialize"));
    init.onclick = () => askInitialize({ model: t("roleNas") }, { role: "nas", size: 0 });
    $("disk-list").replaceChildren(init);
    return;
  }
  $("setup-lead").textContent = t(disk === "missing" ? "nasUnplugged" : "setupLead");
  loadNasCandidates();
}

// No NAS disk (unplugged, or never set): plugging it back is enough, or pick another
// disk to be the NAS disk, used as it is.
async function loadNasCandidates() {
  const list = $("disk-list");
  list.replaceChildren(el("p", "lead", t("searchingDisks")));
  let info;
  try {
    info = await api("api/disks/overview");
  } catch {
    return loadDisks();  // the classic setup (protection mode off)
  }
  list.replaceChildren();
  for (const disk of info.disks) {
    for (const part of disk.partitions) {
      if (part.role !== "free" || !part.id || part.same_disk_as_nas) continue;
      const card = el("div", "disk-item");
      const badge = el("div", "disk-icon");
      badge.append(iconEl("disk"));
      const text = el("div", "disk-info");
      text.append(el("div", "disk-title", disk.model),
        el("div", "disk-sub", [part.label, FS_NAMES[part.fstype] || part.fstype, formatSize(part.size)].filter(Boolean).join(" · ")));
      const use = el("button", "btn primary", t("useAsNas"));
      use.onclick = () => diskAction(t("confirmUseAsNas", { name: disk.model }), () => post("api/disks/role", { id: part.id, role: "nas" }));
      text.append(use);
      card.append(badge, text);
      list.append(card);
    }
  }
  if (!list.children.length) list.append(el("p", "lead", t("diskNotListed")));
  // The classic setup needs every disk readable: only offered with protection mode off.
  try {
    const { disks: all } = await api("api/disks");
    if (all.length && all.every((d) => d.accessible)) {
      const more = el("button", "btn link subtle", t("moreOptions"));
      more.onclick = loadDisks;
      list.append(more);
    }
  } catch { /* not offered */ }
}

// "New disk connected": the user decides what it is for.
function showDiskBanner(newDisks) {
  const banner = $("disk-banner");
  banner.hidden = !newDisks.length;
  banner.replaceChildren();
  for (const disk of newDisks) {
    const row = el("div", "disk-banner-row");
    row.append(iconEl("disk"), el("span", "", t("newDiskBanner", { name: disk.name })));
    const choose = el("button", "btn primary", t("chooseUse"));
    choose.onclick = () => go("personal", "disks");
    const later = el("button", "btn", t("notNow"));
    later.onclick = async () => { await post("api/disks/dismiss", { id: disk.id }); loadStatus(); };
    row.append(choose, later);
    banner.append(row);
  }
}

// Plug and play: notice disks coming and going without reloading the page.
setInterval(async () => {
  if (!$("viewer").hidden) return;
  try {
    const { disk, new_disks: newDisks } = await api("api/status");
    showDiskBanner(newDisks || []);
    if (disk === lastDiskState) return;
    if (disk === "mounted" && lastDiskState !== null) return location.reload();  // the NAS is back
    loadStatus();
  } catch { /* restarting: try again at the next tick */ }
}, 10000);

async function loadDisks() {
  const list = $("disk-list");
  list.replaceChildren(el("p", "lead", t("searchingDisks")));
  try {
    const { disks } = await api("api/disks");
    list.innerHTML = "";
    if (disks.some((d) => !d.accessible)) {
      list.append(el("p", "notice", t("protectionNotice")));
    }
    if (!disks.length) list.append(el("p", "lead", t("noDisks")));
    for (const disk of disks) list.append(diskItem(disk));
  } catch (err) {
    list.replaceChildren(el("p", "lead", err.message));
  }
}

function diskItem(disk) {
  const card = el("div", "disk-item");
  const badge = el("div", "disk-icon");
  badge.append(iconEl("disk"));
  const info = el("div", "disk-info");
  const kind = [disk.transport, disk.removable ? t("removable") : ""].filter(Boolean).join(" · ");
  info.append(el("div", "disk-title", disk.model), el("div", "disk-sub", [formatSize(disk.size), kind, disk.path].filter(Boolean).join(" · ")));
  card.append(badge, info);

  if (!disk.accessible) {
    info.append(el("div", "disk-sub", t("diskLocked")));
    return card;
  }
  for (const part of disk.partitions) {
    const row = el("div", "part-row");
    const desc = [part.label || t("unnamed"), FS_NAMES[part.fstype] || part.fstype || t("unformatted"), formatSize(part.size)].join(" · ");
    row.append(el("span", "", desc));
    if (part.usable) {
      const use = el("button", "btn primary", t("useAsIs"));
      use.title = t("useAsIsTitle");
      use.onclick = () => runDiskAction(use, "api/disks/use", { uuid: part.uuid });
      row.append(use);
    } else {
      row.append(el("span", "disk-sub", t("unsupported")));
    }
    info.append(row);
  }
  const actions = el("div", "disk-actions");
  const format = el("button", disk.partitions.some((p) => p.usable) ? "btn link" : "btn danger",
    t(disk.partitions.length ? "eraseAndFormat" : "prepareDisk"));
  format.onclick = () => askFormat(disk, format);
  actions.append(format);
  info.append(actions);
  return card;
}

async function runDiskAction(button, url, fields) {
  document.querySelectorAll(".disk-item button").forEach((b) => (b.disabled = true));
  button.textContent = t("wait");
  try {
    await post(url, fields);
    if (await loadStatus()) render();
  } catch (err) {
    alert(err.message);
    loadDisks();
  }
}

function askFormat(disk, button) {
  const dialog = $("format-dialog");
  const name = el("span", "", `${disk.model} (${formatSize(disk.size)})`).innerHTML;
  $("format-text").innerHTML = t("formatText", { name });
  $("format-word").innerHTML = t("formatConfirm", { word: t("formatWord") });
  $("format-confirm").value = "";
  dialog.onclose = () => {
    // The user types the word in their own language; the server always wants "FORMAT".
    const typed = $("format-confirm").value.trim().toUpperCase();
    if (dialog.returnValue === "ok") {
      runDiskAction(button, "api/disks/format", { path: disk.path, confirm: typed === t("formatWord") ? "FORMAT" : typed });
    }
  };
  dialog.showModal();
}

$("disk-refresh").onclick = loadDisks;

document.querySelectorAll("#layout-switch button").forEach((button) => {
  button.onclick = () => {
    state.layout = button.dataset.layout;
    try { localStorage.setItem("nas-layout", state.layout); } catch { /* private window: not remembered */ }
    render();
  };
});

// --- Start --------------------------------------------------------------------

translatePage();
document.querySelectorAll(".nav-item").forEach((btn) => {
  btn.onclick = () => go(btn.dataset.space, btn.dataset.view);
});
paintIcons();

api("api/me")
  .then((u) => {
    state.user = u;
    document.querySelectorAll(".nav-admin").forEach((node) => { node.hidden = !u.is_admin; });
    const avatar = avatarEl("avatar", u.display_name);
    $("user").append(avatar, el("span", "", u.display_name));
  })
  .catch(() => {})
  .finally(async () => {
    if (await loadStatus()) go("personal", "home");
  });
