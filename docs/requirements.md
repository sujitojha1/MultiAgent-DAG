# Software Requirements Specification

**Project:** EAG V3 — Session 8: Multi-Agent DAG Orchestration Assignment — **PulseDAG-GithubRepo**  
**Document ID:** SRS-EAG3-S8-001  
**Version:** 1.1  
**Date:** 2026-05-31  
**Standard:** IEEE 29148:2018 + EARS (Easy Approach to Requirements Syntax, Mavin et al.)

> **v1.1 change:** aligned to the chosen problem — **PulseDAG-GithubRepo** (a trending-repo scout). Graded new skill is `relevance_filter` (was a generic `course_generator` placeholder, now retired from assignment scope). Adds the alignment critic (FR-305), the trending-data-source requirement (FR-106/RSK-1), the relevance-criteria input (FR-505), and the non-graded Chrome-extension trigger (§5.7, CON-107). See `docs/idea.md`.

---

## 1. Introduction

### 1.1 Purpose

This document specifies the software requirements for completing the Session 8 assignment of EAG V3. It establishes testable acceptance criteria for all five deliverable parts and the architectural invariants that govern every change.

### 1.2 Scope

**System name:** `PulseDAG-GithubRepo` — the growing-graph orchestrator rooted in `code/flow.py`, applied to a GitHub-trending repository scout.

**Problem domain:** scout GitHub Trending across languages and timeframes, then merge, compute star **metrics** (velocity, cross-source delta), filter for **relevance**, and explain the most useful rising repositories. The DAG mechanics are proven on this domain; see `docs/idea.md` for the full concept.

The system extends the Session 7 cognitive architecture by replacing the single-iteration loop with a directed acyclic graph (DAG) of typed skill nodes. The student must:

1. Pass five base queries carried over from earlier sessions.
2. Demonstrate a parallel fan-out query — 4 trending researchers (Python/Rust × weekly/monthly).
3. Demonstrate a Critic verdict cycle (pass + fail + recovery) — **two critics**: completeness and alignment.
4. Implement the stub Coder skill prompt — trending metrics + a deterministic per-repo fact-line.
5. Add one new skill to the catalogue — **`relevance_filter`**.

A non-graded **Chrome-extension trigger** (§5.7) wraps the existing `Executor` for a usable UI; it is shown in the demo video but is not one of the five graded parts.

Out of scope: gateway internals (`gateway/`), Session 7 carry-over modules (`perception.py`, `decision.py`, `action.py`, `memory.py`, `vector_index.py`, `artifacts.py`, `mcp_server.py`). **Retired from scope:** the `course_generator` placeholder skill (a separate codebase-understanding idea, not part of PulseDAG-GithubRepo).

### 1.3 Intended Audience

| Audience | Usage |
|---|---|
| Student (implementer) | Primary implementation reference |
| Instructor (evaluator) | Acceptance review and grading |

### 1.4 Relationship to Other Documents

| Ref | Document | Role |
|---|---|---|
| [D1] | `docs/Session8_MultiAgent_DAG_Orchestration.md` | Session notes — architecture rationale |
| [D2] | `docs/transcript.txt` | Instructor lecture transcript |
| [D3] | `ASSIGNMENT.md` | Grader checklist (normative) |
| [D4] | `code/flow.py` | Orchestrator implementation |
| [D5] | `code/schemas.py` | Typed contracts (`AgentResult`, `NodeSpec`, `NodeState`) |
| [D6] | `code/agent_config.yaml` | Skill catalogue |
| [D7] | `code/recovery.py` | Failure classification and critic-fail splice |
| [D8] | `code/skills.py` | Skill registry, prompt rendering, dispatcher |
| [D9] | `code/tests/test_recovery.py` | 22 pinned unit tests (normative) |
| [D10] | `docs/idea.md` | PulseDAG-GithubRepo concept — graph shape, skill design, open decisions |
| [D11] | `docs/class_notes.md` | DAG / skills / critic / sandbox study notes |

---

## 2. Terms and Definitions

