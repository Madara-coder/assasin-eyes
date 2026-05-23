/**
 * Calibration status sidebar panel.
 *
 * Tracks the CALIBRATING → CLEAR state transition to record:
 *   - The wall-clock time calibration completed
 *   - The baseline σ² (derived as variance / anomaly_score on the first
 *     post-calibration frame — valid because anomaly_score = σ²_current / σ²_baseline)
 */

import { useEffect, useRef, useState } from 'react';

const THRESHOLD = 2.8;

export default function CalibrationPanel({ message, onRecalibrate }) {
  const [lastCalibratedAt, setLastCalibratedAt] = useState(null);
  const [baselineSigma, setBaselineSigma]       = useState(null);
  const prevStateRef = useRef(null);

  useEffect(() => {
    if (!message) return;

    const prevState = prevStateRef.current;
    prevStateRef.current = message.state;

    // Capture baseline on the first frame after calibration ends.
    if (prevState === 'CALIBRATING' && message.state === 'CLEAR') {
      setLastCalibratedAt(new Date());
      if (message.anomaly_score > 0) {
        // σ²_baseline = σ²_current / anomaly_score  (by definition of anomaly_score)
        setBaselineSigma((message.variance / message.anomaly_score).toFixed(4));
      }
    }
  }, [message]);

  const isCalibrating = message?.state === 'CALIBRATING';
  const isCalibrated  = message?.calibrated === true;
  const progress      = message?.calibration_progress ?? 0;

  const statusLabel = isCalibrating
    ? 'IN PROGRESS'
    : isCalibrated
    ? 'COMPLETE'
    : 'NOT STARTED';

  const statusColor = isCalibrating
    ? 'text-amber-400'
    : isCalibrated
    ? 'text-emerald-400'
    : 'text-gray-600';

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 flex flex-col h-full">

      <h3 className="text-xs font-semibold uppercase tracking-widest text-gray-500 mb-4">
        Calibration
      </h3>

      <div className="space-y-4 flex-1">

        {/* Status */}
        <div>
          <p className="text-xs text-gray-600 mb-0.5">Status</p>
          <p className={`text-sm font-mono font-bold ${statusColor}`}>{statusLabel}</p>
        </div>

        {/* Progress bar — visible only while calibrating */}
        {isCalibrating && (
          <div>
            <div className="flex justify-between text-xs text-gray-600 mb-1">
              <span>Collecting baseline</span>
              <span className="font-mono">{Math.round(progress * 100)}%</span>
            </div>
            <div className="h-1.5 w-full bg-gray-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-amber-400 rounded-full transition-all duration-300 ease-linear"
                style={{ width: `${progress * 100}%` }}
              />
            </div>
          </div>
        )}

        {/* Last calibrated time */}
        <div>
          <p className="text-xs text-gray-600 mb-0.5">Last Calibrated</p>
          <p className="text-sm font-mono text-gray-400">
            {lastCalibratedAt
              ? lastCalibratedAt.toLocaleTimeString('en-US', { hour12: false })
              : '—'}
          </p>
        </div>

        {/* Baseline σ² */}
        <div>
          <p className="text-xs text-gray-600 mb-0.5">Baseline σ²</p>
          <p className="text-sm font-mono text-violet-400">{baselineSigma ?? '—'}</p>
        </div>

        {/* Trigger threshold (static, matches config.py) */}
        <div>
          <p className="text-xs text-gray-600 mb-0.5">Trigger at</p>
          <p className="text-sm font-mono text-amber-500">{THRESHOLD}× baseline</p>
        </div>

        {/* Calibration duration (static, matches config.py) */}
        <div>
          <p className="text-xs text-gray-600 mb-0.5">Duration</p>
          <p className="text-sm font-mono text-gray-400">20 s</p>
        </div>

      </div>

      {/* Recalibrate button at bottom of panel */}
      <button
        onClick={onRecalibrate}
        disabled={isCalibrating}
        className="mt-5 w-full py-2 rounded-lg text-sm font-semibold border transition-colors
                   border-gray-700 bg-gray-800 text-gray-300
                   hover:bg-gray-700 hover:border-gray-600 hover:text-white
                   disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {isCalibrating ? 'Calibrating…' : 'Recalibrate'}
      </button>

    </div>
  );
}
