import { useState } from 'react';
import Login from './Login';
import Sidebar from './Sidebar';
import Overview from './Overview';
import LiveFeed from './LiveFeed';
import Signals from './Signals';
import Violations from './Violations';
import VehicleSearch from './VehicleSearch';
import TrafficAnalysis from './TrafficAnalysis';
import Incidents from './Incidents';
import Emergency from './Emergency';
import { INCIDENTS, VIOLATIONS } from './data';

type Section =
  | 'overview' | 'livefeed' | 'signals' | 'violations'
  | 'vehicle_search' | 'traffic_analysis' | 'incidents' | 'emergency';

interface User {
  name: string;
  role: string;
  badge: string;
}

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [activeSection, setActiveSection] = useState<Section>('overview');
  const [sectionData, setSectionData] = useState<unknown>(null);

  const handleLogin = (u: User) => setUser(u);
  const handleLogout = () => { setUser(null); setActiveSection('overview'); };

  const handleNavigate = (section: string, data?: unknown) => {
    setActiveSection(section as Section);
    setSectionData(data ?? null);
  };

  if (!user) return <Login onLogin={handleLogin} />;

  const alertCount = {
    incidents: INCIDENTS.filter(i => i.status === 'active').length,
    violations: VIOLATIONS.filter(v => v.status === 'pending').length,
  };

  const renderSection = () => {
    switch (activeSection) {
      case 'overview':
        return <Overview onNavigate={handleNavigate} />;
      case 'livefeed':
        return <LiveFeed initialJunctionId={typeof sectionData === 'string' ? sectionData : undefined} />;
      case 'signals':
        return <Signals />;
      case 'violations':
        return <Violations />;
      case 'vehicle_search':
        return <VehicleSearch />;
      case 'traffic_analysis':
        return <TrafficAnalysis />;
      case 'incidents':
        return <Incidents />;
      case 'emergency':
        return <Emergency />;
      default:
        return <Overview onNavigate={handleNavigate} />;
    }
  };

  return (
    <div className="flex h-full overflow-hidden" style={{ background: '#F8FAFC' }}>
      <Sidebar
        active={activeSection}
        onChange={s => { setActiveSection(s); setSectionData(null); }}
        user={user}
        onLogout={handleLogout}
        alertCount={alertCount}
      />
      <main className="flex-1 overflow-hidden">
        {renderSection()}
      </main>
    </div>
  );
}
