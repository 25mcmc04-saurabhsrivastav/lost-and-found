const state = { items: [], summary: {}, activity: [], scanId: null, cameraStream: null, facing: "environment", filter: "all", capturedPhotos: [] };
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

function escapeHtml(value = "") {
  return String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
}

async function api(url, options = {}) {
  const response = await fetch(url, options);
  let body;
  try { body = await response.json(); } catch { body = {}; }
  if (!response.ok) throw new Error(body.detail || "That didn’t work. Please try again.");
  return body;
}

function toast(message) {
  const node = $("#toast");
  node.textContent = message;
  node.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => node.classList.remove("show"), 3200);
}

function niceDate(iso, withTime = false) {
  if (!iso) return "Just now";
  const date = new Date(iso);
  return new Intl.DateTimeFormat("en-IN", withTime ? { hour: "numeric", minute: "2-digit" } : { day: "numeric", month: "short" }).format(date);
}

function itemThumb(item, large = false) {
  const fallback = { Bottle: "🧴", Lunchbox: "🍱", Clothing: "🧦", Footwear: "👟", Toy: "🧸", Bag: "🎒" }[item.category] || "✳";
  return item.photo_url
    ? `<img src="${escapeHtml(item.photo_url)}" alt="${escapeHtml(item.label)}" loading="lazy" />`
    : `<span class="emoji-fallback${large ? " large" : ""}">${fallback}</span>`;
}

function setPage(page) {
  $$(".page").forEach((node) => node.classList.toggle("active", node.id === `page-${page}`));
  $$(".nav-link").forEach((node) => node.classList.toggle("active", node.dataset.page === page));
  $("#crumb-page").textContent = ({ overview: "Overview", registry: "Item registry", returns: "Ready to return" })[page] || "Overview";
  if (page === "registry") renderRegistry();
  if (page === "returns") renderReturns();
  window.location.hash = page;
}

async function refresh() {
  try {
    const [items, summary, activity] = await Promise.all([
      api("/api/items"), api("/api/summary"), api("/api/activity"),
    ]);
    state.items = items;
    state.summary = summary;
    state.activity = activity;
    renderOverview();
    renderRegistry();
    renderReturns();
  } catch (error) {
    toast(error.message.includes("fetch") ? "Start the local app from the README to connect to the scan station." : error.message);
  }
}

function renderOverview() {
  $("#stat-registered").textContent = state.summary.registered ?? "0";
  $("#stat-found").textContent = state.summary.found ?? "0";
  $("#stat-returned").textContent = state.summary.returned ?? "0";
  $("#registry-nav-count").textContent = state.items.filter((item) => item.status === "registered").length;
  $("#return-nav-count").textContent = state.items.filter((item) => item.status === "found").length;

  const found = state.items.filter((item) => item.status === "found").slice(0, 3);
  $("#recent-found-list").innerHTML = found.length ? found.map((item) => `
    <div class="recent-item">
      <div class="item-thumb">${itemThumb(item)}</div>
      <div><strong>${escapeHtml(item.label)}</strong><small>${escapeHtml(item.category)} · ${escapeHtml(item.family_ref || "Room label not added")}</small></div>
      <span class="item-age">${niceDate(item.found_at)}</span>
    </div>`).join("") : `<div class="empty-inline">No new discoveries yet. The next scan may be the beginning of a happy reunion.</div>`;

  const activities = state.activity.slice(0, 4);
  $("#activity-list").innerHTML = activities.length ? activities.map((event) => {
    const action = event.kind === "returned" ? "made it back home" : event.kind === "logged_new" ? "was added to the pick-up shelf" : "found a likely match";
    return `<div class="activity-row"><span class="activity-dot">${event.kind === "returned" ? "↗" : "✳"}</span><div><strong>${escapeHtml(event.label)} ${action}</strong><small>${niceDate(event.created_at, true)} · ${escapeHtml(event.category)}</small></div></div>`;
  }).join("") : `<div class="empty-inline">A little win will show up here when an item is matched or returned.</div>`;

  const samples = state.items.filter((item) => item.is_demo && item.status === "registered").slice(0, 5);
  $("#demo-samples").innerHTML = samples.map((item) => `<button class="sample-chip" data-demo-id="${escapeHtml(item.id)}"><img src="${escapeHtml(item.registered_photo_url)}" alt="" />${escapeHtml(item.label.split(" ").slice(0, 2).join(" "))}</button>`).join("");
  $$("[data-demo-id]").forEach((button) => button.addEventListener("click", () => demoScan(button.dataset.demoId)));
}

