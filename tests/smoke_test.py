#!/usr/bin/env python3
"""
Assassin Eyes — smoke test suite.

Two test groups:

  Unit tests (no server needed)
    Validate the signal processing pipeline in complete isolation.
    Fast — runs in < 1 second.

  Integration tests (live server required)
    Validate HTTP endpoints and the WebSocket stream schema.
    Requires the backend to be running on localhost:8000.

Usage:
    # From the project root:
    cd wifi-radar/backend && python3 ../tests/smoke_test.py
    cd wifi-radar/backend && python3 ../tests/smoke_test.py --unit-only

Exit codes: 0 = all passed, 1 = one or more failures.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ── Path: allow `from processing.X import Y` when run from project root ───────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from processing.filters import MovingAverage, RollingVariance
from processing.detector import AnomalyDetector, MotionState

BASE      = "http://localhost:8000"
WS_URL    = "ws://localhost:8000/ws"
UNIT_ONLY = "--unit-only" in sys.argv

# ── Minimal test harness ──────────────────────────────────────────────────────

_passed = 0
_failed = 0

GREEN  = "\033[32m"
RED    = "\033[31m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


def _ok(label: str) -> None:
    global _passed
    _passed += 1
    print(f"  {GREEN}✓{RESET}  {label}")


def _fail(label: str, reason: str) -> None:
    global _failed
    _failed += 1
    print(f"  {RED}✗{RESET}  {label}")
    print(f"       ↳ {reason}")


def assert_eq(label: str, got, expected) -> None:
    if got == expected:
        _ok(label)
    else:
        _fail(label, f"expected {expected!r}, got {got!r}")


def assert_close(label: str, got: float, expected: float, tol: float = 1e-9) -> None:
    if abs(got - expected) <= tol:
        _ok(label)
    else:
        _fail(label, f"expected ≈ {expected}, got {got:.10f}")


def assert_true(label: str, condition: bool, msg: str = "condition was False") -> None:
    if condition:
        _ok(label)
    else:
        _fail(label, msg)


# ── Unit test: MovingAverage ──────────────────────────────────────────────────

def test_moving_average() -> None:
    ma = MovingAverage(window_size=3)

    assert_close("MA — single sample returns itself",      ma.update(10.0), 10.0)
    assert_close("MA — two samples: correct partial mean", ma.update(20.0), 15.0)
    assert_close("MA — full window mean",                  ma.update(30.0), 20.0)
    # Window full: oldest (10) evicted, new mean = (20+30+40)/3 = 30
    assert_close("MA — rolling evicts oldest sample",      ma.update(40.0), 30.0)
    assert_true( "MA — is_warm after window_size samples", ma.is_warm)

    ma.reset()
    assert_true("MA — reset clears state", not ma.is_warm)


# ── Unit test: RollingVariance ────────────────────────────────────────────────

def test_rolling_variance() -> None:
    rv = RollingVariance(window_size=4)

    # Single sample: variance undefined → 0
    rv.update(5.0)
    assert_close("RV — single sample returns 0", rv.value, 0.0)

    # Constant series: population variance = 0
    rv_const = RollingVariance(window_size=4)
    for _ in range(4):
        rv_const.update(7.0)
    assert_close("RV — constant series variance = 0", rv_const.value, 0.0)

    # [1, 3] with window=2: mean=2, var = ((1-2)²+(3-2)²)/2 = 1.0
    rv2 = RollingVariance(window_size=2)
    rv2.update(1.0)
    rv2.update(3.0)
    assert_close("RV — [1, 3] population variance = 1.0", rv2.value, 1.0)

    # Rolling window: after adding a 4th value, oldest is evicted
    rv3 = RollingVariance(window_size=2)
    rv3.update(0.0)
    rv3.update(0.0)
    assert_close("RV — [0, 0] variance = 0",   rv3.value, 0.0)
    rv3.update(10.0)
    assert_close("RV — [0, 10] variance = 25", rv3.value, 25.0)

    rv_const.reset()
    assert_true("RV — reset clears buffer", not rv_const.is_warm)


# ── Unit test: AnomalyDetector — calibration ─────────────────────────────────

def test_detector_calibration() -> None:
    det = AnomalyDetector(
        window_size=5,
        calibration_seconds=0.08,   # 80 ms — fast enough for a test
        anomaly_threshold=2.0,
        motion_confirm_frames=2,
        clear_confirm_frames=2,
    )
    det.start_calibration()

    # Feed 20 samples before the timer expires so the variance filter warms up
    # and _calibration_samples accumulates real data.
    for _ in range(20):
        out = det.process(-60.0)

    assert_eq("Det — state is CALIBRATING before timeout",
              out.state, MotionState.CALIBRATING)
    assert_true("Det — calibrated=False during calibration",
                not out.calibrated)

    # Wait past the calibration window.
    time.sleep(0.10)

    # process() triggers the transition on the first call after timeout.
    out = det.process(-60.0)
    assert_true("Det — calibrated=True after timeout",  out.calibrated)
    assert_eq(  "Det — state transitions to CLEAR",     out.state, MotionState.CLEAR)
    assert_true("Det — baseline_variance > 0",          det.baseline_variance > 0)
    assert_close("Det — calibration_progress = 1.0",    out.calibration_progress, 1.0)


# ── Unit test: AnomalyDetector — state machine ───────────────────────────────

def test_detector_state_machine() -> None:
    det = AnomalyDetector(
        window_size=3,
        calibration_seconds=0.04,
        anomaly_threshold=3.0,
        motion_confirm_frames=2,
        clear_confirm_frames=2,
    )
    det.start_calibration()
    # Prime the variance filter before the timer expires.
    for _ in range(10):
        det.process(-60.0)
    time.sleep(0.05)
    for _ in range(5):
        det.process(-60.0)

    assert_eq("Det/SM — starts CLEAR after calibration",
              det.process(-60.0).state, MotionState.CLEAR)

    # A single spike must NOT trigger MOTION (needs 2 confirm frames).
    det.process(-25.0)
    assert_eq("Det/SM — single spike does NOT trigger MOTION (hysteresis)",
              det.process(-60.0).state, MotionState.CLEAR)

    # Two consecutive high-variance frames exceed threshold → MOTION.
    det.process(-25.0)
    det.process(-25.0)
    assert_eq("Det/SM — sustained disruption triggers MOTION",
              det.process(-25.0).state, MotionState.MOTION)

    # Return to quiet signal for 2+ frames → back to CLEAR.
    det.process(-60.0)
    det.process(-60.0)
    assert_eq("Det/SM — quiet signal restores CLEAR",
              det.process(-60.0).state, MotionState.CLEAR)


# ── Integration helpers ───────────────────────────────────────────────────────

def _http_get(path: str) -> dict:
    with urllib.request.urlopen(f"{BASE}{path}", timeout=5) as resp:
        return json.loads(resp.read())


def _http_post(path: str) -> dict:
    req = urllib.request.Request(
        f"{BASE}{path}", method="POST",
        data=b"", headers={"Content-Length": "0"},
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


async def _ws_collect(n: int) -> list[dict]:
    import websockets
    frames: list[dict] = []
    async with websockets.connect(WS_URL) as ws:
        while len(frames) < n:
            raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
            frames.append(json.loads(raw))
    return frames


# ── Integration tests ─────────────────────────────────────────────────────────

_REQUIRED: dict[str, type] = {
    "ts":                   float,
    "rssi_raw":             float,
    "rssi_ma":              float,
    "variance":             float,
    "anomaly_score":        float,
    "state":                str,
    "calibrated":           bool,
    "calibration_progress": float,
}
_VALID_STATES = {"CALIBRATING", "CLEAR", "MOTION"}


def test_health_endpoint() -> None:
    try:
        body = _http_get("/")
        assert_eq(  "GET /  → status = 'ok'",          body.get("status"),       "ok")
        assert_true("GET /  → scanner_mode present",    "scanner_mode" in body)
    except Exception as exc:
        _fail("GET /", str(exc))


def test_status_endpoint() -> None:
    try:
        body = _http_get("/status")
        assert_true("GET /status  → non-empty JSON",    bool(body))
    except Exception as exc:
        _fail("GET /status", str(exc))


def test_calibrate_endpoint() -> None:
    try:
        body = _http_post("/calibrate")
        assert_eq(  "POST /calibrate  → status = 'calibrating'",
                    body.get("status"), "calibrating")
        assert_true("POST /calibrate  → duration_seconds present",
                    "duration_seconds" in body)
    except Exception as exc:
        _fail("POST /calibrate", str(exc))


def test_websocket_schema() -> None:
    try:
        frames = asyncio.run(_ws_collect(10))
        assert_true("WS /ws  → received 10 frames", len(frames) == 10)

        for frame in frames:
            for field, expected_type in _REQUIRED.items():
                if field not in frame:
                    _fail(f"WS schema  — field '{field}' missing", "")
                    return
                got_type = type(frame[field])
                if got_type is not expected_type:
                    _fail(f"WS schema  — field '{field}' wrong type",
                          f"expected {expected_type.__name__}, got {got_type.__name__}")
                    return

        _ok("WS /ws  → all 10 frames pass schema validation")
    except Exception as exc:
        _fail("WS /ws  — schema", str(exc))


def test_websocket_values() -> None:
    try:
        frames = asyncio.run(_ws_collect(10))

        bad_states = [f["state"] for f in frames if f["state"] not in _VALID_STATES]
        assert_true("WS /ws  → state values are valid enum members",
                    not bad_states,
                    f"invalid: {bad_states}")

        bad_progress = [f["calibration_progress"] for f in frames
                        if not (0.0 <= f["calibration_progress"] <= 1.0)]
        assert_true("WS /ws  → calibration_progress ∈ [0, 1]",
                    not bad_progress,
                    f"out of range: {bad_progress}")

        bad_rssi = [f["rssi_raw"] for f in frames if not (-120.0 <= f["rssi_raw"] <= 0.0)]
        assert_true("WS /ws  → rssi_raw ∈ [−120, 0] dBm",
                    not bad_rssi,
                    f"implausible values: {bad_rssi}")
    except Exception as exc:
        _fail("WS /ws  — value ranges", str(exc))


# ── Runner ────────────────────────────────────────────────────────────────────

def _run_group(title: str, tests: list) -> None:
    print(f"\n{BOLD}{title}{RESET}")
    for fn in tests:
        try:
            fn()
        except Exception as exc:
            _fail(fn.__name__, f"unhandled exception: {exc}")


if __name__ == "__main__":
    print(f"\n{BOLD}Assassin Eyes — Smoke Test Suite{RESET}")
    print("─" * 44)

    _run_group(
        "Unit Tests  (no server required)",
        [
            test_moving_average,
            test_rolling_variance,
            test_detector_calibration,
            test_detector_state_machine,
        ],
    )

    if not UNIT_ONLY:
        print(f"\n  Connecting to {BASE} …")
        _run_group(
            "Integration Tests  (live server at localhost:8000)",
            [
                test_health_endpoint,
                test_status_endpoint,
                test_calibrate_endpoint,
                test_websocket_schema,
                test_websocket_values,
            ],
        )
    else:
        print("\n  Integration tests skipped (--unit-only)")

    total  = _passed + _failed
    color  = GREEN if _failed == 0 else RED
    banner = "ALL PASSED" if _failed == 0 else f"{_failed} FAILED"
    print(f"\n{'─' * 44}")
    print(f"  {color}{BOLD}{banner}{RESET}  ({_passed}/{total})")
    print()

    sys.exit(0 if _failed == 0 else 1)
