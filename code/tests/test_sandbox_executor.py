"""Tests for FR-404 — sandbox_executor fails gracefully on missing code.

FR-404 [UB, M, Part 4]:
  If the upstream Coder node's AgentResult.output does not contain a
  "code" field, the sandbox_executor node shall return
  AgentResult(success=False, error="no code in upstream coder output")
  WITHOUT attempting subprocess execution.

These tests drive skills.run_skill directly for a sandbox_executor node
whose upstream coder output omits `code`, and prove no subprocess is
spawned by making sandbox.run_python explode if it is ever called.

Run with:  uv run pytest tests/test_sandbox_executor.py -v
"""

import asyncio
import os
import sys

import pytest

# Allow importing from parent (code/) directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import sandbox
import skills
from schemas import AgentResult

ERROR_STRING = "no code in upstream coder output"


def _sandbox_node_graph(coder_output: dict):
    """Build a minimal graph_nodes dict: one upstream coder node feeding a
    sandbox_executor node. The coder node's result carries `coder_output`."""
    return {
        "n:coder": {
            "skill": "coder",
            "inputs": ["USER_QUERY"],
            "result": AgentResult(
                success=True, agent_name="coder", output=coder_output,
            ),
        },
        "n:sandbox": {
            "skill": "sandbox_executor",
            "inputs": ["n:coder"],
            "result": None,
        },
    }


def _run_sandbox(graph_nodes, monkeypatch):
    """Invoke run_skill for the sandbox_executor node, with run_python
    booby-trapped so any subprocess attempt fails the test loudly."""
    def _boom(*args, **kwargs):
        raise AssertionError(
            "sandbox.run_python was called — FR-404 requires no subprocess "
            "execution when upstream `code` is missing"
        )
    monkeypatch.setattr(sandbox, "run_python", _boom)

    skill = skills.SkillRegistry().get("sandbox_executor")
    result, _rendered = asyncio.run(
        skills.run_skill(
            skill, "n:sandbox", graph_nodes,
            session_id="test-fr404", query="compute something",
            failure_report=None,
        )
    )
    return result


def test_missing_code_field_fails_gracefully(monkeypatch):
    """Coder output has a rationale but no `code` key → graceful failure."""
    graph = _sandbox_node_graph({"rationale": "[logic] forgot to emit code"})
    result = _run_sandbox(graph, monkeypatch)

    assert result.success is False
    assert result.error == ERROR_STRING
    assert result.agent_name == "sandbox_executor"


def test_empty_code_field_fails_gracefully(monkeypatch):
    """An empty-string `code` is treated the same as missing — no subprocess."""
    graph = _sandbox_node_graph({"code": "", "rationale": "[logic] empty"})
    result = _run_sandbox(graph, monkeypatch)

    assert result.success is False
    assert result.error == ERROR_STRING


def test_present_code_field_does_run(monkeypatch):
    """Positive control: when `code` is present the branch DOES execute it,
    so the success path is distinct from the FR-404 failure path."""
    calls = {}

    def _fake_run(code, *args, **kwargs):
        calls["code"] = code
        return {"exit_code": 0, "timed_out": False, "stdout": "ok", "stderr": ""}

    monkeypatch.setattr(sandbox, "run_python", _fake_run)

    graph = _sandbox_node_graph({"code": "print('ok')"})
    skill = skills.SkillRegistry().get("sandbox_executor")
    result, _ = asyncio.run(
        skills.run_skill(
            skill, "n:sandbox", graph,
            session_id="test-fr404", query="compute something",
            failure_report=None,
        )
    )

    assert calls["code"] == "print('ok')"
    assert result.success is True
    assert result.error is None
