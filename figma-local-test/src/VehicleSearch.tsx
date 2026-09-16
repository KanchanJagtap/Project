import { useState, useEffect, useRef } from 'react';
import { JUNCTIONS, type VehicleProfile, type Detection, VEHICLE_DB } from './data';
import { api } from './api/client';

const TRAJECTORY_CAMS = ['CAM-01', 'CAM-04', 'CAM-07', 'CAM-12', 'CAM-18', 'CAM-22'];

function TrajectoryMap({ detections }: { detections: Detection[] }) {
  if (detections.length < 2) return null;
  const nodes = detections.slice(0, 6);
  const W = 600;
  const H = 120;
  const spacing = W / Math.max(nodes.length, 1);

  return (
    <div className="rounded-xl overflow-hidden border" style={{ borderColor: '#E2E8F0', background: '#F8FAFC' }}>
      <div className="px-4 py-2 border-b" style={{ borderColor: '#E2E8F0' }}>
        <span className="text-xs font-bold" style={{ color: '#0F172A' }}>Multi-Camera Trajectory</span>
      </div>
      <div className="p-4 overflow-x-auto">
        <svg width={Math.max(W, nodes.length * 130)} height={H} viewBox={`0 0 ${Math.max(W, nodes.length * 130)} ${H}`}>
          {nodes.map((d, i) => {
            const x = 65 + i * 130;
            const isLast = i === nodes.length - 1;
            return (
              <g key={i}>
                {/* Connector line */}
                {i < nodes.length - 1 && (
                  <g>
                    <line x1={x + 30} y1={H / 2} x2={x + 100} y2={H / 2}
                      stroke="#CBD5E1" strokeWidth="2" strokeDasharray="4 3"/>
                    <polygon points={`${x + 100},${H / 2 - 4} ${x + 100},${H / 2 + 4} ${x + 110},${H / 2}`}
                      fill="#94A3B8"/>
                  </g>
                )}
                {/* Node */}
                <circle cx={x} cy={H / 2} r={22} fill={isLast ? '#1D4ED8' : '#E2E8F0'} stroke={isLast ? '#1D4ED8' : '#CBD5E1'} strokeWidth="2"/>
                <text x={x} y={H / 2 - 5} textAnchor="middle" fontSize="9" fontWeight="bold"
                  fill={isLast ? 'white' : '#0F172A'} fontFamily="JetBrains Mono, monospace">
                  {d.cameraId}
                </text>
                <text x={x} y={H / 2 + 7} textAnchor="middle" fontSize="7"
                  fill={isLast ? 'rgba(255,255,255,0.8)' : '#64748B'} fontFamily="Inter, sans-serif">
                  {d.speed}km/h
                </text>
                {/* Time below node */}
                <text x={x} y={H - 8} textAnchor="middle" fontSize="8"
                  fill="#94A3B8" fontFamily="JetBrains Mono, monospace">
                  {d.timestamp.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false })}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}

function VehicleCard({ profile }: { profile: VehicleProfile }) {
  const typeIcon = {
    car: '🚗', truck: '🚛', bus: '🚌', motorcycle: '🏍️', auto: '🛺', suv: '🚙',
  }[profile.vehicleType];

  return (
    <div className="grid grid-cols-3 gap-4 rounded-xl p-4 border" style={{ borderColor: '#E2E8F0', background: '#F8FAFC' }}>
      <div className="col-span-1">
        <div className="w-full h-28 rounded-lg flex items-center justify-center text-5xl"
          style={{ background: '#E2E8F0' }}>
          {typeIcon}
        </div>
      </div>
      <div className="col-span-2 space-y-2">
        <div className="mono text-2xl font-bold" style={{ color: '#0F172A' }}>{profile.plate}</div>
        <div className="grid grid-cols-2 gap-2 text-xs">
          {[
            { label: 'Owner', value: profile.owner },
            { label: 'Phone', value: profile.phone },
            { label: 'Vehicle', value: `${profile.make} ${profile.model}` },
            { label: 'Color', value: profile.color },
            { label: 'State', value: profile.registrationState },
            { label: 'Registered', value: profile.registrationDate },
          ].map(d => (
            <div key={d.label}>
              <span style={{ color: '#94A3B8' }}>{d.label}: </span>
              <span className="font-semibold" style={{ color: '#0F172A' }}>{d.value}</span>
            </div>
          ))}
        </div>
        <div className="flex items-center gap-2 mt-2">
          <span className="text-xs font-bold px-2 py-0.5 rounded"
            style={{ background: profile.violations > 3 ? '#FEF2F2' : '#F0FDF4', color: profile.violations > 3 ? '#DC2626' : '#16A34A' }}>
            {profile.violations} Violations
          </span>
          {profile.isTracked && (
            <span className="text-xs font-bold px-2 py-0.5 rounded blink-fast" style={{ background: '#1D4ED8', color: 'white' }}>
              TRACKING ACTIVE
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

export default function VehicleSearch() {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState<VehicleProfile | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [backendError, setBackendError] = useState(false);
  const [tracking, setTracking] = useState<Record<string, boolean>>({});
  const [recentDetection, setRecentDetection] = useState<{ cam: string; junction: string; time: Date } | null>(null);
  const [liveAlert, setLiveAlert] = useState(false);

  const [anprLoading, setAnprLoading] = useState(false);
  const [anprError, setAnprError] = useState('');
  const [anprResult, setAnprResult] = useState<{
    plate_number: string;
    detection_confidence: number;
    ocr_confidence: number;
    vehicle_found: boolean;
  } | null>(null);

  const [anprChooserOpen, setAnprChooserOpen] = useState(false);
  const [cameraOpen, setCameraOpen] = useState(false);
  const [cameraError, setCameraError] = useState('');

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const mediaInputRef = useRef<HTMLInputElement | null>(null);
  const cameraStreamRef = useRef<MediaStream | null>(null);

  const stopCamera = () => {
    if (cameraStreamRef.current) {
      cameraStreamRef.current.getTracks().forEach(track => track.stop());
      cameraStreamRef.current = null;
    }

    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }

    setCameraOpen(false);
  };

  const startCamera = async () => {
    setAnprChooserOpen(false);
    setCameraError('');

    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraError('Camera access is not supported by this browser.');
      setCameraOpen(true);
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: 'environment' },
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      });

      cameraStreamRef.current = stream;
      setCameraOpen(true);
    } catch (error) {
      console.error('Camera access error:', error);

      setCameraError(
        'Camera access was denied or is unavailable. Please allow camera permission and try again.'
      );

      setCameraOpen(true);
    }
  };

  useEffect(() => {
    if (!cameraOpen) return;

    const video = videoRef.current;
    const stream = cameraStreamRef.current;

    if (!video || !stream) return;

    video.srcObject = stream;
    video.muted = true;
    video.autoplay = true;
    video.playsInline = true;

    const startPlayback = async () => {
      try {
        await video.play();
      } catch (error) {
        console.warn('Camera playback could not start automatically:', error);
      }
    };

    if (video.readyState >= 1) {
      startPlayback();
    } else {
      video.onloadedmetadata = startPlayback;
    }

    return () => {
      video.onloadedmetadata = null;
    };
  }, [cameraOpen]);

  const handleMediaSelection = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];

    if (file) {
      setAnprChooserOpen(false);
      handleRealANPR(file);
    }

    e.currentTarget.value = '';
  };

  const openMediaPicker = () => {
    setAnprChooserOpen(false);
    mediaInputRef.current?.click();
  };

  const captureFromCamera = () => {
    const video = videoRef.current;

    if (!video || video.readyState < 2) {
      setCameraError(
        'Camera is not ready yet. Please wait a moment and try again.'
      );
      return;
    }

    const canvas = document.createElement('canvas');

    canvas.width = video.videoWidth || 1280;
    canvas.height = video.videoHeight || 720;

    const context = canvas.getContext('2d');

    if (!context) {
      setCameraError('Unable to capture the camera frame.');
      return;
    }

    context.drawImage(
      video,
      0,
      0,
      canvas.width,
      canvas.height
    );

    canvas.toBlob(blob => {
      if (!blob) {
        setCameraError('Unable to create the captured image.');
        return;
      }

      const file = new File(
        [blob],
        `anpr-camera-${Date.now()}.jpg`,
        { type: 'image/jpeg' }
      );

      stopCamera();
      handleRealANPR(file);
    }, 'image/jpeg', 0.92);
  };

  useEffect(() => {
    return () => {
      if (cameraStreamRef.current) {
        cameraStreamRef.current
          .getTracks()
          .forEach(track => track.stop());

        cameraStreamRef.current = null;
      }
    };
  }, []);

  const performSearch = async (plateStr: string) => {
    setNotFound(false);
    setRecentDetection(null);
    setLiveAlert(false);
    setBackendError(false);

    const plate = plateStr.trim().toUpperCase();
    setQuery(plate);

    if (!plate) {
      setResult(null);
      setNotFound(true);
      return false;
    }

    setIsLoading(true);

    try {
      const history = await api.getVehicleHistory(plate);
      
      const mappedProfile: VehicleProfile = {
        plate: history.vehicle.canonical_plate_text || plate,
        owner: 'Not available',
        phone: 'Not available',
        vehicleType: (history.vehicle.canonical_vehicle_type as any) || 'car',
        make: 'Not available',
        model: 'Not available',
        color: 'Not available',
        registrationState: 'Not available',
        registrationDate: 'Not available',
        violations: history.vehicle.is_stolen || history.vehicle.is_wanted ? 1 : 0,
        detections: history.tracks.map((t: any) => {
          // Find associated plate observation if it exists (same track session)
          const obs = history.plate_observations.find((o: any) => o.track_session_id === t.track_session_id);
          return {
            cameraId: t.camera_id,
            junctionName: t.junction_name || t.camera_name || `Camera ${t.camera_id}`,
            timestamp: new Date(t.last_seen_at),
            first_seen_at: new Date(t.first_seen_at),
            track_session_id: t.track_session_id,
            local_track_id: t.local_track_id,
            vehicle_type: t.vehicle_type,
            plate_text: obs ? obs.plate_text : 'Unknown',
            direction: 'N/A',
            speed: -1,
            confidence: Math.round(t.confidence * 100),
          };
        }).sort((a: any, b: any) => b.timestamp.getTime() - a.timestamp.getTime()),
        isTracked: false,
      };
      
      setResult(mappedProfile);
      return true;
    } catch (err: any) {
      if (err.message && (err.message.includes('Not found') || err.message.includes('404'))) {
        const localProfile = VEHICLE_DB[plate];
        if (localProfile) {
          setResult(localProfile);
          return true;
        }
        setResult(null);
        setNotFound(true);
      } else {
        setBackendError(true);
      }
      return false;
    } finally {
      setIsLoading(false);
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    await performSearch(query);
  };

  const handleRealANPR = async (file: File) => {
    setAnprLoading(true);
    setAnprError('');
    setAnprResult(null);
    setNotFound(false);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch(
        '/api/processing/anpr_scan',
        {
          method: 'POST',
          body: formData,
        }
      );

      if (!response.ok) {
        throw new Error('ANPR server returned an error.');
      }

      const data = await response.json();

      if (
        !data.detections ||
        data.detections.length === 0
      ) {
        throw new Error(
          'No license plate was detected in this image.'
        );
      }

      const detection = data.detections[0];
      const plateNumber = String(
        detection.plate_number || ''
      ).toUpperCase();

      const found = await performSearch(plateNumber);

      setAnprResult({
        plate_number: plateNumber,
        detection_confidence:
          Number(detection.detection_confidence || 0),
        ocr_confidence:
          Number(detection.ocr_confidence || 0),
        vehicle_found: found,
      });
    } catch (error) {
      setAnprError(
        error instanceof Error
          ? error.message
          : 'Unable to process the image.'
      );
    } finally {
      setAnprLoading(false);
    }
  };

  const handleStartTracking = (plate: string) => {
    setTracking(prev => ({ ...prev, [plate]: true }));
    if (result) {
      setResult(prev => prev ? { ...prev, isTracked: true } : null);
    }
    // Simulate a detection after 8 seconds
    setTimeout(() => {
      const j = JUNCTIONS[Math.floor(Math.random() * JUNCTIONS.length)];
      const cam = j.cameras[Math.floor(Math.random() * j.cameras.length)];
      setRecentDetection({ cam, junction: j.name, time: new Date() });
      setLiveAlert(true);
      setTimeout(() => setLiveAlert(false), 5000);
    }, 8000);
  };

  const quickPlates = Object.keys(VEHICLE_DB);

  return (
    <div className="h-full flex flex-col overflow-hidden" style={{ background: '#F8FAFC' }}>
      {/* Header */}
      <div className="bg-white border-b px-6 py-4" style={{ borderColor: '#E2E8F0' }}>
        <h1 className="text-xl font-bold mb-3" style={{ color: '#0F172A' }}>Vehicle Search & Tracking</h1>

        {/* Search form */}
        <form onSubmit={handleSearch} className="flex gap-3">
          <div className="flex-1 relative">
            <input
              value={query}
              onChange={e => setQuery(e.target.value.toUpperCase())}
              placeholder="Enter number plate (e.g. MH12AB1234)"
              className="w-full px-4 py-3 pl-10 rounded-xl border text-sm mono outline-none font-semibold"
              style={{ borderColor: '#CBD5E1', color: '#0F172A' }}
              onFocus={e => e.target.style.borderColor = '#1D4ED8'}
              onBlur={e => e.target.style.borderColor = '#CBD5E1'}
            />
            <svg className="absolute left-3 top-3.5" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#94A3B8" strokeWidth="2">
              <circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/>
            </svg>
          </div>
          <button type="submit" className="px-6 py-3 rounded-xl font-semibold text-white text-sm"
            style={{ background: '#1D4ED8' }}>
            Search
          </button>

        <button
          type="button"
          disabled={anprLoading}
          onClick={() => {
            setAnprError('');
            setAnprChooserOpen(true);
          }}
          className="px-5 py-3 rounded-xl font-semibold text-sm border transition-all hover:bg-blue-50 disabled:opacity-60 disabled:cursor-not-allowed"
          style={{
            color: '#1D4ED8',
            borderColor: '#BFDBFE',
            background: '#FFFFFF',
          }}
        >
          {anprLoading ? 'Scanning...' : '📷 Real ANPR Scan'}
        </button>

        <input
          ref={mediaInputRef}
          type="file"
          accept="image/*,video/*"
          className="hidden"
          disabled={anprLoading}
          onChange={handleMediaSelection}
        />
        </form>

        {anprChooserOpen && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            style={{ background: 'rgba(15, 23, 42, 0.55)' }}
          >
            <div
              className="w-full max-w-md rounded-2xl bg-white shadow-2xl border"
              style={{ borderColor: '#E2E8F0' }}
            >
              <div className="p-6">
                <div className="flex items-start justify-between mb-5">
                  <div>
                    <h3
                      className="text-lg font-bold"
                      style={{ color: '#0F172A' }}
                    >
                      Real ANPR Scan
                    </h3>

                    <p
                      className="text-sm mt-1"
                      style={{ color: '#64748B' }}
                    >
                      Choose how you want to provide the vehicle image.
                    </p>
                  </div>

                  <button
                    type="button"
                    onClick={() => setAnprChooserOpen(false)}
                    className="w-8 h-8 rounded-lg flex items-center justify-center text-lg"
                    style={{
                      color: '#64748B',
                      background: '#F8FAFC',
                    }}
                  >
                    ×
                  </button>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={startCamera}
                    className="rounded-xl border p-5 text-left transition-all hover:bg-blue-50 hover:border-blue-300"
                    style={{ borderColor: '#BFDBFE' }}
                  >
                    <div className="text-3xl mb-3">📷</div>

                    <div
                      className="font-semibold"
                      style={{ color: '#0F172A' }}
                    >
                      Capture by Camera
                    </div>

                    <div
                      className="text-xs mt-1"
                      style={{ color: '#64748B' }}
                    >
                      Use your laptop camera
                    </div>
                  </button>

                  <button
                    type="button"
                    onClick={openMediaPicker}
                    className="rounded-xl border p-5 text-left transition-all hover:bg-blue-50 hover:border-blue-300"
                    style={{ borderColor: '#BFDBFE' }}
                  >
                    <div className="text-3xl mb-3">🖼️</div>

                    <div
                      className="font-semibold"
                      style={{ color: '#0F172A' }}
                    >
                      Select from Media
                    </div>

                    <div
                      className="text-xs mt-1"
                      style={{ color: '#64748B' }}
                    >
                      Choose an image or video
                    </div>
                  </button>
                </div>

                <div
                  className="mt-4 rounded-lg p-3 text-xs"
                  style={{
                    background: '#F8FAFC',
                    color: '#64748B',
                  }}
                >
                  The selected image is sent to the same AI ANPR engine used
                  by the existing Real ANPR Scan.
                </div>
              </div>
            </div>
          </div>
        )}

        {cameraOpen && (
          <div
            className="fixed inset-0 z-[60] flex items-center justify-center p-4"
            style={{ background: 'rgba(15, 23, 42, 0.75)' }}
          >
            <div className="w-full max-w-3xl rounded-2xl bg-white shadow-2xl overflow-hidden">
              <div
                className="flex items-center justify-between px-5 py-4 border-b"
                style={{ borderColor: '#E2E8F0' }}
              >
                <div>
                  <h3
                    className="font-bold"
                    style={{ color: '#0F172A' }}
                  >
                    Capture Vehicle Image
                  </h3>

                  <p
                    className="text-xs mt-1"
                    style={{ color: '#64748B' }}
                  >
                    Position the license plate clearly inside the camera view.
                  </p>
                </div>

                <button
                  type="button"
                  onClick={stopCamera}
                  className="w-8 h-8 rounded-lg flex items-center justify-center text-lg"
                  style={{
                    color: '#64748B',
                    background: '#F8FAFC',
                  }}
                >
                  ×
                </button>
              </div>

              <div className="p-5">
                {cameraError ? (
                  <div
                    className="rounded-xl p-4 border"
                    style={{
                      background: '#FEF2F2',
                      borderColor: '#FECACA',
                      color: '#B91C1C',
                    }}
                  >
                    <div className="font-semibold mb-1">
                      Camera unavailable
                    </div>

                    <div className="text-sm">
                      {cameraError}
                    </div>
                  </div>
                ) : (
                  <div className="relative rounded-xl overflow-hidden bg-black aspect-video">
                    <video
                      ref={videoRef}
                      autoPlay
                      playsInline
                      muted
                      className="w-full h-full object-cover"
                    />

                    <div className="absolute inset-0 pointer-events-none flex items-center justify-center">
                      <div
                        className="w-[72%] h-[38%] rounded-xl border-2"
                        style={{ borderColor: '#60A5FA' }}
                      />
                    </div>

                    <div className="absolute bottom-3 left-0 right-0 text-center">
                      <span
                        className="inline-block px-3 py-1 rounded-full text-xs font-medium"
                        style={{
                          background: 'rgba(15,23,42,0.75)',
                          color: '#FFFFFF',
                        }}
                      >
                        Align license plate inside the guide
                      </span>
                    </div>
                  </div>
                )}

                <div className="flex justify-end gap-3 mt-4">
                  <button
                    type="button"
                    onClick={stopCamera}
                    className="px-5 py-2.5 rounded-xl border font-semibold text-sm"
                    style={{
                      borderColor: '#CBD5E1',
                      color: '#475569',
                    }}
                  >
                    Cancel
                  </button>

                  {!cameraError && (
                    <button
                      type="button"
                      onClick={captureFromCamera}
                      disabled={anprLoading}
                      className="px-6 py-2.5 rounded-xl font-semibold text-sm text-white disabled:opacity-60"
                      style={{ background: '#1D4ED8' }}
                    >
                      {anprLoading ? 'Scanning...' : '📸 Capture & Scan'}
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Quick access */}
        <div className="flex items-center gap-2 mt-3">
          <span className="text-xs" style={{ color: '#94A3B8' }}>Quick:</span>
          {quickPlates.map(p => (
            <button key={p} onClick={() => { setQuery(p); }}
              className="text-xs px-2.5 py-1 rounded-lg border mono font-semibold transition-all hover:border-blue-300"
              style={{ borderColor: '#E2E8F0', color: '#475569' }}>
              {p}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-5">
        {/* Live alert */}
        {liveAlert && recentDetection && (
          <div className="rounded-xl p-4 border-l-4 blink-fast"
            style={{ background: '#EFF6FF', borderColor: '#1D4ED8' }}>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full flex items-center justify-center"
                style={{ background: '#1D4ED8', color: 'white', fontSize: 20 }}>📡</div>
              <div>
                <div className="font-bold text-sm" style={{ color: '#0F172A' }}>
                  🚨 Vehicle Re-spotted! — {result?.plate}
                </div>
                <div className="text-xs mt-0.5" style={{ color: '#1D4ED8' }}>
                  Detected at <strong>{recentDetection.cam}</strong> — {recentDetection.junction}
                  {' '} · {recentDetection.time.toLocaleTimeString('en-IN')}
                </div>
              </div>
            </div>
          </div>
        )}


      {/* Real ANPR result */}
      {anprResult && (
        <div
          className="rounded-xl border overflow-hidden"
          style={{ borderColor: '#BFDBFE', background: '#FFFFFF' }}
        >
          <div
            className="px-4 py-3 border-b flex items-center justify-between"
            style={{ borderColor: '#DBEAFE', background: '#EFF6FF' }}
          >
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-blue-600" />
              <span className="text-sm font-bold" style={{ color: '#1E3A8A' }}>
                REAL ANPR RESULT
              </span>
            </div>
            <span className="text-xs font-semibold" style={{ color: '#2563EB' }}>
              AI Engine Online
            </span>
          </div>

          <div className="grid grid-cols-4 gap-4 p-4">
            <div>
              <div className="text-xs" style={{ color: '#94A3B8' }}>Detected Plate</div>
              <div className="mono font-bold text-base mt-1" style={{ color: '#0F172A' }}>
                {anprResult.plate_number || '—'}
              </div>
            </div>

            <div>
              <div className="text-xs" style={{ color: '#94A3B8' }}>Plate Detection</div>
              <div className="font-bold text-base mt-1" style={{ color: '#0F172A' }}>
                {(anprResult.detection_confidence * 100).toFixed(1)}%
              </div>
            </div>

            <div>
              <div className="text-xs" style={{ color: '#94A3B8' }}>OCR Confidence</div>
              <div className="font-bold text-base mt-1" style={{ color: '#0F172A' }}>
                {(anprResult.ocr_confidence * 100).toFixed(1)}%
              </div>
            </div>

            <div>
              <div className="text-xs" style={{ color: '#94A3B8' }}>Registry Status</div>
              <div
                className="font-bold text-sm mt-1"
                style={{ color: anprResult.vehicle_found ? '#16A34A' : '#D97706' }}
              >
                {anprResult.vehicle_found
                  ? 'Vehicle Found'
                  : 'Not in Demo Registry'}
              </div>
            </div>
          </div>

        </div>
      )}

      {anprError && (
        <div className="rounded-xl border overflow-hidden p-4 mb-4" style={{ borderColor: '#FECACA', background: '#FEF2F2' }}>
          <div className="flex items-center gap-2 mb-1">
            <span className="w-2 h-2 rounded-full bg-red-600" />
            <span className="text-sm font-bold" style={{ color: '#991B1B' }}>ANPR ERROR</span>
          </div>
          <div className="text-sm" style={{ color: '#DC2626' }}>{anprError}</div>
        </div>
      )}

        {/* Not found */}
        {notFound && !isLoading && !backendError && (
          <div className="rounded-xl p-6 text-center border" style={{ borderColor: '#E2E8F0', background: 'white' }}>
            <div className="text-4xl mb-3">🔍</div>
            <div className="font-bold text-lg" style={{ color: '#0F172A' }}>Vehicle Not Currently Detected</div>
            <div className="text-sm mt-1" style={{ color: '#64748B' }}>
              <span className="mono font-bold">{query}</span> was detected successfully, but no matching record exists in the prototype vehicle registry.
            </div>
            <div className="mt-3 text-xs" style={{ color: '#94A3B8' }}>
              The AI detection is working, but vehicle details are unavailable in the current demo registry.
            </div>
          </div>
        )}

        {/* Result */}
        {result && !isLoading && !backendError && (
          <div className="space-y-5">
            {/* Vehicle card */}
            <div className="bg-white rounded-xl border overflow-hidden" style={{ borderColor: '#E2E8F0' }}>
              <div className="px-4 py-3 border-b flex items-center justify-between" style={{ borderColor: '#E2E8F0' }}>
                <span className="text-sm font-bold" style={{ color: '#0F172A' }}>Vehicle Profile</span>
                {!result.isTracked ? (
                  <button onClick={() => handleStartTracking(result.plate)}
                    className="px-4 py-1.5 rounded-lg text-xs font-bold text-white flex items-center gap-2"
                    style={{ background: '#1D4ED8' }}>
                    <span className="w-1.5 h-1.5 rounded-full bg-white blink-fast"/>
                    Start Tracking
                  </button>
                ) : (
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-blue-500 blink-fast"/>
                    <span className="text-xs font-bold" style={{ color: '#1D4ED8' }}>Tracking Active</span>
                  </div>
                )}
              </div>
              <div className="p-4">
                <VehicleCard profile={result} />
              </div>
            </div>

            {/* Trajectory map */}
            {result.detections.length >= 2 && (
              <div className="bg-white rounded-xl border overflow-hidden" style={{ borderColor: '#E2E8F0' }}>
                <div className="px-4 py-3 border-b" style={{ borderColor: '#E2E8F0' }}>
                  <span className="text-sm font-bold" style={{ color: '#0F172A' }}>Movement Trajectory</span>
                </div>
                <div className="p-4">
                  <TrajectoryMap detections={result.detections} />
                </div>
              </div>
            )}

            {/* Detection history */}
            <div className="bg-white rounded-xl border overflow-hidden" style={{ borderColor: '#E2E8F0' }}>
              <div className="px-4 py-3 border-b" style={{ borderColor: '#E2E8F0' }}>
                <span className="text-sm font-bold" style={{ color: '#0F172A' }}>Detection History</span>
              </div>
              <div className="divide-y" style={{ borderColor: '#F1F5F9' }}>
                {result.detections.map((d, i) => (
                  <div key={i} className="flex items-center gap-4 px-4 py-3">
                    <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                      style={{ background: '#EFF6FF', color: '#1D4ED8' }}>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M23 7l-7 5 7 5V7z"/><rect x="1" y="5" width="15" height="14" rx="2"/>
                      </svg>
                    </div>
                    <div className="flex-1">
                      <div className="flex justify-between items-start">
                        <div className="text-sm font-semibold" style={{ color: '#0F172A' }}>
                          {d.junctionName}
                        </div>
                        <div className="mono text-xs font-semibold" style={{ color: '#1D4ED8' }}>{d.cameraId}</div>
                      </div>
                      <div className="text-xs mt-1 grid grid-cols-2 gap-x-2 gap-y-1" style={{ color: '#64748B' }}>
                        <div><span className="font-semibold">Type:</span> {(d as any).vehicle_type || 'Unknown'}</div>
                        <div><span className="font-semibold">Plate Read:</span> {(d as any).plate_text || 'None'}</div>
                        <div><span className="font-semibold">Track ID:</span> {(d as any).local_track_id !== undefined ? (d as any).local_track_id : 'N/A'}</div>
                        <div><span className="font-semibold">Session:</span> {(d as any).track_session_id ? (d as any).track_session_id.substring(0, 8) : 'N/A'}...</div>
                        <div><span className="font-semibold">First Seen:</span> {(d as any).first_seen_at ? (d as any).first_seen_at.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }) : 'N/A'}</div>
                        <div><span className="font-semibold">Last Seen:</span> {d.timestamp.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}</div>
                        <div>{d.direction} · {d.speed >= 0 ? `Speed: ${d.speed} km/h` : 'Speed: N/A'}</div>
                        <div style={{ color: '#16A34A' }}>Track Conf: {d.confidence}%</div>
                      </div>
                    </div>
                  </div>
                ))}
                {recentDetection && (
                  <div className="flex items-center gap-4 px-4 py-3"
                    style={{ background: '#EFF6FF' }}>
                    <div className="w-8 h-8 rounded-lg flex items-center justify-center"
                      style={{ background: '#1D4ED8', color: 'white' }}>
                      📡
                    </div>
                    <div className="flex-1">
                      <div className="text-sm font-bold" style={{ color: '#1D4ED8' }}>
                        {recentDetection.junction} — LIVE DETECTION
                      </div>
                      <div className="text-xs mt-0.5" style={{ color: '#3B82F6' }}>
                        Vehicle spotted by tracking system
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="mono text-xs font-semibold" style={{ color: '#1D4ED8' }}>{recentDetection.cam}</div>
                      <div className="mono text-xs" style={{ color: '#64748B' }}>
                        {recentDetection.time.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false })}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Violations history */}
            {result.violations > 0 && (
              <div className="rounded-xl p-4 border-l-4" style={{ background: '#FEF2F2', borderColor: '#DC2626' }}>
                <div className="font-semibold text-sm mb-1" style={{ color: '#DC2626' }}>
                  ⚠ {result.violations} recorded violations
                </div>
                <div className="text-xs" style={{ color: '#64748B' }}>
                  This vehicle has a history of traffic violations. Enhanced monitoring active.
                </div>
              </div>
            )}
          </div>
        )}

        {/* Loading state */}
        {isLoading && (
          <div className="rounded-xl p-10 text-center border bg-white" style={{ borderColor: '#E2E8F0' }}>
            <div className="text-5xl mb-4 blink-fast">⏳</div>
            <div className="font-bold text-lg mb-2" style={{ color: '#0F172A' }}>Searching...</div>
            <div className="text-sm" style={{ color: '#64748B' }}>
              Retrieving vehicle profile and trajectory history from the database.
            </div>
          </div>
        )}
        
        {/* Error state */}
        {backendError && !isLoading && (
          <div className="rounded-xl p-10 text-center border bg-white" style={{ borderColor: '#DC2626' }}>
            <div className="text-5xl mb-4">⚠️</div>
            <div className="font-bold text-lg mb-2" style={{ color: '#DC2626' }}>Backend Error</div>
            <div className="text-sm" style={{ color: '#64748B' }}>
              Could not connect to the real PostgreSQL backend API to retrieve vehicle history.
            </div>
          </div>
        )}

        {/* Default state */}
        {!result && !notFound && !isLoading && !backendError && (
          <div className="rounded-xl p-10 text-center border bg-white" style={{ borderColor: '#E2E8F0' }}>
            <div className="text-5xl mb-4">🔍</div>
            <div className="font-bold text-lg mb-2" style={{ color: '#0F172A' }}>Search Any Vehicle</div>
            <div className="text-sm" style={{ color: '#64748B' }}>
              Enter a vehicle registration number to view its profile, detection history,
              violations record and real-time location tracking.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
