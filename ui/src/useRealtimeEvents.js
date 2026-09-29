/**
 * WebSocket realtime hook for React components.
 * Connects to the centralized `realtimeClient` singleton.
 * Component rerenders or hook unmounts do NOT recreate or close the underlying WebSocket!
 */
import { useEffect, useState, useRef } from 'react';
import { realtimeClient, RealtimeState } from './realtimeClient';

export function useRealtimeEvents(onEvent) {
  const [state, setState] = useState(() => realtimeClient.getState());
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    // 1. Subscribe to state changes (debounced, stable)
    const unsubState = realtimeClient.subscribeState((newState) => {
      setState(newState);
    });

    // 2. Subscribe to event stream without recreating socket
    const unsubEvents = realtimeClient.subscribe((event) => {
      if (onEventRef.current) {
        onEventRef.current(event);
      }
    });

    return () => {
      unsubState();
      unsubEvents();
    };
  }, []);

  return state === RealtimeState.CONNECTED;
}

export function useRealtimeStatus() {
  const [status, setStatus] = useState(() => ({
    state: realtimeClient.getState(),
    connectionId: realtimeClient.currentConnectionId,
    isConnected: realtimeClient.isConnected(),
  }));

  useEffect(() => {
    return realtimeClient.subscribeState((state, connectionId) => {
      setStatus({
        state,
        connectionId,
        isConnected: state === RealtimeState.CONNECTED,
      });
    });
  }, []);

  return status;
}
