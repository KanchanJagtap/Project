import { useState, useEffect } from 'react';
import { JUNCTIONS, type Junction, type SignalArm } from './data';

const sigColor = { red: '#DC2626', yellow: '#D97706', green: '#16A34A' };
const sigBg = { red: '#FEF2F2', yellow: '#FFFBEB', green: '#F0FDF4' };

function SignalLight({ color, active }: { color: 'red' | 'yellow' | 'green'; active: boolean }) {
  return (
    <div className="w-7 h-7 rounded-full flex items-center justify-center"
      style={{ background: active ? sigColor[color] : '#374151' }}>
      {active && (
        <div className="w-3.5 h-3.5 rounded-full opacity-60" style={{ background: 'rgba(255,255,255,0.4)' }}/>
      )}
    </div>
  );
}

function SignalHead({ color }: { color: 'red' | 'yellow' | 'green' }) {
  return (
    <div className="flex flex-col gap-1 bg-gray-900 rounded-lg p-2 items-center w-12">
      <SignalLight color="red" active={color === 'red'} />
      <SignalLight color="yellow" active={color === 'yellow'} />
      <SignalLight color="green" active={color === 'green'} />
    </div>
  );
}

const AI_REASONS: Record<string, string> = {
  north: 'High queue + slow speed → extending green by 12s',
  south: 'Low density + high speed → reducing green by 8s',
  east: 'Large vehicle blockage → extending red for safety clearance',
  west: 'Moderate flow → maintaining standard cycle',
};

