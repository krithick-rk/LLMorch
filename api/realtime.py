"""
LLMorch Phase 9 — Realtime event bus.
Manages WebSocket connections and broadcasts typed events.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Set

from fastapi import WebSocket
from api.models import RealtimeEvent


class ConnectionManager:
    """Manages active WebSocket client connections and event broadcasting."""

    def __init__(self) -> None:
        self._connections: Set[WebSocket] = set()
        self._meta: Dict[WebSocket, Dict[str, Any]] = {}
        self._sequence: int = 0
        self._counter: int = 0
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, project_id: str | None = None) -> str:
        await websocket.accept()
        async with self._lock:
            self._counter += 1
            conn_id = f"WS-SRV-{self._counter}"
            self._connections.add(websocket)
            self._meta[websocket] = {
                "conn_id": conn_id,
                "project_id": project_id,
                "connected_at": datetime.now(timezone.utc).isoformat()
            }
        print(f"[REALTIME_BACKEND][{conn_id}] connection_open project_id={project_id}")
        return conn_id

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            meta = self._meta.pop(websocket, None)
            self._connections.discard(websocket)
        conn_id = meta.get("conn_id") if meta else "WS-UNKNOWN"
        print(f"[REALTIME_BACKEND][{conn_id}] connection_close")

    async def broadcast(
        self,
        event_type: str,
        entity_type: str | None = None,
        entity_id: str | None = None,
        payload: Dict[str, Any] | None = None,
        project_id: str | None = None,
        run_id: str | None = None,
    ) -> RealtimeEvent:
        async with self._lock:
            self._sequence += 1
            seq = self._sequence

        p_id = project_id or (payload.get("project_id") if payload else None)
        r_id = run_id or (payload.get("run_id") if payload else None)

        event = RealtimeEvent(
            event_id=f"evt-{uuid.uuid4().hex[:12]}",
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            sequence=seq,
            project_id=p_id,
            run_id=r_id,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload or {},
        )

        message = event.model_dump_json()
        dead: List[WebSocket] = []

        async with self._lock:
            snapshot = list(self._connections)

        for ws in snapshot:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)

        async with self._lock:
            for ws in dead:
                self._connections.discard(ws)

        # Persist event to database
        try:
            from history.database import get_db_path, DatabaseService
            db = DatabaseService(get_db_path())
            actor = (payload.get("actor") or payload.get("agent_id") or "orchestrator") if payload else "orchestrator"
            tool = (payload.get("tool") or payload.get("tool_name")) if payload else None
            now_iso = event.timestamp.isoformat()
            with db.get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO events (
                        event_id, run_id, timestamp, event_type, actor, tool, payload, schema_version, project_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event.event_id, r_id, now_iso, event_type, actor, tool,
                    json.dumps(payload or {}), "1.0", p_id
                ))
                conn.commit()
        except Exception:
            pass

        return event

    def connection_count(self) -> int:
        return len(self._connections)

    async def send_sync_message(self, websocket: WebSocket) -> None:
        """On new connection, send a RESYNC event so client knows to refresh state."""
        async with self._lock:
            seq = self._sequence

        event = RealtimeEvent(
            event_id=f"evt-{uuid.uuid4().hex[:12]}",
            event_type="RESYNC",
            timestamp=datetime.now(timezone.utc),
            sequence=seq,
            entity_type=None,
            entity_id=None,
            payload={"message": "Connection established. Fetch current state from API."},
        )
        await websocket.send_text(event.model_dump_json())


# Singleton event manager shared across the application
event_manager = ConnectionManager()
