// All URLs are relative so the UI works behind Ingress (/api/hassio_ingress/<token>/).
const state = { space: "personal", path: "", user: null };
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
    showSetup(disk !== "mounted", disk);
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

// --- Disk setup wizard -------------------------------------------------------

const FS_NAMES = { ext4: "ext4", exfat: "exFAT", ntfs: "NTFS" };

function showSetup(visible, disk) {
  $("setup").hidden = !visible;
  for (const id of ["grid", "empty", "crumbs"]) $(id).hidden = visible;
  document.querySelector(".actions").hidden = visible;
  if (!visible) return;
  if (!state.user || !state.user.is_admin) {
    $("setup-lead").textContent = "Il NAS non ha ancora un disco. Chiedi a un amministratore di Home Assistant di configurarlo.";
    $("disk-list").innerHTML = "";
    $("disk-refresh").hidden = true;
    return;
  }
  if (disk === "missing") {
    $("setup-lead").textContent = "Il disco del NAS non è collegato. Ricollegalo e riavvia l'add-on, oppure scegline un altro.";
  }
  loadDisks();
}

async function loadDisks() {
  const list = $("disk-list");
  list.innerHTML = '<p class="lead">Cerco i dischi…</p>';
  try {
    const { disks } = await api("api/disks");
    list.innerHTML = "";
    if (disks.some((d) => !d.accessible)) {
      list.append(el("p", "notice",
        "Home Assistant non dà ancora accesso ai dischi a NAS Assistant. Nella pagina dell'add-on disattiva " +
        "\"Modalità protetta\", riavvia l'add-on e torna qui."));
    }
    if (!disks.length) list.innerHTML = '<p class="lead">Nessun disco trovato. Collegane uno e premi "Aggiorna elenco".</p>';
    for (const disk of disks) list.append(diskCard(disk));
  } catch (err) {
    list.innerHTML = `<p class="lead">${err.message}</p>`;
  }
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function diskCard(disk) {
  const card = el("div", "disk-card");
  const info = el("div", "disk-info");
  const kind = [disk.transport, disk.removable ? "rimovibile" : ""].filter(Boolean).join(" · ");
  info.append(el("div", "disk-title", disk.model), el("div", "disk-sub", [formatSize(disk.size), kind, disk.path].filter(Boolean).join(" · ")));

  if (!disk.accessible) {
    info.append(el("div", "disk-sub", "Disco non accessibile finché la modalità protetta è attiva"));
    card.append(el("div", "disk-icon", disk.transport === "USB" ? "🔌" : "💽"), info);
    return card;
  }

  for (const part of disk.partitions) {
    const row = el("div", "part-row");
    const desc = [part.label || "senza nome", FS_NAMES[part.fstype] || part.fstype || "non formattata", formatSize(part.size)].join(" · ");
    row.append(el("span", "", desc));
    if (part.usable) {
      const use = el("button", "btn primary", "Usa così com'è");
      use.title = "Nessun file viene cancellato";
      use.onclick = () => runDiskAction(use, "api/disks/use", { uuid: part.uuid });
      row.append(use);
    } else {
      row.append(el("span", "disk-sub", "formato non supportato"));
    }
    info.append(row);
  }

  const actions = el("div", "disk-actions");
  const format = el("button", disk.partitions.some((p) => p.usable) ? "btn link" : "btn danger",
    disk.partitions.length ? "Cancella tutto e formatta" : "Prepara disco (formatta)");
  format.onclick = () => askFormat(disk, format);
  actions.append(format);
  info.append(actions);

  card.append(el("div", "disk-icon", disk.transport === "USB" ? "🔌" : "💽"), info);
  return card;
}

async function runDiskAction(button, url, fields) {
  const form = new FormData();
  for (const [key, value] of Object.entries(fields)) form.append(key, value);
  document.querySelectorAll(".disk-card button").forEach((b) => (b.disabled = true));
  button.textContent = "Attendi…";
  try {
    await api(url, { method: "POST", body: form });
    await loadStatus();
    open("");
  } catch (err) {
    alert(err.message);
    loadDisks();
  }
}

function askFormat(disk, button) {
  const dialog = $("format-dialog");
  $("format-name").textContent = `${disk.model} (${formatSize(disk.size)})`;
  $("format-confirm").value = "";
  dialog.onclose = () => {
    if (dialog.returnValue === "ok") {
      runDiskAction(button, "api/disks/format", { path: disk.path, confirm: $("format-confirm").value.trim() });
    }
  };
  dialog.showModal();
}

$("disk-refresh").onclick = loadDisks;

api("api/me")
  .then((u) => { state.user = u; $("user").textContent = `👤 ${u.display_name}`; })
  .catch(() => {})
  .finally(() => { loadStatus(); load(); });
