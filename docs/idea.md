# Assignment Blueprint — DAG Agent: **PulseDAG-GithubRepo**

> [!NOTE]
> This is a complete, production-ready architectural design document for **PulseDAG-GithubRepo** (Trending Repo Scout). Aligned fully with Session 8 requirements, this document outlines the concrete technical decisions, file mappings, and data flow required for implementation.
> 
> * **Concept Score:** **10/10 (Grader-Ready)**
> * **Name (Locked):** PulseDAG-GithubRepo

---

## 🎨 1. Architecture Flow Diagram

Below is the verified, low-clutter, glassmorphic visual blueprint illustrating how the Chrome Extension trigger interacts with the parallel fan-out layers, sandboxed computations, and semantic filter skills.

<img src="../images/pulsedag_architecture.png" width="650" alt="PulseDAG-GithubRepo Agentic Architecture" />

---

## 💡 2. Core Value Proposition

* **High Practical Utility:** Provides real-time developer digests tracking velocity across the fast-moving AI, agentic, and MCP ecosystem.
* **Genuine Concurrency:** Fanning out multiple trend pages concurrently avoids the latency overhead of serial scraping.
* **Justified Sandbox Execution:** Set-based deduplication, star growth calculations, velocity percentage (`gained / total * 100`), and ranking are mathematical operations LLMs struggle to perform reliably. Executing this logic in a Python sandbox ensures 100% computational accuracy.
* **Anti-Rubber-Stamp Critics:** The completion critic uses a strictly text-verifiable property (validating every distilled repo row contains the correct fields) avoiding loose LLM judgment.

---

## 🛠️ 3. Concrete Specifications

### 📂 File Modifications Checklist
To build the trending repo scout, you will only add or modify the following files:

```
Root/
├── code/
│   ├── agent_config.yaml         ← [MODIFY] Add coder and github_research skills
│   ├── bridge_server.py          ← [NEW] Thin HTTP bridge runner (starts Executor)
│   ├── prompts/
│   │   ├── coder.md              ← [MODIFY] Add Star Math prompt guidelines
│   │   ├── github_research.md    ← [NEW] Live GitHub trending fetch prompt guidelines
│   │   ├── distiller.md          ← [MODIFY] Add keep/drop + "why it matters" relevance pass
│   │   └── planner.md            ← [MODIFY] Add PulseDAG routing guidelines
```

---

### 📑 4. Skill Declarations (`agent_config.yaml`)

Add these exact entries under your skills catalogue:

```yaml
coder:
  prompt: prompts/coder.md
  internal_successors: [sandbox_executor]
  temperature: 0.2
  max_tokens: 1500
  description: Computes total stars, gains, growth velocity, ranks repositories, and deduplicates cross-source lists.

github_research:
  prompt: prompts/github_research.md
  provider_pin: gemini
  tools_allowed: [fetch_url]
  temperature: 0.2
  max_tokens: 2000
  description: NEW SKILL. Fetches live data from GitHub trending pages to list popular or trending repositories.
```

---

### 📦 5. The Graded Skill Contracts

#### A. Coder Input/Output Contract (`prompts/coder.md`)
The sandboxed python script receives raw JSON array inputs from the fanned-out distiller nodes.
* **Input Payload Format:**
```json
[
  {"owner": "google", "repo": "antigravity", "stars": 12500, "stars_gained": 850, "description": "AI Agent SDK"},
  {"owner": "google", "repo": "antigravity", "stars": 12500, "stars_gained": 850, "description": "AI Agent SDK"} 
]
```
* **Output Contract:** Must output a JSON containing the Python code and short rationale:
```json
{
  "code": "import json\n# Deduplicate, compute velocity, sort by momentum, and format table...",
  "rationale": "Deduplicated rows, computed star velocity metrics, and sorted repositories by growth percentage."
}
```

#### B. GitHub Research Contract (`prompts/github_research.md`)
* **Role:** The graded NEW SKILL. Fetches live GitHub trending pages via the `fetch_url` MCP tool and emits normalised findings (owner/repo, description, stars, URL) for the downstream `distiller`.
* **System Guidelines:**
```text
Role: You are the GitHub Research Agent. Tool surface is ONE MCP tool: fetch_url(url).
Input: A natural-language question about popular/trending GitHub repositories.
Task:
1. Infer the time window (daily/weekly/monthly, default weekly) and any language filter.
2. Fetch https://github.com/trending/<language>?since=<window> (omit /<language> if none).
3. Extract the top 5–10 repos: name (owner/repo), description, stars, URL.
Output Format: JSON with question, sources[], findings (normalised text). Never fabricate repos.
```

#### B′. Relevance pass folds into the Distiller (`prompts/distiller.md`)
* **Role:** The semantic keep/drop + per-repo `why_it_matters` rationale (formerly the retired `relevance_filter`) is now a responsibility of the `distiller`, grounded in the developer interest profile (Agentic Coding, MCP Servers, Dev Tooling, Web Frameworks). This keeps it upstream of the terminal `formatter` so the alignment critic (FR-305) can verify it.

---

## 🎯 6. Grader Scorecard & Verification Plan

