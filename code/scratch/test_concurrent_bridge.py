import json
import sys
import os
import threading
import time
import urllib.request
import urllib.error
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bridge_server import make_server, _active_sessions
from persistence import SessionStore
from schemas import AgentResult, NodeState
import networkx as nx

def run_server_background(server):
    server.serve_forever()

def test_endpoint():
    # Spin up server on a random free port
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        
    server = make_server(port)
    server_thread = threading.Thread(target=run_server_background, args=(server,), daemon=True)
    server_thread.start()
    time.sleep(0.2) # wait for bind
    
    url = f"http://127.0.0.1:{port}"
    session_id = "s8-testconcurrent"
    
    print("[test] Server running on", url)
    
    # 1. Setup a mock graph state to simulate what persistence would have
    store = SessionStore(session_id)
    g = nx.DiGraph()
    # Node 1 complete, Node 2 running, Node 3 pending
    g.add_node("n:1", skill="planner", status="complete", inputs=["USER_QUERY"])
    g.nodes["n:1"]["result"] = AgentResult(success=True, agent_name="planner", elapsed_s=4.6)
    g.add_node("n:2", skill="github_research", status="running", inputs=["n:1"])
    g.add_node("n:3", skill="distiller", status="pending", inputs=["n:2"])
    store.write_graph(g)
    
    # Simulate that this session is currently active
    _active_sessions.add(session_id)
    
    # 2. Query the /session/<id> endpoint concurrently
    try:
        req = urllib.request.Request(f"{url}/session/{session_id}")
        with urllib.request.urlopen(req, timeout=5) as resp:
            status = resp.status
            body = json.loads(resp.read().decode("utf-8"))
            
            print("[test] HTTP Status:", status)
            print("[test] Response JSON:")
            print(json.dumps(body, indent=2))
            
            assert status == 200
            assert body["session_id"] == session_id
            assert body["status"] == "running"
            assert len(body["nodes"]) == 3
            
            # Verify nodes list contains correct statuses
            nodes_map = {n["node_id"]: n for n in body["nodes"]}
            assert nodes_map["n:1"]["status"] == "complete"
            assert nodes_map["n:1"]["elapsed_s"] == 4.6
            assert nodes_map["n:2"]["status"] == "running"
            assert nodes_map["n:3"]["status"] == "pending"
            
            print("[test] CONCURRENT STATUS API VERIFIED SUCCESSFULLY!")
            
    except Exception as e:
        print("[test] FAILED:", e)
        sys.exit(1)
    finally:
        _active_sessions.discard(session_id)
        server.shutdown()
        server.server_close()
        # Clean up session files
        try:
            if store.graph_path.exists():
                store.graph_path.unlink()
            if store.dir.exists():
                store.nodes_dir.rmdir()
                store.dir.rmdir()
        except Exception:
            pass

if __name__ == "__main__":
    test_endpoint()
