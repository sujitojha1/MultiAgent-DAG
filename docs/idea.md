# Assignment Idea — DAG Agent: **PulseDAG-GithubRepo** (Trending Repo Scout)

> Working concept doc for the Session 8 assignment (Issue #15). **Idea only — no implementation yet.** Build on this.

**Name (locked):** PulseDAG-GithubRepo
*("Pulse" = momentum/velocity, not just raw stars; "DAG" = the orchestration; "GithubRepo" = the domain.)*

---

## 1. The pitch (one line)
A multi-agent DAG that scouts GitHub Trending across languages and timeframes, then merges, ranks, and explains the most useful rising repositories — triggered from a **Chrome extension** and powered by the existing Session 8 codebase.

> **Scope guardrail:** the Chrome extension is the *trigger + presentation* layer only. All assignment-graded logic (planner, parallel fan-out, critic, coder, new skill) lives in the existing S8 codebase (`flow.py` executor + gateway V8 + skills). Don't let the extension steal time from the 5 graded parts.

## 2. Why this idea
- **Genuinely useful to me** — I want this digest for real (agentic / MCP / dev tooling landscape moves fast).
- **The parallelism is real, not forced** — multiple trending pages are truly independent fetches.
- **The coder earns its place** — star **metrics + comparison across all repos** (velocity %, cross-source deltas, dedupe, ranking) is multi-step arithmetic + set ops an LLM fumbles, so the sandbox computation is justified, not decorative.
- **The critic has an honestly verifiable property** — **per-row field completeness** of the distilled data, checkable from text (avoids the "syllable rubber-stamp" trap). *Dedup is the coder's job, not the critic's.*
- **Relevance is a first-class step** — a dedicated skill filters the computed list down to what's actually useful to me, separating "the numbers" (coder) from "is this worth my time" (LLM judgment).
- **Great YouTube artifact** — the output is a tangible, readable digest.

## 3. What it does (user's view)
- Input: a request like *"top trending Python & Rust repos this week and this month, ranked by momentum, filtered to what's relevant to agentic / MCP / dev-tooling, with why each matters."*
- Pipeline: fetch trending (parallel) → normalise → **critic: completeness** → **coder: star metrics + cross-repo comparison + a deterministic templated fact-line per repo** → **relevance_filter (new skill): keep/drop + "why it matters"** → **critic: alignment** → format.
- Output: a relevance-filtered, ranked shortlist (top N) per language — total stars, stars-gained, velocity %, cross-source delta, a code-generated factual one-liner, and a relevance-checked "why it matters." Anomalous/inflated entries dropped.

> **Two roles for the few-line summary:** the **coder** emits the *deterministic factual* line (assembled from metrics + the distilled description — no hallucination). The **relevance_filter** adds the *judgment* line ("why it matters to me"). The second critic verifies that judgment is **aligned** with the repo's real description and the interest criteria.

## 4. Graph shape (conceptual)
```text
[Chrome extension popup]
   inputs: language(s) · time window · [🎲 random pick]
        │  builds a query string
        ▼
USER QUERY
  → planner
  → researcher × N            ← PARALLEL fan-out (one per trending page:
        python/weekly · python/monthly · rust/weekly · rust/monthly)
  → distiller                 (→ AUTO-CRITIC: "every row has all required
                               fields?"  fail → planner re-researches the
                               incomplete source → corrected → pass)
  → coder                     (METRICS & COMPARISON across ALL repos:
                               dedupe · velocity = gained/total % ·
                               cross-source delta · rank ·
                               + deterministic templated fact-line per repo)
  → relevance_filter [NEW SKILL]   (keep/drop by relevance + "why it matters")
  → critic (ALIGNMENT)             (planner-emitted: is each "why it matters"
                               faithful to the repo's real description &
                               the interest criteria?  fail → re-filter)
  → formatter
  → DIGEST
```

## 5. How it satisfies the 5 assignment parts
| Part | Mapping | Note |
|---|---|---|
| 1 — base queries pass | hello / A / I / J / K carried over | proves architecture intact |
| 2 — **parallel fan-out** | 4 independent researchers (lang × timeframe) | wall-clock = slowest page, not the sum → easy to prove the `asyncio.gather` barrier |
| 3 — **critic (pass + fail)** | **used twice.** (a) *completeness* on distiller output (auto, `critic:true`); (b) *alignment/faithfulness* on `relevance_filter` output (planner-emitted). **Pick one as the graded pass+fail+recovery demo** — completeness is simplest, alignment is richer. | both text-verifiable, no rubber-stamp. **Recoverable fail** (§11): completeness → re-research the source; alignment → re-filter with the rationale. |
| 4 — **coder** | star **metrics + comparison across all repos**: dedupe · `velocity = gained/total × 100` · cross-source delta · rank · **+ a deterministic templated fact-line per repo** (string assembly from metrics + description) | multi-step arithmetic + set ops + templated text → **unambiguously** beyond what the formatter can do from text; the fact-line is code-generated (no hallucination) |
| 5 — **new skill** | **`relevance_filter`** (prompt-only) — scores/filters the coder's computed table down to repos relevant to the user's interests, drops anomalies, emits the shortlist + one-line "why it matters" | not in the S8 catalog; semantic judgment, cleanly separate from the coder's numbers |

## 6. The new skill: `relevance_filter`
- **Role:** consume the coder's computed table (numbers already done) → apply **semantic relevance** judgment against the user's interest profile (e.g. agentic / MCP / dev-tooling) → keep the relevant repos, drop noise + anomalies (e.g. velocity > 100% with low totals = inflated) → emit a ranked shortlist with a one-line "why it matters" each.
- **Why it's the right new skill:** it's the one thing neither the coder (pure math) nor the distiller (extraction) does — "is this worth *my* time?" is LLM judgment. Clean separation of concern.
- **Type:** prompt-only (`tools_allowed: []`) — operates purely on the coder's output. Relevance criteria passed in via the query / a small interest list.
- **Inputs to design:** how the relevance criteria arrive — hard-coded interest list in the prompt, or passed from the extension as a keyword/profile field.
- **Followed by an alignment critic:** a planner-emitted `critic` node sits between `relevance_filter` and `formatter`, verifying each "why it matters" is faithful to the repo's real description + the interest criteria (catches hallucinated relevance). Fail → re-filter. No Executor change — planner-emitted critics are already supported.

## 7. Trigger UI — Chrome extension
The extension is a thin front-end that **leverages the existing codebase**; it does not re-implement any agent logic.

**Popup controls:**
- **Language** — dropdown / multi-select (Python, Rust, … extensible).
- **Time window** — weekly · monthly · (daily?).
- **🎲 Random pick** — button: surface *one* repo to explore today instead of a full ranked digest ("surprise me").
- **Run** — fires the agent; shows progress, then the digest in the popup.

**How it leverages the codebase (the key integration):**
```text
Chrome extension popup
   │  POST {languages, window, mode: "digest" | "random"}
   ▼
thin HTTP bridge  (NEW — small wrapper that turns the request into a
   user-query string and calls the existing flow.py Executor)
   ▼
flow.py Executor  →  skills  →  gateway V8   ← all EXISTING S8 code
   ▼
digest / single-repo JSON  →  rendered in the popup
```
- The only **new backend code** is a small HTTP entry point in front of the existing `Executor` (today `flow.py` is CLI-driven). Everything below it is unchanged S8.
- `agent_routing.yaml` / skills / persistence all reused as-is. The extension just changes *how the query is triggered* and *where the answer is shown*.

**Random-pick — two interpretations (pick one):**
- **Client-side (simplest):** run the normal digest, then the extension randomly highlights one entry from the ranked list.
- **Server-side (more "DAG"):** `mode:"random"` makes the planner emit a shorter graph (one researcher + a `picker` step) — cheaper, and demonstrates the planner adapting its graph to the request.

## 8. Open design questions (decide before building)
1. **Data source for researchers.** GitHub Trending is server-rendered HTML.
   - Option A: `fetch_url` on `https://github.com/trending/<lang>?since=<weekly|monthly>` — simplest, but HTML is heavy and may not parse cleanly.
   - Option B: an unofficial trending JSON API — more robust for a reliable demo.
   - If `fetch_url` struggles, that's the natural motivation for the **S9 browser skill** → note as a known limitation.
2. **`relevance_filter` criteria source.** Hard-coded interest list in the prompt vs. passed from the extension (keyword/profile). Hard-coded is fine for the demo.
3. **Star-count noise.** GitHub Trending velocities can be inflated/anomalous — the coder computes, the `relevance_filter` drops anomalies (a feature, not a bug).
4. **Output format.** Markdown table grouped by language? JSON for downstream reuse? Both?
5. **Extension ↔ backend transport.** How does the popup reach the Executor? Local HTTP bridge (new thin wrapper around `flow.py`) on a fixed port; CORS/permissions in the extension manifest. (Note: gateway V8 on 8108 is for *LLM* calls — the trigger endpoint is separate.)
6. **Random-pick placement.** Client-side highlight vs. server-side `mode:"random"` planner branch (see §7).

## 9. Demo queries for submission (draft)
1. Base set (hello, A, I, J, K).
2. *Fan-out:* "Find the top trending Python and Rust repos for both this week and this month."
3. *Critic:* a run where one source returns an **incomplete** row (missing `stars_gained`) → critic **fails** on completeness → planner **re-researches that source** → complete → **pass** (recoverable; see §11).
4. *Coder:* "…compute each repo's velocity %, find repos appearing in both weekly and monthly, rank by momentum (dedup across lists), and emit a one-line fact summary per repo."
5. *New skill:* `relevance_filter` narrows the ranked list to agentic / MCP / dev-tooling repos with "why it matters" — then the **alignment critic** confirms the rationale is faithful (and demonstrates a fail→re-filter on a planted hallucinated rationale).

## 10. Stretch / later
- Persist weekly digests and diff week-over-week ("new entrants," "fastest climbers").
- Add a `summariser` pass per top repo (pull its README headline).
- Schedule it (the course's scheduler concept) to run every Monday.
- Extension polish: progress trace view (mirror the graph), one-click "open repo," save/star a pick.

## 11. Review notes & refinements (from chat)
Captured from the requirements audit so the design fixes are not lost.

**Fixes applied to the design above:**
1. **Critic property = field completeness only** (not "no duplicates"). Dedup is unreliable for an LLM-as-judge and is the **coder's** job. Critic checks each distilled row has `owner/repo + total_stars + stars_gained + description` — reliably text-verifiable, dodges the rubber-stamp trap.
2. **Recoverable critic-fail (critical).** A *permanently* malformed page would fail the critic, the planner would re-plan on the same bad input, fail again, hit the **per-target cap (1 re-plan)**, and **never produce a corrected answer** — violating part 3. So the forced fail must be **recoverable**: an incomplete/flaky first research pass that a re-research (or a different fetch path) fixes on attempt 2. The planner prompt already says *"do not re-emit the failing step on the same inputs."*
3. **Coder strengthened to indisputable computation.** "Sort by stars" is borderline (an LLM can fake it). Job is now: **dedupe across 4 lists + velocity % + cross-source delta + rank** — multi-step arithmetic + set ops, clearly beyond text.
4. **Relevance is its own skill.** Per request, `relevance_filter` (the new skill) does semantic "is this useful to me" filtering; the coder does the numbers. Clean separation.
5. **Executor must not be edited.** The HTTP bridge is a *separate module* that imports & calls the existing `Executor` (a "new generic mechanism" / new entry point) — do **not** touch `flow.py`'s `Executor.run` internals, or it's a reportable change. `recovery.py` is untouched, so its unit tests keep passing.
6. **One new skill.** Keep `relevance_filter` as the single new skill. Server-side random-pick would need a 2nd skill (`picker`) — allowed but extra scope; prefer **client-side** random-pick to stay minimal.
7. **Coder also emits a per-repo fact-line — deterministic, not prose.** Code assembles a factual one-liner from metrics + the distilled description (template fill). It does **not** write judgment/prose (that's the LLM's job) — so there's no hallucination to police there.
8. **Second critic = alignment/faithfulness on the judgment.** A planner-emitted critic between `relevance_filter` and `formatter` checks each "why it matters" is supported by the repo's real description + interest criteria. Grounded (both source and claim are in its context), so it's a reliable check — and a richer pass/fail demo than completeness (force a fail by planting a hallucinated rationale → re-filter). Planner-emitted critics need **no Executor change**.

**Re-evaluation against the 5 parts (post-fix):**
| Part | Verdict |
|---|---|
| 1 base queries | ✅ unaffected — keep all additions purely additive |
| 2 parallel fan-out | ✅ 4 independent researchers |
| 3 critic pass+fail+recovery | ✅ **now satisfied** via completeness property + recoverable fail (fix #1, #2) |
| 4 coder | ✅ **now unambiguous** (fix #3) |
| 5 new skill, no Executor change | ✅ `relevance_filter` = yaml + prompt; bridge stays out of Executor (fix #5) |
| 6/7 demo + README | ✅ logs must show the DAG runs, not just the popup |

**Gating dependency:** data source (Q8.1) still decides whether parts 2/3/4 work at all — settle first.

---

### Status / next steps
- [x] Lock the name → **PulseDAG-GithubRepo**
- [x] Critic = completeness property, recoverable fail (§11 #1–2)
- [x] Coder = metrics + cross-repo comparison (§11 #3)
- [x] New skill = `relevance_filter` (§11 #4)
- [ ] Decide data source (Q8.1) ← **gating, do first**
- [ ] Decide `relevance_filter` criteria source (Q8.2)
- [ ] Decide extension↔backend transport (Q8.5)
- [ ] Decide random-pick placement: client vs server (Q8.6) — lean client-side
- [ ] Then move to implementation (HTTP bridge, planner.md additions, relevance_filter.md, coder.md, YAML entries, extension popup)
