# Module 6: Make It Your Own

> Write to `course/modules/06-make-it-your-own.html`. Output ONLY the `<section class="module" id="module-6">…</section>` block. Module 6 = even → `style="background: var(--color-bg)"`. This is the FINALE — end on an empowering, big-picture note.

### Teaching Arc
- **Metaphor:** **Hiring a contractor vs. teaching the office a new skill.** The **Coder + Sandbox** pair is the agent hiring a one-off contractor: "write me a little program to crunch these numbers," run it in a *rented workshop* (the sandbox) that's walled off from the office, take the result, send the contractor home. And adding a brand-new skill is like writing one more index card for the casting binder (Module 2) — the office instantly knows the new role without renovating the building.
- **Opening hook:** "What if the answer needs actual math — rank 13 repositories by a formula? An AI guessing arithmetic is a recipe for wrong numbers. So this agent does something better: it *writes a tiny program, runs it for real, and reads back the exact result.*"
- **Key insight:** Two finale ideas. (1) **Coder → SandboxExecutor** is an *automatic chain*: the Coder writes Python, and the orchestrator *always* runs it next in a subprocess sandbox — wired by one config line (`internal_successors`), no Planner involvement. The sandbox is a **usability** boundary (stops runaway output/loops), explicitly **not** a security jail. (2) **You can add a whole new capability with zero Python** — a YAML entry + a Markdown prompt. The repo proves it: the `github_research` skill was added with no code changes at all.
- **"Why should I care?":** This is the payoff for a vibe coder. You now know *exactly* where to add behavior (a prompt + a config line), why "let the AI run real code" beats "let the AI guess," and what a sandbox does and does NOT protect you from. That's enough to extend an agent like this yourself and to talk to engineers about it precisely.

