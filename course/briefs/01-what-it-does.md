# Module 1: What This Thing Does

> Write to `course/modules/01-what-it-does.html`. Output ONLY the `<section class="module" id="module-1">…</section>` block — no `<html>`, `<head>`, `<body>`, `<style>`, or `<script>` tags. Use `style="background: var(--color-bg-warm)"` on the section (module 1 = warm tone; odd modules warm, even modules use `var(--color-bg)`).

### Teaching Arc
- **Metaphor:** A **film production crew**. You (the director) call out one instruction — "give me a scene where someone reads a letter." A *planner/assistant director* breaks that into jobs (set, lighting, actor), specialists each do their job, and an *editor* stitches the final cut you actually watch. Nobody does everything; each person has one job and hands their work down the line.
- **Opening hook:** "Imagine you type *'Who was Claude Shannon and what did he contribute?'* into this agent and hit enter. What happens in the next 20 seconds is the whole story of this codebase."
- **Key insight:** This agent doesn't answer your question in one big step. It **breaks the question into a small team of specialists, runs them in order, and assembles their work into one answer.** The team is decided *on the fly*, per question.
- **"Why should I care?":** When you understand that an AI agent is really a *pipeline of small steps*, you can steer it ("do the research step differently"), debug it ("which step gave the wrong answer?"), and reason about cost and speed — instead of treating it as one magic black box.

### Core narrative (3–5 screens)
1. **What the app is** — A command-line "agent" you give a question to; it returns a written answer. Plain example: `python flow.py "Say hello"` → *"Hello! How can I assist you today?"*. It can also do research, compare cities, rank GitHub repos, even write and run code. Keep this screen short — it's the "what is this thing" grounding.
2. **The simplest possible run** — For a trivial question, the team is just **two members**: a **Planner** (decides who's needed) and a **Formatter** (writes the final answer). Show this as a 2-step flow diagram. Aha: even the simplest run still goes through a planner — the agent *always* plans first.
3. **A real run, traced** — The Shannon biography question needs four members: **Planner → Researcher → Distiller → Formatter**. Walk the journey: plan the work → go read about Shannon on the web → pull out the key facts (born/died/contributions) → write the human answer. This is the "behind-the-scenes documentary" screen — make it the hero visual (a data-flow animation, see below).
4. **The big idea** — The list of team members is **not fixed**. A "hello" needs 2; a research question needs 4; comparing three cities spins up three researchers at once. The Planner sizes the team to the question. This sets up Module 2 (who the members are) and Module 3 (how the team grows).

### Code Snippets (pre-extracted — use verbatim in code↔English blocks)

Use **one** code↔English translation block this module. Recommended snippet (the CLI entry point — what actually happens when you run the command). File: `code/flow.py` (lines 318–326):

```python
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

Plain-English angle (line by line): grab the words you typed after `python flow.py`; if the first word is `--resume`, pick up an old session instead; otherwise treat everything you typed as the question (with a friendly default if you typed nothing); then hand the question to the `Executor` — the "showrunner" that builds and runs the team. Don't over-explain `async`; one tooltip is enough.

Optional second tiny snippet (the very first thing the showrunner does — seed the team with a Planner). File: `code/flow.py` (lines 184–186):
```python
            store.write_query(query)
            graph = Graph()
            graph.add_node("planner", inputs=["USER_QUERY"])
```
English: save the question to disk, make an empty plan, and add exactly one starting job — the Planner, fed your question. Everything else grows from here. (This plants the seed for Module 3.)

### Interactive Elements (build ALL listed)
- [x] **Code↔English translation** — the `main()` snippet above (required). Optionally the 3-line seed snippet.
- [x] **Data flow animation** (this module owns one of the course's required flow animations) — actors for the Shannon run: `flow-actor-1` = You (the question), `flow-actor-2` = Planner, `flow-actor-3` = Researcher, `flow-actor-4` = Distiller, `flow-actor-5` = Formatter. Steps (remember: NO apostrophes inside labels — the README quote uses none):
  - `{"highlight":"flow-actor-1","label":"You type: Who was Claude Shannon and what did he contribute?"}`
  - `{"highlight":"flow-actor-2","label":"Planner reads the question and decides which specialists are needed","packet":true,"from":"actor-1","to":"actor-2"}`
  - `{"highlight":"flow-actor-3","label":"Researcher goes to the web and gathers raw material","packet":true,"from":"actor-2","to":"actor-3"}`
  - `{"highlight":"flow-actor-4","label":"Distiller pulls out the key facts: born, died, three contributions","packet":true,"from":"actor-3","to":"actor-4"}`
  - `{"highlight":"flow-actor-5","label":"Formatter writes the final human-readable answer","packet":true,"from":"actor-4","to":"actor-5"}`
  - `{"highlight":"flow-actor-1","label":"You read the answer: born 1916, died 2001, founded information theory","packet":true,"from":"actor-5","to":"actor-1"}`
- [x] **Flow diagram** (simple, static) — the 2-step "hello" run: Planner → Formatter. Contrast it visually with the 4-step run to make "the team is sized to the question" land.
- [x] **One or two "aha!" callout boxes** — e.g. "Every run starts with a Planner — the agent decides *how* to answer before it answers." And: "Same machine, different team. The code never changes; the *plan* changes per question."
- [x] **Quiz** — 1 quiz, 3 questions, scenario/tracing style. Ideas: (1) "You ask the agent to just say hi. How many specialists run, and which?" (2) "You ask it to compare the populations of three cities. Why might three researchers run *at the same time*?" (tests the parallel intuition, sets up Module 3) (3) tracing: "The final answer was wrong about Shannon's death date. Which specialist would you suspect first — and which writes the words you actually saw?" (Researcher gathered it; Formatter only phrased it.)
- [x] **Glossary tooltips** — first use, this module: *agent, command line / CLI, Planner, Formatter, Researcher, Distiller, query, parallel, asynchronous (async), session*. Be aggressive.

### Reference Files to Read
- `references/content-philosophy.md` → all of it (content rules).
- `references/gotchas.md` → all of it (checklist).
- `references/interactive-elements.md` → "Code ↔ English Translation Blocks", "Message Flow / Data Flow Animation", "Flow Diagrams", "Callout Boxes", "Multiple-Choice Quizzes" (or "Scenario Quiz"), "Glossary Tooltips".
- `references/design-system.md` → "Module Structure" (wrapper markup), "Color Palette" (background tokens). Accent is **teal** — do not hardcode hex; use `var(--color-accent)`.

### Connections
- **Previous module:** none (this is the opening). Include the brief "here is what this app does and why it is interesting" intro before tracing.
- **Next module:** "The Cast of Skills" — introduces each specialist (Planner, Researcher, Distiller, Critic, Formatter, Coder…) and the surprise that each one is just a config line + a text file, no code.
- **Tone/style notes:** Warm, smart-friend tone. Accent color = teal (use `var(--color-accent)`). Call the specialists **"skills"** interchangeably with "team members" — Module 2 formalizes the word "skill". Actor naming convention across the course: Planner, Researcher, Distiller, Critic, Formatter, Coder, SandboxExecutor, Gateway. Module 1 = warm background tone.
