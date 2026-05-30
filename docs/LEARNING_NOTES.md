# Learning Notes — Session 8: Multi-Agent DAG Orchestration

> Style: codebase-to-course — every concept is paired with the exact code that implements it,
> followed by a plain-English translation and a data-flow annotation.
> Read these alongside `ARCHITECTURE.md` for the full reference.

---

## Module 1 — How a Query Becomes a Graph

### 1.1 Entry Point: `flow.py main()`

```python
# flow.py:313-321
def main() -> None:
    args = sys.argv[1:]
    resume_sid: str | None = None
    if args and args[0] == "--resume":
        resume_sid = args[1] if len(args) > 1 else None
        query = " ".join(args[2:])
    else:
        query = " ".join(args) or "Say hello in one short sentence."
    asyncio.run(Executor().run(query, session_id=resume_sid, resume=bool(resume_sid)))
```

**Plain English:** `main` collects the query from the command line, detects the `--resume` flag, then hands both to `Executor.run` inside an asyncio event loop. The whole graph execution is one `await`.

**Data flow:**
```
CLI args → query string + optional session_id → asyncio.run(Executor.run(...))
```

---

### 1.2 Session Startup: memory + first node

```python
# flow.py:179-195
store.write_query(query)
graph = Graph()
graph.add_node("planner", inputs=["USER_QUERY"])   # ← node n:1 always

memory_hits = memory_svc.read(query) or []         # FAISS lookup ONCE per session
memory_svc.remember(query, source="user_query", run_id=sid)
```

**Plain English:** Before dispatching anything, the orchestrator:
1. Writes the query to disk so resume can recover it.
2. Creates a blank graph with exactly one node: the Planner.
3. Reads FAISS memory ONCE. The same `memory_hits` list is threaded into EVERY skill's prompt for this session — not re-read per node.

**Why read memory only once?** Each skill sees the same knowledge snapshot. Re-reading would produce different hits mid-session if the graph inserts new memory items, which would be confusing for debugging.

---

### 1.3 The Planner's Job: writing the program

The Planner skill returns a JSON object. Here is a real example for the London/Paris/Berlin populations query:

```json
{
  "rationale": "Three populations, then pairwise comparison.",
  "nodes": [
    {"skill":"researcher","inputs":["USER_QUERY"],
     "metadata":{"label":"london","question":"What is the current population of London?"}},
    {"skill":"researcher","inputs":["USER_QUERY"],
     "metadata":{"label":"paris","question":"What is the current population of Paris?"}},
    {"skill":"researcher","inputs":["USER_QUERY"],
     "metadata":{"label":"berlin","question":"What is the current population of Berlin?"}},
    {"skill":"coder","inputs":["n:london","n:paris","n:berlin"],
     "metadata":{"label":"compare"}},
    {"skill":"formatter","inputs":["n:compare"],"metadata":{"label":"out"}}
  ]
}
```

**Plain English:** The Planner is a program generator. Its output IS the execution plan. The Executor reads this JSON, creates nodes, resolves `n:<label>` references into real node IDs, and wires edges. This is the "meta-level shift" from S7 — the model no longer runs inside a loop, it writes the loop.

**What `n:london` means:** The Planner uses human-readable labels. `Graph.extend_from` builds a `label_to_id` map so `"n:london"` resolves to `"n:3"` (or whatever integer the counter assigned). Code: `flow.py:87–131`.

---

## Module 2 — The Graph Data Structure

### 2.1 What lives in a NetworkX node

```python
# flow.py:48-49
self.g.add_node(nid,
    skill   = skill,            # "researcher", "coder", etc.
    inputs  = list(inputs),     # ["USER_QUERY"] or ["n:3", "n:4"]
    metadata= dict(metadata),   # label, question, failure_report, etc.
    status  = "pending"         # state machine
)
```

**Five possible statuses:**
```
pending  → running  → complete
                    → failed   → (recovery planner added)
         → skipped             ← set by critic-fail handler
```

### 2.2 What an edge means