| Term | Definition |
|---|---|
| DAG | Directed Acyclic Graph — the graph is directed (edges have a source and target) and contains no cycles |
| Skill | A YAML entry in `agent_config.yaml` plus a `.md` prompt file in `prompts/`; no Python class per skill |
| Node | A vertex in the graph; carries `skill`, `inputs`, `metadata`, and `status` (`pending/running/complete/failed/skipped`) |
| Planner | The first node in every session; skill = `planner`; emits `NodeSpec` objects that become successor nodes |
| Executor | `flow.Executor`; walks the graph, dispatches ready nodes via `asyncio.gather` |
| `ready_nodes()` | Nodes whose every predecessor is `complete` or `skipped` |
| Critic | Skill that emits `{"verdict":"pass"\|"fail","rationale":"..."}` |
| `internal_successors` | YAML field; orchestrator appends listed skills after any node of this type completes |
| `critic: true` | YAML flag; orchestrator auto-inserts a Critic on every outgoing edge from this skill |
| SandboxExecutor | Skill that calls `sandbox.run_python` instead of the LLM gateway |
| AgentResult | `schemas.AgentResult` — boundary contract between `flow.py` and `skills.py` |
| NodeSpec | `schemas.NodeSpec` — one node the Planner intends the orchestrator to add |
| SID | Session ID `s8-<uuid8>` — names the directory under `state/sessions/` |
| EARS | Easy Approach to Requirements Syntax; provides five sentence templates that make requirements testable |

---

## 3. System Overview

### 3.1 System Description

The orchestrator begins every session with a single Planner node. The Planner reads the user query plus FAISS-ranked memory hits and emits a JSON graph of skill nodes. The Executor walks the graph in a `while` loop, dispatching every `ready_nodes()` batch concurrently via `asyncio.gather`. When a node completes, `Graph.extend_from` splices in any dynamic successors, `internal_successors`, and Critic auto-insertions. Failure triggers `recovery.plan_recovery`; a Critic-fail triggers `recovery.handle_critic_verdict`. All graph and node state is persisted atomically to `state/sessions/<sid>/` so interrupted runs can resume.

### 3.2 Context Diagram

```
User Query
    │
    ▼
[Memory.read]  ─── FAISS hits ──▶  every skill prompt this session
    │
    ▼
n:1  planner  ─── emits NodeSpec list ──▶  Graph.extend_from
    │
    ├──▶ n:2  skill_A   ─┐
    ├──▶ n:3  skill_B   ─┤  asyncio.gather (parallel layer)
    └──▶ n:4  skill_C   ─┘
               │
               ▼
           n:5  aggregator / coder
               │
               ├──▶ n:6  formatter  (terminal — final_answer)
               └──▶ n:7  sandbox_executor  (auto-appended by internal_successors)
```

### 3.3 Five Graph Growth Mechanisms

| # | Mechanism | Where in code |
|---|---|---|
| 1 | Planner seed plan | `flow.Executor.run` adds `planner` as first node |
| 2 | Dynamic successors from any skill | `AgentResult.successors` → `Graph.extend_from` |
| 3 | Static `internal_successors` (yaml) | `Graph.extend_from` lines 133–135 |
| 4 | Critic auto-insertion (`critic: true`) | `Graph.extend_from` lines 139–147 |
| 5 | Planner re-invocation on failure | `flow.Executor.run` lines 262–270 |

---

## 4. Stakeholder Requirements

These capture what the evaluator (instructor) needs to observe.

**STK-1** — The instructor shall be able to watch a YouTube video that clearly demonstrates all five assignment parts with terminal output visible.

**STK-2** — The instructor shall find log excerpts or screenshots for all five parts in `README.md` without having to run the code.

**STK-3** — The instructor shall confirm the 22 unit tests in `tests/test_recovery.py` pass by running `uv run pytest` in `code/`.

---

## 5. System Requirements

EARS sentence patterns used throughout:

| Pattern | Template |
|---|---|
| **Ubiquitous (U)** | `The [system] shall [response]` |
| **Event-driven (E)** | `When [trigger], the [system] shall [response]` |
| **Unwanted behaviour (UB)** | `If [unwanted condition], the [system] shall [response]` |
| **State-driven (S)** | `While [state], the [system] shall [response]` |
| **Optional feature (O)** | `Where [feature is included], the [system] shall [response]` |

Each requirement is tagged with:
- **ID** — unique, never reused
- **EARS pattern** — letter code
- **Priority** — Must (M) / Should (S) / Could (C)
- **Part** — assignment part it satisfies

---

### 5.1 Part 1 — Five Base Queries

**FR-101** [E, M, Part 1]  
When the user submits the query `"Say hello."`, the system shall produce a final answer in two nodes (planner → formatter) with wall-clock time ≤ 3 seconds.

