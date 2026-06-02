# Architecture Review: Atomic Persistence (NFR-301)

**Requirement:** NFR-301 — Atomic Persistence [Must]  
> While any node state or graph state is being written to `state/sessions/<sid>/`, the system
> shall write to a temporary file first and call `os.replace` to swap it in, ensuring the
> previous file is preserved if the process is killed between the write and the swap.

**Review date:** 2026-06-03  
**Verdict: ✅ COMPLIANT — every state write goes through write-temp-then-`os.replace`.**

---

## 1. The Atomic Write Primitive

All writes funnel through one private helper in [`persistence.py`](../code/persistence.py):

```python
# persistence.py · lines 41–47
def _atomic_write(path: Path, data: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")   # e.g. n_001.json.tmp
    mode = "wb" if isinstance(data, bytes) else "w"
    with open(tmp, mode) as f:
        f.write(data)
    os.replace(tmp, path)   # atomic on POSIX; best-effort on Windows
```

`os.replace` is atomic on POSIX (rename(2)) and "as atomic as Windows allows" on Win32 — the OS
guarantees that at any point in time the target path contains either the old complete file or the
new complete file, never a partial write.

---

## 2. Call-site Audit — Every Public Write Path

| Write surface | Call site | File | Lines |
|---|---|---|---|
| `write_query()` | `_atomic_write(self.query_path, query)` | `persistence.py` | 86 |
| `write_graph()` | `_atomic_write(self.graph_path, json.dumps(...))` | `persistence.py` | 110 |
| `write_node()` | `_atomic_write(self._node_path(…), state.model_dump_json(…))` | `persistence.py` | 158 |

**Result: 3 public write methods, all 3 call `_atomic_write` exclusively.**  
There is exactly one `os.replace` call in the entire codebase (`persistence.py:47`), and it is
inside `_atomic_write`. No write method bypasses it.

---

## 3. Call-sites in the Executor (`flow.py`)

All writes from the executor go through the `SessionStore` public API — no direct file I/O:

| Location | Call | What it persists |
|---|---|---|
| `flow.py:184` | `store.write_query(query)` | User's verbatim query |
| `flow.py:221` | `store.write_graph(graph.g)` | Graph before layer dispatch (marks nodes `running`) |
| `flow.py:230–237` | `store.write_node(NodeState(…))` | Node result after completion |
| `flow.py:276` | `store.write_graph(graph.g)` | Graph snapshot after the full ready-layer finishes |
| `flow.py:303–305` | `store.write_node(NodeState(…, status="running"))` | Node marked `running` before execution |

Every call routes through `SessionStore` → `_atomic_write` → `os.replace`.

---

## 4. SIGKILL + Resume Safety (FR-105 / NFR-501)

The atomic write pattern directly enables the SIGKILL-resume path:

```
[Normal flow]                      [SIGKILL mid-write scenario]
write data to .tmp  ──►  .tmp      write data to .tmp  ──► SIGKILL here
os.replace(.tmp → path) ──► path   os.replace never called ──► .tmp orphaned
                                   ──► old `path` is still intact ✓
```

When `flow.Executor.run` resumes a session:
1. `store.read_all_nodes()` skips any orphaned `.tmp` files (they don't match `n_*.json`)
2. Nodes whose last written status was `running` are reset to `pending` (NFR-501)
3. Re-execution proceeds from node boundaries — no partial writes can corrupt recovery

---

## 5. `read_all_nodes()` Resilience

The reader is hardened against the one failure mode that can still occur — a corrupt `.json` file
from an OS crash mid-`os.replace` (extremely rare but non-zero):

```python
# persistence.py · lines 175–183
for p in sorted(self.nodes_dir.glob("n_*.json")):
    try:
        states.append(NodeState.model_validate_json(p.read_text()))
    except (OSError, ValueError) as e:
        print(f"[persistence] WARNING: skipped corrupt node file {p}: …", file=sys.stderr)
```

Corrupt files are skipped with a loud warning, never silently dropped — consistent with the
review-round-3 feedback that bare `except: continue` was masking resume failures.

---

## 6. Graph-Load Integrity (`read_graph`)

The graph reader validates every `AgentResult` on load:

```python
# persistence.py · lines 124–135
for nid, d in g.nodes(data=True):
    if d.pop("_result_typed", False) and isinstance(d.get("result"), dict):
        try:
            d["result"] = AgentResult.model_validate(d["result"])
        except (ValueError, TypeError) as e:
            raise SessionLoadError(…) from e
```

A graph file that cannot be fully round-tripped raises `SessionLoadError` immediately rather
than silently degrading — preventing downstream `isinstance(…, AgentResult)` mismatches.

---

## 7. Verdict

| Check | Result |
|---|---|
| All writes use temp-file + `os.replace` | ✅ |
| No in-place overwrites exist | ✅ |
| Orphaned `.tmp` files excluded from resume reads | ✅ |
| Corrupt files produce loud warning, not silent drop | ✅ |
| Graph load raises on schema mismatch | ✅ |
| SIGKILL mid-write leaves previous file intact | ✅ |

**NFR-301 is fully satisfied.** No code changes required — this document closes the traceability gap.

---

*Reviewed against commit `03b7d25`. See also [docs/requirements.md §8](requirements.md) row NFR-301.*
