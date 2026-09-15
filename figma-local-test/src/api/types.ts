export interface ComponentHealth {
  status: 'ok' | 'degraded' | 'error';
  message?: string;
}

export interface SystemHealthResponse {
  status: 'healthy' | 'unhealthy';
  database: ComponentHealth;
  models: ComponentHealth;
  active_workers: number;
  timestamp: string;
}

export interface ProcessingOverviewResponse {
  total_cameras: number;
  active_cameras: number;
  idle_cameras: number;
  stopped_cameras: number;
  failed_cameras: number;
  total_processed_frames: number;
  aggregate_fps: number;
  average_frame_latency_ms: number | null;
  total_active_vehicles: number;
  total_plates_detected: number;
  system_status: 'OPTIMAL' | 'DEGRADED' | 'IDLE';
  timestamp: string;
}

export interface LatestFrameSnapshot {
  frame_number: number;
  active_vehicle_count: number;
  plate_observations_count: number;
  queue_length: number;
  moving_vehicles: number;
  stationary_vehicles: number;
  traffic_pressure: number;
  traffic_level: string;
}

export interface ProcessingStatusResponse {
  camera_id: string;
  state: 'IDLE' | 'STARTING' | 'RUNNING' | 'STOPPING' | 'STOPPED' | 'FAILED';
  start_time: string | null;
  end_time: string | null;
  elapsed_seconds: number | null;
  processed_frames: number;
  fps: number;
  error_message: string | null;
  latest_frame: LatestFrameSnapshot | null;
  last_frame_processed_at: string | null;
  seconds_since_last_frame_processed: number | null;
  average_frame_latency_ms: number | null;
}

export interface CamerasListResponse {
  cameras: ProcessingStatusResponse[];
  active_count: number;
}

export interface VehicleResponse {
  vehicle_id: string;
  canonical_plate_text: string | null;
  canonical_vehicle_type: string;
  first_detected_at: string;
  last_detected_at: string;
  total_detections_count: number;
  is_stolen: boolean;
  is_wanted: boolean;
  notes: string | null;
}

export interface VehicleTrackResponse {
  track_session_id: string;
  vehicle_id: string | null;
  camera_id: string;
  local_track_id: number;
  vehicle_type: string;
  confidence: number;
  best_confidence: number | null;
  first_seen_at: string;
  last_seen_at: string;
  first_seen_frame: number;
  last_seen_frame: number;
  frames_tracked: number;
  last_bbox: number[];
  center: number[] | null;
  trajectory_summary: any[];
  type_history: string[];
}

export interface PlateObservationResponse {
  observation_id: string;
  plate_text: string;
  raw_plate_text: string | null;
  camera_id: string;
  track_session_id: string | null;
  vehicle_id: string | null;
  frame_number: number;
  timestamp: string;
  detection_confidence: number;
  ocr_confidence: number;
  association_confidence: number | null;
  bbox: number[];
  vehicle_bbox: number[] | null;
  crop_image_uri: string | null;
  ocr_variant: string | null;
  coordinate_space: string;
}

export interface VehicleHistoryResponse {
  vehicle: VehicleResponse;
  tracks: VehicleTrackResponse[];
  plate_observations: PlateObservationResponse[];
}
