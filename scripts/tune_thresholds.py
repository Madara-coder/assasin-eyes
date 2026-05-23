#!/usr/bin/env python3
"""
Assassin Eyes — Threshold Tuning Utility.

Guides you through a two-phase data-collection session and recommends optimal
ANOMALY_THRESHOLD and WINDOW_SIZE values for your specific room and router.

How it works
────────────
Phase 1 (quiet):  You leave the room for 30 seconds. The script records the
                  anomaly scores that represent your environment's noise floor.

Phase 2 (motion): You walk naturally through the room for 30 seconds. The
                  script records anomaly scores caused by your body disrupting
                  the Wi-Fi path.

The script then computes the statistical separation between the two
distributions and recommends a threshold that sits safely above the quiet
ceiling but below the motion floor.

Prerequisites
─────────────
• Backend running with SCANNER_MODE = "beacon" or "ping" (not "mock").
• The detector must be calibrated (wait for the calibration phase to finish
  or click Recalibrate on the dashboard before running this tool).

Usage:
    cd wifi-radar/backend
    source .venv/bin/activate
    python3 ../scripts/tune_thresholds.py

    # Custom WebSocket URL:
    python3 ../scripts/tune_thresholds.py --ws ws://192.168.1.x:8000/ws
"""

from __future__ import annotations

import asyncio
import json
import statistics
import sys
import time

# ── CLI args ──────────────────────────────────────────────────────────────────
WS_URL = "ws://localhost:8000/ws"
for i, arg in enumerate(sys.argv[1:]):
    if arg == "--ws" and i + 2 <= len(sys.argv) - 1:
        WS_URL = sys.argv[i + 2]
        break

PHASE_SECONDS = 30


# ── Collection ────────────────────────────────────────────────────────────────

async def collect(label: str, duration: int) -> list[float]:
    try:
        import websockets
    except ImportError:
        print("\nError: websockets library not found.")
        print("  pip install websockets==14.1")
        sys.exit(1)

    scores: list[float] = []
    deadline = time.monotonic() + duration
    bar_width = 38

    print(f"\n  Collecting {label} data for {duration} s …")

    try:
        async with websockets.connect(WS_URL, open_timeout=5) as ws:
            while time.monotonic() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    msg = json.loads(raw)

                    # Only record post-calibration frames.
                    if msg.get("calibrated") and msg.get("state") != "CALIBRATING":
                        scores.append(float(msg["anomaly_score"]))

                    elapsed   = duration - (deadline - time.monotonic())
                    filled    = min(int(elapsed / duration * bar_width), bar_width)
                    bar       = "█" * filled + "░" * (bar_width - filled)
                    remaining = max(0, int(deadline - time.monotonic()))
                    print(f"\r  [{bar}]  {remaining:2d}s left  n={len(scores):4d}",
                          end="", flush=True)

                except asyncio.TimeoutError:
                    continue
    except OSError as exc:
        print(f"\n\n  Cannot connect to {WS_URL}: {exc}")
        print("  Is the backend running?  uvicorn main:app --host 0.0.0.0 --port 8000")
        sys.exit(1)

    print()
    return scores


# ── Analysis ──────────────────────────────────────────────────────────────────

def percentile(data: list[float], pct: float) -> float:
    idx = max(0, int(pct / 100 * len(data)) - 1)
    return sorted(data)[idx]


