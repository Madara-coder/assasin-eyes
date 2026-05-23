import { memo, useEffect, useRef } from 'react';
import Chart from 'chart.js/auto';
import { RingBuffer, MAX_CHART_POINTS, formatTimestamp } from '../utils/signalProcessor';

/**
 * Real-time RSSI line chart powered by Chart.js.
 *
 * This component renders exactly once and never re-renders for data updates.
 * All chart mutations happen imperatively inside the addRawListener callback,
 * bypassing React's render cycle entirely. chart.update('none') skips
 * Chart.js animations so updates are synchronous and instantaneous.
 *
 * Props:
 *   addRawListener(fn) — from useWebSocket; fn receives each parsed WS frame
 */
const SignalChart = memo(({ addRawListener }) => {
  const canvasRef = useRef(null);

  useEffect(() => {
    const labels  = new RingBuffer(MAX_CHART_POINTS);
    const rawBuf  = new RingBuffer(MAX_CHART_POINTS);
    const maBuf   = new RingBuffer(MAX_CHART_POINTS);

    const chart = new Chart(canvasRef.current, {
      type: 'line',
      data: {
        labels: [],
        datasets: [
          {
            label: 'RSSI Raw',
            data: [],
            borderColor: 'rgba(56, 189, 248, 0.55)',  // sky-400, semi-transparent
            backgroundColor: 'transparent',
            borderWidth: 1.5,
            pointRadius: 0,
            tension: 0.25,
            order: 2,
          },
          {
            label: 'Moving Average',
            data: [],
            borderColor: 'rgba(34, 197, 94, 1)',       // green-500, solid
            backgroundColor: 'rgba(34, 197, 94, 0.06)',
            borderWidth: 2.5,
            pointRadius: 0,
            tension: 0.4,
            fill: true,
            order: 1,
          },
        ],
      },
      options: {
        animation: false,
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: {
            labels: {
              color: '#9ca3af',
              boxWidth: 12,
              font: { size: 12 },
            },
          },
          tooltip: {
            backgroundColor: '#111827',
            titleColor: '#f9fafb',
            bodyColor: '#d1d5db',
            borderColor: '#374151',
            borderWidth: 1,
            callbacks: {
              label: (ctx) => ` ${ctx.dataset.label}: ${ctx.parsed.y.toFixed(1)} dBm`,
            },
          },
        },
        scales: {
          x: {
            ticks: {
              color: '#6b7280',
              maxTicksLimit: 8,
              maxRotation: 0,
              font: { size: 11 },
            },
            grid: { color: 'rgba(55, 65, 81, 0.4)' },
          },
          y: {
            min: -95,
            max: -20,
            title: {
              display: true,
              text: 'Signal Strength (dBm)',
              color: '#6b7280',
              font: { size: 12 },
            },
            ticks: { color: '#6b7280', font: { size: 11 } },
            grid: { color: 'rgba(55, 65, 81, 0.4)' },
          },
        },
      },
    });

    // Imperative update path — zero React re-renders.
    const unsub = addRawListener((msg) => {
      labels.push(formatTimestamp(msg.ts));
      rawBuf.push(msg.rssi_raw);
      maBuf.push(msg.rssi_ma);

      chart.data.labels            = labels.toArray();
      chart.data.datasets[0].data  = rawBuf.toArray();
      chart.data.datasets[1].data  = maBuf.toArray();
      chart.update('none');
    });

    return () => {
      unsub();
      chart.destroy();
    };
  }, [addRawListener]);

  return (
    <div className="relative w-full" style={{ height: '280px' }}>
      <canvas ref={canvasRef} />
    </div>
  );
});

SignalChart.displayName = 'SignalChart';
export default SignalChart;
