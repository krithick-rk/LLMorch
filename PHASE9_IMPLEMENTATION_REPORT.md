# PHASE 9 IMPLEMENTATION REPORT
## LLMorch — Analyst UI, Investigation Console, Realtime Operations

---

## Architecture

```
                    ┌─────────────────────────┐
                    │      React + Vite       │
                    │    Analyst Console      │
                    │    (ui/src/App.jsx)     │
                    └───────────┬─────────────┘
                                │
                    REST (/api) + WebSocket (/ws/events)
                                │
                    ┌───────────▼─────────────┐
                    │     FastAPI API         │
                    │   (api/app.py)          │
                    │   Realtime Gateway      │
                    │   (api/realtime.py)     │
                    └───────────┬─────────────┘
                                │
                    ┌───────────▼─────────────┐
                    │    LLMorch Control      │
                    │        Plane            │
                    ├─────────────────────────┤
                    │ Orchestrator            │
                    │ Scheduler               │
                    │ Agent Registry          │
                    │ History / Evidence      │
                    │ Validator               │
                    └─────────────────────────┘
```

---

## Baseline (Pre-Phase 9)

- Phase 0–8 regression: **197/197 PASS**
- No existing `api/` or `ui/` directory

---

## Backend Implementation

### FastAPI Application (`api/app.py`)
- Binds to `127.0.0.1:8000` by default (configurable via `LLMORCH_API_HOST/PORT`)
- CORS restricted to `localhost:5173` (Vite dev server)
- OpenAPI docs at `/api/docs`
- WebSocket realtime at `/ws/events`

### API Routers

| Router | File | Endpoints |
|--------|------|-----------|
| Tasks | `api/routers/tasks.py` | `GET /api/tasks`, `GET /api/tasks/{id}` |
| Agents | `api/routers/agents.py` | `GET /api/agents`, `GET /api/agents/{id}` |
| Findings | `api/routers/findings.py` | `GET /api/findings`, `GET /api/findings/{id}` |
| Evidence | `api/routers/evidence.py` | `GET /api/evidence`, `GET /api/evidence/{id}` |
| Timeline | `api/routers/timeline.py` | `GET /api/timeline` |
| Repository | `api/routers/repository.py` | `GET /api/repositories`, `/snapshots`, `/analysis-units`, `/security-surface` |
| Validation | `api/routers/validation.py` | `GET /api/validation`, `/reproducers` |
| Controls | `api/routers/controls.py` | `POST /api/controls/action`, `/feedback`, `GET /audit` |

### API Contracts (`api/models.py`)
All responses use typed Pydantic v2 models. No raw DB rows exposed.

### Session (`api/session.py`)
- Local single-user mode: auto-generates token printed at startup
- `X-Session-Token` header-based auth (extensible to multi-user)
- Invalid tokens → 401

---

## Realtime Architecture (`api/realtime.py`)

- **Transport**: WebSocket (`/ws/events`)
- **On connect**: `RESYNC` event sent immediately → client must refresh from API
- **Sequence numbers**: monotonic, enables gap detection
- **Dead connection cleanup**: automatic on send failure
- **Reconnect**: client auto-reconnects every 2.5s, receives RESYNC
- **Ping/pong**: `{"type":"ping"}` → `{"type":"pong"}` keepalive

### Event Envelope
```json
{
  "event_id": "evt-abc123def456",
  "event_type": "TASK_STATUS_CHANGED",
  "timestamp": "2026-09-24T10:00:00Z",
  "sequence": 42,
  "entity_type": "task",
  "entity_id": "task-abc123",
  "payload": {}
}
```

---

## Frontend Architecture (`ui/`)

- **Framework**: React 18 + Vite 4
- **Styling**: Custom CSS (no Tailwind) — dark glassmorphism theme
- **State**: API-backed (no shadow DB), realtime from WebSocket
- **API client**: `ui/src/api.js` — all requests go through this module
- **WS hook**: `ui/src/useRealtimeEvents.js` — RESYNC/gap-aware

