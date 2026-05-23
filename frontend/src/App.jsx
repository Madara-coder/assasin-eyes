import { useCallback } from 'react';
import Dashboard from './components/Dashboard';
import { useWebSocket } from './hooks/useWebSocket';

// WebSocket URL is relative so the Vite dev proxy handles it transparently.
// In production, replace with an absolute wss:// URL pointing at your server.
const WS_URL = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`;

export default function App() {
  const { status, message, addRawListener, reconnect } = useWebSocket(WS_URL);

  const handleRecalibrate = useCallback(async () => {
    try {
      const res = await fetch('/calibrate', { method: 'POST' });
      if (!res.ok) console.error('Calibration request failed:', res.status);
    } catch (err) {
      console.error('Calibration request error:', err);
    }
  }, []);

  return (
    <Dashboard
      message={message}
      status={status}
      addRawListener={addRawListener}
      onRecalibrate={handleRecalibrate}
    />
  );
}
