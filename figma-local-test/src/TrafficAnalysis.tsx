import { useState, useEffect } from 'react';
import { JUNCTIONS, congestionColor } from './data';

// ─── SVG Chart Components ─────────────────────────────────────────────────────

function LineChart({ data, color, label, unit }: {
  data: number[]; color: string; label: string; unit: string;
}) {
  const W = 400; const H = 100;
  const max = Math.max(...data, 1);
  const min = Math.min(...data, 0);
  const range = max - min || 1;
  const pts = data.map((v, i) => ({
    x: (i / (data.length - 1)) * (W - 20) + 10,
    y: H - 10 - ((v - min) / range) * (H - 20),
  }));
  const path = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
  const area = `${path} L${pts[pts.length - 1].x},${H} L${pts[0].x},${H} Z`;

  return (
    <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
      <defs>
        <linearGradient id={`grad-${label}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.3"/>
          <stop offset="100%" stopColor={color} stopOpacity="0.02"/>
        </linearGradient>
      </defs>
      {/* Grid lines */}
      {[0.25, 0.5, 0.75].map(f => (
        <line key={f} x1="0" y1={H * f} x2={W} y2={H * f} stroke="#E2E8F0" strokeWidth="1"/>
      ))}
      <path d={area} fill={`url(#grad-${label})`}/>
      <path d={path} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      {/* Latest point */}
      <circle cx={pts[pts.length - 1].x} cy={pts[pts.length - 1].y} r="4" fill={color}/>
    </svg>
  );
}

function BarChart({ data, labels, color }: { data: number[]; labels: string[]; color: string }) {
  const W = 400; const H = 120;
  const max = Math.max(...data, 1);
  const barW = (W - 20) / data.length - 4;

  return (
    <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
      {data.map((v, i) => {
        const barH = ((v / max) * (H - 24));
        const x = 10 + i * ((W - 20) / data.length) + 2;
        const isHigh = v / max > 0.75;
        return (
          <g key={i}>
            <rect x={x} y={H - 18 - barH} width={barW} height={barH} rx="2"
              fill={isHigh ? '#DC2626' : color} opacity={0.8}/>
            <text x={x + barW / 2} y={H - 4} textAnchor="middle" fontSize="7.5"
              fill="#94A3B8" fontFamily="Inter, sans-serif">{labels[i]}</text>
          </g>
        );
      })}
    </svg>
  );
}

function HeatmapCell({ value, label }: { value: number; label: string }) {
  const bg = value > 80 ? '#DC2626' : value > 60 ? '#EA580C' : value > 40 ? '#D97706' : '#16A34A';
  const opacity = 0.2 + (value / 100) * 0.75;
  return (
    <div className="rounded p-2 text-center" style={{ background: bg + Math.round(opacity * 255).toString(16).padStart(2, '0') }}>
      <div className="text-xs font-bold" style={{ color: value > 40 ? '#fff' : '#0F172A', textShadow: value > 40 ? '0 1px 2px rgba(0,0,0,0.4)' : 'none' }}>
        {value}%
      </div>
      <div className="text-xs mt-0.5" style={{ color: value > 60 ? 'rgba(255,255,255,0.8)' : '#64748B' }}>{label}</div>
    </div>
  );
}

function useTimeSeries(base: number, variance: number, length: number) {
  const [series, setSeries] = useState(() =>
    Array.from({ length }, (_, i) => Math.max(0, base + Math.sin(i * 0.5) * variance + (Math.random() - 0.5) * variance * 0.5))
  );
  useEffect(() => {
    const id = setInterval(() => {
      setSeries(prev => [...prev.slice(1), Math.max(0, base + Math.sin(Date.now() / 3000) * variance + (Math.random() - 0.5) * variance * 0.3)]);
    }, 2000);
    return () => clearInterval(id);
  }, [base, variance]);
  return series;
}

export default function TrafficAnalysis() {
  const [activeJunction, setActiveJunction] = useState('J01');
  const junction = JUNCTIONS.find(j => j.id === activeJunction) || JUNCTIONS[0];

  const densityData = useTimeSeries(junction.signals.north.vehicleDensity, 20, 20);
  const speedData = useTimeSeries(junction.signals.north.avgSpeed, 15, 20);
  const flowData = useTimeSeries(junction.totalVehicles / 3, 30, 20);
  const queueData = useTimeSeries(junction.signals.north.queueLength, 5, 20);

  const hours = ['6am', '7am', '8am', '9am', '10am', '11am', '12pm', '1pm', '2pm', '3pm', '4pm', '5pm', '6pm', '7pm', '8pm'];
  const peakHourData = [25, 55, 88, 82, 62, 45, 50, 58, 52, 60, 75, 92, 95, 78, 55];

  const heatmapTime = ['6-8', '8-10', '10-12', '12-2', '2-4', '4-6', '6-8', '8-10'];
  const junctionNames = JUNCTIONS.slice(0, 6).map(j => j.name.replace(' Junction', '').substring(0, 10));

  const heatmapData = JUNCTIONS.slice(0, 6).map(j =>
    heatmapTime.map((_, ti) => {
      const base = j.signals.north.vehicleDensity;
      const peaks = [0.4, 0.9, 0.6, 0.5, 0.55, 0.85, 0.95, 0.6];
      return Math.min(100, Math.round(base * peaks[ti] + Math.random() * 10));
    })
  );

  const aiPredictions = [
    { junction: 'MG Road Junction', time: '10 min', severity: 'high', reason: 'Evening rush + Signal E3 under-optimized', confidence: 87 },
    { junction: 'Silk Board Junction', time: '5 min', severity: 'critical', reason: 'Ongoing breakdown + increasing vehicle inflow', confidence: 94 },
    { junction: 'Electronic City Junction', time: '15 min', severity: 'high', reason: 'IT park shift-end surge pattern detected', confidence: 91 },
    { junction: 'Koramangala Junction', time: '20 min', severity: 'medium', reason: 'School dismissal + market activity correlation', confidence: 78 },
  ];

  return (
    <div className="h-full flex flex-col overflow-hidden" style={{ background: '#F8FAFC' }}>
      <div className="bg-white border-b px-6 py-4" style={{ borderColor: '#E2E8F0' }}>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold" style={{ color: '#0F172A' }}>Traffic Analysis</h1>
            <p className="text-sm mt-0.5" style={{ color: '#64748B' }}>Real-time analytics · AI predictions · Historical patterns</p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs px-3 py-1 rounded-full" style={{ background: '#EFF6FF', color: '#1D4ED8' }}>
              Live Data
            </span>
            <div className="w-1.5 h-1.5 rounded-full bg-green-500 blink-fast"/>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-5">
        {/* Junction selector */}
        <div className="flex gap-2 flex-wrap">
          {JUNCTIONS.map(j => (
            <button key={j.id} onClick={() => setActiveJunction(j.id)}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold transition-all"
              style={{
                background: activeJunction === j.id ? '#1D4ED8' : 'white',
                color: activeJunction === j.id ? 'white' : '#475569',
                border: `1px solid ${activeJunction === j.id ? '#1D4ED8' : '#E2E8F0'}`,
              }}>
              {j.name.replace(' Junction', '')}
            </button>
          ))}
        </div>

        {/* Real-time charts */}
        <div className="grid grid-cols-2 gap-4">
          {[
            { title: 'Vehicle Density', data: densityData, color: '#DC2626', unit: '%', current: Math.round(densityData[densityData.length - 1]) },
            { title: 'Average Speed', data: speedData, color: '#1D4ED8', unit: 'km/h', current: Math.round(speedData[speedData.length - 1]) },
            { title: 'Vehicle Flow', data: flowData, color: '#16A34A', unit: 'veh/min', current: Math.round(flowData[flowData.length - 1]) },
            { title: 'Queue Length', data: queueData, color: '#D97706', unit: 'vehicles', current: Math.round(queueData[queueData.length - 1]) },
          ].map(chart => (
            <div key={chart.title} className="bg-white rounded-xl border p-4" style={{ borderColor: '#E2E8F0' }}>
              <div className="flex items-baseline justify-between mb-3">
                <div className="text-sm font-bold" style={{ color: '#0F172A' }}>{chart.title}</div>
                <div>
                  <span className="text-xl font-bold mono" style={{ color: chart.color }}>{chart.current}</span>
                  <span className="text-xs ml-1" style={{ color: '#94A3B8' }}>{chart.unit}</span>
                </div>
              </div>
              <LineChart data={chart.data} color={chart.color} label={chart.title} unit={chart.unit}/>
              <div className="flex justify-between text-xs mt-1" style={{ color: '#94A3B8' }}>
                <span>2 min ago</span><span>Now</span>
              </div>
            </div>
          ))}
        </div>

        {/* Peak hours chart */}
        <div className="bg-white rounded-xl border p-4" style={{ borderColor: '#E2E8F0' }}>
          <div className="flex items-baseline justify-between mb-3">
            <div className="text-sm font-bold" style={{ color: '#0F172A' }}>Peak Hour Traffic Pattern — Today</div>
            <div className="text-xs" style={{ color: '#94A3B8' }}>Vehicle density by hour</div>
          </div>
          <BarChart data={peakHourData} labels={hours} color="#1D4ED8"/>
          <div className="mt-3 flex items-center gap-4 text-xs" style={{ color: '#64748B' }}>
            <span>AM Peak: <strong style={{ color: '#DC2626' }}>8–9 AM (88%)</strong></span>
            <span>PM Peak: <strong style={{ color: '#DC2626' }}>5–7 PM (95%)</strong></span>
            <span>Off-Peak: <strong style={{ color: '#16A34A' }}>10 AM–3 PM (avg 52%)</strong></span>
          </div>
        </div>

        {/* Heatmap */}
        <div className="bg-white rounded-xl border p-4" style={{ borderColor: '#E2E8F0' }}>
          <div className="text-sm font-bold mb-4" style={{ color: '#0F172A' }}>Junction Congestion Heatmap — by Hour</div>
          <div className="overflow-x-auto">
            <div style={{ minWidth: 600 }}>
              {/* Hour labels */}
              <div className="grid mb-2" style={{ gridTemplateColumns: '100px repeat(8, 1fr)' }}>
                <div/>
                {heatmapTime.map(t => (
                  <div key={t} className="text-center text-xs font-semibold" style={{ color: '#64748B' }}>{t}</div>
                ))}
              </div>
              {/* Rows */}
              {JUNCTIONS.slice(0, 6).map((j, ji) => (
                <div key={j.id} className="grid gap-1 mb-1" style={{ gridTemplateColumns: '100px repeat(8, 1fr)' }}>
                  <div className="text-xs pr-2 text-right truncate flex items-center justify-end"
                    style={{ color: '#64748B' }}>
                    {j.name.replace(' Junction', '').substring(0, 14)}
                  </div>
                  {heatmapData[ji].map((val, ti) => (
                    <HeatmapCell key={ti} value={val} label={`${val}%`}/>
                  ))}
                </div>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-2 mt-4 text-xs" style={{ color: '#64748B' }}>
            <span>Low</span>
            {['#16A34A', '#D97706', '#EA580C', '#DC2626'].map(c => (
              <div key={c} className="w-6 h-3 rounded" style={{ background: c }}/>
            ))}
            <span>Critical</span>
          </div>
        </div>

        {/* AI predictions */}
        <div className="bg-white rounded-xl border overflow-hidden" style={{ borderColor: '#E2E8F0' }}>
          <div className="px-4 py-3 border-b flex items-center gap-2" style={{ borderColor: '#E2E8F0' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="#1D4ED8">
              <circle cx="12" cy="12" r="10"/>
              <path d="M12 8v4M12 16h.01" stroke="white" strokeWidth="2" strokeLinecap="round"/>
            </svg>
            <span className="text-sm font-bold" style={{ color: '#0F172A' }}>AI Congestion Predictions</span>
            <div className="ml-auto flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 rounded-full bg-blue-500 blink-fast"/>
              <span className="text-xs" style={{ color: '#94A3B8' }}>Updating every 60s</span>
            </div>
          </div>
          <div className="divide-y" style={{ borderColor: '#F1F5F9' }}>
            {aiPredictions.map((p, i) => (
              <div key={i} className="px-4 py-3 flex items-start gap-4">
                <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
                  style={{ background: p.severity === 'critical' ? '#FEF2F2' : p.severity === 'high' ? '#FFF7ED' : '#FFFBEB' }}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={p.severity === 'critical' ? '#DC2626' : p.severity === 'high' ? '#EA580C' : '#D97706'} strokeWidth="2">
                    <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
                    <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
                  </svg>
                </div>
                <div className="flex-1">
                  <div className="text-sm font-bold" style={{ color: '#0F172A' }}>
                    {p.severity === 'critical' ? '🔴' : p.severity === 'high' ? '🟠' : '🟡'}{' '}
                    Heavy congestion predicted at {p.junction} in <span style={{ color: '#DC2626' }}>{p.time}</span>
                  </div>
                  <div className="text-xs mt-0.5" style={{ color: '#64748B' }}>{p.reason}</div>
                </div>
                <div className="text-right flex-shrink-0">
                  <div className="text-xs font-bold" style={{ color: '#16A34A' }}>{p.confidence}%</div>
                  <div className="text-xs" style={{ color: '#94A3B8' }}>confidence</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Junction comparison */}
        <div className="bg-white rounded-xl border overflow-hidden" style={{ borderColor: '#E2E8F0' }}>
          <div className="px-4 py-3 border-b" style={{ borderColor: '#E2E8F0' }}>
            <span className="text-sm font-bold" style={{ color: '#0F172A' }}>Junction Performance Comparison</span>
          </div>
          <div className="p-4 space-y-3">
            {JUNCTIONS.map(j => {
              const density = j.signals.north.vehicleDensity;
              return (
                <div key={j.id} className="flex items-center gap-3">
                  <div className="w-32 text-xs truncate font-semibold" style={{ color: '#475569' }}>
                    {j.name.replace(' Junction', '')}
                  </div>
                  <div className="flex-1 h-5 rounded-full overflow-hidden" style={{ background: '#F1F5F9' }}>
                    <div className="h-full rounded-full flex items-center px-2 transition-all"
                      style={{ width: `${density}%`, background: congestionColor[j.congestionLevel] }}>
                      <span className="text-white text-xs font-bold">{density}%</span>
                    </div>
                  </div>
                  <div className="w-20 text-right">
                    <span className="text-xs font-semibold" style={{ color: congestionColor[j.congestionLevel] }}>
                      {j.signals.north.avgSpeed} km/h
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
