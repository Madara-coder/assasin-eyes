"""
Assassin Eyes — FastAPI backend.

Endpoints:
  GET  /              health check
  GET  /status        current detector state (JSON)
  POST /calibrate     trigger a fresh calibration cycle
  WS   /ws            real-time RSSI + detection stream at BROADCAST_HZ
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Set

import config
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from processing.detector import AnomalyDetector, DetectorOutput, MotionState

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
log = logging.getLogger("assassin-eyes")


# ── Scanner selection ─────────────────────────────────────────────────────────

def _load_scanner() -> AsyncGenerator[float, None]:
    mode = config.SCANNER_MODE.lower()
    if mode == "mock":
        from sensor.mock_scanner import rssi_stream
        log.info("Scanner mode: MOCK (deterministic simulated data)")
    elif mode == "ping":
        from sensor.ping_scanner import rssi_stream
        log.info("Scanner mode: PING (ICMP RTT proxy, target=%s)", config.PING_TARGET)
    elif mode == "beacon":
        from sensor.beacon_scanner import rssi_stream  # type: ignore[import]
        log.info("Scanner mode: BEACON (Scapy monitor mode, iface=%s)", config.WIFI_INTERFACE)
    else:
        raise ValueError(f"Unknown SCANNER_MODE '{mode}'. Choose mock | ping | beacon.")
    return rssi_stream()


# ── Application state ─────────────────────────────────────────────────────────

class AppState:
    def __init__(self) -> None:
        self.detector = AnomalyDetector()
        self.last_output: DetectorOutput | None = None
        self.connected_clients: Set[WebSocket] = set()
        self._scanner_task: asyncio.Task | None = None

    def start_scanner(self) -> None:
        self._scanner_task = asyncio.create_task(
            _run_scanner_loop(self), name="scanner-loop"
        )

    def stop_scanner(self) -> None:
        if self._scanner_task and not self._scanner_task.done():
            self._scanner_task.cancel()


app_state = AppState()


# ── Background scanner loop ───────────────────────────────────────────────────

async def _run_scanner_loop(state: AppState) -> None:
    """
    Continuously reads from the RSSI scanner, runs it through the detector,
    and fans out the result to all connected WebSocket clients.
    """
    stream = _load_scanner()
    log.info("Scanner loop started — broadcasting at %d Hz", config.BROADCAST_HZ)

    async for rssi in stream:
        output = state.detector.process(rssi)
        state.last_output = output

        if state.connected_clients:
            payload = json.dumps(_serialise(output))
            dead: Set[WebSocket] = set()
            for ws in list(state.connected_clients):
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead.add(ws)
            state.connected_clients -= dead


def _serialise(o: DetectorOutput) -> dict:
    return {
        "ts": round(o.ts, 3),
        "rssi_raw": o.rssi_raw,
        "rssi_ma": round(o.rssi_ma, 2),
        "variance": round(o.variance, 4),
        "anomaly_score": round(o.anomaly_score, 3),
        "state": o.state.value,
        "calibrated": o.calibrated,
        "calibration_progress": round(o.calibration_progress, 3),
    }


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting Assassin Eyes backend …")
    app_state.detector.start_calibration()
    app_state.start_scanner()
    yield
    log.info("Shutting down …")
    app_state.stop_scanner()


# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="Assassin Eyes",
    description="Wi-Fi RSSI human motion detector",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── HTTP endpoints ────────────────────────────────────────────────────────────

@app.get("/", tags=["health"])
async def health():
    return {"status": "ok", "scanner_mode": config.SCANNER_MODE}


@app.get("/status", tags=["detector"])
async def get_status():
    o = app_state.last_output
    if o is None:
        return {"status": "warming_up"}
    return _serialise(o)


@app.post("/calibrate", tags=["detector"])
async def trigger_calibration():
    """
    Restart the calibration cycle.  Call this with the room empty to establish
    a fresh RSSI variance baseline.
    """
    app_state.detector.start_calibration()
    log.info("Calibration restarted via HTTP POST /calibrate")
    return {
        "status": "calibrating",
        "duration_seconds": config.CALIBRATION_SECONDS,
    }


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    app_state.connected_clients.add(websocket)
    client = websocket.client
    log.info("WebSocket client connected: %s:%s", client.host, client.port)

    try:
        # Keep the connection open; the scanner loop pushes data to clients.
        # We listen for any incoming messages (e.g. a ping keepalive) so the
        # server detects a dropped connection promptly.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        log.info("WebSocket client disconnected: %s:%s", client.host, client.port)
    finally:
        app_state.connected_clients.discard(websocket)
