# Assassin Eyes

Wi-Fi RSSI-based device-free human motion detector with a real-time browser dashboard.

---

## How It Works (quick summary)

A home router broadcasts Wi-Fi beacon frames ~10 times per second.  When a human
body enters the room it absorbs and scatters RF energy, causing measurable
fluctuations in the Received Signal Strength Indicator (RSSI).  This application:

1. Captures RSSI from beacon frames (or simulates them in mock mode).
2. Runs a sliding-window variance filter to quantify signal instability.
3. Compares variance to a calibrated empty-room baseline → anomaly score.
4. Streams results over WebSockets to a React dashboard at 10 Hz.

---

## Project Structure

```
wifi-radar/
├── backend/
│   ├── config.py               # All tunable parameters
│   ├── main.py                 # FastAPI app + WebSocket /ws
│   ├── requirements.txt
│   ├── processing/
│   │   ├── filters.py          # MovingAverage, RollingVariance
│   │   └── detector.py         # AnomalyDetector (calibration + hysteresis)
│   └── sensor/
│       ├── mock_scanner.py     # Simulated RSSI (no hardware)
│       ├── ping_scanner.py     # ICMP RTT proxy (no root needed)
│       └── beacon_scanner.py   # Scapy beacon RSSI (Phase 5, needs root)
└── frontend/
    ├── package.json
    ├── vite.config.js          # Dev proxy: /ws → ws://localhost:8000/ws
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── index.html
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── index.css
        ├── hooks/
        │   └── useWebSocket.js # WS connection + exponential-backoff reconnect
        ├── utils/
        │   └── signalProcessor.js  # RingBuffer, timestamp formatter
        └── components/
            ├── Dashboard.jsx   # Root layout + header
            ├── SignalChart.jsx # Chart.js imperative RSSI chart (zero re-renders)
            └── MotionAlert.jsx # CALIBRATING / CLEAR / MOTION status banner
```

---

## Phase 2 — Backend Setup & Run

### Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.11 or 3.12 |
| pip | latest |

### 1 — Create a virtual environment

```bash
cd wifi-radar/backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

### 2 — Install dependencies

```bash
pip install -r requirements.txt
```

### 3 — Configure the scanner mode

Open `config.py` and set `SCANNER_MODE`:

| Value | Description | Requirements |
|---|---|---|
| `"mock"` | Deterministic simulated data | None — works everywhere |
| `"ping"` | ICMP RTT proxy | Router reachable via `PING_TARGET` |
| `"beacon"` | Real Scapy RSSI capture | Root/admin + monitor mode (Phase 5) |

For Phase 2 development, leave `SCANNER_MODE = "mock"`.

### 4 — Start the server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

You should see:

```
INFO  Scanner mode: MOCK (deterministic simulated data)
INFO  Scanner loop started — broadcasting at 10 Hz
INFO  Uvicorn running on http://0.0.0.0:8000
```

### 5 — Verify the endpoints

```bash
# Health check
curl http://localhost:8000/

# Latest detector snapshot
curl http://localhost:8000/status

# Trigger a fresh calibration (room must be empty)
curl -X POST http://localhost:8000/calibrate
```

### 6 — Connect to the WebSocket stream

Use `wscat`, Postman, or any WebSocket client:

```bash
npx wscat -c ws://localhost:8000/ws
```

You will receive JSON frames at 10 Hz:

```json
{
  "ts": 1716478823.41,
  "rssi_raw": -61.7,
  "rssi_ma": -61.4,
  "variance": 14.7,
  "anomaly_score": 3.21,
  "state": "MOTION",
  "calibrated": true,
  "calibration_progress": 1.0
}
```

**State values:**

| `state` | Meaning |
|---|---|
| `"CALIBRATING"` | Collecting empty-room baseline (first 20 s) |
| `"CLEAR"` | No motion detected |
| `"MOTION"` | Human movement detected |

---

## Tuning Parameters (`config.py`)

| Parameter | Default | Effect |
|---|---|---|
| `WINDOW_SIZE` | 15 | Larger = smoother but slower to react |
| `CALIBRATION_SECONDS` | 20 | Longer = more accurate baseline |
| `ANOMALY_THRESHOLD` | 2.8 | Lower = more sensitive (more false positives) |
| `MOTION_CONFIRM_FRAMES` | 3 | Frames above threshold before MOTION triggers |
| `CLEAR_CONFIRM_FRAMES` | 5 | Frames below threshold before CLEAR triggers |

---

---

## Phase 3 — Frontend Setup & Run

### Prerequisites

| Requirement | Version |
|---|---|
| Node.js | 18 LTS or 20 LTS |
| npm | 9+ (bundled with Node) |

The backend must be running on port 8000 before you start the frontend.

### 1 — Install dependencies

```bash
cd wifi-radar/frontend
npm install
```

### 2 — Start the dev server

```bash
npm run dev
```

You should see:

```
  VITE v5.x.x  ready in XXX ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: http://192.168.x.x:5173/
