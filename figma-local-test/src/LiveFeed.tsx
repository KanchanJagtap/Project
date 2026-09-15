import { useState, useEffect, useRef, useCallback } from 'react';
import { api } from './api/client';
import { CamerasListResponse, ProcessingStatusResponse } from './api/types';
import { usePolling } from './hooks/usePolling';

import { JUNCTIONS, type Junction, type SignalArm } from './data';

// ─── Types ────────────────────────────────────────────────────────────────────

interface SignalPhaseState {
  type: 'green' | 'yellow' | 'allred';
  direction: 'NS' | 'EW';
  timer: number;
  greenDuration: number;
  nextDirection: 'NS' | 'EW';
  aiReason: string;
  pressure: { north: number; south: number; east: number; west: number };
}

type ArmDir = 'north' | 'south' | 'east' | 'west';
type SigColor = 'red' | 'yellow' | 'green';
type CVType = 'car' | 'truck' | 'bus' | 'motorcycle' | 'auto' | 'suv';

interface CanvasVehicle {
  id: string;
  plate: string;
  type: CVType;
  y: number;
  lane: number;
  color: string;
  velocity: number;
  maxVel: number;
  detected: boolean;
  confidence: number;
  bboxAlpha: number;
}

// ─── Vehicle config ───────────────────────────────────────────────────────────

const VBASE: Record<CVType, { w: number; h: number; label: string; colorRange: string }> = {
  car:        { w: 30, h: 16, label: 'CAR',   colorRange: 'multi'  },
  suv:        { w: 35, h: 18, label: 'SUV',   colorRange: 'multi'  },
  motorcycle: { w: 12, h: 8,  label: 'MOTO',  colorRange: 'dark'   },
  auto:       { w: 22, h: 14, label: 'AUTO',  colorRange: 'yellow' },
  bus:        { w: 52, h: 22, label: 'BUS',   colorRange: 'blue'   },
  truck:      { w: 50, h: 20, label: 'TRUCK', colorRange: 'red'    },
};

const VTYPES: CVType[] = ['car', 'car', 'car', 'suv', 'motorcycle', 'auto', 'bus', 'truck'];

const PLATES_MH = [
  'MH12AB1234', 'MH14CD5678', 'MH15EF9012', 'MH16GH3456',
  'MH17JK7890', 'MH18LM2468', 'MH12AB1234', 'MH14CD5678',
  'MH15EF9012', 'MH16GH3456', 'MH17JK7890', 'MH18LM2468',
];

const MULTI_COLORS = ['#E5E7EB','#1E40AF','#16A34A','#7C3AED','#D97706','#374151','#0F766E','#9F1239'];
const DARK_COLORS  = ['#1F2937','#111827','#0F172A','#27272A'];
const BLUE_COLORS  = ['#1D4ED8','#1E40AF','#2563EB'];
const RED_COLORS   = ['#DC2626','#B91C1C','#9B1C1C'];

function getVehicleColor(type: CVType, seed: number): string {
  switch (type) {
    case 'auto':       return '#F59E0B';
    case 'bus':        return BLUE_COLORS[seed % BLUE_COLORS.length];
    case 'truck':      return RED_COLORS[seed % RED_COLORS.length];
    case 'motorcycle': return DARK_COLORS[seed % DARK_COLORS.length];
    default:           return MULTI_COLORS[seed % MULTI_COLORS.length];
  }
}

function initVehicles(seed: number): CanvasVehicle[] {
  return Array.from({ length: 10 }, (_, i) => {
    const type = VTYPES[(seed + i) % VTYPES.length];
    const maxVel = 0.0018 + ((seed * 7 + i) % 7) * 0.0004;
    return {
      id: `v${seed}-${i}`,
      plate: PLATES_MH[(seed + i) % PLATES_MH.length],
      type,
      y: -0.1 - (i / 10) * 0.8,
      lane: i % 3,
      color: getVehicleColor(type, seed + i),
      velocity: maxVel * 0.6,
      maxVel,
      detected: false,
      confidence: 84 + ((seed + i * 3) % 14),
      bboxAlpha: 0,
    };
  });
}

// ─── Signal state machine helpers ─────────────────────────────────────────────

function calcArmPressure(arm: SignalArm, hasLargeVehicle: boolean): number {
  let p = (arm.vehicleDensity / 100) * 30;
  p += Math.min(arm.queueLength / 20, 1) * 25;
  p += Math.max(0, (80 - arm.avgSpeed) / 80) * 15;
  p += Math.min(arm.waitingTime / 120, 1) * 15;
  p += (arm.occupancy / 100) * 10;

  if (hasLargeVehicle) p += 15;

  return Math.min(100, Math.round(p));
}

function computeJunctionPressure(junction: Junction) {
  const high =
    junction.congestionLevel === 'critical' ||
    junction.congestionLevel === 'high';

  const r = () => Math.random();

  return {
    north: calcArmPressure(
      junction.signals.north,
      high && r() > 0.6,
    ),
    south: calcArmPressure(
      junction.signals.south,
      high && r() > 0.7,
    ),
    east: calcArmPressure(
      junction.signals.east,
      high && r() > 0.5,
    ),
    west: calcArmPressure(
      junction.signals.west,
      high && r() > 0.65,
    ),
  };
}

function computeGreenDuration(dirPressure: number): number {
  const normalized = Math.min(dirPressure / 100, 1);

  return Math.max(
    15,
    Math.min(45, Math.round(20 + normalized * 25)),
  );
}

function getNextDirection(direction: ArmDir): ArmDir {
  const sequence: ArmDir[] = [
    'north',
    'east',
    'south',
    'west',
  ];

  const index = sequence.indexOf(direction);

  return sequence[(index + 1) % sequence.length];
}

function getArmSignalColor(
  arm: ArmDir,
  phase: SignalPhaseState,
): SigColor {
  if (phase.type === 'allred') {
    return 'red';
  }

  if (arm !== phase.direction) {
    return 'red';
  }

  if (phase.type === 'green') {
    return 'green';
  }

  return 'yellow';
}

