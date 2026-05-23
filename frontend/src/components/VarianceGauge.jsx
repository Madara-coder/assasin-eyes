/**
 * SVG arc gauge visualising the anomaly score from 0 to MAX_SCORE.
 *
 * Geometry: 240° clockwise arc (8 o'clock → 12 o'clock → 4 o'clock).
 * SVG angle convention used here: 0° = 3 o'clock, clockwise = positive.
 *
 * Zone layout (proportional to MAX_SCORE = 5.0):
 *   green  0   → 1.0  (below baseline)
 *   amber  1.0 → 2.8  (elevated, approaching threshold)
 *   red    2.8 → 5.0  (threshold exceeded)
 *
 * The component renders once and its props rarely cause a visible re-render
 * because anomaly_score only changes at ~10 Hz and React batches those updates.
 */

import { memo, useMemo } from 'react';

// ── Gauge geometry constants ─────────────────────────────────────────────────
const CX = 100, CY = 88, R = 68, SW = 13;
const GAUGE_START = 150;   // screen degrees — 8 o'clock position
const GAUGE_SWEEP = 240;   // total arc span
const MAX_SCORE   = 5.0;
const THRESHOLD   = 2.8;

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Polar → SVG cartesian. angleDeg uses screen convention (0=right, CW+). */
function ptAt(radius, angleDeg) {
  const r = (angleDeg * Math.PI) / 180;
  return [CX + radius * Math.cos(r), CY + radius * Math.sin(r)];
}

/** Build an SVG arc path string from startDeg to endDeg (CW). */
function arcPath(startDeg, endDeg) {
  const [sx, sy] = ptAt(R, startDeg);
  const [ex, ey] = ptAt(R, endDeg);
  const large    = endDeg - startDeg > 180 ? 1 : 0;
  return `M ${sx.toFixed(2)} ${sy.toFixed(2)} A ${R} ${R} 0 ${large} 1 ${ex.toFixed(2)} ${ey.toFixed(2)}`;
}

/** Map an anomaly score to a screen angle. */
function scoreToAngle(score) {
  return GAUGE_START + (Math.min(Math.max(score, 0), MAX_SCORE) / MAX_SCORE) * GAUGE_SWEEP;
}

/** Return stroke colour for the current score. */
function zoneColor(score) {
  if (score >= THRESHOLD) return '#ef4444'; // red-500
  if (score >= 1.0)       return '#f59e0b'; // amber-500
  return '#22c55e';                          // green-500
}

// ── Pre-computed static arc paths (never change) ──────────────────────────────
const BG_ARC    = arcPath(GAUGE_START, GAUGE_START + GAUGE_SWEEP);
const ARC_GREEN = arcPath(GAUGE_START,                           GAUGE_START + (1.0     / MAX_SCORE) * GAUGE_SWEEP);
const ARC_AMBER = arcPath(GAUGE_START + (1.0     / MAX_SCORE) * GAUGE_SWEEP, GAUGE_START + (THRESHOLD / MAX_SCORE) * GAUGE_SWEEP);
const ARC_RED   = arcPath(GAUGE_START + (THRESHOLD / MAX_SCORE) * GAUGE_SWEEP, GAUGE_START + GAUGE_SWEEP);

// ── Component ─────────────────────────────────────────────────────────────────

const VarianceGauge = memo(({ anomalyScore, state }) => {
  const score    = anomalyScore ?? 0;
  const clamped  = Math.min(score, MAX_SCORE);
  const isCalib  = state === 'CALIBRATING';
  const color    = zoneColor(clamped);
  const needleAng = scoreToAngle(clamped);

  // Active fill arc — recomputed only when score or calibration state changes.
  const fillArc = useMemo(() => {
    if (isCalib || clamped < 0.02) return null;
    return arcPath(GAUGE_START, needleAng);
  }, [clamped, needleAng, isCalib]);

  // Threshold tick — spans the full track stroke width.
  const threshAng  = scoreToAngle(THRESHOLD);
  const [tIx, tIy] = ptAt(R - SW / 2 - 1, threshAng);
  const [tOx, tOy] = ptAt(R + SW / 2 + 1, threshAng);

  // Needle tip sits 5px inside the arc face.
  const [needleX, needleY] = ptAt(R - 5, needleAng);

  return (
    <div className="flex flex-col items-center w-full">
      <svg viewBox="0 0 200 148" className="w-full max-w-[260px]">

        {/* ── Background track ── */}
        <path d={BG_ARC} fill="none" stroke="#111827" strokeWidth={SW} strokeLinecap="round" />

        {/* ── Dimmed zone tracks ── */}
        <path d={ARC_GREEN} fill="none" stroke="#14532d" strokeWidth={SW} strokeLinecap="round" opacity="0.75" />
        <path d={ARC_AMBER} fill="none" stroke="#78350f" strokeWidth={SW} strokeLinecap="round" opacity="0.75" />
        <path d={ARC_RED}   fill="none" stroke="#7f1d1d" strokeWidth={SW} strokeLinecap="round" opacity="0.75" />

        {/* ── Active fill arc (bright, on top of zone tracks) ── */}
        {fillArc && (
          <path d={fillArc} fill="none" stroke={color} strokeWidth={SW} strokeLinecap="round" />
        )}

        {/* ── Threshold marker line ── */}
        <line
          x1={tIx.toFixed(2)} y1={tIy.toFixed(2)}
          x2={tOx.toFixed(2)} y2={tOy.toFixed(2)}
          stroke="#f59e0b" strokeWidth="2.5" strokeLinecap="round"
        />

        {/* ── Needle ── */}
        {!isCalib && (
          <>
            <line
              x1={CX} y1={CY}
              x2={needleX.toFixed(2)} y2={needleY.toFixed(2)}
              stroke={color} strokeWidth="2.5" strokeLinecap="round"
            />
            {/* Hub */}
            <circle cx={CX} cy={CY} r="6"   fill={color} />
            <circle cx={CX} cy={CY} r="3.5" fill="#030712" />
          </>
        )}

        {/* ── Score display (centre of arc bowl) ── */}
        <text
          x={CX} y={CY + 13}
          textAnchor="middle"
          fill={isCalib ? '#374151' : color}
          fontSize="26"
          fontFamily="ui-monospace, SFMono-Regular, monospace"
          fontWeight="700"
        >
          {isCalib ? '—' : clamped.toFixed(2)}
        </text>
        <text
          x={CX} y={CY + 26}
          textAnchor="middle"
          fill="#374151"
          fontSize="8"
          fontFamily="system-ui, sans-serif"
          letterSpacing="2"
        >
          ANOMALY SCORE
        </text>

        {/* ── Scale labels ── */}
        <text x="27"  y="133" textAnchor="middle" fill="#374151" fontSize="9" fontFamily="monospace">0</text>
        <text x="173" y="133" textAnchor="middle" fill="#374151" fontSize="9" fontFamily="monospace">{MAX_SCORE}×</text>
        {/* Threshold label positioned above/left of threshold tick */}
        <text x="128" y="19"  textAnchor="start"  fill="#78350f" fontSize="9" fontFamily="monospace">{THRESHOLD}×</text>
      </svg>

      <p className="text-xs font-semibold tracking-widest text-gray-600 uppercase -mt-1">
        Variance Gauge
      </p>
    </div>
  );
});

VarianceGauge.displayName = 'VarianceGauge';
export default VarianceGauge;
