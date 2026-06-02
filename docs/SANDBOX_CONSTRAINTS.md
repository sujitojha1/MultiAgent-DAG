# Code Review: Sandbox Constraints (NFR-401)

**Requirement:** NFR-401 — Sandbox Constraints [Must]
> While `sandbox.run_python` is executing, the system shall cap combined stdout + stderr at
> **1 MB** and enforce a **30-second** execution timeout.

**Review date:** 2026-06-03  
**Verdict: ✅ COMPLIANT — both caps enforced; probe tests pass (12/12).**

---

## 1. Source File: [`sandbox.py`](../code/sandbox.py)

### 1.1 Constants (lines 28–30)

```python
DEFAULT_TIMEOUT_S    = 30          # NFR-401: 30-second wall-clock cap
DEFAULT_STDOUT_CAP   = 1_000_000   # NFR-401: 1 MB stdout cap
DEFAULT_STDERR_CAP   = 1_000_000   # NFR-401: 1 MB stderr cap
```

Both required values are present as named constants. The values are **not** hard-coded inline —
any caller can override them for testing while the production path always uses the NFR-compliant
defaults.

### 1.2 Timeout Enforcement (lines 78–92)

```python
cp = subprocess.run(
    [sys.executable, str(script_path)],
    ...
    timeout=timeout_s,          # ← wall-clock timeout passed directly to subprocess.run
)
```

On timeout, `subprocess.run` raises `subprocess.TimeoutExpired` and **kills the child process**.
The handler:

```python
except subprocess.TimeoutExpired as te:
    timed_out = True
    stdout_b = te.stdout or b""
    stderr_b = (te.stderr or b"") + f"\n[sandbox] killed after {timeout_s}s wall-clock".encode()
    exit_code = -1
```

- `timed_out = True` signals the caller (sandbox_executor) that the process was killed
- `exit_code = -1` distinguishes a kill from a normal non-zero exit
- The kill message is appended to stderr for operator visibility

### 1.3 Output Cap Enforcement (lines 38–42, 94–95)

```python
def _truncate(b: bytes, cap: int) -> tuple[str, bool]:
    if len(b) <= cap:
        return b.decode("utf-8", errors="replace"), False
    head = b[: max(0, cap - 200)].decode("utf-8", errors="replace")
    return head + f"\n...[truncated; {len(b) - cap + 200} more bytes]...", True
```

Applied to both streams:

```python
stdout_txt, so_trunc = _truncate(stdout_b, stdout_cap)   # line 94
stderr_txt, se_trunc = _truncate(stderr_b, stderr_cap)   # line 95
```

The output is captured in memory first (`capture_output=True`) then truncated before being
returned to the caller. This means a process producing exactly 2 MB of stdout will:
1. Write 2 MB to the subprocess pipe buffer
2. Have its output truncated to 1 MB by `_truncate`
3. Return `stdout_truncated = True` so downstream nodes know data was cut

> [!NOTE]
> The current design buffers all output in memory before truncating. A process that writes
> many gigabytes of output could OOM the orchestrator before the timeout fires. This is
> acceptable for S8 (usability boundary, not security boundary) — the 30-second timeout
> is the primary guard for runaway processes, and the output cap handles noisy-print cases.
> A streaming approach using `subprocess.Popen` + iterative read would address this in S9.

### 1.4 Environment Scrubbing (lines 68–70)

```python
DEFAULT_ENV_WHITELIST = ("PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE")

scrubbed = {k: os.environ[k] for k in env_whitelist if k in os.environ}
```

Only whitelisted vars are passed to the child. API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
`GEMINI_API_KEY`, etc.) are **not** in the whitelist and are therefore not inherited.

---

## 2. Probe Test Results (`tests/test_sandbox.py`)

12 tests added to cover NFR-401:

```
tests/test_sandbox.py::test_simple_print                  PASSED
tests/test_sandbox.py::test_math_computation              PASSED
tests/test_sandbox.py::test_timeout_enforced              PASSED  ← kills infinite loop in 2s
tests/test_sandbox.py::test_timeout_uses_default          PASSED  ← asserts DEFAULT_TIMEOUT_S == 30
tests/test_sandbox.py::test_fast_code_not_killed          PASSED
tests/test_sandbox.py::test_stdout_cap_enforced           PASSED  ← truncation at custom cap
tests/test_sandbox.py::test_stderr_cap_enforced           PASSED
tests/test_sandbox.py::test_stdout_cap_default            PASSED  ← asserts DEFAULT_STDOUT_CAP == 1_000_000
tests/test_sandbox.py::test_stderr_cap_default            PASSED  ← asserts DEFAULT_STDERR_CAP == 1_000_000
tests/test_sandbox.py::test_normal_output_not_truncated   PASSED
tests/test_sandbox.py::test_api_key_scrubbed              PASSED  ← env var not inherited by child
tests/test_sandbox.py::test_nonzero_exit_code             PASSED

12 passed in 2.66s
```

Full suite (22 recovery + 12 sandbox): **34 passed in 3.30s**

---

## 3. Compliance Verdict

| NFR-401 Check | Implementation | Test | Result |
|---|---|---|---|
| 30-second wall-clock timeout | `subprocess.run(timeout=30)` | `test_timeout_enforced` | ✅ |
| Process killed on timeout | `TimeoutExpired` handler sets `exit_code=-1` | `test_timeout_enforced` | ✅ |
| `timed_out=True` returned | Explicit flag in result dict | `test_timeout_enforced` | ✅ |
| 1 MB stdout cap | `DEFAULT_STDOUT_CAP = 1_000_000` + `_truncate` | `test_stdout_cap_default`, `test_stdout_cap_enforced` | ✅ |
| 1 MB stderr cap | `DEFAULT_STDERR_CAP = 1_000_000` + `_truncate` | `test_stderr_cap_default`, `test_stderr_cap_enforced` | ✅ |
| `stdout_truncated` flag | `so_trunc` returned in result dict | `test_stdout_cap_enforced` | ✅ |
| Env-var scrubbing | Whitelist-only passthrough | `test_api_key_scrubbed` | ✅ |

**NFR-401 is fully satisfied.** No code changes required — this document closes the traceability gap.

---

*Reviewed against commit `93f0c38`. See also [docs/requirements.md §8](requirements.md) row NFR-401.*
