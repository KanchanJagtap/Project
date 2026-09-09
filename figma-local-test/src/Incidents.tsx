import { useState } from 'react';
import { INCIDENTS, incidentLabel, type Incident, type IncidentType } from './data';

const severityConfig = {
  critical: { bg: '#FEF2F2', border: '#DC2626', text: '#DC2626', label: 'CRITICAL' },
  high: { bg: '#FFF7ED', border: '#EA580C', text: '#EA580C', label: 'HIGH' },
  medium: { bg: '#FFFBEB', border: '#D97706', text: '#D97706', label: 'MEDIUM' },
  low: { bg: '#F0FDF4', border: '#16A34A', text: '#16A34A', label: 'LOW' },
};

const typeIcon: Record<IncidentType, string> = {
  accident: '💥', collision: '🚗💨', breakdown: '🔧', road_blockage: '🚧',
  fallen_object: '🪵', fire_smoke: '🔥', abnormal_slowdown: '⚠️',
};

function IncidentCard({ incident, onAction }: {
  incident: Incident;
  onAction: (id: string, action: 'police' | 'emergency') => void;
}) {
  const sev = severityConfig[incident.severity];
  const [expanded, setExpanded] = useState(incident.severity === 'critical');

  const minutesAgo = Math.round((Date.now() - incident.timestamp.getTime()) / 60000);

  return (
    <div className="rounded-xl border overflow-hidden"
      style={{ borderColor: sev.border, borderLeftWidth: 4, background: sev.bg }}>
      <div className="p-4">
        <div className="flex items-start gap-3">
          {/* Icon */}
          <div className="w-10 h-10 rounded-lg flex items-center justify-center text-xl flex-shrink-0"
            style={{ background: 'rgba(255,255,255,0.7)' }}>
            {typeIcon[incident.type]}
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-bold px-2 py-0.5 rounded"
                    style={{ background: sev.border, color: 'white' }}>
                    {sev.label}
                  </span>
                  <span className="mono text-xs" style={{ color: '#64748B' }}>{incident.id}</span>
                  {incident.status === 'active' && (
                    <span className="text-xs font-bold px-2 py-0.5 rounded blink-fast"
                      style={{ background: '#DC2626', color: 'white' }}>ACTIVE</span>
                  )}
                </div>
                <h3 className="text-sm font-bold" style={{ color: '#0F172A' }}>
                  {incidentLabel[incident.type]}
                </h3>
                <div className="text-xs mt-0.5" style={{ color: '#475569' }}>
                  {incident.location}
                </div>
              </div>
              <div className="text-right flex-shrink-0">
                <div className="mono text-xs font-bold" style={{ color: sev.text }}>
                  {incident.confidence}% confidence
                </div>
                <div className="text-xs mt-0.5" style={{ color: '#94A3B8' }}>
                  {minutesAgo}m ago
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3 mt-2 text-xs" style={{ color: '#64748B' }}>
              <span>Camera: <strong className="mono">{incident.cameraId}</strong></span>
              <span>Junction: <strong>{incident.junctionName}</strong></span>
            </div>
          </div>
        </div>

        {expanded && (
          <div className="mt-3 pl-13">
            {/* Evidence description */}
            <div className="rounded-lg p-3 mb-3" style={{ background: '#0F172A' }}>
              <div className="flex items-center gap-2 mb-2">
                <div className="w-2 h-2 rounded-full bg-red-500 blink-fast"/>
                <span className="text-xs mono" style={{ color: '#64748B' }}>
                  {incident.cameraId} · EVIDENCE FRAME · {incident.timestamp.toLocaleTimeString('en-IN')}
                </span>
              </div>
              <div className="border border-dashed rounded p-2 text-center"
                style={{ borderColor: sev.border }}>
                <div className="text-2xl mb-1">{typeIcon[incident.type]}</div>
                <div className="text-xs" style={{ color: '#94A3B8' }}>{incident.description}</div>
              </div>
            </div>

            <p className="text-xs mb-3" style={{ color: '#475569' }}>{incident.description}</p>

            {/* Status */}
            <div className="flex items-center gap-2 mb-3">
              <span className="text-xs" style={{ color: '#64748B' }}>Status:</span>
              <span className="text-xs font-semibold capitalize px-2 py-0.5 rounded"
                style={{ background: 'rgba(255,255,255,0.7)', color: sev.text }}>
                {incident.status.replace(/_/g, ' ')}
              </span>
            </div>

            {/* Actions */}
            <div className="flex gap-2">
              <button
                onClick={() => onAction(incident.id, 'police')}
                disabled={incident.status !== 'active'}
                className="flex-1 py-2 rounded-lg text-xs font-bold text-white transition-all"
                style={{ background: incident.status === 'active' ? '#1D4ED8' : '#94A3B8' }}>
                {incident.status === 'active' ? '🚔 Alert Police' : '✓ Police Alerted'}
              </button>
              <button
                onClick={() => onAction(incident.id, 'emergency')}
                disabled={incident.status === 'emergency_notified'}
                className="flex-1 py-2 rounded-lg text-xs font-bold text-white transition-all"
                style={{ background: incident.status === 'emergency_notified' ? '#94A3B8' : '#DC2626' }}>
                {incident.status === 'emergency_notified' ? '✓ Emergency Notified' : '🚨 Notify Emergency'}
              </button>
            </div>
          </div>
        )}

        <button onClick={() => setExpanded(e => !e)}
          className="mt-2 w-full text-center text-xs py-1"
          style={{ color: sev.text }}>
          {expanded ? '▲ Collapse' : '▼ Expand Details'}
        </button>
      </div>
    </div>
  );
}

