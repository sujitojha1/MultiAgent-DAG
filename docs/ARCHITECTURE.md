# Architecture Reference — Session 8 Multi-Agent DAG Orchestrator

> [!NOTE]
> Code-focused walkthrough. Every claim is backed by a file:line reference.
> Read alongside `code/flow.py` (300 lines — fits in your head).

---

## 📂 1. Directory File Map

Below is the visual map of the repository, highlighting where major agentic orchestration components reside:

```text
Root/
├── code/
│   ├── flow.py              ← THE entry point. Graph + Executor + CLI. Read this first.
│   ├── skills.py            ← Skill loading, prompt rendering, gateway dispatch.
│   ├── recovery.py          ← Failure classification + critic-fail splice.
│   ├── persistence.py       ← Atomic session writes (graph.json + per-node JSON).
│   ├── schemas.py           ← Pydantic contracts: AgentResult, NodeSpec, NodeState.
│   ├── sandbox.py           ← subprocess Python runner (usability boundary).
│   ├── mcp_runner.py        ← Multi-turn tool-use loop (tool-calling skills).
│   ├── agent_config.yaml    ← Skill catalogue — the ONLY file you edit to add a skill.
│   └── prompts/
│       ├── planner.md       ← Emits JSON DAG; the "program" the Executor runs.
│       ├── coder.md         ← STUB — your Part 4 work goes here.
│       ├── critic.md        ← Emits {"verdict":"pass"|"fail","rationale":"..."}.
│       └── ...              ← One markdown prompt per skill.
```

> [!TIP]
> **The Two-File Rule:** To add a new skill to the catalog, you only need to edit `agent_config.yaml` and create a prompt file under `prompts/<name>.md`. You do **not** need to touch any Python codebase file.

---

## 📐 2. The Three Core Types (`schemas.py`)

These three Pydantic models are the strict, type-safe boundaries between every orchestration layer:

```mermaid
graph LR
    classDef default fill:#1e1e2e,stroke:#313244,stroke-width:1px,color:#cdd6f4;
    classDef type fill:#b4befe,stroke:#89b4fa,stroke-width:1.5px,color:#11111b;
    classDef process fill:#a6e3a1,stroke:#94e2d5,stroke-width:1.5px,color:#11111b;
    classDef file fill:#f9e2af,stroke:#fab387,stroke-width:1.5px,color:#11111b;

    NS[NodeSpec]:::type -->|Planner Emits| G[flow.Graph.add_node]:::process
    G -->|Dispatches Node| AR[AgentResult]:::type
    AR -->|Executor Persists| NS2[NodeState]:::type
    NS2 -->|Atomic Write| SS[(persistence.SessionStore)]:::file
```

### A. `NodeSpec` — Emitted by the Planner
*Represents one node the Planner intends the orchestrator to create.*
```python
class NodeSpec(BaseModel):
    skill: str              # matches a key in agent_config.yaml
    inputs: list[str]       # "USER_QUERY" | "n:<label>" | "art:<id>"
    metadata: dict          # Opaque bag — label, question, failure_report …
```

### B. `AgentResult` — Returned by Every Skill
*The boundary contract returned by `skills.run_skill`.*
```python
class AgentResult(BaseModel):
    success: bool
    agent_name: str
    output: dict            # skill-specific JSON payload
    successors: list[NodeSpec]  # dynamic children this skill wants added
    elapsed_s: float
    error: str | None
```

### C. `NodeState` — Persisted to Disk per Node
*Represents the full history and execution footprint of a single graph vertex.*
```python
class NodeState(BaseModel):
    node_id: str
    skill: str
    status: Literal["pending","running","complete","failed","skipped"]
    inputs: list[str]
    result: AgentResult | None
    prompt_sent: str | None   # exact bytes sent to gateway — load-bearing for replay
    started_at: float | None
    completed_at: float | None
```

---

## 🕸️ 3. The `Graph` Class (`flow.py:37–149`)

A thin wrapper around `networkx.DiGraph` representing the active execution DAG. Nodes are uniquely labeled string keys (`"n:1"`, `"n:2"`, …).

### 3.1 Node Creation (`Graph.add_node`, line 45)
Whenever a node is added, incoming edges are established automatically for any inputs referencing sibling nodes:
```python
def add_node(self, skill, inputs, metadata=None) -> str:
    self._counter += 1
    nid = f"n:{self._counter}"                      # monotone counter key
    self.g.add_node(nid, skill=skill, inputs=list(inputs),
                    metadata=dict(metadata or {}), status="pending")
    for inp in inputs:
        if inp.startswith("n:") and inp in self.g.nodes:
            self.g.add_edge(inp, nid)               # Directed Edge = Context dependency
    return nid
```

