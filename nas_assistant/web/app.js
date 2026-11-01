// All URLs are relative so the UI works behind Ingress (/api/hassio_ingress/<token>/).
const state = { space: "personal", path: "" };
const $ = (id) => document.getElementById(id);
const IMAGE = /\.(jpe?g|png|gif|webp|heic|avif)$/i;
const VIDEO = /\.(mp4|mov|m4v|webm)$/i;

async function api(url, opts) {
  const res = await fetch(url, opts);
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
  return res.json();
}

const qs = (params) => new URLSearchParams(params).toString();
const join = (...parts) => parts.filter(Boolean).join("/");

function formatSize(bytes) {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  while (bytes >= 1024 && i < units.length - 1) { bytes /= 1024; i++; }
  return `${bytes.toFixed(i ? 1 : 0)} ${units[i]}`;
}

function icon(entry) {
  if (entry.is_dir) return "📁";
  if (VIDEO.test(entry.name)) return "🎬";
  if (/\.pdf$/i.test(entry.name)) return "📄";
  return "📎";
}

function renderCrumbs() {
  const root = state.space === "personal" ? "Il mio spazio" : "Famiglia";
  const parts = state.path ? state.path.split("/") : [];
  const crumbs = $("crumbs");
  crumbs.innerHTML = "";
  [root, ...parts].forEach((label, i) => {
    if (i) crumbs.append(" › ");
    const a = document.createElement("a");
    a.textContent = label;
    a.onclick = () => open(parts.slice(0, i).join("/"));
    crumbs.append(a);
  });
}

async function load() {
  renderCrumbs();
  const grid = $("grid");
  try {
    const { entries } = await api(`api/files?${qs({ space: state.space, path: state.path })}`);
    grid.innerHTML = "";
    $("empty").hidden = entries.length > 0;
    for (const entry of entries) grid.append(card(entry));
  } catch (err) {
    grid.innerHTML = `<p class="empty">${err.message}</p>`;
  }
}

function card(entry) {
  const path = join(state.path, entry.name);
  const url = `api/download?${qs({ space: state.space, path })}`;
  const el = document.createElement("div");
  el.className = "item";
  const thumb = document.createElement("div");
  thumb.className = "thumb";
  if (IMAGE.test(entry.name)) {
    const img = document.createElement("img");
    img.loading = "lazy";
    img.src = url;
    thumb.append(img);
  } else {
    thumb.textContent = icon(entry);
  }
  const name = document.createElement("div");
  name.className = "name";
  name.textContent = entry.name;
  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = entry.is_dir ? "Cartella" : formatSize(entry.size);
  const del = document.createElement("button");
  del.className = "del";
  del.title = "Sposta nel cestino";
  del.textContent = "✕";
  del.onclick = async (e) => {
    e.stopPropagation();
    if (!confirm(`Spostare "${entry.name}" nel cestino?`)) return;
    await api(`api/files?${qs({ space: state.space, path })}`, { method: "DELETE" });
    load(); loadStatus();
  };
  el.append(thumb, name, meta, del);
  el.onclick = () => (entry.is_dir ? open(path) : window.open(url, "_blank"));
  return el;
}

function open(path) { state.path = path; load(); }

async function upload(files) {
  const progress = $("progress");
  progress.hidden = false;
  let done = 0;
  for (const file of files) {
    progress.textContent = `Caricamento ${done + 1} di ${files.length}: ${file.name}`;
    const form = new FormData();
    form.append("space", state.space);
    form.append("path", state.path);
    form.append("file", file);
    try { await api("api/upload", { method: "POST", body: form }); done++; }
    catch (err) { alert(`${file.name}: ${err.message}`); }
  }
  progress.hidden = true;
  load(); loadStatus();
}

async function loadStatus() {
  try {
    const { disk, usage } = await api("api/status");
    if (disk !== "mounted") {
      $("disk-label").textContent = disk === "missing" ? "⚠️ Disco NAS non trovato" : "⚠️ Nessun disco configurato";
      return;
    }
    $("disk-label").textContent = `${formatSize(usage.used)} di ${formatSize(usage.total)}`;
    $("disk-bar").style.width = `${(usage.used / usage.total) * 100}%`;
  } catch { /* shown by load() */ }
}

document.querySelectorAll(".nav-item").forEach((btn) => {
  btn.onclick = () => {
    document.querySelector(".nav-item.active").classList.remove("active");
    btn.classList.add("active");
    state.space = btn.dataset.space;
    open("");
  };
});

$("new-folder").onclick = async () => {
  const name = prompt("Nome della nuova cartella");
  if (!name) return;
  const form = new FormData();
  form.append("space", state.space);
  form.append("path", state.path);
  form.append("name", name);
  try { await api("api/folders", { method: "POST", body: form }); load(); }
  catch (err) { alert(err.message); }
};

$("file-input").onchange = (e) => upload([...e.target.files]);

const drop = $("drop");
drop.ondragover = (e) => { e.preventDefault(); drop.classList.add("dragging"); };
drop.ondragleave = (e) => { if (!drop.contains(e.relatedTarget)) drop.classList.remove("dragging"); };
drop.ondrop = (e) => { e.preventDefault(); drop.classList.remove("dragging"); upload([...e.dataTransfer.files]); };

api("api/me").then((u) => { $("user").textContent = `👤 ${u.display_name}`; }).catch(() => {});
loadStatus();
load();
