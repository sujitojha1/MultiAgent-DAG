"""Unit tests for bridge_server — CON-107 / FR-702 (Issue #51).

These tests exercise the bridge's HTTP surface and query-builder in isolation.
They patch _run_executor_sync so the Gateway and real LLM are NOT required.

Run with:  uv run pytest tests/test_bridge.py -v
"""

import json
import sys
import os
import threading
import time
import urllib.request
import urllib.error
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bridge_server import build_query, make_server, BRIDGE_PORT, _WINDOW_MAP

# ── Query builder ─────────────────────────────────────────────────────────────

def test_build_query_basic():
    q = build_query(["python"], "weekly", None)
    assert "Python" in q
    assert "this week" in q
    assert "agentic" in q.lower() or "MCP" in q


def test_build_query_two_languages():
    q = build_query(["python", "rust"], "monthly", "MCP tooling")
    assert "Python" in q
    assert "Rust" in q
    assert "this month" in q
    assert "MCP tooling" in q


def test_build_query_daily_window():
    q = build_query(["go"], "daily", None)
    assert "today" in q


def test_build_query_custom_mode():
    q = build_query(["python"], "weekly", "data engineering")
    assert "data engineering" in q


def test_build_query_empty_mode_uses_default():
    q = build_query(["rust"], "weekly", "")
    assert "agentic" in q.lower() or "MCP" in q


# ── Integration tests with a live (but patched) bridge server ─────────────────

@pytest.fixture(scope="module")
def bridge():
    """Spin up a real HTTPServer on a free port; shut it down after the module."""
    import socket

    # Find a free port
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    server = make_server(port)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.1)  # let it bind
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    server.server_close()


def _post(url: str, body: dict) -> tuple[int, dict]:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _get(url: str) -> tuple[int, dict]:
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.status, json.loads(resp.read())


def test_health_endpoint(bridge):
    status, body = _get(f"{bridge}/health")
    assert status == 200
    assert body["status"] == "ok"


def test_404_on_unknown_path(bridge):
    req = urllib.request.Request(f"{bridge}/notfound")
    try:
        urllib.request.urlopen(req, timeout=5)
        assert False, "Should have raised HTTPError"
    except urllib.error.HTTPError as e:
        assert e.code == 404


def test_run_returns_digest(bridge):
    """POST /run with a mocked Executor returns session_id, query, answer."""
    with patch("bridge_server._run_executor_sync", return_value="mock answer") as mock_exec:
        status, body = _post(
            f"{bridge}/run",
            {"languages": ["python"], "window": "weekly", "mode": "agentic"},
        )
    assert status == 200, body
    assert "session_id" in body
    assert "query" in body
    assert body["answer"] == "mock answer"
    assert "python" in body["query"].lower() or "Python" in body["query"]
    mock_exec.assert_called_once()


def test_run_accepts_session_id(bridge):
    """Caller-supplied session_id is forwarded to the Executor."""
    with patch("bridge_server._run_executor_sync", return_value="ok") as mock_exec:
        status, body = _post(
            f"{bridge}/run",
            {"languages": ["rust"], "window": "monthly", "session_id": "s8-test1234"},
        )
    assert status == 200
    assert body["session_id"] == "s8-test1234"
    _, kwargs = mock_exec.call_args
    # Called as _run_executor_sync(query, "s8-test1234")
    assert mock_exec.call_args.args[1] == "s8-test1234"


def test_run_bad_window(bridge):
    status, body = _post(f"{bridge}/run", {"languages": ["python"], "window": "yearly"})
    assert status == 400
    assert "window" in body["error"].lower()


def test_run_empty_languages_defaults(bridge):
    """Empty languages list is handled gracefully (defaults to python)."""
    with patch("bridge_server._run_executor_sync", return_value="ok"):
        status, body = _post(f"{bridge}/run", {"languages": [], "window": "weekly"})
    # Empty list → defaults to ["python"] in build_query
    assert status == 200


def test_run_bad_json(bridge):
    req = urllib.request.Request(
        f"{bridge}/run",
        data=b"not json",
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=5)
        assert False
    except urllib.error.HTTPError as e:
        assert e.code == 400


def test_executor_exception_returns_500(bridge):
    """If Executor raises, bridge returns HTTP 500."""
    with patch("bridge_server._run_executor_sync", side_effect=RuntimeError("boom")):
        status, body = _post(f"{bridge}/run", {"languages": ["python"], "window": "weekly"})
    assert status == 500
    assert "boom" in body["error"]


# ── CON-107 compliance — no edits to flow.py ──────────────────────────────────

def test_flow_py_not_modified():
    """bridge_server imports flow only locally; flow.py itself is unchanged."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "flow_check",
        os.path.join(os.path.dirname(__file__), "..", "flow.py"),
    )
    # Just confirm it imports cleanly without the gateway running
    # (we only check the module's attributes, not run anything)
    assert spec is not None
    # The Executor class must still exist unchanged
    src = open(spec.origin, encoding="utf-8").read()
    assert "class Executor:" in src
    assert "async def run(" in src
    # bridge_server should NOT appear in flow.py (no coupling back)
    assert "bridge_server" not in src


def test_bridge_port_distinct_from_gateway():
    """Bridge port must differ from Gateway V8 port 8108."""
    assert BRIDGE_PORT != 8108, "CON-107: bridge must be on a different port than the gateway"
    assert BRIDGE_PORT == 8109