**FR-102** [E, M, Part 1]  
When the user submits query A ("Fetch `https://en.wikipedia.org/wiki/Claude_Shannon` and tell me his birth date, death date, and three key contributions to information theory"), the system shall return a response that includes his birth date, death date, and at least three named contributions to information theory.

**FR-103** [E, M, Part 1]  
When the user submits query I ("Find the populations of London, Paris, Berlin and tell me which two are closest in size"), the system shall dispatch at least three researcher nodes concurrently and complete within 90 seconds wall-clock.

**FR-104** [UB, M, Part 1]  
If the user submits query J ("Read `/nonexistent/path.txt` and tell me what's in it"), the system shall return a graceful failure explanation without dispatching any file-read tool call.

**FR-105** [E, M, Part 1]  
When query K ("For Lagos, Cairo, and Kinshasa, find current populations and growth rates and tell me which is growing fastest") is killed mid-run and restarted with `flow.py --resume <sid>`, the system shall reuse completed-node results and produce a correct final answer without re-running any node that was already `complete`.

---

### 5.1b Trending Data Source (PulseDAG)

**FR-106** [E, M, Part 2/4]  
When a `researcher` node is asked for trending repositories, the system shall obtain, per `(language, timeframe)`, a list of repositories with at least `owner/repo`, `total_stars`, `stars_gained`, and `description`.

**FR-107** [O, S, Part 2/4]  
Where GitHub Trending HTML cannot be parsed reliably by `fetch_url`, the system shall fall back to a structured trending data source (e.g. an unofficial trending JSON API), and the `fetch_url` limitation shall be recorded as motivation for the Session 9 browser skill.

---

### 5.2 Part 2 — Parallel Fan-Out

**FR-201** [E, M, Part 2]  
When the user submits the fan-out query (*"top trending Python and Rust repos for both this week and this month"*), the Planner shall emit one `researcher` node per `(language × timeframe)` page — at least four independent nodes — so the Executor dispatches them in a single `asyncio.gather` call.

**FR-202** [U, M, Part 2]  
The system shall demonstrate that the wall-clock time of a parallel layer equals the maximum elapsed time across its branches, not the sum.

**FR-203** [U, M, Part 2]  
The per-node timing printed to stdout shall show parallel-layer nodes with overlapping start times and the same finish time (within 1 second), confirming the `asyncio.gather` barrier.

---

### 5.3 Part 3 — Critic Verdict (two critics)

PulseDAG-GithubRepo demonstrates the Critic in **two distinct roles**, both with recoverable fails:

- **Completeness critic** (FR-301) — auto-inserted (`critic: true`) on `distiller`; checks each repo row has all required fields.
- **Alignment critic** (FR-305) — planner-emitted between `relevance_filter` and `formatter`; checks each "why it matters" is faithful to the repo's real description and the interest criteria.

**FR-301** [E, M, Part 3]  
When the `distiller` (marked `critic: true`) produces normalised repo rows, the orchestrator shall auto-insert a `critic` node on its outgoing edge that verifies every row contains `owner/repo`, `total_stars`, `stars_gained`, and `description`. (Completeness only — de-duplication is the Coder's responsibility, not the Critic's.)

**FR-302** [E, M, Part 3]  
When a Critic node returns `{"verdict": "fail", "rationale": "..."}`, the system shall mark the blocked child node as `skipped` and queue a recovery Planner node whose `metadata.failure_report` contains the critic rationale.

**FR-303** [U, M, Part 3]  
The student shall demonstrate each Critic across two runs: one producing `{"verdict": "pass"}` and one producing `{"verdict": "fail"}` followed by a corrected answer from the recovery. The forced fail shall be **recoverable** — i.e. a re-plan on different/refreshed inputs yields a passing result (a permanently-malformed input that fails twice and hits the per-target cap does not satisfy this requirement).

**FR-304** [UB, M, Part 3]  
If a Critic-fail recovery has already been triggered for a given target node within the same session, the system shall not queue a second recovery Planner for that target (per-target cap = 1).

**FR-305** [E, M, Part 3]  
When the Planner builds a graph containing a `relevance_filter` node, it shall emit an alignment `critic` node between that node and the `formatter`, whose `metadata.question` asks whether each kept repo's "why it matters" is supported by the repo's description and matches the interest criteria. A planted hallucinated rationale shall produce `{"verdict": "fail"}` and trigger a re-filter that corrects it. This requires no `Executor` change (planner-emitted critics are already supported).

