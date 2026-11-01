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
  if (!res.ok) throw new Error(tError((await res.json().catch(() => ({}))).detail || res.statusText));
  return res.json();
}

const qs = (params) => new URLSearchParams(params).toString();
const join = (...parts) => parts.filter(Boolean).join("/");
const IMAGE = /\.(jpe?g|png|gif|webp|heic|heif|bmp|tiff?)$/i;
const VIDEO = /\.(mp4|mov|m4v|webm|mkv|avi|3gp)$/i;
const kindOf = (name) => (IMAGE.test(name) ? "image" : VIDEO.test(name) ? "video" : null);

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
  document.querySelectorAll(".nav-item").forEach((b) =>
    b.classList.toggle("active", b.dataset.space === space && b.dataset.view === view));
  render();
}

function setHeader(title, subtitle) {
  $("title").textContent = title;
  $("subtitle").textContent = subtitle;
  $("new-folder").hidden = state.view !== "files";
  $("layout-switch").hidden = state.view !== "files";
  document.querySelectorAll("#layout-switch button").forEach((b) => b.classList.toggle("active", b.dataset.layout === state.layout));
  $("upload-btn").hidden = state.view === "trash";
  $("empty-trash").hidden = true;
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
  showEmpty(null);
  document.body.classList.toggle("on-home", state.view === "home");
  $("home").hidden = state.view !== "home";
  if (state.view === "home") return renderHome();
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
  img.src = thumbUrl(item.path, item.v);
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
  await post("api/favorites", { space: state.space, path: item.path, favorite: item.fav ? "0" : "1" });
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
    if (i < parts.length) dropTarget(a, parts.slice(0, i).join("/"));
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
    img.src = thumbUrl(path, entry.v);
    img.onerror = () => { thumb.innerHTML = ""; thumb.append(iconEl(KIND_ICONS[kind])); };
    thumb.append(img);
  } else {
    thumb.append(iconEl(entry.is_dir ? "folder" : KIND_ICONS[entry.kind] || "file"));
  }

  const actions = el("div", "row-actions");
  const more = el("button", "icon-btn");
  more.title = t("more");
  more.append(iconEl("more"));
  more.onclick = (e) => { e.stopPropagation(); openMenu(entry, more.getBoundingClientRect()); };
  actions.append(more);
  row.oncontextmenu = (e) => {
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
      el("div", "meta", shortFmt.format(entry.modified * 1000)),
      el("div", "meta", entry.is_dir ? "—" : formatSize(entry.size)),
      actions,
    );
  } else {
    row.append(thumb, name, actions);
  }

  // Drag a row onto a folder (or a breadcrumb) to move it.
  row.draggable = true;
  row.ondragstart = (e) => {
    e.dataTransfer.setData(DRAG_TYPE, JSON.stringify({ space: state.space, path }));
    e.dataTransfer.effectAllowed = "move";
  };
  if (entry.is_dir) dropTarget(row, path);
  row.onclick = () => {
    if (entry.is_dir) return go(state.space, "files", path);
    if (kind) return openViewer(state.items.findIndex((i) => i.path === path));
    window.open(fileUrl(path, true), "_blank");
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
};

async function renderHome() {
  const seq = renderSeq;
  let data, status;
  try {
    [data, status, state.backup, state.devices] = await Promise.all(
      [api("api/home"), api("api/status"), api("api/backup"), api("api/devices")]);
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
    favoritesCard(data.favorites),
    devicesCard(state.devices),
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
  add.onclick = connectPhone;
  body.append(add);
  node.append(body);
  return node;
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
  Object.assign(picker, { space: state.space, path: state.kind === "all" ? state.path : "", entry, from: state.space });
  $("move-title").textContent = t("moveTitle", { name: entry.name });
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
  moveItem(picker.from, picker.entry.path, picker.space, picker.path);
};
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
    video.src = fileUrl(item.path, true);
    video.controls = true;
    video.autoplay = true;
    video.playsInline = true;
    video.poster = thumbUrl(item.path, item.v, "l");
    stage.append(video);
  } else {
    const img = el("img");
    img.src = thumbUrl(item.path, item.v, "l");
    img.alt = item.name;
    stage.append(img);
    // Preload the neighbours so swiping feels instant.
    for (const n of [state.items[state.viewerIndex + 1], state.items[state.viewerIndex - 1]]) {
      if (n && n.kind === "image") new Image().src = thumbUrl(n.path, n.v, "l");
    }
  }
  const date = new Date(item.taken * 1000);
  $("v-date").textContent = `${dayFmt.format(date)} · ${timeFmt.format(date)}`;
  $("v-name").textContent = item.name;
  $("v-download").href = fileUrl(item.path);
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
function paintFavButton(item) {
  const button = $("v-fav");
  button.replaceChildren(iconEl(item.fav ? "heartFill" : "heart"));
  button.title = t(item.fav ? "unfavorite" : "favorite");
  button.classList.toggle("on", !!item.fav);
}

