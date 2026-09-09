export type SignalColor = 'red' | 'yellow' | 'green';
export type VehicleType = 'car' | 'truck' | 'bus' | 'motorcycle' | 'auto' | 'suv';
export type ViolationType =
  | 'red_light_jump' | 'wrong_lane' | 'wrong_way' | 'no_helmet'
  | 'triple_riding' | 'speeding' | 'no_parking' | 'stop_line'
  | 'invalid_plate' | 'restricted_zone';
export type IncidentType =
  | 'accident' | 'collision' | 'breakdown' | 'road_blockage'
  | 'fallen_object' | 'fire_smoke' | 'abnormal_slowdown';
export type EmergencyType = 'ambulance' | 'fire_brigade' | 'police';

export interface SignalArm {
  color: SignalColor;
  timer: number;
  greenDuration: number;
  redDuration: number;
  yellowDuration: number;
  vehicleDensity: number; // 0-100
  queueLength: number;
  avgSpeed: number;
  occupancy: number; // 0-100
  waitingTime: number; // seconds
}

export interface Junction {
  id: string;
  name: string;
  location: string;
  lat: number;
  lng: number;
  mapX: number; // SVG position
  mapY: number;
  signals: { north: SignalArm; south: SignalArm; east: SignalArm; west: SignalArm };
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
  x: number; // canvas coords
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
  eta: number; // minutes
}

// ─── JUNCTIONS ───────────────────────────────────────────────────────────────

const makeArm = (
  color: SignalColor, timer: number, greenDuration: number,
  density: number, queue: number, speed: number
): SignalArm => ({
  color, timer, greenDuration, redDuration: 45, yellowDuration: 5,
  vehicleDensity: density, queueLength: queue,
  avgSpeed: speed, occupancy: Math.round(density * 0.9), waitingTime: Math.round((100 - speed) * 0.8),
});