function statusLabel(status) {
  return ({ registered: "Registered", found: "Found · awaiting pick-up", returned: "Returned" })[status] || status;
}

function renderRegistry() {
  const search = $("#registry-search")?.value.trim().toLowerCase() || "";
  const all = state.items.filter((item) => state.filter === "all" || item.status === state.filter)
    .filter((item) => !search || `${item.label} ${item.category} ${item.family_ref}`.toLowerCase().includes(search));
  $("#filter-all-count").textContent = state.items.length;
  const grid = $("#registry-grid");
  if (!grid) return;
  if (!all.length) {
    const title = search ? "Nothing quite like that yet." : state.filter === "found" ? "No found items in the register." : state.filter === "returned" ? "No happy returns yet." : "Your register is ready for its first belonging.";
    const copy = search ? "Try another word, category, or room label." : "Add an item photo now so it’s easier to recognise when it turns up.";
    grid.innerHTML = `<div class="empty-state"><span class="empty-state-icon">✳</span><div><strong>${title}</strong><p>${copy}</p></div></div>`;
    return;
  }
  grid.innerHTML = all.map((item) => `
    <article class="registry-card">
      <div class="registry-photo"><img src="${escapeHtml(item.photo_url)}" alt="${escapeHtml(item.label)}" loading="lazy" /><span class="status-badge ${item.status}">${statusLabel(item.status)}</span></div>
      <div class="registry-card-body"><h3 title="${escapeHtml(item.label)}">${escapeHtml(item.label)}</h3><div class="registry-card-meta"><span>${escapeHtml(item.category)}</span><span>${item.is_demo ? "Demo item" : `Added ${niceDate(item.created_at)}`}</span></div><div class="registry-card-ref">${escapeHtml(item.family_ref || "Room label not added")}</div></div>
    </article>`).join("");
}

function renderReturns() {
  const waiting = state.items.filter((item) => item.status === "found");
  const returned = state.items.filter((item) => item.status === "returned").slice(0, 8);
  $("#returns-count").textContent = waiting.length;
  $("#returns-summary-title").textContent = waiting.length ? `${waiting.length} ${waiting.length === 1 ? "little thing is" : "little things are"} waiting to go home.` : "A little room for more happy reunions.";
  $("#returns-summary-copy").textContent = waiting.length ? "Your team has confirmed these belongings. Mark each one returned at pick-up." : "Found belongings will show up here after a staff member confirms a match.";
  $("#return-list").innerHTML = waiting.length ? waiting.map((item) => `
    <article class="return-card"><img src="${escapeHtml(item.photo_url)}" alt="${escapeHtml(item.label)}" /><div><h3>${escapeHtml(item.label)}</h3><p>${escapeHtml(item.category)} · ${escapeHtml(item.family_ref || "No room label")}</p><div class="return-time">Found ${niceDate(item.found_at)}</div></div><button class="button button-light" data-return-id="${escapeHtml(item.id)}">Mark returned <span>↗</span></button></article>`).join("") : `<div class="empty-state"><span class="empty-state-icon">↗</span><div><strong>The pick-up shelf is clear.</strong><p>When your team finds and confirms an item, it’ll be ready to mark returned here.</p></div></div>`;
  $("#returned-list").innerHTML = returned.length ? returned.map((item) => `
    <article class="return-card returned-card"><img src="${escapeHtml(item.photo_url)}" alt="${escapeHtml(item.label)}" /><div><h3>${escapeHtml(item.label)}</h3><p>${escapeHtml(item.category)} · ${escapeHtml(item.family_ref || "No room label")}</p><div class="return-time">Returned ${niceDate(item.returned_at)}</div></div><span class="returned-tag">✓ Back home</span></article>`).join("") : `<div class="empty-inline">Your first reunion will leave a little note here.</div>`;
  $$('[data-return-id]').forEach((button) => button.addEventListener("click", () => markReturned(button.dataset.returnId)));
}

