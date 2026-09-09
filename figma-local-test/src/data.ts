export type SignalColor = 'red' | 'yellow' | 'green';

export type VehicleType =
  | 'car'
  | 'truck'
  | 'bus'
  | 'motorcycle'
  | 'auto'
  | 'suv';

export type ViolationType =
  | 'red_light_jump'
  | 'wrong_lane'
  | 'wrong_way'
  | 'no_helmet'
  | 'triple_riding'
  | 'speeding'
  | 'no_parking'
  | 'stop_line'
  | 'invalid_plate'
  | 'restricted_zone';

export type IncidentType =
  | 'accident'
  | 'collision'
  | 'breakdown'
  | 'road_blockage'
  | 'fallen_object'
  | 'fire_smoke'
  | 'abnormal_slowdown';

export type EmergencyType = 'ambulance' | 'fire_brigade' | 'police';

export interface SignalArm {
  color: SignalColor;
  timer: number;
  greenDuration: number;
  redDuration: number;
  yellowDuration: number;
  vehicleDensity: number;
  queueLength: number;
  avgSpeed: number;
  occupancy: number;
  waitingTime: number;
}

export interface Junction {
  id: string;
  name: string;
  location: string;
  lat: number;
  lng: number;
  mapX: number;
  mapY: number;
  signals: {
    north: SignalArm;
    south: SignalArm;
    east: SignalArm;
    west: SignalArm;
  };
  mode: 'fixed' | 'adaptive';
  congestionLevel: 'low' | 'medium' | 'high' | 'critical';
  cameras: string[];
  totalVehicles: number;
  aiReason?: string;
}

export interface DetectedVehicle {
  id: string;
  plate: string;
  type: VehicleType;
  color: string;
  confidence: number;
  lane: number;
  direction: string;
  speed: number;
  cameraId: string;
  junctionId: string;
  timestamp: Date;
  x: number;
  y: number;
}

export interface Camera {
  id: string;
  name: string;
  junctionId: string;
  direction: 'north' | 'south' | 'east' | 'west';
  status: 'online' | 'offline';
  resolution: string;
  lat: number;
  lng: number;
}

export interface Violation {
  id: string;
  plate: string;
  vehicleType: VehicleType;
  type: ViolationType;
  cameraId: string;
  junctionId: string;
  junctionName: string;
  timestamp: Date;
  confidence: number;
  fine: number;
  status: 'pending' | 'processing' | 'challan_issued' | 'paid';
  speed?: number;
  evidenceDesc: string;
}

export interface VehicleProfile {
  plate: string;
  owner: string;
  phone: string;
  vehicleType: VehicleType;
  make: string;
  model: string;
  color: string;
  registrationState: string;
  registrationDate: string;
  violations: number;
  detections: Detection[];
  isTracked: boolean;
}

export interface Detection {
  cameraId: string;
  junctionName: string;
  timestamp: Date;
  direction: string;
  speed: number;
  confidence: number;
}

export interface Incident {
  id: string;
  type: IncidentType;
  location: string;
  cameraId: string;
  junctionId: string;
  junctionName: string;
  timestamp: Date;
  confidence: number;
  status: 'active' | 'police_notified' | 'emergency_notified' | 'resolved';
  description: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
}

export interface EmergencyVehicle {
  id: string;
  type: EmergencyType;
  vehicleNo: string;
  origin: string;
  destination: string;
  currentJunction: string;
  routeJunctions: string[];
  status: 'active' | 'en_route' | 'arrived';
  corridorActive: boolean;
  detectedAt?: string;
  eta: number;
}

const makeArm = (
  color: SignalColor,
  timer: number,
  greenDuration: number,
  density: number,
  queue: number,
  speed: number,
): SignalArm => ({
  color,
  timer,
  greenDuration,
  redDuration: 45,
  yellowDuration: 5,
  vehicleDensity: density,
  queueLength: queue,
  avgSpeed: speed,
  occupancy: Math.round(density * 0.9),
  waitingTime: Math.round((100 - speed) * 0.8),
});