```python
# flow.py:51-52
for inp in inputs:
    if inp.startswith("n:") and inp in self.g.nodes:
        self.g.add_edge(inp, nid)     # directed: inp → nid
```

**Plain English:** An edge from A to B means "B must wait for A." If the Planner says `{"inputs": ["n:london", "n:paris"]}`, two edges are added: `n:london → coder` and `n:paris → coder`. The coder node stays `pending` until both predecessors are `complete` or `skipped`.

### 2.3 Visualising a DAG for the populations query

```
n:1  planner
 ├──▶ n:2  researcher(london)  ─┐
 ├──▶ n:3  researcher(paris)   ─┼──▶ n:5  coder ──▶ n:6  formatter
 └──▶ n:4  researcher(berlin)  ─┘          └──▶ n:7  sandbox_executor
                                                 (auto-added by internal_successors)
```

**Why n:7 appears after n:5 even though the Planner didn't ask for it:**
`agent_config.yaml` has `coder: internal_successors: [sandbox_executor]`. After the coder node completes, `Graph.extend_from` appends `sandbox_executor` with `inputs=[n:5]` — no Planner involvement.

---

## Module 3 — Parallel Execution: `asyncio.gather`

### 3.1 The gather call

```python
# flow.py:218-219
outcomes = await asyncio.gather(
    *[self._run_one(nid, ...) for nid in ready]
)
```

**Plain English:** `asyncio.gather` runs all `_run_one` coroutines concurrently. Because each `_run_one` makes async HTTP calls to the LLM gateway, Python can interleave them — London, Paris, and Berlin researchers all start within milliseconds of each other and run simultaneously.

### 3.2 The barrier effect (from the timing table)

```
node    skill        start(rel)  elapsed  finish(rel)
n:2     researcher     2.18 s    40.50 s    42.69 s
n:3     researcher     5.80 s    36.89 s    42.69 s   ← same finish
n:4     researcher    10.26 s    32.43 s    42.69 s   ← same finish
```

All three finish at 42.69 s — the `gather` barrier. The wall-clock cost of the parallel layer is `max(40.50, 36.89, 32.43) = 40.50 s`, not `40.50 + 36.89 + 32.43 = 109.82 s`.

**Serial overhead is NOT parallelised:**
```
planner (2.18 s) + coder (18.56 s) + formatter (1.14 s) = 21.88 s   must be sequential
parallel layer cost                                      = 40.50 s
total wall-clock                                         ≈ 62.40 s
```

### 3.3 Why S8 uses fewer tokens than S7

S7: every iteration sends full cumulative history to Perception + Decision.
```
iteration 10 prompt size ≈ 9 iterations × avg_output ≈ O(n²) tokens
```

S8: each node sees only its direct upstream outputs (the `INPUTS:` block in the prompt).
```
researcher sees: USER_QUERY only
coder sees:      AgentResult.output from n:2, n:3, n:4
formatter sees:  AgentResult.output from coder
```
Each scope is bounded — no accumulation. Result: 17k tokens vs 54k tokens for the same query.

---

## Module 4 — Skills: From YAML to Gateway Call

### 4.1 What defines a skill (everything is in YAML)

```yaml
# agent_config.yaml
researcher:
  prompt: prompts/researcher.md    # system prompt
  tools_allowed: [web_search, fetch_url]
  temperature: 0.7
  max_tokens: 2500
  description: Performs multi-step web research.
```

```python
# skills.py:38-53 — Skill.__init__ reads exactly these fields
class Skill:
    def __init__(self, name, cfg):
        self.prompt_path      = ROOT / cfg["prompt"]
        self.tools_allowed    = cfg.get("tools_allowed", [])
        self.internal_successors = cfg.get("internal_successors", [])
        self.critic           = bool(cfg.get("critic", False))
        self.temperature      = float(cfg.get("temperature", 0.3))
        self.max_tokens       = int(cfg.get("max_tokens", 2048))
```

**Plain English:** The `Skill` object is a data bag loaded from YAML. No per-skill Python logic. `SkillRegistry` loads ALL yaml entries at startup — adding a new entry means the new skill is instantly available to the Planner.

