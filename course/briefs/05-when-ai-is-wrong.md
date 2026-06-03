# Module 5: When the AI Is Wrong

> Write to `course/modules/05-when-ai-is-wrong.html`. Output ONLY the `<section class="module" id="module-5">…</section>` block. Module 5 = odd → `style="background: var(--color-bg-warm)"`.

### Teaching Arc
- **Metaphor:** A **newsroom fact-checker standing between the reporter and the printing press**. The reporter (a skill) hands in a story; the fact-checker (the **Critic**) reads it against the source notes and stamps PASS or FAIL. A FAIL doesn't crash the paper — it sends the story back to the editor (a fresh **Planner**) to be reworked. But there's a rule: a story gets *one* rework. If it fails again, the paper runs with a noted gap rather than missing the deadline.
- **Opening hook:** "AI confidently makes things up. It hallucinates dates, invents sources, drops half the answer. So how does this agent avoid shipping garbage? It hires a professional skeptic and gives it veto power."
- **Key insight:** Two layers of robustness. (1) **The Critic** is a skill whose entire job is to read another skill's output and emit `pass`/`fail` with a reason — and a `fail` automatically splices a *recovery Planner* into the graph to try again. (2) **A failure policy** (`recovery.py`) sorts every error into a *type* and decides what to do: a temporary outside-world hiccup is **skipped** (the gateway already retried), a malformed-output bug is **skipped** (re-running won't fix a prompt bug), and a genuine content failure triggers a **re-plan**. There is a hard cap of **one** re-plan per branch so it can't loop forever.
- **"Why should I care?":** This is debugging intuition, bottled. When *your* AI workflow misbehaves, the same three questions apply: is this a transient blip (just retry), a bug in my instructions (fix the prompt, don't retry), or a real dead-end (rethink the approach)? Knowing the difference is how you escape "AI bug loops" instead of mashing retry forever.

### Core narrative (4–6 screens)
1. **AI lies confidently** — Set the stakes with a concrete, real example from this repo: the GitHub-repos run where the answer "only includes Python repositories, but the user query also asked for Rust repositories." That's the kind of silent miss a Critic catches. Frame the problem before the solution.
2. **Meet the Critic** — A skill like any other (Module 2!), but its output is just a verdict + a reason. Show Snippet A (the critic prompt's job + schema). Note temperature 0.0 — we want the *same* judgment every time (callback to Module 2's dials). Aha: it carries *no data* of its own; it's a gate, not a step that transforms anything.
3. **A FAIL rewires the graph** — Here the growing-graph idea (Module 3) pays off: a failed verdict marks the rejected work's child as `skipped` and splices in a brand-new Planner node to recover. Show Snippet B (the heart of `handle_critic_verdict`). Pair with the group-chat or flow beat below. Use the real recovery trace from the README (planner spliced at `n:9` to recover `n:6`).
4. **The one-rework rule** — Without a cap, a stubborn failure could re-plan forever. Show Snippet C (the cap check) and explain: each branch gets one recovery; a second failure logs a loud warning and lets the run finish with a noted gap. Real trace: "critic-fail on n:14 already recovered once; CAP HIT — branch skipped." Aha: graceful degradation beats infinite loops.
5. **Not all failures are equal** — The failure *classifier*. Show Snippet D (the decision table docstring) — it's unusually readable. Three buckets: **transient** (503/timeout → skip, gateway already retried), **validation_error** (malformed output → skip, it's a prompt bug), **upstream_failure** (real miss → re-plan). This is the screen that delivers the "three debugging questions."
6. **(Optional wrap)** — Tie the two layers together: Critic catches *wrong-but-well-formed* answers; the classifier handles *errors*. Together they keep one bad node from sinking the whole run.

### Code Snippets (pre-extracted — use verbatim)

**Snippet A — the Critic's job and output.** File: `code/prompts/critic.md` (lines 7–19):
```text
Procedure:
  1. Read the UPSTREAM_OUTPUT.
  2. Check it against the INPUTS that produced it.
  3. Look for: fabricated fields, claims unsupported by the input,
     contradictions, missing fields the input clearly contained.
  4. Emit pass or fail.

Output schema (JSON, no prose, no markdown fences):

  {
    "verdict": "pass" | "fail",
    "rationale": "<one or two short sentences>"
  }
```
English angle: the Critic reads the work AND the material it was built from, hunts for invented facts / unsupported claims / contradictions / dropped fields, and returns a tiny verdict object: pass or fail plus one or two sentences of why. That's the whole skeptic in a nutshell.

**Snippet B — a FAIL splices in a recovery Planner (hero translation block).** File: `code/recovery.py` (lines 137–150):
```python
    if child_nid and child_nid in graph.g.nodes:
        graph.mark(child_nid, "skipped")

    original_target_nid = _get_original_target(graph, target_nid) if target_nid else target_nid

    if target_nid and not recovered_branches.get(original_target_nid):
        recovered_branches[original_target_nid] = True
        rationale = (result.output or {}).get("rationale", "(no rationale)")
        fr = f"critic failed target={target_nid} child={child_nid} rationale={rationale}"
        rec_nid = graph.add_node("planner", inputs=["USER_QUERY"],
                                 metadata={"failure_report": fr,
                                           "recovers": target_nid,
                                           "recovery_reason": "critic_fail"})
        print(f"  ↪ critic-fail recovery: planner node {rec_nid} for {target_nid}")
```
English angle: first, take the work that was about to use the rejected output and mark it `skipped` so the pipeline doesn't stall. Then, IF this branch hasn't already been rescued once, remember that we're rescuing it now, capture the Critic's reason, and add a fresh Planner box — handing it the failure note so it can plan a smarter second attempt. The new track grows right where the old one failed.