export const JUNCTIONS: Junction[] = [
  {
    id: 'J01', name: 'MG Road Junction', location: 'MG Road, Bengaluru',
    lat: 12.9716, lng: 77.6099, mapX: 420, mapY: 260,
    signals: {
      north: makeArm('red', 28, 35, 78, 14, 22),
      south: makeArm('green', 12, 35, 45, 6, 48),
      east: makeArm('red', 28, 30, 82, 18, 15),
      west: makeArm('red', 28, 30, 60, 9, 35),
    },
    mode: 'adaptive', congestionLevel: 'high', cameras: ['CAM-01', 'CAM-02', 'CAM-03', 'CAM-04'],
    totalVehicles: 234, aiReason: 'Heavy truck blocking east lane increases queue',
  },
  {
    id: 'J02', name: 'Brigade Road Junction', location: 'Brigade Road, Bengaluru',
    lat: 12.9742, lng: 77.6088, mapX: 360, mapY: 200,
    signals: {
      north: makeArm('green', 18, 40, 55, 8, 42),
      south: makeArm('red', 22, 40, 62, 11, 28),
      east: makeArm('red', 22, 35, 48, 7, 38),
      west: makeArm('red', 22, 35, 70, 13, 20),
    },
    mode: 'fixed', congestionLevel: 'medium', cameras: ['CAM-05', 'CAM-06', 'CAM-07', 'CAM-08'],
    totalVehicles: 178,
  },
  {
    id: 'J03', name: 'Silk Board Junction', location: 'Silk Board, Bengaluru',
    lat: 12.9174, lng: 77.6227, mapX: 460, mapY: 360,
    signals: {
      north: makeArm('red', 35, 25, 95, 24, 8),
      south: makeArm('yellow', 4, 25, 88, 22, 12),
      east: makeArm('red', 35, 20, 92, 26, 6),
      west: makeArm('red', 35, 20, 97, 28, 5),
    },
    mode: 'adaptive', congestionLevel: 'critical', cameras: ['CAM-09', 'CAM-10', 'CAM-11', 'CAM-12'],
    totalVehicles: 412, aiReason: 'Multiple large vehicles blocking all westbound lanes',
  },
  {
    id: 'J04', name: 'Hebbal Flyover Junction', location: 'Hebbal, Bengaluru',
    lat: 13.0358, lng: 77.5970, mapX: 300, mapY: 120,
    signals: {
      north: makeArm('green', 22, 50, 40, 5, 55),
      south: makeArm('red', 28, 50, 35, 4, 60),
      east: makeArm('red', 28, 45, 50, 7, 45),
      west: makeArm('red', 28, 45, 45, 6, 48),
    },
    mode: 'fixed', congestionLevel: 'low', cameras: ['CAM-13', 'CAM-14', 'CAM-15', 'CAM-16'],
    totalVehicles: 98,
  },
  {
    id: 'J05', name: 'Koramangala Junction', location: '5th Block, Koramangala, Bengaluru',
    lat: 12.9279, lng: 77.6271, mapX: 480, mapY: 320,
    signals: {
      north: makeArm('red', 15, 30, 68, 12, 28),
      south: makeArm('green', 15, 30, 55, 8, 40),
      east: makeArm('red', 15, 28, 72, 14, 22),
      west: makeArm('red', 15, 28, 62, 10, 30),
    },
    mode: 'adaptive', congestionLevel: 'high', cameras: ['CAM-17', 'CAM-18', 'CAM-19', 'CAM-20'],
    totalVehicles: 287,
  },
  {
    id: 'J06', name: 'Marathahalli Junction', location: 'Marathahalli Bridge, Bengaluru',
    lat: 12.9591, lng: 77.6977, mapX: 580, mapY: 280,
    signals: {
      north: makeArm('green', 8, 35, 48, 7, 44),
      south: makeArm('red', 32, 35, 52, 8, 40),
      east: makeArm('red', 32, 30, 60, 10, 32),
      west: makeArm('red', 32, 30, 65, 11, 28),
    },
    mode: 'fixed', congestionLevel: 'medium', cameras: ['CAM-21', 'CAM-22', 'CAM-23', 'CAM-24'],
    totalVehicles: 165,
  },
  {
    id: 'J07', name: 'Yeshwanthpur Junction', location: 'Yeshwanthpur, Bengaluru',
    lat: 13.0247, lng: 77.5488, mapX: 200, mapY: 160,
    signals: {
      north: makeArm('red', 20, 32, 58, 9, 36),
      south: makeArm('green', 10, 32, 42, 5, 52),
      east: makeArm('red', 20, 28, 48, 7, 42),
      west: makeArm('red', 20, 28, 55, 8, 38),
    },
    mode: 'adaptive', congestionLevel: 'medium', cameras: ['CAM-25', 'CAM-26', 'CAM-27', 'CAM-28'],
    totalVehicles: 142,
  },
  {
    id: 'J08', name: 'Jayanagar Junction', location: '4th Block, Jayanagar, Bengaluru',
    lat: 12.9308, lng: 77.5831, mapX: 320, mapY: 340,
    signals: {
      north: makeArm('green', 25, 45, 35, 4, 58),
      south: makeArm('red', 20, 45, 40, 5, 54),
      east: makeArm('red', 20, 38, 38, 5, 55),
      west: makeArm('red', 20, 38, 32, 4, 60),
    },
    mode: 'fixed', congestionLevel: 'low', cameras: ['CAM-29', 'CAM-30', 'CAM-31', 'CAM-32'],
    totalVehicles: 88,
  },
  {
    id: 'J09', name: 'Rajajinagar Junction', location: 'Rajajinagar, Bengaluru',
    lat: 12.9950, lng: 77.5521, mapX: 180, mapY: 240,
    signals: {
      north: makeArm('red', 18, 35, 72, 13, 25),
      south: makeArm('red', 18, 35, 65, 11, 30),
      east: makeArm('green', 17, 35, 58, 9, 38),
      west: makeArm('red', 18, 30, 70, 12, 26),
    },
    mode: 'adaptive', congestionLevel: 'high', cameras: ['CAM-33', 'CAM-34', 'CAM-35', 'CAM-36'],
    totalVehicles: 201,
  },
  {
    id: 'J10', name: 'Electronic City Junction', location: 'Electronic City Phase 1, Bengaluru',
    lat: 12.8452, lng: 77.6602, mapX: 500, mapY: 440,
    signals: {
      north: makeArm('red', 30, 28, 85, 19, 14),
      south: makeArm('yellow', 3, 28, 80, 17, 18),
      east: makeArm('red', 30, 25, 88, 21, 11),
      west: makeArm('red', 30, 25, 82, 18, 16),
    },
    mode: 'adaptive', congestionLevel: 'critical', cameras: ['CAM-37', 'CAM-38', 'CAM-39', 'CAM-40'],
    totalVehicles: 356, aiReason: 'IT park shift change causing surge — extended green recommended',
  },
  {
    id: 'J11', name: 'Whitefield Junction', location: 'Whitefield Main Road, Bengaluru',
    lat: 12.9698, lng: 77.7500, mapX: 660, mapY: 240,
    signals: {
      north: makeArm('green', 5, 30, 42, 6, 50),
      south: makeArm('red', 25, 30, 48, 7, 44),
      east: makeArm('red', 25, 28, 55, 8, 38),
      west: makeArm('red', 25, 28, 50, 7, 42),
    },
    mode: 'fixed', congestionLevel: 'medium', cameras: ['CAM-41', 'CAM-42', 'CAM-43', 'CAM-44'],
    totalVehicles: 134,
  },
  {
    id: 'J12', name: 'Airport Road Junction', location: 'HAL Airport Road, Bengaluru',
    lat: 12.9604, lng: 77.6388, mapX: 500, mapY: 200,
    signals: {
      north: makeArm('red', 22, 40, 52, 8, 42),
      south: makeArm('green', 18, 40, 45, 6, 50),
      east: makeArm('red', 22, 35, 58, 9, 36),
      west: makeArm('red', 22, 35, 62, 10, 30),
    },
    mode: 'fixed', congestionLevel: 'medium', cameras: ['CAM-45', 'CAM-46', 'CAM-47', 'CAM-48'],
    totalVehicles: 156,
  },
];

