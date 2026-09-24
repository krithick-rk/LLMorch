"""
LLMorch Phase 9 — Session management.
Minimal local single-user session with token validation.
Designed so multi-user RBAC can be added later without changing the interface.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import Header, HTTPException, status

from api.models import SessionInfo

# In-memory single-user session store
# In production this would be replaced with a proper session backend
_sessions: dict[str, SessionInfo] = {}

# Bootstrap a default analyst session token for local use
DEFAULT_TOKEN = secrets.token_urlsafe(32)
_default_session = SessionInfo(
    session_id=str(uuid.uuid4()),
    created_at=datetime.now(timezone.utc),
    role="analyst",
)
_sessions[DEFAULT_TOKEN] = _default_session


def create_session() -> tuple[str, SessionInfo]:
    """Create a new session and return (token, session_info)."""
    token = secrets.token_urlsafe(32)
    session = SessionInfo(
        session_id=str(uuid.uuid4()),
        created_at=datetime.now(timezone.utc),
        role="analyst",
    )
    _sessions[token] = session
    return token, session


def validate_session(token: str) -> Optional[SessionInfo]:
    """Return session if token is valid, else None."""
    return _sessions.get(token)


def get_default_token() -> str:
    """Return the auto-generated default analyst token (printed at startup)."""
    return DEFAULT_TOKEN


# FastAPI dependency
def require_session(x_session_token: Optional[str] = Header(default=None)) -> SessionInfo:
    """
    FastAPI dependency. Validates X-Session-Token header.
    For local single-user mode the default token is printed at startup.
    """
    if x_session_token is None:
        # For local localhost-only deployments, allow unauthenticated access
        # with the default session (safe because API binds only to 127.0.0.1)
        return _default_session

    session = validate_session(x_session_token)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
        )
    return session