**Snippet C — one rescue per branch, then degrade gracefully.** File: `code/recovery.py` (lines 151–155):
```python
    elif target_nid:
        cap_hit.append(target_nid)
        print(f"  ↪ critic-fail on {target_nid} already recovered once; "
              f"CAP HIT — branch skipped, final will reflect missing data")
    return True
```
English angle: if we get here, this branch already used its one do-over and failed again. Don't loop forever — record that the cap was hit, print a loud warning, and let the run finish. The final answer will note the gap instead of hanging.

**Snippet D — sorting errors into what-to-do buckets.** File: `code/recovery.py` (lines 66–71):
```python
    Decision table (all coverage):
      reason=transient                          → skip (gateway already retried)
      reason=validation_error                   → skip (prompt bug, not runtime)
      reason=upstream_failure, failed=planner   → skip (would loop on Planner errors)
      reason=upstream_failure, failed=other     → replan
```
English angle: a plain-English rulebook. Temporary network blip? Skip — the gateway already retried, no point re-planning. Output didn't match the required shape? Skip — that's a bug in the instructions, re-running won't help. A real content failure in a normal skill? Re-plan. (And never re-plan a failed Planner — that would loop.)

### Interactive Elements (build ALL listed)
- [x] **Code↔English translation** — Snippet B required (hero). Add Snippet A (the verdict schema) and/or Snippet D (the decision table) — D reads almost like prose and is great for non-technical learners.
- [x] **Spot-the-Bug OR Scenario quiz feel** — this module is a natural fit for "spot the bug": show a short distilled answer that drops the Rust repos and ask the learner to predict the Critic's verdict + reason. (Counts toward the per-module quiz; you may use the Scenario Quiz pattern instead.)
- [x] **Group chat OR data-flow animation** (bonus — the two mandatory ones are Modules 1 & 3) — strongly encouraged here: dramatize the rejection. Suggested group chat (`chat-module5`):
  - Distiller: "Here is my distilled list of trending repos."
  - Critic: "Checking against the request… the user asked for Python AND Rust. You only included Python."
  - Critic: "Verdict: FAIL. Reason: missing Rust repositories."
  - Planner (recovery): "Got the failure note. Re-planning — I will spin up the Rust research that got missed."
  - Critic: "Second attempt still short? That is the cap. I will let it ship with a noted gap rather than loop forever."
  - (NO apostrophes in any flow `data-steps` labels if you use a flow animation.)
- [x] **Config/permission badge or callout** — Critic temperature 0.0 ("same verdict every time"); recovery cap = 1 per branch.
- [x] **Aha! callout(s)** — "Three debugging questions for ANY flaky AI step: is it a blip (retry), a bad instruction (fix the prompt), or a dead end (rethink)? This agent encodes exactly that as skip / skip / re-plan." And: "A fact-checker that can't *fix* anything is still invaluable — its only power is to say no, and that's enough to stop garbage from shipping."
- [x] **Quiz** — 1 quiz, 3–4 questions, debugging/decision style (can incorporate the spot-the-bug above). Ideas: (1) the Rust-missing spot-the-bug → predict verdict. (2) "A skill failed with `503 Service Unavailable`. Should the agent re-plan? Why not?" (transient → skip; gateway already retried). (3) "An answer comes back malformed because the prompt asks for the wrong JSON. Re-planning runs it again and it fails identically. What's the real fix?" (fix the prompt — it's a validation_error, not a runtime issue). (4) decision: "Why cap recovery at one re-plan instead of retrying until it passes?"
- [x] **Glossary tooltips** — first use: *hallucination, Critic, verdict, gate, splice, recovery, re-plan, transient error, validation error, classifier, graceful degradation, cap, skipped, branch, rationale*. Aggressive.

### Reference Files to Read
- `references/content-philosophy.md` → all.
- `references/gotchas.md` → all (heed `data-steps` apostrophe warning if using a flow animation).
- `references/interactive-elements.md` → "Code ↔ English Translation Blocks", "Spot the Bug Challenge" and/or "Scenario Quiz", "Group Chat Animation" (or "Message Flow / Data Flow Animation"), "Callout Boxes", "Permission/Config Badges", "Glossary Tooltips".
- `references/design-system.md` → "Module Structure", "Color Palette", "Animations & Transitions". Accent = teal via `var(--color-accent)`.

### Connections
- **Previous module:** "The Outside World" — ended on the `503` failure. Pick that thread up: outside-world errors are one of the failure types handled here.
- **Next module:** "Make It Your Own" — the Coder skill (writes & runs real Python in a sandbox) and the punchline that you can add a whole new capability with just a config line + a prompt, no Python.
- **Tone/style notes:** Odd module → `var(--color-bg-warm)`. Use the REAL recovery traces and the REAL critic verdict quote from the README — they make it concrete and trustworthy. Critic was teased in Module 2; this is its full story. Accent = teal.
