import { useState } from 'react';

interface LoginProps {
  onLogin: (user: { name: string; role: string; badge: string }) => void;
}

export default function Login({ onLogin }: LoginProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [accessLevel, setAccessLevel] = useState('traffic_police');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const credentials: Record<string, { name: string; badge: string; role: string }> = {
    'admin@stms.gov.in': { name: 'Suresh Menon', badge: 'ADM-001', role: 'System Administrator' },
    'officer@stms.gov.in': { name: 'Priya Rajan', badge: 'TPC-4421', role: 'Traffic Police' },
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    await new Promise(r => setTimeout(r, 1200));
    const user = credentials[email.toLowerCase()];
    if (user && password === 'stms2024') {
      onLogin(user);
    } else {
      setError('Invalid credentials. Please try again.');
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen flex" style={{ background: 'linear-gradient(135deg, #0F172A 0%, #1E3A5F 50%, #0F172A 100%)' }}>
      {/* Background grid pattern */}
      <div className="absolute inset-0 opacity-10"
        style={{ backgroundImage: 'linear-gradient(#3B82F6 1px, transparent 1px), linear-gradient(90deg, #3B82F6 1px, transparent 1px)', backgroundSize: '40px 40px' }} />

      {/* Left panel - branding */}
      <div className="hidden lg:flex flex-col justify-between w-1/2 p-16 relative z-10">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: '#1D4ED8' }}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="3" fill="white"/>
              <path d="M12 2v3M12 19v3M2 12h3M19 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1" stroke="white" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </div>
          <div>
            <div className="text-white font-bold text-lg leading-tight">STMS</div>
            <div className="text-blue-300 text-xs">Smart Traffic Management System</div>
          </div>
        </div>

        <div>
          <div className="text-blue-400 text-sm font-semibold tracking-widest uppercase mb-4">
            Bengaluru Metropolitan Area
          </div>
          <h1 className="text-5xl font-bold text-white leading-tight mb-6">
            City-Wide<br />Traffic Control<br />Command Center
          </h1>
          <p className="text-slate-400 text-lg leading-relaxed max-w-md">
            AI-powered traffic management platform integrating real-time camera feeds, adaptive signal control, violation detection and emergency response coordination.
          </p>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-3 gap-6">
          {[
            { value: '48', label: 'Active Cameras' },
            { value: '12', label: 'Junctions' },
            { value: '24/7', label: 'Monitoring' },
          ].map(s => (
            <div key={s.label} className="border border-slate-700 rounded-xl p-4">
              <div className="text-2xl font-bold text-blue-400">{s.value}</div>
              <div className="text-slate-400 text-sm mt-1">{s.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Right panel - login form */}
      <div className="flex-1 flex items-center justify-center p-8 relative z-10">
        <div className="w-full max-w-md">
          <div className="bg-white rounded-2xl shadow-2xl p-8">
            {/* Header */}
            <div className="text-center mb-8">
              <div className="w-14 h-14 rounded-2xl mx-auto mb-4 flex items-center justify-center" style={{ background: '#0F172A' }}>
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
                  <rect x="3" y="11" width="18" height="11" rx="2" stroke="#3B82F6" strokeWidth="2"/>
                  <path d="M7 11V7a5 5 0 0110 0v4" stroke="#3B82F6" strokeWidth="2" strokeLinecap="round"/>
                </svg>
              </div>
              <h2 className="text-2xl font-bold" style={{ color: '#0F172A' }}>Secure Login</h2>
              <p className="text-slate-500 text-sm mt-1">Traffic Management Authority — Bengaluru</p>
            </div>

            {/* Quick fill hint */}
            <div className="rounded-lg p-3 mb-6 text-xs" style={{ background: '#EFF6FF', border: '1px solid #BFDBFE' }}>
              <div className="font-semibold text-blue-800 mb-1">Demo Credentials</div>
              <div className="text-blue-700 space-y-0.5">
                <div>Admin: <span className="mono">admin@stms.gov.in</span></div>
                <div>Officer: <span className="mono">officer@stms.gov.in</span></div>
                <div>Password: <span className="mono">stms2024</span></div>
              </div>
            </div>

            <form onSubmit={handleLogin} className="space-y-5">
              <div>
                <label className="block text-sm font-semibold mb-2" style={{ color: '#0F172A' }}>
                  Official Email Address
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="officer@stms.gov.in"
                  className="w-full px-4 py-3 rounded-lg border text-sm outline-none transition-all"
                  style={{ borderColor: '#E2E8F0', color: '#0F172A' }}
                  onFocus={e => e.target.style.borderColor = '#1D4ED8'}
                  onBlur={e => e.target.style.borderColor = '#E2E8F0'}
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-semibold mb-2" style={{ color: '#0F172A' }}>
                  Password
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full px-4 py-3 rounded-lg border text-sm outline-none transition-all"
                  style={{ borderColor: '#E2E8F0', color: '#0F172A' }}
                  onFocus={e => e.target.style.borderColor = '#1D4ED8'}
                  onBlur={e => e.target.style.borderColor = '#E2E8F0'}
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-semibold mb-2" style={{ color: '#0F172A' }}>
                  Access Level
                </label>
                <select
                  value={accessLevel}
                  onChange={e => setAccessLevel(e.target.value)}
                  className="w-full px-4 py-3 rounded-lg border text-sm outline-none"
                  style={{ borderColor: '#E2E8F0', color: '#0F172A', background: 'white' }}
                >
                  <option value="system_admin">System Administrator</option>
                  <option value="traffic_police">Traffic Police</option>
                </select>
              </div>

              {error && (
                <div className="rounded-lg p-3 text-sm" style={{ background: '#FEF2F2', color: '#DC2626', border: '1px solid #FECACA' }}>
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 rounded-lg font-semibold text-white text-sm transition-all"
                style={{ background: loading ? '#93C5FD' : '#1D4ED8' }}
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="animate-spin h-4 w-4 text-white" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
                    </svg>
                    Authenticating...
                  </span>
                ) : 'Sign In to Command Center'}
              </button>
            </form>

            <div className="mt-6 pt-6 border-t text-center">
              <p className="text-xs text-slate-400">
                Authorized personnel only. All access is monitored and logged.<br />
                Karnataka Traffic Police — Ministry of Home Affairs
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