---

### 5.4 Part 4 — Coder Skill

**FR-401** [U, M, Part 4]  
The file `prompts/coder.md` shall contain a complete, functional prompt (stub text removed) that instructs the LLM to emit a JSON object with exactly two fields: `"code"` (valid Python source) and `"rationale"` (one short sentence).

**FR-402** [E, M, Part 4]  
When a Coder node completes successfully, the system shall automatically append a `sandbox_executor` successor node via the `internal_successors` entry in `agent_config.yaml`, without any Planner or Executor code change.

**FR-403** [E, M, Part 4]  
When the `sandbox_executor` node runs, the system shall extract the `"code"` field from the upstream Coder's `AgentResult.output`, execute it via `sandbox.run_python`, and store `stdout`, `stderr`, `exit_code`, and generated files in its own `AgentResult.output`.

**FR-404** [UB, M, Part 4]  
If the upstream Coder node's `AgentResult.output` does not contain a `"code"` field, the `sandbox_executor` node shall return `AgentResult(success=False, error="no code in upstream coder output")` without attempting subprocess execution.

**FR-405** [U, M, Part 4]  
The student shall demonstrate the Coder on the trending-metrics query, where the correct answer requires computation the Formatter cannot reliably produce from text: de-duplicating repos across the four lists, computing `velocity = stars_gained / total_stars × 100` per repo, computing the cross-source delta (repos appearing in both weekly and monthly), and ranking by momentum.

**FR-406** [E, S, Part 4]  
When the Coder runs, it shall additionally emit a **deterministic templated fact-line** per repo (string assembly from the computed metrics + the distilled description) — code-generated, not LLM prose, so it carries no hallucination risk.

---

### 5.5 Part 5 — New Skill

**FR-501** [U, M, Part 5]  
The student shall add one new entry — **`relevance_filter`** — to `agent_config.yaml`, a capability not covered by the existing catalogue (`planner`, `retriever`, `researcher`, `distiller`, `summariser`, `critic`, `formatter`, `sandbox_executor`, `coder`, `browser`). It is prompt-only (`tools_allowed: []`): it consumes the Coder's computed table and applies semantic relevance judgment (keep/drop) plus a one-line "why it matters" per kept repo.

**FR-502** [U, M, Part 5]  
The new skill shall have a corresponding prompt file at `prompts/relevance_filter.md` following the same structural conventions as existing prompt files.

**FR-503** [E, M, Part 5]  
When a query requiring `relevance_filter` is submitted, the Planner shall emit it as a node in the DAG, and the Executor shall dispatch it through the standard `run_skill` path without any `flow.py` or `skills.py` modification.

**FR-504** [UB, M, Part 5]  
If the new skill implementation requires adding a skill-name branch (`if skill.name == "relevance_filter"`) to `flow.Executor`, the implementation shall be considered non-conformant to the architectural rule: adding a skill is a YAML edit and a prompt file only.

**FR-505** [E, S, Part 5]  
When `relevance_filter` runs, the interest criteria shall be available to it — either hard-coded in `relevance_filter.md` or supplied via the query / the extension's profile field — so its keep/drop judgment is grounded in a stated interest profile (default: agentic / MCP / dev-tooling).

---

### 5.6 Submission

**FR-601** [U, M, Submission]  
The student shall submit a YouTube demo video that clearly shows Parts 1–5 with terminal output legible on screen.

**FR-602** [U, M, Submission]  
The student shall update `README.md` with gateway log excerpts or terminal screenshots confirming results for all five parts.

---

### 5.7 Chrome Extension Trigger (non-graded)

The extension is the trigger + presentation layer for PulseDAG-GithubRepo. It is **not** one of the five graded parts; it is built and shown in the demo video for usability. All graded logic is proven via the DAG run logs, independent of the extension.

**FR-701** [O, C, Extension]  
Where the Chrome extension is included, its popup shall let the user choose language(s), a time window, and a "🎲 random pick" option, and a "Run" action shall trigger an agent run and render the resulting digest.

**FR-702** [O, S, Extension]  
Where the extension is included, it shall reach the agent through a thin HTTP bridge — a **new, separate module** that imports and calls the existing `flow.Executor` — and shall not require changes to `Executor.run` internals.

