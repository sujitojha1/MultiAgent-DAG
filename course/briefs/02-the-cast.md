# Module 2: The Cast of Skills

> Write to `course/modules/02-the-cast.html`. Output ONLY the `<section class="module" id="module-2">…</section>` block. Module 2 = even → `style="background: var(--color-bg)"`.

### Teaching Arc
- **Metaphor:** A **theater troupe with a casting binder**. Each actor (skill) has an index card: their name, their one job, and the lines they are told to deliver (their script). To add a new actor you just add a new card — you do not rebuild the theater. The "engine" that runs the play never needs to know who the actors are.
- **Opening hook:** "In Module 1 you met a *team* that changes per question. Now meet the full roster of who can be on that team — and the surprising fact that each member is defined by just two small files, zero programming."
- **Key insight:** **A skill = one YAML entry + one Markdown prompt. There is no Python class per skill.** The orchestrator treats every team member identically; what makes a Researcher different from a Critic is *only its config line and its instructions text*.
- **"Why should I care?":** This is the single most empowering fact for a vibe coder: you can add or change a capability of this AI agent by editing a text file and a config line — no code. It also teaches you the difference between *prompt* (instructions) and *engine* (code that runs instructions), which is exactly the vocabulary you need to steer AI tools.

### Core narrative (4–6 screens)
1. **Meet the roster** — Present the skills as character cards (pattern/feature cards with icons). For each: name, one-line job. Use the real descriptions from `agent_config.yaml`:
   - **Planner** — "Decomposes user queries into the initial DAG and synthesises recovery subgraphs on node failure." (the assistant director)
   - **Researcher** — "Performs multi-step web research and produces normalised text outputs."
   - **Retriever** — "Searches Memory and the FAISS index for material relevant to a query." (looks in what the agent already knows)
   - **GitHub Research** — "Fetches live data from GitHub trending pages and the GitHub API."
   - **Distiller** — "Extracts structured fields from raw text or page content." (the fact-extractor)
   - **Summariser** — "Condenses long content into a short form."
   - **Critic** — "Evaluates an upstream node's output; emits pass or fail with rationale." (quality control — full story in Module 5)
   - **Formatter** — "Renders the final answer for the user." (the editor)
   - **Coder** — "Emits Python code; the orchestrator hands it to sandbox_executor next." (Module 6)
   - **SandboxExecutor** — "Runs code from a Coder node and returns stdout, stderr, exit code." (Module 6)
2. **The big reveal: a skill is two files** — Show the anatomy. One YAML block names the skill and points to its instructions; one Markdown file IS the instructions. Hero code↔English block on the `researcher` YAML entry (below).
3. **The instructions ARE the skill** — Show a trimmed real prompt so the learner sees that "intelligence" here is plain English instructions. Use the `retriever.md` opening (below). Aha: the skill's "brain" is a paragraph of English you can read and edit.
4. **One engine, many actors** — Short screen: the code that loads skills does NOT have a special case per skill. Show the `SkillRegistry` snippet (below). Aha callout: "If you searched this codebase for `if skill == 'researcher'` you would not find it. The engine is skill-agnostic." (Foreshadow Module 6: adding a skill = adding a card.)
5. **Dials, not rewrites** — Each card has knobs: `temperature` (how creative/random) and `tools_allowed` (what the skill is allowed to reach for). Note Critic runs at temperature 0.0 (we want the same verdict every time); Researcher at 0.7 (we want it to explore). Use config badges for this.

### Code Snippets (pre-extracted — use verbatim)

**Snippet A — the casting card (hero translation block).** File: `code/agent_config.yaml` (lines 45–50):
```yaml
researcher:
  prompt: prompts/researcher.md
  tools_allowed: [web_search, fetch_url]
  temperature: 0.7         # exploratory; let the model choose phrasings
  max_tokens: 2500
  description: Performs multi-step web research and produces normalised text outputs.
```
English angle: `researcher:` is the skill's name (used in plans). `prompt:` points to the text file holding its instructions. `tools_allowed` lists what real-world actions it may take (search the web, fetch a page). `temperature: 0.7` means "be fairly creative." `description` is the human one-liner. That is the *entire* definition of the Researcher — there is no Researcher.py.