function genAiReason(
  direction: ArmDir,
  greenDuration: number,
  pressure: {
    north: number;
    south: number;
    east: number;
    west: number;
  },
  junction: Junction,
): string {
  const dirPressure = pressure[direction];
  const base = greenDuration - 20;

  const directionLabel: Record<ArmDir, string> = {
    north: 'North approach',
    east: 'East approach',
    south: 'South approach',
    west: 'West approach',
  };

  const currentApproach = directionLabel[direction];

  if (junction.congestionLevel === 'critical') {
    return `Critical congestion detected — ${currentApproach} at ${dirPressure}% pressure. Green time maximized.`;
  }

  if (base >= 15) {
    return `High queue + waiting time on ${currentApproach} — Green extended by ${base}s over baseline.`;
  }

  if (base <= -3) {
    return `${currentApproach} pressure is lower — cycle shortened by ${Math.abs(base)}s to serve other approaches.`;
  }

  if (
    junction.aiReason?.includes('large vehicle') ||
    junction.aiReason?.includes('truck')
  ) {
    return `Large vehicle detected on ${currentApproach} — additional green time allocated to clear lane.`;
  }

  return `Adaptive control selected ${currentApproach} at ${dirPressure}% pressure — standard ${greenDuration}s green phase.`;
}

// ─── useJunctionSignal hook ───────────────────────────────────────────────────

function useJunctionSignal(junction: Junction, seed: number) {
  const jRef = useRef(junction);
  jRef.current = junction;

  const [phase, setPhase] = useState<SignalPhaseState>(() => {
    const sequence: ArmDir[] = [
      'north',
      'east',
      'south',
      'west',
    ];

    const dir = sequence[seed % sequence.length];
    const pressure = computeJunctionPressure(junction);
    const greenDuration = computeGreenDuration(pressure[dir]);

    return {
      type: 'green',
      direction: dir,
      timer: greenDuration,
      greenDuration,
      nextDirection: getNextDirection(dir),
      aiReason: 'System initialized — sequential adaptive cycle.',
      pressure,
    };
  });

  useEffect(() => {
    const id = setInterval(() => {
      setPhase(prev => {
        if (prev.timer > 1) {
          return {
            ...prev,
            timer: prev.timer - 1,
          };
        }

        // Green → Yellow
        if (prev.type === 'green') {
          return {
            ...prev,
            type: 'yellow',
            timer: 4,
          };
        }

        // Yellow → All Red
        if (prev.type === 'yellow') {
          return {
            ...prev,
            type: 'allred',
            timer: 2,
          };
        }

        // All Red → next directional green
        const j = jRef.current;
        const pressure = computeJunctionPressure(j);
        const nextDir = prev.nextDirection;
        const greenDuration = computeGreenDuration(
          pressure[nextDir],
        );

        return {
          type: 'green',
          direction: nextDir,
          timer: greenDuration,
          greenDuration,
          nextDirection: getNextDirection(nextDir),
          aiReason: genAiReason(
            nextDir,
            greenDuration,
            pressure,
            j,
          ),
          pressure,
        };
      });
    }, 1000);

    return () => clearInterval(id);
  }, []);

  const armSignals: Record<ArmDir, SigColor> = {
    north: getArmSignalColor('north', phase),
    south: getArmSignalColor('south', phase),
    east: getArmSignalColor('east', phase),
    west: getArmSignalColor('west', phase),
  };

  return {
    armSignals,
    phaseState: phase,
  };
}

// ─── CCTV Canvas ──────────────────────────────────────────────────────────────

const STOP_Y    = 0.69;
const CANVAS_H  = 340;
const CANVAS_W  = 560;

interface CCTVProps {
  seed: number;
  signalColor: SigColor;
  direction: ArmDir;
  density: number;
  onDetectionsChange: (d: CanvasVehicle[]) => void;
}

