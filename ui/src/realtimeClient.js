/**
 * Centralized Realtime Client for LLMorch.
 * 
 * Strict architectural guarantees:
 * 1. Exactly ONE WebSocket connection per active project context.
 * 2. Stable State Machine: DISCONNECTED, CONNECTING, CONNECTED, RECONNECTING, FAILED.
 * 3. Monotonically increasing Connection IDs (WS-1, WS-2...).
 * 4. Comprehensive lifecycle logging:
 *    connection_created, connection_open, connection_close, connection_error,
 *    heartbeat_sent, heartbeat_received, reconnect_scheduled, reconnect_attempt,
 *    subscription_created, subscription_removed, duplicate_prevented.
 * 5. Bounded exponential backoff (1s, 2s, 4s, 8s, 15s max) with ±20% jitter.
 *    Reset backoff counter ONLY after connection is stable for > 5000ms.
 * 6. Debounced UI state updates (150ms) to eliminate sub-second visual flickering.
 * 7. Page navigation & component rerender do NOT recreate WebSocket.
 * 8. Fallback polling support and project-scoped event distribution.
 */

export const RealtimeState = {
  DISCONNECTED: 'DISCONNECTED',
  CONNECTING: 'CONNECTING',
  CONNECTED: 'CONNECTED',
  RECONNECTING: 'RECONNECTING',
  FAILED: 'FAILED',
};

const BACKOFF_STEPS = [1000, 2000, 4000, 8000, 15000];
const HEARTBEAT_INTERVAL_MS = 20000;
const STABILITY_THRESHOLD_MS = 5000;
const MAX_RECONNECT_ATTEMPTS = 10;
const STATE_DEBOUNCE_MS = 150;

class RealtimeClient {
  constructor() {
    this.connectionCounter = 0;
    this.currentConnectionId = null;
    this.ws = null;
    this.state = RealtimeState.DISCONNECTED;
    this.debouncedState = RealtimeState.DISCONNECTED;

    this.activeProjectId = null;
    this.activeRunId = null;

    this.reconnectAttempt = 0;
    this.reconnectTimer = null;
    this.heartbeatTimer = null;
    this.stabilityTimer = null;
    this.debounceTimer = null;

    this.seq = 0;
    this.listeners = new Set();
    this.stateListeners = new Set();

    // Fallback polling callbacks
    this.fallbackPollers = new Set();
    this.fallbackTimer = null;
  }

  log(lifecycleEvent, details = {}) {
    const connId = this.currentConnectionId || 'WS-INIT';
    const ts = new Date().toISOString();
    const payloadStr = Object.keys(details).length ? ` ${JSON.stringify(details)}` : '';
    console.log(`[REALTIME][${ts}][${connId}] ${lifecycleEvent}${payloadStr}`);
  }

  /**
   * Set active project/run context.
   * Connects once on project selection.
   * Closes cleanly and reconnects on project switch.
   * Disconnects when project is cleared.
   */
  setProject(projectId, runId = null) {
    this.activeRunId = runId;

    if (!projectId) {
      if (this.activeProjectId) {
        this.log('subscription_removed', { project_id: this.activeProjectId });
        this.activeProjectId = null;
        this.disconnect('no_project');
      }
      return;
    }

    if (this.activeProjectId === projectId) {
      // Same project: no reconnection needed!
      return;
    }

    // Project switched
    if (this.activeProjectId) {
      this.log('subscription_removed', { old_project_id: this.activeProjectId, new_project_id: projectId });
      this.disconnect('project_switch');
    }

    this.activeProjectId = projectId;
    this.reconnectAttempt = 0;
    this.log('subscription_created', { project_id: projectId });
    this.connect();
  }

  /**
   * Connects to backend WebSocket stream.
   * Prevents duplicate connections if already connecting or open.
   */
  connect() {
    // Prevent duplicate connection if socket is already open or in progress
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      this.log('duplicate_prevented', {
        reason: 'Connection already active',
        connection_id: this.currentConnectionId,
        readyState: this.ws.readyState
      });
      return;
    }

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    this.connectionCounter += 1;
    this.currentConnectionId = `WS-${this.connectionCounter}`;
    const connId = this.currentConnectionId;

    this.setState(this.reconnectAttempt > 0 ? RealtimeState.RECONNECTING : RealtimeState.CONNECTING);
    this.log('connection_created', { connection_id: connId, project_id: this.activeProjectId });

    const host = window.location.host;
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const pParam = this.activeProjectId ? `?project_id=${encodeURIComponent(this.activeProjectId)}` : '';
    const wsUrl = `${protocol}//${host}/ws/events${pParam}`;