---

## Screens

| # | Screen | Status |
|---|--------|--------|
| 1 | Run Overview | ✅ Live task counts, agent availability, recent task table |
| 2 | Task DAG | ✅ Clickable nodes, detail panel with runs |
| 3 | Repository Graph | ✅ Snapshots, Analysis Units with security-surface |
| 4 | Agent Panel | ✅ Dynamic — reflects registry, elastic 1–4 agents |
| 5 | Hypothesis Panel | ✅ Trust level indicators, state filter, evidence links |
| 6 | Evidence Viewer | ✅ Raw/canonical/semantic hash display, redaction |
| 7 | Timeline | ✅ Chronological events, event-type filter |
| 8 | Finding Dossier | ✅ Full dossier with evidence/reproducers/validation/feedback |
| 9 | Global Intelligence | ✅ Pattern events with trust notice |

---

## Control Plane Safety

Every analyst action follows this pipeline:
```
UI action
  → POST /api/controls/action
  → validate session
  → validate action type + target type
  → verify target exists (or 404)
  → policy check (high-impact requires reason)
  → persist auditable event to DB
  → apply state transition (via control plane, not raw mutation)
  → broadcast realtime event
  → return ControlResponse
```

**Finding state** — no PATCH/PUT/POST endpoint exists for findings.
The only valid path: `validator/decision service → finding state`.

**Evidence** — no creation endpoint. Read-only API only.

**Sensitive data** — provenance redaction strips `api_key`, `secret`, `password`, `token`, `private_key`, `credential` fields.

---

## Database Migrations (Phase 9)

Idempotent `ALTER TABLE ADD COLUMN` migrations added to `DatabaseService._init_db()`:
- `events`: `task_id`, `entity_type`, `entity_id`
- `evidence`: `finding_id`, `source_tool`, `timestamp`, `stdout`, `stderr`, etc.
- `findings`: `state`, `severity`, `created_at`, `updated_at`, etc.
- `validation_results`: `finding_id`, `timestamp`, `replay_count`, etc.
- `reproducers`: `finding_id`, `status`, `manifest_hash`

Helper `get_db_path()` added — respects `LLMORCH_DB_PATH` env override for test isolation.

---

## Tests

| Suite | Tests | Result |
|-------|-------|--------|
| `test_phase9_api.py` | API endpoints, auth, redaction | ✅ |
| `test_phase9_realtime.py` | WS connect, RESYNC, ordering, gap detection | ✅ |
| `test_phase9_controls.py` | Authority, audit trail, high-impact gate, no direct DB | ✅ |
| **Phase 9 total** | **72** | ✅ |
| **Full regression (P0–P9)** | **269** | ✅ |

---

## Security

- API binds to `127.0.0.1` only (no public exposure by default)
- CORS restricted to localhost origins
- No raw SQL endpoint, no shell execution endpoint
- No SQLite file download endpoint
- Evidence provenance redaction active
- Session token required (unauthenticated only allowed on localhost)
- High-impact operations require explicit `reason` field

---

## Known Limitations

1. **Task DAG** — dependencies rendered as flat node list (no graphical edge arrows). Full DAG edge rendering requires React Flow or Cytoscape integration via `npm install`.
2. **Repository Graph** — nodes displayed as tiles, not a force-directed graph. Cytoscape.js integration is the next step.
3. **Sandbox execution view** — visible in Evidence Viewer via `sandbox_id` field; dedicated sandbox screen pending.
4. **Budget visualization** — not yet exposed in UI (backend schemas exist but no budget API endpoint).
5. **Failover visualization** — events are captured in Timeline; dedicated failover lane is a future enhancement.

---

## Starting the System

```bash
# Terminal 1: Backend API
cd ~/LLMorch
python3 -m api.server

# Terminal 2: Frontend dev server
cd ~/LLMorch/ui
npm run dev
# → open http://localhost:5173
```