export const JUNCTIONS: Junction[] = [
  {
    id: 'J01',
    name: 'Shivajinagar Junction',
    location: 'Shivajinagar, Pune, Maharashtra',
    lat: 18.5308,
    lng: 73.8475,
    mapX: 420,
    mapY: 250,
    signals: {
      north: makeArm('red', 28, 35, 78, 14, 22),
      south: makeArm('green', 12, 35, 45, 6, 48),
      east: makeArm('red', 28, 30, 82, 18, 15),
      west: makeArm('red', 28, 30, 60, 9, 35),
    },
    mode: 'adaptive',
    congestionLevel: 'high',
    cameras: ['CAM-01', 'CAM-02', 'CAM-03', 'CAM-04'],
    totalVehicles: 234,
    aiReason: 'Heavy vehicle flow detected on the east approach',
  },
  {
    id: 'J02',
    name: 'Swargate Junction',
    location: 'Swargate, Pune, Maharashtra',
    lat: 18.5018,
    lng: 73.8636,
    mapX: 350,
    mapY: 350,
    signals: {
      north: makeArm('green', 18, 40, 55, 8, 42),
      south: makeArm('red', 22, 40, 62, 11, 28),
      east: makeArm('red', 22, 35, 48, 7, 38),
      west: makeArm('red', 22, 35, 70, 13, 20),
    },
    mode: 'fixed',
    congestionLevel: 'medium',
    cameras: ['CAM-05', 'CAM-06', 'CAM-07', 'CAM-08'],
    totalVehicles: 178,
  },
  {
    id: 'J03',
    name: 'Hadapsar Junction',
    location: 'Hadapsar, Pune, Maharashtra',
    lat: 18.5089,
    lng: 73.926,
    mapX: 610,
    mapY: 330,
    signals: {
      north: makeArm('red', 35, 25, 95, 24, 8),
      south: makeArm('yellow', 4, 25, 88, 22, 12),
      east: makeArm('red', 35, 20, 92, 26, 6),
      west: makeArm('red', 35, 20, 97, 28, 5),
    },
    mode: 'adaptive',
    congestionLevel: 'critical',
    cameras: ['CAM-09', 'CAM-10', 'CAM-11', 'CAM-12'],
    totalVehicles: 412,
    aiReason: 'High peak-hour queue detected on multiple approaches',
  },
  {
    id: 'J04',
    name: 'Katraj Junction',
    location: 'Katraj, Pune, Maharashtra',
    lat: 18.4575,
    lng: 73.868,
    mapX: 270,
    mapY: 440,
    signals: {
      north: makeArm('green', 22, 50, 40, 5, 55),
      south: makeArm('red', 28, 50, 35, 4, 60),
      east: makeArm('red', 28, 45, 50, 7, 45),
      west: makeArm('red', 28, 45, 45, 6, 48),
    },
    mode: 'fixed',
    congestionLevel: 'low',
    cameras: ['CAM-13', 'CAM-14', 'CAM-15', 'CAM-16'],
    totalVehicles: 98,
  },
  {
    id: 'J05',
    name: 'CBS Junction',
    location: 'Central Bus Stand, Nashik, Maharashtra',
    lat: 20.0059,
    lng: 73.79,
    mapX: 500,
    mapY: 170,
    signals: {
      north: makeArm('red', 15, 30, 68, 12, 28),
      south: makeArm('green', 15, 30, 55, 8, 40),
      east: makeArm('red', 15, 28, 72, 14, 22),
      west: makeArm('red', 15, 28, 62, 10, 30),
    },
    mode: 'adaptive',
    congestionLevel: 'high',
    cameras: ['CAM-17', 'CAM-18', 'CAM-19', 'CAM-20'],
    totalVehicles: 287,
    aiReason: 'Bus and auto-rickshaw concentration increasing queue pressure',
  },
  {
    id: 'J06',
    name: 'Dwarka Circle',
    location: 'Dwarka Circle, Nashik, Maharashtra',
    lat: 19.9975,
    lng: 73.819,
    mapX: 650,
    mapY: 250,
    signals: {
      north: makeArm('green', 8, 35, 48, 7, 44),
      south: makeArm('red', 32, 35, 52, 8, 40),
      east: makeArm('red', 32, 30, 60, 10, 32),
      west: makeArm('red', 32, 30, 65, 11, 28),
    },
    mode: 'fixed',
    congestionLevel: 'medium',
    cameras: ['CAM-21', 'CAM-22', 'CAM-23', 'CAM-24'],
    totalVehicles: 165,
  },
  {
    id: 'J07',
    name: 'Savedi Chowk',
    location: 'Savedi, Ahilyanagar, Maharashtra',
    lat: 19.091,
    lng: 74.748,
    mapX: 220,
    mapY: 160,
    signals: {
      north: makeArm('red', 20, 32, 58, 9, 36),
      south: makeArm('green', 10, 32, 42, 5, 52),
      east: makeArm('red', 20, 28, 48, 7, 42),
      west: makeArm('red', 20, 28, 55, 8, 38),
    },
    mode: 'adaptive',
    congestionLevel: 'medium',
    cameras: ['CAM-25', 'CAM-26', 'CAM-27', 'CAM-28'],
    totalVehicles: 142,
  },
  {
    id: 'J08',
    name: 'Ahmednagar MIDC Chowk',
    location: 'MIDC Area, Ahilyanagar, Maharashtra',
    lat: 19.115,
    lng: 74.739,
    mapX: 330,
    mapY: 120,
    signals: {
      north: makeArm('green', 25, 45, 35, 4, 58),
      south: makeArm('red', 20, 45, 40, 5, 54),
      east: makeArm('red', 20, 38, 38, 5, 55),
      west: makeArm('red', 20, 38, 32, 4, 60),
    },
    mode: 'fixed',
    congestionLevel: 'low',
    cameras: ['CAM-29', 'CAM-30', 'CAM-31', 'CAM-32'],
    totalVehicles: 88,
  },
  {
    id: 'J09',
    name: 'Pipeline Road Junction',
    location: 'Pipeline Road, Ahilyanagar, Maharashtra',
    lat: 19.095,
    lng: 74.755,
    mapX: 180,
    mapY: 290,
    signals: {
      north: makeArm('red', 18, 35, 72, 13, 25),
      south: makeArm('red', 18, 35, 65, 11, 30),
      east: makeArm('green', 17, 35, 58, 9, 38),
      west: makeArm('red', 18, 30, 70, 12, 26),
    },
    mode: 'adaptive',
    congestionLevel: 'high',
    cameras: ['CAM-33', 'CAM-34', 'CAM-35', 'CAM-36'],
    totalVehicles: 201,
    aiReason: 'Mixed traffic and heavy vehicles increasing waiting time',
  },
  {
    id: 'J10',
    name: 'Sion Junction',
    location: 'Sion, Mumbai, Maharashtra',
    lat: 19.046,
    lng: 72.863,
    mapX: 520,
    mapY: 390,
    signals: {
      north: makeArm('red', 30, 28, 85, 19, 14),
      south: makeArm('yellow', 3, 28, 80, 17, 18),
      east: makeArm('red', 30, 25, 88, 21, 11),
      west: makeArm('red', 30, 25, 82, 18, 16),
    },
    mode: 'adaptive',
    congestionLevel: 'critical',
    cameras: ['CAM-37', 'CAM-38', 'CAM-39', 'CAM-40'],
    totalVehicles: 356,
    aiReason: 'Peak-hour traffic surge — extended green recommended',
  },
  {
    id: 'J11',
    name: 'Andheri Junction',
    location: 'Andheri East, Mumbai, Maharashtra',
    lat: 19.1197,
    lng: 72.8468,
    mapX: 690,
    mapY: 130,
    signals: {
      north: makeArm('green', 5, 30, 42, 6, 50),
      south: makeArm('red', 25, 30, 48, 7, 44),
      east: makeArm('red', 25, 28, 55, 8, 38),
      west: makeArm('red', 25, 28, 50, 7, 42),
    },
    mode: 'fixed',
    congestionLevel: 'medium',
    cameras: ['CAM-41', 'CAM-42', 'CAM-43', 'CAM-44'],
    totalVehicles: 134,
  },
  {
    id: 'J12',
    name: 'Pimpri Chowk',
    location: 'Pimpri, Pune, Maharashtra',
    lat: 18.6298,
    lng: 73.7997,
    mapX: 560,
    mapY: 70,
    signals: {
      north: makeArm('red', 22, 40, 52, 8, 42),
      south: makeArm('green', 18, 40, 45, 6, 50),
      east: makeArm('red', 22, 35, 58, 9, 36),
      west: makeArm('red', 22, 35, 62, 10, 30),
    },
    mode: 'fixed',
    congestionLevel: 'medium',
    cameras: ['CAM-45', 'CAM-46', 'CAM-47', 'CAM-48'],
    totalVehicles: 156,
  },
];

