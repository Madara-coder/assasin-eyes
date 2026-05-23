#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# teardown_monitor.sh — Restore a Wi-Fi interface to managed mode on Linux.
#
# Usage:
#   sudo bash scripts/teardown_monitor.sh [interface]
#
# Default interface: wlan0  (or WIFI_INTERFACE from backend/config.py)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/../backend/config.py"

DEFAULT_IFACE="wlan0"
if [[ -f "$CONFIG_FILE" ]]; then
    _cfg=$(grep -E '^WIFI_INTERFACE\s*=' "$CONFIG_FILE" | head -1 | sed 's/.*=\s*"\(.*\)".*/\1/')
    [[ -n "$_cfg" ]] && DEFAULT_IFACE="$_cfg"
fi

IFACE="${1:-$DEFAULT_IFACE}"

if [[ "$EUID" -ne 0 ]]; then
    echo "Error: this script must be run as root."
    echo "  sudo bash scripts/teardown_monitor.sh $IFACE"
    exit 1
fi

echo ""
echo "  Assassin Eyes — Restore Managed Mode"
echo "  Interface : $IFACE"
echo ""

echo "  [1/4]  Bringing $IFACE down …"
ip link set "$IFACE" down

echo "  [2/4]  Switching $IFACE to managed mode …"
iw dev "$IFACE" set type managed

echo "  [3/4]  Bringing $IFACE up …"
ip link set "$IFACE" up

echo "  [4/4]  Re-enabling NetworkManager …"
if command -v nmcli &>/dev/null; then
    nmcli device set "$IFACE" managed yes 2>/dev/null && echo "        NetworkManager: managed" || true
fi

CURRENT_MODE=$(iw dev "$IFACE" info 2>/dev/null | grep -E 'type' | awk '{print $2}')
echo ""
if [[ "$CURRENT_MODE" == "managed" ]]; then
    echo "  ✓  $IFACE is back in managed mode."
else
    echo "  ✗  Mode is '$CURRENT_MODE'. You may need to reboot or reconnect manually."
fi
echo ""