### 4.2 Prompt rendering — what the LLM actually receives

```python
# skills.py:149-159
def render_prompt(skill, query, resolved, failure_report, memory_hits):
    parts = [
        skill.prompt_template().rstrip(),   # system prompt from .md file
        "",
        f"USER_QUERY: {query}",
        "",
        f"FAILURE:\n{failure_report}" if failure_report else None,
        f"MEMORY HITS ({len(memory_hits)} from FAISS):\n{hits_block}" if memory_hits else None,
        "",
        "INPUTS:",
        json.dumps(resolved, indent=2)[:20_000]
    ]
    return "\n".join(p for p in parts if p is not None)
```

**Plain English:** The prompt has four sections stacked vertically:
1. **System prompt** (from `.md` file) — the skill's persona and output contract
2. **USER_QUERY** — the original query, always present
3. **FAILURE** — only on recovery runs; tells the Planner what went wrong
4. **MEMORY HITS** — FAISS-ranked knowledge from this session's memory read
5. **INPUTS** — the upstream node outputs this skill should work with

### 4.3 Two dispatch paths in `run_skill`

```python
# skills.py:251-294 (simplified)
if skill.name == "sandbox_executor":
    code = upstream_coder_output.get("code")
    return sandbox.run_python(code)          # NO LLM CALL

elif skill.tools_allowed:
    return await run_with_tools(...)         # multi-turn tool loop (mcp_runner)

else:
    return LLM().chat(...)                   # single-turn text
```

**The `if skill.name == "sandbox_executor"` is the ONLY legitimate skill-name branch in the codebase.** It exists because sandbox_executor fundamentally cannot go through the LLM gateway — it runs Python. Any new skill you add must NOT add another branch here.

---

## Module 5 — Coder Skill: Your Part 4 Work

### 5.1 What the Coder must output

```json
{"code": "...", "rationale": "one line"}
```

The `"code"` field is extracted verbatim by `sandbox_executor`:
```python
# skills.py:254-255
for r in resolved:
    if r.get("kind") == "upstream":
        code = r["output"].get("code") or code
```

**If `code` is empty or missing:**
```python
# skills.py:257-261
if not code:
    return AgentResult(success=False, error="no code in upstream coder output")
```
This surfaces clearly in the Executor log: `[n:7] sandbox_executor failed  err=no code in upstream coder output`.

### 5.2 What a good Coder prompt teaches the LLM