// ─── CAMERAS ────────────────────────────────────────────────────────────────

export const CAMERAS: Camera[] = JUNCTIONS.flatMap((j, ji) =>
  (['north', 'south', 'east', 'west'] as const).map((dir, di) => ({
    id: `CAM-${String(ji * 4 + di + 1).padStart(2, '0')}`,
    name: `${j.name} - ${dir.charAt(0).toUpperCase() + dir.slice(1)} Approach`,
    junctionId: j.id,
    direction: dir,
    status: ji === 2 && di === 3 ? 'offline' : 'online' as Camera['status'],
    resolution: '1920×1080',
    lat:
      j.lat +
      (dir === 'north' ? 0.002 : dir === 'south' ? -0.002 : 0),
    lng:
      j.lng +
      (dir === 'east' ? 0.002 : dir === 'west' ? -0.002 : 0),
  })),
);

// ─── VIOLATIONS ─────────────────────────────────────────────────────────────

const plates = [
  'MH12AB1234',
  'MH14CD5678',
  'MH15EF9012',
  'MH16GH3456',
  'MH17JK7890',
  'MH18LM2468',
];

const violationTypes: {
  type: ViolationType;
  fine: number;
  desc: string;
}[] = [
  {
    type: 'red_light_jump',
    fine: 1000,
    desc: 'Vehicle crossed stop line after red signal',
  },
  {
    type: 'speeding',
    fine: 2000,
    desc: 'Vehicle detected above the permitted speed limit',
  },
  {
    type: 'wrong_way',
    fine: 5000,
    desc: 'Vehicle travelling against the traffic flow',
  },
  {
    type: 'no_helmet',
    fine: 500,
    desc: 'Rider detected without helmet on two-wheeler',
  },
  {
    type: 'triple_riding',
    fine: 1000,
    desc: 'Three persons detected on a two-wheeler',
  },
  {
    type: 'stop_line',
    fine: 500,
    desc: 'Vehicle crossed stop line while signal was red',
  },
  {
    type: 'no_parking',
    fine: 500,
    desc: 'Vehicle detected in a no-parking zone',
  },
  {
    type: 'wrong_lane',
    fine: 500,
    desc: 'Vehicle detected in an incorrect lane',
  },
  {
    type: 'invalid_plate',
    fine: 5000,
    desc: 'Number plate appears partially obscured or tampered',
  },
  {
    type: 'restricted_zone',
    fine: 2000,
    desc: 'Vehicle entered a restricted traffic zone',
  },
];

