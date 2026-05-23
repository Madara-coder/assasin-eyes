"""
ICMP ping-based RSSI proxy scanner (fallback, no root / monitor mode needed).

Wi-Fi signal quality correlates with round-trip time: when RSSI degrades the
AP retransmits frames, increasing RTT.  We invert and scale RTT to produce a
synthetic "RSSI" value that the detector pipeline can consume identically to
real RSSI readings.

Mapping:  rssi_proxy = BASE - (rtt_ms - RTT_FLOOR) * SCALE_FACTOR

Limitations:
  - RTT is influenced by CPU load on the target, not just RF conditions.
  - Motion events produce subtle RTT changes; the beacon scanner is far more
    sensitive.  Use this only when monitor mode is unavailable.
"""

from __future__ import annotations

import asyncio
import platform
import re
import time
from typing import AsyncGenerator

import config

# Ping command arguments differ between OS families.
_PING_COUNT_FLAG = "-n" if platform.system() == "Windows" else "-c"
_PING_DEADLINE_FLAG = "-w" if platform.system() == "Windows" else "-W"

# RTT below this value is considered the noise floor (ms).
_RTT_FLOOR_MS = 1.0

# How many dBm to subtract per extra millisecond of RTT above the floor.
_SCALE_FACTOR = 0.5

# Clamp range for synthetic RSSI output (dBm).
_RSSI_MIN = -90.0
_RSSI_MAX = -20.0


async def _ping_once(target: str) -> float:
    """
    Fire a single ICMP echo and return the RTT in milliseconds.
    Returns -1.0 on timeout or error.
    """
    cmd = [
        "ping",
        _PING_COUNT_FLAG, "1",
        _PING_DEADLINE_FLAG, "1",
        target,
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=2.0)
    except (asyncio.TimeoutError, FileNotFoundError):
        return -1.0

    output = stdout.decode(errors="ignore")

    # Parse "time=X.X ms" or "time=X ms" from the ping reply.
    match = re.search(r"time[=<]([\d.]+)\s*ms", output, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return -1.0


def _rtt_to_rssi(rtt_ms: float) -> float:
    if rtt_ms < 0:
        return _RSSI_MIN
    synthetic = config.MOCK_RSSI_BASE - max(rtt_ms - _RTT_FLOOR_MS, 0.0) * _SCALE_FACTOR
    return max(_RSSI_MIN, min(_RSSI_MAX, synthetic))


async def rssi_stream() -> AsyncGenerator[float, None]:
    """
    Async generator yielding one synthetic RSSI value (dBm) per tick.
    """
    interval = 1.0 / config.BROADCAST_HZ
    next_tick = time.monotonic()

    while True:
        rtt = await _ping_once(config.PING_TARGET)
        yield round(_rtt_to_rssi(rtt), 2)

        next_tick += interval
        sleep_for = next_tick - time.monotonic()
        if sleep_for > 0:
            await asyncio.sleep(sleep_for)
        else:
            next_tick = time.monotonic()
