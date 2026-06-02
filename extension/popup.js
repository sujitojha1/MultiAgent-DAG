// PulseDAG popup — FR-701 (controls) + FR-703 (random pick).
// Calls the HTTP bridge (Issue #51) on localhost:8109 and renders the digest.

const BRIDGE = "http://localhost:8109";
const LANGUAGES = ["Python", "Rust", "Go", "JavaScript", "TypeScript", "C++", "Java", "Zig"];
const STORE_KEY = "pulsedag.prefs";

const $ = (sel) => document.querySelector(sel);

// ── Status note ──────────────────────────────────────────────────────
// kind: "ok" | "down" | "busy" | "unknown"
function setStatus(html, kind = "unknown") {
  $("#status-dot").className = "dot dot-" + kind;
  $("#status-text").innerHTML = html;
}

// ── State / preferences ──────────────────────────────────────────────
const prefs = loadPrefs();

function loadPrefs() {
  try {
    return JSON.parse(localStorage.getItem(STORE_KEY)) || {};
  } catch {
    return {};
  }
}
function savePrefs() {
  localStorage.setItem(STORE_KEY, JSON.stringify({
    langs: [...selectedLangs],
    window: $("#window").value,
    mode: $("#mode").value,
  }));
}

const selectedLangs = new Set(prefs.langs?.length ? prefs.langs : ["Python"]);

// ── Build language chips ─────────────────────────────────────────────
function renderChips() {
  const box = $("#lang-chips");
  box.innerHTML = "";
  for (const lang of LANGUAGES) {
    const el = document.createElement("span");
    el.className = "chip" + (selectedLangs.has(lang) ? " on" : "");
    el.textContent = lang;
    el.addEventListener("click", () => {
      if (selectedLangs.has(lang)) selectedLangs.delete(lang);
      else selectedLangs.add(lang);
      if (selectedLangs.size === 0) selectedLangs.add(lang); // keep ≥1
      renderChips();
      savePrefs();
    });
    box.appendChild(el);
  }
}

// ── Health check → status note ───────────────────────────────────────
async function checkHealth() {
  try {
    const r = await fetch(`${BRIDGE}/health`, { method: "GET" });
    const ok = r.ok && (await r.json()).status === "ok";
    if (ok) setStatus("Bridge <strong>online</strong> on :8109", "ok");
    else setStatus("Bridge responded with an error", "down");
  } catch {
    setStatus("Bridge <strong>offline</strong> — start it on :8109", "down");
  }
}

// ── Run ──────────────────────────────────────────────────────────────
const PHASES = [
  "Connecting to the bridge…",
  "Spinning up the DAG…",
  "Scanning GitHub trending…",
  "Ranking repos by momentum…",
  "Distilling the digest…",
];
let runTimers = [];
function clearRunTimers() { runTimers.forEach(clearInterval); runTimers.forEach(clearTimeout); runTimers = []; }

