# Class Notes — Session 8: Multi-Agent DAG Orchestration

> Running notes for quick reference. **Key Notes** below are the cheat-sheet; click a topic to jump to the detail.

---

## 🔑 Key Notes (TL;DR)

**DAG** = **D**irected (edges flow one way) · **A**cyclic (no cycles, never loops back) · **G**raph. → [details](#dag-directed-acyclic-graph)
- Replaces S7's sequential agent loop. Planner builds a graph; Executor runs every node whose predecessors are done. → [why](#why-a-graph-instead-of-a-sequential-loop)
- **Edges = context.** A node gets only its predecessors' outputs — not the whole history. → [props](#core-properties)
- **Independent nodes run in parallel** (`asyncio.gather`). Parallel-layer cost = **slowest branch, not the sum**. → [exec](#state--execution)
- **Graph is stateful; LLMs are stateless.** State persisted to JSON → resumable. NetworkX `DiGraph` + Kahn's algorithm. → [exec](#state--execution)
- **Dynamic, not fixed** — grows as nodes complete/fail; planner re-plans on failure. → [dynamic](#dynamic-not-fixed)
- Populations query: **125s→62s, 54k→17k tokens, 2.11× speedup.** Win is the *trace shape*, not raw speed. → [example](#the-classic-example-real-metrics-from-session-md)

**Skill** = **prompt + MCP tools + temperature** (a triple). Defined by 1 `.md` + 1 YAML entry; no Python per skill. → [details](#skills)
- Token savings come from **not carrying history forward**, *not* from skills themselves. → [gotchas](#-two-common-misunderstandings)
- NOT Claude-style lazy skills — whole prompt loads every time. → [gotchas](#-two-common-misunderstandings)
- Catalog: `planner, retriever, researcher, distiller, summariser, critic, formatter, sandbox_executor, coder, browser`. **coder** is the stub assignment. → [catalog](#catalog-session-8)

**Critic** = LLM that reads a node's output and emits `pass`/`fail`. On fail → child skipped + **one** planner re-plan (per-target cap). Generic critic *rubber-stamps* precise constraints (can't count) — fix = give it a tool. → [details](#critic-loop)

**Sandbox** = `subprocess.run` wrapper for Coder's Python. 30 s timeout, 1 MB out caps, fresh temp dir, **env whitelist** (only `PATH/HOME/LANG/LC_ALL/LC_CTYPE` pass — secrets dropped). Usability boundary, **not** security. → [details](#sandbox-environment)

**Other mechanisms:** recovery classifier · Gateway V8 · node-boundary resume. → [quick ref](#quick-reference-other-s8-mechanisms-from-session-md)

**Refs:** Wikipedia DAG · NetworkX topo-sort · asyncio docs. → [references](#references)

---

## DAG (Directed Acyclic Graph)

### What the letters mean
- **D — Directed**: every edge points one way (node A → node B), indicating a flow / dependency.
- **A — Acyclic**: **no directed cycles** — starting at any node and following the edges, you can never return to it. (In the video this is verbally garbled as "cyclic," but it means *a-cyclic* = **no cycle**.)
- **G — Graph**: nodes connected by edges.

> **Formal definition** ([Wikipedia](https://en.wikipedia.org/wiki/Directed_acyclic_graph)): a directed graph with no directed cycles. Key theorem: **DAGs are exactly the directed graphs that have a topological ordering** — a linear order where every edge u→v has u before v. This is what makes dependency-driven execution possible.

> **Project nuance — DiGraph with self-loop:** the code uses a NetworkX **DiGraph**. The video mentions a node calling *itself* for recovery/critic-retry. In the actual S8 implementation only the **planner** is re-invoked on failure (via a new recovery node); other nodes don't self-loop yet (deferred — e.g. formatter appending long reports). A self-loop is strictly a 1-cycle, so the "pure DAG" property holds for the inter-node structure the planner builds.

### Why a graph instead of a sequential loop
| Sequential (Session 7) | Graph / DAG (Session 8) |
|---|---|
| One step at a time | Independent nodes run **in parallel** |
| History grows every iteration → context bloat | Each node gets only the context it needs (its incoming edges) |
| A failure means re-run from scratch | Re-run **only the failed sub-graph** |
| Hard to tweak one step | Change one node's prompt/LLM/temperature, replay the rest |

### Core properties
- **Nodes = units of work** (an agent/skill: researcher, coder, critic, formatter…).
- **Edges = dependencies AND context flow**. If N8's input is N3 + N6, drawing those edges means N3's and N6's outputs are automatically passed to N8. *"Edges are the context."*
- **A node fires when all its predecessors are done or skipped** — no manual `if this then that`. Dependencies satisfied → it runs.
- **Parallelism is free**: nodes with no shared dependency execute concurrently (via `asyncio.gather`). Wall-clock = **max of the branches, not the sum**.

### Dynamic, not fixed
- The graph is **not** decided fully up front and frozen. The planner builds the initial graph, but it **grows/changes** as nodes complete or fail.
- "The structure visible at iteration N is *not* the structure at termination."
- On failure → planner is re-invoked, builds new/extended nodes. Old graph isn't deleted, just marked **stale/skipped**.

### State & execution
- The **graph is stateful**, the LLMs/agents are **stateless**. State lives in the graph (per-node: status, input, output, memory), persisted to JSON.
- Node states: **pending / running / complete / skipped**.
- **NetworkX** provides the data structure (`DiGraph`) + graph algorithms. The `Executor` in `flow.py` *is* the orchestrator (replaces the old `while` loop). Graph saved via `nx.node_link_data` → `graph.json`.
- The executor loop is essentially **Kahn's algorithm** (same approach as NetworkX's `topological_sort`): repeatedly pick nodes whose every predecessor is complete/skipped and run them. Non-DAG → NetworkX raises `NetworkXUnfeasible`.
- Concurrency is via Python **`asyncio.gather`** — runs all "ready" coroutines concurrently and waits for *all* to finish before returning (an implicit **barrier**). Returns results in input order.
- Persistence is atomic (write temp file → `os.replace`) so a kill mid-run leaves a valid file → **resumable** from any node boundary.

```text
# Executor loop (from the session MD)
while there exist incomplete nodes:
    ready = nodes whose every predecessor is complete or skipped
    run all ready nodes concurrently via asyncio.gather
    for each completed node:
        extend the graph with any successors the skill emitted
        persist the graph and the node state to disk
```

### The classic example (real metrics from session MD)
> "Find the populations of London, Paris, Berlin and tell me which two are closest in size."

```text
USER QUERY → n:1 planner
          → n:2/3/4 researcher (London | Paris | Berlin)  ← run in PARALLEL
          → n:5 coder
          → n:6 formatter  +  n:7 sandbox_executor  ← diamond (trust + verify)
          → ANSWER
```

| Metric | Session 7 (sequential) | Session 8 (DAG) |
|---|---|---|
| Iterations / nodes | 11 iterations | 7 nodes |
| Wall-clock | 125 s | **62 s** |
| Gateway calls | 60 | 15 |
| Input tokens | 54,000 | **17,000** |

- 3 researchers all finish at the **same instant** (42.69 s) — the `asyncio.gather` barrier. Parallel-layer cost = **max branch (40.5 s), not the sum (110 s)**.
- Speedup **2.11×**, not 3× — serial overhead (planner + coder + formatter) isn't parallelised. *Optimise the slowest branch, not the average.*
- Token savings are **structural**: S7 re-sends cumulative history every iteration; S8 nodes are scoped to their own inputs only.
- **Teaching point:** the lesson isn't the speedup — it's the **shape of the trace** (context flow along edges, node self-detecting failure, critic attachable anywhere).

---

## Skills

### What a skill is
A **skill = prompt + MCP tools + temperature** (a "triple"). The S8 packaging of what already existed in S7 — just bundled and named.

> *"Skill is literally the prompt that we had last time, and we were infusing the MCP tools it can call when building the prompt. That is exactly what we're doing now, just calling it skill."*

- **Prompt** = the **system prompt** (e.g. `planner.md`). No separate user prompt — the **user query** is the only user input.
- **Tools** = the subset of MCP tools the agent may call.
- **Temperature** = 0–1 creativity dial (becoming obsolete — see below).

### How a skill is defined (real code)
Two files per skill, **no Python class per skill**:
1. **A prompt `.md`** under `code/prompts/` — the system prompt.
2. **An entry in `code/agent_config.yaml`** — registers prompt path, allowed tools, temperature, etc.

`skills.py` reads the prompt + tool list and assembles the system prompt. Plug-and-play: drop in `myskill.md`, add a YAML entry, tell the planner it exists.

### `agent_config.yaml` fields (actual)
| Field | Meaning |
|---|---|
| `prompt` | path to the system-prompt markdown |
| `tools_allowed` | MCP tools this skill may call; `[]` = text-only |
| `temperature` | creativity dial 0–1 |
| `max_tokens` | output cap |
| `description` | one-liner for dashboards/replay |
| `internal_successors` | **static graph extension** — skills auto-added as successors when this finishes (e.g. `coder → sandbox_executor`) |
| `critic: true` | orchestrator inserts a **Critic** node on every outgoing edge (e.g. `distiller`) |

```yaml
researcher:
  prompt: prompts/researcher.md
  tools_allowed: [web_search, fetch_url]
  temperature: 0.7          # exploratory
  max_tokens: 2500

critic:
  prompt: prompts/critic.md
  temperature: 0.0          # pass/fail → deterministic

coder:                      # STUB — student assignment
  prompt: prompts/coder.md
  internal_successors: [sandbox_executor]
  temperature: 0.2
```

### Catalog (Session 8)
`planner, retriever, researcher, distiller, summariser, critic, formatter, sandbox_executor, coder, browser`
- **planner** is itself a skill (just always called first).
- **coder** prompt is empty → **assignment**. **browser** → Session 9 stub.

### ⚠️ Two common misunderstandings
1. **Skills do NOT reduce tokens by themselves.** Renaming a prompt to a "skill" = zero savings. Token reduction comes from **not carrying history forward** (graph passes only relevant context per node). The *separation-of-concern* win (a focused sub-agent with only the needed skill, ~10–40k tokens, vs. one mega-agent with everything, ~100k) is real — but that's scoping, not the label.
2. **These are NOT Claude-style skills (yet).** Claude loads a short *description* and reads the full *body* on demand. Here the **whole prompt loads every time** — no description/body split. Syncing to the GitHub/Claude skill format is future work.

### Why skills matter — separation of concern
Each agent is scoped to one job with just its prompt + tools, instead of one LLM juggling a million-token context. Architecture stays constant; only skills change per use case (instructor's construction company: 40–50 skills for CAD, per-city building codes, HVAC regs…). A skill can also pin a **small LLM** (e.g. function-calling Gemma 270M) for narrow tasks to save cost.

### Note on temperature (getting obsolete)
| Skill | Temp | Reasoning |
|---|---|---|
| Critic | 0.0 | pass/fail verdict — want the same answer on the same input |
| Distiller | 0.1 | extraction — the field is in the input or it isn't |
| Retriever | 0.2 | retrieval is mostly deterministic |
| Planner | 0.4 | decompositions need a little breathing room |
| Researcher | 0.7 | exploratory web search — at 0.0 it can loop on the same query |

Gemini 3 docs now recommend keeping temperature at `1.0` for everything; vendors are moving to deterministic-by-default for agentic use, so temperature is being dropped (planned: removed from S9 onward). If you see looping/degraded reasoning on Gemini-routed skills, reset all to `1.0` and constrain behaviour in the **prompt** instead.

---

## Critic Loop

### What it is
An LLM that reads **one upstream node's output** and emits a binary **`pass` / `fail`** verdict with a one-line rationale. Validates work mid-flight without round-tripping everything through the planner. Temperature `0.0` (deterministic). **Makes no tool calls.**

Output schema (`prompts/critic.md`):
```json
{ "verdict": "pass" | "fail", "rationale": "<one or two short sentences>" }
```
Procedure: read `UPSTREAM_OUTPUT` → check against the `INPUTS` that produced it → look for fabricated fields, unsupported claims, contradictions, missing fields → emit pass/fail. *"Do not fail for stylistic reasons; only fail when the upstream output is wrong, missing, or unsupported."*

### How it enters the graph (two paths)
1. **Auto-insert** — a skill flagged `critic: true` in `agent_config.yaml` (currently **`distiller`**). The orchestrator splices a critic node onto **every outgoing edge** of that node.
2. **Planner-emitted** — planner inserts a critic when the user demands a strict, checkable constraint (`"exactly 5-7-5 syllables"`, `"valid JSON"`, `"≤280 chars"`). Critic's input = the writing node's id; `metadata.question` repeats the constraint.

### The loop (on fail)
```text
producer ──→ critic
               │ pass → flow continues, graph unchanged
               │ fail → 1. blocked child marked  skipped
                        2. ONE planner-recovery node queued (carries the rationale)
                        3. per-target cap = max 1 re-plan per branch  → no infinite loop
```
Bounded by design: planner re-plans → corrected sub-graph → if it fails again the **per-target cap** stops it. Handled separately from node-*failure* recovery (`recovery.py`) because it needs the critic's target/child metadata + run-scoped cap state.

### ⚠️ Rubber-stamp finding (key teaching point)
Forcing query: *"write a haiku, exactly 4-6-4 syllables (not 5-7-5)."* Across 3 runs the coder emitted **5-7-5** and the critic returned **`pass`** ("follows the 4-6-4 structure"). **It never counted — it keyword-matched and approved**, because the critic can make no tool calls. LLM-as-judge is reliable for **fluency/tone/completeness**, unreliable for **precise structural constraints** (syllables, exact arithmetic, regex, char counts).

**Separate the two problems — they live in different code:**
| Problem | Fixed in |
|---|---|
| **Wiring** — does the critic splice in, skip the child, queue recovery? | the **orchestrator** (unit-tested, correct) |
| **Policy** — is the verdict actually *right*? | the critic's **prompt**, or give it a **tool** |

S9 fix = **critic-with-tools** (syllable counter / JSON-schema validator / arithmetic) so verdicts are grounded.

### Assignment note (Issue #15, part 3)
Must produce **both a pass and a fail** across two runs, and the fail must splice in a recovery that corrects the answer. Pick a property the LLM critic *can* check from text alone (e.g. "contains exactly these 3 fields", "JSON parses", "mentions X") — **avoid syllable-counting** (the rubber-stamp trap) unless you add a tool.

---

## Sandbox Environment

### What it is
A thin wrapper around `subprocess.run` (`code/sandbox.py`) that runs the **Coder** node's Python in a child process and returns `stdout / stderr / exit_code / files_written`. It's the "verify" branch of the populations diamond (alongside the formatter's "trust" branch).

> The LLM **almost never sees it** — the orchestrator calls `sandbox.run_python(code)` directly and packs the result. `sandbox_executor.md` only runs for optional post-mortem explanations. Effectively pure-Python plumbing in a skill's clothing.

### Actual boundaries (`sandbox.py`)
| Control | Value | Why |
|---|---|---|
| Wall-clock timeout | `30 s` | kills runaway loops (`timed_out=True`, exit `-1`) |
| stdout / stderr caps | `1 MB` each | a noisy `print` can't poison orchestrator output (truncated) |
| cwd | fresh `tempfile.TemporaryDirectory("s8sandbox-")` | throwaway dir; written files listed in `files_written` |
| **Env scrubbing** | **whitelist only** | the real security bit ↓ |

### Env scrubbing = the key idea
```python
DEFAULT_ENV_WHITELIST = ("PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE")
scrubbed = {k: os.environ[k] for k in env_whitelist if k in os.environ}
# child gets env=scrubbed — everything else (API keys, git tokens…) is DROPPED
```
- **PATH** → find `python3`. **HOME** → libs that look for `~`. **LANG/LC_ALL/LC_CTYPE** → UTF-8 locale/encoding.
- Protection = the child can't read `OPENAI_API_KEY` etc. because they aren't in its environment.

> **Video correction:** `LC_ALL` does *not* "hide all env variables." The hiding is done by passing a fresh `env=` dict to `subprocess.run` (the whitelist). `LC_ALL`/`LC_CTYPE` are kept for *encoding*, not secret-hiding.

### ⚠️ Usability boundary, NOT security
Per the module docstring: *no chroot, no container, no syscall filter, no FS allowlist beyond cwd. A malicious script can read `/etc` and call the network.* It stops **mistakes** (infinite loops, runaway output, accidental secret leakage), not **attacks**. Real isolation → **Firejail** / container (out of S8 scope). One of the five named "honest design choices."

### Returned dict
`{exit_code, stdout, stdout_truncated, stderr, stderr_truncated, files_written:[{name,size_bytes}], timed_out, cwd}` — `cwd` kept so the artifact pipeline can collect generated files.

### Assignment note (Issue #15, part 4)
Fill `prompts/coder.md` so the coder emits Python that runs cleanly here: self-contained, prints the answer to stdout, no network/secret deps, finishes < 30 s. `coder` auto-routes to `sandbox_executor` via `internal_successors`.

---

## Quick reference: other S8 mechanisms (from session MD)

- **Recovery classifier** (`recovery.py`): `transient` (5xx/timeout → skip, gateway already retried) · `validation_error` (→ skip, fix is a prompt) · `upstream_failure` (→ replan, but planner-own failures skip to avoid looping). Guards against the "503 → re-plan → 503" loop.
- **Sandbox** is a **usability boundary, not security** — fresh temp dir, 1 MB stdout cap, 30 s timeout, locale env vars (`PATH/HOME/LANG/LC_ALL/LC_CTYPE`) scrubbed to hide secrets; a hostile script could still reach the network.
- **Gateway V8** (port 8108; V7 stays on 8107): `agent`/`session` tags on every call, `/v1/cost/by_agent`, `/v1/chat/batch` (parallel dispatch), retry-on-5xx, `agent_routing.yaml` pins agent→provider (saves 200–400 ms router latency, loses auto-failover; not hot-reloaded).
- **Resume guarantee is at the node boundary, not the tool-call boundary** — a researcher killed mid-tool-loop re-runs from the top (mid-tool resume deferred).

---

## References

- [Directed acyclic graph — Wikipedia](https://en.wikipedia.org/wiki/Directed_acyclic_graph) — formal DAG definition, cycles, topological ordering theorem
- [DAGs & Topological Sort — NetworkX Notebooks](https://networkx.org/nx-guides/content/algorithms/dag/index.html) — guided intro
- [`networkx.topological_sort`](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.dag.topological_sort.html) — Kahn's algorithm; `NetworkXUnfeasible` if not a DAG
- [`asyncio` — Coroutines and Tasks (Python docs)](https://docs.python.org/3/library/asyncio-task.html) — `gather()` concurrency + barrier semantics; `TaskGroup` alternative
- [Databricks — What is a DAG](https://www.databricks.com/blog/what-is-dag) · [GeeksforGeeks — Intro to DAG](https://www.geeksforgeeks.org/dsa/introduction-to-directed-acyclic-graph/) — accessible overviews
- [DAGs: The Backbone of Modern Multi-Agent AI (Medium)](https://santanub.medium.com/directed-acyclic-graphs-the-backbone-of-modern-multi-agent-ai-d9a0fe842780) — DAGs in agent orchestration
- Meta agent-harness research (the "code as agent harness" direction referenced in class): [Meta-Harness paper page](https://huggingface.co/papers/2603.28052) · [HyperAgents writeup](https://cobusgreyling.medium.com/hyperagents-by-meta-892580e14f5b) *(exact paper the instructor cited is uncertain; these are the closest matches)*
- Local: `docs/Session8_MultiAgent_DAG_Orchestration.md` (full writeup) · `code/agent_config.yaml` (skill catalog) · `code/flow.py` (orchestrator)
