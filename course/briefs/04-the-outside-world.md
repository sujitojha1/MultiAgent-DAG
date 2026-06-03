# Module 4: The Outside World

> Write to `course/modules/04-the-outside-world.html`. Output ONLY the `<section class="module" id="module-4">…</section>` block. Module 4 = even → `style="background: var(--color-bg)"`.

### Teaching Arc
- **Metaphor:** A **shared embassy switchboard / interpreter desk** for a building full of specialists. No specialist phones a foreign government directly. They all hand their request to one front desk (the **Gateway**), which knows which interpreter (AI provider) is on duty, keeps a logbook, retries when a line drops, and reuses recent answers instead of re-dialing. And when a specialist needs something from the real world — search the web, open a page, look something up — they request it through a fixed set of **approved hotlines (tools)**, never by reaching out on their own.
- **Opening hook:** "When the Researcher 'goes to the web' or 'asks the AI,' where does that actually go? Out of this program entirely — to services that cost money, have rate limits, and sometimes fail. This is the module about the edge of the system."
- **Key insight:** Two boundaries to the outside world: (1) **the Gateway** — every call to a large language model goes through one front desk that handles provider choice, retries, caching, and cost; (2) **tools** — a skill can only touch the outside world through a small, declared menu (`web_search`, `fetch_url`, `search_knowledge`). A skill with an empty tool list is "blindfolded" — pure thinking, no reaching out.
- **"Why should I care?":** This is where real-world constraints live: **cost, rate limits, latency, and failure modes.** A vibe coder who understands "everything funnels through a gateway with a tool allowlist" can reason about *why an app got expensive*, *why it got rate-limited*, and *how to give an AI capability safely* (add a tool, don't hand it the keys to everything).

### Core narrative (4–6 screens)
1. **Inside vs. outside** — Recap: Modules 1–3 were the agent's *internal* org chart. Now we cross the boundary. Two gates out: the AI brain (Gateway) and the hands (tools). Set up the two halves of the module.
2. **The Gateway: one front desk for all AI calls** — Why funnel everything through one place? Central logging, cost tracking, provider routing, retries, caching. Real detail from the repo: the Gateway is a separate service (FastAPI) running on `http://localhost:8108`; skills call it with their own name attached (`agent=<skill_name>`) so each skill can be routed to a preferred AI provider and billed separately. Show Snippet A (the non-tool LLM call). Aha: the agent doesn't talk to OpenAI/Gemini/etc. directly — it talks to its own switchboard, which decides.
3. **Routing & provider pins** — Different skills can prefer different AI providers. Real example from config: `github_research` is pinned to `gemini` because another provider "returned empty {} after 91s (couldn't tool-call)." Use Snippet B — this is a fantastic, real "why this decision was made" moment. Config badge: 📌 provider_pin: gemini.
4. **Tools: the approved hotlines** — A skill may only call tools on its menu. Show the real tool catalog entries (Snippet C). Three tools in this agent: `web_search` (find pages, capped at 5 results), `fetch_url` (read one page as clean text), `search_knowledge` (vector-search the agent's own saved knowledge). Tie back to Module 2: `tools_allowed` in the YAML is the menu; this is what those names point to. Aha: capability is *granted*, not assumed — the Formatter literally cannot browse the web because it has no tools.
5. **When the line is busy** — Outside services fail and throttle. The README's own troubleshooting table is gold: a `503 Service Unavailable` means "all providers in cooldown / unconfigured — add a key or wait a minute." Set up Module 5 (failure handling) with this: transient outside-world errors are expected and handled, not crashes.

### Code Snippets (pre-extracted — use verbatim)

**Snippet A — every AI call goes through the Gateway (hero translation block).** File: `code/skills.py` (lines 301–310):
```python
    else:
        reply = await asyncio.to_thread(
            LLM().chat,
            prompt=rendered,
            agent=skill.name,
            session=session_id,
            provider=skill.provider_pin,
            max_tokens=skill.max_tokens,
            temperature=skill.temperature,
        )
```
English angle: send the finished instructions (`prompt`) to the Gateway's `chat` door. Attach *who is asking* (`agent=skill.name`) and *which session*, so the front desk can route and log it. `provider` is an optional "I insist on this interpreter" override; `max_tokens`/`temperature` are the per-skill dials from Module 2. The skill never names a real AI company — the Gateway resolves that.

**Snippet B — a real routing decision, with the reason in a comment.** File: `code/agent_config.yaml` (lines 52–59):
```yaml
github_research:
  prompt: prompts/github_research.md
  provider_pin: gemini     # drive fetch_url tool-loop + JSON on gemini; ollama
                           # returned empty {} after 91s (couldn't tool-call)
  tools_allowed: [fetch_url]
  temperature: 0.2         # structured extraction; keep it deterministic
  max_tokens: 2000
  description: Fetches live data from GitHub trending pages and the GitHub API to list popular or trending repositories.
```
English angle: this skill is *pinned* to the Gemini provider. The comment is the honest engineering reason — a different provider couldn't reliably use tools and stalled for 91 seconds. This is what "choosing a model for a job" looks like in practice.

**Snippet C — the approved hotlines (tool catalog).** File: `code/skills.py` (lines 202–222):
```python
    "web_search": {
        "name": "web_search",
        "description": "Search the web (Tavily primary, DDG fallback). Hard-capped at 5 results.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer", "default": 3},
            },
            "required": ["query"],
        },
    },
    "fetch_url": {
        "name": "fetch_url",
        "description": "Fetch clean markdown from a URL via crawl4ai.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
```
English angle: each tool is a little contract — its name, what it does, and exactly what inputs it accepts (`web_search` needs a `query`; `fetch_url` needs a `url`). The AI can only ask for tools shaped like this, and only the ones its skill is allowed. Note the built-in guardrail: web search is "hard-capped at 5 results."

### Interactive Elements (build ALL listed)
- [x] **Code↔English translation** — Snippet A required (hero). Add Snippet B (routing/pin) — it is a memorable real-world decision. Snippet C optional as a third or rendered as cards instead.
- [x] **Pattern/feature cards or icon-label rows** — the three tools as cards: 🔎 `web_search` (find pages, max 5), 📄 `fetch_url` (read one page as clean text), 🧠 `search_knowledge` (search what the agent already knows).
- [x] **Config/permission badges** — provider pin (📌 gemini), `tools_allowed` per skill (Researcher 🌐🌐, Formatter 🚫 none), and the gateway port `:8108`. Reinforce "capability is granted by config."
- [x] **Data-flow OR group-chat animation** (optional but encouraged; the two *required* course animations are already owned by Modules 1 and 3, so this is bonus) — e.g., a Researcher handing a request to the Gateway, the Gateway picking a provider and (on a 503) retrying. Keep it light; do not duplicate Module 3's hero.
- [x] **Aha! callout** — "A skill with an empty `tools_allowed` list is *thinking-only* — it physically cannot reach the internet. That is a safety feature, not a limitation." And/or: "One gateway means one place to see cost, one place to add a key, one place to fix a provider outage."
- [x] **Quiz** — 1 quiz, 3–4 questions, debugging/decision style. Ideas: (1) "Your agent suddenly returns `503 Service Unavailable`. Based on this module, what is the most likely cause and first fix?" (provider cooldown / missing key → add a key or wait). (2) "You want the Formatter to start citing live web pages, but it never browses. Why — and what is the smallest change?" (no tools allowed → add `web_search`/`fetch_url` to its menu). (3) decision: "A teammate hardcodes one AI provider's name inside five different skills' code. Why is routing through a single gateway better?" (4) "`web_search` is hard-capped at 5 results. Name one real reason a team would cap that." (cost / latency / noise).
- [x] **Glossary tooltips** — first use: *LLM (large language model), provider, gateway, API, FastAPI, port / localhost, routing, provider pin, tool, MCP, vector search, cache, rate limit, latency, 503 / status code, tool-use loop, deterministic*. Aggressive.

### Reference Files to Read
- `references/content-philosophy.md` → all.
- `references/gotchas.md` → all.
- `references/interactive-elements.md` → "Code ↔ English Translation Blocks", "Pattern/Feature Cards" (or "Icon-Label Rows"), "Permission/Config Badges", "Multiple-Choice Quizzes", "Callout Boxes", "Glossary Tooltips" (and "Message Flow / Data Flow Animation" only if you add the optional bonus animation).
- `references/design-system.md` → "Module Structure", "Color Palette". Accent = teal via `var(--color-accent)`.

### Connections
- **Previous module:** "The Graph That Grows Itself" — the boxes and parallel lanes. Now we follow a box's request across the boundary to real services.
- **Next module:** "When the AI Is Wrong" — outside services fail and AIs make things up; the agent has a built-in quality checker (Critic) and a failure policy that decides skip vs. retry vs. re-plan.
- **Tone/style notes:** Even module → `var(--color-bg)`. Don't over-build animations here — Modules 1 and 3 carry the two mandatory ones; keep this module card- and badge-heavy. The `503` detail bridges into Module 5 — end on it. Accent = teal.
