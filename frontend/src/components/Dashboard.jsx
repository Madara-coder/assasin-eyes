/**
 * Root layout for the Assassin Eyes dashboard.
 *
 * Grid layout (Phase 4):
 *   Row 1  MotionAlert banner          (full width)
 *   Row 2  SignalChart (2/3) | VarianceGauge (1/3)
 *   Row 3  MetricsPanel (2/3) | CalibrationPanel (1/3)
 */

import CalibrationPanel from './CalibrationPanel';
import MetricsPanel     from './MetricsPanel';
import MotionAlert      from './MotionAlert';
import SignalChart      from './SignalChart';
import VarianceGauge    from './VarianceGauge';
import { WS_STATUS }    from '../hooks/useWebSocket';

const WS_STYLE = {
  [WS_STATUS.CONNECTED]:    { dot: 'bg-emerald-400',              text: 'text-emerald-400' },
  [WS_STATUS.CONNECTING]:   { dot: 'bg-amber-400 animate-pulse',  text: 'text-amber-400'   },
  [WS_STATUS.RECONNECTING]: { dot: 'bg-amber-400 animate-pulse',  text: 'text-amber-400'   },
  [WS_STATUS.DISCONNECTED]: { dot: 'bg-red-500',                  text: 'text-red-400'     },
};

export default function Dashboard({ message, status, addRawListener, onRecalibrate }) {
  const ws = WS_STYLE[status] ?? WS_STYLE[WS_STATUS.CONNECTING];

  return (
    <div className="min-h-screen bg-gray-950 text-white">

      {/* ── Sticky header ─────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-10 border-b border-gray-800 bg-gray-950/90 backdrop-blur">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-extrabold tracking-tight">
              <span className="text-red-500">Assassin</span>
              <span className="text-white"> Eyes</span>
            </h1>
            <p className="text-[11px] text-gray-600 mt-0.5 font-mono tracking-wide">
              Wi-Fi RSSI · Device-Free Localization
            </p>
          </div>

          {/* WebSocket connection pill */}
          <div className={`flex items-center gap-2 text-xs font-mono ${ws.text}`}>
            <span className={`h-2 w-2 rounded-full flex-shrink-0 ${ws.dot}`} />
            {status}
          </div>
        </div>
      </header>

      {/* ── Main content ──────────────────────────────────────────────────── */}
      <main className="max-w-6xl mx-auto px-6 py-8 space-y-6">

        {/* Row 1 — Detection state banner */}
        <MotionAlert
          state={message?.state ?? 'CALIBRATING'}
          anomalyScore={message?.anomaly_score}
          calibrationProgress={message?.calibration_progress}
        />

        {/* Row 2 — Live chart (2/3) + Variance gauge (1/3) */}
        <div className="grid grid-cols-3 gap-6">

          <section className="col-span-2 bg-gray-900 border border-gray-800 rounded-xl p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-500">
                Live Signal · RSSI
              </h2>
              {message && (
                <span className="text-xs font-mono text-gray-600">
                  raw&nbsp;
                  <span className="text-sky-400">{message.rssi_raw?.toFixed(1)}</span>
                  &nbsp;dBm&nbsp;·&nbsp;MA&nbsp;
                  <span className="text-emerald-400">{message.rssi_ma?.toFixed(1)}</span>
                  &nbsp;dBm
                </span>
              )}
            </div>
            <SignalChart addRawListener={addRawListener} />
          </section>

          <section className="col-span-1 bg-gray-900 border border-gray-800 rounded-xl p-6
                              flex items-center justify-center">
            <VarianceGauge
              anomalyScore={message?.anomaly_score}
              state={message?.state ?? 'CALIBRATING'}
            />
          </section>

        </div>

        {/* Row 3 — Metrics (2/3) + Calibration panel (1/3) */}
        <div className="grid grid-cols-3 gap-6 items-start">

          <section className="col-span-2">
            <MetricsPanel message={message} />
          </section>

          <section className="col-span-1">
            <CalibrationPanel message={message} onRecalibrate={onRecalibrate} />
          </section>

        </div>

      </main>
    </div>
  );
}
