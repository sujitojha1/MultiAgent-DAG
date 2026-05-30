# Architecture Reference — Session 8 Multi-Agent DAG Orchestrator

> Code-focused walkthrough. Every claim is backed by a file:line reference.
> Read alongside `code/flow.py` (300 lines — fits in your head).

---

## 1. File Map

```
code/
├── flow.py          ← THE entry point. Graph + Executor + CLI. Read this first.
├── skills.py        ← Skill loading, prompt rendering, gateway dispatch
├── recovery.py      ← Failure classification + critic-fail splice
├── persistence.py   ← Atomic session writes (graph.json + per-node JSON)
├── schemas.py       ← Pydantic contracts: AgentResult, NodeSpec, NodeState
├── sandbox.py       ← subprocess Python runner (usability boundary)
├── mcp_runner.py    ← Multi-turn tool-use loop (tool-calling skills)
├── agent_config.yaml← Skill catalogue — the ONLY file you edit to add a skill
└── prompts/
    ├── planner.md   ← Emits JSON DAG; the "program" the Executor runs
    ├── coder.md     ← STUB — your Part 4 work goes here
    ├── critic.md    ← Emits {"verdict":"pass"|"fail","rationale":"..."}
    └── ...          ← one .md per skill
```

**Rule of thumb:** to add a skill → edit `agent_config.yaml` + write `prompts/<name>.md`. Zero Python.

---

## 2. The Three Core Types (`schemas.py`)

These three Pydantic models are the boundaries between every layer.

### `NodeSpec` — what the Planner emits (one per node it wants created)
```python
class NodeSpec(BaseModel):
    skill: str              # matches a key in agent_config.yaml
    inputs: list[str]       # "USER_QUERY" | "n:<label>" | "art:<id>"
    metadata: dict          # opaque bag — label, question, failure_report …
```

### `AgentResult` — what every skill returns
```python
class AgentResult(BaseModel):
    success: bool
    agent_name: str
    output: dict            # skill-specific JSON payload
    successors: list[NodeSpec]  # dynamic children this skill wants added
    elapsed_s: float
    error: str | None
```

### `NodeState` — what gets persisted to disk per node
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

**Data flow:** `NodeSpec` → Executor creates node → skill runs → `AgentResult` → Executor persists as `NodeState`.

---

## 3. The `Graph` Class (`flow.py:37–149`)

A thin wrapper around `networkx.DiGraph`. Nodes are strings `"n:1"`, `"n:2"`, …

### 3.1 How a node is created (`Graph.add_node`, line 45)

```python
def add_node(self, skill, inputs, metadata=None) -> str:
    self._counter += 1
    nid = f"n:{self._counter}"                      # always monotone — never gaps
    self.g.add_node(nid, skill=skill, inputs=list(inputs),
                    metadata=dict(metadata or {}), status="pending")
    for inp in inputs:
        if inp.startswith("n:") and inp in self.g.nodes:
            self.g.add_edge(inp, nid)               # edge = dependency
    return nid
```

**Key:** an edge `A → B` means "B cannot run until A is complete or skipped."

### 3.2 How ready nodes are found (`Graph.ready_nodes`, line 58)

```python
def ready_nodes(self) -> list[str]:
    out = []
    for nid, d in self.g.nodes(data=True):
        if d["status"] != "pending":
            continue
        preds = list(self.g.predecessors(nid))
        # complete OR skipped — skipped unblocks the path so unrelated
        # branches downstream don't stall on a critic-failed branch
        if all(self.g.nodes[p]["status"] in ("complete", "skipped") for p in preds):
            out.append(nid)
    return out
```

**All returned nodes run concurrently.** `skipped` is as good as `complete` for unblocking.

### 3.3 How the graph grows (`Graph.extend_from`, line 74)

Called after every successful node. Does three things in order:

```
1. ADD DYNAMIC SUCCESSORS
   result.successors (NodeSpec list) → new nodes
   resolves n:<label> → n:<int> so the Planner can use human names

2. ADD STATIC SUCCESSORS (internal_successors from yaml)
   e.g. coder → [sandbox_executor] added automatically, no Planner needed

3. CRITIC AUTO-INSERTION (if skill has critic: true)
   For each new child:
     - remove edge  src → child
     - add critic node with inputs=[src]
     - add edge     critic → child
   Child now waits for Critic, not directly for src
```

**Example — Distiller (critic: true) with one child:**
```
Before extend_from:   distiller → formatter
After extend_from:    distiller → critic → formatter
```

---

## 4. The `Executor` Loop (`flow.py:154–291`)

```python
# Simplified pseudocode — actual loop is flow.py:206–271
while True:
    ready = graph.ready_nodes()
    if not ready and not graph.has_running():
        break                                    # done

    for nid in ready:
        graph.mark(nid, "running")
    store.write_graph(graph.g)                   # persist before dispatch

    outcomes = await asyncio.gather(             # ALL ready nodes fire at once
        *[self._run_one(nid, ...) for nid in ready]
    )

    for nid, result, prompt in outcomes:
        graph.g.nodes[nid]["result"] = result
        graph.mark(nid, "complete" if result.success else "failed")
        store.write_node(NodeState(...))         # persist node state

        if result.success:
            if skill == "critic":
                handle_critic_verdict(...)       # may mark child skipped + queue recovery
            graph.extend_from(nid, result, ...)  # grow the graph
            if skill == "formatter":
                formatter_answer = result.output["final_answer"]
        else:
            decision = plan_recovery(...)        # classify: skip or replan
            if decision.action == "replan":
                graph.add_node("planner", ...)   # splice recovery planner
```

