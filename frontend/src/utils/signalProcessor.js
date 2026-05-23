/**
 * Client-side data structures for the real-time chart.
 *
 * RingBuffer keeps the most recent N items with O(1) push and a fast snapshot.
 * Using a plain array + shift() is O(n) but at 300 elements and 10 Hz the cost
 * is ~3 µs/tick — negligible compared to Chart.js render time.
 */

export const MAX_CHART_POINTS = 300; // 30 seconds at 10 Hz

export class RingBuffer {
  constructor(capacity) {
    this._capacity = capacity;
    this._data = [];
  }

  push(value) {
    this._data.push(value);
    if (this._data.length > this._capacity) {
      this._data.shift();
    }
  }

  /** Returns a shallow copy — safe to hand directly to Chart.js. */
  toArray() {
    return this._data.slice();
  }

  get length() {
    return this._data.length;
  }

  clear() {
    this._data = [];
  }
}

/**
 * Format a Unix epoch (seconds, float) as HH:MM:SS for chart axis labels.
 */
export function formatTimestamp(ts) {
  return new Date(ts * 1_000).toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}