    try {
      const socket = new WebSocket(wsUrl);
      this.ws = socket;

      socket.onopen = () => {
        if (this.currentConnectionId !== connId) return;
        this.log('connection_open', { connection_id: connId });
        this.setState(RealtimeState.CONNECTED);

        // Mark stable after 5s to reset exponential backoff
        if (this.stabilityTimer) clearTimeout(this.stabilityTimer);
        this.stabilityTimer = setTimeout(() => {
          if (this.state === RealtimeState.CONNECTED && this.currentConnectionId === connId) {
            this.reconnectAttempt = 0;
            this.log('connection_stable', { connection_id: connId });
          }
        }, STABILITY_THRESHOLD_MS);

        // Start heartbeat ping loop
        this.startHeartbeat(socket, connId);
      };

      socket.onmessage = (evt) => {
        if (this.currentConnectionId !== connId) return;
        try {
          const raw = evt.data;
          if (raw === '{"type":"pong"}' || raw.includes('"pong"')) {
            this.log('heartbeat_received', { connection_id: connId });
            return;
          }

          const data = JSON.parse(raw);

          // RESYNC event from backend
          if (data.event_type === 'RESYNC' || data.type === 'RESYNC') {
            this.seq = data.sequence || this.seq;
            this.broadcastToSubscribers({ type: 'RESYNC', ...data });
            return;
          }

          // Gap detection
          if (data.sequence && this.seq > 0 && data.sequence !== this.seq + 1) {
            this.broadcastToSubscribers({
              type: 'GAP_DETECTED',
              expected: this.seq + 1,
              got: data.sequence
            });
          }
          this.seq = data.sequence || this.seq;

          // Project-scoped filtering
          if (data.project_id && this.activeProjectId && data.project_id !== this.activeProjectId) {
            return;
          }

          this.broadcastToSubscribers(data);
        } catch (err) {
          // JSON parse or handler error
        }
      };

      socket.onerror = (err) => {
        if (this.currentConnectionId !== connId) return;
        this.log('connection_error', { connection_id: connId });
      };

      socket.onclose = (evt) => {
        if (this.currentConnectionId !== connId) return;
        this.log('connection_close', {
          connection_id: connId,
          code: evt.code,
          reason: evt.reason || 'normal_close'
        });
        this.cleanupSocket();

        // If closed intentionally via project switch or no project, do not auto-reconnect
        if (evt.code === 1000 || !this.activeProjectId) {
          this.setState(RealtimeState.DISCONNECTED);
          return;
        }

        this.scheduleReconnect();
      };
    } catch (err) {
      this.log('connection_error', { connection_id: connId, error: String(err) });
      this.scheduleReconnect();
    }
  }

  startHeartbeat(socket, connId) {
    if (this.heartbeatTimer) clearInterval(this.heartbeatTimer);
    this.heartbeatTimer = setInterval(() => {
      if (socket.readyState === WebSocket.OPEN && this.currentConnectionId === connId) {
        try {
          socket.send('{"type":"ping"}');
          this.log('heartbeat_sent', { connection_id: connId });
        } catch {
          // Error sending ping
        }
      }
    }, HEARTBEAT_INTERVAL_MS);
  }

  scheduleReconnect() {
    if (this.reconnectAttempt >= MAX_RECONNECT_ATTEMPTS) {
      this.setState(RealtimeState.FAILED);
      this.log('reconnect_failed_max_attempts', { attempts: this.reconnectAttempt });
      return;
    }

    this.reconnectAttempt += 1;
    const baseDelay = BACKOFF_STEPS[Math.min(this.reconnectAttempt - 1, BACKOFF_STEPS.length - 1)];
    // Add jitter: ±20%
    const jitter = 0.8 + Math.random() * 0.4;
    const delay = Math.round(baseDelay * jitter);

    this.setState(RealtimeState.RECONNECTING);
    this.log('reconnect_scheduled', {
      attempt: this.reconnectAttempt,
      delay_ms: delay,
      max_attempts: MAX_RECONNECT_ATTEMPTS
    });

    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = setTimeout(() => {
      this.log('reconnect_attempt', { attempt: this.reconnectAttempt });
      this.connect();
    }, delay);
  }

  cleanupSocket() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
    if (this.stabilityTimer) {
      clearTimeout(this.stabilityTimer);
      this.stabilityTimer = null;
    }
    if (this.ws) {
      try {
        this.ws.onopen = null;
        this.ws.onmessage = null;
        this.ws.onerror = null;
        this.ws.onclose = null;
        if (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING) {
          this.ws.close();
        }
      } catch {}
      this.ws = null;
    }
  }

  disconnect(reason = 'manual') {
    this.log('connection_close', { reason, connection_id: this.currentConnectionId });
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.cleanupSocket();
    this.setState(RealtimeState.DISCONNECTED);
  }

  setState(newState) {
    this.state = newState;

    // Debounce the state notification so sub-millisecond socket blips don't flicker the UI
    if (this.debounceTimer) clearTimeout(this.debounceTimer);

    if (newState === RealtimeState.CONNECTED) {
      // Connected can be immediate or fast
      this.debouncedState = RealtimeState.CONNECTED;
      this.notifyStateListeners();
    } else {
      this.debounceTimer = setTimeout(() => {
        this.debouncedState = this.state;
        this.notifyStateListeners();
      }, STATE_DEBOUNCE_MS);
    }
  }

  notifyStateListeners() {
    for (const listener of this.stateListeners) {
      try {
        listener(this.debouncedState, this.currentConnectionId);
      } catch (err) {
        console.error('[REALTIME] Error in state listener:', err);
      }
    }
  }

  broadcastToSubscribers(event) {
    for (const listener of this.listeners) {
      try {
        listener(event);
      } catch (err) {
        console.error('[REALTIME] Error in event listener:', err);
      }
    }
  }

  /**
   * Subscribe to event stream.
   * Returns an unsubscribe function.
   * Does NOT recreate the WebSocket.
   */
  subscribe(callback) {
    this.listeners.add(callback);
    return () => {
      this.listeners.delete(callback);
    };
  }

  /**
   * Subscribe to debounced state changes.
   * Returns an unsubscribe function.
   */
  subscribeState(callback) {
    this.stateListeners.add(callback);
    // Immediate callback with current debounced state
    try {
      callback(this.debouncedState, this.currentConnectionId);
    } catch {}
    return () => {
      this.stateListeners.delete(callback);
    };
  }

  getState() {
    return this.debouncedState;
  }

  isConnected() {
    return this.debouncedState === RealtimeState.CONNECTED;
  }
}

// Export singleton instance
export const realtimeClient = new RealtimeClient();
