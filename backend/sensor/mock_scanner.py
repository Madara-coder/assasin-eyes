"""
Deterministic mock RSSI scanner.

Produces a realistic RSSI time-series without any hardware or network access.
The signal model is:

    RSSI(t) = BASE + gaussian_noise(0, NOISE_STD)
              + motion_burst(t) * MOTION_MAGNITUDE

where motion_burst(t) is a raised-cosine envelope centred on each simulated
motion event, giving a smooth ramp-up / ramp-down that exercises the
detector's hysteresis correctly.
"""

from __future__ import annotations

import asyncio
import math
import random
import time
from typing import AsyncGenerator

import config


async def rssi_stream() -> AsyncGenerator[float, None]:
    """
    Async generator that yields one float RSSI value (dBm) per tick.

    The interval between yields is determined by config.BROADCAST_HZ so that
    downstream consumers do not need to manage their own timing.
    """
    interval = 1.0 / config.BROADCAST_HZ
    motion_interval = config.MOCK_MOTION_INTERVAL
    motion_duration = config.MOCK_MOTION_DURATION

    start_time = time.monotonic()
    next_tick = start_time

    while True:
        now = time.monotonic()
        elapsed = now - start_time

        # Compute where we are within the current motion cycle.
        cycle_position = elapsed % motion_interval

        # During the first `motion_duration` seconds of each cycle, inject a
        # raised-cosine motion burst.  Outside that window the signal is quiet.
        if cycle_position < motion_duration:
            # Raised cosine: 0 → 1 → 0 over the burst duration
            phase = cycle_position / motion_duration  # 0.0 – 1.0
            envelope = 0.5 * (1.0 - math.cos(2.0 * math.pi * phase))
            motion_component = envelope * config.MOCK_MOTION_MAGNITUDE
        else:
            motion_component = 0.0

        # Add independent Gaussian noise on every tick.
        noise = random.gauss(0.0, config.MOCK_NOISE_STD)

        rssi = config.MOCK_RSSI_BASE + noise + motion_component
        yield round(rssi, 2)

        # Sleep until the next scheduled tick, absorbing any processing drift.
        next_tick += interval
        sleep_for = next_tick - time.monotonic()
        if sleep_for > 0:
            await asyncio.sleep(sleep_for)
        else:
            # We drifted behind; reset the tick anchor to avoid a catch-up storm.
            next_tick = time.monotonic()
