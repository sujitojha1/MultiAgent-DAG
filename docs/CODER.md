# Coder Skill — Code Notes

> **Already have docs?** Yes. **To review the canonical explanation, read
> [`docs/LEARNING_NOTES.md`](LEARNING_NOTES.md) → Module 5 ("Coder Skill").**
> It has the full Coder → SandboxExecutor → Formatter chain with code
> examples. This file is a focused companion that maps the contract to the
> exact lines of code that enforce it.

---

## What the Coder does

The Coder is an LLM-backed skill that turns upstream text data into a short
Python program. It does **not** run the program itself — that is the job of
its static internal successor, `sandbox_executor`.

```
coder (LLM)  ──emits──▶  {"code": "...", "rationale": "..."}
   │
   └─(internal_successors)─▶  sandbox_executor (no LLM)
                                  └─ runs the code in a subprocess
                                     ▶ {"stdout": "...", "exit_code": 0, ...}
```

## The output contract (one sentence)

`prompts/coder.md` must make the LLM emit a **bare** JSON object
`{"code": "<python that prints the answer to stdout>", "rationale": "<one line>"}`
— no markdown fences — because `sandbox_executor` reads the `code` field
verbatim and fails with `no code in upstream coder output` if it is empty
or missing.

## Where each rule is enforced in code

| Rule | Enforced by |
| --- | --- |
| Coder is auto-followed by the sandbox | `code/agent_config.yaml` — coder `internal_successors: [sandbox_executor]` |
| `code` is extracted verbatim from the upstream output dict | `code/skills.py:251–255` |
| Empty/missing `code` → hard failure | `code/skills.py:256–261` → `error="no code in upstream coder output"` |
| The code is run as a subprocess; success = `exit_code 0 and not timed_out` | `code/skills.py:262–268` |
| Markdown fences are tolerated but discouraged | `code/skills.py:parse_skill_json` strips them |
| 30s wall-clock cap, stdout/stderr caps, no real OS isolation | `code/sandbox.py:run_python` |

## The non-obvious bit

The sandbox runs the emitted code as a **standalone subprocess with an empty
namespace** — it never sees `INPUTS`. So the Coder must **inline any upstream
value it needs as a Python literal** in the source it emits. Code that tries
to reference the upstream output at runtime will fail with a `NameError`.

```python
# Good — values from INPUTS copied in as literals:
cities = {'Tokyo': 37.0, 'London': 9.0, 'Berlin': 3.7, 'Paris': 11.0}
target = 5.0
print(min(cities, key=lambda c: abs(cities[c] - target)))
```

## Coding constraints the prompt teaches

- Standard library only — no pip packages, no imports beyond stdlib.
- No network, no file writes, no `input()`. Self-contained.
- Print the final answer to **stdout** (nothing downstream reads stderr).
- `code` is a single JSON string: escape newlines as `\n`, no triple quotes,
  no markdown fences.

## Verified end-to-end

Against the live gateway:

- **Happy path** — coder (Gemini) emitted `{"code","rationale"}`, inlined the
  populations as a literal; `sandbox_executor` ran it → `exit_code: 0`,
  `stdout: "Berlin 3.7 million"`.
- **Failure path** — coder output missing `code` → `success=False`,
  `error="no code in upstream coder output"`.

## Related files

- [`docs/LEARNING_NOTES.md`](LEARNING_NOTES.md) — **Module 5** (canonical; review this first)
- [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) — DAG orchestration, recovery policy
- `code/prompts/coder.md` — the prompt this doc describes
- `code/prompts/sandbox_executor.md` — the rarely-LLM'd post-mortem prompt
- `code/skills.py` — dispatch + the sandbox bypass
- `code/sandbox.py` — the subprocess runner