**Two things keep this loop finite:**
1. `MAX_NODES = 60` (hard cap, `flow.py:32`) — a looping Planner hits this
2. Per-target cap in `recovered_branches` dict — Critic-fail can only trigger one recovery per branch

---

## 5. Skill Execution (`skills.py:230–338`)

`run_skill` has two dispatch paths based on `skill.name`:

### Path A — `sandbox_executor` (no LLM call)
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

### Path B — All other skills (LLM call via gateway)
```python
tools = tool_payload(skill.tools_allowed)
if tools:
    reply = await run_with_tools(...)   # mcp_runner — multi-turn tool loop
else:
    reply = await asyncio.to_thread(LLM().chat, ...)  # single-turn
parsed = parse_skill_json(reply["text"])
```

### How the prompt is built (`skills.render_prompt`, line 146)
```
[skill system prompt from prompts/<name>.md]
USER_QUERY: <original query>
[FAILURE: <failure_report> if this is a recovery run]
MEMORY HITS (N from FAISS):
  - [fact] descriptor  /  source  /  chunk preview …
INPUTS:
[JSON array of resolved upstream outputs]
```

**The INPUTS block** is what one node "sees" from its predecessors — not the full history. This is why S8 uses far fewer tokens than S7.

---

## 6. Failure & Recovery (`recovery.py`)

### `classify_failure(error_text)` — three buckets

| Return value | Triggers | What the Executor does |
|---|---|---|
| `"transient"` | 503, 502, 504, timeout, connection | `skip` — gateway already retried |
| `"validation_error"` | "malformed", "ValidationError" | `skip` — fix the prompt, not the run |
| `"upstream_failure"` | everything else | `replan` — queue recovery Planner |

**Why planner failures always skip:**
```python
if failed_skill == "planner":
    return RecoveryDecision(action="skip", ...)  # no infinite Planner loop
```

### `handle_critic_verdict` — critic-fail splice

```
Critic returns verdict="fail"
    → mark child node "skipped"
    → if target not in recovered_branches:
          add new planner node with failure_report
          set recovered_branches[target] = True
      else:
          cap hit → log warning, branch stays missing
```

---

## 7. Persistence (`persistence.py`)

Session directory layout:
```
state/sessions/<sid>/
├── query.txt           # original query verbatim
├── graph.json          # nx.node_link_data — the full graph
└── nodes/
    ├── n_001.json      # NodeState for n:1 (planner)
    ├── n_002.json      # NodeState for n:2
    └── …
```

**Atomic write pattern** (write-tmp, os.replace):
```python
tmp = path.with_suffix(".tmp")
tmp.write_text(json.dumps(data))
os.replace(tmp, path)              # atomic on POSIX — previous file safe on kill
```

**Resume** (`flow.Executor.run`, line 163):
```python
if resume:
    graph_obj = store.read_graph()
    for _, d in graph.g.nodes(data=True):
        if d["status"] == "running":
            d["status"] = "pending"  # re-run any node that was in-flight
```

---

## 8. How to Add a New Skill (Two-File Rule)

1. **`agent_config.yaml`** — add an entry:
```yaml
my_skill:
  prompt: prompts/my_skill.md
  tools_allowed: []          # or [web_search, fetch_url, search_knowledge]
  temperature: 0.3
  max_tokens: 1200
  description: One line.
```

2. **`prompts/my_skill.md`** — write the system prompt. Must end with instructions to output JSON (all skills return JSON; `parse_skill_json` strips markdown fences).

3. **Nothing else.** `SkillRegistry.__init__` loads all yaml entries automatically. The Executor dispatches any skill through the same `run_skill` path.

The only legitimate reason to touch `flow.py` for a new skill is if it needs a **new generic mechanism** (like `internal_successors` or `critic: true` were new mechanisms) — not a one-off `if skill.name == "..."` branch.

---

## 9. The Coder → SandboxExecutor Chain

This is the one pre-wired skill chain. It works through `internal_successors`:

```yaml
# agent_config.yaml
coder:
  internal_successors: [sandbox_executor]
```

```python
# flow.Graph.extend_from (line 133)
for child_skill in src_def.internal_successors:
    nid = self.add_node(child_skill, inputs=[src_nid])
    added.append(nid)
```

**What the Coder prompt must emit:**
```json
{"code": "populations = {'London': 9_541_000, ...}\n...", "rationale": "Compare pairwise distances"}
```

**What sandbox_executor does with it** (`skills.run_skill:252`):
```python
code = r["output"].get("code") or code   # extracted from coder AgentResult.output
out  = run_python(code)                  # sandbox.py: subprocess, 30s timeout, 1MB cap
```

The `sandbox.py` result (`stdout`, `stderr`, `exit_code`) flows back into `AgentResult.output` and is available to the Formatter as an upstream input.