```

Open **http://localhost:5173** in your browser.

### 3 — What you will see

| Time | Behaviour |
|---|---|
| 0 – 20 s | Amber **CALIBRATING** banner with progress bar; chart starts filling |
| 20 s | Transitions to green **ALL CLEAR**; anomaly score appears |
| ~32 s | First mock motion burst fires; banner turns red **MOTION DETECTED** |
| ~36 s | Burst ends; returns to **ALL CLEAR** |
| Every 12 s | Motion burst repeats on the mock scanner cycle |

### 4 — Running both servers together (recommended)

Open two terminal tabs:

**Terminal 1 — backend**
```bash
cd wifi-radar/backend
source .venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 — frontend**
```bash
cd wifi-radar/frontend
npm run dev
```

### 5 — How the proxy works

The Vite dev server proxies:

| Browser request | Forwarded to |
|---|---|
| `ws://localhost:5173/ws` | `ws://localhost:8000/ws` |
| `POST /calibrate` | `http://localhost:8000/calibrate` |
| `GET /status` | `http://localhost:8000/status` |

No CORS or mixed-content issues in development.  In production, put both behind
the same Nginx/Caddy reverse proxy using the same mapping.

### 6 — Production build

```bash
cd wifi-radar/frontend
npm run build    # outputs to frontend/dist/
npm run preview  # serve the built output locally on port 4173
```

---

---

## Phase 4 — Full Dashboard (VarianceGauge · MetricsPanel · CalibrationPanel)

No new dependencies are required. Phase 4 is entirely within the frontend.

### New components

| Component | File | Description |
|---|---|---|
| `VarianceGauge` | `src/components/VarianceGauge.jsx` | SVG arc gauge, 240° sweep, three coloured zone tracks, animated needle |
| `MetricsPanel` | `src/components/MetricsPanel.jsx` | 3×2 grid of live metric cards (RSSI, MA, σ², anomaly, threshold, Hz) |
| `CalibrationPanel` | `src/components/CalibrationPanel.jsx` | Calibration status, last-calibrated timestamp, computed baseline σ², Recalibrate button |

### Dashboard layout

```
┌───────────────────────────────────────────────────────────┐
│  Header: title + WS connection status pill                │
├───────────────────────────────────────────────────────────┤
│  MotionAlert banner (CALIBRATING / CLEAR / MOTION)        │
├─────────────────────────────┬─────────────────────────────┤
│  Live RSSI chart (2/3)      │  Variance arc gauge (1/3)  │
├─────────────────────────────┼─────────────────────────────┤
│  Signal metrics — 3×2 grid  │  Calibration panel (1/3)   │
│  (2/3)                      │  + Recalibrate button       │
└─────────────────────────────┴─────────────────────────────┘
```

### How to run (same as Phase 3)

```bash
# Terminal 1
cd wifi-radar/backend && source .venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2
cd wifi-radar/frontend && npm run dev
```

Open **http://localhost:5173**.  
After the 20-second calibration the full dashboard populates with live values.  
Use the **Recalibrate** button (bottom of the Calibration panel) to restart baseline collection.

### Gauge colour zones

| Zone | Anomaly score range | Meaning |
|---|---|---|
| Green | 0 – 1.0× | Signal stable, below baseline variance |
| Amber | 1.0 – 2.8× | Elevated — background activity or minor disruption |
| Red | 2.8×+ | Threshold exceeded — motion detected |

---

---

## Phase 5 — Real Hardware Scanners

### New / updated files

| File | Description |
|---|---|
| `backend/sensor/beacon_scanner.py` | Scapy AsyncSniffer → asyncio.Queue bridge; radiotap `dBm_AntSignal` extraction; BSSID filter; rate-limiter |
| `backend/config.py` | Added `TARGET_BSSID`, `WIFI_CHANNEL` |
| `scripts/setup_monitor.sh` | Enables monitor mode on Linux, auto-reads config.py defaults |
| `scripts/teardown_monitor.sh` | Restores managed mode and re-enables NetworkManager |

