import { useCallback, useEffect, useRef, useState } from 'react';

export const WS_STATUS = {
  CONNECTING: 'CONNECTING',
  CONNECTED: 'CONNECTED',
  RECONNECTING: 'RECONNECTING',
  DISCONNECTED: 'DISCONNECTED',
};

const MAX_RETRY_DELAY_MS = 30_000;

/**
 * Manages a WebSocket connection with automatic exponential-backoff reconnection.
 *
 * Returns:
 *   status       — WS_STATUS enum value (React state, triggers re-renders)
 *   message      — latest parsed JSON frame (React state, triggers re-renders)
 *   addRawListener(fn) — register a callback invoked on every message BEFORE
 *                        React state updates. Use for imperative chart updates
 *                        that must not trigger re-renders. Returns an unsub fn.
 *   reconnect()  — manually force an immediate reconnect
 */
export function useWebSocket(url) {
  const [status, setStatus]   = useState(WS_STATUS.CONNECTING);
  const [message, setMessage] = useState(null);

  const wsRef           = useRef(null);
  const retryCountRef   = useRef(0);
  const retryTimerRef   = useRef(null);
  const mountedRef      = useRef(true);
  const listenersRef    = useRef(new Set());
  // Stable ref to the connect function so closures inside event handlers
  // always call the latest version without a stale-closure bug.
  const connectRef      = useRef(null);

  const addRawListener = useCallback((fn) => {
    listenersRef.current.add(fn);
    return () => listenersRef.current.delete(fn);
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current) {
      // Remove event handlers before closing to suppress the onclose handler.
      wsRef.current.onopen    = null;
      wsRef.current.onmessage = null;
      wsRef.current.onclose   = null;
      wsRef.current.onerror   = null;
      wsRef.current.close();
    }

    const ws = new WebSocket(url);
    wsRef.current = ws;
    setStatus(WS_STATUS.CONNECTING);

    ws.onopen = () => {
      if (!mountedRef.current) return;
      retryCountRef.current = 0;
      setStatus(WS_STATUS.CONNECTED);
    };

    ws.onmessage = (event) => {
      if (!mountedRef.current) return;
      let data;
      try {
        data = JSON.parse(event.data);
      } catch {
        return;
      }
      // Notify imperative listeners first (chart updates, no React re-render).
      listenersRef.current.forEach((fn) => fn(data));
      // Then update React state (triggers re-renders for MotionAlert etc.).
      setMessage(data);
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      setStatus(WS_STATUS.RECONNECTING);
      const delay = Math.min(1_000 * 2 ** retryCountRef.current, MAX_RETRY_DELAY_MS);
      retryCountRef.current += 1;
      retryTimerRef.current = setTimeout(() => connectRef.current?.(), delay);
    };

    ws.onerror = () => {
      // onclose fires immediately after onerror; reconnect logic lives there.
      ws.close();
    };
  }, [url]);

  connectRef.current = connect;

  const reconnect = useCallback(() => {
    clearTimeout(retryTimerRef.current);
    retryCountRef.current = 0;
    connect();
  }, [connect]);

  useEffect(() => {
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      clearTimeout(retryTimerRef.current);
      if (wsRef.current) {
        wsRef.current.onopen    = null;
        wsRef.current.onmessage = null;
        wsRef.current.onclose   = null;
        wsRef.current.onerror   = null;
        wsRef.current.close();
      }
    };
  }, [connect]);

  return { status, message, addRawListener, reconnect };
}