const minutesAgo = (m: number) =>
  new Date(Date.now() - m * 60000);

export const VIOLATIONS: Violation[] = plates.map((plate, i) => {
  const vt = violationTypes[i % violationTypes.length];
  const j = JUNCTIONS[i % JUNCTIONS.length];

  return {
    id: `VIO-${String(2026001 + i)}`,
    plate,
    vehicleType: (
      ['car', 'suv', 'truck', 'motorcycle', 'auto', 'bus'] as VehicleType[]
    )[i % 6],
    type: vt.type,
    cameraId: j.cameras[i % 4],
    junctionId: j.id,
    junctionName: j.name,
    timestamp: minutesAgo(i * 4 + 2),
    confidence: 85 + (i * 7) % 14,
    fine: vt.fine,
    status: (
      ['pending', 'pending', 'processing', 'challan_issued', 'paid'] as Violation['status'][]
    )[i % 5],
    speed:
      vt.type === 'speeding'
        ? 82 + (i % 20)
        : undefined,
    evidenceDesc: vt.desc,
  };
});

// ─── VEHICLE PROFILES ───────────────────────────────────────────────────────

export const VEHICLE_DB: Record<string, VehicleProfile> = {
  'MH12AB1234': {
    plate: 'MH12AB1234',
    owner: 'Demo Owner 01',
    phone: '+91 90000 00001',
    vehicleType: 'car',
    make: 'Hyundai',
    model: 'i20',
    color: 'White',
    registrationState: 'Maharashtra',
    registrationDate: '2021-03-15',
    violations: 3,
    isTracked: true,
    detections: [
      {
        cameraId: 'CAM-01',
        junctionName: 'Shivajinagar Junction',
        timestamp: minutesAgo(2),
        direction: 'Northbound',
        speed: 38,
        confidence: 94,
      },
      {
        cameraId: 'CAM-05',
        junctionName: 'Swargate Junction',
        timestamp: minutesAgo(8),
        direction: 'Eastbound',
        speed: 42,
        confidence: 91,
      },
      {
        cameraId: 'CAM-17',
        junctionName: 'CBS Junction',
        timestamp: minutesAgo(15),
        direction: 'Northbound',
        speed: 35,
        confidence: 88,
      },
      {
        cameraId: 'CAM-25',
        junctionName: 'Savedi Chowk',
        timestamp: minutesAgo(28),
        direction: 'Westbound',
        speed: 22,
        confidence: 96,
      },
    ],
  },

  'MH14CD5678': {
    plate: 'MH14CD5678',
    owner: 'Demo Owner 02',
    phone: '+91 90000 00002',
    vehicleType: 'suv',
    make: 'Mahindra',
    model: 'XUV700',
    color: 'Black',
    registrationState: 'Maharashtra',
    registrationDate: '2022-07-22',
    violations: 1,
    isTracked: false,
    detections: [
      {
        cameraId: 'CAM-09',
        junctionName: 'Hadapsar Junction',
        timestamp: minutesAgo(5),
        direction: 'Southbound',
        speed: 28,
        confidence: 89,
      },
    ],
  },

  'MH15EF9012': {
    plate: 'MH15EF9012',
    owner: 'Demo Operator 01',
    phone: '+91 90000 00003',
    vehicleType: 'truck',
    make: 'Tata',
    model: 'LPT 709',
    color: 'Red',
    registrationState: 'Maharashtra',
    registrationDate: '2019-11-08',
    violations: 7,
    isTracked: true,
    detections: [
      {
        cameraId: 'CAM-05',
        junctionName: 'Swargate Junction',
        timestamp: minutesAgo(3),
        direction: 'Westbound',
        speed: 35,
        confidence: 97,
      },
      {
        cameraId: 'CAM-17',
        junctionName: 'CBS Junction',
        timestamp: minutesAgo(18),
        direction: 'Southbound',
        speed: 28,
        confidence: 94,
      },
      {
        cameraId: 'CAM-29',
        junctionName: 'Ahmednagar MIDC Chowk',
        timestamp: minutesAgo(32),
        direction: 'Eastbound',
        speed: 31,
        confidence: 92,
      },
    ],
  },

  'MH16GH3456': {
    plate: 'MH16GH3456',
    owner: 'Demo Owner 03',
    phone: '+91 90000 00004',
    vehicleType: 'motorcycle',
    make: 'Bajaj',
    model: 'Pulsar 150',
    color: 'Blue',
    registrationState: 'Maharashtra',
    registrationDate: '2023-01-19',
    violations: 2,
    isTracked: true,
    detections: [
      {
        cameraId: 'CAM-25',
        junctionName: 'Savedi Chowk',
        timestamp: minutesAgo(4),
        direction: 'Southbound',
        speed: 46,
        confidence: 93,
      },
      {
        cameraId: 'CAM-33',
        junctionName: 'Pipeline Road Junction',
        timestamp: minutesAgo(21),
        direction: 'Northbound',
        speed: 39,
        confidence: 90,
      },
    ],
  },

  'MH17JK7890': {
    plate: 'MH17JK7890',
    owner: 'Demo Owner 04',
    phone: '+91 90000 00005',
    vehicleType: 'car',
    make: 'Maruti Suzuki',
    model: 'Swift',
    color: 'Grey',
    registrationState: 'Maharashtra',
    registrationDate: '2020-09-12',
    violations: 0,
    isTracked: false,
    detections: [
      {
        cameraId: 'CAM-41',
        junctionName: 'Andheri Junction',
        timestamp: minutesAgo(7),
        direction: 'Eastbound',
        speed: 41,
        confidence: 95,
      },
    ],
  },

  'MH18LM2468': {
    plate: 'MH18LM2468',
    owner: 'Demo Operator 02',
    phone: '+91 90000 00006',
    vehicleType: 'bus',
    make: 'Tata',
    model: 'Starbus',
    color: 'White',
    registrationState: 'Maharashtra',
    registrationDate: '2018-05-28',
    violations: 4,
    isTracked: true,
    detections: [
      {
        cameraId: 'CAM-17',
        junctionName: 'CBS Junction',
        timestamp: minutesAgo(6),
        direction: 'Northbound',
        speed: 24,
        confidence: 92,
      },
      {
        cameraId: 'CAM-21',
        junctionName: 'Dwarka Circle',
        timestamp: minutesAgo(24),
        direction: 'Westbound',
        speed: 29,
        confidence: 89,
      },
    ],
  },
};

