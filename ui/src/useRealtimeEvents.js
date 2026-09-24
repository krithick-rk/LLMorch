/**
 * WebSocket realtime hook.
 * Connects to /ws/events, handles RESYNC, maintains sequence tracking,
 * and triggers a callback when events arrive.
 */
import { useEffect, useRef, useCallback, useState } from 'react';

const WS_URL = `ws://${window.location.host}/ws/events`;
const RECONNECT_DELAY_MS = 2500;

export function useRealtimeEvents(onEvent) {
  const wsRef = useRef(null);
  const seqRef = useRef(0);
  const timerRef = useRef(null);
  const [connected, setConnected] = useState(false);

  const connect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
    }
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      // Send ping every 25s to keep alive
      timerRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send('{"type":"ping"}');
        }
      }, 25000);
    };

    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);
        if (data.event_type === 'RESYNC') {
          // On RESYNC: client must refresh state from API
          seqRef.current = data.sequence;
          onEvent({ type: 'RESYNC', sequence: data.sequence });
          return;
        }
        // Gap detection
        if (data.sequence && seqRef.current > 0 && data.sequence !== seqRef.current + 1) {
          onEvent({ type: 'GAP_DETECTED', expected: seqRef.current + 1, got: data.sequence });
        }
        seqRef.current = data.sequence || seqRef.current;
        onEvent(data);
      } catch {}
    };

    ws.onerror = () => setConnected(false);
    ws.onclose = () => {
      setConnected(false);
      clearInterval(timerRef.current);
      // Auto-reconnect
      setTimeout(connect, RECONNECT_DELAY_MS);
    };
  }, [onEvent]);

  useEffect(() => {
    connect();
    return () => {
      clearInterval(timerRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect]);

  return connected;
}