### 3.2 Finding Ready Nodes (`Graph.ready_nodes`, line 58)
Finds all nodes whose predecessors are either `complete` or `skipped`, enabling concurrent execution batches:
```python
def ready_nodes(self) -> list[str]:
    out = []
    for nid, d in self.g.nodes(data=True):
        if d["status"] != "pending":
            continue
        preds = list(self.g.predecessors(nid))
        # completed OR skipped predecessors unblock execution
        if all(self.g.nodes[p]["status"] in ("complete", "skipped") for p in preds):
            out.append(nid)
    return out
```

### 3.3 Growing the Graph (`Graph.extend_from`, lines 74–149)

Called by the Executor each time a node completes. It splices in new children in **three sequential steps, in this fixed order**, and returns the list of new node ids:

1. **Dynamic successors** (lines 86–131) — children the skill emitted at runtime (`result.successors`). Added in **two passes**: pass 1 creates each node bare and records its `metadata.label → assigned-id`; pass 2 resolves each child's `inputs`, translating `n:<label>` → assigned id, passing `n:<int>` / `USER_QUERY` / `art:` references through, and falling back to the parent for anything unknown. The label indirection lets the **Planner name nodes symbolically** without knowing the integer ids it will be handed.
2. **Static `internal_successors`** (lines 133–135) — YAML-driven, no runtime data. Every skill of this type gets its listed successors auto-appended off the parent (e.g. `coder → sandbox_executor`), with zero Planner/Executor code change.
3. **Critic auto-insertion** (lines 137–147) — only if the *source* skill is `critic: true`. For each child added in Steps 1–2, it interposes a Critic: cut the `src → child` edge, add a `critic` node fed by `src`, rewire `critic → child`. The child cannot become `ready` until the Critic passes.

```python
def extend_from(self, src_nid, result, *, registry) -> list[str]:
    added = []
    src_def = registry.get(self.g.nodes[src_nid]["skill"])
    # Step 1 — dynamic successors (two-pass: add bare, then resolve label refs)
    ...
    # Step 2 — static internal_successors
    for child_skill in src_def.internal_successors:
        added.append(self.add_node(child_skill, inputs=[src_nid]))
    # Step 3 — critic auto-insertion over a SNAPSHOT of Steps 1+2
    if src_def.critic and added:
        for child_nid in list(added):              # snapshot — no critic-on-critic
            self.g.remove_edge(src_nid, child_nid)
            critic_nid = self.add_node("critic", inputs=[src_nid],
                                       metadata={"target": src_nid, "child": child_nid})
            self.g.add_edge(critic_nid, child_nid)
            added.append(critic_nid)
    return added
```

**Why the order is load-bearing:** Step 3 iterates `list(added)` — a snapshot taken *before* any critics are appended — so it gates **every** child from Steps 1 and 2 (dynamic *and* static), and critics never receive critics of their own. Running critic-insertion between Steps 1 and 2 would let the `internal_successors` children slip through ungated; the ordering is what makes the Critic a *complete* gate. These are three of the **five growth actors** in the `flow.py` module docstring — the other two being the Planner's seed plan and `recovery.plan_recovery` re-invocation on node failure (§6).

---

## 🔄 4. The `Executor` Loop (`flow.py:154–291`)

The main runtime loop handles parallel node dispatching, state persistence boundaries, and dynamic graph growth.

```mermaid
graph TD
    classDef default fill:#1e1e2e,stroke:#313244,color:#cdd6f4;
    classDef start fill:#f9e2af,stroke:#fab387,stroke-width:1.5px,color:#11111b;
    classDef check fill:#f5c2e7,stroke:#cba6f7,stroke-width:1.5px,color:#11111b;
    classDef run fill:#b4befe,stroke:#89b4fa,stroke-width:1.5px,color:#11111b;
    classDef recovery fill:#f38ba8,stroke:#eba0ac,stroke-width:1.5px,color:#11111b;

    S([Start Executor Loop]):::start --> R{Get Ready Nodes}:::check
    R -->|Empty & None Running| E([End Loop]):::start
    R -->|Has Ready Nodes| M[Mark Nodes 'running']:::run
    M --> P[Persist Graph]:::run
    P --> G[asyncio.gather Dispatch]:::run
    G --> O{Did Node Succeed?}:::check
    
    O -->|Yes| EX[Extend Graph successors]:::run
    EX --> PE[Persist Node complete]:::run
    PE --> R
    
    O -->|No| CL[Classify Failure]:::recovery
    CL --> RE{Recovery Action?}:::check
    RE -->|Skip| R
    RE -->|Replan| SP[Splice Recovery Planner Node]:::recovery
    SP --> R
```