// ─── CAMERAS ──────────────────────────────────────────────────────────────────

export const CAMERAS: Camera[] = JUNCTIONS.flatMap((j, ji) =>
  (['north', 'south', 'east', 'west'] as const).map((dir, di) => ({
    id: `CAM-${String(ji * 4 + di + 1).padStart(2, '0')}`,
    name: `${j.name} - ${dir.charAt(0).toUpperCase() + dir.slice(1)} Approach`,
    junctionId: j.id,
    direction: dir,
    status: (ji === 2 && di === 3) ? 'offline' : 'online' as Camera['status'],
    resolution: '1920×1080',
    lat: j.lat + (dir === 'north' ? 0.002 : dir === 'south' ? -0.002 : 0),
    lng: j.lng + (dir === 'east' ? 0.002 : dir === 'west' ? -0.002 : 0),
  }))
);

// ─── VIOLATIONS ───────────────────────────────────────────────────────────────

const plates = [
  'KA 01 AB 1234', 'KA 05 MN 7823', 'MH 12 CD 5678', 'KA 03 EF 9012',
  'KA 51 GH 3456', 'KA 02 IJ 7890', 'TN 22 XY 4512', 'KA 19 PQ 8834',
  'AP 28 RS 2290', 'KA 04 TU 6677', 'KA 09 VW 1122', 'DL 8C AM 4433',
  'KA 50 ZA 9988', 'MH 02 BC 5544', 'KA 11 DE 3311',
];

const violationTypes: { type: ViolationType; fine: number; desc: string }[] = [
  { type: 'red_light_jump', fine: 1000, desc: 'Vehicle crossed stop line 2.3s after red signal' },
  { type: 'speeding', fine: 2000, desc: 'Vehicle detected at 82 km/h in 60 km/h zone' },
  { type: 'wrong_way', fine: 5000, desc: 'Vehicle travelling against traffic flow on one-way road' },
  { type: 'no_helmet', fine: 500, desc: 'Rider detected without helmet on two-wheeler' },
  { type: 'triple_riding', fine: 1000, desc: 'Three persons detected on two-wheeler' },
  { type: 'stop_line', fine: 500, desc: 'Vehicle crossed stop line while signal was red' },
  { type: 'no_parking', fine: 500, desc: 'Vehicle parked in no-parking zone' },
  { type: 'wrong_lane', fine: 500, desc: 'Two-wheeler detected in heavy vehicle lane' },
  { type: 'invalid_plate', fine: 5000, desc: 'Number plate partially obscured/tampered' },
  { type: 'restricted_zone', fine: 2000, desc: 'Vehicle entered restricted zone without permit' },
];

const minutesAgo = (m: number) => new Date(Date.now() - m * 60000);

