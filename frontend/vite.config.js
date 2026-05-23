import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // WebSocket frames: ws://localhost:5173/ws → ws://localhost:8000/ws
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
        changeOrigin: true,
      },
      // HTTP REST calls: /calibrate, /status → http://localhost:8000/...
      '/calibrate': { target: 'http://localhost:8000', changeOrigin: true },
      '/status':    { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
});