---

### Scanner A — Beacon Frame (recommended, most accurate)

Captures RSSI directly from the router's 802.11 beacon frames via the radiotap header.  
**Requires:** root/sudo + Wi-Fi interface in monitor mode.

#### Step 1 — Find your Wi-Fi interface name

```bash
# Linux
iw dev
# Look for the Interface line, e.g. "Interface wlan0"

# macOS
networksetup -listallhardwareports
# Look for "Wi-Fi" hardware, note the Device (e.g. en0)
```

#### Step 2 — (Linux only) Enable monitor mode

```bash
sudo bash scripts/setup_monitor.sh wlan0 6
# Replace wlan0 with your interface, 6 with your router's Wi-Fi channel
```

Confirm it worked:
```bash
iw dev wlan0 info | grep type
# Should output: type monitor
```

#### Step 3 — Find your router's BSSID

```bash
# Linux (while still in managed mode, or use another adapter)
iwlist wlan0 scan | grep -E 'Address|ESSID'

# macOS
/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport -s

# Any OS — check your router's admin page (usually 192.168.1.1)
# The BSSID is listed as "Wireless MAC Address" or similar.
```

#### Step 4 — Update config.py

```python
SCANNER_MODE   = "beacon"
WIFI_INTERFACE = "wlan0"      # your interface in monitor mode
TARGET_BSSID   = "aa:bb:cc:dd:ee:ff"  # your router's MAC (lowercase)
WIFI_CHANNEL   = 6            # your router's channel
```

#### Step 5 — Start the backend with root

```bash
cd wifi-radar/backend
source .venv/bin/activate
sudo .venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

You should see:
```
INFO  Scanner mode: BEACON (Scapy monitor mode, iface=wlan0)
INFO  Beacon sniffer started  iface=wlan0  bssid=aa:bb:cc:dd:ee:ff
INFO  Scanner loop started — broadcasting at 10 Hz
```

#### Step 6 — When you're done

```bash
sudo bash scripts/teardown_monitor.sh wlan0
```

---

### Scanner B — ICMP Ping (fallback, no root needed)

Uses round-trip time to the router as a proxy for signal quality.  Less sensitive
than beacon capture but requires zero hardware setup.

```python
# backend/config.py
SCANNER_MODE = "ping"
PING_TARGET  = "192.168.1.1"   # your router's IP address
```

Start normally (no sudo required):
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

### macOS notes

macOS restricts raw 802.11 frame capture.  Options:

| Option | Effort | Quality |
|---|---|---|
| Use `"ping"` scanner | Zero | Low sensitivity |
| Use a USB Wi-Fi adapter (e.g. Alfa AWUS036ACS) on Linux VM | Medium | Full RSSI |
| Enable monitor mode on en0 via `airport` utility + SIP | High | Full RSSI |

For development and demos, `"mock"` and `"ping"` modes both run without any macOS restrictions.

---

### Troubleshooting beacon scanner

| Symptom | Likely cause | Fix |
|---|---|---|
| `RuntimeError: No beacon frames received …` | Interface not in monitor mode | Run `setup_monitor.sh` |
| `PermissionError: [Errno 1] Operation not permitted` | Not running as root | Use `sudo uvicorn …` |
| Frames captured but RSSI is always `None` | Driver doesn't expose `dBm_AntSignal` | Try a different Wi-Fi adapter |
| RSSI shows but signal is very stable (no motion response) | Wrong BSSID or wrong channel | Verify `TARGET_BSSID` and `WIFI_CHANNEL` |
| NetworkManager keeps reverting interface to managed | `nmcli` not available | Kill `wpa_supplicant` manually: `sudo pkill wpa_supplicant` |

---

---

## Phase 6 — Integration Testing · Threshold Tuning · Production

### New files

| File | Description |
|---|---|
| `tests/smoke_test.py` | Unit tests for filters + detector; integration tests for HTTP endpoints and WS schema |
| `scripts/tune_thresholds.py` | Interactive two-phase tuning utility — recommends `ANOMALY_THRESHOLD` for your room |
| `deploy/nginx.conf` | Nginx reverse proxy: static frontend + API proxy + WebSocket upgrade |
| `deploy/assassin-eyes.service` | systemd unit file for production backend |

---

### Running the smoke test

```bash
# Unit tests only (no server needed — fast)
cd wifi-radar/backend
python3 ../tests/smoke_test.py --unit-only

