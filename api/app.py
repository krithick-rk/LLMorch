"""
LLMorch Phase 9 — FastAPI application entry point.

Architecture:
    Browser → Frontend UI → REST + WebSocket → FastAPI → Control Plane
                                                              ↓
                                             Orchestrator / Scheduler / History / Evidence / Validator

Binding: localhost only by default (safe). Configurable via LLMORCH_API_HOST / LLMORCH_API_PORT.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.models import HealthResponse, SessionInfo
from api.session import require_session, get_default_token
from api.realtime import event_manager
from api.routers import (
    tasks,
    agents,
    findings,
    evidence,
    timeline,
    repository,
    validation,
    controls,
    models,
    tokens,
    settings,
)

# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="LLMorch Analyst Console API",
    description=(
        "Phase 9.1 REST + WebSocket API for the LLMorch hardware security "
        "vulnerability research orchestration system with Agent Switching, "
        "Model Registry, and Authoritative Token Accounting."
    ),
    version="9.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
# Allow only the local Vite dev server by default.
# Production deployments should restrict this further.
_FRONTEND_ORIGINS = os.environ.get(
    "LLMORCH_FRONTEND_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _FRONTEND_ORIGINS],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(tasks.router)
app.include_router(agents.router)
app.include_router(models.router)
app.include_router(tokens.router)
app.include_router(tokens.budgets_router)
app.include_router(settings.router)
app.include_router(settings.config_alias_router)
app.include_router(findings.router)
app.include_router(evidence.router)
app.include_router(timeline.router)
app.include_router(repository.router)
app.include_router(validation.router)
app.include_router(controls.router)


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/api/health", response_model=HealthResponse, tags=["health"])
def health():
    from history.database import get_db_path, DatabaseService
    try:
        db = DatabaseService(get_db_path())
        with db.get_connection() as conn:
            conn.execute("SELECT 1").fetchone()
        db_ok = True
    except Exception:
        db_ok = False
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        version="9.0.0",
        db_connected=db_ok,
        realtime_active=event_manager.connection_count() >= 0,
    )


# ─── Session bootstrap ────────────────────────────────────────────────────────

@app.get("/api/session", response_model=SessionInfo, tags=["session"])
def get_session(session: SessionInfo = Depends(require_session)):
    return session


@app.post("/api/session", response_model=dict, tags=["session"])
def create_new_session():
    from api.session import create_session
    token, sess = create_session()
    return {"session_token": token, "session_id": sess.session_id, "role": sess.role}


# ─── WebSocket realtime endpoint ──────────────────────────────────────────────

@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    """
    WebSocket endpoint for realtime event delivery.
    On connect: sends RESYNC so client knows to refresh API state.
    On disconnect: connection is cleaned up automatically.
    Event format: RealtimeEvent JSON with monotonic sequence numbers.
    """
    await event_manager.connect(websocket)
    await event_manager.send_sync_message(websocket)
    try:
        while True:
            # Keep connection alive; client may send pings
            data = await websocket.receive_text()
            # Clients can send {"type":"ping"} to check liveness
            if data.strip() == '{"type":"ping"}':
                await websocket.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        await event_manager.disconnect(websocket)
    except Exception:
        await event_manager.disconnect(websocket)


# ─── Startup / Shutdown ───────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    token = get_default_token()
    print("=" * 60)
    print("  LLMorch Analyst Console API  v9.0.0")
    print("=" * 60)
    print(f"  Docs:      http://127.0.0.1:8000/api/docs")
    print(f"  WS:        ws://127.0.0.1:8000/ws/events")
    print(f"  Session:   {token[:16]}...")
    print("  (pass as X-Session-Token header, or omit for local access)")
    print("=" * 60)


@app.on_event("shutdown")
async def shutdown():
    print("[LLMorch API] Shutting down.")