function openModal(id) {
  $("#" + id).classList.add("open");
  $("#" + id).setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
}

function closeModal(id) {
  $("#" + id).classList.remove("open");
  $("#" + id).setAttribute("aria-hidden", "true");
  if (!$$(".modal-backdrop.open").length) document.body.style.overflow = "";
  if (id === "scan-modal") stopCamera();
}

function resetScanModal() {
  state.scanId = null;
  state.capturedPhotos = [];
  stopCamera();
  $("#scan-content").hidden = false;
  $("#match-results").hidden = true;
  $("#match-results").innerHTML = "";
  $("#capture-empty").hidden = false;
  $("#camera-video").hidden = true;
  $("#scan-preview").hidden = true;
  $("#capture-overlay").hidden = true;
  $("#capture-overlay span").textContent = "ANGLE 1 OF 3 · PLACE ITEM";
  $("#capture-loading").hidden = true;
  $("#scan-file").value = "";
}

function openScan() { resetScanModal(); openModal("scan-modal"); }

async function startCamera() {
  stopCamera();
  state.capturedPhotos = [];
  $("#capture-overlay span").textContent = "ANGLE 1 OF 3 · PLACE ITEM";
  try {
    state.cameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: state.facing }, width: { ideal: 1280 }, height: { ideal: 900 } }, audio: false });
    const video = $("#camera-video");
    video.srcObject = state.cameraStream;
    video.hidden = false;
    $("#capture-empty").hidden = true;
    $("#scan-preview").hidden = true;
    $("#capture-overlay").hidden = false;
    $("#switch-camera").hidden = false;
    $("#switch-camera").textContent = state.facing === "environment" ? "Use front camera" : "Use back camera";
  } catch (error) {
    toast(error.name === "NotAllowedError" ? "Camera access is blocked. Upload a photo to keep going." : "Camera isn’t available here. Upload a photo to keep going.");
  }
}

function stopCamera() {
  if (state.cameraStream) state.cameraStream.getTracks().forEach((track) => track.stop());
  state.cameraStream = null;
  const video = $("#camera-video");
  if (video) video.srcObject = null;
}

async function submitScan(files) {
  const photoFiles = Array.isArray(files) ? files : files ? [files] : [];
  if (!photoFiles.length) return;
  if (photoFiles.length > 3) return toast("Choose up to three item photos for one scan.");
  stopCamera();
  $("#capture-empty").hidden = true;
  $("#camera-video").hidden = true;
  const preview = $("#scan-preview");
  preview.src = URL.createObjectURL(photoFiles[0]);
  preview.hidden = false;
  $("#capture-overlay").hidden = true;
  $("#capture-loading").hidden = false;
  try {
    const form = new FormData();
    photoFiles.forEach((file, index) => form.append("photos", file, file.name || `station-view-${index + 1}.jpg`));
    const result = await api("/api/scans", { method: "POST", body: form });
    state.scanId = result.scan_id;
    $("#capture-loading").hidden = true;
    $("#scan-content").hidden = true;
    renderMatches(result);
  } catch (error) {
    $("#capture-loading").hidden = true;
    $("#capture-empty").hidden = false;
    $("#scan-preview").hidden = true;
    $("#scan-file").value = "";
    toast(error.message);
  }
}

async function demoScan(itemId) {
  const item = state.items.find((entry) => entry.id === itemId);
  if (!item) return;
  openScan();
  try {
    const response = await fetch(item.registered_photo_url);
    const blob = await response.blob();
    await submitScan([new File([blob], "sample-belonging.jpg", { type: blob.type || "image/jpeg" })]);
  } catch (error) {
    toast(error.message || "Could not load that sample scan.");
  }
}

