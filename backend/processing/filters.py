"""
Real-time signal processing primitives.

Both classes operate on a fixed-size circular (ring) buffer so that no
allocation occurs after initialization — safe for a tight 10 Hz loop.
"""

from collections import deque


class MovingAverage:
    """
    Computes an online sliding-window arithmetic mean.

    The mean is recalculated incrementally: when a new sample arrives the
    oldest value is subtracted from the running sum and the new value is
    added, keeping the operation O(1) per sample.
    """

    def __init__(self, window_size: int) -> None:
        if window_size < 1:
            raise ValueError("window_size must be >= 1")
        self._window_size = window_size
        self._buffer: deque[float] = deque(maxlen=window_size)
        self._running_sum: float = 0.0

    def update(self, value: float) -> float:
        """
        Ingest a new sample and return the current mean.

        Returns the mean of however many samples are buffered (< window_size
        during warm-up), not a full-window mean, so the output is valid from
        the very first sample.
        """
        if len(self._buffer) == self._window_size:
            self._running_sum -= self._buffer[0]
        self._buffer.append(value)
        self._running_sum += value
        return self._running_sum / len(self._buffer)

    @property
    def value(self) -> float:
        if not self._buffer:
            return 0.0
        return self._running_sum / len(self._buffer)

    @property
    def is_warm(self) -> bool:
        """True once the buffer holds a full window of samples."""
        return len(self._buffer) == self._window_size

    def reset(self) -> None:
        self._buffer.clear()
        self._running_sum = 0.0


class RollingVariance:
    """
    Computes an online sliding-window population variance using Welford's
    two-pass method over a ring buffer.

    Welford's online algorithm (single-pass) is numerically stable but tracks
    variance over all samples ever seen.  For a *sliding window* we need the
    variance to age out old samples, so we recompute from the buffer each tick.
    At a window of 15 samples this is 15 multiplications — negligible at 10 Hz.
    """

    def __init__(self, window_size: int) -> None:
        if window_size < 2:
            raise ValueError("window_size must be >= 2 for meaningful variance")
        self._window_size = window_size
        self._buffer: deque[float] = deque(maxlen=window_size)

    def update(self, value: float) -> float:
        """
        Ingest a new sample and return the current population variance.

        Returns 0.0 until at least two samples have been buffered.
        """
        self._buffer.append(value)
        return self.value

    @property
    def value(self) -> float:
        n = len(self._buffer)
        if n < 2:
            return 0.0
        mean = sum(self._buffer) / n
        return sum((x - mean) ** 2 for x in self._buffer) / n

    @property
    def is_warm(self) -> bool:
        return len(self._buffer) == self._window_size

    def reset(self) -> None:
        self._buffer.clear()
