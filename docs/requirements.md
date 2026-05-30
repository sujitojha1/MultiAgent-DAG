# Software Requirements Specification

**Project:** EAG V3 — Session 8: Multi-Agent DAG Orchestration Assignment  
**Document ID:** SRS-EAG3-S8-001  
**Version:** 1.0  
**Date:** 2026-05-30  
**Standard:** IEEE 29148:2018 + EARS (Easy Approach to Requirements Syntax, Mavin et al.)

---

## 1. Introduction

### 1.1 Purpose

This document specifies the software requirements for completing the Session 8 assignment of EAG V3. It establishes testable acceptance criteria for all five deliverable parts and the architectural invariants that govern every change.

### 1.2 Scope

**System name:** `multiagent-dag-s8` (the growing-graph orchestrator rooted in `code/flow.py`)

The system extends the Session 7 cognitive architecture by replacing the single-iteration loop with a directed acyclic graph (DAG) of typed skill nodes. The student must:

1. Pass five base queries carried over from earlier sessions.
2. Demonstrate a parallel fan-out query.
3. Demonstrate a Critic verdict cycle (pass + fail + recovery).
4. Implement the stub Coder skill prompt.
5. Add one new skill to the catalogue.

Out of scope: gateway internals (`gateway/`), Session 7 carry-over modules (`perception.py`, `decision.py`, `action.py`, `memory.py`, `vector_index.py`, `artifacts.py`, `mcp_server.py`).

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

### 5.2 Part 2 — Parallel Fan-Out

**FR-201** [E, M, Part 2]  
When a query instructs comparison or processing of N ≥ 3 independent concrete items, the Planner shall emit one node per item so the Executor dispatches them in a single `asyncio.gather` call.

**FR-202** [U, M, Part 2]  
The system shall demonstrate that the wall-clock time of a parallel layer equals the maximum elapsed time across its branches, not the sum.

**FR-203** [U, M, Part 2]  
The per-node timing printed to stdout shall show parallel-layer nodes with overlapping start times and the same finish time (within 1 second), confirming the `asyncio.gather` barrier.

---

### 5.3 Part 3 — Critic Verdict

**FR-301** [E, M, Part 3]  
When a query specifies a verifiable structural constraint (e.g., exact character count, JSON schema validity, numeric bounds), the Planner shall insert a `critic` node between the writing node and the `formatter` node.

**FR-302** [E, M, Part 3]  
When a Critic node returns `{"verdict": "fail", "rationale": "..."}`, the system shall mark the blocked child node as `skipped` and queue a recovery Planner node whose `metadata.failure_report` contains the critic rationale.

**FR-303** [U, M, Part 3]  
The student shall demonstrate the same Critic query across two runs: one producing `{"verdict": "pass"}` and one producing `{"verdict": "fail"}` followed by a corrected answer from the recovery Planner.

**FR-304** [UB, M, Part 3]  
If a Critic-fail recovery has already been triggered for a given target node within the same session, the system shall not queue a second recovery Planner for that target (per-target cap = 1).

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
The student shall demonstrate the Coder on one query where the correct answer requires numeric computation (ranking, arithmetic, statistical comparison) that the Formatter cannot reliably produce from free text alone.

---

### 5.5 Part 5 — New Skill

**FR-501** [U, M, Part 5]  
The student shall add one new entry to `agent_config.yaml` for a skill capability not covered by the existing catalogue (`planner`, `retriever`, `researcher`, `distiller`, `summariser`, `critic`, `formatter`, `sandbox_executor`, `coder`, `browser`).

**FR-502** [U, M, Part 5]  
The new skill shall have a corresponding prompt file at `prompts/<skill_name>.md` following the same structural conventions as existing prompt files.

**FR-503** [E, M, Part 5]  
When a query requiring the new skill is submitted, the Planner shall emit the new skill as a node in the DAG, and the Executor shall dispatch it through the standard `run_skill` path without any `flow.py` or `skills.py` modification.

**FR-504** [UB, M, Part 5]  
If a new skill implementation requires adding a skill-name branch (`if skill.name == "<new>"`) to `flow.Executor`, the implementation shall be considered non-conformant to the architectural rule: adding a skill is a YAML edit and a prompt file only.

---

### 5.6 Submission

**FR-601** [U, M, Submission]  
The student shall submit a YouTube demo video that clearly shows Parts 1–5 with terminal output legible on screen.

**FR-602** [U, M, Submission]  
The student shall update `README.md` with gateway log excerpts or terminal screenshots confirming results for all five parts.

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