function renderMatches(result) {
  const matches = result.matches || [];
  const matchHtml = matches.length ? matches.map((item, index) => {
    const scores = item.scores;
    const best = index === 0;
    return `<article class="match-card ${best ? "best" : ""}">
      <div class="match-card-head"><img src="${escapeHtml(item.registered_photo_url)}" alt="${escapeHtml(item.label)}" /><div><strong>${escapeHtml(item.label)}</strong><small>${escapeHtml(item.category)} · ${escapeHtml(item.family_ref || "No room label")}${best ? " · Closest visual match" : ""}</small></div><div class="match-score">${scores.overall}%<small>SIMILAR</small></div></div>
      <div class="score-details">${[["Colour", scores.color], ["Shape", scores.shape], ["Pattern", scores.pattern]].map(([name, value]) => `<div class="score-detail"><span>${name}<b>${value}%</b></span><div class="score-track"><i style="width:${value}%"></i></div></div>`).join("")}</div>
      <button class="button ${best ? "button-lime" : "button-light"}" data-confirm-id="${escapeHtml(item.id)}">Confirm this match <span>↗</span></button>
    </article>`;
  }).join("") : `<div class="empty-inline">There aren’t any registered items to compare yet. You can still log this find for the team.</div>`;

  $("#match-results").innerHTML = `
    <div class="scan-result-header"><div><h3>A few familiar things?</h3><p>${result.views} ${result.views === 1 ? "view" : "views"} compared · suggestions for your team to check.</p></div><button id="scan-again">← Try another photo</button></div>
    <div class="scan-result-layout"><div><img class="scan-result-photo" src="${escapeHtml(result.photo_url)}" alt="Scanned belonging" /><div class="scan-detection"><span>VISUAL CUES</span><strong>${escapeHtml(result.features.dominant_color)} · ${escapeHtml(result.features.pattern_hint)}</strong></div></div>
    <div class="matches-column"><p class="match-note">Scores compare colour, silhouette and pattern against registered photos. They are clues, not a decision.</p>${matchHtml}
    <div class="no-match-box"><span class="no-match-icon">＋</span><div><strong>None of these look right?</strong><small>Keep a record for someone to identify later.</small></div><button id="show-log-new">Log as found</button></div>
    <form id="log-new-form" class="log-new-form" hidden></form></div></div>`;
  $("#match-results").hidden = false;
  $$('[data-confirm-id]').forEach((button) => button.addEventListener("click", () => confirmMatch(button.dataset.confirmId)));
  $("#scan-again").addEventListener("click", () => {
    $("#match-results").hidden = true;
    $("#match-results").innerHTML = "";
    $("#scan-content").hidden = false;
    $("#capture-empty").hidden = false;
    $("#scan-preview").hidden = true;
  });
  $("#show-log-new").addEventListener("click", showLogNewForm);
}

function showLogNewForm() {
  const form = $("#log-new-form");
  form.innerHTML = `<div class="new-found-fields"><label class="field-label">Item name<input name="label" placeholder="e.g. Small blue mitten" required maxlength="80" /></label><label class="field-label">Item type<select name="category"><option>Other</option><option>Bottle</option><option>Lunchbox</option><option>Clothing</option><option>Footwear</option><option>Toy</option><option>Bag</option></select></label><button class="button button-dark" type="submit">Add to pick-up shelf <span>↗</span></button></div>`;
  form.hidden = false;
  form.onsubmit = async (event) => {
    event.preventDefault();
    const body = new FormData(form);
    try {
      await api(`/api/scans/${state.scanId}/log-new`, { method: "POST", body });
      closeModal("scan-modal");
      await refresh();
      setPage("returns");
      toast("Added to the pick-up shelf for your team to identify.");
    } catch (error) { toast(error.message); }
  };
}

async function confirmMatch(itemId) {
  const body = new FormData();
  body.append("item_id", itemId);
  try {
    const item = await api(`/api/scans/${state.scanId}/confirm`, { method: "POST", body });
    closeModal("scan-modal");
    await refresh();
    setPage("returns");
    toast(`${item.label} is ready to return when the family arrives.`);
  } catch (error) { toast(error.message); }
}