// ─── INCIDENTS ──────────────────────────────────────────────────────────────

export const INCIDENTS: Incident[] = [
  {
    id: 'INC-001',
    type: 'collision',
    location: 'Shivajinagar Junction, Pune',
    cameraId: 'CAM-01',
    junctionId: 'J01',
    junctionName: 'Shivajinagar Junction',
    timestamp: minutesAgo(3),
    confidence: 89,
    severity: 'high',
    status: 'active',
    description:
      'Two vehicles involved in a rear-end collision. Northbound lane partially blocked.',
  },
  {
    id: 'INC-002',
    type: 'breakdown',
    location: 'CBS Junction, Nashik',
    cameraId: 'CAM-17',
    junctionId: 'J05',
    junctionName: 'CBS Junction',
    timestamp: minutesAgo(8),
    confidence: 94,
    severity: 'high',
    status: 'police_notified',
    description:
      'Bus breakdown detected near the junction. Vehicle occupying the left lane and causing queue formation.',
  },
  {
    id: 'INC-003',
    type: 'road_blockage',
    location: 'Hadapsar Junction, Pune',
    cameraId: 'CAM-09',
    junctionId: 'J03',
    junctionName: 'Hadapsar Junction',
    timestamp: minutesAgo(13),
    confidence: 91,
    severity: 'critical',
    status: 'emergency_notified',
    description:
      'Goods vehicle blocking two lanes. Emergency response workflow activated.',
  },
  {
    id: 'INC-004',
    type: 'abnormal_slowdown',
    location: 'Sion Junction, Mumbai',
    cameraId: 'CAM-37',
    junctionId: 'J10',
    junctionName: 'Sion Junction',
    timestamp: minutesAgo(19),
    confidence: 85,
    severity: 'medium',
    status: 'active',
    description:
      'AI detected an unusual traffic slowdown with average speed dropping significantly in the last five minutes.',
  },
  {
    id: 'INC-005',
    type: 'fallen_object',
    location: 'Pipeline Road Junction, Ahilyanagar',
    cameraId: 'CAM-33',
    junctionId: 'J09',
    junctionName: 'Pipeline Road Junction',
    timestamp: minutesAgo(26),
    confidence: 79,
    severity: 'medium',
    status: 'active',
    description:
      'Roadside object detected in the traffic lane. Vehicles are changing lanes to avoid the obstruction.',
  },
];