**Snippet B — the instructions are just English.** File: `code/prompts/retriever.md` (lines 1–5):
```text
You are the Retriever skill. You search the agent's existing knowledge
base for material relevant to a question.

Your tool surface is one MCP tool: `search_knowledge(query, k)`. Use it.
Do not narrate; do not invent other tools.
```
English angle: this whole "skill" is a letter addressed to the AI telling it who to be and what it is allowed to touch. You could edit this file in any text editor.

**Snippet C — one loader for everyone (no per-skill code).** File: `code/skills.py` (lines 61–69):
```python
class SkillRegistry:
    def __init__(self):
        cfg = yaml.safe_load(AGENT_CONFIG_PATH.read_text())
        self._skills: dict[str, Skill] = {n: Skill(n, c) for n, c in cfg.items()}

    def get(self, name: str) -> Skill:
        if name not in self._skills:
            raise KeyError(f"unknown skill: {name}")
        return self._skills[name]
```
English angle: read the config file, and for every entry build one generic `Skill` object. They all use the same `Skill` blueprint — the engine never branches on *which* skill it is. Adding a skill to the YAML automatically makes it loadable; removing it makes it unknown.

### Interactive Elements (build ALL listed)
- [x] **Pattern/feature cards** — the roster of skills as character cards with icons + one-line jobs (screen 1). This is the hero visual.
- [x] **Code↔English translation** — at least one required; use Snippet A (the YAML card) as the main one. Optionally add Snippet B or C as a second.
- [x] **Config/permission badges** — for the "dials" screen: show `temperature` and `tools_allowed` as badges (e.g., Researcher: 🌐 web_search, 🌐 fetch_url, 🎲 temp 0.7; Critic: 🔒 no tools, 🎯 temp 0.0).
- [x] **Quiz** — 1 quiz, 3–4 questions, scenario/decision style. Ideas: (1) "You want the agent to also be able to translate text to French. Roughly what do you need to add?" (a YAML entry + a prompt file — no code). (2) "Which skill should have `tools_allowed: [web_search]` and which should have an empty list — Researcher or Formatter? Why?" (3) "The Critic keeps giving slightly different verdicts on identical input. Which dial would you reach for?" (temperature → 0). (4) decision: "Two skills do similar things; one reads the *web*, one reads the *agent's own saved knowledge*. Which is Researcher, which is Retriever?"
- [x] **Glossary tooltips** — first use this module: *YAML, Markdown, prompt, skill, orchestrator, temperature, token / max_tokens, tool, MCP, registry, class, instance*. Aggressive.
- [x] **Aha! callout** — "Prompt vs. engine: the *prompt* is the English instructions; the *engine* is the unchanging Python that delivers them. Most of what feels like 'the AI being smart' lives in editable prompt files."

### Reference Files to Read
- `references/content-philosophy.md` → all.
- `references/gotchas.md` → all.
- `references/interactive-elements.md` → "Pattern/Feature Cards", "Code ↔ English Translation Blocks", "Permission/Config Badges", "Multiple-Choice Quizzes", "Callout Boxes", "Glossary Tooltips".
- `references/design-system.md` → "Module Structure", "Color Palette". Accent = teal via `var(--color-accent)`.

### Connections
- **Previous module:** "What This Thing Does" — established the per-question team and the Planner→…→Formatter pipeline. Build on the troupe idea.
- **Next module:** "The Graph That Grows Itself" — how these skills get wired into a runnable structure that *expands at runtime* and runs members in parallel.
- **Tone/style notes:** Even module → `var(--color-bg)`. Keep skill names consistent with Module 1. Don't deep-dive Critic or Coder here (Modules 5 and 6 own them) — one-line tease only. Accent = teal.
