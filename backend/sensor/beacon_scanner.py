"""
Scapy 802.11 beacon-frame RSSI scanner — primary production scanner.

How it works
────────────
Every home router broadcasts a beacon frame roughly 10 times per second
(the standard DTIM/TIM interval is 100 ms).  These frames travel as
broadcast 802.11 Management frames (type=0, subtype=8) and are visible to
any receiver in range that is listening in monitor mode.

The radiotap header prepended by the driver contains a `dBm_AntSignal`
field — the received signal strength in dBm.  We extract that field from
every matching beacon and feed it into the AnomalyDetector pipeline.

Thread architecture
───────────────────
Scapy's AsyncSniffer runs its capture loop in a daemon thread.  Each
captured packet is examined in that thread; valid RSSI values are handed
to the asyncio event loop via `loop.call_soon_threadsafe`, depositing
them in a bounded `asyncio.Queue`.  The async generator (`rssi_stream`)
drains the queue in the event loop thread — no locks needed.

Requirements
────────────
• Root / sudo privileges  (raw socket access for 802.11 capture)
• Wi-Fi interface in monitor mode
  Linux:  sudo bash scripts/setup_monitor.sh
  macOS:  see README.md — Phase 5 / macOS notes

Optional but recommended
────────────────────────
Set `TARGET_BSSID` in config.py to your router's MAC address so that only
its beacons are counted.  Without a filter, all APs within radio range
contribute beacons which can saturate the queue; the rate-limiter handles
this correctly but a BSSID filter gives a cleaner, single-source signal.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import AsyncGenerator

import config

log = logging.getLogger("assassin-eyes.beacon")


# ── RSSI extraction ───────────────────────────────────────────────────────────

def _extract_rssi(pkt) -> float | None:
    """
    Return the received signal strength (dBm) from a packet's RadioTap header.

    The `dBm_AntSignal` field is present in virtually every radiotap frame
    produced by Linux mac80211 drivers and most macOS CoreWLAN drivers.
    Returns None only when the field is completely absent (rare, driver-specific).
    """
    try:
        from scapy.layers.dot11 import RadioTap
    except ImportError:
        from scapy.all import RadioTap  # older scapy layout

    if not pkt.haslayer(RadioTap):
        return None

    rt = pkt[RadioTap]
    sig = getattr(rt, "dBm_AntSignal", None)
    if sig is not None:
        return float(sig)
    return None


# ── BSSID filtering ───────────────────────────────────────────────────────────

def _bssid_matches(pkt) -> bool:
    """
    Return True if the beacon comes from TARGET_BSSID, or always True when
    no filter is configured.

    In a 802.11 beacon frame the addr3 field carries the BSSID (the AP's
    own MAC address, identical to addr2 for infrastructure APs).
    """
    target = config.TARGET_BSSID.strip().lower()
    if not target:
        return True

    try:
        from scapy.layers.dot11 import Dot11
    except ImportError:
        from scapy.all import Dot11

    if not pkt.haslayer(Dot11):
        return False

    bssid = pkt.addr3
    return bool(bssid and bssid.lower() == target)


# ── Thread-safe queue helper ──────────────────────────────────────────────────

def _enqueue(queue: asyncio.Queue, value: float) -> None:
    """Executed inside the event loop thread via call_soon_threadsafe."""
    try:
        queue.put_nowait(value)
    except asyncio.QueueFull:
        # Drop the incoming frame rather than blocking the sniffer thread.
        # Under normal conditions (single AP, 10 Hz) this never fires.
        pass


# ── Public async generator ────────────────────────────────────────────────────

async def rssi_stream() -> AsyncGenerator[float, None]:
    """
    Yield one float RSSI value (dBm) per tick, rate-limited to BROADCAST_HZ.

    The generator is an infinite loop; it exits only when the caller stops
    iterating or when no beacons are received within the timeout window.
    """
    try:
        from scapy.all import AsyncSniffer
        from scapy.layers.dot11 import Dot11Beacon
    except ImportError as exc:
        raise ImportError(
            "Scapy is not installed or its 802.11 layers are unavailable.\n"
            f"Run:  pip install scapy==2.6.1\nOriginal error: {exc}"
        ) from exc

    loop       = asyncio.get_running_loop()
    queue: asyncio.Queue[float] = asyncio.Queue(maxsize=200)
    stop_flag  = threading.Event()

    # ── Packet callback (runs in sniffer thread) ──────────────────────────────
    def _on_packet(pkt) -> None:
        if stop_flag.is_set():
            return
        if not pkt.haslayer(Dot11Beacon):
            return
        if not _bssid_matches(pkt):
            return
        rssi = _extract_rssi(pkt)
        if rssi is not None:
            loop.call_soon_threadsafe(_enqueue, queue, rssi)

    sniffer = AsyncSniffer(
        iface=config.WIFI_INTERFACE,
        prn=_on_packet,
        # BPF filter pre-selects management frames before Python sees them.
        # Reduces CPU load on busy 2.4 GHz channels significantly.
        filter="type mgt subtype beacon",
        store=False,
    )

    try:
        sniffer.start()
        log.info(
            "Beacon sniffer started  iface=%s  bssid=%s",
            config.WIFI_INTERFACE,
            config.TARGET_BSSID or "any",
        )

        min_interval = 1.0 / config.BROADCAST_HZ
        last_yield_at = 0.0

        while True:
            # Wait up to 10 s for the first/next beacon.
            try:
                rssi = await asyncio.wait_for(queue.get(), timeout=10.0)
            except asyncio.TimeoutError:
                raise RuntimeError(
                    f"No beacon frames received on '{config.WIFI_INTERFACE}' within 10 s.\n\n"
                    "Troubleshooting checklist:\n"
                    "  1. Is the interface in monitor mode?\n"
                    "       sudo bash scripts/setup_monitor.sh\n"
                    "  2. Is WIFI_INTERFACE in config.py correct?\n"
                    "       Linux:  iw dev\n"
                    "       macOS:  networksetup -listallhardwareports\n"
                    "  3. Are you running with root privileges?\n"
                    "       sudo uvicorn main:app --reload --host 0.0.0.0 --port 8000\n"
                    "  4. Is TARGET_BSSID set correctly (or empty for any AP)?\n"
                )

            # Rate-limit: yield at most BROADCAST_HZ values per second.
            # Extra beacons (multi-AP environments) are silently discarded.
            now = loop.time()
            if now - last_yield_at >= min_interval:
                last_yield_at = now
                yield round(rssi, 2)

    finally:
        stop_flag.set()
        if sniffer.running:
            sniffer.stop(join=True)
        log.info("Beacon sniffer stopped.")