### 4.1 Loop Guards
To prevent infinite execution loops (e.g., a looping Planner), two strict bounds are enforced:
1. `MAX_NODES = 60` (`flow.py:32`): A hard maximum cap on the graph's node count.
2. **Per-Target Cap:** The `recovered_branches` dictionary limits Critic-failed recovery planners to at most one re-plan per branch.

---

## 🛠️ 5. Skill Execution (`skills.py:230–338`)

`run_skill` contains two programmatic routing branches based on `skill.name`:

### Path A — `sandbox_executor` (No LLM Call)
Extracts Python source code from upstream and runs it inside a secure sandbox container:
```python
if skill.name == "sandbox_executor":
    code = ""
    for r in resolved:
        if r.get("kind") == "upstream":
            code = r["output"].get("code") or code
    if not code:
        return AgentResult(success=False, error="no code in upstream coder output")
    out = run_python(code)              # sandbox.py subprocess
    return AgentResult(success=(out["exit_code"] == 0), output=out)
```

### Path B — All Other Skills (LLM Call via Gateway)
Constructs the scoped system prompt injecting FAISS memory hits and upstream resolved output data before executing the model call via port `8108`.

---

## 🚨 6. Failure & Recovery (`recovery.py`)

### 6.1 Failure Classification (`classify_failure`)
Classifies gateway error payloads into three categories, deciding whether to retry, skip, or trigger recovery:

```mermaid
graph TD
    classDef default fill:#1e1e2e,stroke:#313244,color:#cdd6f4;
    classDef check fill:#f5c2e7,stroke:#cba6f7,stroke-width:1.5px,color:#11111b;
    classDef action fill:#a6e3a1,stroke:#94e2d5,stroke-width:1.5px,color:#11111b;
    classDef replan fill:#f38ba8,stroke:#eba0ac,stroke-width:1.5px,color:#11111b;

    E[Gateway Error String] --> C{Error Type?}:::check
    C -->|5xx / Timeout / Conn| T[Transient Error]:::action
    C -->|ValidationError / Malformed JSON| V[Validation Error]:::action
    C -->|Other Error| U[Upstream Failure]:::replan
    
    T -->|Executor Action| S1[SKIP Node]:::action
    V -->|Executor Action| S2[SKIP Node]:::action
    U -->|Executor Action| RP[REPLAN - Spawn Recovery Planner]:::replan
```

### 6.2 Critic Verdict Splicing (`handle_critic_verdict`)
Spliced automatically on edges of nodes with `critic: true` in YAML.

<img src="../images/critic_loop_diagram.png" width="550" alt="Multi-Agent Critic Loop" />

When a Critic node returns a `fail` verdict:
1. The target child is marked `skipped` to bypass the broken branch.
2. A new Planner node is dynamically queued, injected with the failure rationale.
3. The branch is re-planned (limited by a strict per-target recovery cap of 1).

---

## 💾 7. Persistence Layer (`persistence.py`)

### 7.1 Atomic Write Pattern
To protect session records from data corruption if the system process is terminated mid-write, a strict **atomic swap** pattern is implemented:
```python
tmp = path.with_suffix(".tmp")
tmp.write_text(json.dumps(data))
os.replace(tmp, path)              # POSIX-compliant atomic file system swap
```

### 7.2 Resume Safety
Upon resuming an interrupted session via `flow.py --resume <sid>`, any node that was left in the `running` state at crash time is reset to `pending` and re-executed cleanly from its boundary.

---

## 📦 8. Coder → SandboxExecutor Chain

The static execution chain is automatically declared using `internal_successors` in the skill YAML catalog:

<img src="../images/sandbox_environment.png" width="550" alt="Secure Sandbox Environment for AI Code Execution" />

1. **Coder** emits a JSON payload matching the contract: `{"code": "<python source>", "rationale": "..."}`.
2. **`internal_successors`** appends `sandbox_executor` automatically.
3. **`sandbox_executor`** runs the Python script in a throwaway directory with a **30-second timeout**, a **1 MB output cap**, and an **environment whitelist** (`PATH`, `HOME`, `LANG`, `LC_ALL`, `LC_CTYPE`) to scrub API keys and keep execution isolated.