async function markReturned(id) {
  try {
    const item = await api(`/api/items/${id}/return`, { method: "POST" });
    await refresh();
    toast(`${item.label} marked as returned. A little win!`);
  } catch (error) { toast(error.message); }
}

function bindEvents() {
  $$(".nav-link").forEach((button) => button.addEventListener("click", () => setPage(button.dataset.page)));
  $$('[data-page-link]').forEach((button) => button.addEventListener("click", () => setPage(button.dataset.pageLink)));
  ["#open-scan", "#hero-scan", "#returns-scan"].forEach((selector) => $(selector).addEventListener("click", openScan));
  $("#open-register").addEventListener("click", () => { $("#register-form").reset(); $("#register-file-label").textContent = "Add a photo"; openModal("register-modal"); });
  $$("[data-close]").forEach((button) => button.addEventListener("click", () => closeModal(button.dataset.close)));
  $$(".modal-backdrop").forEach((backdrop) => backdrop.addEventListener("click", (event) => { if (event.target === backdrop) closeModal(backdrop.id); }));
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") $$(".modal-backdrop.open").forEach((modal) => closeModal(modal.id)); });
  $("#take-photo").addEventListener("click", startCamera);
  $("#switch-camera").addEventListener("click", () => { state.facing = state.facing === "environment" ? "user" : "environment"; startCamera(); });
  $("#snap-photo").addEventListener("click", () => {
    const video = $("#camera-video");
    const canvas = $("#capture-canvas");
    if (!video.videoWidth) return toast("Camera is still getting ready. Try again in a moment.");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    canvas.toBlob(async (blob) => {
      if (!blob) return;
      state.capturedPhotos.push(new File([blob], `station-view-${state.capturedPhotos.length + 1}.jpg`, { type: "image/jpeg" }));
      if (state.capturedPhotos.length < 3) {
        $("#capture-overlay span").textContent = `ANGLE ${state.capturedPhotos.length + 1} OF 3 · ROTATE TRAY`;
        const shutter = $("#snap-photo");
        shutter.disabled = true;
        let rotated = false;
        try { rotated = (await api("/api/hardware/rotate", { method: "POST" })).rotated; } catch { /* A manual turntable remains usable offline. */ }
        shutter.disabled = false;
        toast(rotated ? `View ${state.capturedPhotos.length} saved. Tray advanced; take the next view.` : `View ${state.capturedPhotos.length} saved. Rotate the tray for the next angle.`);
      } else {
        submitScan(state.capturedPhotos);
      }
    }, "image/jpeg", .92);
  });
  $("#scan-file").addEventListener("change", (event) => submitScan([...event.target.files]));
  $("#register-file").addEventListener("change", (event) => { if (event.target.files[0]) $("#register-file-label").textContent = event.target.files[0].name; });
  $("#registry-search").addEventListener("input", renderRegistry);
  $$(".filter-pill").forEach((button) => button.addEventListener("click", () => {
    state.filter = button.dataset.filter;
    $$(".filter-pill").forEach((pill) => pill.classList.toggle("active", pill === button));
    renderRegistry();
  }));
  $("#register-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!$("#register-file").files[0]) return toast("Add a photo of the belonging before saving it.");
    const button = $("#save-register");
    button.disabled = true;
    button.textContent = "Saving…";
    try {
      await api("/api/items", { method: "POST", body: new FormData(event.currentTarget) });
      closeModal("register-modal");
      await refresh();
      setPage("registry");
      toast("Belonging added to the register.");
    } catch (error) { toast(error.message); }
    finally { button.disabled = false; button.innerHTML = "Save belonging <span>↗</span>"; }
  });
}

$("#today-label").textContent = new Intl.DateTimeFormat("en-IN", { weekday: "short", day: "numeric", month: "short", year: "numeric" }).format(new Date());
bindEvents();
const initialPage = ["registry", "returns"].includes(window.location.hash.slice(1)) ? window.location.hash.slice(1) : "overview";
setPage(initialPage);
refresh();