function CCTVCanvas({ seed, signalColor, direction, density, onDetectionsChange }: CCTVProps) {
  const canvasRef  = useRef<HTMLCanvasElement>(null);
  const vehiclesRef = useRef<CanvasVehicle[]>(initVehicles(seed));
  const frameRef   = useRef<number>(0);
  const signalRef  = useRef<SigColor>(signalColor);
  const detectionsRef = useRef<CanvasVehicle[]>([]);
  signalRef.current = signalColor;

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const W = canvas.width, H = canvas.height;
    const sig = signalRef.current;

    // ── Vehicle physics: follow-the-leader model ──
    const sortedVehicles = [...vehiclesRef.current].sort((a, b) => a.y - b.y);
    vehiclesRef.current = sortedVehicles.map(v => {
      // Find leader: same lane, closest vehicle ahead (higher y)
      const leader = sortedVehicles.find(
        o => o.id !== v.id && o.lane === v.lane && o.y > v.y && o.y - v.y < 0.32
      );
      const leaderHeight = leader
        ? (VBASE[leader.type].h * (0.22 + 0.78 * leader.y)) / (H * 0.72)
        : 0;

      let stopTarget: number;
      if (leader) {
        stopTarget = leader.y - leaderHeight - 0.012;
      } else if (sig === 'red' || sig === 'yellow') {
        stopTarget = STOP_Y;
      } else {
        stopTarget = 2.0;
      }

      const distToStop = stopTarget - v.y;
      let velocity = v.velocity;

      if (distToStop <= 0.002) {
        velocity = 0;
      } else if (distToStop < 0.22) {
        velocity = v.maxVel * Math.pow(Math.max(0, distToStop / 0.22), 0.65);
      } else if (sig === 'green') {
        velocity = Math.min(v.maxVel, velocity + 0.00015);
      }
      velocity = Math.max(0, velocity);
      const newY = v.y + velocity;

      if (newY > 1.1) {
        const type = VTYPES[(seed + Math.floor(Math.random() * 100)) % VTYPES.length];
        return {
          ...v,
          type,
          color: getVehicleColor(type, seed + Math.floor(Math.random() * 100)),
          y: -(0.05 + Math.random() * 0.2),
          velocity: v.maxVel * 0.5,
          detected: false,
          bboxAlpha: 0,
        };
      }
      const detected = newY > 0.3 ? true : v.detected;
      const bboxAlpha = detected ? Math.min(1, v.bboxAlpha + 0.07) : v.bboxAlpha;
      return { ...v, y: newY, velocity, detected, bboxAlpha };
    });

    // ── Background ──
    const bgGrad = ctx.createLinearGradient(0, 0, 0, H);
    bgGrad.addColorStop(0, '#080b14');
    bgGrad.addColorStop(0.35, '#111520');
    bgGrad.addColorStop(1, '#1a1d28');
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, W, H);

    // Bokeh city lights
    const bokehs: [number, number, number, string, number][] = [
      [0.08,0.06,20,'#FF6B35',0.55],[0.18,0.03,14,'#FFF176',0.45],
      [0.32,0.09,26,'#FFB300',0.5], [0.45,0.02,16,'#FFFFFF',0.35],
      [0.55,0.11,22,'#FF6B35',0.45],[0.68,0.05,18,'#FFF176',0.55],
      [0.78,0.08,28,'#FFB300',0.4], [0.88,0.04,12,'#FFFFFF',0.45],
      [0.12,0.14,10,'#FF3D00',0.25],[0.42,0.16,12,'#FF6B35',0.3],
      [0.72,0.12,16,'#FFF176',0.35],[0.93,0.1, 11,'#FFFFFF',0.3],
    ];
    bokehs.forEach(([bx,by,br,bc,bo]) => {
      const grd = ctx.createRadialGradient(bx*W, by*H, 0, bx*W, by*H, br);
      const hex = Math.round(bo * 255).toString(16).padStart(2,'0');
      grd.addColorStop(0, bc + hex);
      grd.addColorStop(1, 'transparent');
      ctx.fillStyle = grd;
      ctx.beginPath();
      ctx.arc(bx*W, by*H, br, 0, Math.PI*2);
      ctx.fill();
    });

    // Building silhouettes
    const buildings = [
      [0.02,0.07,0.22],[0.15,0.05,0.14],[0.28,0.08,0.18],[0.45,0.05,0.16],
      [0.6, 0.07,0.2], [0.72,0.06,0.14],[0.82,0.08,0.16],[0.91,0.05,0.1],
    ];
    buildings.forEach(([bx,bh,bw]) => {
      ctx.fillStyle = '#060912';
      ctx.fillRect(bx*W, (0.28-bh)*H, bw*W, bh*H);
      for (let wy=0; wy<4; wy++) for (let wx=0; wx<3; wx++) {
        if (Math.sin(seed + bx*100 + wy*7 + wx*3) > 0.1) {
          ctx.fillStyle = `rgba(255,240,180,${0.25+Math.abs(Math.sin(seed+wx+wy))*0.3})`;
          ctx.fillRect((bx+0.01+wx*0.045)*W, (0.28-bh+0.01+wy*0.016)*H, 3, 4);
        }
      }
    });

    // Horizon line
    ctx.fillStyle = '#1e2130';
    ctx.fillRect(0, H*0.27, W, H*0.02);

    // ── Road ──
    const vanishX = W * 0.5;
    const roadTopW = W * 0.16;
    const roadGrad = ctx.createLinearGradient(0, H*0.28, 0, H);
    roadGrad.addColorStop(0, '#181b24');
    roadGrad.addColorStop(0.4, '#1e2230');
    roadGrad.addColorStop(1, '#252836');
    ctx.fillStyle = roadGrad;
    ctx.beginPath();
    ctx.moveTo(vanishX - roadTopW/2, H*0.28);
    ctx.lineTo(vanishX + roadTopW/2, H*0.28);
    ctx.lineTo(W, H);
    ctx.lineTo(0, H);
    ctx.closePath();
    ctx.fill();

    // Kerb
    ctx.fillStyle = '#14171f';
    ctx.beginPath();
    ctx.moveTo(0, H*0.28); ctx.lineTo(vanishX - roadTopW/2, H*0.28); ctx.lineTo(0, H); ctx.closePath(); ctx.fill();
    ctx.beginPath();
    ctx.moveTo(W, H*0.28); ctx.lineTo(vanishX + roadTopW/2, H*0.28); ctx.lineTo(W, H); ctx.closePath(); ctx.fill();

    const getLaneX = (lane: number, yFrac: number) => {
      const t = Math.min(1, Math.max(0, (yFrac - 0.28) / 0.72));
      const halfW = (W/2)*t + (roadTopW/2)*(1-t);
      const laneW = halfW*2 / 3;
      return vanishX + (lane - 1) * laneW;
    };

    // Dashed lane dividers (white)
    ctx.strokeStyle = 'rgba(255,255,255,0.45)';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([14,14]);
    for (let dy = H*0.3; dy < H; dy += 30) {
      const yF = dy/H;
      const dashLen = 14 * ((yF - 0.28)/0.72 + 0.2);
      for (let li = 0; li < 2; li++) {
        const lineX = li === 0 ? getLaneX(0, yF) : getLaneX(2, yF);
        ctx.beginPath(); ctx.moveTo(lineX, dy); ctx.lineTo(lineX, dy + dashLen); ctx.stroke();
      }
    }

    // Double yellow center divider (Indian road standard)
    ctx.setLineDash([]);
    for (let side = -1; side <= 1; side += 2) {
      for (let dy2 = H*0.29; dy2 < H; dy2 += 1) {
        const yF2 = dy2/H;
        const t2 = (yF2-0.28)/0.72;
        const cx = vanishX + side * (2 + t2*3);
        const alpha = 0.5 + t2*0.4;
        ctx.fillStyle = `rgba(255,200,0,${alpha})`;
        ctx.fillRect(cx, dy2, 1+t2*1.5, 1);
      }
    }

    // Zebra crossing at stop line
    const stopCanvasY = H*0.28 + STOP_Y * H*0.72;
    const zebraH = 14 + STOP_Y*20;
    const zebraL = getLaneX(0, STOP_Y) - 20;
    const zebraR = getLaneX(2, STOP_Y) + 20;
    const stripeCount = 8;
    const stripeW = (zebraR - zebraL) / stripeCount;
    for (let s=0; s<stripeCount; s++) {
      if (s % 2 === 0) {
        ctx.fillStyle = 'rgba(255,255,255,0.18)';
        ctx.fillRect(zebraL + s*stripeW, stopCanvasY - zebraH, stripeW, zebraH);
      }
    }

    // Stop line (solid white)
    ctx.strokeStyle = 'rgba(255,255,255,0.8)';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(getLaneX(0, STOP_Y) - 20, stopCanvasY);
    ctx.lineTo(getLaneX(2, STOP_Y) + 20, stopCanvasY);
    ctx.stroke();

    // Road reflections (headlight on wet road)
    [[0.35,0.62,'#FF6B00'],[0.52,0.70,'#FF4400'],[0.45,0.55,'#FFA500']].forEach(
      ([rx,ry,rc]) => {
        const grd2 = ctx.createLinearGradient(0, (ry as number)*H, 0, ((ry as number)+0.07)*H);
        grd2.addColorStop(0, (rc as string)+'30');
        grd2.addColorStop(1, 'transparent');
        ctx.fillStyle = grd2;
        ctx.fillRect(((rx as number)-0.05)*W, (ry as number)*H, 0.1*W, 0.07*H);
      }
    );

    // ── Draw vehicles ──
    vehiclesRef.current.forEach(v => {
      if (v.y < -0.05 || v.y > 1.15) return;
      const canvasY = H*0.28 + v.y * H*0.72;
      const scale   = 0.22 + 0.78 * Math.max(0, v.y);
      const base    = VBASE[v.type];
      const vw = base.w * scale, vh = base.h * scale;
      const laneX = getLaneX(v.lane, v.y);

      // Shadow
      ctx.fillStyle = `rgba(0,0,0,${0.28*scale})`;
      ctx.beginPath();
      ctx.ellipse(laneX, canvasY, vw*0.5, vh*0.15, 0, 0, Math.PI*2);
      ctx.fill();

      if (v.type === 'auto') {
        // Auto-rickshaw: distinctive yellow-black body
        // Main body (yellow-black)
        ctx.fillStyle = '#F59E0B';
        ctx.beginPath();
        (ctx as CanvasRenderingContext2D & { roundRect: (x: number, y: number, w: number, h: number, r: number) => void }).roundRect(laneX - vw/2, canvasY - vh, vw, vh*0.75, 2*scale);
        ctx.fill();
        // Black hood / top
        ctx.fillStyle = '#1C1917';
        ctx.beginPath();
        (ctx as CanvasRenderingContext2D & { roundRect: (x: number, y: number, w: number, h: number, r: number) => void }).roundRect(laneX - vw*0.45, canvasY - vh, vw*0.9, vh*0.55, 2*scale);
        ctx.fill();
        // Yellow canopy stripe
        ctx.fillStyle = '#FBBF24';
        ctx.fillRect(laneX - vw*0.45, canvasY - vh*0.8, vw*0.9, vh*0.1);
        // Front (open)
        ctx.fillStyle = 'rgba(0,0,0,0.5)';
        ctx.fillRect(laneX - vw*0.45, canvasY - vh*0.75, vw*0.9, vh*0.25);
        // Three wheels (flat bottom representation)
        ctx.fillStyle = '#292524';
        [-0.35, 0.35].forEach(dx => {
          ctx.beginPath();
          ctx.ellipse(laneX + vw*dx, canvasY, 3*scale, 2*scale, 0, 0, Math.PI*2);
          ctx.fill();
        });
      } else {
        // Standard vehicle body
        const bodyColors: Record<CVType, string> = {
          car: v.color, suv: v.color, motorcycle: v.color,
          auto: v.color, bus: v.color, truck: v.color,
        };
        ctx.fillStyle = bodyColors[v.type];
        ctx.beginPath();
        (ctx as CanvasRenderingContext2D & { roundRect: (x: number, y: number, w: number, h: number, r: number) => void }).roundRect(laneX - vw/2, canvasY - vh, vw, vh, 2.5*scale);
        ctx.fill();

        if (v.type === 'motorcycle') {
          // Rider silhouette
          ctx.fillStyle = '#1C1917';
          ctx.beginPath();
          ctx.arc(laneX, canvasY - vh*1.2, 3*scale, 0, Math.PI*2);
          ctx.fill();
          ctx.fillRect(laneX - 2*scale, canvasY - vh*1.1, 4*scale, vh*0.8);
        } else {
          // Windshield
          ctx.fillStyle = 'rgba(140,210,255,0.5)';
          ctx.beginPath();
          (ctx as CanvasRenderingContext2D & { roundRect: (x: number, y: number, w: number, h: number, r: number) => void }).roundRect(laneX - vw*0.28, canvasY - vh*0.88, vw*0.56, vh*0.3, 1.5);
          ctx.fill();

          if (v.type === 'bus' || v.type === 'truck') {
            // Side windows
            for (let w2=0; w2<3; w2++) {
              ctx.fillStyle = 'rgba(140,210,255,0.35)';
              ctx.fillRect(laneX - vw*0.42 + w2*vw*0.28, canvasY - vh*0.55, vw*0.2, vh*0.2);
            }
          }
        }

        // Headlights glow
        [-0.35, 0.35].forEach(dx => {
          const hx = laneX + vw*dx, hy = canvasY - vh*0.06;
          const grd3 = ctx.createRadialGradient(hx, hy, 0, hx, hy, 7*scale);
          grd3.addColorStop(0, 'rgba(255,248,200,0.9)');
          grd3.addColorStop(1, 'transparent');
          ctx.fillStyle = grd3;
          ctx.beginPath(); ctx.arc(hx, hy, 7*scale, 0, Math.PI*2); ctx.fill();
        });

        // Tail lights
        ctx.fillStyle = '#DC2626';
        [-0.35, 0.35].forEach(dx => {
          ctx.beginPath();
          ctx.arc(laneX + vw*dx, canvasY - vh*0.92, 2.5*scale, 0, Math.PI*2);
          ctx.fill();
        });
      }

      // ── AI bounding box ──
      if (v.detected && v.bboxAlpha > 0.15 && v.y > 0.3) {
        const pad = 5*scale;
        const bx2 = laneX - vw/2 - pad, by2 = canvasY - vh - pad;
        const bw2 = vw + pad*2, bh2 = vh + pad*2;
        const a = v.bboxAlpha;

        ctx.save();
        ctx.strokeStyle = `rgba(34,197,94,${a})`;
        ctx.lineWidth = 1.5;
        ctx.setLineDash([5,4]);
        ctx.strokeRect(bx2, by2, bw2, bh2);
        ctx.restore();

        // Corner brackets
        const cs = 7*scale;
        ctx.strokeStyle = `rgba(34,197,94,${a})`;
        ctx.lineWidth = 2;
        ctx.setLineDash([]);
        [
          [bx2, by2, cs, cs], [bx2+bw2-cs, by2, -cs, cs],
          [bx2, by2+bh2-cs, cs, -cs], [bx2+bw2-cs, by2+bh2-cs, -cs, -cs],
        ].forEach(([cx2,cy2,dx2,dy2]) => {
          ctx.beginPath();
          ctx.moveTo(cx2 + (dx2 > 0 ? 0 : dx2), cy2);
          ctx.lineTo(cx2, cy2);
          ctx.lineTo(cx2, cy2 + (dy2 > 0 ? 0 : dy2));
          ctx.stroke();
        });

        // Plate below box
        if (v.y > 0.42 && a > 0.5) {
          const labelW = Math.max(56, v.plate.length*5.5)*scale;
          const lx2 = laneX - labelW/2;
          const ly2 = by2 + bh2 + 2;
          ctx.fillStyle = `rgba(34,197,94,${a*0.9})`;
          ctx.fillRect(lx2, ly2, labelW, 12*scale);
          ctx.fillStyle = `rgba(0,0,0,${a})`;
          ctx.font = `bold ${Math.round(7*scale)}px JetBrains Mono, monospace`;
          ctx.textAlign = 'center';
          ctx.fillText(v.plate, laneX, ly2 + 8*scale);

          // Type + conf + lane (left of box)
          if (bx2 > 60) {
            ctx.fillStyle = `rgba(0,0,0,${a*0.75})`;
            ctx.fillRect(bx2-58, by2, 54, 38*scale);
            ctx.fillStyle = `rgba(34,197,94,${a})`;
            ctx.font = `bold ${Math.round(7*scale)}px sans-serif`;
            ctx.textAlign = 'center';
            ctx.fillText(VBASE[v.type].label, bx2-31, by2 + 10*scale);
            ctx.fillStyle = `rgba(255,255,255,${a*0.8})`;
            ctx.fillText(`${v.confidence}%`, bx2-31, by2 + 20*scale);
            ctx.fillStyle = `rgba(148,163,184,${a*0.7})`;
            ctx.fillText(`L${v.lane+1}`, bx2-31, by2 + 30*scale);
          }
          ctx.textAlign = 'left';
        }
      }
    });

    // ── Film grain ──
    const imgData = ctx.getImageData(0, 0, W, H);
    const d = imgData.data;
    for (let i=0; i<d.length; i+=20) {
      const noise = (Math.random()-0.5)*10;
      d[i]   = Math.min(255, Math.max(0, d[i]+noise));
      d[i+1] = Math.min(255, Math.max(0, d[i+1]+noise));
      d[i+2] = Math.min(255, Math.max(0, d[i+2]+noise));
    }
    ctx.putImageData(imgData, 0, 0);

    // ── Vignette ──
    const vig = ctx.createRadialGradient(W/2, H/2, H*0.28, W/2, H/2, H*0.85);
    vig.addColorStop(0, 'transparent');
    vig.addColorStop(1, 'rgba(0,0,0,0.5)');
    ctx.fillStyle = vig;
    ctx.fillRect(0, 0, W, H);

    // Timestamp / direction stamp
    const now = new Date().toLocaleTimeString('en-IN', { hour12: false });
    ctx.fillStyle = 'rgba(0,0,0,0.5)';
    ctx.fillRect(0, H-22, W, 22);
    ctx.fillStyle = 'rgba(255,255,255,0.55)';
    ctx.font = '9px JetBrains Mono, monospace';
    ctx.textAlign = 'left';
    ctx.fillText(`${now} | ${direction.toUpperCase()} APPROACH`, 8, H-7);

    // Report detections
    const newDetections = vehiclesRef.current.filter(v => v.detected && v.y > 0.45);
    if (JSON.stringify(newDetections.map(v=>v.id)) !== JSON.stringify(detectionsRef.current.map(v=>v.id))) {
      detectionsRef.current = newDetections;
      onDetectionsChange([...newDetections]);
    }

    frameRef.current = requestAnimationFrame(draw);
  }, [seed, direction, onDetectionsChange]);

  useEffect(() => {
    frameRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frameRef.current);
  }, [draw]);

  return <canvas ref={canvasRef} width={CANVAS_W} height={CANVAS_H} className="w-full block" />;
}

