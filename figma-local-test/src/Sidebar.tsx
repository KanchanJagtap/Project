import { useState } from 'react';

type Section =
  | 'overview' | 'livefeed' | 'signals' | 'violations'
  | 'vehicle_search' | 'traffic_analysis' | 'incidents' | 'emergency';

interface SidebarProps {
  active: Section;
  onChange: (s: Section) => void;
  user: { name: string; role: string; badge: string };
  onLogout: () => void;
  alertCount: { incidents: number; violations: number };
}

const NAV = [
  { id: 'overview' as Section, label: 'Overview', icon: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
      <rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
    </svg>
  )},
  { id: 'livefeed' as Section, label: 'Live Feed', icon: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <circle cx="12" cy="12" r="2"/><path d="M16.24 7.76a6 6 0 010 8.49m-8.48-.01a6 6 0 010-8.49m11.31-2.82a10 10 0 010 14.14m-14.14 0a10 10 0 010-14.14"/>
    </svg>
  )},
  { id: 'signals' as Section, label: 'Signals', icon: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <rect x="9" y="2" width="6" height="20" rx="3"/><circle cx="12" cy="7" r="1.5" fill="currentColor" stroke="none"/>
      <circle cx="12" cy="12" r="1.5" fill="currentColor" stroke="none"/><circle cx="12" cy="17" r="1.5" fill="currentColor" stroke="none"/>
    </svg>
  )},
  { id: 'violations' as Section, label: 'Violations', icon: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
      <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
    </svg>
  ), badge: 'violations' as 'violations' },
  { id: 'vehicle_search' as Section, label: 'Vehicle Search', icon: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/>
    </svg>
  )},
  { id: 'traffic_analysis' as Section, label: 'Traffic Analysis', icon: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
    </svg>
  )},
  { id: 'incidents' as Section, label: 'Incidents', icon: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
    </svg>
  ), badge: 'incidents' as 'incidents' },
  { id: 'emergency' as Section, label: 'Emergency', icon: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
    </svg>
  )},
];

export default function Sidebar({ active, onChange, user, onLogout, alertCount }: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false);
  const now = new Date();

  return (
    <aside
      className="flex flex-col h-full relative transition-all duration-300"
      style={{ width: collapsed ? 64 : 240, background: '#0F172A', minWidth: collapsed ? 64 : 240 }}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 py-5 border-b" style={{ borderColor: 'rgba(255,255,255,0.08)' }}>
        <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: '#1D4ED8' }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="3" fill="white"/>
            <path d="M12 2v3M12 19v3M2 12h3M19 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1" stroke="white" strokeWidth="2" strokeLinecap="round"/>
          </svg>
        </div>
        {!collapsed && (
          <div className="overflow-hidden">
            <div className="text-white font-bold text-sm leading-tight">STMS</div>
            <div className="text-slate-500 text-xs">Maharashtra</div>
          </div>
        )}
        <button
          onClick={() => setCollapsed(c => !c)}
          className="ml-auto text-slate-500 hover:text-slate-300 transition-colors flex-shrink-0"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            {collapsed
              ? <path d="M9 18l6-6-6-6"/>
              : <path d="M15 18l-6-6 6-6"/>}
          </svg>
        </button>
      </div>

      {/* Live status bar */}
      {!collapsed && (
        <div className="px-4 py-3 border-b" style={{ borderColor: 'rgba(255,255,255,0.06)', background: 'rgba(22,163,74,0.08)' }}>
          <div className="flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-green-400 blink-fast"/>
            <span className="text-green-400 text-xs font-semibold">SYSTEM LIVE</span>
            <span className="text-slate-500 text-xs ml-auto mono">
              {now.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </span>
          </div>
        </div>
      )}

      {/* Navigation */}
      <nav className="flex-1 py-3 overflow-y-auto">
        {!collapsed && (
          <div className="px-4 mb-2">
            <span className="text-slate-600 text-xs font-semibold tracking-wider uppercase">Navigation</span>
          </div>
        )}
        {NAV.map(item => {
          const isActive = active === item.id;
          const badgeCount = item.badge === 'violations' ? alertCount.violations : item.badge === 'incidents' ? alertCount.incidents : 0;
          return (
            <button
              key={item.id}
              onClick={() => onChange(item.id)}
              className={`sidebar-item w-full flex items-center gap-3 px-4 py-2.5 text-left relative ${isActive ? 'active' : ''}`}
              style={{ color: isActive ? '#93C5FD' : '#94A3B8' }}
              title={collapsed ? item.label : undefined}
            >
              <span className="flex-shrink-0">{item.icon}</span>
              {!collapsed && (
                <>
                  <span className="text-sm font-medium">{item.label}</span>
                  {badgeCount > 0 && (
                    <span className="ml-auto text-xs font-bold px-1.5 py-0.5 rounded-full"
                      style={{ background: '#DC2626', color: 'white', minWidth: 20, textAlign: 'center' }}>
                      {badgeCount}
                    </span>
                  )}
                </>
              )}
              {collapsed && badgeCount > 0 && (
                <span className="absolute top-1 right-1 w-2 h-2 rounded-full" style={{ background: '#DC2626' }}/>
              )}
            </button>
          );
        })}
      </nav>

      {/* Bottom: user info */}
      <div className="border-t p-3" style={{ borderColor: 'rgba(255,255,255,0.08)' }}>
        {!collapsed ? (
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 text-white text-sm font-bold"
              style={{ background: '#1D4ED8' }}>
              {user.name.charAt(0)}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-white text-xs font-semibold truncate">{user.name}</div>
              <div className="text-slate-500 text-xs truncate">{user.badge}</div>
            </div>
            <button onClick={onLogout} className="text-slate-600 hover:text-red-400 transition-colors" title="Logout">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/>
              </svg>
            </button>
          </div>
        ) : (
          <div className="flex justify-center">
            <div className="w-8 h-8 rounded-full flex items-center justify-center text-white text-sm font-bold"
              style={{ background: '#1D4ED8' }}>
              {user.name.charAt(0)}
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