**CON-104** — Gateway V7 (`gateway/` on port 8107) must remain untouched.

**CON-105** — The `Graph` must remain acyclic: `Graph.add_node` only adds edges from a predecessor node to the new node; a node cannot reference itself or a descendant as an input.

**CON-106** — `MAX_NODES = 60` in `flow.py` must not be increased as a workaround for a looping Planner. If the cap fires, the root cause must be fixed in the prompt.

---

## 8. Traceability Matrix

| Req ID | Summary | Assignment Part | Primary File(s) | Test / Verification |
|---|---|---|---|---|
| FR-101 | hello ≤ 3 s, 2 nodes | Part 1 | `flow.py`, `prompts/planner.md` | demo / timing log |
| FR-102 | Shannon bio query | Part 1 | `prompts/researcher.md`, `prompts/distiller.md` | demo / log |
| FR-103 | Populations parallel, ≤ 90 s | Parts 1 & 2 | `flow.py` (asyncio.gather), `prompts/researcher.md` | demo / timing log |
| FR-104 | Graceful fail on bad path | Part 1 | `prompts/planner.md` | demo / log |
| FR-105 | SIGKILL + resume | Part 1 | `flow.py`, `persistence.py` | demo / log |
| FR-201 | Planner emits ≥ 3 parallel nodes | Part 2 | `prompts/planner.md`, `flow.Graph.extend_from` | demo / log |
| FR-202 | Wall-clock = max not sum | Part 2 | `flow.Executor.run` (gather) | demo / timing table |
| FR-203 | Shared finish timestamp in log | Part 2 | `flow.Executor.run` stdout | demo / log |
| FR-301 | Critic inserted for constraint queries | Part 3 | `prompts/planner.md`, `flow.Graph.extend_from` | demo / log |
| FR-302 | Critic-fail → child skipped + recovery | Part 3 | `recovery.handle_critic_verdict` | `test_recovery.py` lines 97–135 |
| FR-303 | Pass + fail demonstrated across 2 runs | Part 3 | `prompts/critic.md` | demo / 2 × log |
| FR-304 | Per-target cap = 1 re-plan | Part 3 | `recovery.handle_critic_verdict` | `test_recovery.py` |
| FR-401 | coder.md complete prompt | Part 4 | `prompts/coder.md` | code review / demo |
| FR-402 | internal_successors auto-appends sandbox | Part 4 | `agent_config.yaml`, `flow.Graph.extend_from:133` | demo / log |
| FR-403 | sandbox_executor runs code field | Part 4 | `skills.run_skill` (sandbox branch) | demo / stdout |
| FR-404 | sandbox_executor fails on missing code | Part 4 | `skills.run_skill:257` | demo / log |
| FR-405 | Coder on computation query | Part 4 | `prompts/coder.md`, `sandbox.py` | demo / sandbox stdout |
| FR-501 | New skill in agent_config.yaml | Part 5 | `agent_config.yaml` | code review |
| FR-502 | New skill prompt file | Part 5 | `prompts/<new>.md` | code review |
| FR-503 | New skill dispatched, no Executor change | Part 5 | `flow.py` (unchanged), `skills.py` (unchanged) | demo / diff |
| FR-504 | No Executor branch for new skill | Part 5 | `flow.py` | code review / `git diff` |
| FR-601 | YouTube demo | Submission | — | instructor view |
| FR-602 | README.md logs | Submission | `README.md` | instructor review |
| NFR-101 | 22 tests pass before and after | All | `tests/test_recovery.py` | `uv run pytest` |
| NFR-201 | Fewer tokens than S7 | Part 2 | Gateway `/v1/cost/by_agent` | log comparison |
| NFR-301 | Atomic writes | All | `persistence.py` | architecture review |
| NFR-401 | Sandbox 1 MB / 30 s cap | Part 4 | `sandbox.py` | code review |
| NFR-501 | Node-boundary resume | Part 1 | `persistence.py`, `flow.Executor.run:172` | demo |
| CON-101 | S7 modules byte-identical | All | 7 carry-over files | `git diff` |
| CON-102 | No skill-name branch in Executor (Part 5) | Part 5 | `flow.py` | `git diff` |
| CON-103 | Classifier labels stable | All | `recovery.classify_failure` | `test_recovery.py` |
| CON-104 | Gateway V7 untouched | — | `gateway/` | `git diff` |
| CON-105 | Graph acyclic by construction | All | `flow.Graph.add_node` | architecture review |
| CON-106 | MAX_NODES not raised as workaround | All | `flow.py:32` | code review |
