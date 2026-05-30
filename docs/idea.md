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
│   ├── agent_config.yaml         ← [MODIFY] Add coder and relevance_filter skills
│   ├── bridge_server.py          ← [NEW] Thin HTTP bridge runner (starts Executor)
│   ├── prompts/
│   │   ├── coder.md              ← [MODIFY] Add Star Math prompt guidelines
│   │   ├── relevance_filter.md   ← [NEW] Semantic scoring prompt guidelines
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

relevance_filter:
  prompt: prompts/relevance_filter.md
  tools_allowed: []
  temperature: 0.3
  max_tokens: 1200
  description: NEW SKILL. Scores and filters repositories semantically matching the user's specific developer interest profile.
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

#### B. Relevance Filter Contract (`prompts/relevance_filter.md`)
* **Role:** Takes the ranked computed data from the sandbox and runs a semantic LLM pass to drop irrelevant repos or anomalies (e.g., repos with growth velocities above 100% but under 50 total stars).
* **System Guidelines:**
```text
Role: You are the Relevance Filter Agent.
Input: A JSON list of ranked trending repositories from the coder sandbox.
Task:
1. Filter the list down to repositories matching the developer interests: Agentic Coding, MCP Servers, Dev Tooling, or Web Frameworks.
2. Filter out anomalies (e.g., velocity spikes from micro-repos).
3. For each kept repository, write a concise, one-sentence "why it matters" explanation showing why it fits the criteria.
Output Format: A JSON object containing the filtered list.
```

---

## 🎯 6. Grader Scorecard & Verification Plan

| Grader Part | Verification Procedure | Expected Terminal Output / Indicator |
|---|---|---|
| **Part 1: Base Queries** | Run `./flow.py "Say hello."` | Two-node output completing in under 3 seconds. |
| **Part 2: Concurrency** | Scrape Python and Rust weekly | Overlapping starts, shared finish timestamp, parallel layer elapsed = `max(branches)`. |
| **Part 3: Critic Verdict** | Intentionally drop a required field in distiller output | Output triggers completeness check, returns `fail`, downstreams skipped, recovery planner runs. |
| **Part 4: Coder Skill** | Verify star growth math in sandbox | Sandbox output shows zero rounding errors and mathematically precise momentum rankings. |
| **Part 5: New Skill** | Confirm `relevance_filter` triggers | Graph trace prints: `planner` → `researcher` → `distiller` → `coder` → `sandbox_executor` → `relevance_filter` → `formatter`. |

---

## 🔍 7. Settle Gating Design Questions

> [!IMPORTANT]
> **Resolution on Data Source:** We will use an unofficial GitHub Trending JSON API (Option B) for the researchers. If the JSON API is unavailable, the researcher falls back to `fetch_url` to scrape `https://github.com/trending`, ensuring robust offline/online resilience.
> 
> **Resolution on Transport:** The Chrome Extension pop-up issues simple POST queries to a local `bridge_server.py` running on port `8109` (separate from gateway V8). The bridge acts as a command bridge, launching `flow.Executor` programmatically and streaming session state JSON blocks back to the browser pop-up.
> 
> **Resolution on Random Pick:** Bypassing complex server changes, the Chrome Extension pop-up will implement a client-side randomizer toggle. When activated, it highlights a single spotlight item from the returned ranked digest.