Your `prompts/coder.md` must tell the model:
1. Its role: receive text data from upstream nodes, write Python that computes the answer
2. The exact output JSON shape (`{"code": "...", "rationale": "..."}`)
3. Coding constraints: no external libraries beyond stdlib, no network calls, print the final answer to stdout
4. That markdown fences around the JSON are forbidden (the `parse_skill_json` stripper handles them but it's cleaner without)

### 5.3 The chain in the graph

```
coder (n:5)   status=complete   output={"code":"...", "rationale":"..."}
    │
    └──▶ sandbox_executor (n:7)   [auto-added by internal_successors]
              │
              └─ runs subprocess → output={"stdout":"London closest...", "exit_code":0}
                      │
                      └──▶ formatter sees both coder.output and sandbox_executor.output
```

---

## Module 6 — Critic: Pass, Fail, Recovery

### 6.1 When does a Critic node appear?

Two ways:

**Auto-inserted (distiller has `critic: true` in yaml):**
```python
# flow.Graph.extend_from:139-147
if src_def.critic and added:
    for child_nid in list(added):
        self.g.remove_edge(src_nid, child_nid)           # break direct edge
        critic_nid = self.add_node("critic", inputs=[src_nid],
                                   metadata={"target":src_nid, "child":child_nid})
        self.g.add_edge(critic_nid, child_nid)           # critic gates the child
```

**Planner-emitted:** The Planner prompt says "when the user demands a strict format constraint, insert a critic node between the writing node and the formatter." The Planner emits the critic as a `NodeSpec` with `inputs=[writing_node_id]`.

### 6.2 Critic verdict handling

```python
# recovery.handle_critic_verdict (recovery.py:97-135)
if verdict == "fail":
    graph.mark(child_nid, "skipped")           # block the next step
    if target not in recovered_branches:
        recovered_branches[target] = True
        graph.add_node("planner", inputs=["USER_QUERY"],
                       metadata={"failure_report": rationale, "recovers": target})
    else:
        cap_hit.append(target)                 # second fail → give up gracefully
```

**Plain English state machine:**
```
critic.verdict = "pass"  →  child runs normally
critic.verdict = "fail"  →  child skipped
                          →  recovery planner queued (first fail only)
                          →  recovery planner runs, makes new subgraph
                          →  new subgraph runs → formatter → answer
```

### 6.3 The rubber-stamp finding (from session notes)

With the query: *"Write a haiku exactly 4-6-4 syllables (not 5-7-5)"*, the Critic approved a 5-7-5 poem three times in a row. Why? The Critic prompt asks the LLM to count syllables, but LLMs don't count syllables — they pattern-match on the keyword "4-6-4" and approve.

**Fix options:**
1. Give the Critic an MCP tool that actually counts syllables (tool call in the Critic's `tools_allowed`)
2. Use a query property the LLM CAN verify: JSON validity, presence of a keyword, numeric comparison

**Lesson for Part 3:** Choose a Critic constraint that the LLM can reliably evaluate (e.g., "answer contains fewer than 280 characters", "output is valid JSON", "answer mentions all three cities"). Avoid precise counting of phonemes, characters, or exact arithmetic.

---

## Module 7 — Adding the `course_generator` Skill (Part 5)

This is the new skill proposed for Part 5, inspired by [zarazhangrui/codebase-to-course](https://github.com/zarazhangrui/codebase-to-course).

### 7.1 What it does

A `course_generator` skill takes upstream researcher or distiller outputs (text about a codebase or topic) and produces a structured educational markdown module: concept explanation, annotated code, data-flow diagram in ASCII, and a quiz question.

### 7.2 YAML entry

```yaml
# agent_config.yaml — new entry
course_generator:
  prompt: prompts/course_generator.md
  tools_allowed: []              # text-only; receives upstream text as INPUTS
  temperature: 0.5
  max_tokens: 2000
  description: Converts upstream research or distilled content into a structured educational module with code annotations, data-flow diagrams, and quiz questions.
```

### 7.3 Why this satisfies the architectural rule

- Zero Executor changes: `course_generator` dispatches through the standard `LLM().chat` path (no tools, no special-case branch)
- Zero `skills.py` changes: `SkillRegistry` picks it up automatically from yaml
- The Planner can emit it as any other node: `{"skill":"course_generator","inputs":["n:distiller_output"]}`

### 7.4 Example query

```
"Explain how the graph.extend_from method works in the S8 orchestrator. 
Format the explanation as a course module with code, a data-flow diagram, and one quiz question."
```

Expected DAG:
```
planner → retriever(search_knowledge) → distiller → course_generator → formatter
```

---

## Quick Reference: The Five Graph Growth Mechanisms

| # | Trigger | Code location | Who controls it |
|---|---|---|---|
| 1 | Session start | `flow.py:181` | Hardcoded: always `planner` as n:1 |
| 2 | Skill returns `AgentResult.successors` | `Graph.extend_from:89-131` | The skill's LLM output |
| 3 | `internal_successors` in yaml | `Graph.extend_from:133-135` | YAML entry |
| 4 | `critic: true` in yaml | `Graph.extend_from:139-147` | YAML entry |
| 5 | Node failure → `plan_recovery` returns "replan" | `flow.py:262-270` | `recovery.py` classifier |

## Quick Reference: When Nodes Get Skipped (not failed)

| Trigger | Code |
|---|---|
| Critic returns `verdict="fail"` | `recovery.handle_critic_verdict` marks child `skipped` |
| `plan_recovery` returns `action="skip"` (transient or validation error) | `flow.py:257-260` — node marked `failed`, no recovery queued |

Note: `failed` and `skipped` are different. A `failed` node can trigger recovery. A `skipped` node unblocks its successors as if it had completed.