$("v-fav").onclick = async () => {
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
  const item = state.items[state.viewerIndex];
  inlineRename($("v-name"), { name: item.name, is_dir: false }, async (name) => {
    const { name: saved } = await post("api/rename", { space: state.space, path: item.path, name });
    const folder = item.path.includes("/") ? item.path.slice(0, item.path.lastIndexOf("/") + 1) : "";
    Object.assign(item, { name: saved, path: folder + saved });
    showViewerItem();
    render();
  });
};
$("v-name").onclick = () => $("v-rename").click();
$("v-delete").onclick = async () => {
  const item = state.items[state.viewerIndex];
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

// Files travel in 16 MB pieces: a dropped connection only costs one piece,
// and no request goes over the 100 MB limit of tunnels such as Cloudflare.
const CHUNK = 16 * 1024 * 1024;
const STALL_MS = 60 * 1000;
const RETRIES = 4;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function putChunk(url, blob, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    let last = Date.now();
    const watchdog = setInterval(() => {
      if (Date.now() - last > STALL_MS) xhr.abort();
    }, 5000);
    const fail = (message, offset) => { clearInterval(watchdog); reject(Object.assign(new Error(message), { offset })); };
    xhr.open("PUT", url);
    xhr.upload.onprogress = (e) => { last = Date.now(); onProgress(e.loaded); };
    xhr.onload = () => {
      clearInterval(watchdog);
      let body = {};
      try { body = JSON.parse(xhr.responseText || "{}"); } catch { /* not JSON */ }
      if (xhr.status < 300) return resolve(body);
      const detail = body.detail || {};
      if (xhr.status === 409 && typeof detail.offset === "number") return fail("resume", detail.offset);
      fail(typeof detail === "string" ? tError(detail) : t("httpError", { status: xhr.status }));
    };
    xhr.onerror = () => fail(t("connectionLost"));
    xhr.onabort = () => fail(t("connectionStalled"));
    xhr.send(blob);
  });
}

async function uploadOne(file, path, onProgress) {
  let offset = 0;
  let attempts = 0;
  for (;;) {
    const end = Math.min(offset + CHUNK, file.size);
    const final = end >= file.size;
    const url = `api/upload?${qs({ space: state.space, path, name: file.name, offset, ...(final ? { final: 1 } : {}) })}`;
    try {
      await putChunk(url, file.slice(offset, end), (loaded) => onProgress(offset + loaded));
      if (final) return;
      offset = end;
      attempts = 0;
    } catch (err) {
      if (err.offset !== undefined) { offset = err.offset; continue; }  // server tells where to resume
      if (++attempts >= RETRIES) throw err;
      $("toast-text").textContent = t("retrying", { i: attempts, n: RETRIES - 1 });
      await sleep(2000 * attempts);
      // Resume from what actually reached the disk, not from the start of the piece.
      try {
        ({ offset } = await api(`api/upload?${qs({ space: state.space, path, name: file.name })}`));
      } catch { /* still offline: retry the same piece */ }
    }
  }
}

async function upload(files) {
  if (!files.length) return;
  // In the gallery new photos go to Photos/<year>/<month>, like a camera roll.
  const now = new Date();
  const target = state.view === "photos"
    ? join(t("photosFolder"), String(now.getFullYear()), String(now.getMonth() + 1).padStart(2, "0"))
    : state.path;
  const total = files.reduce((sum, f) => sum + f.size, 0) || 1;
  let done = 0;
  const errors = [];
  $("toast").hidden = false;
  for (const [i, file] of files.entries()) {
    $("toast-text").textContent = t("uploading", { i: i + 1, n: files.length, name: file.name });
    try {
      await uploadOne(file, target, (loaded) => { $("toast-bar").style.width = `${((done + loaded) / total) * 100}%`; });
    } catch (err) {
      errors.push(`${file.name}: ${err.message}`);
    }
    done += file.size;
  }
  $("toast-text").textContent = errors.length ? t("notUploaded", { n: errors.length }) : t("uploaded", { n: files.length });
  $("toast-bar").style.width = "100%";
  if (errors.length) alert(errors.join("\n"));
  setTimeout(() => { $("toast").hidden = true; $("toast-bar").style.width = "0"; }, 2500);
  render();
  loadStatus();
}

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

async function loadStatus() {
  try {
    const { disk, usage } = await api("api/status");
    showSetup(disk !== "mounted", disk);
    if (disk !== "mounted") {
      $("disk-label").textContent = t(disk === "missing" ? "diskMissing" : "diskNone");
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
  for (const id of ["gallery", "files", "crumbs", "topbar"]) $(id).hidden = visible;
  if (visible) showEmpty(null);
  if (!visible) return;
  if (!state.user || !state.user.is_admin) {
    $("setup-lead").textContent = t("setupNoAdmin");
    $("disk-list").innerHTML = "";
    $("disk-refresh").hidden = true;
    return;
  }
  if (disk === "missing") {
    $("setup-lead").textContent = t("setupMissing");
  }
  loadDisks();
}

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
    const avatar = avatarEl("avatar", u.display_name);
    $("user").append(avatar, el("span", "", u.display_name));
  })
  .catch(() => {})
  .finally(async () => {
    if (await loadStatus()) go("personal", "home");
  });
