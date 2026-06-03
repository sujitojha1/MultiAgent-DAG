# Module 3: The Graph That Grows Itself

> Write to `course/modules/03-the-growing-graph.html`. Output ONLY the `<section class="module" id="module-3">…</section>` block. Module 3 = odd → `style="background: var(--color-bg-warm)"`.

### Teaching Arc
- **Metaphor:** A **relay race where the track builds itself as runners arrive**. Each runner (skill) finishes their leg and *lays down the next stretch of track* for whoever comes next. Some legs split into several lanes run side by side; the next runner only starts once everyone feeding into them has passed the baton. The finish line isn't drawn in advance — it appears as the race unfolds.
- **Opening hook:** "In Module 1 a 'hello' used 2 specialists and a research question used 4. Nobody wrote those two different pipelines by hand. So where do they come from? The agent *grows its own plan while it runs*."
- **Key insight:** The agent's plan is a **graph** — boxes (nodes = skill jobs) connected by arrows (edges = 'this must finish before that starts'). It is a **DAG** (no loops — arrows never circle back). Crucially the graph **grows at runtime**: a finished skill can splice in new boxes. And any boxes with no unfinished arrows pointing into them **run at the same time**.
- **"Why should I care?":** "Run in parallel where possible, wait only where you must" is the core idea behind why some AI workflows are fast and others crawl. Understanding the dependency graph lets you reason about speed ("why is this slow? what is it waiting on?") and lets you describe workflows precisely to AI tools ("these three steps have no dependency — do them concurrently").

### Core narrative (4–6 screens)
1. **Boxes and arrows** — Define node (one skill job) and edge (a dependency: the arrow means "the answer flows this way, and the second box waits for the first"). Define **DAG**: directed (arrows have direction), acyclic (no cycles). Hero static diagram: the Shannon graph from Module 1 as 4 connected boxes. Use the architecture diagram or a flow diagram.
2. **The graph starts as a single seed** — One box: the Planner, fed your question. Everything else is grown. Show the seed snippet (below). Tie back to Module 1.
3. **A finished skill lays new track** — When a node finishes, the orchestrator calls `extend_from` to splice in the successors that node asked for. Show the *concept* of "add the new boxes, then wire their arrows" — use Snippet B (the add-node core) for the code↔English block; describe `extend_from` in prose rather than pasting all 80 lines.
4. **Parallel lanes (the hero moment)** — How does the agent know what can run together? Anything whose feeding boxes are all done is "ready," and all ready boxes fire **at once**. Show Snippet C (`ready_nodes`) and Snippet D (the `asyncio.gather` line). Ground it in the real numbers from the README: three city-population researchers ran concurrently — the layer took **27.3s** (the slowest branch) instead of **69.9s** (the three added up) — a **2.56× speed-up**. This is the module's centerpiece; pair the code with the data-flow OR group-chat animation.
5. **Why no loops** — DAG = acyclic on purpose: a plan that could point back at itself could run forever. There's even a hard cap (`MAX_NODES = 60`) so a misbehaving Planner can't grow the graph endlessly. Short screen + config badge.

### Code Snippets (pre-extracted — use verbatim)

**Snippet A — the seed (one starting box).** File: `code/flow.py` (lines 184–186):
```python
            store.write_query(query)
            graph = Graph()
            graph.add_node("planner", inputs=["USER_QUERY"])
```
English: save the question, create an empty graph, drop in exactly ONE node — the Planner — wired to your question. The plan is now a single box.

**Snippet B — adding a box and auto-wiring its arrows (hero translation block).** File: `code/flow.py` (lines 45–53):
```python
    def add_node(self, skill: str, inputs: list[str], metadata: dict | None = None) -> str:
        self._counter += 1
        nid = f"n:{self._counter}"
        self.g.add_node(nid, skill=skill, inputs=list(inputs),
                        metadata=dict(metadata or {}), status="pending")
        for inp in inputs:
            if inp.startswith("n:") and inp in self.g.nodes:
                self.g.add_edge(inp, nid)
        return nid
```
English angle: give the new box a unique name like `n:5`; record which skill it runs, what it reads, and mark it `pending` (not started). Then for every input that is another box (`n:…`), draw an arrow from that box to this one. So inputs literally become the dependency arrows.

