# PulseDAG Chrome Extension (FR-701 / FR-703)

A trigger + presentation UI for **PulseDAG-GithubRepo**. The popup lets you pick
languages and a time window, fires a run through the HTTP bridge, and renders the
ranked, relevance-filtered digest. The 🎲 button highlights a random pick from the
digest (FR-703). **Non-graded** — used in the demo video.

```
 popup ──POST /run──▶ bridge_server.py (:8109) ──▶ flow.Executor ──▶ digest
```

## 1. Start the bridge

The extension talks to the HTTP bridge from Issue #51 (CON-107), **not** the
Gateway LLM port 8108.

```bash
cd code
uv run python bridge_server.py        # listens on http://localhost:8109
```

A green dot in the popup header = bridge online; red = offline.

## 2. Load the extension

1. Open `chrome://extensions`
2. Toggle **Developer mode** (top-right)
3. Click **Load unpacked** and select this `extension/` folder
4. Pin **PulseDAG** and click the icon

## 3. Use it

- **Languages** — click chips to multi-select (at least one stays on).
- **Window** — daily / weekly / monthly.
- **Topic / mode** — free-text relevance filter (defaults to `agentic / MCP / dev-tooling`).
- **▶ Run PulseDAG** — calls the bridge and renders the digest.
- **🎲 Random pick** — highlights a random repo line from the digest.

Selections persist via `localStorage`.

## Files

| File | Purpose |
|------|---------|
| `manifest.json` | MV3 manifest; `host_permissions` for `localhost:8109` |
| `popup.html` / `popup.css` / `popup.js` | the popup UI + bridge client |
| `icons/` | generated icons (`make_icons.py` regenerates them) |

Regenerate icons: `uv run python icons/make_icons.py`.
