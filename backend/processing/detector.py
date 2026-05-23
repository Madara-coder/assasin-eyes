"""
Anomaly detector for RSSI-based device-free human motion detection.

Detection pipeline per sample:
  1. Feed raw RSSI into MovingAverage  → smoothed signal
  2. Feed raw RSSI into RollingVariance → instantaneous instability σ²
  3. During calibration: accumulate σ² values to build a baseline mean
  4. Post-calibration: compute anomaly_score = σ²_current / σ²_baseline
  5. Hysteresis state machine: CLEAR ↔ MOTION with confirm-frame debounce
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List

import config
from processing.filters import MovingAverage, RollingVariance


class MotionState(str, Enum):
    CLEAR = "CLEAR"
    MOTION = "MOTION"
    CALIBRATING = "CALIBRATING"


@dataclass
class DetectorOutput:
    ts: float
    rssi_raw: float
    rssi_ma: float
    variance: float
    anomaly_score: float
    state: MotionState
    calibrated: bool
    calibration_progress: float  # 0.0 – 1.0


class AnomalyDetector:
    """
    Stateful, single-threaded anomaly detector.

    Usage:
        detector = AnomalyDetector()
        detector.start_calibration()
        for rssi in stream:
            output = detector.process(rssi)
            broadcast(output)
    """

    def __init__(
        self,
        window_size: int = config.WINDOW_SIZE,
        calibration_seconds: float = config.CALIBRATION_SECONDS,
        anomaly_threshold: float = config.ANOMALY_THRESHOLD,
        motion_confirm_frames: int = config.MOTION_CONFIRM_FRAMES,
        clear_confirm_frames: int = config.CLEAR_CONFIRM_FRAMES,
    ) -> None:
        self._ma = MovingAverage(window_size)
        self._var = RollingVariance(window_size)

        self._calibration_seconds = calibration_seconds
        self._anomaly_threshold = anomaly_threshold
        self._motion_confirm = motion_confirm_frames
        self._clear_confirm = clear_confirm_frames

        # Calibration state
        self._calibrating: bool = False
        self._calibration_start: float = 0.0
        self._calibration_samples: List[float] = []
        self._baseline_variance: float = 1.0  # sensible non-zero default
        self._calibrated: bool = False

        # Hysteresis state machine
        self._state: MotionState = MotionState.CLEAR
        self._above_count: int = 0
        self._below_count: int = 0

    # ── Public API ────────────────────────────────────────────────────────────

    def start_calibration(self) -> None:
        """
        Begin a calibration phase.  Call this once the room is confirmed empty.
        The detector will collect RSSI variance for `calibration_seconds` and
        then compute the baseline automatically.
        """
        self._calibrating = True
        self._calibration_start = time.monotonic()
        self._calibration_samples = []
        self._calibrated = False
        self._state = MotionState.CALIBRATING
        self._ma.reset()
        self._var.reset()
        self._above_count = 0
        self._below_count = 0

    def process(self, rssi_raw: float) -> DetectorOutput:
        """
        Ingest one raw RSSI sample (dBm) and return a fully populated output.
        Thread-safe as long as only one thread calls this method.
        """
        now = time.time()

        rssi_ma = self._ma.update(rssi_raw)
        variance = self._var.update(rssi_raw)

        # ── Calibration phase ────────────────────────────────────────────────
        if self._calibrating:
            elapsed = time.monotonic() - self._calibration_start
            progress = min(elapsed / self._calibration_seconds, 1.0)

            if self._var.is_warm:
                self._calibration_samples.append(variance)

            if elapsed >= self._calibration_seconds:
                self._finish_calibration()

            return DetectorOutput(
                ts=now,
                rssi_raw=rssi_raw,
                rssi_ma=rssi_ma,
                variance=variance,
                anomaly_score=0.0,
                state=MotionState.CALIBRATING,
                calibrated=False,
                calibration_progress=progress,
            )

        # ── Detection phase ──────────────────────────────────────────────────
        anomaly_score = self._compute_anomaly_score(variance)
        self._update_state(anomaly_score)

        return DetectorOutput(
            ts=now,
            rssi_raw=rssi_raw,
            rssi_ma=rssi_ma,
            variance=variance,
            anomaly_score=anomaly_score,
            state=self._state,
            calibrated=self._calibrated,
            calibration_progress=1.0,
        )

    @property
    def is_calibrated(self) -> bool:
        return self._calibrated

    @property
    def baseline_variance(self) -> float:
        return self._baseline_variance

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _finish_calibration(self) -> None:
        self._calibrating = False
        self._calibrated = True

        if self._calibration_samples:
            # Use the mean of all collected variance samples as the baseline.
            self._baseline_variance = max(
                sum(self._calibration_samples) / len(self._calibration_samples),
                0.01,  # guard against divide-by-zero in pathological cases
            )
        self._state = MotionState.CLEAR
        self._above_count = 0
        self._below_count = 0

    def _compute_anomaly_score(self, variance: float) -> float:
        return variance / self._baseline_variance

    def _update_state(self, anomaly_score: float) -> None:
        """
        Hysteresis state machine.

        CLEAR  → MOTION : anomaly_score exceeds threshold for MOTION_CONFIRM
                          consecutive frames
        MOTION → CLEAR  : anomaly_score falls below threshold for CLEAR_CONFIRM
                          consecutive frames
        """
        if self._state == MotionState.CLEAR:
            if anomaly_score >= self._anomaly_threshold:
                self._above_count += 1
                self._below_count = 0
                if self._above_count >= self._motion_confirm:
                    self._state = MotionState.MOTION
                    self._above_count = 0
            else:
                self._above_count = 0

        elif self._state == MotionState.MOTION:
            if anomaly_score < self._anomaly_threshold:
                self._below_count += 1
                self._above_count = 0
                if self._below_count >= self._clear_confirm:
                    self._state = MotionState.CLEAR
                    self._below_count = 0
            else:
                self._below_count = 0
