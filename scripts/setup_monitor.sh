#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# setup_monitor.sh — Enable monitor mode on a Linux Wi-Fi interface.
#
# Usage:
#   sudo bash scripts/setup_monitor.sh [interface] [channel]
#
# Defaults:
#   interface → value of WIFI_INTERFACE in backend/config.py  (fallback: wlan0)
#   channel   → value of WIFI_CHANNEL in backend/config.py    (fallback: 6)
#
# What it does:
#   1. Stops NetworkManager from managing the interface (prevents it from
#      reverting monitor mode back to managed automatically).
#   2. Brings the interface down.
#   3. Switches the interface type to "monitor".
#   4. Brings the interface back up.
#   5. Locks to the specified channel (optional but recommended — locking to
#      the router's channel maximises beacon capture rate and RSSI consistency).
#
# Restore managed mode:
#   sudo bash scripts/teardown_monitor.sh [interface]
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Resolve arguments ─────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/../backend/config.py"

# Read defaults from config.py if present.
DEFAULT_IFACE="wlan0"
DEFAULT_CHANNEL="6"
if [[ -f "$CONFIG_FILE" ]]; then
    _cfg_iface=$(grep -E '^WIFI_INTERFACE\s*=' "$CONFIG_FILE" | head -1 | sed 's/.*=\s*"\(.*\)".*/\1/')
    _cfg_chan=$(grep -E '^WIFI_CHANNEL\s*=' "$CONFIG_FILE" | head -1 | grep -oE '[0-9]+' | head -1)
    [[ -n "$_cfg_iface" ]]   && DEFAULT_IFACE="$_cfg_iface"
    [[ -n "$_cfg_chan" ]]     && DEFAULT_CHANNEL="$_cfg_chan"
fi

IFACE="${1:-$DEFAULT_IFACE}"
CHANNEL="${2:-$DEFAULT_CHANNEL}"

# ── Root check ────────────────────────────────────────────────────────────────
if [[ "$EUID" -ne 0 ]]; then
    echo "Error: this script must be run as root."
    echo "  sudo bash scripts/setup_monitor.sh $IFACE $CHANNEL"
    exit 1
fi

# ── Dependency check ──────────────────────────────────────────────────────────
for cmd in iw ip; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "Error: '$cmd' not found. Install it with: apt install iw iproute2"
        exit 1
    fi
done

# ── Enable monitor mode ───────────────────────────────────────────────────────
echo ""
echo "  Assassin Eyes — Monitor Mode Setup"
echo "  Interface : $IFACE"
echo "  Channel   : $CHANNEL"
echo ""

# Kill processes that might fight for the interface (wpa_supplicant, dhclient).
echo "  [1/5]  Stopping interface-management processes …"
if command -v nmcli &>/dev/null; then
    nmcli device set "$IFACE" managed no 2>/dev/null && echo "        NetworkManager: unmanaged" || true
fi
if command -v airmon-ng &>/dev/null; then
    airmon-ng check kill 2>/dev/null || true
fi

echo "  [2/5]  Bringing $IFACE down …"
ip link set "$IFACE" down

echo "  [3/5]  Switching $IFACE to monitor mode …"
iw dev "$IFACE" set type monitor

echo "  [4/5]  Bringing $IFACE up …"
ip link set "$IFACE" up

if [[ "$CHANNEL" -gt 0 ]]; then
    echo "  [5/5]  Locking to channel $CHANNEL …"
    iw dev "$IFACE" set channel "$CHANNEL" 2>/dev/null || \
        echo "        Warning: channel lock failed (driver may not support it — continuing anyway)"
else
    echo "  [5/5]  Skipping channel lock (WIFI_CHANNEL = 0)"
fi

# ── Verify ────────────────────────────────────────────────────────────────────
CURRENT_MODE=$(iw dev "$IFACE" info 2>/dev/null | grep -E 'type' | awk '{print $2}')
echo ""
if [[ "$CURRENT_MODE" == "monitor" ]]; then
    echo "  ✓  $IFACE is now in monitor mode."
else
    echo "  ✗  Mode check failed (got: '$CURRENT_MODE'). Check driver support."
    exit 1
fi

echo ""
echo "  Next steps:"
echo "    1. Update backend/config.py if needed:"
echo "         WIFI_INTERFACE = \"$IFACE\""
echo "         SCANNER_MODE   = \"beacon\""
echo "         TARGET_BSSID   = \"aa:bb:cc:dd:ee:ff\"  # your router's MAC"
echo "    2. Start the backend with root:"
echo "         sudo .venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "  Restore managed mode when done:"
echo "    sudo bash scripts/teardown_monitor.sh $IFACE"
echo ""