**FR-703** [O, C, Extension]  
Where "random pick" is selected, the system shall surface a single repository to explore. The simplest conformant implementation is client-side selection from the ranked digest; a server-side `mode:"random"` planner branch is an allowed alternative (and would introduce a second new skill, `picker`).

---

## 6. Non-Functional Requirements

**NFR-101 — Test Suite Integrity** [Must]  
The system shall pass all 22 unit tests in `tests/test_recovery.py` before any change is made and after all changes are complete. (`uv run pytest` exit code = 0.)

**NFR-201 — Token Efficiency** [Should]  
The parallel fan-out query (FR-103, FR-201) shall consume fewer input tokens than an equivalent Session 7 sequential run, as demonstrated by comparing `/v1/cost/by_agent` output from the Gateway.

**NFR-301 — Atomic Persistence** [Must]  
While any node state or graph state is being written to `state/sessions/<sid>/`, the system shall write to a temporary file first and call `os.replace` to swap it in, ensuring the previous file is preserved if the process is killed between the write and the swap.

**NFR-401 — Sandbox Constraints** [Must]  
While `sandbox.run_python` is executing, the system shall cap combined stdout + stderr at 1 MB and enforce a 30-second execution timeout.

**NFR-501 — Resume Granularity** [Must]  
When a session is resumed, the system shall re-execute from the node boundary: any node whose status was `running` at kill time shall be reset to `pending` and re-run from its start. Mid-tool-call resume is deferred to Session 9.

---

## 7. Constraints

**CON-101** — The files `perception.py`, `decision.py`, `action.py`, `memory.py`, `vector_index.py`, `artifacts.py`, and `mcp_server.py` must be byte-identical to their Session 7 versions. Verified with `git diff`.

**CON-102** — `flow.Executor` must contain no `if skill.name == "<new-skill>"` branch for any skill added in Part 5.

**CON-103** — `recovery.classify_failure` must preserve all existing label assignments for the 22 error-string test cases in `test_recovery.py`.

**CON-104** — Gateway V8 (`gateway/` on port 8108) must remain untouched.

**CON-105** — The `Graph` must remain acyclic: `Graph.add_node` only adds edges from a predecessor node to the new node; a node cannot reference itself or a descendant as an input.

**CON-106** — `MAX_NODES = 60` in `flow.py` must not be increased as a workaround for a looping Planner. If the cap fires, the root cause must be fixed in the prompt.

**CON-107** — The Chrome-extension HTTP bridge must be a separate module that imports and calls the existing `flow.Executor`; it must not edit `Executor.run` internals (it is a new invocation entry point, a permitted "new generic mechanism", not a logic change). The trigger endpoint is distinct from Gateway V8's LLM port 8108.

---

## 7a. Risks

**RSK-1 — Trending data fetch.** Parts 2/3/4 all depend on researchers obtaining trending data. GitHub Trending is server-rendered HTML and may not parse cleanly via `fetch_url`. **Mitigation (FR-107):** spike `fetch_url` first; fall back to a structured trending JSON API. Decide before implementing the fan-out. Residual `fetch_url` gap → documented S9 browser-skill motivation.

---

## 8. Traceability Matrix

