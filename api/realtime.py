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
        self._sequence: int = 0
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast(
        self,
        event_type: str,
        entity_type: str | None = None,
        entity_id: str | None = None,
        payload: Dict[str, Any] | None = None,
    ) -> RealtimeEvent:
        async with self._lock:
            self._sequence += 1
            seq = self._sequence

        event = RealtimeEvent(
            event_id=f"evt-{uuid.uuid4().hex[:12]}",
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            sequence=seq,
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