**Snippet C — what is allowed to run right now.** File: `code/flow.py` (lines 58–69):
```python
    def ready_nodes(self) -> list[str]:
        # A predecessor counts as "satisfied" when it is either complete or
        # skipped (the latter is how a Critic-fail removes a child from the
        # critical path without blocking unrelated branches downstream).
        out = []
        for nid, d in self.g.nodes(data=True):
            if d["status"] != "pending":
                continue
            preds = list(self.g.predecessors(nid))
            if all(self.g.nodes[p]["status"] in ("complete", "skipped") for p in preds):
                out.append(nid)
        return out
```
English angle: look at every not-yet-started box; if every box with an arrow into it has already finished (or was skipped), it is "ready." Return the whole ready list — these can all go now.

**Snippet D — running the ready boxes together.** File: `code/flow.py` (lines 223–224):
```python
            outcomes = await asyncio.gather(*[self._run_one(nid, graph, sid, query, store, memory_hits)
                                              for nid in ready])
```
English angle: `asyncio.gather` launches every ready box at the same time and waits for all of them to come back. THIS one line is why three city researchers run concurrently instead of one-after-another.

### Interactive Elements (build ALL listed)
- [x] **Group chat animation** (this module owns one of the course's required group-chat animations) — frame the growing graph as a backstage conversation. Actors + colors via `var(--color-actor-1..n)`. Suggested script (id e.g. `chat-module3`):
  - Planner: "Question is in. This needs web research on three cities — I am spawning three Researcher jobs, one per city."
  - Researcher (London): "On it — fetching London population."
  - Researcher (Paris): "Paris here, running at the same time as you two."
  - Researcher (Berlin): "Berlin, same. None of us waits for the others."
  - Formatter: "I cannot start until all three of you report back — I am wired to all three."
  - Researcher (Paris): "Done. Slowest of us sets the pace — about 27 seconds, not 70."
  - Formatter: "All three in. Writing the final comparison now."
- [x] **Data flow / parallel animation** — visualize the fan-out: one Planner box → three Researcher boxes lighting up *simultaneously* → converging into one Formatter box. (If you prefer, fold this into the group-chat beat, but a visual showing three lanes active at once is strongly encouraged as the hero.) NO apostrophes in any `data-steps` label.
- [x] **Code↔English translation** — Snippet B required (hero). Strongly consider also showing Snippet D (the one-line `gather`) as a short second block — it is the punchline of the module.
- [x] **Config/permission badge or callout** — `MAX_NODES = 60` as a "safety rail: the plan cannot grow past 60 boxes." And define DAG = "Directed Acyclic Graph: arrows have direction and never form a loop."
- [x] **Aha! callout** — "The plan is data, not code. The agent edits its own to-do graph while running — which is why two different questions produce two different pipelines from the exact same program."
- [x] **Quiz** — 1 quiz, 3–4 questions, tracing/decision style. Ideas: (1) "Three researcher boxes all have only the Planner feeding them. Do they run one-by-one or together? Why?" (2) "A Formatter box has arrows coming from three researchers; two are done, one is still running. Is the Formatter 'ready'? " (no — waits for all). (3) decision/speed: "A workflow has step B depending on A, and step C depending on nothing. A user complains it is slow. Which two steps could overlap?" (4) "Why is the plan a DAG and not allowed to contain a loop?"
- [x] **Glossary tooltips** — first use: *graph, node, edge, DAG, directed, acyclic, dependency, parallel / concurrent, asyncio / asynchronous, pending, predecessor, runtime*. Aggressive.

### Reference Files to Read
- `references/content-philosophy.md` → all.
- `references/gotchas.md` → all (note the `data-steps` single-quote warning).
- `references/interactive-elements.md` → "Group Chat Animation", "Message Flow / Data Flow Animation", "Code ↔ English Translation Blocks", "Interactive Architecture Diagram" (optional for the boxes-and-arrows hero), "Callout Boxes", "Multiple-Choice Quizzes", "Glossary Tooltips".
- `references/design-system.md` → "Module Structure", "Color Palette" (actor colors `--color-actor-*`), "Animations & Transitions". Accent = teal via `var(--color-accent)`.

### Connections
- **Previous module:** "The Cast of Skills" — we now know who the boxes can be; this module wires them into a runnable, self-growing structure.
- **Next module:** "The Outside World" — when a Researcher box actually goes to the web or an LLM, it goes through a shared gateway and a set of tools. That is where the real cost, latency, and failure live.
- **Tone/style notes:** Odd module → `var(--color-bg-warm)`. The parallel-speedup numbers (27.3s vs 69.9s, 2.56×) are real (README Part 2) — use them, they make it concrete. Accent = teal.