| Req ID | Summary | Assignment Part | Primary File(s) | Test / Verification | Issue(s) |
|---|---|---|---|---|---|
| FR-101 | hello ≤ 3 s, 2 nodes | Part 1 | `flow.py`, `prompts/planner.md` | demo / timing log | #13, #20 |
| FR-102 | Shannon bio query | Part 1 | `prompts/researcher.md`, `prompts/distiller.md` | demo / log | #21 |
| FR-103 | Populations parallel, ≤ 90 s | Parts 1 & 2 | `flow.py` (asyncio.gather), `prompts/researcher.md` | demo / timing log | #22 |
| FR-104 | Graceful fail on bad path | Part 1 | `prompts/planner.md` | demo / log | #23 |
| FR-105 | SIGKILL + resume | Part 1 | `flow.py`, `persistence.py` | demo / log | #24 |
| FR-106 | Researcher returns trending rows w/ required fields | Parts 2 & 4 | `prompts/researcher.md` | demo / log | #25 |
| FR-107 | fetch_url → JSON API fallback (data source) | Parts 2 & 4 | `prompts/researcher.md` | spike / RSK-1 | (new) |
| FR-201 | Planner emits 4 parallel trending researchers | Part 2 | `prompts/planner.md`, `flow.Graph.extend_from` | demo / log | #25 |
| FR-202 | Wall-clock = max not sum | Part 2 | `flow.Executor.run` (gather) | demo / timing table | #27 |
| FR-203 | Shared finish timestamp in log | Part 2 | `flow.Executor.run` stdout | demo / log | #26 |
| FR-301 | Completeness critic auto on distiller | Part 3 | `agent_config.yaml`, `prompts/critic.md`, `flow.Graph.extend_from` | demo / log | #28 |
| FR-302 | Critic-fail → child skipped + recovery | Part 3 | `recovery.handle_critic_verdict` | `test_recovery.py` lines 97–135 | #30 |
| FR-303 | Pass + recoverable fail across 2 runs (both critics) | Part 3 | `prompts/critic.md` | demo / 2 × log | #29, #30 |
| FR-304 | Per-target cap = 1 re-plan | Part 3 | `recovery.handle_critic_verdict` | `test_recovery.py` | #31 |
| FR-305 | Alignment critic (planner-emitted) on relevance_filter | Part 3 | `prompts/planner.md`, `prompts/critic.md` | demo / log | #28, #30 |
| FR-401 | coder.md complete prompt | Part 4 | `prompts/coder.md` | code review / demo | #33 |
| FR-402 | internal_successors auto-appends sandbox | Part 4 | `agent_config.yaml`, `flow.Graph.extend_from:133` | demo / log | #34 |
| FR-403 | sandbox_executor runs code field | Part 4 | `skills.run_skill` (sandbox branch) | demo / stdout | #34 |
| FR-404 | sandbox_executor fails on missing code | Part 4 | `skills.run_skill:257` | demo / log | #45 |
| FR-405 | Coder on trending metrics (velocity, delta, dedup, rank) | Part 4 | `prompts/coder.md`, `sandbox.py` | demo / sandbox stdout | #35 |
| FR-406 | Coder emits deterministic per-repo fact-line | Part 4 | `prompts/coder.md` | demo / stdout | #35 |
| FR-501 | `relevance_filter` in agent_config.yaml | Part 5 | `agent_config.yaml` | code review | #36 |
| FR-502 | `prompts/relevance_filter.md` prompt file | Part 5 | `prompts/relevance_filter.md` | code review | #37 |
| FR-503 | relevance_filter dispatched, no Executor change | Part 5 | `flow.py` (unchanged), `skills.py` (unchanged) | demo / diff | #38 |
| FR-504 | No Executor branch for relevance_filter | Part 5 | `flow.py` | code review / `git diff` | #39 |
| FR-505 | Relevance criteria available to the skill | Part 5 | `prompts/relevance_filter.md` | code review / demo | #36, #38 |
| FR-701..703 | Chrome extension trigger (non-graded) | Extension | extension/, HTTP bridge module | demo video | (new) |
| FR-601 | YouTube demo | Submission | — | instructor view | #43 |
| FR-602 | README.md logs | Submission | `README.md` | instructor review | #40, #41, #42 |
| NFR-101 | 22 tests pass before and after | All | `tests/test_recovery.py` | `uv run pytest` | #14 |
| NFR-201 | Fewer tokens than S7 | Part 2 | Gateway `/v1/cost/by_agent` | log comparison | #46 |
| NFR-301 | Atomic writes | All | `persistence.py` | architecture review | #47 |
| NFR-401 | Sandbox 1 MB / 30 s cap | Part 4 | `sandbox.py` | code review | #48 |
| NFR-501 | Node-boundary resume | Part 1 | `persistence.py`, `flow.Executor.run:172` | demo | #24 |
| CON-101 | S7 modules byte-identical | All | 7 carry-over files | `git diff` | — |
| CON-102 | No skill-name branch in Executor (Part 5) | Part 5 | `flow.py` | `git diff` | #39 |
| CON-103 | Classifier labels stable | All | `recovery.classify_failure` | `test_recovery.py` | — |
| CON-104 | Gateway V8 untouched | — | `gateway/` | `git diff` | #12 |
| CON-105 | Graph acyclic by construction | All | `flow.Graph.add_node` | architecture review | — |
| CON-106 | MAX_NODES not raised as workaround | All | `flow.py:32` | code review | — |
| CON-107 | Extension bridge is separate module, no Executor edit | Extension | HTTP bridge module, `flow.py` | `git diff` | (new) |
| RSK-1 | Trending data fetch risk + mitigation | Parts 2/3/4 | `prompts/researcher.md` | spike | (new) |
