const STATE_CONFIG = {
  CALIBRATING: {
    wrapper:     'border-amber-500/60 bg-amber-950/40',
    dot:         'bg-amber-400',
    dotPing:     '',
    label:       'text-amber-300',
    description: 'text-amber-500/80',
    title:       'CALIBRATING',
    subtitle:    'Collecting empty-room baseline — keep the room clear',
    showScore:   false,
    showProgress: true,
  },
  CLEAR: {
    wrapper:     'border-emerald-500/60 bg-emerald-950/30',
    dot:         'bg-emerald-400',
    dotPing:     '',
    label:       'text-emerald-300',
    description: 'text-emerald-600',
    title:       'ALL CLEAR',
    subtitle:    'No motion detected — environment is stable',
    showScore:   true,
    showProgress: false,
  },
  MOTION: {
    wrapper:     'border-red-500/70 bg-red-950/40',
    dot:         'bg-red-500',
    dotPing:     'animate-ping bg-red-500',
    label:       'text-red-400',
    description: 'text-red-500/70',
    title:       'MOTION DETECTED',
    subtitle:    'Human presence detected via RSSI disruption',
    showScore:   true,
    showProgress: false,
  },
};

/**
 * Top-of-dashboard status banner.
 *
 * Props:
 *   state               — 'CALIBRATING' | 'CLEAR' | 'MOTION'
 *   anomalyScore        — number | null
 *   calibrationProgress — 0.0 – 1.0
 */
export default function MotionAlert({ state, anomalyScore, calibrationProgress }) {
  const cfg = STATE_CONFIG[state] ?? STATE_CONFIG.CALIBRATING;
  const pct = Math.round((calibrationProgress ?? 0) * 100);

  return (
    <div
      className={`rounded-xl border-2 px-6 py-5 transition-all duration-500 ${cfg.wrapper}`}
      role="status"
      aria-live="polite"
    >
      <div className="flex items-center gap-5">

        {/* Animated status dot */}
        <div className="relative flex-shrink-0 h-5 w-5">
          {cfg.dotPing && (
            <span className={`absolute inline-flex h-full w-full rounded-full opacity-75 ${cfg.dotPing}`} />
          )}
          <span className={`relative inline-flex h-5 w-5 rounded-full ${cfg.dot}`} />
        </div>

        {/* Title + subtitle */}
        <div className="flex-1 min-w-0">
          <p className={`text-2xl font-bold tracking-widest font-mono ${cfg.label}`}>
            {cfg.title}
          </p>
          <p className={`text-sm mt-0.5 ${cfg.description}`}>{cfg.subtitle}</p>
        </div>

        {/* Anomaly score badge */}
        {cfg.showScore && (
          <div className="flex-shrink-0 text-right">
            <p className="text-xs uppercase tracking-widest text-gray-500 mb-1">Anomaly Score</p>
            <p className={`text-4xl font-mono font-bold tabular-nums ${cfg.label}`}>
              {anomalyScore != null ? anomalyScore.toFixed(2) : '—'}
            </p>
          </div>
        )}

        {/* Calibration progress bar */}
        {cfg.showProgress && (
          <div className="flex-shrink-0 w-32">
            <div className="flex justify-between text-xs text-amber-500/70 mb-1">
              <span className="uppercase tracking-wider">Progress</span>
              <span className="font-mono">{pct}%</span>
            </div>
            <div className="h-2 w-full bg-gray-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-amber-400 rounded-full transition-all duration-300 ease-linear"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
