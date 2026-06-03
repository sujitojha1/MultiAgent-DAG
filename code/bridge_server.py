"""HTTP bridge server for PulseDAG — Issue #51 (CON-107, FR-702).

Thin, NEW module.  Zero edits to flow.Executor internals.

What it does
------------
Listens on http://localhost:8109 (distinct from Gateway V8's :8108).
Accepts POST /run with a JSON body and calls flow.Executor.run().
Returns the final digest as JSON.

Request body schema
-------------------
{
  "languages": ["python", "rust"],   // one or more language names
  "window":    "weekly",             // "daily" | "weekly" | "monthly"
  "mode":      "agentic",            // free-form topic filter (optional)
  "session_id": "s8-abc123"         // optional: re-use a specific session id
}

Response body (200 OK)
----------------------
{
  "session_id": "s8-<hex>",
  "query":      "<the query string that was sent to the Executor>",
  "answer":     "<final answer from the Executor>"
}

Error responses
---------------
400 — missing/bad body
500 — Executor raised an exception

CON-107 compliance
------------------
- This is a SEPARATE module.  flow.py is untouched.
- git diff shows no change to Executor.run internals.
- Port 8109 is distinct from the Gateway V8 LLM port 8108.

Usage
-----
    uv run python bridge_server.py          # starts on :8109

    # From another terminal / the Chrome Extension:
    curl -s -X POST http://localhost:8109/run \\
         -H "Content-Type: application/json" \\
         -d '{"languages":["python","rust"],"window":"weekly","mode":"agentic"}' | python -m json.tool
"""

from __future__ import annotations

import asyncio
import json
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from typing import Any

# ── Query builder ─────────────────────────────────────────────────────────────

_WINDOW_MAP = {
    "daily":   "today",
    "weekly":  "this week",
    "monthly": "this month",
}

_DEFAULT_MODE = "agentic / MCP / dev-tooling"


def build_query(languages: list[str], window: str, mode: str | None) -> str:
    """Turn bridge request fields into the natural-language query the Planner expects."""
    lang_str = " and ".join(lang.strip().title() for lang in languages) if languages else "Python"
    period   = _WINDOW_MAP.get(window.lower(), "this week")
    topic    = mode.strip() if mode and mode.strip() else _DEFAULT_MODE

    return (
        f"Find the top trending {lang_str} repos {period}, "
        f"rank by momentum, and keep only what's relevant to {topic} "
        f"with a one-line why-it-matters each."
    )


# ── Async runner helper ───────────────────────────────────────────────────────

def _run_executor_sync(query: str, session_id: str | None) -> str:
    """Run Executor.run() in a fresh event loop (called from the HTTP handler thread)."""
    # Import here so bridge_server can be imported without starting the gateway.
    from flow import Executor  # noqa: PLC0415  (local import by design)

    return asyncio.run(Executor().run(query, session_id=session_id))


# ── HTTP handler ──────────────────────────────────────────────────────────────

_active_sessions: set[str] = set()