export const VIOLATIONS: Violation[] = plates.map((plate, i) => {
  const vt = violationTypes[i % violationTypes.length];
  const j = JUNCTIONS[i % JUNCTIONS.length];
  return {
    id: `VIO-${String(2024001 + i)}`,
    plate,
    vehicleType: (['car', 'motorcycle', 'truck', 'bus', 'auto', 'suv'] as VehicleType[])[i % 6],
    type: vt.type,
    cameraId: j.cameras[i % 4],
    junctionId: j.id,
    junctionName: j.name,
    timestamp: minutesAgo(i * 4 + 2),
    confidence: 85 + (i * 7) % 14,
    fine: vt.fine,
    status: (['pending', 'pending', 'processing', 'challan_issued', 'paid'] as Violation['status'][])[i % 5],
    speed: vt.type === 'speeding' ? 82 + (i % 20) : undefined,
    evidenceDesc: vt.desc,
  };
});

// ─── VEHICLE PROFILES ─────────────────────────────────────────────────────────

export const VEHICLE_DB: Record<string, VehicleProfile> = {
  'KA 01 AB 1234': {
    plate: 'KA 01 AB 1234', owner: 'Rajesh Kumar', phone: '+91 98765 43210',
    vehicleType: 'car', make: 'Maruti Suzuki', model: 'Swift Dzire', color: 'White',
    registrationState: 'Karnataka', registrationDate: '2021-03-15', violations: 3, isTracked: false,
    detections: [
      { cameraId: 'CAM-01', junctionName: 'MG Road Junction', timestamp: minutesAgo(2), direction: 'Northbound', speed: 38, confidence: 94 },
      { cameraId: 'CAM-04', junctionName: 'MG Road Junction', timestamp: minutesAgo(8), direction: 'Eastbound', speed: 42, confidence: 91 },
      { cameraId: 'CAM-07', junctionName: 'Brigade Road Junction', timestamp: minutesAgo(15), direction: 'Northbound', speed: 35, confidence: 88 },
      { cameraId: 'CAM-12', junctionName: 'Silk Board Junction', timestamp: minutesAgo(28), direction: 'Westbound', speed: 22, confidence: 96 },
    ],
  },
  'KA 05 MN 7823': {
    plate: 'KA 05 MN 7823', owner: 'Priya Sharma', phone: '+91 87654 32109',
    vehicleType: 'motorcycle', make: 'Honda', model: 'Activa 6G', color: 'Blue',
    registrationState: 'Karnataka', registrationDate: '2022-07-22', violations: 1, isTracked: false,
    detections: [
      { cameraId: 'CAM-09', junctionName: 'Silk Board Junction', timestamp: minutesAgo(5), direction: 'Southbound', speed: 28, confidence: 89 },
    ],
  },
  'MH 12 CD 5678': {
    plate: 'MH 12 CD 5678', owner: 'Amit Desai', phone: '+91 76543 21098',
    vehicleType: 'truck', make: 'Tata Motors', model: 'LPT 2518', color: 'Red',
    registrationState: 'Maharashtra', registrationDate: '2019-11-08', violations: 7, isTracked: true,
    detections: [
      { cameraId: 'CAM-05', junctionName: 'Brigade Road Junction', timestamp: minutesAgo(3), direction: 'Westbound', speed: 35, confidence: 97 },
      { cameraId: 'CAM-09', junctionName: 'Silk Board Junction', timestamp: minutesAgo(18), direction: 'Southbound', speed: 28, confidence: 94 },
    ],
  },
};

// ─── INCIDENTS ────────────────────────────────────────────────────────────────

