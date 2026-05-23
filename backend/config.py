# Central configuration for all backend modules.
# Tune these values after calibration to match your specific environment.

# ── Network interface ────────────────────────────────────────────────────────
# The wireless interface to sniff on (Phase 5, real scanner).
# Run `iwconfig` (Linux) or `networksetup -listallhardwareports` (macOS) to find yours.
WIFI_INTERFACE = "wlan0"

# Target MAC or IP to ping when using the fallback ping scanner.
PING_TARGET = "192.168.1.1"

# ── Signal processing ────────────────────────────────────────────────────────
# Sliding window length for moving average and variance calculations.
# At ~10 Hz sample rate: 15 samples = 1.5-second window.
WINDOW_SIZE = 15

# ── Anomaly detection ────────────────────────────────────────────────────────
# Number of seconds to collect baseline data during calibration.
CALIBRATION_SECONDS = 20

# Anomaly score multiplier above which MOTION state is triggered.
# e.g. 2.8 means current variance is 2.8× the baseline variance.
ANOMALY_THRESHOLD = 2.8

# Hysteresis: consecutive frames above threshold required to enter MOTION state.
MOTION_CONFIRM_FRAMES = 3

# Consecutive frames below threshold required to return to CLEAR state.
CLEAR_CONFIRM_FRAMES = 5

# ── Mock scanner ─────────────────────────────────────────────────────────────
# Simulated RSSI baseline (dBm) for the mock data generator.
MOCK_RSSI_BASE = -62.0

# Standard deviation of ambient noise when no motion is present (dBm).
MOCK_NOISE_STD = 1.2

# Magnitude of the RSSI disruption injected during a simulated motion event.
MOCK_MOTION_MAGNITUDE = 10.0

# Duration of each simulated motion burst (seconds).
MOCK_MOTION_DURATION = 4.0

# Interval between simulated motion events (seconds).
MOCK_MOTION_INTERVAL = 12.0

# ── WebSocket server ─────────────────────────────────────────────────────────
# Approximate target broadcast rate in Hz.
BROADCAST_HZ = 10

# ── Scanner selection ────────────────────────────────────────────────────────
# "mock"   → deterministic fake data, no hardware required
# "ping"   → ICMP ping RTT proxy scanner, no root/monitor mode required
# "beacon" → Scapy beacon frame RSSI (Phase 5, requires monitor mode + root)
SCANNER_MODE = "mock"
