/**
 * Grid of six metric cards showing the live signal pipeline values.
 *
 * Cards are ordered to mirror the processing pipeline left-to-right:
 *   raw input → smoothed → variance → anomaly score | static config values
 */

const THRESHOLD = 2.8;

function anomalyColor(score) {
  if (score == null)      return 'text-gray-600';
  if (score >= THRESHOLD) return 'text-red-400';
  if (score >= 1.0)       return 'text-amber-400';
  return 'text-emerald-400';
}

function MetricCard({ label, value, unit, colorClass }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg px-4 py-3">
      <p className="text-xs text-gray-600 uppercase tracking-widest mb-1.5">{label}</p>
      <p className={`text-2xl font-mono font-bold tabular-nums leading-none ${colorClass}`}>
        {value ?? '—'}
        {unit && value != null && (
          <span className="text-xs font-normal text-gray-600 ml-1">{unit}</span>
        )}
      </p>
    </div>
  );
}

export default function MetricsPanel({ message }) {
  const score = message?.anomaly_score;

  const cards = [
    {
      label:      'RAW RSSI',
      value:      message?.rssi_raw?.toFixed(1),
      unit:       'dBm',
      colorClass: 'text-sky-400',
    },
    {
      label:      'MOVING AVG',
      value:      message?.rssi_ma?.toFixed(1),
      unit:       'dBm',
      colorClass: 'text-emerald-400',
    },
    {
      label:      'VARIANCE σ²',
      value:      message?.variance?.toFixed(3),
      unit:       '',
      colorClass: 'text-violet-400',
    },
    {
      label:      'ANOMALY SCORE',
      value:      score?.toFixed(2),
      unit:       '×',
      colorClass: anomalyColor(score),
    },
    {
      label:      'TRIGGER THRESHOLD',
      value:      `${THRESHOLD.toFixed(2)}`,
      unit:       '×',
      colorClass: 'text-amber-500',
    },
    {
      label:      'SAMPLE RATE',
      value:      '10',
      unit:       'Hz',
      colorClass: 'text-slate-400',
    },
  ];

  return (
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-widest text-gray-500 mb-3">
        Signal Metrics
      </h3>
      <div className="grid grid-cols-3 gap-3">
        {cards.map((c) => (
          <MetricCard key={c.label} {...c} />
        ))}
      </div>
    </div>
  );
}
