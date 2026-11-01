// All URLs are relative so the UI works behind Ingress (/api/hassio_ingress/<token>/).
const state = { space: "personal", view: "photos", path: "", kind: "all", user: null, items: [], viewerIndex: -1 };
const $ = (id) => document.getElementById(id);

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
  move: '<path d="M3 7.5A2.5 2.5 0 0 1 5.5 5H9l2 2.2h7.5A2.5 2.5 0 0 1 21 9.7v7.8a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 17.5z"/><path d="M9 13.5h6M12.5 11l2.5 2.5-2.5 2.5"/>',
};

// File types, as catalogued by the server (app/kinds.py).
const KIND_ICONS = { image: "photos", video: "video", audio: "audio", document: "document", archive: "archive", other: "file" };
const KIND_FILTERS = ["all", "image", "video", "audio", "document", "archive", "other"];

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

const thumbUrl = (path, v, size = "s") => `api/thumb?${qs({ space: state.space, path, size, v })}`;
const fileUrl = (path, inline = false) => `api/download?${qs({ space: state.space, path, ...(inline ? { inline: 1 } : {}) })}`;

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
}

function showEmpty(title, text) {
  $("empty").hidden = !title;
  if (title) { $("empty-title").textContent = title; $("empty-text").textContent = text; }
}

function render() {
  $("gallery").innerHTML = "";
  $("files").innerHTML = "";
  $("crumbs").innerHTML = "";
  $("chips").innerHTML = "";
  showEmpty(null);
  return state.view === "photos" ? renderGallery() : renderFiles();
}

// --- Gallery ------------------------------------------------------------------

async function renderGallery() {
  const where = t(state.space === "personal" ? "mySpace" : "family");
  setHeader(t(state.space === "personal" ? "photos" : "familyPhotos"), where);
  let items;
  try {
    ({ items } = await api(`api/photos?${qs({ space: state.space })}`));
  } catch (err) {
    return showEmpty(t("photosLoadError"), err.message);
  }
  state.items = items;
  const photos = items.filter((i) => i.kind === "image").length;
  const videos = items.length - photos;
  setHeader($("title").textContent,
    [where, t("photoCount", { n: photos }), videos ? t("videoCount", { n: videos }) : ""].filter(Boolean).join(" · "));
  if (!items.length) {
    return showEmpty(t("noPhotosTitle"), t("noPhotosText"));
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
  let entries;
  try {
    ({ entries } = state.kind === "all"
      ? await api(`api/files?${qs({ space: state.space, path: state.path })}`)
      : await api(`api/files/by-kind?${qs({ space: state.space, kind: state.kind })}`));
  } catch (err) {
    return showEmpty(t("folderOpenError"), err.message);
  }
  for (const e of entries) e.path = e.path || join(state.path, e.name);
  // The viewer browses the photos and videos of this list.
  state.items = entries.filter((e) => !e.is_dir && kindOf(e.name))
    .map((e) => ({ path: e.path, name: e.name, kind: kindOf(e.name), taken: e.modified, v: e.v }));
  if (!entries.length) {
    return state.kind === "all"
      ? showEmpty(t("emptyFolderTitle"), t("emptyFolderText"))
      : showEmpty(t("noKindTitle"), t("noKindText"));
  }
  const list = $("files");
  for (const entry of entries) list.append(fileRow(entry));
}

function renderChips() {
  const chips = $("chips");
  for (const kind of KIND_FILTERS) {
    const chip = el("button", kind === state.kind ? "chip active" : "chip");
    if (kind !== "all") chip.append(iconEl(KIND_ICONS[kind]));
    chip.append(el("span", "", t(`kind_${kind}`)));
    chip.onclick = () => go(state.space, "files", kind === "all" ? state.path : "", kind);
    chips.append(chip);
  }
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
  const row = el("div", "row");

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

  const name = el("div", "name");
  name.append(el("div", "", entry.name));
  if (state.kind !== "all") {
    // Catalogue view: say which folder the file is in.
    const folder = path.includes("/") ? path.slice(0, path.lastIndexOf("/")) : t(state.space === "personal" ? "files" : "sharedFiles");
    name.append(el("div", "where", folder));
  }
  row.append(
    thumb,
    name,
    el("div", "meta", shortFmt.format(entry.modified * 1000)),
    el("div", "meta", entry.is_dir ? "—" : formatSize(entry.size)),
    actions,
  );

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

async function removeItem(path) {
  await api(`api/files?${qs({ space: state.space, path })}`, { method: "DELETE" });
  loadStatus();
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

async function renameItem(entry) {
  const name = prompt(t("renamePrompt"), entry.name);
  if (!name || name === entry.name) return;
  try {
    await post("api/rename", { space: state.space, path: entry.path, name });
  } catch (err) {
    alert(err.message);
  }
  render();
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
  item("rename", t("rename"), () => renameItem(entry));
  item("move", t("moveTo"), () => openMoveDialog(entry));
  if (!entry.is_dir) item("download", t("download"), () => { location.href = fileUrl(entry.path); });
  item("trash", t("moveToTrash"), async () => {
    if (!confirm(t("confirmTrash", { name: entry.name }))) return;
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

function closeViewer() {
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
$("v-delete").onclick = async () => {
  const item = state.items[state.viewerIndex];
  if (!confirm(t("confirmTrash", { name: item.name }))) return;
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
const draggingFiles = (e) => e.dataTransfer.types.includes("Files");
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

// --- Start --------------------------------------------------------------------

translatePage();
document.querySelectorAll(".nav-item").forEach((btn) => {
  btn.onclick = () => go(btn.dataset.space, btn.dataset.view);
});
paintIcons();

api("api/me")
  .then((u) => {
    state.user = u;
    const avatar = el("span", "avatar", (u.display_name || "?").charAt(0).toUpperCase());
    $("user").append(avatar, el("span", "", u.display_name));
  })
  .catch(() => {})
  .finally(async () => {
    if (await loadStatus()) go("personal", "photos");
  });