async function run() {
  const runBtn = $("#run");
  const result = $("#result");
  const digest = $("#digest");

  $("#empty").classList.add("hidden");
  result.classList.remove("hidden");
  $("#result-meta").textContent = "";
  digest.innerHTML =
    '<div class="loader"><div class="spinner"></div><div class="loader-text" id="loader-text">Spinning up the DAG…</div></div>';
  runBtn.disabled = true;
  runBtn.textContent = "Running…";

  // Live status note: busy dot + elapsed timer + cycling phase labels.
  const t0 = performance.now();
  setStatus("<strong>Running</strong> PulseDAG…", "busy");
  clearRunTimers();
  runTimers.push(setInterval(() => {
    $("#status-elapsed").textContent = ((performance.now() - t0) / 1000).toFixed(1) + "s";
  }, 100));
  let phase = 0;
  const loaderText = () => $("#loader-text");
  if (loaderText()) loaderText().textContent = PHASES[0];
  runTimers.push(setInterval(() => {
    phase = Math.min(phase + 1, PHASES.length - 1);
    if (loaderText()) loaderText().textContent = PHASES[phase];
  }, 1400));

  const body = {
    languages: [...selectedLangs].map((l) => l.toLowerCase()),
    window: $("#window").value,
    mode: $("#mode").value.trim() || undefined,
  };

  try {
    const r = await fetch(`${BRIDGE}/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);

    const secs = ((performance.now() - t0) / 1000).toFixed(1);
    clearRunTimers();
    $("#status-elapsed").textContent = "";
    setStatus(`Done · <strong>${escapeHtml(data.session_id || "session")}</strong>`, "ok");
    $("#result-meta").textContent = `${data.session_id} · ${secs}s`;
    renderDigest(data.answer || "(empty digest)");
  } catch (e) {
    clearRunTimers();
    $("#status-elapsed").textContent = "";
    const offline = String(e).includes("Failed to fetch");
    setStatus(offline ? "Bridge <strong>offline</strong> — start it on :8109" : "Run failed", "down");
    digest.innerHTML =
      `<p class="err">⚠ <span>${escapeHtml(offline ? "Could not reach the bridge on :8109. Is bridge_server.py running?" : e.message)}</span></p>`;
  } finally {
    runBtn.disabled = false;
    runBtn.textContent = "▶ Run PulseDAG";
  }
}

// ── Minimal, safe markdown render ────────────────────────────────────
function renderDigest(text) {
  const digest = $("#digest");
  digest.innerHTML = "";
  const lines = text.replace(/\r/g, "").split("\n");
  let ul = null;

  const closeList = () => { if (ul) { digest.appendChild(ul); ul = null; } };

  for (const raw of lines) {
    const line = raw.trimEnd();
    if (!line.trim()) { closeList(); continue; }

    const h = line.match(/^(#{1,6})\s+(.*)$/);
    const li = line.match(/^\s*(?:[-*•]|\d+[.)])\s+(.*)$/);

    if (h) {
      closeList();
      const el = document.createElement(h[1].length <= 2 ? "h2" : "h3");
      el.innerHTML = inline(h[2]);
      digest.appendChild(el);
    } else if (li) {
      if (!ul) ul = document.createElement("ul");
      const el = document.createElement("li");
      el.className = "line pick-target";
      el.innerHTML = inline(li[1]);
      ul.appendChild(el);
    } else {
      closeList();
      const el = document.createElement("p");
      el.className = "line pick-target";
      el.innerHTML = inline(line);
      digest.appendChild(el);
    }
  }
  closeList();
}

function inline(s) {
  let out = escapeHtml(s);
  // [label](url) and bare urls → links
  out = out.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
  out = out.replace(/(^|[\s(])((?:https?:\/\/)[^\s)]+)/g,
    '$1<a href="$2" target="_blank" rel="noreferrer">$2</a>');
  out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  out = out.replace(/`([^`]+)`/g, "<code>$1</code>");
  return out;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// ── 🎲 Random pick (FR-703) ──────────────────────────────────────────
function randomPick() {
  const targets = [...document.querySelectorAll(".digest .pick-target")]
    .filter((el) => el.textContent.trim().length > 8);
  if (!targets.length) return;
  document.querySelectorAll(".digest .picked").forEach((el) => el.classList.remove("picked"));
  const choice = targets[Math.floor(Math.random() * targets.length)];
  choice.classList.add("picked");
  choice.scrollIntoView({ behavior: "smooth", block: "center" });
}

// ── Wire up ──────────────────────────────────────────────────────────
function init() {
  renderChips();
  if (prefs.window) $("#window").value = prefs.window;
  if (prefs.mode) $("#mode").value = prefs.mode;

  $("#window").addEventListener("change", savePrefs);
  $("#mode").addEventListener("input", savePrefs);
  $("#run").addEventListener("click", run);
  $("#dice").addEventListener("click", randomPick);

  checkHealth();
}

document.addEventListener("DOMContentLoaded", init);