class BridgeHandler(BaseHTTPRequestHandler):
    """Handle POST /run and GET /health."""

    server_version = "PulseDAG-Bridge/1.0"
    # Silence the per-request log spam; set to True for verbose debugging.
    _verbose: bool = False

    def log_message(self, fmt: str, *args: Any) -> None:  # type: ignore[override]
        if self._verbose:
            super().log_message(fmt, *args)

    # ------------------------------------------------------------------
    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json({"status": "ok", "port": self.server.server_address[1]})
        elif self.path.startswith("/session/"):
            session_id = self.path.split("/")[-1]
            self._handle_session_status(session_id)
        else:
            self._send_json({"error": "not found"}, status=404)

    def _handle_session_status(self, session_id: str) -> None:
        from persistence import SessionStore

        store = SessionStore(session_id)
        g = None
        try:
            g = store.read_graph()
        except Exception as exc:
            self._send_json({"error": f"failed to read session graph: {exc}"}, status=500)
            return

        if g is None:
            # Graph not created yet (might be spinning up)
            status = "running" if session_id in _active_sessions else "unknown"
            self._send_json({
                "session_id": session_id,
                "status": status,
                "nodes": []
            })
            return

        nodes_list = []
        for nid, d in g.nodes(data=True):
            node_info = {
                "node_id": nid,
                "skill": d.get("skill"),
                "status": d.get("status"),
                "inputs": d.get("inputs", []),
            }
            res = d.get("result")
            if res:
                if hasattr(res, "elapsed_s"):
                    node_info["elapsed_s"] = res.elapsed_s
                    node_info["error"] = res.error
                elif isinstance(res, dict):
                    node_info["elapsed_s"] = res.get("elapsed_s")
                    node_info["error"] = res.get("error")
            nodes_list.append(node_info)

        # Determine overall status
        if session_id in _active_sessions:
            overall_status = "running"
        else:
            has_formatter_complete = any(
                n.get("skill") == "formatter" and n.get("status") == "complete"
                for n in nodes_list
            )
            has_any_failed = any(n.get("status") == "failed" for n in nodes_list)
            
            if has_formatter_complete:
                overall_status = "complete"
            elif has_any_failed:
                overall_status = "failed"
            else:
                has_pending_or_running = any(
                    n.get("status") in ("pending", "running")
                    for n in nodes_list
                )
                overall_status = "complete" if not has_pending_or_running else "running"

        # Try to find final answer
        answer = None
        for n in nodes_list:
            if n.get("skill") == "formatter" and n.get("status") == "complete":
                for nid, d in g.nodes(data=True):
                    if nid == n["node_id"]:
                        res = d.get("result")
                        if res:
                            output = res.output if hasattr(res, "output") else res.get("output", {})
                            answer = output.get("final_answer")
                if answer:
                    break

        if not answer:
            for nid in reversed(list(g.nodes)):
                d = g.nodes[nid]
                if d.get("status") == "complete" and d.get("result"):
                    res = d.get("result")
                    output = res.output if hasattr(res, "output") else res.get("output", {})
                    if isinstance(output, dict):
                        answer = output.get("final_answer") or json.dumps(output)[:2000]
                    else:
                        answer = str(output)
                    break

        self._send_json({
            "session_id": session_id,
            "status": overall_status,
            "nodes": nodes_list,
            "answer": answer
        })

    # ------------------------------------------------------------------
    def do_POST(self) -> None:
        if self.path != "/run":
            self._send_json({"error": "not found"}, status=404)
            return

        # Read body
        length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(length) if length else b""

        try:
            body: dict = json.loads(body_bytes or b"{}")
        except json.JSONDecodeError as exc:
            self._send_json({"error": f"invalid JSON: {exc}"}, status=400)
            return

        languages: list[str] = body.get("languages") or ["python"]
        window:    str        = body.get("window", "weekly")
        mode:      str | None = body.get("mode")
        session_id: str | None = body.get("session_id") or f"s8-{uuid.uuid4().hex[:8]}"

        # Validate
        if not isinstance(languages, list) or not languages:
            self._send_json({"error": "'languages' must be a non-empty list"}, status=400)
            return
        if window not in _WINDOW_MAP:
            self._send_json(
                {"error": f"'window' must be one of {list(_WINDOW_MAP)}"},
                status=400,
            )
            return

        query = build_query(languages, window, mode)
        print(f"\n[bridge] POST /run  sid={session_id}  query={query!r}", flush=True)

        _active_sessions.add(session_id)
        try:
            answer = _run_executor_sync(query, session_id)
        except Exception as exc:
            print(f"[bridge] Executor error: {exc}", file=sys.stderr, flush=True)
            self._send_json({"error": str(exc)}, status=500)
            return
        finally:
            _active_sessions.discard(session_id)

        self._send_json({"session_id": session_id, "query": query, "answer": answer})

    # ------------------------------------------------------------------
    def _send_json(self, payload: dict, *, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")  # Chrome Extension needs this
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        """Pre-flight CORS for the Chrome Extension."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


# ── Server bootstrap ──────────────────────────────────────────────────────────

BRIDGE_PORT = 8109


def make_server(port: int = BRIDGE_PORT) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("0.0.0.0", port), BridgeHandler)
    server.socket.setsockopt(
        __import__("socket").SOL_SOCKET,
        __import__("socket").SO_REUSEADDR,
        1,
    )
    return server


def run_server(port: int = BRIDGE_PORT, *, verbose: bool = False) -> None:
    BridgeHandler._verbose = verbose
    server = make_server(port)
    print(
        f"[bridge] PulseDAG HTTP bridge listening on http://0.0.0.0:{port}\n"
        f"[bridge] POST /run  {{languages, window, mode, session_id}}\n"
        f"[bridge] GET  /health\n"
        f"[bridge] Ctrl-C to stop.",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[bridge] shutting down", flush=True)
    finally:
        server.server_close()


def start_background(port: int = BRIDGE_PORT, *, verbose: bool = False) -> threading.Thread:
    """Start the bridge server in a daemon thread (useful for tests and notebooks)."""
    BridgeHandler._verbose = verbose
    server = make_server(port)
    t = threading.Thread(target=server.serve_forever, daemon=True, name="bridge-server")
    t.server = server  # type: ignore[attr-defined]
    t.start()
    return t


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="PulseDAG HTTP bridge — calls flow.Executor from a POST request."
    )
    parser.add_argument("--port", type=int, default=BRIDGE_PORT,
                        help=f"Port to listen on (default: {BRIDGE_PORT})")
    parser.add_argument("--verbose", action="store_true",
                        help="Log every HTTP request to stdout")
    args = parser.parse_args()
    run_server(port=args.port, verbose=args.verbose)