export const INCIDENTS: Incident[] = [
  {
    id: 'INC-001', type: 'collision', location: 'MG Road near Commercial Street',
    cameraId: 'CAM-01', junctionId: 'J01', junctionName: 'MG Road Junction',
    timestamp: minutesAgo(3), confidence: 89, severity: 'high',
    status: 'active',
    description: 'Two vehicles involved in rear-end collision on MG Road northbound lane. Lane partially blocked.',
  },
  {
    id: 'INC-002', type: 'breakdown', location: 'Silk Board Flyover - Entry Ramp',
    cameraId: 'CAM-09', junctionId: 'J03', junctionName: 'Silk Board Junction',
    timestamp: minutesAgo(8), confidence: 94, severity: 'high',
    status: 'police_notified',
    description: 'Bus breakdown on eastbound entry ramp. Vehicle occupying left lane. Causing significant queue.',
  },
  {
    id: 'INC-003', type: 'road_blockage', location: 'Electronic City Elevated Expressway',
    cameraId: 'CAM-37', junctionId: 'J10', junctionName: 'Electronic City Junction',
    timestamp: minutesAgo(13), confidence: 91, severity: 'critical',
    status: 'emergency_notified',
    description: 'Overturned goods vehicle blocking two lanes. Cargo spilled on road. Emergency services dispatched.',
  },
  {
    id: 'INC-004', type: 'abnormal_slowdown', location: 'Whitefield Main Road near ITPL',
    cameraId: 'CAM-41', junctionId: 'J11', junctionName: 'Whitefield Junction',
    timestamp: minutesAgo(19), confidence: 85, severity: 'medium',
    status: 'active',
    description: 'Unusual traffic slowdown detected. Average speed dropped 60% in last 5 minutes. No visible obstruction.',
  },
  {
    id: 'INC-005', type: 'fallen_object', location: 'Marathahalli Bridge - Southbound',
    cameraId: 'CAM-21', junctionId: 'J06', junctionName: 'Marathahalli Junction',
    timestamp: minutesAgo(26), confidence: 79, severity: 'medium',
    status: 'active',
    description: 'Large fallen tree branch detected on southbound lane. Vehicles swerving to avoid.',
  },
];

// ─── EMERGENCY VEHICLES ───────────────────────────────────────────────────────

export const EMERGENCY_VEHICLES: EmergencyVehicle[] = [
  {
    id: 'EMG-001', type: 'ambulance', vehicleNo: 'KA-01 AMB 1042',
    origin: 'Koramangala (Incident Site)', destination: 'Apollo Hospital, Bannerghatta Road',
    currentJunction: 'J05', routeJunctions: ['J05', 'J08', 'J09'],
    status: 'en_route', corridorActive: true,
    detectedAt: 'CAM-17', eta: 8,
  },
  {
    id: 'EMG-002', type: 'fire_brigade', vehicleNo: 'KA-01 FIRE 231',
    origin: 'Rajajinagar Fire Station', destination: 'Electronic City Incident',
    currentJunction: 'J09', routeJunctions: ['J09', 'J08', 'J03', 'J10'],
    status: 'active', corridorActive: true,
    detectedAt: 'CAM-33', eta: 14,
  },
];

// ─── FINE RULES ───────────────────────────────────────────────────────────────

export const FINE_RULES: Record<ViolationType, { fine: number; points: number; description: string }> = {
  red_light_jump: { fine: 1000, points: 2, description: 'Jumping Red Signal — Section 119, MV Act' },
  speeding: { fine: 2000, points: 3, description: 'Over Speeding — Section 183, MV Act' },
  wrong_way: { fine: 5000, points: 4, description: 'Driving Against Traffic — Section 184, MV Act' },
  no_helmet: { fine: 500, points: 1, description: 'Not Wearing Helmet — Section 129, MV Act' },
  triple_riding: { fine: 1000, points: 2, description: 'Triple Riding — Section 128, MV Act' },
  stop_line: { fine: 500, points: 1, description: 'Stop Line Violation — Section 119, MV Act' },
  no_parking: { fine: 500, points: 1, description: 'Parking Violation — Section 122, MV Act' },
  wrong_lane: { fine: 500, points: 1, description: 'Wrong Lane — Section 112, MV Act' },
  invalid_plate: { fine: 5000, points: 4, description: 'Invalid/Tampered Number Plate — Section 39, MV Act' },
  restricted_zone: { fine: 2000, points: 2, description: 'Restricted Zone Entry — Local Traffic Act' },
};

// ─── HELPERS ──────────────────────────────────────────────────────────────────

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
  accident: 'Accident', collision: 'Vehicle Collision', breakdown: 'Vehicle Breakdown',
  road_blockage: 'Road Blockage', fallen_object: 'Fallen Object',
  fire_smoke: 'Fire / Smoke', abnormal_slowdown: 'Abnormal Slowdown',
};

export const congestionColor = {
  low: '#16A34A', medium: '#D97706', high: '#EA580C', critical: '#DC2626',
};

export const vehicleColors = ['#E5E7EB', '#1E40AF', '#DC2626', '#16A34A', '#7C3AED', '#D97706', '#374151', '#0F766E'];