### Core narrative (4–6 screens)
1. **Why not just ask the AI to do the math?** — Because language models are notoriously shaky at arithmetic and will *confidently* return wrong totals. The fix: have the AI write code, then actually execute it. Frame with the real Part-4 task: rank trending repos by "velocity" = stars_gained / total_stars × 100.
2. **The Coder writes a tiny program** — The Coder skill's whole job is to emit runnable Python plus a one-line reason. Crucial subtlety worth a screen: the sandbox starts *empty* — it can't see the agent's data — so the Coder must **paste the numbers it needs directly into the code as literals.** Show Snippet A (the inline-literals rule from coder.md). Aha: "the code must carry its own groceries — the kitchen is bare."
3. **The automatic hand-off** — One config line makes Coder → SandboxExecutor inseparable. Show Snippet B (`internal_successors: [sandbox_executor]`) and Snippet C (the orchestrator splicing it in). Callback to Module 3: this is *static* track-laying, decided by config, not by the Planner. Aha: some edges in the graph are wired by the YAML, not planned.
4. **The rented workshop (sandbox)** — Show Snippet D (the sandbox's own honest disclaimer). Make the security point loudly and clearly: timeout + output caps keep a runaway script from poisoning the run, but this is NOT isolation — a hostile script could still read files or hit the network. Real numbers from the repo: 30-second timeout, 1 MB output cap, most env vars scrubbed. Config badges. Then show the real result: the code ran in ~0.1s and produced an exact ranking (top repo at 97.37% velocity).
5. **Add a skill with zero Python (the big one)** — The finale's thesis. The `github_research` skill shipped with NO Python changes — just a YAML entry, a prompt file, and a routing hint. Show Snippet E (the real `git diff --stat`). Callback to Module 2 (skill = 2 files) and Module 4 (provider routing). Aha: "the engine is done; new abilities are content."
6. **The big picture (close the course)** — One recap visual tying all six modules into a single sentence each: a question comes in → the Planner sizes a team → the team is a self-growing graph run in parallel → calls to the outside world funnel through one gateway and a tool allowlist → a Critic guards quality and a policy handles failure → and you extend it all with prompts, not code. End empowering: "You can now read this agent, debug it, and add to it."

### Code Snippets (pre-extracted — use verbatim)

**Snippet A — the Coder must inline its data (key subtlety).** File: `code/prompts/coder.md` (lines 10–13):
```text
Your Python runs in a separate subprocess sandbox that does NOT see
INPUTS. It starts with an empty namespace. Therefore any number, string,
or list you need from INPUTS must be copied into the source you emit as a
literal — the code cannot reference the upstream output at runtime.
```
English angle: the program runs in a fresh, empty room with none of the agent's data in it. So the Coder has to physically write the numbers into the program text itself. If it forgets, the program runs against nothing.

**Snippet B — one line makes Coder → Sandbox automatic.** File: `code/agent_config.yaml` (lines 92–97):
```yaml
coder:
  prompt: prompts/coder.md
  internal_successors: [sandbox_executor]
  temperature: 0.2
  max_tokens: 1500
  description: STUB. Student assignment for Session 8. Emits Python code; the orchestrator hands it to sandbox_executor next.
```
English angle: `internal_successors: [sandbox_executor]` means "whenever a Coder finishes, automatically add a SandboxExecutor right after it." The Planner never has to ask — the pairing is baked into the config.

**Snippet C — the orchestrator honoring that config.** File: `code/flow.py` (lines 138–140):
```python
        for child_skill in src_def.internal_successors:
            nid = self.add_node(child_skill, inputs=[src_nid])
            added.append(nid)
```
English angle: after any node finishes, look up its `internal_successors` from the config and add each one as a new box fed by this node. This is the generic mechanism behind the automatic Coder→Sandbox hand-off — no skill-specific code.

**Snippet D — the sandbox tells you what it is NOT.** File: `code/sandbox.py` (lines 9–14):
```text
What it is NOT. This is not OS-level isolation. There is no chroot, no
container, no syscall filter, no FS allowlist beyond cwd. A malicious
script can read /etc and call out to the network. The sandbox is a
USABILITY boundary — it keeps a runaway loop or noisy print from
poisoning the orchestrator's stdout — not a SECURITY boundary.
```
English angle: refreshingly honest self-documentation. This "sandbox" stops accidents (endless loops, giant output) — but it is NOT a jail. A genuinely malicious program could still misbehave. Knowing this boundary is exactly the kind of thing you'd want to flag to an AI or an engineer.

**Snippet E — a whole skill added with zero Python.** File: `README.md` (the `git diff --stat` for the skill-introduction commit):
```text
 code/agent_config.yaml          |  18 +++   ← skill entry + provider_pin + tools_allowed
 code/prompts/github_research.md |  28 ++++  ← full system prompt (new file)
 gateway/agent_routing.yaml      |   1 +     ← routing hint only
```
English angle: the entire new capability was three small text edits — a config entry, a new instructions file, and a one-line routing hint. Not a single line of program logic changed. That is the architecture's promise: *new abilities are content, not code.*

### Interactive Elements (build ALL listed)
- [x] **Code↔English translation** — Snippet A or D required as hero (both are vivid). Add Snippet B (the one-line chain) and/or Snippet E (the zero-Python diff) — E is the perfect finale punchline.
- [x] **Config/permission badges** — sandbox limits: ⏱ 30s timeout, 📦 1 MB output cap, 🔒 env vars scrubbed (only PATH/HOME/LANG kept); and `internal_successors: [sandbox_executor]`.
- [x] **Pattern/feature cards or numbered step cards** — the Coder→Sandbox→Formatter mini-pipeline as 3 step cards, OR the "add a skill in 3 steps" recipe (write the prompt → add the YAML entry → optional routing hint).
- [x] **Recap / architecture visual** — the closing big-picture screen. A six-row recap (one line per module) or a single end-to-end diagram of the whole journey. This is the course's send-off — make it satisfying.
- [x] **Aha! callout(s)** — "AI is bad at arithmetic but good at *writing code that does* arithmetic. Letting it run real code turns a guess into a computation." And the finale: "The engine is finished. Everything you'd want to add is a prompt and a config line."
- [x] **Quiz** — 1 quiz, 3–4 questions, scenario/decision style. Ideas: (1) "You want the agent to compute a weighted score across 20 items. Why route through Coder+Sandbox instead of asking the AI to do the math in its head?" (2) "The Coder wrote correct logic but the program printed nothing useful. The sandbox starts empty — what did the Coder likely forget?" (inline the literals). (3) decision/security: "A teammate says 'we can run any untrusted code, it's sandboxed.' Based on this module, what do you push back on?" (usability boundary, not security). (4) the finale flex: "You want to add a 'translate to Spanish' skill. List what you'd create — and what you would NOT need to touch." (a prompt + YAML entry; no engine/Python changes).
- [x] **Glossary tooltips** — first use: *subprocess, sandbox, namespace, literal, stdout / stderr, exit code, timeout, environment variable, isolation / chroot / container, internal successors, git diff / diff stat, stub*. Aggressive.

### Reference Files to Read
- `references/content-philosophy.md` → all.
- `references/gotchas.md` → all.
- `references/interactive-elements.md` → "Code ↔ English Translation Blocks", "Permission/Config Badges", "Pattern/Feature Cards" or "Numbered Step Cards", "Interactive Architecture Diagram" or "Flow Diagrams" (for the recap), "Callout Boxes", "Multiple-Choice Quizzes", "Glossary Tooltips".
- `references/design-system.md` → "Module Structure", "Color Palette". Accent = teal via `var(--color-accent)`.

### Connections
- **Previous module:** "When the AI Is Wrong" — quality and failure handling. Now the empowering finale: building on the agent.
- **Next module:** none — this is the last module. Close the whole course with the big-picture recap and an encouraging send-off to the learner.
- **Tone/style notes:** Even module → `var(--color-bg)`. This is the finale — land the two emotional beats: (1) "run real code, don't guess" and (2) "you can extend this with prompts, not code." Use the REAL repo facts (velocity formula, 97.37% top result, 0.1s run, the zero-Python diff). Accent = teal.
