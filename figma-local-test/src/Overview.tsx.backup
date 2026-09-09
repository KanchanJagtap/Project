import { useState, useEffect } from 'react';
import { JUNCTIONS, INCIDENTS, VIOLATIONS, EMERGENCY_VEHICLES, congestionColor, type Junction } from './data';

interface OverviewProps {
  onNavigate: (section: string, data?: unknown) => void;
}

const StatCard = ({ label, value, sub, color, icon }: {
  label: string; value: string | number; sub?: string; color: string; icon: React.ReactNode;
}) => (
  <div className="stat-card bg-white rounded-xl p-4 border flex items-start gap-4" style={{ borderColor: '#E2E8F0' }}>
    <div className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
      style={{ background: color + '15', color }}>
      {icon}
    </div>
    <div>
      <div className="text-2xl font-bold" style={{ color: '#0F172A' }}>{value}</div>
      <div className="text-xs font-semibold" style={{ color: '#475569' }}>{label}</div>
      {sub && <div className="text-xs mt-0.5" style={{ color: '#94A3B8' }}>{sub}</div>}
    </div>
  </div>
);

const CityMap = ({ junctions, onJunctionClick }: {
  junctions: Junction[];
  onJunctionClick: (j: Junction) => void;
}) => {
  const [hovered, setHovered] = useState<string | null>(null);

  // Road connections between junctions
  const roads = [
    ['J01', 'J02'], ['J01', 'J05'], ['J01', 'J12'], ['J02', 'J04'], ['J02', 'J07'],
    ['J03', 'J05'], ['J03', 'J10'], ['J04', 'J07'], ['J05', 'J08'], ['J05', 'J12'],
    ['J06', 'J11'], ['J06', 'J12'], ['J07', 'J09'], ['J08', 'J09'], ['J09', 'J07'],
    ['J10', 'J03'], ['J11', 'J06'], ['J12', 'J11'],
  ];

  const getJunction = (id: string) => junctions.find(j => j.id === id);

  return (
    <div className="relative w-full h-full bg-white rounded-xl overflow-hidden border" style={{ borderColor: '#E2E8F0' }}>
      {/* Map background */}
      <div className="absolute inset-0" style={{
        background: '#F8FAFC',
        backgroundImage: 'linear-gradient(#E2E8F0 1px, transparent 1px), linear-gradient(90deg, #E2E8F0 1px, transparent 1px)',
        backgroundSize: '40px 40px',
      }}/>

      <svg width="100%" height="100%" viewBox="0 0 760 500" className="absolute inset-0">
        {/* City blocks (background rectangles) */}
        {[
          [60, 60, 120, 80], [220, 40, 100, 60], [380, 50, 80, 70], [530, 60, 100, 70],
          [650, 120, 80, 100], [60, 180, 90, 80], [380, 180, 80, 60], [120, 300, 80, 100],
          [380, 420, 100, 60], [600, 360, 100, 70], [60, 380, 100, 80], [240, 200, 60, 80],
        ].map(([x, y, w, h], i) => (
          <rect key={i} x={x} y={y} width={w} height={h} rx="4" fill="#E8EDF2" opacity="0.6"/>
        ))}

        {/* Roads */}
        {roads.map(([a, b], i) => {
          const ja = getJunction(a);
          const jb = getJunction(b);
          if (!ja || !jb) return null;
          return (
            <line key={i} x1={ja.mapX} y1={ja.mapY} x2={jb.mapX} y2={jb.mapY}
              stroke="#CBD5E1" strokeWidth="8" strokeLinecap="round"/>
          );
        })}

        {/* Road center markings */}
        {roads.map(([a, b], i) => {
          const ja = getJunction(a);
          const jb = getJunction(b);
          if (!ja || !jb) return null;
          return (
            <line key={`m${i}`} x1={ja.mapX} y1={ja.mapY} x2={jb.mapX} y2={jb.mapY}
              stroke="#E2E8F0" strokeWidth="1" strokeDasharray="6 6" opacity="0.8"/>
          );
        })}

        {/* Emergency corridor highlight */}
        {EMERGENCY_VEHICLES.filter(ev => ev.corridorActive).map(ev => {
          const route = ev.routeJunctions;
          for (let i = 0; i < route.length - 1; i++) {
            const ja = getJunction(route[i]);
            const jb = getJunction(route[i + 1]);
            if (!ja || !jb) continue;
          }
          return route.slice(0, -1).map((rid, i) => {
            const ja = getJunction(rid);
            const jb = getJunction(route[i + 1]);
            if (!ja || !jb) return null;
            return (
              <line key={`emg-${ev.id}-${i}`}
                x1={ja.mapX} y1={ja.mapY} x2={jb.mapX} y2={jb.mapY}
                stroke="#DC2626" strokeWidth="4" strokeDasharray="8 4"
                className="corridor-active" opacity="0.8"/>
            );
          });
        })}

        {/* Junctions */}
        {junctions.map(j => {
          const isHovered = hovered === j.id;
          const color = congestionColor[j.congestionLevel];
          return (
            <g key={j.id} className="map-junction"
              onMouseEnter={() => setHovered(j.id)}
              onMouseLeave={() => setHovered(null)}
              onClick={() => onJunctionClick(j)}>
              {/* Outer glow for critical/high */}
              {(j.congestionLevel === 'critical' || j.congestionLevel === 'high') && (
                <circle cx={j.mapX} cy={j.mapY} r={isHovered ? 20 : 16} fill={color} opacity="0.15"/>
              )}
              {/* Junction circle */}
              <circle cx={j.mapX} cy={j.mapY} r={isHovered ? 10 : 8} fill={color}
                stroke="white" strokeWidth="2.5"/>
              {/* Camera icon indicator */}
              <circle cx={j.mapX} cy={j.mapY} r={3} fill="white" opacity="0.9"/>

              {/* Label */}
              {(isHovered || j.congestionLevel === 'critical') && (
                <g>
                  <rect x={j.mapX - 60} y={j.mapY - 36} width={120} height={22} rx="4"
                    fill="#0F172A" opacity="0.9"/>
                  <text x={j.mapX} y={j.mapY - 21} textAnchor="middle"
                    fill="white" fontSize="9" fontFamily="Inter, sans-serif" fontWeight="600">
                    {j.name.length > 20 ? j.name.substring(0, 18) + '…' : j.name}
                  </text>
                </g>
              )}
            </g>
          );
        })}

        {/* Legend */}
        <g>
          <rect x="20" y="455" width="230" height="36" rx="6" fill="white" opacity="0.95" stroke="#E2E8F0"/>
          {[
            { color: '#16A34A', label: 'Low' },
            { color: '#D97706', label: 'Medium' },
            { color: '#EA580C', label: 'High' },
            { color: '#DC2626', label: 'Critical' },
          ].map((item, i) => (
            <g key={item.label} transform={`translate(${30 + i * 56}, 473)`}>
              <circle r="5" fill={item.color}/>
              <text x="8" y="4" fontSize="9" fill="#475569" fontFamily="Inter, sans-serif">{item.label}</text>
            </g>
          ))}
        </g>

        {/* Title */}
        <text x="740" y="20" textAnchor="end" fontSize="10" fill="#94A3B8" fontFamily="Inter, sans-serif">
          Bengaluru Metropolitan Area
        </text>
      </svg>

      {/* Junction detail popup */}
      {hovered && (() => {
        const j = junctions.find(x => x.id === hovered);
        if (!j) return null;
        return (
          <div className="absolute bottom-4 right-4 bg-white rounded-xl shadow-lg p-4 w-56 border z-20"
            style={{ borderColor: '#E2E8F0' }}>
            <div className="flex items-start justify-between mb-3">
              <div>
                <div className="font-bold text-sm" style={{ color: '#0F172A' }}>{j.name}</div>
                <div className="text-xs mt-0.5" style={{ color: '#64748B' }}>{j.location}</div>
              </div>
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full capitalize"
                style={{ background: congestionColor[j.congestionLevel] + '20', color: congestionColor[j.congestionLevel] }}>
                {j.congestionLevel}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div><span style={{ color: '#94A3B8' }}>Vehicles</span><div className="font-bold">{j.totalVehicles}</div></div>
              <div><span style={{ color: '#94A3B8' }}>Cameras</span><div className="font-bold">{j.cameras.length}</div></div>
              <div><span style={{ color: '#94A3B8' }}>Avg Speed</span><div className="font-bold">{j.signals.north.avgSpeed} km/h</div></div>
              <div><span style={{ color: '#94A3B8' }}>Mode</span><div className="font-bold capitalize">{j.mode}</div></div>
            </div>
            <div className="mt-3 text-xs text-center font-semibold" style={{ color: '#1D4ED8' }}>
              Click to view details →
            </div>
          </div>
        );
      })()}
    </div>
  );
};

