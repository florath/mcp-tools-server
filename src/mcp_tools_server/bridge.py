#!/usr/bin/env python3
"""
MCP stdio-to-HTTP bridge for mcp-tools-server.

Codex spawns this as a subprocess STDIO MCP server.  It inherits codex's
working directory, automatically creates a session on the persistent HTTP
mcp-tools-server for that directory, bridges MCP JSON-RPC over stdio to the
HTTP REST API, and cleans up the session on exit.

Result: switching project directories requires no config changes — just run
codex from the project directory.

Configuration in ~/.codex/config.toml:

    [mcp_servers.mcp_file_server]
    command = "mcp-session-bridge"

Optional environment variable overrides:
    MCP_TOOLS_HOST      HTTP server host  (default: 127.0.0.1)
    MCP_TOOLS_PORT      HTTP server port  (default: 7091)
    MCP_WORKING_DIR     Override working directory (default: $PWD)

Session lifecycle
-----------------
- A session is created (or refreshed) on every MCP ``initialize`` message.
  Codex sends ``initialize`` both at startup and after a ``/compact``, so
  this is the natural point to get a clean session.
- If a tool call fails because the session has expired (e.g. the HTTP server
  was restarted), the bridge recreates the session and retries once.
- On process exit the active session is deleted from the server.
"""
import atexit
import http.client
import json
import os
import sys
from typing import Any, Dict, Optional

SERVER_HOST: str = os.environ.get("MCP_TOOLS_HOST", "127.0.0.1")
SERVER_PORT: int = int(os.environ.get("MCP_TOOLS_PORT", "7091"))
WORKING_DIR: str = os.environ.get("MCP_WORKING_DIR", os.getcwd())

_session_id: Optional[str] = None


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only — no external dependencies)
# ---------------------------------------------------------------------------

def _http(method: str, path: str, body: Any = None,
          extra_headers: Optional[Dict[str, str]] = None) -> tuple[int, Dict]:
    """Return (http_status, parsed_body)."""
    conn = http.client.HTTPConnection(SERVER_HOST, SERVER_PORT, timeout=30)
    headers = {"Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    payload = json.dumps(body).encode() if body is not None else b""
    conn.request(method, path, payload, headers)
    resp = conn.getresponse()
    status = resp.status
    data = resp.read()
    conn.close()
    return status, (json.loads(data) if data else {})


def _create_session(directory: str) -> str:
    _, result = _http("POST", "/sessions", {"directory": directory})
    if not result.get("success"):
        raise RuntimeError(
            f"mcp-session-bridge: failed to create session for '{directory}': "
            f"{result.get('error', 'unknown error')}"
        )
    return result["session_id"]


def _delete_session(session_id: str) -> None:
    try:
        conn = http.client.HTTPConnection(SERVER_HOST, SERVER_PORT, timeout=5)
        conn.request("DELETE", f"/sessions/{session_id}", b"",
                     {"Content-Type": "application/json"})
        conn.getresponse()
        conn.close()
    except Exception:
        pass


def _refresh_session() -> None:
    """Delete the current session (if any) and open a fresh one."""
    global _session_id
    if _session_id:
        _delete_session(_session_id)
    _session_id = _create_session(WORKING_DIR)


def _is_session_error(status: int, result: Dict) -> bool:
    """Return True when the HTTP response indicates a missing/expired session."""
    if status not in (400, 403):
        return False
    error_msg = (result.get("error") or result.get("details") or "").lower()
    return "session" in error_msg or "no active session" in error_msg


# ---------------------------------------------------------------------------
# MCP JSON-RPC message handler
# ---------------------------------------------------------------------------

def _handle(msg: Dict) -> Optional[Dict]:
    method: str = msg.get("method", "")
    msg_id = msg.get("id")       # None → notification, no response expected
    params: Dict = msg.get("params") or {}

    if msg_id is None:
        return None              # notification — no response needed

    if method == "initialize":
        # Codex sends initialize at startup AND after /compact.
        # Refresh the session each time so we always have a valid one.
        try:
            _refresh_session()
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32603, "message": str(exc)},
            }
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}, "resources": {}},
                "serverInfo": {
                    "name": "mcp-tools-server-bridge",
                    "version": "1.0.0",
                },
            },
        }

    if method == "tools/list":
        _, data = _http("GET", "/tools/schemas")
        tools = [
            {
                "name": t["function"]["name"],
                "description": t["function"].get("description", ""),
                "inputSchema": t["function"].get("parameters", {"type": "object"}),
            }
            for t in data.get("tools", [])
        ]
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": tools}}

    # MCP requires these endpoints to exist even when the server has no resources.
    # Returning "Method not found" causes codex to enter retry loops.
    if method == "resources/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"resources": []}}

    if method == "resources/templates/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"resourceTemplates": []}}

    if method == "tools/call":
        tool_name: str = params.get("name", "")
        arguments: Dict = params.get("arguments") or {}
        try:
            status, result = _http(
                "POST", f"/{tool_name}/v1", arguments,
                {"X-MCP-Session-ID": _session_id} if _session_id else {},
            )
            # Auto-recover: if the session expired (e.g. server was restarted),
            # create a new session and retry once.
            if _is_session_error(status, result):
                _refresh_session()
                status, result = _http(
                    "POST", f"/{tool_name}/v1", arguments,
                    {"X-MCP-Session-ID": _session_id},
                )
            text = json.dumps(result.get("result", result))
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"content": [{"type": "text", "text": text}]},
            }
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32603, "message": str(exc)},
            }

    # Unknown method
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _cleanup() -> None:
    if _session_id:
        _delete_session(_session_id)


def main() -> None:
    atexit.register(_cleanup)

    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue
        response = _handle(msg)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