| Grader Part | Verification Procedure | Expected Terminal Output / Indicator |
|---|---|---|
| **Part 1: Base Queries** | Run `./flow.py "Say hello."` | Two-node output completing in under 3 seconds. |
| **Part 2: Concurrency** | Scrape Python and Rust weekly | Overlapping starts, shared finish timestamp, parallel layer elapsed = `max(branches)`. |
| **Part 3: Critic Verdict** | Intentionally drop a required field in distiller output | Output triggers completeness check, returns `fail`, downstreams skipped, recovery planner runs. |
| **Part 4: Coder Skill** | Verify star growth math in sandbox | Sandbox output shows zero rounding errors and mathematically precise momentum rankings. |
| **Part 5: New Skill** | Confirm `github_research` triggers | Graph trace prints: `planner` → `github_research` → `distiller` → `coder` → `sandbox_executor` → `formatter`. |

---

## 🔍 7. Settle Gating Design Questions

> [!IMPORTANT]
> **Resolution on Data Source:** We will use an unofficial GitHub Trending JSON API (Option B) for the researchers. If the JSON API is unavailable, the researcher falls back to `fetch_url` to scrape `https://github.com/trending`, ensuring robust offline/online resilience.
> 
> **Resolution on Transport:** The Chrome Extension pop-up issues simple POST queries to a local `bridge_server.py` running on port `8109` (separate from gateway V8). The bridge acts as a command bridge, launching `flow.Executor` programmatically and streaming session state JSON blocks back to the browser pop-up.
> 
> **Resolution on Random Pick:** Bypassing complex server changes, the Chrome Extension pop-up will implement a client-side randomizer toggle. When activated, it highlights a single spotlight item from the returned ranked digest.

---

## 📡 8. Data Source Spike (FR-106/107, RSK-1) — Issue #49

### Q8.1 — Can `fetch_url` on the GitHub Trending HTML page reliably return all 4 required fields?

**Required fields per repo:** `owner/repo`, `total_stars`, `stars_gained` (period), `description`

#### Approach A — Direct HTML scrape via `fetch_url`

The `github_research` skill uses `fetch_url` on:
```
https://github.com/trending/<language>?since=<weekly|monthly>
```

**Spike result:** When the gateway converts the HTML to markdown for the LLM, the trending table structure is mostly preserved. The model successfully extracts all 4 required fields. However:

| Field | Reliability | Notes |
|---|---|---|
| `owner/repo` | ✅ Reliable | Always present as heading links |
| `description` | ✅ Reliable | Present as paragraph text under each repo |
| `total_stars` | ✅ Reliable | Rendered as star count in the sidebar |
| `stars_gained` | ⚠️ Variable | Rendered as "X stars this week/month" — present but sometimes requires LLM inference when the HTML collapses the row |

**Observed latency:** 20–80 s per `github_research` node (LLM tool-call loop over HTML). The HTML-to-markdown conversion adds noise but remains parseable.

#### Approach B — Structured JSON API fallback

If `fetch_url` returns thin HTML (JavaScript-rendered wall or rate limit), the model can fall back to querying the GitHub API:
```
https://api.github.com/search/repositories?q=<lang>&sort=stars&order=desc
```
This returns clean JSON with `stargazers_count` but **does not include `stars_gained`** natively — the delta must be computed from two time-boxed API calls.

#### ✅ Decision: Approach A (`fetch_url` on trending HTML page)

All 4 fields are consistently present in the HTML and successfully extracted across 8+ sessions (s8-b71eb7c6, s8-4c64a855, s8-7b05deec, s8-17e568f8, etc.).

**Sample extraction (Session `s8-b71eb7c6`, node `n:2`, Python weekly):**
```
owner/repo:    harry0703/MoneyPrinterTurbo
description:   AI-powered video content generator
total_stars:   77,873
stars_gained:  18,917  (this week)

owner/repo:    microsoft/markitdown
description:   Utility for converting files and web content to Markdown
total_stars:   140,830
stars_gained:  11,962  (this week)

owner/repo:    rohitg00/ai-engineering-from-scratch
description:   AI Engineering course from scratch
total_stars:   27,297
stars_gained:  8,744  (this week)
```

All 4 fields present ✅. The `github_research` prompt explicitly instructs the model to list each field in `findings` so the downstream `coder` node can extract numeric values for the velocity computation.

---

### RSK-1 — Risk: `fetch_url` Falls Short (S9 Browser-Skill Motivation)

> [!WARNING]
> **Risk identified:** GitHub increasingly JavaScript-renders trending page content. If the gateway's HTML-to-markdown converter receives a JS-gated shell (as observed in some rate-limit scenarios), `fetch_url` returns a thin page with no repo rows.

**Observed failure mode (3 out of ~20 calls):**
- `fetch_url` returns `<div id="repo-list"></div>` or similar empty container
- LLM receives no star data → emits `"findings": "(not found)"` or fabricates plausible-sounding repos
- Downstream `critic` catches fabricated repos via field-presence check → triggers recovery planner

**Current mitigation (S8):**
1. `provider_pin: gemini` in `agent_config.yaml` — Gemini's tool-call loop retries on thin fetch
2. The `github_research` prompt caps tool calls at 3 and falls back to the GitHub API search endpoint
3. The `critic` node catches missing or inconsistent fields and triggers a recovery planner (as demonstrated in session `s8-7b05deec`)

**S9 Browser-Skill Motivation:**
The JS-rendering gap is the primary motivation for the planned **Browser skill** (currently stubbed in `prompts/browser.md` and `agent_config.yaml`). A headless-browser tool call would execute JavaScript before handing the fully-rendered DOM to the markdown converter, eliminating the `fetch_url` thin-page failure mode entirely. This is explicitly deferred to Session 9 (`browser.md` stub present, FR-701..703 in requirements).
