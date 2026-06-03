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
function getWindowValue() {
  const activeChip = $("#window-chips .chip.on");
  return activeChip ? activeChip.getAttribute("data-value") : "weekly";
}
function setWindowActiveChip(val) {
  document.querySelectorAll("#window-chips .chip").forEach(chip => {
    if (chip.getAttribute("data-value") === val) {
      chip.classList.add("on");
    } else {
      chip.classList.remove("on");
    }
  });
}
function savePrefs() {
  localStorage.setItem(STORE_KEY, JSON.stringify({
    langs: [...selectedLangs],
    window: getWindowValue(),
    mode: $("#mode").value,
  }));
}

const selectedLangs = new Set(prefs.langs?.length ? prefs.langs : ["Python"]);

// ── Custom Multiselect Component ─────────────────────────────────────
function renderMultiselect() {
  const selectedTagsContainer = $("#selected-tags");
  const dropdown = $("#multiselect-dropdown");
  const searchInput = $("#multiselect-search");
  
  // Render tags
  selectedTagsContainer.innerHTML = "";
  for (const lang of selectedLangs) {
    const tag = document.createElement("div");
    tag.className = "tag";
    tag.textContent = lang;
    
    const removeBtn = document.createElement("span");
    removeBtn.className = "tag-remove";
    removeBtn.textContent = "×";
    removeBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      if (selectedLangs.size > 1) {
        selectedLangs.delete(lang);
        renderMultiselect();
        savePrefs();
      }
    });
    
    tag.appendChild(removeBtn);
    selectedTagsContainer.appendChild(tag);
  }
  
  // Update input placeholder based on selected items
  if (selectedLangs.size > 0) {
    searchInput.placeholder = "";
  } else {
    searchInput.placeholder = "Select languages...";
  }

  // Render options in dropdown based on search query
  const query = searchInput.value.trim().toLowerCase();
  dropdown.innerHTML = "";
  
  let matches = 0;
  for (const lang of LANGUAGES) {
    if (query && !lang.toLowerCase().includes(query)) {
      continue;
    }
    matches++;
    
    const item = document.createElement("div");
    item.className = "dropdown-item" + (selectedLangs.has(lang) ? " selected" : "");
    item.innerHTML = `<span>${lang}</span><span class="dropdown-item-check">✓</span>`;
    
    item.addEventListener("click", (e) => {
      e.stopPropagation();
      if (selectedLangs.has(lang)) {
        if (selectedLangs.size > 1) {
          selectedLangs.delete(lang);
        }
      } else {
        selectedLangs.add(lang);
      }
      // Clear search but keep open and focused
      searchInput.value = "";
      searchInput.style.width = "40px";
      renderMultiselect();
      savePrefs();
      searchInput.focus();
    });
    
    dropdown.appendChild(item);
  }
  
  if (matches === 0) {
    const noResults = document.createElement("div");
    noResults.className = "dropdown-item";
    noResults.style.cursor = "default";
    noResults.style.color = "var(--faint)";
    noResults.textContent = "No results found";
    dropdown.appendChild(noResults);
  }
}

function setupMultiselectEvents() {
  const container = $("#multiselect-container");
  const searchInput = $("#multiselect-search");
  const inputEl = $("#multiselect-input");
  
  // Click on the multiselect area focuses search and opens dropdown
  inputEl.addEventListener("click", (e) => {
    container.classList.add("open");
    $("#multiselect-dropdown").classList.remove("hidden");
    searchInput.focus();
  });
  
  // Filter on input type
  searchInput.addEventListener("input", () => {
    searchInput.style.width = Math.max(40, searchInput.value.length * 8 + 10) + "px";
    renderMultiselect();
  });
  
  // Prevent click on search input from bubbling
  searchInput.addEventListener("click", (e) => {
    e.stopPropagation();
  });

  // Close dropdown on click outside
  document.addEventListener("click", (e) => {
    if (!container.contains(e.target)) {
      container.classList.remove("open");
      $("#multiselect-dropdown").classList.add("hidden");
      searchInput.value = "";
      searchInput.style.width = "40px";
      renderMultiselect();
    }
  });
}

// ── Copy to Clipboard ────────────────────────────────────────────────
async function copyToClipboard(text, el) {
  try {
    await navigator.clipboard.writeText(text);
    el.classList.add("copied");
    setTimeout(() => el.classList.remove("copied"), 1500);
  } catch (err) {
    console.error("Failed to copy text: ", err);
  }
}

function setupCopyEvents() {
  document.addEventListener("click", (e) => {
    const copyable = e.target.closest(".copyable-command");
    if (copyable) {
      const text = copyable.textContent.trim();
      copyToClipboard(text, copyable);
    }
  });
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
  
  // Inject steps-progress container
  digest.innerHTML = '<div id="steps-progress" class="steps-progress"></div>';
    
  runBtn.disabled = true;
  runBtn.textContent = "Running…";

  // Reset run timers
  const t0 = performance.now();
  clearRunTimers();

  const sessionId = "s8-" + Math.random().toString(16).slice(2, 10);
  const body = {
    languages: [...selectedLangs].map((l) => l.toLowerCase()),
    window: getWindowValue(),
    mode: $("#mode").value.trim() || undefined,
    session_id: sessionId,
  };

  // Set up polling loop
  const pollStatus = async () => {
    try {
      const r = await fetch(`${BRIDGE}/session/${sessionId}`);
      if (!r.ok) return;
      const data = await r.json();
      if (data && data.nodes) {
        renderStepsProgress(data.nodes);
      }
    } catch (err) {
      console.error("Error polling session:", err);
    }
  };
  
  // Run once immediately, then start interval
  pollStatus();
  runTimers.push(setInterval(pollStatus, 500));

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
    $("#result-meta").textContent = `${data.session_id} · ${secs}s`;
    renderDigest(data.answer || "(empty digest)");
  } catch (e) {
    clearRunTimers();
    const offline = String(e).includes("Failed to fetch");
    if (offline) {
      setStatus("Bridge <strong>offline</strong>", "down");
    }
    
    const errorMsg = offline 
      ? `Could not reach the bridge on :8109. Start it using <code class="copyable-command" title="Click to copy">uv run python bridge_server.py</code>`
      : e.message;
      
    digest.innerHTML = `<p class="err">⚠ <span>${errorMsg}</span></p>`;
  } finally {
    runBtn.disabled = false;
    runBtn.textContent = "▶ Run";
  }
}

