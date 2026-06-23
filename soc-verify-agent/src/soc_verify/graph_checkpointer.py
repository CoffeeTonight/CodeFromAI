"""Persistent LangGraph checkpointer — survives CLI restart for graph resume."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

_lock = threading.Lock()
_checkpointers: dict[str, Any] = {}
_connections: dict[str, sqlite3.Connection] = {}


def get_graph_checkpointer(root: Path):
    """Return a SqliteSaver keyed by workspace root (one DB per root)."""
    key = str(root.resolve())
    with _lock:
        if key not in _checkpointers:
            from langgraph.checkpoint.sqlite import SqliteSaver

            db_path = Path(key) / "runs" / "graph_sessions" / "checkpoints.sqlite"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(db_path), check_same_thread=False)
            _connections[key] = conn
            _checkpointers[key] = SqliteSaver(conn)
        return _checkpointers[key]


def reset_graph_checkpointer_cache() -> None:
    """Close DB handles and clear in-process cache (test helper simulating new process)."""
    with _lock:
        for conn in _connections.values():
            conn.close()
        _connections.clear()
        _checkpointers.clear()