def analyse(quiet: list[float], motion: list[float]) -> None:
    W = 54
    print(f"\n{'═' * W}")
    print("  Analysis Results")
    print(f"{'═' * W}")

    if len(quiet) < 10:
        print("\n  ✗  Not enough quiet-phase data (< 10 samples).")
        print("     Make sure the backend is calibrated and SCANNER_MODE ≠ 'mock'.")
        return

    q_mean  = statistics.mean(quiet)
    q_sd    = statistics.stdev(quiet) if len(quiet) > 1 else 0.0
    q_p95   = percentile(quiet, 95)
    q_p99   = percentile(quiet, 99)

    print(f"\n  Empty-room baseline (anomaly score ×):")
    print(f"    samples  = {len(quiet)}")
    print(f"    mean     = {q_mean:.3f}×")
    print(f"    std dev  = {q_sd:.3f}×")
    print(f"    p95      = {q_p95:.3f}×")
    print(f"    p99      = {q_p99:.3f}×")

    if len(motion) < 10:
        # Quiet-data-only recommendation: 2.5× above the quiet p99.
        rec = round(max(q_p99 * 2.5, q_mean + 3 * q_sd), 2)
        print(f"\n  No motion data — using quiet statistics only.")
        _print_recommendation(rec, note="Run with motion phase for higher accuracy.")
        return

    m_mean = statistics.mean(motion)
    m_sd   = statistics.stdev(motion) if len(motion) > 1 else 0.0
    m_p5   = percentile(motion, 5)
    m_p50  = percentile(motion, 50)

    print(f"\n  Motion phase (anomaly score ×):")
    print(f"    samples  = {len(motion)}")
    print(f"    mean     = {m_mean:.3f}×")
    print(f"    std dev  = {m_sd:.3f}×")
    print(f"    p5       = {m_p5:.3f}×  ← lowest 5 %% of motion scores")
    print(f"    median   = {m_p50:.3f}×")

    separation = m_p5 - q_p99
    print(f"\n  Separation  (motion p5 − quiet p99) = {separation:.3f}×")

    if separation <= 0.0:
        print("\n  ⚠  Distributions OVERLAP — reliable detection is unlikely.")
        print("     Suggestions:")
        print("     • Switch to 'beacon' scanner mode (much more sensitive than ping)")
        print("     • Position the router so its beam crosses the monitored area")
        print("     • Reduce WINDOW_SIZE to 8–10 for quicker variance response")
        print("     • Try a less congested Wi-Fi channel (1, 6, or 11 on 2.4 GHz)")
        return

    # Place threshold 60 % of the way from quiet p99 to motion p5.
    threshold = q_p99 + separation * 0.6
    threshold = round(threshold, 2)

    quality = (
        "Excellent" if separation > 3.0 else
        "Good"      if separation > 1.5 else
        "Marginal"
    )
    print(f"  Separation quality: {quality}")

    note = None
    if quality == "Excellent":
        tighter = round(q_p99 * 1.4, 2)
        note = (f"Excellent gap — you can tighten to {tighter}× for higher "
                "sensitivity if false-positive rate is acceptable.")

    _print_recommendation(threshold, note)

    print(f"  (Conservative alternative: {round(q_p99 * 2.0, 2)}× — fewer false positives)")
    print()


def _print_recommendation(threshold: float, note: str | None = None) -> None:
    W = 48
    print(f"\n  ╔{'═' * W}╗")
    print(f"  ║  Recommended config.py values:                ║")
    print(f"  ║                                               ║")
    print(f"  ║    ANOMALY_THRESHOLD = {threshold:<6.2f}                ║")
    print(f"  ║    WINDOW_SIZE       = 15  (default, keep it) ║")
    print(f"  ╚{'═' * W}╝")
    if note:
        print(f"\n  ℹ  {note}")


# ── Interactive flow ──────────────────────────────────────────────────────────

def prompt(msg: str) -> None:
    try:
        input(msg)
    except EOFError:
        pass  # non-interactive mode — continue immediately


async def main() -> None:
    W = 46
    print(f"\n  Assassin Eyes — Threshold Tuning Utility")
    print(f"  {'─' * W}")
    print(f"  Backend WebSocket: {WS_URL}")
    print(f"  Collection window: {PHASE_SECONDS} s per phase")
    print()
    print("  IMPORTANT: Set SCANNER_MODE = 'beacon' or 'ping' in config.py.")
    print("  The backend must be running AND the detector must be calibrated")
    print("  (anomaly scores are only recorded after calibration completes).")

    print(f"\n  ┌{'─' * W}┐")
    print(f"  │  PHASE 1 — Empty Room                        │")
    print(f"  │  Leave the monitored area now.               │")
    print(f"  │  Ensure nobody is moving in the room.        │")
    print(f"  └{'─' * W}┘")
    prompt("\n  Press Enter when the room is empty …")

    quiet = await collect("empty-room", PHASE_SECONDS)

    print(f"\n  ┌{'─' * W}┐")
    print(f"  │  PHASE 2 — Motion                            │")
    print(f"  │  Walk through the room at a natural pace.    │")
    print(f"  │  Cover the whole floor area if possible.     │")
    print(f"  └{'─' * W}┘")
    prompt("\n  Press Enter when you are ready to walk …")

    motion = await collect("motion", PHASE_SECONDS)

    analyse(quiet, motion)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n  Tuning session interrupted.")
        sys.exit(0)