function JunctionSignalCard({
  junction, onModeChange,
}: {
  junction: Junction;
  onModeChange: (id: string, mode: 'fixed' | 'adaptive') => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const arms = (['north', 'south', 'east', 'west'] as const);
  const isCritical = junction.congestionLevel === 'critical';
  const isHigh = junction.congestionLevel === 'high';

  return (
    <div className="bg-white rounded-xl border overflow-hidden" style={{
      borderColor: isCritical ? '#DC2626' : isHigh ? '#EA580C' : '#E2E8F0',
      borderLeftWidth: (isCritical || isHigh) ? 4 : 1,
    }}>
      {/* Header */}
      <div className="p-4">
        <div className="flex items-start justify-between mb-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold px-2 py-0.5 rounded" style={{ background: '#EFF6FF', color: '#1D4ED8' }}>
                {junction.id}
              </span>
              {isCritical && (
                <span className="text-xs font-bold px-2 py-0.5 rounded blink-fast"
                  style={{ background: '#DC2626', color: 'white' }}>CRITICAL</span>
              )}
            </div>
            <h3 className="text-sm font-bold mt-1" style={{ color: '#0F172A' }}>{junction.name}</h3>
            <div className="text-xs mt-0.5" style={{ color: '#94A3B8' }}>
              {junction.totalVehicles} vehicles · {junction.cameras.length} cameras
            </div>
          </div>

          {/* Mode toggle */}
          <div className="flex items-center gap-1 p-1 rounded-lg" style={{ background: '#F1F5F9' }}>
            {(['fixed', 'adaptive'] as const).map(m => (
              <button key={m} onClick={() => onModeChange(junction.id, m)}
                className="px-2.5 py-1 rounded text-xs font-semibold capitalize transition-all"
                style={{
                  background: junction.mode === m ? (m === 'adaptive' ? '#1D4ED8' : '#475569') : 'transparent',
                  color: junction.mode === m ? 'white' : '#94A3B8',
                }}>
                {m === 'adaptive' ? 'AI Adaptive' : 'Fixed'}
              </button>
            ))}
          </div>
        </div>

        {/* Signal display - compact 4-arm view */}
        <div className="grid grid-cols-4 gap-2">
          {arms.map(arm => {
            const sig = junction.signals[arm];
            return (
              <div key={arm} className="rounded-lg p-2 text-center"
                style={{ background: sigBg[sig.color] }}>
                <div className="text-xs font-semibold mb-1.5 uppercase" style={{ color: sigColor[sig.color] }}>
                  {arm.charAt(0)}
                </div>
                <div className="flex flex-col gap-0.5 items-center mb-1.5">
                  {(['red', 'yellow', 'green'] as const).map(c => (
                    <div key={c} className="w-4 h-4 rounded-full"
                      style={{ background: sig.color === c ? sigColor[c] : '#E2E8F0' }}/>
                  ))}
                </div>
                <div className="mono text-sm font-bold" style={{ color: sigColor[sig.color] }}>
                  {sig.timer}s
                </div>
                <div className="text-xs mt-0.5" style={{ color: '#94A3B8' }}>{sig.vehicleDensity}%</div>
              </div>
            );
          })}
        </div>

        {/* AI reason if adaptive */}
        {junction.mode === 'adaptive' && junction.aiReason && (
          <div className="mt-3 rounded-lg p-2.5 text-xs flex items-start gap-2"
            style={{ background: '#EFF6FF', border: '1px solid #BFDBFE' }}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="#1D4ED8" className="flex-shrink-0 mt-0.5">
              <circle cx="12" cy="12" r="10"/>
              <path d="M12 8v4M12 16h.01" stroke="white" strokeWidth="2" strokeLinecap="round"/>
            </svg>
            <span style={{ color: '#1E40AF' }}>{junction.aiReason}</span>
          </div>
        )}

        <button onClick={() => setExpanded(e => !e)}
          className="mt-3 w-full text-xs font-semibold text-center py-1.5 rounded-lg transition-all"
          style={{ background: '#F8FAFC', color: '#64748B' }}>
          {expanded ? '▲ Collapse' : '▼ Detailed View'}
        </button>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t px-4 pb-4 pt-3" style={{ borderColor: '#E2E8F0' }}>
          <div className="grid grid-cols-2 gap-3">
            {arms.map(arm => {
              const sig = junction.signals[arm];
              return (
                <div key={arm} className="rounded-xl p-3 border" style={{ borderColor: '#E2E8F0' }}>
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-3 h-3 rounded-full" style={{ background: sigColor[sig.color] }}/>
                    <span className="text-xs font-bold uppercase" style={{ color: '#0F172A' }}>{arm} Arm</span>
                    <span className="ml-auto text-xs mono" style={{ color: sigColor[sig.color] }}>
                      {sig.color.toUpperCase()} {sig.timer}s
                    </span>
                  </div>

                  {/* Metrics grid */}
                  <div className="grid grid-cols-2 gap-2 text-xs mb-3">
                    {[
                      { label: 'Lane Density', value: `${sig.vehicleDensity}%`, warn: sig.vehicleDensity > 80 },
                      { label: 'Queue Length', value: `${sig.queueLength} veh`, warn: sig.queueLength > 15 },
                      { label: 'Avg Speed', value: `${sig.avgSpeed} km/h`, warn: sig.avgSpeed < 20 },
                      { label: 'Wait Time', value: `${sig.waitingTime}s`, warn: sig.waitingTime > 60 },
                      { label: 'Occupancy', value: `${sig.occupancy}%`, warn: sig.occupancy > 85 },
                      { label: 'Green Dur.', value: `${sig.greenDuration}s`, warn: false },
                    ].map(m => (
                      <div key={m.label}>
                        <div style={{ color: '#94A3B8' }}>{m.label}</div>
                        <div className="font-bold mono" style={{ color: m.warn ? '#DC2626' : '#0F172A' }}>{m.value}</div>
                      </div>
                    ))}
                  </div>

                  {/* Density bar */}
                  <div>
                    <div className="flex justify-between text-xs mb-1" style={{ color: '#94A3B8' }}>
                      <span>Lane Pressure</span>
                      <span className="font-bold" style={{
                        color: sig.vehicleDensity > 80 ? '#DC2626' : sig.vehicleDensity > 60 ? '#D97706' : '#16A34A'
                      }}>{sig.vehicleDensity}%</span>
                    </div>
                    <div className="h-2 rounded-full" style={{ background: '#E2E8F0' }}>
                      <div className="h-full rounded-full" style={{
                        width: `${sig.vehicleDensity}%`,
                        background: sig.vehicleDensity > 80 ? '#DC2626' : sig.vehicleDensity > 60 ? '#D97706' : '#16A34A',
                      }}/>
                    </div>
                  </div>

                  {/* AI analysis in adaptive mode */}
                  {junction.mode === 'adaptive' && (
                    <div className="mt-2 text-xs rounded p-2" style={{ background: '#EFF6FF', color: '#1E40AF' }}>
                      <strong>AI:</strong> {AI_REASONS[arm]}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Manual signal override */}
          <div className="mt-3 pt-3 border-t" style={{ borderColor: '#E2E8F0' }}>
            <div className="text-xs font-semibold mb-2" style={{ color: '#0F172A' }}>Manual Override</div>
            <div className="grid grid-cols-4 gap-2">
              {arms.map(arm => (
                <div key={arm} className="text-center">
                  <div className="text-xs mb-1.5" style={{ color: '#64748B' }}>{arm}</div>
                  <div className="flex gap-1 justify-center">
                    {(['red', 'green'] as const).map(c => (
                      <button key={c} className="text-xs px-1.5 py-1 rounded font-semibold border text-white"
                        style={{ background: sigColor[c], borderColor: sigColor[c] }}>
                        {c.charAt(0).toUpperCase()}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function Signals() {
  const [junctions, setJunctions] = useState(JUNCTIONS);
  const [filterMode, setFilterMode] = useState<'all' | 'adaptive' | 'fixed' | 'critical'>('all');
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      setTick(t => t + 1);
      setJunctions(prev => prev.map(j => {
        const nextSignals = { ...j.signals };
        const arms = ['north', 'south', 'east', 'west'] as const;
        arms.forEach(arm => {
          const sig = nextSignals[arm];
          const newTimer = Math.max(0, sig.timer - 1);
          let newColor = sig.color;
          if (newTimer === 0) {
            if (sig.color === 'green') newColor = 'yellow';
            else if (sig.color === 'yellow') newColor = 'red';
            else newColor = 'green';
          }
          nextSignals[arm] = { ...sig, timer: newTimer || (newColor === 'green' ? sig.greenDuration : newColor === 'yellow' ? sig.yellowDuration : sig.redDuration), color: newColor };
        });
        // AI adaptive adjustment
        if (j.mode === 'adaptive') {
          arms.forEach(arm => {
            const sig = nextSignals[arm];
            if (sig.vehicleDensity > 80 && sig.color === 'green' && sig.timer < 5) {
              nextSignals[arm] = { ...sig, timer: sig.timer + 8 }; // extend
            }
          });
        }
        return { ...j, signals: nextSignals };
      }));
    }, 1000);
    return () => clearInterval(id);
  }, []);

  const handleModeChange = (id: string, mode: 'fixed' | 'adaptive') => {
    setJunctions(prev => prev.map(j => j.id === id ? { ...j, mode } : j));
  };

  const filtered = junctions.filter(j => {
    if (filterMode === 'adaptive') return j.mode === 'adaptive';
    if (filterMode === 'fixed') return j.mode === 'fixed';
    if (filterMode === 'critical') return j.congestionLevel === 'critical' || j.congestionLevel === 'high';
    return true;
  });

  const adaptiveCount = junctions.filter(j => j.mode === 'adaptive').length;
  const criticalCount = junctions.filter(j => j.congestionLevel === 'critical').length;

  return (
    <div className="h-full flex flex-col overflow-hidden" style={{ background: '#F8FAFC' }}>
      {/* Header */}
      <div className="bg-white border-b px-6 py-4" style={{ borderColor: '#E2E8F0' }}>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold" style={{ color: '#0F172A' }}>Signal Control</h1>
            <p className="text-sm mt-0.5" style={{ color: '#64748B' }}>
              {adaptiveCount} AI Adaptive · {junctions.length - adaptiveCount} Fixed Timer · {criticalCount} Critical
            </p>
          </div>
          <div className="flex items-center gap-2">
            {(['all', 'adaptive', 'fixed', 'critical'] as const).map(f => (
              <button key={f} onClick={() => setFilterMode(f)}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold capitalize transition-all"
                style={{
                  background: filterMode === f ? '#1D4ED8' : '#F1F5F9',
                  color: filterMode === f ? 'white' : '#64748B',
                }}>
                {f === 'all' ? 'All Junctions' : f === 'adaptive' ? 'AI Adaptive' : f === 'fixed' ? 'Fixed Timer' : 'Critical Only'}
              </button>
            ))}
          </div>
        </div>

        {/* Summary row */}
        <div className="mt-4 grid grid-cols-4 gap-3">
          {[
            { label: 'Currently Green', value: junctions.filter(j => j.signals.north.color === 'green').length, color: '#16A34A' },
            { label: 'Currently Red', value: junctions.filter(j => j.signals.north.color === 'red').length, color: '#DC2626' },
            { label: 'AI Optimizing', value: adaptiveCount, color: '#1D4ED8' },
            { label: 'Avg Cycle Time', value: '92s', color: '#D97706' },
          ].map(s => (
            <div key={s.label} className="rounded-lg p-3 text-center" style={{ background: s.color + '10', border: `1px solid ${s.color}30` }}>
              <div className="text-2xl font-bold" style={{ color: s.color }}>{s.value}</div>
              <div className="text-xs mt-0.5" style={{ color: '#64748B' }}>{s.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Signal cards grid */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="grid grid-cols-2 gap-4">
          {filtered.map(j => (
            <JunctionSignalCard key={j.id} junction={j} onModeChange={handleModeChange} />
          ))}
        </div>
      </div>
    </div>
  );
}
