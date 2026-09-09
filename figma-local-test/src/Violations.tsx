import { useState } from 'react';
import { VIOLATIONS, FINE_RULES, violationLabel, type Violation, type ViolationType } from './data';

const statusColor = {
  pending: { bg: '#FEF2F2', text: '#DC2626' },
  processing: { bg: '#FFFBEB', text: '#D97706' },
  challan_issued: { bg: '#EFF6FF', text: '#1D4ED8' },
  paid: { bg: '#F0FDF4', text: '#16A34A' },
};

const typeColor: Record<ViolationType, string> = {
  red_light_jump: '#DC2626', speeding: '#EA580C', wrong_way: '#7C3AED',
  no_helmet: '#D97706', triple_riding: '#D97706', stop_line: '#DC2626',
  no_parking: '#64748B', wrong_lane: '#D97706', invalid_plate: '#7C3AED',
  restricted_zone: '#0891B2',
};

function ViolationDetailModal({ violation, onClose, onProcess }: {
  violation: Violation;
  onClose: () => void;
  onProcess: (id: string) => void;
}) {
  const rule = FINE_RULES[violation.type];
  const [sent, setSent] = useState(false);

  const handleIssue = () => {
    onProcess(violation.id);
    setSent(true);
    setTimeout(() => { onClose(); }, 1500);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6"
      style={{ background: 'rgba(15,23,42,0.75)' }}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden">
        {/* Header */}
        <div className="flex items-start justify-between p-6 border-b" style={{ borderColor: '#E2E8F0', background: '#FEF2F2' }}>
          <div>
            <span className="text-xs font-bold px-2 py-0.5 rounded mb-2 inline-block mono"
              style={{ background: '#DC2626', color: 'white' }}>
              {violation.id}
            </span>
            <h2 className="text-xl font-bold" style={{ color: '#0F172A' }}>
              {violationLabel[violation.type]}
            </h2>
            <div className="mono text-lg font-bold mt-1" style={{ color: '#DC2626' }}>
              {violation.plate}
            </div>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>

        <div className="p-6 space-y-5">
          {/* Evidence panel */}
          <div className="rounded-xl overflow-hidden relative" style={{ background: '#0F172A', height: 140 }}>
            {/* Simulated CCTV evidence frame */}
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <div className="text-slate-600 text-xs mb-2 mono">EVIDENCE FRAME · {violation.cameraId}</div>
                <div className="border-2 border-dashed border-blue-500 px-8 py-4 rounded-lg"
                  style={{ background: 'rgba(59,130,246,0.08)' }}>
                  <div className="text-blue-400 font-bold mono text-sm">{violation.plate}</div>
                  <div className="text-slate-400 text-xs mt-1">{violation.evidenceDesc}</div>
                </div>
              </div>
            </div>
            <div className="absolute top-2 left-2 text-xs mono" style={{ color: '#64748B' }}>
              REC ● {violation.cameraId}
            </div>
            <div className="absolute top-2 right-2 text-xs mono" style={{ color: '#64748B' }}>
              {violation.timestamp.toLocaleString('en-IN')}
            </div>
            <div className="absolute bottom-2 left-2 right-2 flex justify-between text-xs">
              <span style={{ color: '#10B981' }}>ANPR DETECTED · CONF: {violation.confidence}%</span>
              <span style={{ color: '#F59E0B' }}>LOCKED</span>
            </div>
          </div>

          {/* Violation details */}
          <div className="grid grid-cols-2 gap-3 text-sm">
            {[
              { label: 'Camera', value: violation.cameraId },
              { label: 'Junction', value: violation.junctionName },
              { label: 'Time', value: violation.timestamp.toLocaleTimeString('en-IN') },
              { label: 'Vehicle Type', value: violation.vehicleType.toUpperCase() },
              { label: 'Confidence', value: `${violation.confidence}%` },
              { label: 'Speed', value: violation.speed ? `${violation.speed} km/h` : 'N/A' },
            ].map(d => (
              <div key={d.label} className="rounded-lg p-3" style={{ background: '#F8FAFC' }}>
                <div className="text-xs" style={{ color: '#94A3B8' }}>{d.label}</div>
                <div className="font-semibold mono mt-0.5" style={{ color: '#0F172A' }}>{d.value}</div>
              </div>
            ))}
          </div>

          {/* Legal rule */}
          <div className="rounded-xl p-4 border-l-4" style={{ background: '#FFFBEB', borderColor: '#D97706' }}>
            <div className="text-xs font-bold mb-1" style={{ color: '#D97706' }}>Applicable Provision</div>
            <div className="text-sm font-semibold" style={{ color: '#0F172A' }}>{rule.description}</div>
            <div className="flex items-center gap-4 mt-2 text-xs">
              <span>Fine: <strong style={{ color: '#DC2626' }}>₹{rule.fine.toLocaleString()}</strong></span>
              <span>Penalty Points: <strong>{rule.points}</strong></span>
            </div>
          </div>

          {/* Actions */}
          {!sent ? (
            <div className="flex gap-3">
              <button onClick={handleIssue}
                className="flex-1 py-3 rounded-xl font-bold text-white text-sm"
                style={{ background: '#DC2626' }}>
                Generate Demo E-Challan (₹{violation.fine.toLocaleString()})
              </button>
              <button onClick={onClose}
                className="flex-1 py-3 rounded-xl font-semibold text-sm border"
                style={{ borderColor: '#E2E8F0', color: '#475569' }}>
                Mark for Review
              </button>
            </div>
          ) : (
            <div className="py-4 rounded-xl text-center font-bold text-green-700"
              style={{ background: '#F0FDF4' }}>
              ✓ Demo e-Challan generated · Prototype notification queued
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function Violations() {
  const [violations, setViolations] = useState(VIOLATIONS);
  const [selected, setSelected] = useState<Violation | null>(null);
  const [typeFilter, setTypeFilter] = useState<ViolationType | 'all'>('all');
  const [statusFilter, setStatusFilter] = useState<Violation['status'] | 'all'>('all');
  const [search, setSearch] = useState('');

  const handleProcess = (id: string) => {
    setViolations(prev => prev.map(v =>
      v.id === id ? { ...v, status: 'challan_issued' } : v
    ));
  };

  const filtered = violations.filter(v => {
    if (typeFilter !== 'all' && v.type !== typeFilter) return false;
    if (statusFilter !== 'all' && v.status !== statusFilter) return false;
    if (search && !v.plate.toLowerCase().includes(search.toLowerCase()) &&
        !v.junctionName.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const stats = {
    total: violations.length,
    pending: violations.filter(v => v.status === 'pending').length,
    challan: violations.filter(v => v.status === 'challan_issued').length,
    revenue: violations.filter(v => v.status === 'challan_issued' || v.status === 'paid').reduce((s, v) => s + v.fine, 0),
  };

  return (
    <div className="h-full flex flex-col overflow-hidden" style={{ background: '#F8FAFC' }}>
      {/* Header */}
      <div className="bg-white border-b px-6 py-4" style={{ borderColor: '#E2E8F0' }}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-xl font-bold" style={{ color: '#0F172A' }}>Violations & ANPR</h1>
            <p className="text-sm mt-0.5" style={{ color: '#64748B' }}>AI-detected traffic violations · Auto-ANPR</p>
          </div>
          <button className="px-4 py-2 rounded-lg text-sm font-semibold text-white"
            style={{ background: '#1D4ED8' }}>
            Export Report
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-4 gap-3 mb-4">
          {[
            { label: 'Total Today', value: stats.total, color: '#0F172A' },
            { label: 'Pending', value: stats.pending, color: '#DC2626' },
            { label: 'Challans Issued', value: stats.challan, color: '#1D4ED8' },
            { label: 'Revenue', value: `₹${(stats.revenue / 1000).toFixed(1)}K`, color: '#16A34A' },
          ].map(s => (
            <div key={s.label} className="rounded-xl p-3 text-center" style={{ background: '#F8FAFC', border: '1px solid #E2E8F0' }}>
              <div className="text-2xl font-bold" style={{ color: s.color }}>{s.value}</div>
              <div className="text-xs mt-0.5" style={{ color: '#64748B' }}>{s.label}</div>
            </div>
          ))}
        </div>

        {/* Filters */}
        <div className="flex items-center gap-3">
          <input
            type="text" value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search plate or junction..."
            className="flex-1 px-3 py-2 rounded-lg border text-sm outline-none"
            style={{ borderColor: '#E2E8F0' }}
          />
          <select value={statusFilter} onChange={e => setStatusFilter(e.target.value as Violation['status'] | 'all')}
            className="px-3 py-2 rounded-lg border text-sm outline-none"
            style={{ borderColor: '#E2E8F0', background: 'white' }}>
            <option value="all">All Status</option>
            <option value="pending">Pending</option>
            <option value="processing">Processing</option>
            <option value="challan_issued">Challan Issued</option>
            <option value="paid">Paid</option>
          </select>
          <select value={typeFilter} onChange={e => setTypeFilter(e.target.value as ViolationType | 'all')}
            className="px-3 py-2 rounded-lg border text-sm outline-none"
            style={{ borderColor: '#E2E8F0', background: 'white' }}>
            <option value="all">All Types</option>
            {Object.entries(violationLabel).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Violations table */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="bg-white rounded-xl border overflow-hidden" style={{ borderColor: '#E2E8F0' }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: '#F8FAFC', borderBottom: '1px solid #E2E8F0' }}>
                {['Violation ID', 'Vehicle Plate', 'Type', 'Junction / Camera', 'Time', 'Fine', 'Confidence', 'Status', 'Action'].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold" style={{ color: '#475569' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((v, i) => {
                const sc = statusColor[v.status];
                return (
                  <tr key={v.id} className="border-b hover:bg-slate-50 cursor-pointer"
                    style={{ borderColor: '#F1F5F9' }}
                    onClick={() => setSelected(v)}>
                    <td className="px-4 py-3 mono text-xs font-semibold" style={{ color: '#64748B' }}>{v.id}</td>
                    <td className="px-4 py-3">
                      <span className="mono font-bold" style={{ color: '#0F172A' }}>{v.plate}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-xs font-semibold px-2 py-1 rounded"
                        style={{ background: typeColor[v.type] + '15', color: typeColor[v.type] }}>
                        {violationLabel[v.type]}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs" style={{ color: '#64748B' }}>
                      <div>{v.junctionName}</div>
                      <div className="mono" style={{ color: '#94A3B8' }}>{v.cameraId}</div>
                    </td>
                    <td className="px-4 py-3 text-xs mono" style={{ color: '#64748B' }}>
                      {Math.round((Date.now() - v.timestamp.getTime()) / 60000)}m ago
                    </td>
                    <td className="px-4 py-3 font-bold text-sm" style={{ color: '#D97706' }}>
                      ₹{v.fine.toLocaleString()}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1">
                        <div className="h-1.5 w-12 rounded-full" style={{ background: '#E2E8F0' }}>
                          <div className="h-full rounded-full" style={{
                            width: `${v.confidence}%`,
                            background: v.confidence > 90 ? '#16A34A' : '#D97706',
                          }}/>
                        </div>
                        <span className="text-xs mono">{v.confidence}%</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-xs font-semibold px-2 py-1 rounded capitalize"
                        style={{ background: sc.bg, color: sc.text }}>
                        {v.status.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {v.status === 'pending' && (
                        <button
                          onClick={e => { e.stopPropagation(); setSelected(v); }}
                          className="text-xs px-2.5 py-1 rounded font-semibold text-white"
                          style={{ background: '#DC2626' }}>
                          Process
                        </button>
                      )}
                      {v.status === 'challan_issued' && (
                        <span className="text-xs" style={{ color: '#1D4ED8' }}>Sent ✓</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {filtered.length === 0 && (
            <div className="py-12 text-center" style={{ color: '#94A3B8' }}>No violations match your filters</div>
          )}
        </div>
      </div>

      {selected && (
        <ViolationDetailModal
          violation={selected}
          onClose={() => setSelected(null)}
          onProcess={handleProcess}
        />
      )}
    </div>
  );
}