// ─── EMERGENCY VEHICLES ─────────────────────────────────────────────────────

export const EMERGENCY_VEHICLES: EmergencyVehicle[] = [
  {
    id: 'EMG-001',
    type: 'ambulance',
    vehicleNo: 'MH-12-AMB-1042',
    origin: 'Pune Emergency Response Unit',
    destination: 'Sassoon General Hospital, Pune',
    currentJunction: 'J01',
    routeJunctions: ['J01', 'J02', 'J12'],
    status: 'en_route',
    corridorActive: true,
    detectedAt: 'CAM-01',
    eta: 8,
  },
  {
    id: 'EMG-002',
    type: 'fire_brigade',
    vehicleNo: 'MH-15-FIRE-231',
    origin: 'Nashik Fire Station',
    destination: 'CBS Junction Incident',
    currentJunction: 'J06',
    routeJunctions: ['J06', 'J05'],
    status: 'active',
    corridorActive: true,
    detectedAt: 'CAM-21',
    eta: 6,
  },
  {
    id: 'EMG-003',
    type: 'police',
    vehicleNo: 'MH-16-PS-047',
    origin: 'Ahilyanagar Traffic Control',
    destination: 'Pipeline Road Junction',
    currentJunction: 'J08',
    routeJunctions: ['J08', 'J09'],
    status: 'en_route',
    corridorActive: false,
    detectedAt: 'CAM-30',
    eta: 5,
  },
];

