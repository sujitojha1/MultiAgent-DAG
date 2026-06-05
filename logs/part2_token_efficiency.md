# Session Log: Part 2 — Token Efficiency of Parallel Fan-Out (NFR-201)

Traces to **NFR-201 — Token Efficiency** [Should] in [`docs/requirements.md`](../docs/requirements.md).

> The parallel fan-out query (FR-103 / FR-201) shall consume fewer input
> tokens than an equivalent Session 7 sequential run, as demonstrated by
> comparing `/v1/cost/by_agent` output from the Gateway.

- **Session ID**: `s8-e742b7c9`
- **User Query**: "Find the populations of London, Paris, Berlin and tell me which two are closest in size"
- **Provider**: gemini (all nodes)
- **Companion log** (execution trace): [part2_parallel_fanout.md](part2_parallel_fanout.md)

---

## 1. Measured S8 fan-out cost — `GET /v1/cost/by_agent?session=s8-e742b7c9`

Pulled directly from the Gateway cost ledger (`gateway/gateway_v8.db`). This
is real, recorded data — every researcher branch ran as an independent
node and its tokens were billed independently.

```json
{
  "planner":    [{ "agent": "planner",    "provider": "gemini", "calls": 1, "in_tok": 1279,  "out_tok": 246 }],
  "researcher": [{ "agent": "researcher", "provider": "gemini", "calls": 6, "in_tok": 16653, "out_tok": 973 }],
  "formatter":  [{ "agent": "formatter",  "provider": "gemini", "calls": 1, "in_tok": 1714,  "out_tok": 138 }]
}
```

**Total input tokens (fan-out): 19,646.**

### Per-call breakdown (chronological, from the `calls` table)

The three researchers each run a 2-turn tool-use loop: turn 1 emits the
`web_search` call (~934 in-tok, just the sub-query + memory hits + tool
schema); turn 2 receives that branch's search results and writes the
findings.

| call id | agent      | turn                     | input tokens |
|--------:|------------|--------------------------|-------------:|
| 1087    | planner    | plan the DAG             |        1,279 |
| 1088    | researcher | London — search call     |          934 |
| 1089    | researcher | Paris — search call      |          934 |
| 1090    | researcher | Berlin — search call     |          934 |
| 1091    | researcher | London — + search result |        4,127 |
| 1092    | researcher | Paris — + search result  |        5,441 |
| 1093    | researcher | Berlin — + search result |        4,283 |
| 1094    | formatter  | synthesize 3 findings    |        1,714 |
|         |            | **total**                |   **19,646** |

The load-bearing observation: each branch's **`web_search` result payload**
(≈ `4127−934 = 3,193` for London, `5441−934 = 4,507` for Paris,
`4283−934 = 3,349` for Berlin) is seen **only by that one researcher**. It
never enters any sibling's prompt, and only the small distilled findings
(296 / 297 / 290 out-tok) reach the formatter (1,714 in-tok).

---

## 2. Equivalent S7 sequential baseline

In Session 7 the same task is answered by a **single sequential ReAct
agent**: one growing conversation that searches each city in turn. Because
each turn resends the full transcript, every prior search result is
re-billed on every subsequent turn — the heavy payloads accumulate.

The baseline below is reconstructed from the **measured payload sizes of
this very run** (the `base` per-turn prompt and the three search-result
sizes above), since the S7 agent itself is not part of this repository.
`assistant tool_call` framing is ~30 tok/turn.

| turn | content (transcript resent each turn)                       | input tokens |
|-----:|-------------------------------------------------------------|-------------:|
| 1    | base + query → search London                                |          934 |
| 2    | base + [London result 3,193] → search Paris                 |        4,157 |
| 3    | base + [London 3,193 + Paris 4,507] → search Berlin         |        8,694 |
| 4    | base + [London 3,193 + Paris 4,507 + Berlin 3,349] → answer |       12,073 |
|      | **total**                                                   |   **25,858** |

The single transcript carries all three search payloads forward, so the
third and fourth turns alone (8,694 + 12,073) already exceed the entire
fan-out run.

---

## 3. Side-by-side comparison

| metric                                  | S7 sequential (single agent) | S8 parallel fan-out | delta |
|-----------------------------------------|-----------------------------:|--------------------:|------:|
| Input tokens — research + synthesis     |                       25,858 |              18,367 | −29.0% |
| Input tokens — incl. planning           |                       25,858 |              19,646 | −24.0% |
| Search-result payload re-billed         |     3× (accumulated, 4 turns)|    1× per branch    |   —    |

**Conclusion — NFR-201 satisfied.** The parallel fan-out run consumes
**19,646** input tokens versus **~25,858** for the equivalent sequential
single-agent run — **~24% fewer** (≈29% fewer on the research+synthesis
portion). The saving comes from branch isolation: each researcher's bulky
`web_search` results are billed once inside its own 2-turn sub-conversation
and discarded, whereas the sequential agent re-bills every result on every
later turn as the transcript grows.

---

## 4. Reproduce

The fan-out numbers come straight from the Gateway ledger:

```bash
# Live endpoint (Gateway running on :8108):
curl "http://localhost:8108/v1/cost/by_agent?session=s8-e742b7c9"

# Or directly from the recorded ledger (no server needed):
python - <<'PY'
import sys, json
sys.path.insert(0, "gateway")
import db
print(json.dumps(db.by_agent(session="s8-e742b7c9", since=0), indent=2))
PY
```

Per-call breakdown:

```sql
SELECT id, agent, input_tokens, output_tokens, tool_calls
FROM calls WHERE session='s8-e742b7c9' ORDER BY ts;
```
