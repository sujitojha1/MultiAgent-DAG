// Runs the REAL popup.js in a stubbed DOM to verify renderDigest + randomPick
// (FR-703). No browser needed.  Run:  node test_popup_logic.mjs
import { readFileSync } from "node:fs";
import vm from "node:vm";

const all = []; // registry of every created element

class El {
  constructor(tag) {
    this.tagName = tag.toUpperCase();
    this.className = "";
    this.children = [];
    this.parent = null;
    this._text = "";
    this._handlers = {};
    all.push(this);
  }
  set innerHTML(html) {
    if (html === "") { this.children = []; this._text = ""; return; }
    this._text = String(html).replace(/<[^>]+>/g, "")
      .replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">");
  }
  get textContent() {
    if (this.children.length) return this.children.map((c) => c.textContent).join(" ");
    return this._text;
  }
  set textContent(v) { this._text = v; this.children = []; }
  appendChild(c) { c.parent = this; this.children.push(c); return c; }
  addEventListener(ev, fn) { this._handlers[ev] = fn; }
  get classList() {
    const self = this;
    return {
      add: (c) => { if (!self._classes().includes(c)) self.className = (self.className + " " + c).trim(); },
      remove: (c) => { self.className = self._classes().filter((x) => x !== c).join(" "); },
      contains: (c) => self._classes().includes(c),
    };
  }
  _classes() { return this.className.split(/\s+/).filter(Boolean); }
  scrollIntoView() {}
  matchesClassChain(chain) {
    // chain: ['digest','pick-target'] — el has last class & some ancestor has each prior
    if (!this._classes().includes(chain[chain.length - 1])) return false;
    let need = chain.slice(0, -1), node = this.parent;
    let i = need.length - 1;
    while (node && i >= 0) {
      if (node._classes().includes(need[i])) i--;
      node = node.parent;
    }
    return i < 0;
  }
}

const digest = new El("div");
digest.className = "digest";

const stubEls = {
  "#digest": digest,
  "#result": new El("section"),
  "#empty": new El("section"),
  "#result-meta": new El("span"),
  "#run": new El("button"),
  "#dice": new El("button"),
  "#window": Object.assign(new El("select"), { value: "weekly" }),
  "#mode": Object.assign(new El("input"), { value: "" }),
  "#lang-chips": new El("div"),
  "#status-dot": new El("span"),
};

function queryAll(sel) {
  const chain = sel.split(/\s+/).map((s) => s.replace(/^\./, ""));
  return all.filter((el) => el.matchesClassChain(chain));
}

const document = {
  querySelector: (sel) => stubEls[sel] ?? null,
  querySelectorAll: (sel) => queryAll(sel),
  createElement: (t) => new El(t),
  addEventListener: () => {},
};

const sandbox = {
  document,
  localStorage: { getItem: () => null, setItem: () => {} },
  performance: { now: () => 0 },
  fetch: async () => ({ ok: true, json: async () => ({ status: "ok" }) }),
  Math, JSON, console, Set, Array, performance: { now: () => 0 },
};
sandbox.window = sandbox;

const code = readFileSync(new URL("./popup.js", import.meta.url), "utf8");
vm.createContext(sandbox);
vm.runInContext(code, sandbox);

// ── Exercise renderDigest with a realistic digest ──
const DIGEST = `# Trending Python & Rust — this week

1. [astral-sh/ty](https://github.com/astral-sh/ty) — type checker; momentum 9.4
2. [BerriAI/litellm](https://github.com/BerriAI/litellm) — agentic gateway; momentum 8.7
- ruff now formats notebooks — relevant to dev-tooling`;

sandbox.renderDigest(DIGEST);

const targets = queryAll(".digest .pick-target");
const headings = digest.children.filter((c) => c.tagName === "H2" || c.tagName === "H3");
const liCount = digest.children
  .filter((c) => c.tagName === "UL")
  .reduce((n, ul) => n + ul.children.length, 0);

console.log(`heading rendered : ${headings.length}  (expect 1)`);
console.log(`list items       : ${liCount}  (expect 3)`);
console.log(`pick-targets     : ${targets.length}  (expect 3)`);

let fail = 0;
if (headings.length !== 1) fail++;
if (liCount !== 3) fail++;
if (targets.length !== 3) fail++;

// link rendering inside a list item
const firstLi = digest.children.find((c) => c.tagName === "UL").children[0];
if (!firstLi._text.includes("astral-sh/ty")) { console.log("FAIL: link label missing"); fail++; }

// ── randomPick highlights exactly one target ──
sandbox.randomPick();
const picked = queryAll(".digest .picked");
console.log(`picked after 🎲  : ${picked.length}  (expect 1)`);
if (picked.length !== 1) fail++;

// picking again moves the highlight (still exactly one)
sandbox.randomPick();
const picked2 = queryAll(".digest .picked");
if (picked2.length !== 1) { console.log("FAIL: more than one picked after re-roll"); fail++; }

console.log(fail === 0 ? "\nALL POPUP-LOGIC CHECKS PASSED" : `\n${fail} CHECK(S) FAILED`);
process.exit(fail === 0 ? 0 : 1);