# Full suite (start the backend first)
uvicorn main:app --host 0.0.0.0 --port 8000 &
python3 ../tests/smoke_test.py
```

Expected output:

```
Unit Tests  (no server required)
  ✓  MA — single sample returns itself
  ✓  MA — two samples: correct partial mean
  ✓  MA — full window mean
  ✓  MA — rolling evicts oldest sample
  ✓  MA — is_warm after window_size samples
  ✓  MA — reset clears state
  ✓  RV — single sample returns 0
  ... (13 more)

Integration Tests  (live server at localhost:8000)
  ✓  GET /  → status = 'ok'
  ✓  GET /status  → non-empty JSON
  ✓  POST /calibrate  → status = 'calibrating'
  ✓  WS /ws  → all 10 frames pass schema validation
  ✓  WS /ws  → state values are valid enum members
  ✓  WS /ws  → calibration_progress ∈ [0, 1]
  ✓  WS /ws  → rssi_raw ∈ [−120, 0] dBm

──────────────────────────────────────────────
  ALL PASSED  (19/19)
```

---

### Threshold tuning (real hardware only)

Run **after** switching to `beacon` or `ping` scanner mode and letting the detector calibrate.

```bash
cd wifi-radar/backend
source .venv/bin/activate
python3 ../scripts/tune_thresholds.py
```

The utility runs two 30-second collection phases (empty room, then walking), analyses the statistical separation between the two distributions, and prints a recommendation:

```
  ╔════════════════════════════════════════════════╗
  ║  Recommended config.py values:                ║
  ║                                               ║
  ║    ANOMALY_THRESHOLD = 3.14                   ║
  ║    WINDOW_SIZE       = 15  (default, keep it) ║
  ╚════════════════════════════════════════════════╝
```

Apply the recommendation in `backend/config.py`, restart the backend, and recalibrate.

---

### Production deployment

#### 1 — Build the frontend

```bash
cd wifi-radar/frontend
npm run build           # outputs to frontend/dist/
```

#### 2 — Install Nginx config

```bash
# Edit deploy/nginx.conf first: update `server_name` and `root`
sudo ln -s $(pwd)/deploy/nginx.conf /etc/nginx/sites-available/assassin-eyes
sudo ln -s /etc/nginx/sites-available/assassin-eyes /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

#### 3 — Install systemd service

```bash
# Edit deploy/assassin-eyes.service: update WorkingDirectory and ExecStart paths
sudo cp deploy/assassin-eyes.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now assassin-eyes
sudo journalctl -u assassin-eyes -f     # watch live logs
```

#### 4 — (Beacon scanner) Grant raw socket capability

Avoids running the whole process as root while still allowing pcap access:

```bash
sudo setcap cap_net_raw,cap_net_admin+eip \
    /opt/wifi-radar/backend/.venv/bin/python3
```

---

## Quick-Start Cheatsheet

```bash
# ── Development (mock data, no hardware) ─────────────────────────────────────
cd wifi-radar/backend && source .venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000   # Terminal 1

cd wifi-radar/frontend && npm run dev                   # Terminal 2
# Open http://localhost:5173

# ── Switch to real router ────────────────────────────────────────────────────
# 1. Set SCANNER_MODE = "beacon" and WIFI_INTERFACE / TARGET_BSSID in config.py
# 2. sudo bash scripts/setup_monitor.sh
# 3. sudo .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
# 4. python3 ../scripts/tune_thresholds.py   (after calibration)

# ── Tests ────────────────────────────────────────────────────────────────────
cd wifi-radar/backend && python3 ../tests/smoke_test.py
```

---

## Phase Roadmap

| Phase | Status | Description |
|---|---|---|
| 1 | Done | Architecture design & file structure |
| 2 | Done | Backend: FastAPI, filters, detector, mock scanner |
| 3 | Done | Frontend: Vite scaffold, WebSocket hook, SignalChart, MotionAlert |
| 4 | Done | Frontend: VarianceGauge, MetricsPanel, CalibrationPanel, full grid layout |
| 5 | Done | Real Scapy beacon scanner, ping scanner, monitor-mode helper scripts |
| 6 | **Done** | Smoke tests, threshold tuning utility, Nginx config, systemd service |

---

## License

MIT