const JunctionModal = ({ junction, onClose, onNavigate }: {
  junction: Junction;
  onClose: () => void;
  onNavigate: (s: string, d?: unknown) => void;
}) => {
  const arms = ['north', 'south', 'east', 'west'] as const;
  const sigColor = { red: '#DC2626', yellow: '#D97706', green: '#16A34A' };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6"
      style={{ background: 'rgba(15,23,42,0.7)' }}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-start justify-between p-6 border-b" style={{ borderColor: '#E2E8F0' }}>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-semibold px-2 py-0.5 rounded" style={{ background: '#EFF6FF', color: '#1D4ED8' }}>
                {junction.id}
              </span>
              <span className="text-xs font-semibold px-2 py-0.5 rounded capitalize"
                style={{ background: congestionColor[junction.congestionLevel] + '20', color: congestionColor[junction.congestionLevel] }}>
                {junction.congestionLevel} traffic
              </span>
            </div>
            <h2 className="text-xl font-bold" style={{ color: '#0F172A' }}>{junction.name}</h2>
            <p className="text-sm mt-0.5" style={{ color: '#64748B' }}>{junction.location}</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 ml-4">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>

        <div className="p-6 space-y-5">
          {/* Quick stats */}
          <div className="grid grid-cols-4 gap-3">
            {[
              { label: 'Total Vehicles', value: junction.totalVehicles },
              { label: 'Avg Speed', value: `${junction.signals.north.avgSpeed} km/h` },
              { label: 'Cameras', value: junction.cameras.length },
              { label: 'Mode', value: junction.mode === 'adaptive' ? 'AI Adaptive' : 'Fixed' },
            ].map(s => (
              <div key={s.label} className="rounded-lg p-3 text-center" style={{ background: '#F8FAFC' }}>
                <div className="text-lg font-bold" style={{ color: '#0F172A' }}>{s.value}</div>
                <div className="text-xs" style={{ color: '#64748B' }}>{s.label}</div>
              </div>
            ))}
          </div>

          {/* Signal arms */}
          <div>
            <h3 className="text-sm font-semibold mb-3" style={{ color: '#0F172A' }}>Signal States</h3>
            <div className="grid grid-cols-2 gap-3">
              {arms.map(arm => {
                const sig = junction.signals[arm];
                return (
                  <div key={arm} className="rounded-xl p-4 border" style={{ borderColor: '#E2E8F0' }}>
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-xs font-semibold uppercase tracking-wide" style={{ color: '#64748B' }}>
                        {arm}
                      </span>
                      <div className="flex items-center gap-1.5">
                        <div className="w-3 h-3 rounded-full" style={{ background: sigColor[sig.color] }}/>
                        <span className="text-xs font-bold uppercase" style={{ color: sigColor[sig.color] }}>
                          {sig.color}
                        </span>
                        <span className="mono text-xs" style={{ color: '#64748B' }}>{sig.timer}s</span>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                      <div className="flex justify-between"><span style={{ color: '#94A3B8' }}>Density</span><strong>{sig.vehicleDensity}%</strong></div>
                      <div className="flex justify-between"><span style={{ color: '#94A3B8' }}>Queue</span><strong>{sig.queueLength} veh</strong></div>
                      <div className="flex justify-between"><span style={{ color: '#94A3B8' }}>Speed</span><strong>{sig.avgSpeed} km/h</strong></div>
                      <div className="flex justify-between"><span style={{ color: '#94A3B8' }}>Wait</span><strong>{sig.waitingTime}s</strong></div>
                    </div>
                    {/* Density bar */}
                    <div className="mt-2 h-1.5 rounded-full" style={{ background: '#E2E8F0' }}>
                      <div className="h-full rounded-full" style={{
                        width: `${sig.vehicleDensity}%`,
                        background: sig.vehicleDensity > 80 ? '#DC2626' : sig.vehicleDensity > 60 ? '#D97706' : '#16A34A'
                      }}/>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* AI Reason */}
          {junction.aiReason && (
            <div className="rounded-xl p-4 border-l-4" style={{ background: '#EFF6FF', borderColor: '#1D4ED8' }}>
              <div className="flex items-center gap-2 mb-1">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="#1D4ED8">
                  <circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01" stroke="white" strokeWidth="2" strokeLinecap="round"/>
                </svg>
                <span className="text-xs font-bold" style={{ color: '#1D4ED8' }}>AI Analysis</span>
              </div>
              <p className="text-sm" style={{ color: '#1E40AF' }}>{junction.aiReason}</p>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3">
            <button
              onClick={() => { onClose(); onNavigate('livefeed', junction.id); }}
              className="flex-1 py-2.5 rounded-lg text-sm font-semibold text-white"
              style={{ background: '#1D4ED8' }}>
              View Live Cameras
            </button>
            <button
              onClick={() => { onClose(); onNavigate('signals', junction.id); }}
              className="flex-1 py-2.5 rounded-lg text-sm font-semibold border"
              style={{ borderColor: '#1D4ED8', color: '#1D4ED8' }}>
              Control Signals
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default function Overview({ onNavigate }: OverviewProps) {
  const [junctions, setJunctions] = useState(JUNCTIONS);
  const [selectedJunction, setSelectedJunction] = useState<Junction | null>(null);
  const [tick, setTick] = useState(0);

  // Live tick
  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 1000);
    return () => clearInterval(id);
  }, []);

  // Simulate changing vehicle counts and signals
  useEffect(() => {
    setJunctions(prev => prev.map(j => ({
      ...j,
      totalVehicles: Math.max(10, j.totalVehicles + Math.floor(Math.random() * 6) - 3),
      signals: {
        north: { ...j.signals.north, timer: Math.max(0, j.signals.north.timer - 1) || j.signals.north.greenDuration },
        south: { ...j.signals.south, timer: Math.max(0, j.signals.south.timer - 1) || j.signals.south.greenDuration },
        east: { ...j.signals.east, timer: Math.max(0, j.signals.east.timer - 1) || j.signals.east.greenDuration },
        west: { ...j.signals.west, timer: Math.max(0, j.signals.west.timer - 1) || j.signals.west.greenDuration },
      },
    })));
  }, [tick]);

  const totalVehicles = junctions.reduce((s, j) => s + j.totalVehicles, 0);
  const activeIncidents = INCIDENTS.filter(i => i.status === 'active').length;
  const pendingViolations = VIOLATIONS.filter(v => v.status === 'pending').length;
  const congestedJunctions = junctions.filter(j => j.congestionLevel === 'high' || j.congestionLevel === 'critical').length;
  const avgSpeed = Math.round(junctions.reduce((s, j) => s + j.signals.north.avgSpeed, 0) / junctions.length);
  const emergencyActive = EMERGENCY_VEHICLES.filter(e => e.corridorActive).length;

  const aiInsights = [
    { icon: '🔴', text: 'Silk Board Junction: Critical congestion. Truck blocking westbound — AI extending green by 15s.', time: '1m ago', severity: 'critical' },
    { icon: '🟡', text: 'Electronic City Junction: IT park shift change surge predicted. Recommend adaptive mode.', time: '3m ago', severity: 'high' },
    { icon: '🟢', text: 'Hebbal Junction: Signal optimization saved avg 8.2s wait time per vehicle this hour.', time: '5m ago', severity: 'info' },
    { icon: '🔴', text: 'MG Road: Heavy congestion predicted in 10 minutes due to evening rush hour — pre-adjusting signals.', time: '7m ago', severity: 'high' },
    { icon: '🟡', text: 'Koramangala Junction: Queue forming on east approach. Recommending lane-specific green extension.', time: '9m ago', severity: 'medium' },
  ];

  return (
    <div className="h-full flex flex-col overflow-hidden" style={{ background: '#F8FAFC' }}>
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 bg-white border-b" style={{ borderColor: '#E2E8F0' }}>
        <div>
          <h1 className="text-xl font-bold" style={{ color: '#0F172A' }}>Traffic Command Overview</h1>
          <div className="flex items-center gap-2 mt-0.5">
            <div className="w-1.5 h-1.5 rounded-full bg-green-500 blink-fast"/>
            <span className="text-xs" style={{ color: '#64748B' }}>
              Live · Bengaluru Metropolitan Area · {new Date().toLocaleString('en-IN', { timeStyle: 'short', dateStyle: 'medium' })}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs px-3 py-1 rounded-full font-semibold" style={{ background: '#FEF2F2', color: '#DC2626' }}>
            {emergencyActive} Emergency Active
          </span>
          <button
            onClick={() => onNavigate('emergency')}
            className="text-xs px-3 py-1.5 rounded-lg font-semibold text-white"
            style={{ background: '#DC2626' }}>
            Emergency Panel →
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-5">
        {/* Stat cards */}
        <div className="grid grid-cols-6 gap-3">
          <StatCard label="Total Vehicles" value={totalVehicles.toLocaleString()} sub="Active on roads"
            color="#1D4ED8"
            icon={<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><rect x="1" y="3" width="15" height="13" rx="2"/><path d="M16 8h4l3 3v4h-7V8z"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/></svg>}
          />
          <StatCard label="Violations Today" value={VIOLATIONS.length} sub={`${pendingViolations} pending`}
            color="#D97706"
            icon={<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>}
          />
          <StatCard label="Active Incidents" value={activeIncidents} sub="Require attention"
            color="#DC2626"
            icon={<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>}
          />
          <StatCard label="Emergency Vehicles" value={emergencyActive} sub="Green corridors active"
            color="#7C3AED"
            icon={<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>}
          />
          <StatCard label="Congested Junctions" value={`${congestedJunctions}/12`} sub="High or critical"
            color="#EA580C"
            icon={<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>}
          />
          <StatCard label="Avg Speed" value={`${avgSpeed} km/h`} sub="City-wide average"
            color="#16A34A"
            icon={<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>}
          />
        </div>

        {/* Map + AI Insights */}
        <div className="grid grid-cols-3 gap-5" style={{ height: 420 }}>
          <div className="col-span-2">
            <CityMap junctions={junctions} onJunctionClick={setSelectedJunction} />
          </div>

          {/* AI insights */}
          <div className="flex flex-col gap-3">
            <div className="bg-white rounded-xl border p-4 flex-1 overflow-hidden flex flex-col" style={{ borderColor: '#E2E8F0' }}>
              <div className="flex items-center gap-2 mb-3">
                <div className="w-6 h-6 rounded flex items-center justify-center" style={{ background: '#EFF6FF' }}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="#1D4ED8">
                    <circle cx="12" cy="12" r="10"/>
                    <path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3" stroke="white" strokeWidth="2" fill="none"/>
                    <line x1="12" y1="17" x2="12.01" y2="17" stroke="white" strokeWidth="2"/>
                  </svg>
                </div>
                <span className="text-sm font-bold" style={{ color: '#0F172A' }}>AI Traffic Insights</span>
                <span className="ml-auto text-xs mono" style={{ color: '#94A3B8' }}>LIVE</span>
                <div className="w-1.5 h-1.5 rounded-full bg-blue-500 blink-fast"/>
              </div>
              <div className="space-y-2 overflow-y-auto flex-1">
                {aiInsights.map((ins, i) => (
                  <div key={i} className="rounded-lg p-3 text-xs border-l-2"
                    style={{
                      background: ins.severity === 'critical' ? '#FEF2F2' : ins.severity === 'high' ? '#FFFBEB' : '#F0FDF4',
                      borderColor: ins.severity === 'critical' ? '#DC2626' : ins.severity === 'high' ? '#D97706' : '#16A34A',
                    }}>
                    <div className="font-semibold mb-0.5" style={{ color: '#0F172A' }}>
                      {ins.icon} {ins.text}
                    </div>
                    <div style={{ color: '#94A3B8' }}>{ins.time}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Emergency vehicles */}
            <div className="bg-white rounded-xl border p-4" style={{ borderColor: '#E2E8F0' }}>
              <div className="flex items-center gap-2 mb-3">
                <span className="text-sm font-bold" style={{ color: '#0F172A' }}>Active Emergency</span>
                <div className="ml-auto w-1.5 h-1.5 rounded-full blink-fast" style={{ background: '#DC2626' }}/>
              </div>
              {EMERGENCY_VEHICLES.map(ev => (
                <div key={ev.id} className="flex items-start gap-3 py-2 border-t text-xs" style={{ borderColor: '#F1F5F9' }}>
                  <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5"
                    style={{ background: ev.type === 'ambulance' ? '#FEF2F2' : '#FFF7ED', color: ev.type === 'ambulance' ? '#DC2626' : '#EA580C' }}>
                    {ev.type === 'ambulance' ? '🚑' : '🚒'}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold mono" style={{ color: '#0F172A' }}>{ev.vehicleNo}</div>
                    <div style={{ color: '#64748B' }} className="truncate">{ev.destination}</div>
                    <div className="mt-1">
                      <span className="font-semibold" style={{ color: '#DC2626' }}>ETA: {ev.eta} min</span>
                      {' · '}
                      <span style={{ color: '#16A34A' }}>Corridor Active</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Bottom row: junction list + recent violations */}
        <div className="grid grid-cols-2 gap-5">
          {/* Junction table */}
          <div className="bg-white rounded-xl border overflow-hidden" style={{ borderColor: '#E2E8F0' }}>
            <div className="px-4 py-3 border-b flex items-center justify-between" style={{ borderColor: '#E2E8F0' }}>
              <span className="text-sm font-bold" style={{ color: '#0F172A' }}>Junction Status</span>
              <button onClick={() => onNavigate('signals')} className="text-xs" style={{ color: '#1D4ED8' }}>View All →</button>
            </div>
            <div className="divide-y" style={{ borderColor: '#F1F5F9' }}>
              {junctions.slice(0, 6).map(j => (
                <div key={j.id} className="flex items-center gap-3 px-4 py-2.5 hover:bg-slate-50 cursor-pointer"
                  onClick={() => setSelectedJunction(j)}>
                  <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: congestionColor[j.congestionLevel] }}/>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-semibold truncate" style={{ color: '#0F172A' }}>{j.name}</div>
                    <div className="text-xs" style={{ color: '#94A3B8' }}>{j.totalVehicles} vehicles</div>
                  </div>
                  <div className="flex items-center gap-2 text-xs">
                    <span style={{ color: '#64748B' }}>{j.signals.north.avgSpeed} km/h</span>
                    <span className="px-1.5 py-0.5 rounded text-xs font-semibold capitalize"
                      style={{ background: congestionColor[j.congestionLevel] + '20', color: congestionColor[j.congestionLevel] }}>
                      {j.congestionLevel}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Recent violations */}
          <div className="bg-white rounded-xl border overflow-hidden" style={{ borderColor: '#E2E8F0' }}>
            <div className="px-4 py-3 border-b flex items-center justify-between" style={{ borderColor: '#E2E8F0' }}>
              <span className="text-sm font-bold" style={{ color: '#0F172A' }}>Recent Violations</span>
              <button onClick={() => onNavigate('violations')} className="text-xs" style={{ color: '#1D4ED8' }}>View All →</button>
            </div>
            <div className="divide-y" style={{ borderColor: '#F1F5F9' }}>
              {VIOLATIONS.slice(0, 6).map(v => (
                <div key={v.id} className="flex items-center gap-3 px-4 py-2.5 hover:bg-slate-50 cursor-pointer"
                  onClick={() => onNavigate('violations')}>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="mono text-sm font-bold" style={{ color: '#0F172A' }}>{v.plate}</span>
                      <span className="text-xs px-1.5 py-0.5 rounded"
                        style={{ background: '#FEF2F2', color: '#DC2626' }}>
                        {v.type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                      </span>
                    </div>
                    <div className="text-xs mt-0.5" style={{ color: '#94A3B8' }}>
                      {v.junctionName} · {Math.round((Date.now() - v.timestamp.getTime()) / 60000)}m ago
                    </div>
                  </div>
                  <div className="text-sm font-bold" style={{ color: '#D97706' }}>₹{v.fine.toLocaleString()}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {selectedJunction && (
        <JunctionModal
          junction={selectedJunction}
          onClose={() => setSelectedJunction(null)}
          onNavigate={onNavigate}
        />
      )}
    </div>
  );
}