// ─── FINE RULES ─────────────────────────────────────────────────────────────

export const FINE_RULES: Record<
  ViolationType,
  { fine: number; points: number; description: string }
> = {
  red_light_jump: {
    fine: 1000,
    points: 2,
    description: 'Jumping Red Signal — Section 119, MV Act',
  },
  speeding: {
    fine: 2000,
    points: 3,
    description: 'Over Speeding — Section 183, MV Act',
  },
  wrong_way: {
    fine: 5000,
    points: 4,
    description: 'Driving Against Traffic — Section 184, MV Act',
  },
  no_helmet: {
    fine: 500,
    points: 1,
    description: 'Not Wearing Helmet — Section 129, MV Act',
  },
  triple_riding: {
    fine: 1000,
    points: 2,
    description: 'Triple Riding — Section 128, MV Act',
  },
  stop_line: {
    fine: 500,
    points: 1,
    description: 'Stop Line Violation — Section 119, MV Act',
  },
  no_parking: {
    fine: 500,
    points: 1,
    description: 'Parking Violation — Section 122, MV Act',
  },
  wrong_lane: {
    fine: 500,
    points: 1,
    description: 'Wrong Lane — Section 112, MV Act',
  },
  invalid_plate: {
    fine: 5000,
    points: 4,
    description: 'Invalid/Tampered Number Plate — Section 39, MV Act',
  },
  restricted_zone: {
    fine: 2000,
    points: 2,
    description: 'Restricted Zone Entry — Local Traffic Rules',
  },
};

// ─── HELPERS ────────────────────────────────────────────────────────────────

export const violationLabel: Record<ViolationType, string> = {
  red_light_jump: 'Red Light Jump',
  speeding: 'Speeding',
  wrong_way: 'Wrong Way',
  no_helmet: 'No Helmet',
  triple_riding: 'Triple Riding',
  stop_line: 'Stop Line Violation',
  no_parking: 'No Parking',
  wrong_lane: 'Wrong Lane',
  invalid_plate: 'Invalid Plate',
  restricted_zone: 'Restricted Zone',
};

export const incidentLabel: Record<IncidentType, string> = {
  accident: 'Accident',
  collision: 'Vehicle Collision',
  breakdown: 'Vehicle Breakdown',
  road_blockage: 'Road Blockage',
  fallen_object: 'Fallen Object',
  fire_smoke: 'Fire / Smoke',
  abnormal_slowdown: 'Abnormal Slowdown',
};

export const congestionColor = {
  low: '#16A34A',
  medium: '#D97706',
  high: '#EA580C',
  critical: '#DC2626',
};

export const vehicleColors = [
  '#E5E7EB',
  '#1E40AF',
  '#DC2626',
  '#16A34A',
  '#7C3AED',
  '#D97706',
  '#374151',
  '#0F766E',
];