export default function Incidents() {
  const [incidents, setIncidents] = useState(INCIDENTS);
  const [filter, setFilter] = useState<'all' | 'active' | 'critical'>('all');

  const handleAction = (id: string, action: 'police' | 'emergency') => {
    setIncidents(prev => prev.map(inc =>
      inc.id === id ? {
        ...inc,
        status: action === 'police'
          ? (inc.status === 'active' ? 'police_notified' : inc.status)
          : 'emergency_notified'
      } : inc
    ));
  };

  const filtered = incidents.filter(inc => {
    if (filter === 'active') return inc.status === 'active';
    if (filter === 'critical') return inc.severity === 'critical' || inc.severity === 'high';
    return true;
  });

  const activeCount = incidents.filter(i => i.status === 'active').length;
  const criticalCount = incidents.filter(i => i.severity === 'critical').length;

  return (
    <div className="h-full flex flex-col overflow-hidden" style={{ background: '#F8FAFC' }}>
      <div className="bg-white border-b px-6 py-4" style={{ borderColor: '#E2E8F0' }}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-xl font-bold" style={{ color: '#0F172A' }}>Incident Detection</h1>
            <p className="text-sm mt-0.5" style={{ color: '#64748B' }}>AI-monitored traffic incidents · Auto-detection</p>
          </div>
          {activeCount > 0 && (
            <div className="flex items-center gap-2 px-4 py-2 rounded-xl"
              style={{ background: '#FEF2F2', border: '1px solid #FECACA' }}>
              <div className="w-2 h-2 rounded-full bg-red-500 blink-fast"/>
              <span className="text-sm font-bold" style={{ color: '#DC2626' }}>{activeCount} Active Incidents</span>
            </div>
          )}
        </div>

        {/* Stats */}
        <div className="grid grid-cols-4 gap-3 mb-4">
          {[
            { label: 'Total Incidents', value: incidents.length, color: '#0F172A' },
            { label: 'Active', value: activeCount, color: '#DC2626' },
            { label: 'Critical', value: criticalCount, color: '#EA580C' },
            { label: 'Resolved', value: incidents.filter(i => i.status === 'resolved').length, color: '#16A34A' },
          ].map(s => (
            <div key={s.label} className="rounded-xl p-3 text-center border" style={{ borderColor: '#E2E8F0' }}>
              <div className="text-2xl font-bold" style={{ color: s.color }}>{s.value}</div>
              <div className="text-xs mt-0.5" style={{ color: '#64748B' }}>{s.label}</div>
            </div>
          ))}
        </div>

        {/* Filters */}
        <div className="flex gap-2">
          {(['all', 'active', 'critical'] as const).map(f => (
            <button key={f} onClick={() => setFilter(f)}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold capitalize"
              style={{
                background: filter === f ? '#1D4ED8' : '#F1F5F9',
                color: filter === f ? 'white' : '#64748B',
              }}>
              {f === 'all' ? 'All Incidents' : f === 'active' ? 'Active Only' : 'Critical & High'}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="space-y-4">
          {filtered.map(inc => (
            <IncidentCard key={inc.id} incident={inc} onAction={handleAction} />
          ))}
          {filtered.length === 0 && (
            <div className="rounded-xl p-10 text-center bg-white border" style={{ borderColor: '#E2E8F0' }}>
              <div className="text-4xl mb-3">✅</div>
              <div className="font-bold" style={{ color: '#0F172A' }}>No incidents matching filter</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
