"""Tests for NFR-401 — Sandbox Constraints.

Verifies that sandbox.run_python:
  - Truncates stdout and stderr at the configured cap (1 MB default)
  - Terminates a process that exceeds the wall-clock timeout (30 s default)
  - Returns timed_out=True and exit_code=-1 on timeout
  - Returns exit_code=0 and correct stdout for well-behaved code
  - Scrubs env vars (API keys etc.) from the child process

Run with:  uv run pytest tests/test_sandbox.py -v
"""

import sys
import os

import pytest

# Allow importing from parent (code/) directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sandbox import run_python, DEFAULT_TIMEOUT_S, DEFAULT_STDOUT_CAP, DEFAULT_STDERR_CAP


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_simple_print():
    """Well-behaved code produces correct stdout and exit_code 0."""
    result = run_python('print("hello nfr401")')
    assert result["exit_code"] == 0
    assert "hello nfr401" in result["stdout"]
    assert result["timed_out"] is False
    assert result["stdout_truncated"] is False


def test_math_computation():
    """Coder-style velocity computation executes and returns numeric output."""
    code = """\
data = [("repo/a", 5000, 1000), ("repo/b", 200, 190)]
for name, total, gained in data:
    v = (gained / total) * 100
    print(f"{name}: {v:.2f}%")
"""
    result = run_python(code)
    assert result["exit_code"] == 0
    assert "repo/a: 20.00%" in result["stdout"]
    assert "repo/b: 95.00%" in result["stdout"]


# ---------------------------------------------------------------------------
# NFR-401 — 30-second timeout cap
# ---------------------------------------------------------------------------

def test_timeout_enforced():
    """An infinite loop is killed after the configured timeout."""
    # Use a tiny timeout so the test completes quickly.
    result = run_python("while True: pass", timeout_s=2)
    assert result["timed_out"] is True, "Process should have been killed"
    assert result["exit_code"] == -1, "Timed-out process must return exit_code -1"
    assert "killed after 2s" in result["stderr"], "Kill message should appear in stderr"


def test_timeout_uses_default():
    """Default timeout constant is 30 s (not overridden by a shorter value)."""
    assert DEFAULT_TIMEOUT_S == 30, (
        f"NFR-401 requires 30 s cap; got {DEFAULT_TIMEOUT_S}"
    )


def test_fast_code_not_killed():
    """Code that finishes well inside the timeout is NOT marked as timed_out."""
    result = run_python("import time; time.sleep(0); print('done')", timeout_s=10)
    assert result["timed_out"] is False
    assert "done" in result["stdout"]


# ---------------------------------------------------------------------------
# NFR-401 — 1 MB stdout/stderr cap
# ---------------------------------------------------------------------------

def test_stdout_cap_enforced():
    """stdout is truncated at the configured cap and stdout_truncated is True."""
    cap = 4_000  # use a small cap so the test runs fast
    # Write just enough bytes to exceed the cap.
    code = f"print('x' * {cap + 500})"
    result = run_python(code, stdout_cap=cap)
    assert result["stdout_truncated"] is True, "stdout should be flagged as truncated"
    assert "truncated" in result["stdout"], "Truncation marker should appear in output"
    assert len(result["stdout"]) <= cap + 300, "Truncated output should be near the cap"


def test_stderr_cap_enforced():
    """stderr is truncated at the configured cap and stderr_truncated is True."""
    cap = 4_000
    code = f"import sys; sys.stderr.write('e' * {cap + 500})"
    result = run_python(code, stderr_cap=cap)
    assert result["stderr_truncated"] is True
    assert "truncated" in result["stderr"]


def test_stdout_cap_default():
    """Default stdout cap constant is 1 MB (NFR-401)."""
    assert DEFAULT_STDOUT_CAP == 1_000_000, (
        f"NFR-401 requires 1 MB stdout cap; got {DEFAULT_STDOUT_CAP}"
    )


def test_stderr_cap_default():
    """Default stderr cap constant is 1 MB (NFR-401)."""
    assert DEFAULT_STDERR_CAP == 1_000_000, (
        f"NFR-401 requires 1 MB stderr cap; got {DEFAULT_STDERR_CAP}"
    )


def test_normal_output_not_truncated():
    """Output under the cap is NOT marked truncated."""
    result = run_python('print("short output")')
    assert result["stdout_truncated"] is False
    assert result["stderr_truncated"] is False


# ---------------------------------------------------------------------------
# Env scrubbing (security boundary)
# ---------------------------------------------------------------------------

def test_api_key_scrubbed():
    """Sensitive env vars are NOT inherited by the child process."""
    # Inject a fake key into the parent env and verify it doesn't leak.
    os.environ["FAKE_SECRET_KEY_NFR401"] = "super-secret"
    try:
        code = """\
import os
v = os.environ.get("FAKE_SECRET_KEY_NFR401", "NOT_FOUND")
print(v)
"""
        result = run_python(code)
        assert "NOT_FOUND" in result["stdout"], (
            "Secret env var should be scrubbed from child process"
        )
        assert "super-secret" not in result["stdout"]
    finally:
        del os.environ["FAKE_SECRET_KEY_NFR401"]


# ---------------------------------------------------------------------------
# Non-zero exit code passthrough
# ---------------------------------------------------------------------------

def test_nonzero_exit_code():
    """A script that calls sys.exit(42) returns exit_code=42."""
    result = run_python("import sys; sys.exit(42)")
    assert result["exit_code"] == 42
    assert result["timed_out"] is False