// ─── AI Decision Panel ────────────────────────────────────────────────────────

function AIDecisionPanel({ phase }: { phase: SignalPhaseState }) {
  const { pressure } = phase;
  const arms: ArmDir[] = ['north', 'south', 'east', 'west'];
  const maxPressure = Math.max(pressure.north, pressure.south, pressure.east, pressure.west);
  const phaseLabel = phase.type === 'allred' ? 'ALL RED' : `${phase.direction} ${phase.type.toUpperCase()}`;

  return (
    <div className="px-4 py-3" style={{ background: '#0F172A', borderTop: '1px solid #1E293B' }}>
      <div className="flex items-center gap-2 mb-2">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#818CF8" strokeWidth="2.5">
          <path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z"/><path d="M12 8v4l3 3"/>
        </svg>
        <span className="text-xs font-bold" style={{ color: '#818CF8' }}>AI Signal Decision</span>
        <span className="ml-auto text-xs mono px-2 py-0.5 rounded"
          style={{
            background: phase.type === 'green' ? '#14532D' : phase.type === 'yellow' ? '#713F12' : '#1C1C2E',
            color: phase.type === 'green' ? '#22C55E' : phase.type === 'yellow' ? '#F59E0B' : '#94A3B8',
          }}>
          {phaseLabel}
        </span>
        <span className="text-xs" style={{ color: '#475569' }}>→ next: {phase.nextDirection}</span>
      </div>

      <div className="text-xs mb-2.5 italic" style={{ color: '#94A3B8', lineHeight: 1.4 }}>
        "{phase.aiReason}"
      </div>

      <div className="grid grid-cols-4 gap-1.5">
        {arms.map(arm => {
          const val = pressure[arm];
          const isMax = val === maxPressure;
          const barColor = isMax ? '#DC2626' : val > 60 ? '#D97706' : '#1D4ED8';
          return (
            <div key={arm}>
              <div className="flex justify-between text-xs mb-0.5">
                <span className="uppercase font-bold" style={{ color: '#64748B' }}>{arm[0]}</span>
                <span className="font-bold" style={{ color: isMax ? '#DC2626' : '#94A3B8' }}>{val}%</span>
              </div>
              <div className="h-1.5 rounded-full overflow-hidden" style={{ background: '#1E293B' }}>
                <div className="h-full rounded-full transition-all duration-500"
                  style={{ width: `${val}%`, background: barColor }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Camera Card ──────────────────────────────────────────────────────────────

const DIR_LABELS = ['North Lane', 'South Lane', 'East Lane', 'West Lane'] as const;
type DirLabel = typeof DIR_LABELS[number];
const DIR_ARMS: ArmDir[] = ['north', 'south', 'east', 'west'];

function CameraCard({ junction, cardIndex, onJunctionView, camData }: {
  junction: Junction;
  cardIndex: number;
  onJunctionView: (j: Junction) => void;
  camData?: CamerasListResponse | null;
}) {
  const [activeDir, setActiveDir] = useState<DirLabel>('North Lane');
  const [detections, setDetections] = useState<CanvasVehicle[]>([]);
  const { armSignals, phaseState } = useJunctionSignal(junction, cardIndex);

  const dirIndex = DIR_LABELS.indexOf(activeDir);
  const armKey   = DIR_ARMS[dirIndex];
  const sigColor = armSignals[armKey];
  const sig      = junction.signals[armKey];

  const sigDisplay: Record<SigColor, string> = { red: '#DC2626', yellow: '#F59E0B', green: '#16A34A' };
  const camId = `SIG${String(cardIndex * 4 + dirIndex + 1).padStart(3, '0')}`;

  return (
    <div className="rounded-2xl overflow-hidden flex flex-col" style={{ background: '#1E293B', border: '1px solid #334155' }}>
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3" style={{ background: '#1E293B', borderBottom: '1px solid #334155' }}>
        <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: '#DC2626' }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round">
            <path d="M23 7l-7 5 7 5V7z"/><rect x="1" y="5" width="15" height="14" rx="2"/>
          </svg>
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-white font-bold text-sm leading-tight truncate">{junction.name}</div>
          <div className="text-slate-400 text-xs">{camId} · {junction.mode === 'adaptive' ? 'AI Adaptive' : 'Fixed'}</div>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full" style={{ background: '#0F172A', border: '1px solid #334155' }}>
            <div className="w-1.5 h-1.5 rounded-full bg-red-500 blink-fast"/>
            <span className="text-xs font-semibold text-white">LIVE</span>
          </div>
          <button onClick={() => onJunctionView(junction)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold text-white"
            style={{ background: '#1D4ED8' }}>
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
            </svg>
            Junction View
          </button>
        </div>
      </div>

      {/* Lane tabs */}
      <div className="flex gap-1.5 px-4 py-2.5" style={{ background: '#1E293B', borderBottom: '1px solid #334155' }}>
        {DIR_LABELS.map(d => {
          const ai = DIR_LABELS.indexOf(d);
          const sc = armSignals[DIR_ARMS[ai]];
          return (
            <button key={d} onClick={() => setActiveDir(d)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold transition-all"
              style={{
                background: activeDir === d ? '#1D4ED8' : '#334155',
                color: activeDir === d ? '#FFFFFF' : '#94A3B8',
              }}>
              <div className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                style={{ background: sigDisplay[sc] }}/>
              {d}
            </button>
          );
        })}
      </div>

      {/* Video feed */}
      <div className="relative" style={{ background: '#080b14' }}>
        <CCTVCanvas
          seed={cardIndex * 4 + dirIndex}
          signalColor={sigColor}
          direction={armKey}
          density={sig.vehicleDensity}
          onDetectionsChange={setDetections}
        />
        <div className="absolute inset-0 pointer-events-none cctv-overlay"/>

        {/* AI detection overlay */}
        <div className="absolute top-3 left-3 rounded-xl overflow-hidden"
          style={{ background: 'rgba(0,0,0,0.72)', border: '1px solid rgba(255,255,255,0.1)', backdropFilter: 'blur(4px)', minWidth: 145 }}>
          <div className="flex items-center gap-1.5 px-3 py-2 border-b" style={{ borderColor: 'rgba(255,255,255,0.1)' }}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#22C55E" strokeWidth="2" strokeLinecap="round">
              <rect x="1" y="3" width="15" height="13" rx="2"/><path d="M16 8h4l3 3v4h-7V8z"/>
              <circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/>
            </svg>
            <span className="text-xs font-bold text-white">AI Detection</span>
          </div>
          <div className="px-3 py-2.5 space-y-1.5">
            {([
              { label: 'Vehicles', value: detections.length },
              { label: 'Density',  value: `${sig.vehicleDensity}%` },
              { label: 'Signal',   value: sigColor.toUpperCase(), color: sigDisplay[sigColor] },
            ] as { label: string; value: string|number; color?: string }[]).map(row => (
              <div key={row.label} className="flex justify-between items-center gap-4">
                <span className="text-xs" style={{ color: '#94A3B8' }}>{row.label}:</span>
                <span className="text-xs font-bold" style={{ color: row.color ?? '#FFFFFF' }}>{row.value}</span>
              </div>
            ))}
          </div>
          {detections.slice(0, 3).map(v => (
            <div key={v.id} className="mx-2 mb-1.5 px-2 py-1 rounded text-xs"
              style={{ background: 'rgba(34,197,94,0.12)', border: '1px solid rgba(34,197,94,0.25)' }}>
              <div className="font-bold mono" style={{ color: '#22C55E', fontSize: 10 }}>{v.plate}</div>
              <div className="flex justify-between" style={{ color: '#64748B', fontSize: 10 }}>
                <span>{VBASE[v.type].label}</span><span>{v.confidence}%</span>
              </div>
            </div>
          ))}
        </div>

        {/* Signal panel */}
        <div className="absolute top-3 right-3 rounded-xl overflow-hidden"
          style={{ background: 'rgba(0,0,0,0.72)', border: '1px solid rgba(255,255,255,0.1)', backdropFilter: 'blur(4px)' }}>
          <div className="px-3 py-2 border-b text-center" style={{ borderColor: 'rgba(255,255,255,0.1)' }}>
            <span className="text-xs font-bold text-white">Signal</span>
          </div>
          <div className="px-3 py-2.5 flex flex-col items-center gap-1.5">
            {(['red','yellow','green'] as SigColor[]).map(c => (
              <div key={c} className="flex items-center gap-2 w-full">
                <div className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0"
                  style={{ background: sigColor === c ? sigDisplay[c] : '#374151' }}>
                  {sigColor === c && <div className="w-2 h-2 rounded-full bg-white opacity-60"/>}
                </div>
                <span className="text-xs font-semibold uppercase"
                  style={{ color: sigColor === c ? sigDisplay[c] : '#4B5563' }}>{c}</span>
              </div>
            ))}
          </div>
          <div className="mx-3 mb-3 rounded-lg p-2.5 text-center"
            style={{ background: sigDisplay[sigColor]+'20', border: `1px solid ${sigDisplay[sigColor]}40` }}>
            <div className="text-xs mb-0.5" style={{ color: '#94A3B8' }}>
              {phaseState.type === 'green' ? 'Green Time' : phaseState.type === 'yellow' ? 'Clearing' : 'All Red'}
            </div>
            <div className="text-3xl font-black mono leading-none" style={{ color: sigDisplay[sigColor] }}>
              {phaseState.timer}s
            </div>
          </div>
        </div>
      </div>

      {/* AI Decision Panel */}
      <AIDecisionPanel phase={phaseState} />
    </div>
  );
}

// ─── Junction View ────────────────────────────────────────────────────────────

function JunctionView({ junction, onBack }: { junction: Junction; onBack: () => void }) {
  const { armSignals, phaseState } = useJunctionSignal(junction, 99);
  const sigDisplay: Record<SigColor, string> = { red: '#DC2626', yellow: '#F59E0B', green: '#16A34A' };

  // Signal timeline
  const totalCycle = phaseState.greenDuration + 4 + 2; // green + yellow + allred
  const elapsed = totalCycle - phaseState.timer;
  const timelineProgress = Math.max(0, Math.min(1, elapsed / totalCycle));

  return (
    <div className="h-full flex flex-col overflow-hidden" style={{ background: '#0F172A' }}>
      {/* Header */}
      <div className="flex items-center gap-3 px-6 py-4 border-b flex-shrink-0" style={{ borderColor: 'rgba(255,255,255,0.08)' }}>
        <button onClick={onBack} className="text-slate-400 hover:text-white transition-colors">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M19 12H5M12 19l-7-7 7-7"/>
          </svg>
        </button>
        <div className="flex-1">
          <h2 className="text-white font-bold">{junction.name} — Junction View</h2>
          <div className="text-slate-400 text-xs">{junction.location}</div>
        </div>
        {/* Arm signal indicators */}
        <div className="flex items-center gap-2">
          {DIR_ARMS.map(arm => (
            <div key={arm} className="flex flex-col items-center gap-1">
              <div className="w-3 h-3 rounded-full" style={{ background: sigDisplay[armSignals[arm]] }}/>
              <span className="text-xs" style={{ color: '#475569' }}>{arm[0].toUpperCase()}</span>
            </div>
          ))}
        </div>
        <div className="flex items-center gap-1.5 ml-2">
          <div className="w-1.5 h-1.5 rounded-full bg-green-400 blink-fast"/>
          <span className="text-green-400 text-xs font-semibold">LIVE</span>
        </div>
      </div>

      {/* AI decision summary */}
      <div className="px-6 py-3 flex-shrink-0" style={{ background: '#1E293B', borderBottom: '1px solid #334155' }}>
        <div className="flex items-center gap-4">
          <span className="text-xs font-bold" style={{ color: '#818CF8' }}>AI Decision:</span>
          <span className="text-xs italic" style={{ color: '#94A3B8' }}>"{phaseState.aiReason}"</span>
          <span className="ml-auto text-xs mono px-2 py-0.5 rounded"
            style={{
              background: phaseState.type === 'green' ? '#14532D' : '#713F12',
              color: phaseState.type === 'green' ? '#22C55E' : '#F59E0B',
            }}>
            Phase: {phaseState.direction} {phaseState.type.toUpperCase()}
          </span>
        </div>
      </div>

      {/* 2×2 camera grid */}
      <div className="flex-1 overflow-auto p-4">
        <div className="grid grid-cols-2 gap-4 mb-4">
          {DIR_ARMS.map((arm, ai) => {
            const sig    = junction.signals[arm];
            const sigC   = armSignals[arm];
            const camId  = junction.cameras[ai] || `CAM-${ai+1}`;
            return (
              <div key={arm} className="rounded-xl overflow-hidden" style={{ background: '#1E293B', border: '1px solid #334155' }}>
                <div className="flex items-center gap-2 px-3 py-2 border-b" style={{ borderColor: '#334155' }}>
                  <div className="w-2.5 h-2.5 rounded-full" style={{ background: sigDisplay[sigC] }}/>
                  <span className="text-white text-xs font-bold uppercase">{arm} Approach</span>
                  <span className="mono text-xs ml-auto" style={{ color: sigDisplay[sigC] }}>
                    {sigC.toUpperCase()} {phaseState.timer}s
                  </span>
                  <span className="mono text-xs" style={{ color: '#475569' }}>{camId}</span>
                </div>
                <div className="relative">
                  <CCTVCanvas
                    seed={ai * 11 + 3}
                    signalColor={sigC}
                    direction={arm}
                    density={sig.vehicleDensity}
                    onDetectionsChange={() => {}}
                  />
                  <div className="cctv-overlay absolute inset-0 pointer-events-none"/>
                </div>
              </div>
            );
          })}
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-4 gap-3 mb-4">
          {DIR_ARMS.map(arm => {
            const sig = junction.signals[arm];
            const pressure = phaseState.pressure[arm];
            return (
              <div key={arm} className="rounded-xl p-3" style={{ background: '#1E293B', border: '1px solid #334155' }}>
                <div className="text-xs font-bold uppercase mb-2" style={{ color: '#64748B' }}>{arm}</div>
                {[
                  { label: 'Queue',    value: `${sig.queueLength} veh` },
                  { label: 'Speed',    value: `${sig.avgSpeed} km/h` },
                  { label: 'Wait',     value: `${sig.waitingTime}s` },
                  { label: 'Pressure', value: `${pressure}%`, highlight: pressure > 70 },
                ].map(s => (
                  <div key={s.label} className="flex justify-between text-xs mb-0.5">
                    <span style={{ color: '#475569' }}>{s.label}</span>
                    <span className="font-bold" style={{ color: s.highlight ? '#DC2626' : '#E2E8F0' }}>{s.value}</span>
                  </div>
                ))}
              </div>
            );
          })}
        </div>

        {/* Signal timeline */}
        <div className="rounded-xl p-4" style={{ background: '#1E293B', border: '1px solid #334155' }}>
          <div className="text-xs font-bold mb-3" style={{ color: '#94A3B8' }}>Signal Cycle Timeline</div>
          <div className="relative h-6 rounded-full overflow-hidden" style={{ background: '#0F172A' }}>
            {/* Green segment */}
            <div className="absolute inset-y-0 left-0 flex items-center justify-center text-xs font-bold text-white"
              style={{
                width: `${(phaseState.greenDuration / totalCycle) * 100}%`,
                background: '#16A34A',
                borderRadius: '999px 0 0 999px',
              }}>
              GREEN {phaseState.greenDuration}s
            </div>
            {/* Yellow segment */}
            <div className="absolute inset-y-0 flex items-center justify-center text-xs font-bold"
              style={{
                left: `${(phaseState.greenDuration / totalCycle) * 100}%`,
                width: `${(4 / totalCycle) * 100}%`,
                background: '#F59E0B',
                color: '#000',
              }}>
              4s
            </div>
            {/* Red segment */}
            <div className="absolute inset-y-0 flex items-center justify-center text-xs font-bold text-white"
              style={{
                left: `${((phaseState.greenDuration + 4) / totalCycle) * 100}%`,
                width: `${(2 / totalCycle) * 100}%`,
                background: '#DC2626',
                borderRadius: '0 999px 999px 0',
              }}>
              2s
            </div>
            {/* Progress cursor */}
            <div className="absolute top-0 bottom-0 w-0.5 bg-white opacity-90"
              style={{ left: `${timelineProgress * 100}%`, transition: 'left 1s linear' }}/>
          </div>
          <div className="flex justify-between text-xs mt-1" style={{ color: '#475569' }}>
            <span>Phase start</span>
            <span>Next phase: {phaseState.nextDirection} GREEN</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Live Feed Main ───────────────────────────────────────────────────────────

export default function LiveFeed({ initialJunctionId }: { initialJunctionId?: string }) {
  const { data: camData } = usePolling(() => api.getCamerasList(), 2000);

  const [junctionView, setJunctionView] = useState<Junction | null>(
    initialJunctionId ? JUNCTIONS.find(j => j.id === initialJunctionId) || null : null
  );
  const [page, setPage] = useState(0);

  if (junctionView) {
    return <JunctionView junction={junctionView} onBack={() => setJunctionView(null)} />;
  }

  const perPage    = 4;
  const totalPages = Math.ceil(JUNCTIONS.length / perPage);
  const visible    = JUNCTIONS.slice(page * perPage, page * perPage + perPage);
  const onlineCount = JUNCTIONS.length * 4;

  return (
    <div className="h-full flex flex-col overflow-hidden" style={{ background: '#F1F5F9' }}>
      {/* Header */}
      <div className="bg-white border-b px-6 py-4 flex items-center justify-between" style={{ borderColor: '#E2E8F0' }}>
        <div>
          <h1 className="text-xl font-bold" style={{ color: '#0F172A' }}>Live Camera Feeds</h1>
          <p className="text-sm mt-0.5" style={{ color: '#64748B' }}>
            AI-powered adaptive signal control with follow-leader vehicle physics
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full"
            style={{ background: '#F0FDF4', border: '1px solid #BBF7D0' }}>
            <div className="w-2 h-2 rounded-full bg-green-500 blink-fast"/>
            <span className="text-sm font-semibold" style={{ color: '#16A34A' }}>
              {onlineCount} Active Cameras
            </span>
          </div>
          {totalPages > 1 && (
            <div className="flex items-center gap-1">
              <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}
                className="w-8 h-8 rounded-lg flex items-center justify-center border transition-all disabled:opacity-30"
                style={{ borderColor: '#E2E8F0' }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#475569" strokeWidth="2"><path d="M15 18l-6-6 6-6"/></svg>
              </button>
              <span className="text-xs px-2" style={{ color: '#94A3B8' }}>{page+1}/{totalPages}</span>
              <button onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page === totalPages - 1}
                className="w-8 h-8 rounded-lg flex items-center justify-center border transition-all disabled:opacity-30"
                style={{ borderColor: '#E2E8F0' }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#475569" strokeWidth="2"><path d="M9 18l6-6-6-6"/></svg>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Camera grid */}
      <div className="flex-1 overflow-y-auto p-5">
        <div className="grid grid-cols-2 gap-5">
          {visible.map((junction, i) => (
            <CameraCard
              key={junction.id}
              junction={junction}
              cardIndex={page * perPage + i}
              onJunctionView={setJunctionView}
              camData={camData}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
