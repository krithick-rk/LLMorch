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

from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse, Response

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


# ─── Frontend UI & Static Files ───────────────────────────────────────────────

_REPO_ROOT = Path(__file__).resolve().parent.parent
_UI_DIST = _REPO_ROOT / "ui" / "dist"

_FALLBACK_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>LLMorch — Autonomous Vulnerability Research Console</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #0b0f19;
      color: #f1f5f9;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      margin: 0;
      padding: 1.5rem;
      box-sizing: border-box;
    }
    .card {
      background: #111827;
      border: 1px solid #1f2937;
      border-radius: 10px;
      padding: 2rem 2.5rem;
      max-width: 580px;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
    }
    h1 {
      color: #38bdf8;
      font-size: 1.5rem;
      margin-top: 0;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    p { color: #94a3b8; font-size: 0.95rem; line-height: 1.5; }
    pre {
      background: #030712;
      border: 1px solid #1f2937;
      border-radius: 6px;
      padding: 0.75rem 1rem;
      overflow-x: auto;
    }
    code { color: #38bdf8; font-family: monospace; font-size: 0.9rem; }
    .btn {
      display: inline-block;
      background: #0284c7;
      color: white;
      padding: 0.6rem 1.2rem;
      border-radius: 6px;
      margin-top: 1rem;
      text-decoration: none;
      font-weight: 500;
      transition: background 0.15s ease;
    }
    .btn:hover { background: #0369a1; }
  </style>
</head>
<body>
  <div class="card">
    <h1>🛡️ LLMorch Analyst Console API</h1>
    <p>The backend control plane is running. To serve the visual console web interface:</p>
    <pre><code>cd ui && npm run build</code></pre>
    <p>Or start the live-reloading Vite dev server:</p>
    <pre><code>cd ui && npm run dev</code></pre>
    <a href="/api/docs" class="btn">Explore API Docs &rarr;</a>
  </div>
</body>
</html>
"""

# Mount /assets if the directory exists
if (_UI_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=str(_UI_DIST / "assets")), name="ui-assets")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    fav = _UI_DIST / "favicon.ico"
    if fav.is_file():
        return FileResponse(fav)
    svg = _UI_DIST / "vite.svg"
    if svg.is_file():
        return FileResponse(svg, media_type="image/svg+xml")
    return Response(status_code=204)


@app.get("/vite.svg", include_in_schema=False)
def vite_svg():
    svg = _UI_DIST / "vite.svg"
    if svg.is_file():
        return FileResponse(svg, media_type="image/svg+xml")
    return Response(status_code=404)


@app.get("/", include_in_schema=False)
def serve_root():
    index_file = _UI_DIST / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    return HTMLResponse(content=_FALLBACK_HTML)


_SPA_CLIENT_ROUTES = {
    "", "overview", "dag", "repo", "repository", "agents",
    "hypothesis", "hypotheses", "evidence", "timeline",
    "dossier", "findings", "intel", "intelligence", "settings",
    "tasks", "runs", "models", "tokens", "budgets",
}


@app.get("/{full_path:path}", include_in_schema=False)
def spa_fallback(full_path: str):
    # 1. Never intercept API, WebSocket, or internal paths
    if (
        full_path.startswith("api/")
        or full_path == "api"
        or full_path.startswith("ws/")
        or full_path == "ws"
        or full_path.startswith("history/")
        or full_path == "history"
    ):
        raise HTTPException(status_code=404, detail="Not Found")

    # 2. Check if a static file exists in _UI_DIST
    target = (_UI_DIST / full_path).resolve()
    try:
        if _UI_DIST.resolve() in target.parents and target.is_file():
            return FileResponse(target)
    except Exception:
        pass

    # 3. Reject any request with a file extension that does not exist in dist (e.g. .db, .py, .json)
    last_segment = full_path.split("/")[-1]
    if "." in last_segment and not last_segment.startswith("."):
        raise HTTPException(status_code=404, detail="Not Found")

    # 4. For known SPA routes or route paths without file extensions, serve index.html
    root_route = full_path.split("/")[0]
    if root_route in _SPA_CLIENT_ROUTES or "." not in last_segment:
        index_file = _UI_DIST / "index.html"
        if index_file.is_file():
            return FileResponse(index_file)
        return HTMLResponse(content=_FALLBACK_HTML)

    raise HTTPException(status_code=404, detail="Not Found")


# ─── Startup / Shutdown ───────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    token = get_default_token()
    print("=" * 60)
    print("  LLMorch Analyst Console  v9.1.0")
    print("=" * 60)
    print("  Console:   http://127.0.0.1:8000/")
    print("  Docs:      http://127.0.0.1:8000/api/docs")
    print("  WS:        ws://127.0.0.1:8000/ws/events")
    print(f"  Session:   {token[:16]}...")
    print("  (pass as X-Session-Token header, or omit for local access)")
    print("=" * 60)


@app.on_event("shutdown")
async def shutdown():
    print("[LLMorch API] Shutting down.")
