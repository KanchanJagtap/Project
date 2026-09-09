import { useState, useEffect, useRef, useMemo } from 'react';
import { EMERGENCY_VEHICLES, JUNCTIONS, type EmergencyVehicle, type Junction } from './data';

// ─── Types ────────────────────────────────────────────────────────────────────

interface GPSState {
  progress: number;
  currentSegment: number;
  gpsStatus: 'active' | 'degraded' | 'lost';
  lastKnownProgress: number;
  detectedByCamera: string | null;
  speed: number;
}

interface Waypoint {
  id: string;
  label: string;
  mapX: number;
  mapY: number;
  progressThreshold: number;
  type: 'origin' | 'junction' | 'destination';
  svgX: number;
  svgY: number;
}

type CorridorStatus = 'upcoming' | 'approaching' | 'current' | 'passed' | 'restoring';

interface JunctionCorridorStatus {
  junctionId: string;
  status: CorridorStatus;
  progressThreshold: number;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const EMG_COLOR = { ambulance: '#DC2626', fire_brigade: '#EA580C', police: '#1D4ED8' };
const EMG_ICON  = { ambulance: '🚑', fire_brigade: '🚒', police: '🚔' };
const EMG_BG    = { ambulance: '#FEF2F2', fire_brigade: '#FFF7ED', police: '#EFF6FF' };
const EMG_LABEL = { ambulance: 'Ambulance', fire_brigade: 'Fire Brigade', police: 'Police' };

const SVG_W = 700;
const SVG_H = 160;
const SVG_PAD_X = 70;
const SVG_MID_Y = SVG_H / 2;

// ─── Helpers ─────────────────────────────────────────────────────────────────

function buildWaypoints(vehicle: EmergencyVehicle, junctions: Junction[]): Waypoint[] {
  const routeJcts = vehicle.routeJunctions
    .map(id => junctions.find(j => j.id === id))
    .filter((j): j is Junction => j !== undefined);

  const total = routeJcts.length + 2; // origin + junctions + destination
  const spread = SVG_W - SVG_PAD_X * 2;

  const originX  = routeJcts.length > 0 ? routeJcts[0].mapX - 80  : 200;
  const originY  = routeJcts.length > 0 ? routeJcts[0].mapY       : 200;
  const destX    = routeJcts.length > 0 ? routeJcts[routeJcts.length-1].mapX + 80 : 600;
  const destY    = routeJcts.length > 0 ? routeJcts[routeJcts.length-1].mapY      : 200;

  const raw: Waypoint[] = [
    {
      id: 'origin', label: vehicle.origin,
      mapX: originX, mapY: originY,
      progressThreshold: 0,
      type: 'origin',
      svgX: SVG_PAD_X,
      svgY: SVG_MID_Y,
    },
    ...routeJcts.map((j, i) => ({
      id: j.id,
      label: j.name.replace(' Junction',''),
      mapX: j.mapX,
      mapY: j.mapY,
      progressThreshold: (i + 1) / (total - 1),
      type: 'junction' as const,
      svgX: SVG_PAD_X + ((i + 1) / (total - 1)) * spread,
      svgY: SVG_MID_Y + Math.sin((i + 1) * 0.9) * 22,
    })),
    {
      id: 'destination', label: vehicle.destination,
      mapX: destX, mapY: destY,
      progressThreshold: 1,
      type: 'destination',
      svgX: SVG_PAD_X + spread,
      svgY: SVG_MID_Y,
    },
  ];
  return raw;
}

function getCorridorStatus(progress: number, threshold: number): CorridorStatus {
  if (progress > threshold + 0.05) return 'passed';
  if (Math.abs(progress - threshold) <= 0.05) return 'current';
  if (progress > threshold - 0.15) return 'approaching';
  return 'upcoming';
}

function getCorridorStatuses(
  vehicle: EmergencyVehicle,
  progress: number,
  waypoints: Waypoint[],
): JunctionCorridorStatus[] {
  return vehicle.routeJunctions.map(jid => {
    const wp = waypoints.find(w => w.id === jid);
    const threshold = wp?.progressThreshold ?? 0;
    return {
      junctionId: jid,
      status: getCorridorStatus(progress, threshold),
      progressThreshold: threshold,
    };
  });
}

function getMarkerPosition(progress: number, waypoints: Waypoint[]) {
  if (waypoints.length < 2) return { x: SVG_PAD_X, y: SVG_MID_Y };
  let segIdx = waypoints.length - 2;
  for (let i = 0; i < waypoints.length - 1; i++) {
    if (progress <= waypoints[i + 1].progressThreshold) {
      segIdx = i;
      break;
    }
  }
  const wp1 = waypoints[segIdx];
  const wp2 = waypoints[segIdx + 1];
  const segRange = wp2.progressThreshold - wp1.progressThreshold;
  const localT = segRange > 0 ? (progress - wp1.progressThreshold) / segRange : 0;
  const t = Math.max(0, Math.min(1, localT));
  return {
    x: wp1.svgX + (wp2.svgX - wp1.svgX) * t,
    y: wp1.svgY + (wp2.svgY - wp1.svgY) * t,
  };
}

// ─── GPS Simulation Hook ─────────────────────────────────────────────────────

function useGPSSimulation(vehicle: EmergencyVehicle, isActive: boolean): GPSState {
  const [gpsState, setGpsState] = useState<GPSState>({
    progress: 0,
    currentSegment: 0,
    gpsStatus: 'active',
    lastKnownProgress: 0,
    detectedByCamera: null,
    speed: 65,
  });
  const recoveryTimerRef = useRef(0);
  const vehicleRef = useRef(vehicle);
  vehicleRef.current = vehicle;

  useEffect(() => {
    if (!isActive) return;
    const id = setInterval(() => {
      setGpsState(prev => {
        if (prev.progress >= 1) return prev;

        let { gpsStatus, detectedByCamera } = prev;

        // GPS status transitions
        const rand = Math.random();
        if (gpsStatus === 'active') {
          if (rand < 0.05) gpsStatus = 'degraded';
          else if (rand < 0.01) { gpsStatus = 'lost'; recoveryTimerRef.current = 10; }
        } else if (gpsStatus === 'degraded') {
          if (rand < 0.12) gpsStatus = 'active';
          else if (rand < 0.03) { gpsStatus = 'lost'; recoveryTimerRef.current = 10; }
        } else {
          recoveryTimerRef.current = Math.max(0, recoveryTimerRef.current - 0.5);
          if (recoveryTimerRef.current <= 0) gpsStatus = 'active';
        }

        // Camera detection sync
        if (Math.random() < 0.05 && vehicleRef.current.routeJunctions.length > 0) {
          const jIdx = Math.floor(Math.random() * vehicleRef.current.routeJunctions.length);
          const camNum = jIdx * 4 + Math.floor(Math.random() * 4) + 1;
          detectedByCamera = `CAM-${String(camNum).padStart(2,'0')}`;
          gpsStatus = 'active';
        }

        // Progress: dead reckoning when lost (slightly slower/noisier)
        const speedFactor = gpsStatus === 'lost' ? 0.85 : 1.0;
        const newProgress = Math.min(1, prev.progress + speedFactor * 0.003);
        const newSpeed    = gpsStatus === 'lost' ? prev.speed : Math.round(45 + Math.random() * 35);

        return {
          progress: newProgress,
          currentSegment: Math.floor(newProgress * vehicleRef.current.routeJunctions.length),
          gpsStatus,
          lastKnownProgress: gpsStatus !== 'lost' ? newProgress : prev.lastKnownProgress,
          detectedByCamera,
          speed: newSpeed,
        };
      });
    }, 500);
    return () => clearInterval(id);
  }, [isActive]);

  return gpsState;
}

// ─── Emergency Route Map (SVG) ────────────────────────────────────────────────

function EmergencyRouteMap({
  vehicle, junctions, gpsState, corridorStatuses, eta,
}: {
  vehicle: EmergencyVehicle;
  junctions: Junction[];
  gpsState: GPSState;
  corridorStatuses: JunctionCorridorStatus[];
  eta: number;
}) {
  const waypoints = useMemo(
    () => buildWaypoints(vehicle, junctions),
    [vehicle, junctions],
  );
  const markerPos = getMarkerPosition(gpsState.progress, waypoints);

  const statusColor: Record<CorridorStatus, string> = {
    passed:     '#374151',
    current:    '#DC2626',
    approaching:'#D97706',
    upcoming:   '#1E3A5F',
    restoring:  '#16A34A',
  };

  const nodeColor = (wp: Waypoint): string => {
    if (wp.type === 'origin')      return '#4B5563';
    if (wp.type === 'destination') return '#6D28D9';
    const cs = corridorStatuses.find(s => s.junctionId === wp.id);
    return cs ? statusColor[cs.status] : '#374151';
  };

  const segmentColor = (i: number): string => {
    if (i >= waypoints.length - 1) return '#374151';
    const progress = gpsState.progress;
    const wp1 = waypoints[i];
    const wp2 = waypoints[i + 1];
    if (progress > wp2.progressThreshold) return '#374151'; // passed
    if (progress > wp1.progressThreshold) return '#F59E0B'; // current
    // Check if next junction is approaching/current
    const cs2 = corridorStatuses.find(s => s.junctionId === wp2.id);
    if (cs2 && (cs2.status === 'approaching' || cs2.status === 'current')) return '#16A34A';
    if (cs2 && cs2.status === 'passed') return '#374151';
    return '#1E3A5F';
  };

  return (
    <div className="rounded-xl overflow-hidden" style={{ background: '#0F172A', border: '1px solid #1E293B' }}>
      <div className="px-4 py-2 border-b flex items-center gap-2" style={{ borderColor: 'rgba(255,255,255,0.08)' }}>
        <div className="w-2 h-2 rounded-full bg-red-500 blink-fast"/>
        <span className="text-xs font-bold text-white">Emergency Green Corridor — ACTIVE</span>
        <span className="ml-auto text-xs mono" style={{ color: '#64748B' }}>
          {vehicle.vehicleNo} · ETA {eta} min
        </span>
      </div>
      <div className="relative overflow-x-auto">
        <svg width="100%" height={SVG_H + 30} viewBox={`0 0 ${SVG_W} ${SVG_H + 30}`} preserveAspectRatio="xMidYMid meet">
          {/* Road segments */}
          {waypoints.map((wp, i) => {
            if (i >= waypoints.length - 1) return null;
            const next = waypoints[i + 1];
            const sc = segmentColor(i);
            return (
              <g key={`seg-${i}`}>
                <line x1={wp.svgX} y1={wp.svgY} x2={next.svgX} y2={next.svgY}
                  stroke="#1E293B" strokeWidth={12} strokeLinecap="round"/>
                <line x1={wp.svgX} y1={wp.svgY} x2={next.svgX} y2={next.svgY}
                  stroke={sc} strokeWidth={7} strokeLinecap="round"/>
                {/* Direction arrow midpoint */}
                <text
                  x={(wp.svgX + next.svgX) / 2}
                  y={(wp.svgY + next.svgY) / 2 - 9}
                  textAnchor="middle" fontSize="11" fill={sc} opacity="0.8">
                  →
                </text>
              </g>
            );
          })}

          {/* Waypoint nodes */}
          {waypoints.map((wp) => {
            const isCurrent = corridorStatuses.find(s => s.junctionId === wp.id)?.status === 'current';
            const nc = nodeColor(wp);
            const r  = wp.type === 'junction' ? (isCurrent ? 13 : 10) : 9;

            return (
              <g key={wp.id}>
                {/* Pulse ring for current */}
                {isCurrent && (
                  <circle cx={wp.svgX} cy={wp.svgY} r={22} fill="none"
                    stroke="#DC2626" strokeWidth={2} opacity="0.5">
                    <animate attributeName="r" from="16" to="28" dur="1.5s" repeatCount="indefinite"/>
                    <animate attributeName="opacity" from="0.7" to="0" dur="1.5s" repeatCount="indefinite"/>
                  </circle>
                )}
                <circle cx={wp.svgX} cy={wp.svgY} r={r+3} fill="#0F172A"/>
                <circle cx={wp.svgX} cy={wp.svgY} r={r} fill={nc}/>
                {wp.type === 'origin' && (
                  <text x={wp.svgX} y={wp.svgY+4} textAnchor="middle" fontSize="9" fill="white">🏥</text>
                )}
                {wp.type === 'destination' && (
                  <text x={wp.svgX} y={wp.svgY+4} textAnchor="middle" fontSize="9" fill="white">⭐</text>
                )}
                {/* Label */}
                <text x={wp.svgX} y={wp.svgY + r + 14} textAnchor="middle"
                  fontSize="8" fill={isCurrent ? '#EF4444' : '#64748B'} fontFamily="Inter, sans-serif">
                  {wp.label.substring(0, 16)}
                </text>
                {/* Status badge */}
                {wp.type === 'junction' && (() => {
                  const cs = corridorStatuses.find(s => s.junctionId === wp.id);
                  if (!cs) return null;
                  const badge: Record<CorridorStatus, string> = {
                    current: 'ACTIVE', approaching: 'CLEARING', passed: 'RESTORED',
                    upcoming: 'QUEUED', restoring: 'RESTORING',
                  };
                  return (
                    <text x={wp.svgX} y={wp.svgY - r - 6} textAnchor="middle"
                      fontSize="7" fill={statusColor[cs.status]} fontFamily="JetBrains Mono, monospace"
                      fontWeight="bold">
                      {badge[cs.status]}
                    </text>
                  );
                })()}
              </g>
            );
          })}

          {/* Emergency vehicle marker */}
          <g>
            {/* Glow */}
            <circle cx={markerPos.x} cy={markerPos.y} r={16} fill={EMG_COLOR[vehicle.type]} opacity="0.25">
              <animate attributeName="r" from="12" to="22" dur="1s" repeatCount="indefinite"/>
              <animate attributeName="opacity" from="0.4" to="0" dur="1s" repeatCount="indefinite"/>
            </circle>
            <circle cx={markerPos.x} cy={markerPos.y} r={14} fill={EMG_COLOR[vehicle.type]} opacity="0.15"/>
            <text x={markerPos.x} y={markerPos.y + 6} textAnchor="middle" fontSize="16">
              {EMG_ICON[vehicle.type]}
            </text>
          </g>

          {/* GPS status */}
          <g transform="translate(10, 5)">
            <circle cx={7} cy={7} r={4}
              fill={gpsState.gpsStatus === 'active' ? '#22C55E' : gpsState.gpsStatus === 'degraded' ? '#F59E0B' : '#DC2626'}/>
            <text x={15} y={11} fontSize="9" fill="#64748B" fontFamily="Inter">
              GPS {gpsState.gpsStatus === 'lost' ? 'DEAD RECKONING' : gpsState.gpsStatus.toUpperCase()}
            </text>
            <text x={120} y={11} fontSize="9" fill="#94A3B8" fontFamily="JetBrains Mono">
              {gpsState.speed} km/h
            </text>
            <text x={170} y={11} fontSize="9" fill="#94A3B8" fontFamily="JetBrains Mono">
              {Math.round(gpsState.progress * 100)}% complete
            </text>
            {gpsState.detectedByCamera && (
              <text x={260} y={11} fontSize="9" fill="#818CF8" fontFamily="JetBrains Mono">
                Cam: {gpsState.detectedByCamera}
              </text>
            )}
          </g>
        </svg>
      </div>
    </div>
  );
}

// ─── GPS Status Panel ─────────────────────────────────────────────────────────

function GPSStatusPanel({ gpsState, vehicle, junctions }: {
  gpsState: GPSState;
  vehicle: EmergencyVehicle;
  junctions: Junction[];
}) {
  const currentJct = junctions.find(j =>
    vehicle.routeJunctions[Math.min(gpsState.currentSegment, vehicle.routeJunctions.length - 1)] === j.id
  );

  const sigBars = (status: GPSState['gpsStatus']) => {
    const bars = status === 'active' ? 4 : status === 'degraded' ? 2 : 0;
    return (
      <div className="flex items-end gap-0.5">
        {[1,2,3,4].map(b => (
          <div key={b} className="w-1.5 rounded-sm"
            style={{
              height: `${b * 4}px`,
              background: b <= bars
                ? (status === 'active' ? '#22C55E' : status === 'degraded' ? '#F59E0B' : '#DC2626')
                : '#374151',
            }}/>
        ))}
      </div>
    );
  };

  return (
    <div className="rounded-xl p-3 border" style={{ background: '#0F172A', borderColor: '#1E293B' }}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-bold" style={{ color: '#94A3B8' }}>GPS Telemetry</span>
        {gpsState.gpsStatus === 'lost' && (
          <span className="text-xs font-bold px-1.5 py-0.5 rounded blink-fast"
            style={{ background: '#7F1D1D', color: '#FCA5A5' }}>DEAD RECKONING</span>
        )}
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
        {[
          { label: 'GPS Signal', value: (
            <div className="flex items-center gap-1.5">
              {sigBars(gpsState.gpsStatus)}
              <span className="text-xs font-bold" style={{
                color: gpsState.gpsStatus === 'active' ? '#22C55E' : gpsState.gpsStatus === 'degraded' ? '#F59E0B' : '#DC2626',
              }}>
                {gpsState.gpsStatus.toUpperCase()}
              </span>
            </div>
          )},
          { label: 'Speed',     value: <span className="text-xs font-bold text-white">{gpsState.speed} km/h</span> },
          { label: 'Progress',  value: <span className="text-xs font-bold text-white">{Math.round(gpsState.progress * 100)}%</span> },
          { label: 'Junction',  value: <span className="text-xs font-bold text-white truncate">{currentJct?.name.replace(' Junction','') ?? '—'}</span> },
          ...(gpsState.detectedByCamera ? [{
            label: 'Camera',
            value: <span className="text-xs font-bold" style={{ color: '#818CF8' }}>{gpsState.detectedByCamera}</span>,
          }] : []),
        ].map(row => (
          <div key={row.label} className="flex justify-between items-center gap-2">
            <span className="text-xs flex-shrink-0" style={{ color: '#475569' }}>{row.label}:</span>
            {row.value}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Signal Override Cards ────────────────────────────────────────────────────

function SignalOverrideList({ corridorStatuses, junctions }: {
  corridorStatuses: JunctionCorridorStatus[];
  junctions: Junction[];
}) {
  const config: Record<CorridorStatus, { icon: string; label: string; bg: string; border: string; text: string }> = {
    passed:     { icon: '✓', label: 'Restored to Normal AI', bg: '#F8FAFC', border: '#E2E8F0', text: '#94A3B8' },
    restoring:  { icon: '↺', label: 'Restoring Normal Signals', bg: '#F0FDF4', border: '#BBF7D0', text: '#16A34A' },
    current:    { icon: '🚨', label: 'CORRIDOR ACTIVE — Route GREEN, Conflicts RED', bg: '#FEF2F2', border: '#FECACA', text: '#DC2626' },
    approaching:{ icon: '⚡', label: 'Pre-clearing Signals', bg: '#FFFBEB', border: '#FDE68A', text: '#D97706' },
    upcoming:   { icon: '📍', label: 'Queued', bg: '#F8FAFC', border: '#E2E8F0', text: '#64748B' },
  };

  return (
    <div>
      <div className="text-xs font-bold mb-2" style={{ color: '#0F172A' }}>Route Signal Override Status</div>
      <div className="grid grid-cols-3 gap-2">
        {corridorStatuses.map(cs => {
          const j = junctions.find(x => x.id === cs.junctionId);
          if (!j) return null;
          const cfg = config[cs.status];
          return (
            <div key={cs.junctionId} className="rounded-lg p-2.5 text-center border"
              style={{ background: cfg.bg, borderColor: cfg.border }}>
              <div className="text-lg mb-0.5">{cfg.icon}</div>
              <div className="text-xs font-bold mb-0.5" style={{ color: cfg.text }}>
                {j.name.replace(' Junction','')}
              </div>
              <div className="text-xs leading-tight" style={{ color: cfg.text, fontSize: 10 }}>
                {cfg.label}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Active Vehicle Card ──────────────────────────────────────────────────────

function ActiveVehicleCard({ vehicle, junctions, onDeactivate }: {
  vehicle: EmergencyVehicle;
  junctions: Junction[];
  onDeactivate: (id: string) => void;
}) {
  const gpsState = useGPSSimulation(vehicle, vehicle.corridorActive);
  const waypoints = useMemo(() => buildWaypoints(vehicle, junctions), [vehicle, junctions]);
  const corridorStatuses = useMemo(
    () => getCorridorStatuses(vehicle, gpsState.progress, waypoints),
    [vehicle, gpsState.progress, waypoints],
  );

  // ETA: never increases
  const initialEta = useRef(vehicle.eta);
  const eta = Math.max(0, Math.round(initialEta.current * (1 - gpsState.progress)));

  return (
    <div className="bg-white rounded-2xl border overflow-hidden"
      style={{ borderColor: '#E2E8F0', borderTopColor: EMG_COLOR[vehicle.type], borderTopWidth: 4 }}>
      {/* Vehicle header */}
      <div className="flex items-start gap-4 p-5">
        <div className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl flex-shrink-0"
          style={{ background: EMG_BG[vehicle.type] }}>
          {EMG_ICON[vehicle.type]}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className="mono font-bold" style={{ color: '#0F172A' }}>{vehicle.vehicleNo}</span>
            <span className="text-xs font-semibold px-2 py-0.5 rounded"
              style={{ background: EMG_BG[vehicle.type], color: EMG_COLOR[vehicle.type] }}>
              {EMG_LABEL[vehicle.type]}
            </span>
            {vehicle.corridorActive && (
              <span className="text-xs font-bold px-2 py-0.5 rounded blink-fast"
                style={{ background: '#16A34A', color: 'white' }}>CORRIDOR ACTIVE</span>
            )}
          </div>
          <div className="grid grid-cols-3 gap-x-4 text-xs mt-2">
            <div><span style={{ color: '#94A3B8' }}>From: </span><strong className="truncate block">{vehicle.origin}</strong></div>
            <div><span style={{ color: '#94A3B8' }}>To: </span><strong className="truncate block">{vehicle.destination}</strong></div>
            <div>
              <span style={{ color: '#94A3B8' }}>ETA: </span>
              <strong style={{ color: eta <= 3 ? '#DC2626' : eta <= 7 ? '#D97706' : '#16A34A' }}>
                {eta} min
              </strong>
            </div>
          </div>
        </div>
        <button onClick={() => onDeactivate(vehicle.id)}
          className="flex-shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold border"
          style={{ borderColor: '#E2E8F0', color: '#64748B' }}>
          Mark Arrived
        </button>
      </div>

      {/* GPS Telemetry */}
      <div className="px-5 pb-3">
        <GPSStatusPanel gpsState={gpsState} vehicle={vehicle} junctions={junctions} />
      </div>

      {/* Route map */}
      <div className="px-5 pb-4">
        <EmergencyRouteMap
          vehicle={vehicle}
          junctions={junctions}
          gpsState={gpsState}
          corridorStatuses={corridorStatuses}
          eta={eta}
        />
      </div>

      {/* Signal override cards */}
      <div className="px-5 pb-5">
        <SignalOverrideList corridorStatuses={corridorStatuses} junctions={junctions} />
      </div>

      {/* Override info banner */}
      <div className="mx-5 mb-5 rounded-xl p-4 border-l-4"
        style={{ background: '#EFF6FF', borderColor: '#1D4ED8' }}>
        <div className="text-xs font-bold mb-1" style={{ color: '#1D4ED8' }}>System Override Active</div>
        <div className="text-xs" style={{ color: '#1E40AF' }}>
          Emergency priority active: route signals are coordinated GREEN, while conflicting approaches are held RED. Normal adaptive control resumes after the emergency vehicle clears each junction.
          Normal adaptive AI resumes automatically as vehicle clears each junction.
        </div>
      </div>
    </div>
  );
}

// ─── Add Vehicle Form ─────────────────────────────────────────────────────────

function AddVehicleForm({ onAdd }: { onAdd: (v: EmergencyVehicle) => void }) {
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ type: 'ambulance', vehicleNo: '', origin: '', destination: '' });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const j1 = JUNCTIONS[0];
    const j2 = JUNCTIONS[1];
    const j3 = JUNCTIONS[3];
    onAdd({
      id: `EMG-${Date.now()}`,
      type: form.type as EmergencyVehicle['type'],
      vehicleNo: form.vehicleNo,
      origin: form.origin,
      destination: form.destination,
      currentJunction: j1.id,
      routeJunctions: [j1.id, j2.id, j3.id],
      status: 'active',
      corridorActive: true,
      eta: Math.floor(Math.random() * 12) + 6,
    });
    setShow(false);
    setForm({ type: 'ambulance', vehicleNo: '', origin: '', destination: '' });
  };

  if (!show) {
    return (
      <button onClick={() => setShow(true)}
        className="w-full py-3 rounded-xl font-bold text-white flex items-center justify-center gap-2"
        style={{ background: '#DC2626' }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10"/><path d="M12 8v8M8 12h8"/>
        </svg>
        Register Emergency Vehicle
      </button>
    );
  }

  return (
    <div className="bg-white rounded-xl border p-5" style={{ borderColor: '#E2E8F0' }}>
      <h3 className="text-sm font-bold mb-4" style={{ color: '#0F172A' }}>Register Emergency Vehicle</h3>
      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-semibold mb-1" style={{ color: '#475569' }}>Type</label>
            <select value={form.type} onChange={e => setForm(f => ({ ...f, type: e.target.value }))}
              className="w-full px-3 py-2 rounded-lg border text-sm outline-none"
              style={{ borderColor: '#E2E8F0', background: 'white' }}>
              <option value="ambulance">Ambulance</option>
              <option value="fire_brigade">Fire Brigade</option>
              <option value="police">Police Vehicle</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold mb-1" style={{ color: '#475569' }}>Vehicle Number</label>
            <input type="text" value={form.vehicleNo} onChange={e => setForm(f => ({ ...f, vehicleNo: e.target.value }))}
              placeholder="MH-12-AMB-1042"
              className="w-full px-3 py-2 rounded-lg border text-sm mono outline-none"
              style={{ borderColor: '#E2E8F0' }} required/>
          </div>
          <div>
            <label className="block text-xs font-semibold mb-1" style={{ color: '#475569' }}>Origin</label>
            <input type="text" value={form.origin} onChange={e => setForm(f => ({ ...f, origin: e.target.value }))}
              placeholder="Incident location"
              className="w-full px-3 py-2 rounded-lg border text-sm outline-none"
              style={{ borderColor: '#E2E8F0' }} required/>
          </div>
          <div>
            <label className="block text-xs font-semibold mb-1" style={{ color: '#475569' }}>Destination</label>
            <input type="text" value={form.destination} onChange={e => setForm(f => ({ ...f, destination: e.target.value }))}
              placeholder="Hospital / Station"
              className="w-full px-3 py-2 rounded-lg border text-sm outline-none"
              style={{ borderColor: '#E2E8F0' }} required/>
          </div>
        </div>
        <div className="flex gap-2">
          <button type="submit" className="flex-1 py-2.5 rounded-lg text-sm font-bold text-white"
            style={{ background: '#DC2626' }}>
            Activate Green Corridor
          </button>
          <button type="button" onClick={() => setShow(false)}
            className="px-4 py-2.5 rounded-lg text-sm border"
            style={{ borderColor: '#E2E8F0', color: '#64748B' }}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}

// ─── Emergency Main ───────────────────────────────────────────────────────────

export default function Emergency() {
  const [vehicles, setVehicles] = useState(EMERGENCY_VEHICLES);

  const handleAdd = (v: EmergencyVehicle) => setVehicles(prev => [v, ...prev]);

  const handleDeactivate = (id: string) => {
    setVehicles(prev => prev.map(v =>
      v.id === id ? { ...v, corridorActive: false, status: 'arrived' as const } : v
    ));
  };

  const activeVehicles    = vehicles.filter(v => v.corridorActive);
  const completedVehicles = vehicles.filter(v => !v.corridorActive);
  const signalsOverridden = activeVehicles.reduce((s, v) => s + v.routeJunctions.length * 4, 0);
  const avgEta            = activeVehicles.length > 0
    ? Math.round(activeVehicles.reduce((s, v) => s + v.eta, 0) / activeVehicles.length)
    : 0;

  return (
    <div className="h-full flex flex-col overflow-hidden" style={{ background: '#F8FAFC' }}>
      {/* Header */}
      <div className="bg-white border-b px-6 py-4" style={{ borderColor: '#E2E8F0' }}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <h1 className="text-xl font-bold" style={{ color: '#0F172A' }}>Emergency Management</h1>
              {activeVehicles.length > 0 && (
                <span className="text-xs font-bold px-2 py-0.5 rounded blink-fast"
                  style={{ background: '#DC2626', color: 'white' }}>
                  {activeVehicles.length} ACTIVE
                </span>
              )}
            </div>
            <p className="text-sm" style={{ color: '#64748B' }}>
              Green Corridor Management · GPS Tracking · Signal Override
            </p>
          </div>
        </div>

        {/* Stat cards */}
        <div className="grid grid-cols-4 gap-3">
          {[
            { label: 'Active Corridors',   value: activeVehicles.length,              color: '#DC2626', bg: '#FEF2F2' },
            { label: 'Signals Overridden', value: signalsOverridden,                   color: '#D97706', bg: '#FFFBEB' },
            { label: 'Avg ETA',            value: activeVehicles.length > 0 ? `${avgEta} min` : '—', color: '#1D4ED8', bg: '#EFF6FF' },
            { label: 'Missions Today',     value: vehicles.length,                     color: '#16A34A', bg: '#F0FDF4' },
          ].map(s => (
            <div key={s.label} className="rounded-xl p-3 text-center border"
              style={{ background: s.bg, borderColor: s.color+'30' }}>
              <div className="text-2xl font-bold" style={{ color: s.color }}>{s.value}</div>
              <div className="text-xs mt-0.5" style={{ color: '#64748B' }}>{s.label}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-5">
        {/* Register form */}
        <AddVehicleForm onAdd={handleAdd} />

        {/* Active corridors */}
        {activeVehicles.length > 0 && (
          <div>
            <h2 className="text-sm font-bold mb-3" style={{ color: '#0F172A' }}>Active Green Corridors</h2>
            <div className="space-y-5">
              {activeVehicles.map(vehicle => (
                <ActiveVehicleCard
                  key={vehicle.id}
                  vehicle={vehicle}
                  junctions={JUNCTIONS}
                  onDeactivate={handleDeactivate}
                />
              ))}
            </div>
          </div>
        )}

        {/* Completed missions */}
        {completedVehicles.length > 0 && (
          <div>
            <h2 className="text-sm font-bold mb-3" style={{ color: '#94A3B8' }}>Completed Missions</h2>
            <div className="space-y-2">
              {completedVehicles.map(v => (
                <div key={v.id} className="flex items-center gap-3 bg-white rounded-xl p-4 border"
                  style={{ borderColor: '#E2E8F0' }}>
                  <div className="text-xl">{EMG_ICON[v.type]}</div>
                  <div className="flex-1 min-w-0">
                    <div className="mono text-sm font-semibold" style={{ color: '#64748B' }}>{v.vehicleNo}</div>
                    <div className="text-xs truncate" style={{ color: '#94A3B8' }}>
                      {v.origin} → {v.destination}
                    </div>
                  </div>
                  <span className="flex-shrink-0 text-xs font-semibold px-2 py-0.5 rounded"
                    style={{ background: '#F0FDF4', color: '#16A34A' }}>Arrived ✓</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* How it works */}
        <div className="bg-white rounded-xl border p-5" style={{ borderColor: '#E2E8F0' }}>
          <h3 className="text-sm font-bold mb-3" style={{ color: '#0F172A' }}>How Green Corridor Works</h3>
          <div className="grid grid-cols-4 gap-3">
            {[
              { icon: '📡', title: 'Detection', desc: 'Emergency vehicle detected via CCTV or operator input' },
              { icon: '🗺️', title: 'Route Calc.', desc: 'AI selects the fastest feasible route through monitored junctions' },
              { icon: '🟢', title: 'Progressive Clear', desc: 'Signals are pre-cleared ahead of the emergency vehicle' },
              { icon: '✅', title: 'Auto-Restore', desc: 'Normal adaptive signal control resumes after the vehicle passes' },
            ].map(s => (
              <div key={s.title} className="text-center">
                <div className="w-10 h-10 rounded-full mx-auto mb-2 flex items-center justify-center text-xl"
                  style={{ background: '#EFF6FF' }}>{s.icon}</div>
                <div className="text-xs font-bold mb-1" style={{ color: '#0F172A' }}>{s.title}</div>
                <div className="text-xs" style={{ color: '#64748B' }}>{s.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