// ── Minimal, safe markdown render ────────────────────────────────────
function renderDigest(text) {
  const digest = $("#digest");
  digest.classList.remove("has-carousel");
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
  initCarousel();
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
  const digest = $("#digest");
  const slides = [...digest.querySelectorAll("li.line")];
  if (!slides.length) return;
  
  document.querySelectorAll(".digest .picked").forEach((el) => el.classList.remove("picked"));
  
  const choiceIdx = Math.floor(Math.random() * slides.length);
  const choice = slides[choiceIdx];
  choice.classList.add("picked");
  
  showSlide(choiceIdx);
  choice.scrollIntoView({ behavior: "smooth", block: "center" });
}

let currentSlideIndex = 0;

function initCarousel() {
  const digest = $("#digest");
  const slides = [...digest.querySelectorAll("li.line")];
  if (slides.length <= 1) return;

  digest.classList.add("has-carousel");
  currentSlideIndex = 0;
  
  slides.forEach((slide, idx) => {
    if (idx === 0) {
      slide.classList.add("active");
    } else {
      slide.classList.remove("active");
    }
  });

  const dotsContainer = document.createElement("div");
  dotsContainer.className = "carousel-dots";

  slides.forEach((_, idx) => {
    const dot = document.createElement("div");
    dot.className = "carousel-dot" + (idx === 0 ? " active" : "");
    dot.addEventListener("click", () => {
      showSlide(idx);
    });
    dotsContainer.appendChild(dot);
  });

  digest.appendChild(dotsContainer);
}

function showSlide(index) {
  const digest = $("#digest");
  const slides = [...digest.querySelectorAll("li.line")];
  const dots = [...digest.querySelectorAll(".carousel-dot")];
  if (index < 0 || index >= slides.length) return;

  slides[currentSlideIndex].classList.remove("active");
  dots[currentSlideIndex].classList.remove("active");

  currentSlideIndex = index;

  slides[currentSlideIndex].classList.add("active");
  dots[currentSlideIndex].classList.add("active");
}

// ── Wire up ──────────────────────────────────────────────────────────
// ── Render Steps Progress ───────────────────────────────────────────
function renderStepsProgress(nodes) {
  const container = $("#steps-progress");
  if (!container) return;

  if (!nodes || nodes.length === 0) {
    container.innerHTML = "";
    return;
  }

  // Sort nodes by numeric ID suffix (n:1, n:2, etc.)
  const sortedNodes = [...nodes].sort((a, b) => {
    const numA = parseInt(a.node_id.split(":")[1]) || 0;
    const numB = parseInt(b.node_id.split(":")[1]) || 0;
    return numA - numB;
  });

  container.innerHTML = sortedNodes
    .map((node) => {
      let statusClass = "step-pending";
      let statusSymbol = "○";

      if (node.status === "complete") {
        statusClass = "step-complete";
        statusSymbol = "✓";
      } else if (node.status === "running") {
        statusClass = "step-running";
        statusSymbol = '<span class="step-spinner"></span>';
      } else if (node.status === "failed") {
        statusClass = "step-failed";
        statusSymbol = "✗";
      } else if (node.status === "skipped") {
        statusClass = "step-skipped";
        statusSymbol = "—";
      }

      const timeStr = node.elapsed_s ? `${node.elapsed_s.toFixed(1)}s` : "";
      const errorStr = node.error
        ? `<span class="step-error-desc" title="${escapeHtml(node.error)}">${escapeHtml(
            node.error.slice(0, 32)
          )}${node.error.length > 32 ? "..." : ""}</span>`
        : "";

      const displayName = node.skill.replace(/_/g, " ");

      return `
        <div class="step-item ${statusClass}">
          <span class="step-status">${statusSymbol}</span>
          <span class="step-name">${escapeHtml(displayName)}</span>
          ${errorStr}
          <span class="step-time">${timeStr}</span>
        </div>
      `;
    })
    .join("");
}

// ── Wire up ──────────────────────────────────────────────────────────
function init() {
  renderMultiselect();
  setupMultiselectEvents();
  setupCopyEvents();
  
  if (prefs.window) {
    setWindowActiveChip(prefs.window);
  }
  if (prefs.mode) $("#mode").value = prefs.mode;

  // Add click handlers for window chips
  document.querySelectorAll("#window-chips .chip").forEach(chip => {
    chip.addEventListener("click", () => {
      setWindowActiveChip(chip.getAttribute("data-value"));
      savePrefs();
    });
  });

  $("#mode").addEventListener("input", savePrefs);
  $("#run").addEventListener("click", run);
  $("#dice").addEventListener("click", randomPick);

  checkHealth();
}

document.addEventListener("DOMContentLoaded", init);
